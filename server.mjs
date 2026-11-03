import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';

const APP_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const ID_PATTERN = /^[a-zA-Z0-9_-]{8,80}$/;
const MAX_BODY_BYTES = 128 * 1024;
const MAX_MESSAGE_LENGTH = 24000;
const TURN_TIMEOUT_MS = 10 * 60 * 1000;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function sendJson(response, status, payload) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(payload));
}

async function readJson(request) {
  if (!/^application\/json(?:\s*;|$)/i.test(request.headers['content-type'] || '')) {
    throw new HttpError(415, '請使用 application/json 傳送訊息。');
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new HttpError(413, '訊息過長，請縮短後再試。');
    chunks.push(chunk);
  }
  let payload;
  try {
    payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new HttpError(400, '無法讀取訊息內容。');
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new HttpError(400, '訊息格式不正確。');
  }
  return payload;
}

function explainError(error) {
  const message = error instanceof Error ? error.message : String(error);
  if (/not logged in|unauthorized|authentication|401|refresh token/i.test(message)) {
    return 'Codex 登入需要確認。請在同一個電腦帳戶的 CMD 執行 codex login，再重新送出。';
  }
  if (/rate.limit|usage.limit|quota|429/i.test(message)) {
    return 'Codex 目前達到用量或速率限制，請稍後再試，或在 Codex 檢查可用額度。';
  }
  if (/ENOENT|Cannot find|Missing.*Codex|Could not resolve/i.test(message)) {
    return '找不到 Codex 套件或執行檔。請在本資料夾執行 npm install @openai/codex-sdk @openai/codex，然後重啟服務。';
  }
  return ('Codex 回報：' + message).slice(0,2200);
}

function toolStatus(item) {
  const labels = {
    command_execution: 'Codex 正在執行工作…',
    mcp_tool_call: 'Codex 正在使用工具…',
    web_search: 'Codex 正在搜尋資料…',
    file_change: 'Codex 正在處理檔案…',
  };
  return labels[item?.type] || null;
}

// Exported so the HTTP/event behavior can be checked without using an account
// or making model requests. The normal entry point always uses the real SDK.
export function createChatServer({ codex, workspace = process.cwd(), startupError = null } = {}) {
  const conversations = new Map();
  const activeRequests = new Map();
  const options = {
    workingDirectory: resolve(workspace),
    sandboxMode: 'read-only',
    skipGitRepoCheck: true,
  };

  const server = http.createServer(async (request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");

    try {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 3210;
      const hosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
      const host = request.headers.host || '';
      if (!hosts.has(host)) throw new HttpError(403, '請透過本機網址開啟。');
      const expectedOrigin = `http://${host}`;
      const origin = request.headers.origin;
      if ((origin && origin !== expectedOrigin) || request.headers['sec-fetch-site'] === 'cross-site') {
        throw new HttpError(403, '請從本機聊天網頁送出訊息。');
      }
      if (request.method === 'POST' && origin !== expectedOrigin) {
        throw new HttpError(403, '請從本機聊天網頁送出訊息。');
      }
      const path = new URL(request.url || '/', expectedOrigin).pathname;

      if (request.method === 'GET' && (path === '/' || path === '/codex-chat.html')) {
        const html = await readFile(join(APP_DIRECTORY, 'codex-chat.html'));
        response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        response.end(html);
        return;
      }
      if (request.method === 'GET' && path === '/favicon.ico') {
        response.writeHead(204);
        response.end();
        return;
      }
      if (request.method === 'GET' && path === '/api/status') {
        sendJson(response, 200, {
          ok: true,
          ready: Boolean(codex),
          message: codex
            ? '本機服務已就緒，送出訊息時會沿用 Codex 登入。'
            : startupError || '請先在本資料夾安裝 Codex SDK，再重新啟動服務。',
        });
        return;
      }
      if (request.method === 'POST' && path === '/api/cancel') {
        const payload = await readJson(request);
        if (typeof payload.requestId !== 'string' || !ID_PATTERN.test(payload.requestId)) {
          throw new HttpError(400, '無效的請求編號。');
        }
        const active = activeRequests.get(payload.requestId);
        active?.controller.abort();
        sendJson(response, 200, { ok: true, cancelled: Boolean(active) });
        return;
      }
      if (request.method !== 'POST' || path !== '/api/chat') {
        throw new HttpError(404, '找不到這個頁面。');
      }
      if (!codex) throw new HttpError(503, startupError || 'Codex SDK 尚未安裝。');

      const payload = await readJson(request);
      if (typeof payload.message !== 'string' || !payload.message.trim()) {
        throw new HttpError(400, '請先輸入訊息。');
      }
      if (payload.message.length > MAX_MESSAGE_LENGTH) {
        throw new HttpError(413, '單則訊息最多 24,000 個字元。');
      }
      if (typeof payload.requestId !== 'string' || !ID_PATTERN.test(payload.requestId)) {
        throw new HttpError(400, '無效的請求編號。請重新整理頁面。');
      }
      if (activeRequests.has(payload.requestId)) throw new HttpError(409, '這個請求已經在處理。');
      if (payload.conversationId != null &&
          (typeof payload.conversationId !== 'string' || !ID_PATTERN.test(payload.conversationId))) {
        throw new HttpError(400, '無效的對話編號。');
      }

      let conversationId = payload.conversationId || null;
      let conversation = conversationId ? conversations.get(conversationId) : null;
      if (conversationId && !conversation) {
        throw new HttpError(409, '這段對話已過期，或本機服務已重新啟動。請按「新對話」再繼續。');
      }
      if (conversation?.busy) throw new HttpError(409, '上一則訊息仍在處理，請先等待或停止。');
      if (!conversation) {
        if (conversations.size >= 64) {
          const unused = [...conversations].find(([, entry]) => !entry.busy);
          if (unused) conversations.delete(unused[0]);
          else throw new HttpError(429, '目前處理中的對話過多，請稍後再試。');
        }
        conversationId = randomUUID();
        conversation = { thread: codex.startThread(options), busy: false };
        conversations.set(conversationId, conversation);
      }
      conversation.busy = true;
      const controller = new AbortController();
      activeRequests.set(payload.requestId, { controller, conversationId });
      let timeoutReached = false;
      const timeout = setTimeout(() => { timeoutReached = true; controller.abort(); }, TURN_TIMEOUT_MS);
      timeout.unref();

      response.writeHead(200, {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'X-Accel-Buffering': 'no',
      });
      response.flushHeaders();
      const send = event => {
        if (!response.destroyed && !response.writableEnded) response.write(JSON.stringify(event) + '\n');
      };
      const onClose = () => {
        if (!response.writableEnded) controller.abort();
      };
      response.on('close', onClose);
      send({ type: 'session', conversationId, threadId: conversation.thread.id });
      send({ type: 'status', message: 'Codex 正在處理你的訊息…' });

      try {
        let completed = false;
        let usage;
        const { events } = await conversation.thread.runStreamed(payload.message, { signal: controller.signal });
        for await (const event of events) {
          if (controller.signal.aborted) break;
          if (event.type === 'thread.started') {
            send({ type: 'session', conversationId, threadId: event.thread_id });
          } else if (event.type === 'item.completed' && event.item?.type === 'agent_message') {
            send({ type: 'message', id: event.item.id, text: event.item.text });
          } else if (event.type === 'item.started') {
            const message = toolStatus(event.item);
            if (message) send({ type: 'status', message });
          } else if (event.type === 'turn.failed') {
            throw new Error(event.error?.message || '這次回覆未完成。');
          } else if (event.type === 'error') {
            throw new Error(event.message || 'Codex 發生錯誤。');
          } else if (event.type === 'turn.completed') {
            completed = true;
            usage = event.usage;
          }
        }
        if (controller.signal.aborted) throw new Error('cancelled');
        if (!completed) throw new Error('Codex 程序提前結束，未收到完成事件。');
        send({ type: 'done', conversationId, threadId: conversation.thread.id, usage });
      } catch (error) {
        if (timeoutReached) {
          send({ type: 'error', message: '這次回覆超過 10 分鐘，已停止。請縮短問題後再試。' });
        } else if (controller.signal.aborted) {
          send({ type: 'status', message: '已停止這次回覆。' });
          send({ type: 'done', conversationId, threadId: conversation.thread.id, cancelled: true });
        } else {
          send({ type: 'error', message: explainError(error) });
        }
      } finally {
        clearTimeout(timeout);
        activeRequests.delete(payload.requestId);
        conversation.busy = false;
        response.end();
      }
    } catch (error) {
      if (!response.headersSent && !response.destroyed) {
        sendJson(response, error.status || 500, { error: error.message || '本機服務發生錯誤。' });
      } else if (!response.writableEnded) {
        response.end();
      }
    }
  });

  server.requestTimeout = 30000;
  server.headersTimeout = 15000;
  server.abortActiveRequests = () => {
    for (const { controller } of activeRequests.values()) controller.abort();
  };
  return server;
}

function openBrowser(url) {
  const command = process.platform === 'win32' ? 'cmd.exe' : process.platform === 'darwin' ? 'open' : 'xdg-open';
  const args = process.platform === 'win32' ? ['/d', '/c', 'start', '', url] : [url];
  const child = spawn(command, args, { detached: true, stdio: 'ignore', windowsHide: true });
  child.on('error', () => {});
  child.unref();
}

async function main() {
  const port = Number(process.env.CODEX_CHAT_PORT || 3210);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    console.error('CODEX_CHAT_PORT 必須是 1024 至 65535 之間的整數。');
    process.exitCode = 1;
    return;
  }
  let codex;
  let startupError;
  try {
    const { Codex } = await import('@openai/codex-sdk');
    codex = new Codex();
  } catch {
    startupError = '找不到 Codex SDK 或執行檔。請在此資料夾執行 npm install @openai/codex-sdk @openai/codex，然後重啟服務。';
  }
  const server = createChatServer({ codex, startupError });
  server.on('error', error => {
    console.error(error.code === 'EADDRINUSE'
      ? `連接埠 ${port} 已被使用。請關閉之前的服務，或修改 CODEX_CHAT_PORT。`
      : `啟動失敗：${error.message}`);
    process.exitCode = 1;
  });
  server.listen(port, '127.0.0.1', () => {
    const url = `http://127.0.0.1:${port}`;
    console.log(`\nCodex Chat 已啟動：${url}\n保持這個視窗開啟，按 Ctrl+C 關閉。\n`);
    if (startupError) console.log(startupError);
    if (process.argv.includes('--open')) openBrowser(url);
  });
  const shutdown = () => {
    server.abortActiveRequests();
    server.close();
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
