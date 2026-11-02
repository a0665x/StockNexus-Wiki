# 文件盤點與維護分工

上層：[PROJECT_MAP.md](../PROJECT_MAP.md)。更新：2026-11-02。

| 文件 | 職責 |
| --- | --- |
| [README](../../README.md) | StockNexus-Wiki 簡介、啟動、簡短操作及文件連結 |
| [PROJECT_MAP](../PROJECT_MAP.md) | Level 1 索引；不堆放逐次操作日誌 |
| [WORKFLOWS](../WORKFLOWS.md) | 命名邊界、使用／開發／部署標準流程 |
| [ARCHITECTURE](../ARCHITECTURE.md) | 資料流、模組與狀態邊界 |
| [SOURCES_AND_CACHE](../SOURCES_AND_CACHE.md) | 來源覆蓋、文章／圖譜快取、失效與性能 |
| [UI](../UI.md) | 顯示、互動、偏好／快照、GPU 預算 |
| [RUNTIME](../RUNTIME.md) | 啟動、Docker、資料位置、憑證與實際環境查核 |
| [TESTING](../TESTING.md) | 按修改領域選回歸及已知測試限制 |
| [CHANGELOG](../CHANGELOG.md) | 時序歷史；中途方案不等於目前行為 |
| [docs/API.md](../../docs/API.md) | 完整功能及 API 操作；機器合約以 schema／OpenAPI 為準 |
| [data/README.md](../../data/README.md) | DB 與備份說明 |
| [schema](../../schema/news-atlas.schema.json) | 機器可讀欄位合約 |

references 保存可追溯的事故與設計取捨；目前行為寫在 Level 2，歷史文不直接當作操作指示。

## 尚未實作

新聞全文抓取／全文索引、向量語意推論、全 DB 圖內搜尋、MCP transport、多使用者授權、
跨 origin 偏好同步、持久 pair evidence、閒置背景補算與跨程序計算合併。
Yahoo 已支援含台灣的地區選擇；不要沿用早期僅 US Finance 的描述。

本次文件命名不修改遠端 repo、UI 品牌、Compose project、DB 路徑或 localStorage keys。
