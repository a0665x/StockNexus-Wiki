/* Interface translation only. Original news, evidence and JSON are never translated. */
(function(root){
  const dictionary={
'時間貢獻':'Time contribution','股價貢獻':'Price contribution','混合倍率':'Blended size',
'滾輪縮放焦點日期範圍；雙擊還原。平均線為基準後逐日累計平均；超過 N 日遮罩。價格為歷史日線，非即時報價。':'Wheel to zoom around the focused date; double-click to reset. The line is the forward cumulative mean; prices beyond N sessions are masked. Historical daily prices, not live quotes.',

'已保留既有關聯；新資料的關聯仍在更新。':'Existing edges retained; edges for updated news are still being refreshed.',
'單一指定':'Single selection','分群渲染':'Group rendering','3D 無法啟動；請查看錯誤原因後重試。':'3D could not start. Review the error and retry.',
'新聞與關聯已載入':'News and edges loaded',
'所有來源已隱藏；請勾選顯示來源。':'All sources are hidden. Enable visible sources.',
'正在等待搜尋結果。':'Waiting for search results.',
'此搜尋目前沒有可顯示結果；請檢查來源狀態。':'This search has no visible results. Check source status.',
'此頁尚未載入搜尋結果；可搜尋或開啟已儲存圖譜。':'No results loaded on this page. Search or open a saved graph.',

'所選來源':'Selected sources','完整資料保留':'All data retained','連線':'Edges','Root 星群':'Root constellation',
"渲染預算":"Render budget",
"3D 渲染預算":"3D render budget",
"800（預設）":"800 (default)",
"3D 暫時無法使用；可重試，時間軸與新聞仍保留。":"3D unavailable. Retry is available; timeline and news are retained.",
"正在重建 3D…":"Rebuilding 3D\u2026",
"新聞已載入，正在計算關聯；可切換視圖。":"News loaded; calculating edges. Views remain available.",
"搜尋中，暫時保留上一張圖。":"Searching; previous graph retained.",
"正在讀取新聞；可切換視圖。":"Loading news; views remain available.",
"套用關聯中；目前圖譜保留，可繼續操作。":"Applying edges; current graph retained and controls remain available.",
"新聞已保留，關聯尚未完成；可在設定中重新套用。":"News retained; edges are incomplete. Reapply in settings.",
"尚無新聞；請先搜尋。":"No news yet. Start a search.",
"圖譜已就緒":"Graph ready",
"重試建立 3D；目前新聞會保留。":"Retry 3D; current news will be retained.",
"準備就緒":"Ready",
"停止等待":"Stop waiting",
"重試 3D":"Retry 3D",
"選擇分類":"Choose channel",
"分類星群":"Channel constellation",
"Root 星河":"Root constellation",
"分類亮光僅套用 3D；root 選取保留。":"Channel glow applies to 3D only; root selection is retained.",
"選擇分類；點擊新聞只查看詳情。":"Choose a channel; clicking news opens details.",
"分類模式：點擊只查看新聞，不改 root。":"Channel mode: clicking news opens details and retains roots.",
"此分類在目前來源沒有新聞。":"No news in this channel for the selected sources.",
"點擊新聞或搜尋 roots":"Click news or search roots",
"新聞已載入，正在計算關聯":"News loaded; calculating edges",
"正在讀取新聞":"Loading news",
"關聯計算未完成；新聞已保留，可在關聯設定重試。":"Edges incomplete; news retained. Retry in edge settings.",
"只限制同時繪製的節點與連線；完整資料保留於時間軸、清單與匯出。優先顯示選取項目與分類，再依日期由新到舊。":"Limits only simultaneous 3D nodes and edges. All data remains in timeline, list and export. Selection and channel take priority, followed by newest news.",
'Google 來源顏色':'Google source color','Yahoo 來源顏色':'Yahoo source color','Massive 來源顏色':'Massive source color','重設來源顏色':'Reset source colors',
'自訂分類':'Custom channels','縮小時間軸':'Zoom out timeline','放大時間軸':'Zoom in timeline','按月份取樣':'Sampled across months',
'關聯設定':'Edge settings','自適應補線':'Adaptive connections','相似度門檻':'Similarity threshold','連線限制':'Edge limits','最少共同標題詞':'Minimum shared title terms','時間半衰期（天）':'Time half-life (days)','來源內連線上限':'Within-source edge limit','跨來源連線上限':'Cross-source edge limit','優先覆蓋孤立點':'Prioritize isolated nodes','套用':'Apply','關聯計算進度':'Edge calculation progress','重新抓取已快取新聞':'Refetch cached news','儲存圖譜快照':'Save graph snapshot','略過新聞快取重新抓取，不影響圖譜快照。':'Bypass the news cache and refetch. Saved graph snapshots are unchanged.','保存目前新聞、連線與檢視設定，不重新抓新聞。':'Save the current news, edges and view settings without refetching news.',

    '通用探索 · 跨月關聯／覆蓋優先':'General exploration · Across months / coverage first',
    '標題規則最少共同詞數':'Minimum shared terms for title rule',
    '優先連接有證據的孤立點':'Prioritize isolated nodes with qualifying evidence',

"⚙ 關聯設定":"\u2699 Edge settings",
"連線如何成立？":"What makes an edge?",
"只重算已載入新聞的連線，不重新抓新聞；沒有連線的孤立節點始終保留。":"Rebuilds edges from loaded news without fetching. Isolated news nodes always remain.",
"目前使用可解釋文字規則。沒有 embedding；產業分類不參與加權，時間大小焦點也不改變 edge。":"Uses explainable text rules. No embeddings or industry weighting. The node-size date focus does not change edges.",
"選擇連線定義":"Choose an edge definition",
"原始規則 · 三種依據":"Original rules \u00b7 Three evidence types",
"同一公司／實體 · 7 天":"Same company / entity \u00b7 7 days",
"共同主題 · 7 天":"Shared topic \u00b7 7 days",
"相似標題 · 3 天":"Similar title \u00b7 3 days",
"自訂條件":"Custom conditions",
"共同公司／實體":"Shared company / entity",
"共同主題＋標題詞":"Shared topic + title terms",
"最大相隔天數":"Maximum days apart",
"最低 Jaccard 相似度":"Minimum Jaccard similarity",
"時間與連線數量":"Time and edge budgets",
"時間衰減半衰期（天，0＝關閉）":"Time-decay half-life (days; 0 = off)",
"每篇來源內連線上限":"Internal edges per article",
"每個跨來源配對的連線上限":"Edges per cross-source pair",
"Jaccard＝共同標題詞數 ÷ 兩篇標題詞的聯集數。英文以詞、中文以連續雙字比對；不是語意距離。":"Jaccard = shared title terms \u00f7 all distinct terms in both titles. Uses English words and Chinese character pairs, not semantic distance.",
"待套用定義與計分方式":"Pending definition and scoring",
"A · 顯示原始規則":"A \u00b7 Show original rules",
"B · 套用上方定義":"B \u00b7 Apply definition above",
"A／B 使用同一批已載入新聞。套用會重算候選連線；左側「延伸設定」的 edge 門檻只篩選已產生的連線，兩者不同。點選新聞可查看每條連線的依據與分數。":"A/B uses the same loaded news. Apply rebuilds candidate edges; the exploration edge thresholds only filter existing edges. Select an article to inspect evidence and scores.",

    '3D 無法使用，已切換時間軸；新聞與關聯搜尋仍可使用。':'3D unavailable. Switched to Timeline; news and relationship search remain available.',
    '3D 初始化失敗（WebGL）。':'3D initialization failed (WebGL).',
    '3D 渲染中斷（WebGL context lost）。':'3D rendering interrupted (WebGL context lost).',
    '新聞仍可使用，或切換時間軸查看。Chrome 請檢查設定 → 系統 → 圖形加速及 chrome://gpu，完成後重新載入頁面。':'News remains available; you can also switch to Timeline. In Chrome, check Settings → System → graphics acceleration and chrome://gpu, then reload the page.',
    '台灣':'Taiwan','美國':'United States','香港':'Hong Kong','日本':'Japan','英國':'United Kingdom','Yahoo 新聞 RSS':'Yahoo News RSS',
    "上下拉調整局部大小，左右拉調整該側寬度；中心左右拉可調整整體寬度。8× 起完整補償遠近。":"Drag vertically to sculpt size, horizontally to stretch that side. Drag the center sideways to adjust both sides. Full depth compensation at 8×.",
    "曲線塑形點；左右鍵選日期，上下鍵調大小，Shift＋左右鍵調寬度":"Curve point; left/right selects date, up/down sizes, Shift + left/right adjusts width",
    "直接拖曳曲線：上下調大小，左右調寬度":"Drag the curve: vertical for size, horizontal for width",
    "拖曳篩選框；收合時點擊展開":"Drag sources; click the collapsed icon to expand",
    "拖曳時間焦點；收合時點擊展開":"Drag date focus; click the collapsed icon to expand",
    "台灣 · 繁中":"Taiwan · Chinese",
    "美國 · 英文":"US · English",
    "香港 · 繁中":"Hong Kong · Chinese",
    "日本 · 日文":"Japan · Japanese",
    "英國 · 英文":"UK · English",
    "RSS 國家／地區":"RSS country/region",
    "Google／Yahoo 共用國家／地區":"Shared country/region for Google and Yahoo",
    "Yahoo 新聞 RSS ·":"Yahoo News RSS ·",
    "RSS 搜尋版本":"RSS search edition",
    "記住 Massive key（本機沿用）":"Remember Massive key on this host",
    "忘記已記住的 key":"Forget remembered key",
    "記住的金鑰會保存於瀏覽器與主機的獨立私有設定，重啟或換 port 仍可沿用；不寫入新聞 DB 或匯出檔。":"Remembered keys are stored in the browser and a separate private host file, reusable across restarts and ports. Excluded from the news DB and exports.",
    "已記住金鑰；重新整理會沿用。":"Key remembered; reused after refresh.",
    "金鑰仍在此瀏覽器；伺服器保存失敗，請重試。":"Key remains in this browser; host persistence failed. Please retry.",
    "伺服器金鑰清除失敗，請重試。":"Failed to remove the host key. Please retry.",
    "已保存於本機；重啟或換 port 會沿用。":"Saved on this host; reused across restarts and ports.",
    "已清除記住的金鑰；環境變數設定仍由主機管理。":"Remembered key cleared; environment configuration is managed by the host.",
    "主機已有金鑰，搜尋會自動沿用。":"A host key is configured and will be reused for searches.",

    '曲線塑形 · 直接拖曳任一段':'Sculpt curve · Drag any segment',
    '最大放大':'Maximum gain',
    '復原上一步':'Undo last edit',
    '直接上下拖曳曲線任一段，調整附近日期的節點大小':'Drag any curve segment up or down to size nodes near that date',
    '曲線塑形點；左右鍵選日期，上下鍵調大小':'Curve sculpt point; left/right selects a date, up/down adjusts size',
    '抓住曲線任一段上下拉，局部塑形；可分次拉出不同形狀。最高放大達 8× 時完整補償遠近。':'Drag any segment up/down to sculpt nearby dates. Repeat to shape the curve. Full depth compensation starts at 8× maximum gain.',
    '直接拖曳底部曲線塑形，調整各日期附近的放大效果。高強度會補償 3D 遠近差異；取消勾選恢復原大小。':'Sculpt the curve below to adjust magnification near each date. High gain compensates for 3D distance; uncheck for original sizes.',

    '時間曲線未載入，請重新啟動服務並重新整理頁面。搜尋、語言切換與 API 說明仍可使用。':'The time curve did not load. Restart the server and refresh the page. Search, language selection and API help remain available.',
    "拖曳底部鐘形曲線調整放大倍率與波寬。高強度會補償 3D 遠近差異；取消勾選恢復原大小。":"Drag the bell curve below to adjust gain and width. High gain compensates for 3D distance; uncheck to restore original sizes.",
    "鐘形增強 · 拖曳曲線調整":"Bell enhancement \u00b7 Drag to adjust",
    "波峰":"Peak",
    "波寬":"Width",
    "遠近補償":"Depth compensation",
    "天":"days",
    "重設曲線":"Reset curve",
    "拖曳波峰上下調整倍率，拖曳兩側調整波寬":"Drag the peak vertically for gain, or the sides for width",
    "左側波寬":"Left width handle",
    "右側波寬":"Right width handle",
    "波峰放大倍率":"Peak radius multiplier",
    "上下拉曲線調強弱，左右拉藍點調寬窄；8× 起完整補償遠近。":"Drag the curve up/down for gain, blue handles sideways for width. Full depth compensation starts at 8\u00d7.",

    "依時間距離調整節點大小":"Size nodes by date proximity",
    "接近選定日期的節點半徑最多放大為 2 倍；取消勾選恢復一致大小。日期未知維持原大小。":"Nodes near the focus date have up to twice the base radius. Uncheck for uniform sizes. Unknown dates retain the base size.",
    "時間大小焦點":"Node size date focus",
    "節點放大焦點日期":"Focus date for larger nodes",
    "圖譜日期區間 · 左舊右新":"Loaded graph range \u00b7 Oldest to newest",
    "密度格以最淺關聯深度高亮；★ 表示 root，比例表示格內命中篇數。":"Cells highlight the shallowest selected depth. \u2605 marks roots; fractions show matching articles in each cell.",
    "關聯深度":"Relationship depth",
    "未在選定樹內":"Outside selected trees",

    '候選 tree 預覽 · 點一下確認 root':'Candidate tree preview · Click to confirm root','預覽中 · 點一下進入星系':'Preview · Click to enter galaxy','靠近只預覽候選 tree，點一下才確認 root。點空白或按 Esc 回全局；單一 root 閒置 5.5 秒回全局，關鍵字多星系持續鎖定。':'Hover previews a candidate tree; click to confirm a root. Click empty space or press Esc for overview. Single roots return after 5.5 idle seconds; keyword galaxies stay locked.',
    '收合':'Collapse','展開':'Expand','歸位':'Reset position','拖曳篩選框；方向鍵移動':'Drag filter panel; arrow keys to move','比對已載入新聞的標題、來源摘要、代碼與分類；不包含未抓取的全文。':'Matches loaded titles, provider summaries, symbols and categories; excludes article bodies that were not fetched.',
    '搜尋設定已自動保存在此瀏覽器。':'Search settings are saved automatically in this browser.','瀏覽器儲存不可用；重新整理後無法保留搜尋設定。':'Browser storage is unavailable; search settings cannot survive a refresh.',
    'Roots 在目前視野外，可按「重設視角」查看全圖。':'Roots are outside the current view. Use Reset view to see the full graph.',
"圖內搜尋就緒 · v3":"Graph search ready \u00b7 v3","請輸入圖內搜尋關鍵字。":"Enter graph search keywords.","目前圖譜沒有節點，請先搜尋新聞並勾選顯示來源。":"No graph nodes. Search news and select visible sources first.","Top N 必須為 1–10 的整數。":"Top N must be an integer from 1 to 10.","搜尋中…":"Searching\u2026","個節點":"nodes","圖譜或選取已變更，請重新搜尋。":"Graph or selection changed. Search again.","已掃描":"Scanned","命中":"Matched","高亮節點":"Highlighted nodes","光暈已關閉或亮度為 0，請至光暈設定開啟。":"Glow is disabled or brightness is zero. Enable it in glow settings.","目前門檻下沒有延伸連線，僅標示 roots。":"No branches pass current thresholds; only roots are highlighted.","3D 無法使用，請查看下方 roots 清單。":"3D is unavailable. See the roots list below.","密度格不顯示星系；請切換 3D 或逐篇節點。":"Density cells do not display galaxies. Switch to 3D or individual nodes.","已套用星系；視角保持不變。":"Galaxies applied; camera unchanged.","圖內搜尋失敗；目前圖譜保留。":"Graph search failed; graph preserved.",

    '搜尋目前圖譜文字（robot 可匹配 robotics）；點圖中空白處返回全局。':'Search current graph text (robot also matches robotics). Click empty graph space to return to overview.',
    '在當下圖譜上搜尋並疊加星系；點圖中空白處返回全局。':'Search the current graph and overlay galaxies. Click empty graph space to return to overview.',
    '沒有符合的 roots；保留目前圖譜與星系。':'No matching roots. Current graph and galaxies are preserved.',
    '圖內搜尋失敗；目前圖譜與星系已保留。':'Graph search failed. Current graph and galaxies are preserved.',

    '圖內關鍵字 · 多星系搜尋':'Graph keywords · Multiple galaxies','關鍵字 / 公司 / 主題':'Keyword / company / topic','搜尋 roots':'Find roots','返回全局':'Return to overview','搜尋目前圖上的新聞；鎖定多個 root，返回全局後才能重選。':'Search loaded news; roots stay locked until you return to the overview.','尋找相關 roots…':'Finding relevant roots…','圖譜已變更，請重新搜尋。':'Graph changed. Please search again.','已鎖定 roots':'Locked roots','星系 root 鎖定後不因滑鼠移動而更換。點空白處或返回全局才能重選；單一 root 閒置 5.5 秒回全局，關鍵字多星系持續鎖定。':'Galaxy roots do not change on hover. Click empty space or return to overview to reselect. A single root returns after 5.5 idle seconds; keyword galaxies stay locked.',

    'Massive API key 如何取得？':'How do I get a Massive API key?','取得 Massive API key':'Get a Massive API key','關閉說明':'Close help','前往 Massive Dashboard，註冊或登入帳號。':'Open the Massive Dashboard and sign up or log in.','在 Dashboard 找到自己的 API key，複製後貼回這個欄位。':'Find your API key in the Dashboard, copy it, and paste it into this field.','勾選 Massive 並填入股票代碼，再開始搜尋。':'Select Massive, enter a ticker, then search.','開啟 Massive Dashboard ↗':'Open Massive Dashboard ↗','Google／Yahoo 免費來源不需要此 key。Massive 可取得的資料與歷史範圍依帳號方案而定；請勿公開分享金鑰。':'Google/Yahoo sources do not require this key. Massive data access and history depend on your account plan. Do not share your key publicly.','拖曳節點牽動關聯 · 空白旋轉 · Ctrl＋左鍵拖拉平移 · 金色線跨來源':'Drag nodes · Drag empty space to orbit · Ctrl + left-drag to pan · Gold edges cross sources',

    'Google 新聞 RSS · 台灣繁中':'Google News RSS · Taiwan / Chinese','Yahoo Finance · 美國英文 RSS':'Yahoo Finance · US / English RSS',
    '黏性強度':'Sticky selection strength','越強越容易吸附；範圍會隨縮放及節點畫面大小調整。調整時，虛線圈顯示目前 root 的吸附範圍。':'Higher strength captures nodes more easily. The area adapts to zoom and projected node size. A dashed circle previews the current root’s capture area while adjusting.','靠近或點選後保留星系，拖拉時不會消失。點空白處或閒置 5.5 秒回到全局；按住拖拉期間不計閒置。':'Exploration remains visible after hovering or selecting, including during drag. Click empty space or stay idle for 5.5 seconds to return to the overview. Held drags never time out.',

    '附近吸附半徑':'Proximity radius','靠近節點即可探索，按住可拖動；空白處仍可旋轉視角。':'Approach a node to explore; press and drag to move it. Drag empty space to orbit.',
    '資料區間':'Date range','日期設定方式':'Date range mode','自訂日期':'Custom dates','快速區間':'Quick range','回推月份':'Lookback months','3 個月':'3 months','6 個月':'6 months','9 個月':'9 months','12 個月':'12 months','以今天（UTC）為結束日，自動回推月份；搜尋時更新為當天日期。':'Count back from today (UTC). Dates refresh when you search.','區間與歷史資料限制':'Date range and historical coverage','本程式單次最多 366 天，快速區間提供 3／6／9／12 個月。Massive 實際歷史範圍依帳號授權；Google／Yahoo RSS 不保證完整歷史。長區間可能需多次補抓，請查看各來源覆蓋狀態。':'This app allows up to 366 days per search, with 3/6/9/12-month shortcuts. Massive history depends on account access; Google/Yahoo RSS does not guarantee complete history. Long ranges may require repeated fetches; check source coverage.',

    '星系光暈與深度明暗':'Galaxy glow & depth fading','啟用漸層光暈':'Enable depth glow','光暈亮度':'Glow brightness','光暈大小（px）':'Glow size (px)','每層保留亮度':'Brightness retained per hop','非關聯節點亮度':'Unrelated node brightness','取消固定 root':'Unpin root','重設光暈':'Reset glow','各層亮度預覽':'Brightness by depth','滑鼠暫時探索；點選可固定 root，移開後仍保留。深度越深越淡，點空白或按下方按鈕取消固定。光暈只影響顯示。':'Hover to explore; click to pin a root, including on mobile. Deeper nodes fade. Click the background or unpin below to clear. Glow changes appearance only.',

    '文字辨識':'Text match','來源標註':'Source annotation','文章文字':'Article text','標題':'Title','摘要':'Summary',
    '新聞關聯觀測台':'News relationship explorer','搜尋':'Search','新聞清單':'News list','真實來源 · 關聯由規則產生':'Real sources · Rule-based relationships','關閉':'Close','搜尋真實新聞':'Search real news',
    '搜尋關鍵字（Google／Yahoo）':'Keywords (Google / Yahoo)','例如 半導體、NVIDIA':'e.g. semiconductors, NVIDIA','股票代碼（僅 Massive，請明確填寫）':'Ticker (Massive only, explicit symbol)','例如 NVDA、2330.TW':'e.g. NVDA, 2330.TW','起始日期（UTC）':'Start date (UTC)','結束日期（UTC，含當日）':'End date (UTC, inclusive)','搜尋來源':'Search sources','Google 新聞 RSS':'Google News RSS','Massive API key（選填）':'Massive API key (optional)','也可在伺服器環境設定':'Or configure on the server','伺服器已設定 key，可留白':'Server key configured; may leave blank',
    '記住金鑰會存於此瀏覽器的本機儲存空間；不寫入新聞 DB 或匯出檔。':'Remembered keys are stored locally in this browser, excluded from the news DB and exports.','記住此瀏覽器的 Massive key':'Remember Massive key in this browser','清除已記住的 key':'Forget saved key','已記住此瀏覽器的 key。':'Key remembered in this browser.','已清除瀏覽器保存的 key。':'Saved browser key cleared.','瀏覽器儲存不可用；此 key 僅供本次使用。':'Browser storage unavailable; key will be used for this session only.','無法清除本機儲存；請使用瀏覽器網站資料設定清除。':'Storage could not be cleared; clear site data in browser settings.',
    '強制更新已快取區間':'Force refresh cached dates','進階關聯與多層探索':'Advanced relationships & multi-hop exploration','只篩選目前已載入、有依據的連線，不會搜尋整個 DB 或新增推論。分數不是機率；延伸路徑不是因果。':'Filter loaded evidence-based edges only; this does not search the entire DB or infer new edges. Scores are not probabilities; paths are not causality.',
    '來源內 edge 最低分數':'Within-source minimum score','跨來源 edge 最低分數':'Cross-source minimum score','滑鼠延伸深度':'Hover expansion depth','每個節點最多延伸分支':'Max branches per node','從主節點起的累積門檻':'Cumulative threshold from root','沿路分數相乘；低於門檻、已走訪節點、深度或分支上限即停止。最多高亮 150 個節點。':'Scores multiply along each path. Stop at the threshold, visited nodes, depth or branch limit. Highlight up to 150 nodes.','重設關聯設定':'Reset relationship settings',
    '本地 SQLite 快取會跨重啟保留。':'Local SQLite cache persists across restarts.','搜尋新聞':'Search news','停止等待':'Stop waiting','搜尋進度':'Search progress','尚未開始':'Not started','已完成來源比例':'Completed sources','各來源資料組成':'Source composition','DB 既有':'Already in DB','本次新增':'Newly fetched','匯出 JSON':'Export JSON','重設視角':'Reset view','儲存目前圖譜到 DB':'Save current graph to DB','已儲存圖譜':'Saved graphs',
    '分類 Channel · 新增／管理':'Channels · Add / manage','比對標題與摘要的關鍵字，一篇新聞可屬於多個分類。':'Match keywords in titles and summaries. Articles can belong to multiple channels.','自訂分類名稱':'Custom channel name','例如 機器人商業化':'e.g. Robotics commercialization','關鍵字（逗號或換行分隔）':'Keywords (comma or newline separated)','機器人, humanoid, robotics':'robots, humanoid, robotics','比對方式':'Match rule','任一關鍵字':'Any keyword','全部關鍵字':'All keywords','顏色':'Color','新增 Channel':'Add channel','更新 Channel':'Update channel','取消編輯':'Cancel editing','用最新規則重新分類':'Reclassify with current rules','編輯':'Edit','移除':'Remove',
    '連線依據：來源股票代碼、文章中的公司名稱、共同主題與標題文字。點擊新聞可檢查各條線的證據；連線不代表因果。RSS 快照不保證歷史新聞完整。':'Edges use source tickers, company mentions, shared topics and title terms. Select news to inspect evidence. Edges are not causal; RSS snapshots are not complete historical coverage.',
    '3D 新聞關聯圖':'3D news graph','新聞分類時間軸':'News channel timeline','呈現模式':'View mode','3D 關聯':'3D graph','時間軸 × Channel':'Timeline × Channel','新聞':'News','有依據的關聯':'Evidence-based edges','圖上顯示來源 · 即時篩選':'Visible sources · Live filter','依來源分組（預設混合勾選來源）':'Group by source (mixed by default)','原有來源內關聯':'Within-source edges','跨來源補充關聯':'Cross-source edges','全部分類':'All channels','管理':'Manage','時間軸縮放':'Timeline zoom','呈現方式':'Presentation','密度格 · 點選展開':'Density cells · Click to explore','逐篇節點':'Individual nodes','播放':'Play','暫停':'Pause','發布截止':'Published through','時間軸發布截止日期':'Publication cutoff','搜尋後，真實新聞會出現在這裡。':'Search to display real news here.',
    '拖曳節點牽動關聯 · 拖曳空白旋轉 · 滾輪縮放 · 點擊查看新聞':'Drag nodes to move neighbors · Drag background to orbit · Scroll to zoom · Click for details','拖曳節點牽動關聯 · 拖曳空白旋轉 · 金色線為跨來源關聯':'Drag nodes to move neighbors · Drag background to orbit · Gold edges cross sources','橫向捲動／縮放 · 發布日期（UTC）× 主要分類 · 連線非因果':'Scroll / zoom · Published date (UTC) × primary channel · Edges are not causal',
    '新聞詳情':'News details','點擊節點或新聞清單查看來源、摘要和原文。':'Select a node or article for source, summary and original link.','節點資料與標準 Schema':'Node data & standard schema','展開欄位查看值；原始文章、來源與關聯證據保持不變。':'Expand fields to see values. Article data, sources and evidence remain unchanged.','搜尋結果':'Search results','介面語言':'Interface language','調整搜尋面板寬度':'Resize search panel','調整新聞面板寬度':'Resize news panel',
    '晶片製造':'Chip manufacturing','生產／供應鏈':'Production / supply chain','財務報告':'Financial reports','股價／交易':'Stock prices / trading','產品／技術':'Products / technology','政策／法規':'Policy / regulation','其他／未分類':'Other / unclassified',
    '日期未知':'Unknown date','來源未提供摘要。':'No summary supplied by source.','閱讀原文 ↗':'Read original ↗','取得途徑：':'Acquired via: ','Channel 分類依據':'Channel evidence',' · 主要分類':' · Primary channel','未命中目前分類規則':'No current channel rule matched','與這篇新聞的關聯':'Related articles','共同實體':'Shared entity','共同主題':'Shared topic','相似標題':'Similar title','跨來源 · ':'Cross-source · ','目前沒有足夠文字依據建立關聯，保留為獨立節點。':'Insufficient textual evidence for an edge; kept as an independent node.','目前來源沒有可顯示新聞。':'No visible news for these sources.','請勾選至少一個顯示來源。':'Select at least one visible source.','點擊新聞查看來源與關聯依據。':'Select news for source and relationship evidence.',
    '此瀏覽器無法啟動 3D 圖譜，仍可搜尋並使用右側新聞清單。':'3D is unavailable in this browser. Search and the news list are still available.','這段日期沒有取得新聞。請查看來源狀態或調整日期。':'No news found for these dates. Check source status or adjust dates.','3D 無法啟動，請使用新聞清單。':'3D unavailable; use the news list.','請選擇來源並填寫關鍵字或股票代碼。':'Select a source and enter keywords or a ticker.','正在檢查本地日期覆蓋…':'Checking local date coverage…','搜尋連線提早中斷；已載入資料仍保留':'Search connection ended early; loaded data is retained.','已停止等待或連線超時。已取得資料保留；伺服器可能仍在完成本次補抓並寫入 DB。':'Stopped waiting or timed out. Loaded data is retained; the server may still finish fetching and saving.','搜尋失敗：':'Search failed: ',
    '等待中':'Waiting','檢查／補抓中':'Checking / fetching gaps','檢查快取':'Checking cache','已略過':'Skipped','部分／失敗':'Partial / failed','快取完成':'Cache ready','完成':'Complete','新增':'New','合計':'Total','查看錯誤':'Show error','覆蓋／來源說明':'Coverage / source notes','尚無資料':'No data','仍有未覆蓋日期，可稍後補抓':'Some dates remain uncovered; retry later.',
    '儲存中…':'Saving…','儲存失敗':'Save failed','儲存失敗：':'Save failed: ','尚無已儲存圖譜':'No saved graphs','請等待目前搜尋／儲存完成。':'Wait for the current search / save to finish.','已存圖譜':'Saved graph','歷史圖譜快照 · 未重新搜尋':'Saved graph snapshot · No new search','載入失敗：':'Load failed: ',' · 預設':' · Default','未命中其他分類':'No other channel matched','無法讀取分類':'Could not load channels','重新分類中…':'Reclassifying…','搜尋資料已更新，請再按重新分類。':'Search data changed. Reclassify again.','已依最新規則分類目前新聞；已存快照不變。':'Current articles reclassified; saved snapshots are unchanged.','分類失敗：':'Classification failed: ','Schema 載入失敗，請關閉後重試。':'Schema failed to load. Close and reopen to retry.','日期與分類新聞密度格':'News density by date and channel','新聞發布日期與分類泳道':'News dates and channel lanes'
  };
  Object.assign(dictionary,{"新對話": "New chat", "停止": "Stop", "傳送": "Send", "複製": "Copy", "已複製": "Copied", "新聞詳情": "News details", "右側內容": "Details panel", "向新聞助理提問": "Ask the news assistant", "整理我選取的新聞，或幫我調整畫面…": "Summarize selected news, or adjust the view…", "開啟 Chat 後連線。": "Open Chat to connect.", "已連線 · 使用本機登入": "Connected · Using local sign-in", "目前範圍：": "Current scope: ", "Roots 與關聯": "Roots and related news", "選定新聞": "Selected news", "目前結果": "Current results", "每次提問跟隨目前選取；回答期間可繼續操作。": "Each question follows the current selection; you can keep exploring.", "正在連線…": "Connecting…", "正在停止…": "Stopping…", "已停止回覆": "Reply stopped", "已停止操作": "Action stopped", "回覆完成": "Reply complete", "已開始新對話": "New conversation started", "複製失敗，請選取文字": "Copy failed; select the text manually", "連線中斷，回覆可能未完成。": "Connection interrupted; the reply may be incomplete.", "正在讀取目前新聞情境…": "Reading the current news context…", "正在讀取新聞或操作畫面…": "Reading news or updating the view…", "目前選取新聞": "Selected article", "大小依賴：時間 ↔ 股價": "Size blend: time ↔ stock return", "新聞後的平均股價報酬": "Mean stock return after publication", "報酬交易日：1、3、5、7": "Return horizon: 1, 3, 5, 7 trading days", "載入股價": "Load prices", "股價權重": "Stock-return weight", "股價": "Stock return", "交易日平均報酬": "trading-day mean return", "交易日": "trading days", "未指定股票": "No ticker selected", "讀取股價中…": "Loading prices…", "篇有完整股價": "articles with complete prices", "截至": "as of", "尚未載入股價": "Prices not loaded", "請先填入 Massive 股票代碼": "Enter an explicit Massive ticker first", "股價讀取失敗": "Price request failed", "資料不足；僅時間大小": "Insufficient data; time size only", "資料不足或尚未滿 N 日：僅使用時間大小；不視為零報酬。": "Missing or incomplete future window: time size only, not zero return.", "拆股調整後收盤價，不含股息；平均 +5% → 2×，−5% → 0.5×，範圍 0.25–4×。此為歷史後續表現，不是預測。": "Split-adjusted closes, excluding dividends. Mean +5% → 2×; −5% → 0.5×; range 0.25–4×. Historical outcomes, not forecasts.", "時間": "Time", "篇": "articles", "分類": "Category", "股價來源格式錯誤": "Invalid price-provider response", "需要 Massive API key 才能讀取股價": "A Massive API key is required for prices"});
  Object.assign(dictionary,{"上漲": "Up", "下跌": "Down", "K 線：收盤對開盤；平均線：相對基準收盤": "Candles: close vs open; mean: relative to baseline close", "焦點": "Focus", "基準收盤": "Baseline close", "資料不足": "Incomplete data", "載入股價後顯示 K 線；點選新聞或拖曳時間軸定位。": "Load prices for candles; select news or drag the time axis.", "漲跌配色": "Price colors", "美股：綠漲紅跌": "US: green up, red down", "台股：紅漲綠跌": "Taiwan: red up, green down", "平均線為基準後逐日累計平均；超過 N 日遮罩。價格為歷史日線，非即時報價。": "Line: cumulative mean after baseline; beyond N days is masked. Historical daily prices, not live quotes.", "股價時間定位": "Price date focus", "調整工具與新聞區域高度": "Resize tools and news areas", "調整兩個工具高度": "Resize the two tools", "停靠工具": "Docked tools", "放開以停靠工具": "Release to dock tool", "停靠": "Dock", "浮動": "Float"});
  Object.assign(dictionary,{'大小與報酬設定':'Size and return settings'});
  Object.assign(dictionary,{'調整視窗大小':'Resize panes','請填入股票代碼以顯示股價':'Enter an explicit ticker to show prices','沒有可用的歷史股價':'No historical prices available'});
  const patterns=[
    [/^(\d+) 篇 · (\d+) 關聯 · (\d+) roots$/,(_,a,b,c)=>`${a} articles · ${b} related · ${c} roots`],
    [/^顯示 (\d+) 節點 · 所選來源共 (\d+) 筆$/,(_,a,b)=>`Showing ${a} nodes · ${b} selected-source records`],
    [/^DB (\d+) 筆 · 圖譜快照 (\d+) 份$/,(_,a,b)=>`DB ${a} articles · ${b} snapshots`],
    [/^(\d+) \/ (\d+) 個來源完成$/,(_,a,b)=>`${a} / ${b} sources complete`],
    [/^處理中 · (\d+) 秒$/,(_,a)=>`Processing · ${a}s`],[/^搜尋完成 · (\d+) 秒$/,(_,a)=>`Search complete · ${a}s`],
    [/^讀取中 · (\d+) 次請求$/,(_,a)=>`Fetching · ${a} requests`],
    [/^API 完整 (\d+)\/(\d+) 天 · RSS 快照 (\d+) 天$/,(_,a,b,c)=>`API complete ${a}/${b} days · RSS snapshot ${c} days`],
    [/^延伸 (\d+) 個節點 · 最多 (\d+) 層 · 每節點 (\d+) 分支( · 已達顯示上限)?$/,(_,a,b,c,d)=>`${a} related nodes · Up to ${b} hops · ${c} branches/node${d?' · Display limit reached':''}`],
    [/^(\d+) 篇新聞 · 點選一篇查看內容$/,(_,a)=>`${a} articles · Select one for details`],
    [/^(\d+) 篇$/,(_,a)=>`${a} articles`],
    [/^已儲存「(.+)」· (.+) 分開保存$/,(_,a,b)=>`Saved “${a}” · ${b} stored separately`],
    [/^已載入「(.+)」· (.+)$/,(_,a,b)=>`Loaded “${a}” · ${b}`],
    [/^搜尋服務回應異常（(\d+)）$/,(_,a)=>`Search service error (${a})`],
    [/ · 相隔 ([\d.]+|—) 天$/,(_,a)=>` · ${a} days apart`]
  ];
  let lang='zh-Hant';try{if(JSON.parse(localStorage.getItem('graphnews.language'))==='en')lang='en';}catch{}
  const keys=Object.keys(dictionary).sort((a,b)=>b.length-a.length);
  function t(text){if(lang!=='en'||typeof text!=='string')return text;let result=text;for(const [pattern,replace]of patterns){const match=text.match(pattern);if(match&&match[0]===text)return text.replace(pattern,replace);result=result.replace(pattern,replace);}if(dictionary[result])return dictionary[result];
    // Translate UI fragments only; raw news/JSON subtrees are excluded by the walker.
    for(const key of keys)if(result.includes(key))result=result.split(key).join(dictionary[key]);return result;
  }
  const originals=new WeakMap(),attributes=new WeakMap();let observer=null;
  function translateNode(node){
    if(node.nodeType===3){if(!node.parentElement||node.parentElement.closest('script,style,textarea,.raw,.json-tree'))return;const old=originals.get(node),current=node.nodeValue;const source=old&&current===old.rendered?old.source:current;const rendered=t(source);originals.set(node,{source,rendered});if(current!==rendered)node.nodeValue=rendered;return;}
    if(node.nodeType!==1||node.matches('script,style,textarea,.raw,.json-tree'))return;
    for(const name of ['placeholder','aria-label','title']){if(!node.hasAttribute(name))continue;let state=attributes.get(node);if(!state){state={};attributes.set(node,state);}const current=node.getAttribute(name),old=state[name],source=old&&current===old.rendered?old.source:current,rendered=t(source);state[name]={source,rendered};if(current!==rendered)node.setAttribute(name,rendered);}
    for(const child of node.childNodes)translateNode(child);
  }
  function refresh(){if(typeof document==='undefined')return;document.documentElement.lang=lang;document.title=lang==='en'?'GraphNews · News relationship explorer':'GraphNews · 新聞關聯觀測台';translateNode(document.body);}
  function setLanguage(value){lang=value==='en'?'en':'zh-Hant';try{localStorage.setItem('graphnews.language',JSON.stringify(lang));}catch{}refresh();if(typeof root.dispatchEvent==='function')root.dispatchEvent(new Event('atlas-language'));}
  function start(){if(typeof MutationObserver==='undefined')return;refresh();observer=new MutationObserver(records=>{for(const r of records){if(r.type==='childList')for(const n of r.addedNodes)translateNode(n);else translateNode(r.target);}});observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','aria-label','title']});}
  root.AtlasI18n={t,language:()=>lang,setLanguage,start};if(typeof module!=='undefined'&&module.exports)module.exports=root.AtlasI18n;
})(globalThis);
