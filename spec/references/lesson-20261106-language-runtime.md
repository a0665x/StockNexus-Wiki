# 2026-11-06 — Chat 語系、重連與多視窗

狀態：原始碼、隔離生命週期測試及正式服務驗收完成；交付結果見 [TESTING](../TESTING.md)。通用思路見 [協作偏好](../ai-dev-experience-preferences.md)，這裡保留專案證據與邊界。

## 症狀與可重現證據

使用者在 Wiki 重連、新開同一網址及切換英文後，仍看到「已連線 · 使用本機登入」以及含「個節點／依目前選取與日期討論觀點」的情境卡。初次隔離 Chrome 測試在真實 HTTP 資產上重現：New chat／Stop 已是英文，連線狀態和 Wiki 情境仍為中文；等待下一次 sync 也未修復。

先列三個假設再取證：Wiki 翻譯邊界排除 Chat、非同步 callback 寫入固定中文、視窗間沒有偏好通知。探查暫時移除翻譯邊界只能翻好部分詞句；第二個實際分頁切成中文時第一頁仍為英文。三個原因均有證據。

## 原因與修正

| 原因 | 修正及維持的條件 |
| --- | --- |
| News Chat 倚賴全局 MutationObserver；移入 `data-own-i18n` Wiki 後不會被掃描 | Chat 的控制列、分頁、情境、狀態、提示與可存取名稱由自己完整呈現，仍保留 Wiki／原文的翻譯隔離 |
| `connect`、`sync`、stream、reset、cancel／error 路徑寫入固定中文；切語言只更新按鈕 | 保存 canonical 狀態／參數，所有狀態寫入與 `atlas-language` 都按目前語系呈現；情境使用完整模板，資料在模板翻譯之後才插入 |
| 語言只在載入時讀 localStorage，已開啟視窗各自保留舊值 | `AtlasI18n` 為 UI 語言唯一來源；同來源、同 profile 的 storage 事件讀目前值、走同一通知，不回寫形成迴圈。News／Wiki runtime 都回報該語言 |
| 附帶測出 cancel 回應比 done 晚到，已停止又變成 Stopping | 按下取消時先顯示 stopping；取消 HTTP 確認不再覆蓋串流已完成的最終狀態 |

切語言不重開 Chat、不呼叫模型、不修改生成保存語系、股票、日期或 root。原始訊息、輸入及引用文字不翻譯；未知服務錯誤細節保留原文，已知 UI 錯誤則翻譯模板。

## 防止重犯的驗證

`tests/browser_chat_language.py` 建立隔離股票與 Wiki，經實際 Handler 載入全部頁面資產。僅 Chat transport 使用可控回應，控制 session／turn／cancel 回應先後；沒有呼叫真實模型或寫正式資料。

涵蓋初始掛載、切語言後再 sync、中文／英文來回、reset、回覆進行中切語言、cancel 晚確認、錯誤文字重繪、session 過期與重連、隱藏 News Chat 再顯示、三個真正獨立 URL 分頁的雙向 storage 同步、reload，以及獨立 Chrome profile 的冷啟動和隔離。比對原訊息、News node 物件／鏡頭、模型、生成語系、日期和 roots 不變，並收集各頁 JS 錯誤。

測試先捕捉原始中文殘留，再捕捉取消晚確認覆蓋最終狀態；修正後相同斷言通過。測試本身曾因 CDP 全域 `const` 重複宣告中止，改為區塊範圍，未放寬產品斷言。正式服務資料較多，首次測試未等完整初始化即逾時；改等 `show()` 完成再斷言，且把這項等待納回測試 helper。不能把短暫載入中誤判為狀態遺失，也不能只等待第一批節點就宣稱初始化完成。

邊界：UI 語言是同來源瀏覽器偏好，不是主機 workspace 設定；不同 port、host 或 profile 不自動共享。新 profile 測試是在掛載前設定自己的英文偏好，並非宣稱跨 profile 同步。session 失效／晚回應由隔離 transport 驗證，不代表所有實體網路、休眠與代理行為都已測過。
