# 標準工作流程

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。以 2026-11-06 的工作區實作為準。先讀 [協作偏好](ai-dev-experience-preferences.md)，計算定義見 [CALCULATION_METHODS.md](CALCULATION_METHODS.md)。

## 專案命名與相容性

展示名稱 **StockNexus-Wiki**；GitHub repository slug **stocknexus-wiki**。
這是文件命名規範，不代表遠端儲存庫已完成改名或推送。

目前保留 `news_atlas/`、`news-atlas` Compose project/image、`data/graph/<ticker>/news-atlas.sqlite3`、
`NEWS_ATLAS_DB`、`graphnews.*` localStorage，以及程式內既有 UI 名稱。
若未來全面改名，需另做容器／資料位置／憑證／瀏覽器偏好遷移；不可全域字串取代後直接部署。

## 啟動與更新

1. 在專案根目錄確認資料位置，讀 [RUNTIME.md](RUNTIME.md)。
2. Docker 用 `./run.sh`；更新原始碼後用 `./run.sh up`，建置成功才更新唯一容器。
3. 自動化用 `./run.sh up --non-interactive`；預設不新增 Tailscale 路由。
4. 確認 `/api/status` 與容器健康，再刷新網頁。`restart` 只重啟現有映像，不載入新原始碼。
5. 本機 Python 模式修改後端需重啟；不要同時啟動兩套服務爭用資料或 port。

## 搜尋與更新圖譜

1. 左側先輸入必填 EXCHANGE:SYMBOL 股票識別；自動帶出 symbol 的第二欄查詢字詞可逗號分隔補充，再選來源、RSS 地區與 UTC 日期。
2. `/api/search` 從各來源 membership 讀取當前查詢的已存新聞，正規化後查完整圖譜快取。
3. 命中：第一個 `cache` 事件包含節點與 edges。未命中：先送節點，`relations_pending=true`。
4. 各來源並行檢查新鮮度、補抓缺口並更新 DB；每個完成來源送出 `source` 事件。
5. 每次新集合優先查快取。若仍需計算，保留兩端文章完全未改變的舊關聯證據，標記仍在更新。
6. 來源完成後，使用該次設定取得完整圖譜；同資料／分類／設定／版本命中才可直接重用。
7. `graph` 事件替換最終關聯，`done` 結束搜尋。錯誤保留已取得資料；取消等待拒絕晚到 UI 回應，後端工作可能繼續。

`Already in DB` 只描述文章，不代表 edges 已完成，也不代表所有來源日期覆蓋完整。
補抓、圖譜建構、HTTP 傳輸、前端物理排列與 GPU 繪製是不同階段，不能混用耗時數字。
細節見 [SOURCES_AND_CACHE.md](SOURCES_AND_CACHE.md)。

## 設定與刷新

| 操作 | 生效範圍與保存 |
| --- | --- |
| 編輯右上 Edge settings 欄位 | 草稿；未按套用不改已生效規則 |
| 按套用且成功 | `/api/graph/build` 重新取得符合規則的線；保存 `graphnews.relationSettings` |
| 套用失敗／過期回應 | 保留原圖與已套用設定；不宣稱成功 |
| 刷新後再次搜尋 | 使用同 origin 最後成功保存的偏好；命中圖譜也必須符合這份設定 |
| 左側進階 edge 分數／探索深度 | 篩選已載入關聯與走訪範圍，不重抓新聞 |
| 3D render budget | 當頁顯示量；100–2400 的既有選項，未保存時預設 800；已保存工作區沿用選擇，不改後端 edges |
| 圖內 Search | 本地排名、選 roots；不抓來源或查全 DB |

新使用者沒有保存值才使用 unified 自適應設定；已保存 original/general/custom 不再被舊遷移覆寫。
同 origin 指協定、主機名與 port 相同；App、Chrome、localhost、IP、Tailscale 不保證共享偏好。
若顯示仍在更新，眼前的保留線不是新資料的最終度數預算選線。

## 快照、DB 與備份

- 搜尋自動更新新聞 DB；「儲存圖譜快照」另外凍結當時資料、關聯、視圖與規則。
- 想看當時狀態：從「已儲存圖譜」載入。想看更新資料：重新搜尋，來源補抓可能增加文章並令完整圖快取失效。
- 載入快照不覆寫左側搜尋草稿。快照的規則在當頁還原，不等於跨頁偏好已保存。
- 新聞 DB、圖譜快取 sidecar、主機私有金鑰與瀏覽器偏好分開管理；金鑰不進 API 回應／快照／匯出。
- 備份使用 SQLite backup API 或先停止服務；不可漏掉正在寫入的 WAL。詳見 [DB 說明](../data/README.md)。

## 開發到交付

1. 先讀專案地圖、任務相關 spec、CHANGELOG 與事故紀錄，核對現有程式。
2. Bug 建立能失敗的重現；效能問題先量測，分清 cache hit/miss 與 GPU 路徑。
3. 使用暫存 DB／隔離 fixture；正式資料僅按任務授權操作，不用正式 DB 做測試寫入。
4. 依 [TESTING.md](TESTING.md) 驗證：後端／API、JS、實際 HTTP assets 與必要的真實瀏覽器互動。
5. 新增 JS 同時檢查靜態路由與版本參數；修改關聯語義提高 graph cache VERSION。
6. 更新最相關 spec 與 CHANGELOG，事故另記 reference；保留已驗證與未驗證範圍。
7. 部署後確認唯一 healthy 容器、HTTP 回應與實際版本。提交／推送前確認有效 Git checkout、branch、remote；未推送不可宣稱遠端已更新。


2026-11-06：News/Wiki 工作畫面另存於主機 workspace SQLite；新視窗會先恢復清理過的新聞快照及 Wiki 控制值。新聞股票欄必填 EXCHANGE:SYMBOL，位於可編輯逗號查詢字詞之前。Wiki Graph 方法自動從完整 News 範圍採樣與點選時相同的 root tree，直到 Wiki 日期內所有目標被涵蓋；不要求手動點選，繪製上限不裁切工作集合。新設定驗證成功後才取消進行中的舊工作，接續未完成新聞；閒置 Apply 只保存。模型與顯示篩選的草稿不因切頁重設。
