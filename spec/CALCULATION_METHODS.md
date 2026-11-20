# 計算方法、範圍與目的

2026-11-06 全頁原始碼查核；2026-11-09 對 8285c09 更新 root 分段及分類統計口徑。此頁是方法索引；實作／邊界以所鏈接模組與測試為準。顯示切片、運算全集與持久資料不可混為同一集合。

## 新聞與關聯

- 來源文章按正規化 URL／穩定 ID 去重；來源 provenance 保留。儲存 membership 用 provider＋query key，股票分庫；跨來源合併不等於刪掉各來源紀錄。見 [DATA_MODEL](DATA_MODEL.md)、[model.py](../news_atlas/model.py)。
- 詞彙集合相似度是 `J(A,B)=|A∩B|/|A∪B|`。規則按 entity → topic → title 優先擇一：entity 基分 `.72+min(.20,.07×共同實體數)`；topic `.40+min(.25,J)`；title `.45+min(.30,J/2)`。各自有日期窗口與最低相似度／共同詞門檻。不是三項相加，也不是機率。
- 啟用半衰期 H 時乘 `2^(-相隔日數/H)`，H=0 不衰減；依分數／日期／ID 排序，在每端鄰居預算內選線。自適應模式先保留嚴格合格邊，再用擴大窗口的合格候選補孤立點，保留無證據的孤立點。見 [relation_settings.py](../news_atlas/relation_settings.py)、[model.py](../news_atlas/model.py)。
- `graph_payload` 對各來源完整集合建圖，再補來源配對跨來源線；已移除舊 800 篇計算截斷。3D 預設 800、最高 2400 是繪製預算，不縮小完整搜尋／Wiki 工作集合。見 [graph_payload.py](../news_atlas/graph_payload.py)。

## Root 排名、展開與 Wiki 覆蓋

- 圖內搜尋對每個查詢詞的 title／summary／symbols／entities／topics／channels 命中加 8／2／10／6／3／3，按分數降序及 ID 排序；每詞每欄位計命中，不按詞頻累加。Top N 僅取有關結果。英文短詞有邊界，四字母以上允許指定欄位詞首匹配；不是 embedding。
- 單 root 展開先過濾邊，再以 BFS、強邊優先，路徑權重為沿途權重乘積；受深度、每分支數、路徑最低權重與每樹上限約束。這不是最強路徑搜尋。多 root 的其他根是屏障，共同非根可同屬多樹。見 [SCHEMA_AND_RULES](references/SCHEMA_AND_RULES.md)、[exploration.py](../news_atlas/exploration.py)。
- Wiki Graph 以已確認 News 圖的完整 provider/id 範圍和當下規則重建相同圖；不取 GPU 切片，也不要求先點 root。從 Wiki 日期內目標按連線權重總和／ID 選 root；若該根目標已由前樹覆蓋則跳過，否則取整棵樹並扣除新覆蓋目標，直到未覆蓋集合為空。孤立新聞也有單點樹。見 [forest.py](../news_atlas/wiki/forest.py)。
- 例如 12 個月 News＋1 個月 Wiki：在 12 個月圖上取樹，只有該 1 個月新聞是完成分母；日期外及已完成成員仍可作脈絡。相似樹不重複記分，跨 provider revision 仍按實際引用身份處理。
- 覆蓋率＝已確認範圍內完成的唯一 revision／該範圍目標 revision；所選日期另有相應計數。每棵樹依每段最多 12 篇（含共用 anchor）及約 65000 JSON 字元雙界限分段，只有所有段成功發布才把本樹目標算完成；不是發出請求就算完成。固定方法批次為 5／10／15／20 篇，Graph 篇數由樹決定。見 [evidence.py](../news_atlas/wiki/evidence.py)、[compiler.py](../news_atlas/wiki/compiler.py)。

## 時間與股價大小

- 預設時間倍率 `1+(peak-1)×exp(-.5×(日距離/max(1天,日期跨度×width))²)`；使用者塑形後以 129 個相對位置樣本的 log 倍率插值取代預設鐘形。數值範圍與局部塑形見 [UI](UI.md)、[time-lens.js](../dist/time-lens.js)。
- 美東發布時間早於 09:30 可用當天完整交易日，否則從下一交易日開始；第一個完整交易日收盤 C0 為基準。N=1／3／5／7，`平均報酬=(Σ(Cj/C0-1))/N`，j=1…N。以實際存在的後續日線計交易日，不插補缺日；不足 N 天回傳缺資料。調整後價格不含股息。
- 股價倍率用完整基準日報酬絕對值 nearest-rank P95 作尺度：`z=clamp(平均報酬/P95,-1,1)`，`價格倍率=2^(2z)`，介於 .25 與 4。全零尺度則 z=0。基準日去重，不依新聞重複次數加權。
- 最終倍率 `(1-w)×時間倍率+w×價格倍率`；缺行情則只用時間倍率。3D 遠近補償作用於顯示 mesh，不改 edges／根節點／物理距離。調圖表縮放只改顯示窗口，不重算原完整域的尺度。
- K 線是當日 O/H/L/C；疊線第 j 點為基準後前 j 個收盤的累計平均，非傳統向後移動平均。分類、時間焦點、發布日期篩選和價格基準是不同概念。詳見 [PRICE_LENS](PRICE_LENS.md)。

## Wiki 知識與統計

- 模型提案只可在引用／節點型別／關係範圍驗證後發布。跨新聞 RELATED_TO 要有兩端原文引文與理由；有界檢索不等於全圖重算。版本原子發布，最後十個檢查點可選，原證據及引用保留。
- 分類選單、時間圖及清單共用目前載入圖的 `opinion_index`／taxonomy，以觀點群根計數。Thesis 沿 DEPENDS_ON、反向 SUPPORTS／CONTRADICTS 收集相依成員（每個 Thesis 群最多 200 節點）；未被涵蓋的非 ArticleRevision 節點也建立群，並非只統計 Thesis。見 [classifier.py](../news_atlas/wiki/classifier.py)。
- 每群取側欄日期範圍內最新引用新聞日，按分類標籤各計一次，最多 60 桶；多標籤總和可大於唯一觀點群數。未分類與尚待分類分開顯示，沒有日期者不畫日期柱。統計與 GPU 可見節點數分開，但受 API 載入圖範圍影響，不能聲稱無條件完整全庫。舊 direct/indirect/low/uncertain assessment 保留於詳情，不再作分類主索引；色彩不代表可信度。
- 詳情的 current_market 按目前天數及最新本機價格快取重算；生成時 market_evidence 固定保存，兩者不可互相覆寫。token 統計用實際回報與逐批日期歸屬，缺舊帳本時明示不納入。
- 視覺選取在既有 Wiki 關係三跳內、最多 150 節點高亮；其餘已渲染資料變暗，不造線、不重新排位置。這個閱讀集合不是 Graph 模式的模型工作全集。見 [WIKI_RUNTIME](WIKI_RUNTIME.md)。

## 資料合併

合併是依主鍵取聯集；同內容重複跳過，不同內容保留本地並存 merge_conflicts，版本重新對應且保留來源映射。現存庫鎖定後原地 transaction commit，新庫以排他發布建立；先備份與全量預檢，逐庫原子，非跨庫全域原子。來源工作匯入為停止，目標活躍 Wiki 拒絕合併；不啟動模型。詳見 [DATA_MERGE](DATA_MERGE.md)。
