# 圖譜股票分庫與路徑契約

```text
data/
  graph/
    GOOGL/news-atlas.sqlite3
    GOOGL/news-atlas.sqlite3.prices.sqlite3
    GOOGL/news-atlas.sqlite3.graphs.sqlite3
    GOOGL/news-atlas.sqlite3.pairs.sqlite3
    _unassigned/news-atlas.sqlite3
    .layout-v1.json
  llm_wiki/GOOGL/wiki.sqlite3
  private/                  # 共用憑證、Chat socket/log、遷移備份
  .merge-backups/            # 合併備份，也可能位於更內層目標
```

## 路由

GraphRepository 是服務入口；Store 保持單庫介面供測試／離線工具使用。repository.path 是 NEWS_ATLAS_DB 的憑證定位相容入口，不代表根目錄仍有新聞 DB。正式讀寫使用 for_ticker/for_query 取得請求專屬 Store，不能改共用全域股票或由文章標題猜 ticker。

- search、search/result、cache/graph：明確 ticker 路由所有來源；未填則 _unassigned。不要求勾選 Massive 來源。
- 關聯 build／preview：請求 ticker 的圖／配對快取。前端傳已建立圖譜 exportMeta 的 ticker，不用尚未搜尋的表單草稿。
- prices/lens：明確 ticker。舊無 ticker payload 留於 _unassigned，以完整 ticker/range/method 雜湊鍵核對後重用；新 payload 保存 ticker。
- 快照依 search.ticker 保存。列表、按 ID 還原及文章 ID 查詢跨股票目錄讀取。全域文章數按 provider/id 去重。
- 全域分類於 _unassigned；新股票沿用分類，股票目錄保有可攜副本。
- Wiki 的 llm_wiki 與 private socket 取自 data_root。訂閱讀取對應股票 graph DB，不能錯建巢狀 llm_wiki/private。
- Chat 登入、API key、socket、log 仍為 data/private，不搬入單股。
- server.py、scripts/launch.py 均用 GraphRepository。read_prices.py 支援股票及 _unassigned 的 raw daily_prices；wiki_readiness.py 可用 --ticker 指定。

## 遷移

停掉舊服務後啟動新版。先以 SQLite backup 保存主 DB 到 private/graph-layout-backup-<時間>/，再將舊主檔及 WAL/SHM／sidecars 移至 graph/_unassigned。按 Massive query key、快照 search.ticker/query/region、Wiki 已確認訂閱建立分股副本。先提交完整副本，再刪除已移走的 membership／快照及沒有剩餘 membership 的已複製文章。

多股明確共用同查詢時允許兩邊保有內容。無歸屬查詢、孤立文章、額外表及無法識別 ticker 的舊價格快取留在 _unassigned。raw daily_prices 等額外表亦保留在 _unassigned，由離線工具讀取。

每股複製可重試；完成後建立 graph/.layout-v1.json。舊主 DB 和完成布局同時存在時拒絕啟動，要求用合併工具匯入。遷移只供離線啟動，沒有多程序同時遷移保證；中斷後先查備份和檔案，不可隨意刪 marker。

日後明確 ticker 搜尋可按完整 query key 重用 _unassigned 文章／membership／coverage。目標已有內容優先，未分類副本保留；不按相同新聞文字混讀其他股票。合併工具不啟動網路或 LLM。

## 驗證

- test_graph_storage.py：遷移聯集、無歸屬保留、並行隔離、Wiki 訂閱、快照／文章讀取、Handler 路由、舊價格快取、查詢重用、路徑逃逸拒絕。
- test_merge_data.py：全層／單股合併、衝突、版本對應、備份與來回去重。
- browser_wiki.py：即時進度、取消、覆蓋率、無歷史紀錄與瀏覽器錯誤。
- 生產遷移前在一致性副本比對 articles、memberships、coverage、attempts、snapshots、snapshot_articles、snapshot_relations、channels、membership_origins，分庫聯集須與原 DB 完全相同。
