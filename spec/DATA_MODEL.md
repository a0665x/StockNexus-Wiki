# 資料、Schema 與持久層

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。細節：[SCHEMA_AND_RULES.md](references/SCHEMA_AND_RULES.md)。

## 權威定義與流向

[news-atlas.schema.json](../schema/news-atlas.schema.json) 是 JSON Schema Draft 2020-12、資料版號 2.0；[openapi.py](../news_atlas/openapi.py) 從它產生共用元件。SQLite `user_version=4`、OpenAPI `info.version`、analysis_version／channel_version 是不同層的版本，不要混為單一 migration 號。

原始來源 → `article` 清理標題／摘要、URL、UTC → canonical URL 去重保留 origins → entities/topics 規則 → channels 分類 → relations → graph/source_graphs/cross_relations → runtime view 或 snapshot。

summary 是來源 description，不是全文。language 可為 null。不能把來源明確 ticker 與文字辨識的 alias 證據混用。

## SQLite 表

| 表 | 粒度／用途 |
| --- | --- |
| articles | `(provider,id)`：標準文章 JSON、發布日期 |
| memberships | `(provider,query_key,article_id)`：查詢歸屬 |
| membership_origins | `(provider,query_key,article_id)`：此查詢取得文章時的 source JSON，保留國別／語言／網站限制 |
| coverage | `(provider,query_key,day)`：kind、checked_at |
| attempts | 請求窗口、錯誤碼、retry_until |
| channels | 自訂分類；預設分類在程式 |
| snapshots | ID、名稱、created_at、search_json、view_json |
| snapshot_articles | snapshot + provider + article ID 的凍結內容 |
| snapshot_relations | snapshot + scope + edge ID；cross 是跨來源 |

Store 每次連線有 transaction context、WAL、15 秒 SQLite timeout。資料庫自動 CREATE IF NOT EXISTS；不能把目前初始化流程當作任意舊 schema 的完整遷移框架。

## 不同生命週期的狀態

| 狀態 | 保存位置 | 語義 |
| --- | --- | --- |
| 搜尋草稿 | 瀏覽器 `graphnews.searchDraft` | 尚未送出也保存的左側輸入 |
| 取得快取 | SQLite articles/memberships/coverage | 可重用的真實來源內容與窗口知識 |
| 手動快照 | SQLite snapshot_* | 使用者當時文章、關聯、位置及顯示設定 |
| 工作畫面 | private/workspace.sqlite3 的 news/wiki payload | 白名單化的圖譜與獨立控制值；新瀏覽器恢復，不是查詢覆蓋證明 |
| Wiki 知識／工作 | llm_wiki/<ticker>/wiki.sqlite3 | 引用、版本、模型工作與已完成範圍；不由瀏覽器顯示預算決定 |

快照的 search 是歷史 metadata，不能載入後覆寫左側草稿。還原時保留凍結 channel 定義、原順序、位置、來源選擇、探索／光暈設定、focus roots 及 time_focus（enabled/date/peak/width/profile?；profile 為 129 個 1–12 的有限數值，覆蓋 Gaussian；舊資料缺 peak/width 時使用 2/.12）。保存來源／edge 門檻篩選後的完整圖，時間／分類只存顯示設定，不刪除暫時隱藏的 root 或中間路徑。舊快照沒有 time_focus 時關閉日期大小效果。舊快照缺欄位使用相容預設；不是每個新 UI preference 都寫入快照。

[snapshots.py](../news_atlas/snapshots.py) 同時服務儲存和 `/api/view/validate`。來源分區、cross 邊、位置 ID、focus 模式／root IDs 需一致。保存只接受白名單欄位，不能把 Three.js mesh／循環物件或 key 序列化進去。

來源新增可選 `source.country`、`source.language`、`source.sites`；同網址跨地區觀測累積於 origins。SQLite 4 以 CREATE TABLE IF NOT EXISTS 加上 membership_origins，不刪資料／不改舊新聞 payload；舊查詢沒有該表記錄時 fallback 原 source。快照 search.rss_region 保存歷史地區，但還原不覆寫正在編輯的地區草稿。Massive key 位於 DB 之外的私有設定檔。

自適應關聯：relation_settings.adaptive 預設 false（API 舊行為相容），WebUI unified 偏好設 true。先以不寬於原始 30／7／3 天與 .18／.5、至少四詞的條件建立 strict edges；再用使用者的較寬條件只補 degree=0 節點，受同一連線預算限制，不做額外密集填線。evidence.adaptive_stage 區分 strict／expanded。
