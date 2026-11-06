# Schema 與規則細節

上層：[DATA_MODEL.md](../DATA_MODEL.md)、[UI.md](../UI.md)。權威實作：[model.py](../../news_atlas/model.py)、[channels.py](../../news_atlas/channels.py)、[exploration.py](../../news_atlas/exploration.py)、[graph-view.js](../../dist/graph-view.js)。

## 文章與識別

canonical_url 只接受 http/https、有效 host、無帳密，移除 utm_*／fbclid／gclid／guccounter 與 fragment、排序 query。文章 ID 是 canonical URL 的 SHA-256 前 24 字元。它不是標題雜湊；不同 URL 的轉載不會自動語意合併，RSS 包裝 URL 也不等於解析最終 publisher URL。

article：id/title/summary/url/published_at/source/symbols/language/fetched_at。來源摘要清理 HTML，title 上限 2000，summary 12000。UTC 日期解析失敗為 null，取得流程按有效發布日期篩選。

enrich：entities 明確 ticker 優先，否則公司 alias 的文字命中；topics 由文字規則。保存 method／field／evidence，analysis_version 為 rules-v1。去重保留 origins、合併 symbols，偏好較長摘要；同 URL 以日期／ID 排序後選代表文章。

Merged UI 用 canonical ID；來源分組時用 `provider::id` 並保留 article_id。快照 source_graphs 仍保存 canonical IDs；view positions／focus 在分組模式要使用 prefixed IDs。

## 關聯生成

先依條件為所有候選 pair 評分，再依分數高、日期近、ID 排序限制兩端 degree。超過 30 日不連。

| type | 條件 | 分數 |
| --- | --- | --- |
| shared_entity | 有共同實體 | .72 + min(.2, .07 × 共同實體數) |
| shared_topic | ≤7 日、共同 topic、≥2 標題重疊詞、Jaccard≥.18 | .40 + min(.25, Jaccard) |
| similar_title | ≤3 日、≥4 重疊詞、Jaccard≥.5 | .45 + min(.3, Jaccard/2) |

if/elif 優先順序如上，不是累加三種 edge。規則可由 `relation_settings` 切換或調整；未提供時完整保留上表 defaults（rules-v1）。自訂為 rules-v2：三類開關、各自 1–366 天窗口、topic/title Jaccard、來源內 0–6／跨來源 0–2 預算；half_life 0 關閉，1–366 時乘 `2^(-days/half_life)`，證據附 base_score、time_factor 及完整設定。始終保留孤立點，無 embedding 或 channel 加權。權威設定與驗證在 `news_atlas/relation_settings.py`。

普通 degree budget 預設 6；graph_payload 對來源內獨立建圖，再以各來源配對完整候選、每端 budget 2 補 cross 關聯（舊 800 候選截斷已移除）。cross_only 排除 origins 重疊的 pair。不能為了圖更密而虛構 evidence。

Channel 對 title/summary literal keywords 作 any/all，多標籤且有 primary_channel；內建晶片製造、生產供應鏈、財報、股價、產品、政策及 fallback other。自訂分類／版本與詳細限制以 channels.py 為準。

## 圖內排名與森林

`rankRoots`／`rank_roots` 用 NFKC、最多 20 個去重 terms。每個 term 在 title/summary/symbols/entities/topics/channels 的命中分別加 8/2/10/6/3/3；不是詞頻乘分。英文起始有 word boundary，四字母以上的 title/summary/topics/channels 可詞首匹配；symbols/entities 精確匹配。中文 literal substring。不含全文、跨語言翻譯或 embedding。

得分降序、ID 升序；Top 1–10，不以無關文章補足。`IPO` 大小寫不敏感，短詞維持精確邊界；`robot` 可命中 robots/robotics。API method 為 weighted_prefix_v2。

延伸參數預設：internalMin=0、crossMin=0、depth=2、branchLimit=4、pathMin=.25、maxNodes=150。限制：深度 1–6、分支 1–12，每樹最多 150。先套 edge 篩選，再 BFS、較強邊優先、沿途 weight 相乘，遇訪問過節點／預算／門檻停止。不是最強路徑演算法。

多樹的其他 selected roots 是 barrier，不被另一 root 吃成分支；共同非 root 節點可屬多棵樹。JS 合併 nodes 保存 memberships/parents，採最小 depth 決定亮度；各樹邊取聯集，不重複造新聞。整張可見圖受當下 GPU 預算限制（預設 800、最高 2400），不縮小搜尋全集或 Wiki root 工作輸入。

## 快照設定

view：sources/separate/positions/mode/channel_filter/cutoff/timeline_zoom/timeline_style/channel_definitions/exploration/glow/focus/time_focus。time_focus 包含 boolean enabled 與 UTC date（或 null）、peak（1–12，預設 2）、width（.01–.5，預設 .12）及可選 profile（129 個 1–12 有限數字，拒絕 boolean/null/錯誤長度）。profile 在相對焦點日期的 [-1,1] 日期跨度等距取樣，用 log 倍率線性插值，優先於 peak/width；不更改文章或 edge schema。focus 包含 mode（overview/single/keyword）、root_ids、query、limit。overview 不帶 roots，single 一個，keyword 必須有 query 和 roots。所有 root／位置 ID 必須在對應 view 範圍。

canonical schema 是結構合約；HTTP handler 及 snapshots.py 另有語義驗證。調整其中一層時需同時檢查另一層，不能假定只通過 JSON Schema 就能儲存。


通用探索 B 參數：entity_days=180、topic_days=60、title_days=30、topic_similarity=.10、title_similarity=.25、title_terms_min=3、coverage_first=true，其他沿用 A。新增 title_terms_min（2–6，預設4）與 coverage_first（boolean，預設false）。覆蓋優先先匹配兩端尚無連線的合格候選，再補一端孤立者，最後按原排序填滿剩餘預算；不為缺乏證據的 pair 造邊。最大天數及 days_apart schema 上限 366，A 的原始 30／7／3 天行為不變。
