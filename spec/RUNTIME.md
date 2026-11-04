# 啟動、操作與環境查核

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。

## Docker／Compose

`./run.sh up` 先互動確認、再建置及背景啟動，`status`／`logs`／`restart`／`down` 管理容器；`down` 保留資料。設定見根目錄 `.env.example` 和 `compose.yaml`。預設只發布 127.0.0.1:8765，`ATLAS_BIND=0.0.0.0` 開放區網；Docker 的主機與容器 port 都固定 8765；PORT 僅影響本機 Python。data bind mount 沿用既有資料，切換前停止本機 Python。容器非 root，UID/GID 預設由 run.sh 取得，直接 Compose 預設 1000:1000；選單可建立新的可寫資料目錄。不要以正式 DB 做容器測試。

單一 SQLite 服務尚不支援多副本；擴容需先分離共享 DB、抓取佇列、限流及憑證。映像使用 Python 3.12 slim，僅複製 runtime 程式／schema／前端，健康檢查 `/api/status`，server.py 處理 SIGTERM 關閉服務。Python 直接接收停止訊號，不依賴 Docker init。此主機的 Snap Docker 在設定 no-new-privileges 時連 python --version 都回 operation not permitted，因此 Compose 不預設此選項；保留非 root、唯讀 root filesystem 與 cap_drop ALL。標準操作見 [WORKFLOWS.md](WORKFLOWS.md)。

## 啟動

Python 3.10+，正式執行僅用標準函式庫；瀏覽器需 WebGL。Node.js 用於測試，前端不用 npm 安裝／build。

```bash
./run.sh local
# 可預選 port／模式
./run.sh --port 9000 --mode tailscale --https-port 8444
# 自動化：指定 port，衝突就失敗
./run.sh --non-interactive --mode local --port 9000
# 舊的直接啟動方式仍可用
python3 server.py
```

`run.sh local` → `scripts/launch.py` 提供 ←／→／Enter 模式與 port 選單、自訂輸入及最後確認。候選 port 會實際 bind/listen 探測；占用時提供其他候選，權限錯誤不誤報占用。建立 HTTPServer 後保留 socket，再初始化 DB，防止檢查與使用之間被搶占；若最後綁定失敗則重新選擇。q／Esc／Ctrl+C 會還原終端模式與游標。

Local 預設開啟 `http://127.0.0.1:8765`，程序需保持執行。Ctrl+C 停止。這是直接 Python + SQLite，不建立 Docker bridge。

直接執行 `python3 server.py` 且未設定 `PORT` 時，若 8765 已被使用，server 會直接綁定作業系統分配的可用埠；請以終端印出的實際網址為準。明確指定 `PORT` 時不自動換埠，衝突會顯示設定其他 PORT 的提示並退出，不初始化 DB。更換連接埠會使用不同的瀏覽器 localStorage；Tailscale 代理仍需同步調整目標埠。

[run.sh](../run.sh) 使用 Bash 呼叫新版 Python 啟動器；可從其他目錄用絕對路徑呼叫。相對 `NEWS_ATLAS_DB` 路徑以專案根目錄為基準。`./run.sh local --offline` 保留離線搜尋功能，可與新版啟動選項合用。

| 環境變數 | 預設／用途 |
| --- | --- |
| `PORT` | 8765 |
| `NEWS_ATLAS_CACHE_ONLY` | 設為 `1` 時搜尋只讀 DB，強制更新也不連外補抓；可用 `./run.sh local --offline` 啟用 |
| `NEWS_ATLAS_DB` | 專案 `data/news-atlas.sqlite3`；可指定測試或其他 DB |
| `MASSIVE_API_KEY` | 選填；請求內 key → 主機私有保存值 → 環境值；不輸出內容 |

直接 `server.py` 及 run.sh 的 Local 模式綁定 `0.0.0.0`；run.sh 的 Tailscale 模式後端只綁定 `127.0.0.1`。手機使用主機在同一網路的實際 IPv4 + port；`127.0.0.1` 在手機代表手機自己，`0.0.0.0` 不是瀏覽網址。不要把過往熱點 IP 當固定設定。

`run.sh` 的 Tailscale 模式檢查 Running／DNSName，再檢查既有 Serve（含 Foreground／Services）及 Funnel port，另外選 HTTPS port。啟動前再次檢查占用，啟動前景 `tailscale serve --https=PORT http://127.0.0.1:HTTP_PORT`；輪詢實際代理設定就緒後顯示 URL。Ctrl+C／SIGTERM／終端關閉的 SIGHUP、HTTP 啟動失敗或 proxy 異常均清理此次 proxy 與 HTTPServer；不使用 --bg、不 reset 或全域 off。實作依據：[Serve 官方文件](https://tailscale.com/docs/reference/tailscale-cli/serve)。

既有獨立 [Tailscale 腳本](../start-tailscale.sh) 檢查 tailnet 狀態、8443 未被使用及本機 8765 可達，然後建立 HTTPS 8443 代理。不是啟動 server 的腳本；自訂 PORT 需同步調整代理。服務本身沒有登入／授權層，定位是本機或受信任網路。

## 確認執行中的版本

```bash
curl -fsS http://127.0.0.1:8765/api/status
curl -fsS http://127.0.0.1:8765/api/capabilities
```

瀏覽 `/docs`、`/openapi.json`、`/api/schema`。若 status 正常而 capabilities/docs 404，可能仍在跑舊 Python 程序。**前端檔案更新可即時被讀取，但 Python module／route 要重啟才載入**。不要因新版前端可見，就宣稱後端已更新。JS URL 帶版本參數，修改跨模組合約時應一併更新相關資源版本。

重新整理只載入前端；不自動從快照還原整張圖。左側搜尋草稿保存在同 origin 的 localStorage，跨 localhost／區網 IP／Tailscale／port 不共享。瀏覽器拒絕儲存時有提示。

## DB、憑證與版本控制

DB 是跨重啟累積的單一 SQLite，不是每次搜尋一份。備份先停止 server，或使用 SQLite backup API；不能只任意複製正在寫入的主檔而忽略 WAL。詳見 [data/README.md](../data/README.md)。不要把現有使用者 DB 當測試可刪除資料。

讀取 Massive key 的測試／除錯不得列印環境或 localStorage 憑證。一般搜尋草稿不含 key，key 由獨立記住／忘記控制管理。

提交前確認 Git 根目錄、分支、remote 與工作目錄狀態。專案展示名稱為 StockNexus-Wiki，建議 repository slug 為 stocknexus-wiki；遠端統一為 https://github.com/a0665x/StockNexus-Wiki.git。

前端整頁失去互動時，先檢查 HTTP script 回應與第一個 JavaScript 例外；不要先把問題歸因於 API key 或來源。參閱 [前端資源事故及重啟驗證](references/bugfix-20261029-frontend-asset-startup.md)。塑形 profile 的後端驗證也需要重啟 Python，否則舊程序可能丟棄新欄位。

主機記住的金鑰在 `<DB所在目錄>/private/<DB檔名>.massive-key`，目錄 0700、檔案 0600，原子置換；不加密，也不由 HTTP static 路由提供。預設路徑及 key／暫存檔 pattern 均由 .gitignore 排除。DB 備份不含金鑰；清除主機保存不改環境變數。新增 key API、地區搜尋、SQLite 4 遷移需要重啟 Python。

## 有新聞但 3D 空白

WebGL 初始化失敗或使用中 context lost 時，前端自動改用時間軸，診斷提示可展開；資料與 roots 搜尋保留。恢復 context 後可手動返回 3D。Chrome 的 GPU 必須在瀏覽器所在裝置上排查，不能以 server GPU 取代；先查 chrome://gpu 與原始 Console 錯誤。詳見 [WebGL 降級與驗證紀錄](references/bugfix-20261029-webgl-fallback.md)。

### Docker 啟動器驗證與 Tailscale

`run.sh` → `scripts/docker_launch.py`，主機 Python 3.10+ 標準函式庫。固定 -p news-atlas、HTTP 8765、scale atlas=1；fcntl 主機鎖序列化不同 checkout 的啟停。preflight 驗證資料、port、project working_dir；占用者屬其他程序／專案時拒絕啟動，不停止它。建置在清理之前，避免建置失敗中斷舊服務；異常／多副本／殘留會 scoped down，健康單一容器由 Compose 沿用或更新。檢查完成後恰好一個 healthy，主機 `/api/status` 200。

已安裝且連線的 Tailscale 顯示左右鍵選單，沒有安裝不問；非互動預設不新增，可用 --tailscale on/off 明確指定。--https-port 預設 8443，與 HTTP 8765 分開。使用 --bg 及持久路由所有權記錄，down 只清理自己建立且未被別人加上其他 handlers 的路由。不得以 serve reset 清理。實際主機驗證未新增／修改 Tailscale 路由，互動選擇、確認及 HTTPS URL 以 PTY mock 驗證。

## 資料位置選擇

無參數 `./run.sh` 等同 Docker up。`scripts/storage_paths.py` 每次 up 檢查已掛載的其他實體磁碟、容量，提供沿用／磁碟／自訂路徑。選定後且確認啟動才停止容器、複製及驗證 SQLite/WAL 和一般檔案，切換 data 符號連結，保留原資料備份。`.atlas-storage.json` 優先於環境設定；磁碟缺席拒絕啟動，down/status 仍可使用。非互動換位置需同時指定 `--data-dir` 與 `--migrate-data`。只接受空目標、不掛載、不格式化、不改 owner；連結或狀態保存失敗回復原連結／目錄。自動化命令與設定見下表。

啟動器英文輸出：Docker／Compose／Python、project owner、容器數／健康、8765 ownership、storage mount/free/write+fsync、三個服務的 DNS/TLS/HTTPS reachability。網路失敗 WARN 不阻止快取操作；無憑證探測不宣稱 account/data 授權可用。互動箭頭選單、搬移與本機模式同樣英文。

全量資料不截斷。相同文章／設定的關聯結果最多快取 8 組，回傳複製以避免不同圖譜共享可變 evidence。第一次大圖計算仍可能較久，前端關聯等待 300 秒、搜尋 600 秒；逾時回報並保留當前資料。


## 常用命令與環境設定

```bash
./run.sh up --non-interactive
./run.sh status
./run.sh logs
./run.sh down
# 明確指定新位置並同意搬移；目標必須為空
./run.sh up --non-interactive --data-dir /mnt/storage/stocknexus-data --migrate-data
```

可選擇從 [.env.example](../.env.example) 複製 `.env`；不提交金鑰。

| 設定 | 行為 |
| --- | --- |
| ATLAS_BIND | Docker 發布位址，預設 127.0.0.1；0.0.0.0 開放區網 |
| ATLAS_DATA_DIR | 未保存路徑時的 Docker 資料位置；保存狀態優先 |
| ATLAS_UID / ATLAS_GID | data 的執行者權限；啟動器預設取目前使用者 |
| ATLAS_IMAGE_TAG | 映像標籤，預設 local |
| PORT | 只影響本機 Python；Docker 固定 8765 |

`restart` 不重建映像；原始碼更新必須 `up`。新增的 `.graphs.sqlite3` 是可丟棄的衍生快取，
正式新聞與快照仍在主 DB；詳見 [快取語義](SOURCES_AND_CACHE.md)。
同 IP 不代表同 GPU 程序／設定；App、headless SwiftShader 與使用者 Chrome 必須分別驗證。
診斷順序與證據限制見 [渲染事故紀錄](references/lesson-20261102-rendering-cache-settings.md)。

Docker 的 port 檢查依實際 `ATLAS_BIND` 位址執行（預設 127.0.0.1），包括清理舊容器後的再檢查。Tailscale 僅在 tailnet 位址監聽同號 port 時，不應誤擋 loopback 啟動；若選 0.0.0.0，仍會檢查所有介面的占用。
