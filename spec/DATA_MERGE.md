# 跨電腦資料合併

入口：專案根目錄 `merge_data.sh`（Python 標準函式庫，無須 npm、網路或模型）。來源接受 **data、graph、llm_wiki 或單一股票目錄**；目標可為 data、graph／llm_wiki 分類目錄或對應單股目錄。資料夾層級以標準檔案／目錄名稱辨識。使用可讀取相同 DB 格式的專案版本。

```bash
# 預覽：不修改目標資料內容，也不建立備份。
./merge_data.sh --from /media/usb/data --to ./data --dry-run

# 正式合併：網頁可保持開啟；先暫停目標股票的 Wiki 工作／持續維護。
./merge_data.sh --from /media/usb/data --to ./data
```

Docker／Python 服務與網頁可保持開啟，不需為合併重啟。先在頁面停止欲合併股票的 Wiki 工作／持續維護；工具在鎖內檢查 active jobs 與 enabled/catch_up，忙碌時拒絕，避免兩套寫入交錯。正在搜尋若持有 DB 寫入鎖，可等它完成後重試。腳本不幫使用者關服務或偷偷啟動模型。來源可用 SQLite backup 取得一致副本；不要直接搬正在寫入的主檔而漏掉 WAL。來源若仍在線，工具以 SQLite backup 讀取各資料庫的一致快照；各 DB 之間不是同一瞬間的全域快照。

## 合併範圍

- `graph/<ticker>/news-atlas.sqlite3`：新聞、查詢 membership／來源、涵蓋紀錄、抓取嘗試、分類、圖譜快照及其文章／連線。若含已知 daily_prices／price_downloads 表亦處理。
- `llm_wiki/<ticker>/wiki.sqlite3`：股票 Wiki 的引用文章、節點、連線、版本、抽取與工作紀錄。股票識別必須符合資料夾股票代號。舊版 research/<hash> 亦可作為匯入來源；舊目標需先啟動新版遷移。
- `graph/<ticker>/news-atlas.sqlite3.prices.sqlite3`：股價查詢快取條目。相同 key 但內容不同仍遵循下方衝突策略，不合成兩個價格序列。
- 不搬 `private/`、金鑰、登入、socket、log、圖譜／配對快取、其他未知檔案。可重建快取保留目標現狀。
- 目前只識別上述標準檔名；自訂 NEWS_ATLAS_DB 檔名須先建立標準名稱的備份匯入包。未知資料表、較新 user_version、不同欄位結構、view／trigger、巢狀或相同路徑、DB symlink 都會拒絕。

## 去重與衝突

1. 新聞按 provider + id；Wiki 按穩定節點／連線／revision ID 去重。相同內容不重做，也不呼叫 LLM。
2. 同主鍵但內容不同，不猜哪份是真：保留目標有效內容，來源衝突內容寫入同 DB 的 `merge_conflicts`，並保有完整來源備份。報告提供衝突數；衝突資料不會自動作為已確認新聞或模型結論呈現在圖上。
3. Wiki 版本重新對應，`merge_versions` 保存來源對應，支援同一包重複匯入及 A → B → A。既有目標歷史不改寫；新增知識的 available_at／版本建立時間採匯入時間，原時間保留在來源備份。引用文章 ID／引用字句與節點識別不改寫。
4. 抓取嘗試等整數流水號以內容去重並重配 ID；`merge_records` 保存對應。快照同 ID 但內容不同時另建穩定匯入 ID，子文章／連線一併對應，避免混入另一份快照。
5. 保留目標 Wiki 設定；新股票帶入來源設定但關閉 enabled/catch_up。來源 queued/running 工作改為 interrupted，不會匯入後偷偷啟動。review evidence_epoch 不能跨電腦當成已複查證明，新匯入項目設為 0。
6. 匯入來源呼叫帳本後，daily_calls 可能包含別台的呼叫；此計數不是目前電腦或帳號週用量。

因此這是「資料取聯集、重複去除、衝突另存」，不是把所有矛盾內容強行變成一份真相。現有 UI 沒有衝突解決頁；可透過報告／SQLite 排查 `merge_conflicts`。

## 寫入、備份與復原

先對所有 DB 建立一致快照、在暫存副本合併並驗證。既有目標 DB 持有寫入鎖；有 active Wiki 工作或開啟維護時拒絕。任何預檢失敗不修改目標資料內容。

正式寫入前，完整備份到目標：

```text
.merge-backups/<時間-識別碼>/
  before/       # 修改前既有的各個資料庫
  source/       # 本次來源一致快照
  report.json   # 每個 DB 的新增／重複／衝突數與已提交清單
```

**每個 SQLite DB 個別原子提交，不保證跨檔案一次提交。** 若斷電或磁碟錯誤導致部分完成，查看報告後可再次執行相同合併（去重），或停服後用 `before/` 復原已存在的資料庫。新建資料庫沒有 before 副本，完整回復需依報告移除本次新增者。還原時必須處理舊 WAL/SHM，不能直接在運作中的 DB 上覆蓋檔案。工具不自動做具破壞性的復原。

## 驗證

`python -m unittest discover -s tests -p test_merge_data.py -v`：兩端不相交／重疊資料、衝突保存、重複及來回匯入、Wiki 版本／引用、快照 ID 衝突、整數 ID 碰撞、新股票停用、活躍目標拒絕、壞引用預檢、備份、dry-run、未知格式與價格條目。

## 按資料夾選取股票

```bash
# 只合併 GOOGL 到本地 data（其他股票不動）
./merge_data.sh --from /media/usb/data/llm_wiki/GOOGL --to ./data --dry-run
./merge_data.sh --from /media/usb/data/llm_wiki/GOOGL --to ./data

# 合併所有 Wiki，不碰新聞主 DB
./merge_data.sh --from /media/usb/data/llm_wiki --to ./data/llm_wiki

# 單股直接對單股
./merge_data.sh --from /media/usb/data/llm_wiki/GOOGL --to ./data/llm_wiki/GOOGL
```

整個 data 來源仍合併新聞主 DB 與全部 Wiki。單股目錄包含該 Wiki 引用的新聞版本，可獨立閱讀；它不含原新聞主圖的完整搜尋 memberships。不同交易所同 ticker 會拒絕合併，避免混淆。

## Graph 層級辨識

```bash
./merge_data.sh --from /media/usb/data/graph/GOOGL --to ./data --dry-run
./merge_data.sh --from /media/usb/data/graph/GOOGL --to ./data/graph
./merge_data.sh --from /media/usb/data/graph --to ./data/graph
./merge_data.sh --from /media/usb/data --to ./data
```

來源以 DB 檔名、股票 metadata 及標準目錄推導；目標以現有內容和 graph／llm_wiki／ticker 名稱辨識。不存在且無標準名稱的目標預設為 data 根。graph 不能送入 llm_wiki，多股不能送進單股，股票名稱不符會拒絕。無法判定的非標準混合布局會拒絕。

舊版根 news-atlas.sqlite3 可作來源，保守匯入 graph/_unassigned（不猜 RSS 股票）；舊目標需先啟動新版遷移。之後明確 ticker 搜尋會按完整 query key 重用未分類文章與覆蓋紀錄。詳見 [GRAPH_STORAGE.md](GRAPH_STORAGE.md)。

## 開著頁面合併後會看到什麼

`./run.sh up` 成功後會印出上述預覽／正式合併範例，使用實際啟動資料路徑及可含空格的 shell 引號。將 `/media/usb/data` 換成自己的 USB 路徑；已選其他磁碟時以印出的 `--to` 為準。

Wiki 開啟時約每 6 秒重讀股票目錄，視窗／選單取得焦點也會更新。新股票加入下拉選單，已選股票的最新版本會刷新；固定歷史版本仍維持原選擇。模型、日期、選取與 News runtime 不因目錄更新被重設。新匯入股票不會自動搶走目前畫面。

若只匯入新聞 graph 而沒有 Wiki，新資料可用對應股票／範圍從 DB 查詢；不會憑空新增一個「已建立的 Wiki」。目前 News 圖譜保留原探索狀態，需重新載入／查詢才能納入新文章；這與 Wiki 股票目錄自動更新是兩種行為。

`tests/browser_live_merge.py` 在隔離的真實 HTTP 服務與 Chrome 上執行實際 CLI dry-run／合併，驗證新股票出現、既有版本更新、選擇與新聞圖譜保留及無模型呼叫。
