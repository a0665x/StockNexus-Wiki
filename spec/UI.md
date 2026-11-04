# 前端互動與狀態

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。實作索引：[ARCHITECTURE.md](ARCHITECTURE.md)。回歸合約：[BEHAVIOR_CONTRACTS.md](references/BEHAVIOR_CONTRACTS.md)。

## app.js 的狀態邊界

- `basePayload`：取得的來源圖；`focusView`：來源與 edge 門檻篩選後的圖；`currentView` 再套時間／分類顯示篩選。
- `articles`／`relations`：當下視圖；ForceGraph 自己持有物理節點及 link 端點物件。
- `networkPositions`／`internalLengths`：保持位置與來源內關聯距離，切換模式不是重建隨機佈局。
- `exportMeta`：本次圖譜或快照的取得資訊，與左側搜尋草稿不同。
- `hovered`／`candidateTrace`：滑鼠候選預覽，不是已確認 root；背景維持全局亮度。
- `lockedRoots`／`keywordLocked`／`activeTrace`：焦點及森林；`selected`：詳情文章，不能因查看文章而重選 root。
- `rootSearchTicket`／`rootSearchBusy`：等待 paint 的本地搜尋防重入／過期結果保護。

## 兩個搜尋入口

左側新聞搜尋送 `/api/search`、消耗來源請求並更新 DB。它開始新資料集，不能從圖內 Search 誤觸。

圖內 Search 是獨立 `div role=search`，按鈕 `type=button`；輸入框 Enter 攔截原生提交。直接 `AtlasView.rankRoots(articles,...)`，80ms yield 讓忙碌提示可繪製，再套森林。**不 fetch、不換模式、不改相機、不清完整資料**；超出 GPU 預算時，選取 roots 可更新顯示切片以納入原本未繪製的文章。零筆或輸入錯誤保留既有焦點；成功固定新 roots，既有圖仍在。錯誤與 warnings 明確顯示。API explore 並非此 UI 的依賴。

匹配欄位、分數與英文詞首規則見 [SCHEMA_AND_RULES.md](references/SCHEMA_AND_RULES.md)。不是全文、全 DB 或語意模型。

## 顯示與操作

預設 Google 藍／Yahoo 橙／Massive 紫紅；來源調色盤可修改並保存。勾選來源預設混合，亦可來源分組；來源內 edge 與跨來源補充 edge 分開。預設啟用時間大小焦點：UTC 日期越接近滑桿日期，半徑由 1 倍漸增至 peak（預設 2，上限 12）；日期未知不套用日期增益。設定可關閉，恢復 `.nodeVal(3)`。塑形後依自訂曲線決定倍率，可不對稱或多峰；大小不代表重要性。

滑鼠拖節點沿相機平面牽引鄰居，空白拖曳旋轉、滾輪縮放、Ctrl＋左鍵平移相機與 target。自適應吸附根據畫面投影與縮放，按住拖拉鎖定操作。靠近只預覽，點一下才確認 root，拖拉不算確認。已選 root 不因滑過／查看其他文章而切換；點空白或 Esc 清 focus，圖仍保留。

單 root 閒置 5.5 秒回全局，按住節點／平移不逾時；關鍵字多 roots 持續固定。光暈在 WebGL 同一 render 幀投影 Canvas，非圖片；多層漸淡、root 最亮、共同節點採最淺層。退場漸淡並逐步恢復背景材質亮度。調亮度／範圍／decay／背景不改關聯證據。

時間軸：UTC 發布日期 × channel。密度格共用 `focusView` 產生的 `activeTrace`，切換分類／cutoff 不清除暫時隱藏的 roots；取消來源才移除該來源不再存在的 roots。密度格以格內最淺 depth 高亮、★ 標示 root，`命中/總數 · d深度` 區分集合內部狀態；channel 計數顯示總篇數／關聯篇數／roots。集合連線只高亮選定 tree 中既有 edge。Hover 不取代已確認森林。切到時間軸或完成圖內搜尋會捲至可見 roots。

底部時間大小滑桿跟隨**已載入圖譜**的 `exportMeta.start/end`，不是尚未送出的搜尋草稿；無圖時才預覽左側日期。UTC 每日一步，60 天以上按日曆月標記，短區間約 6 格，端點顯示完整日期。`timeScale = 1 + (peak-1)*exp(-0.5*(日距離/max(1天,區間跨度×width))²)`；peak 1–12、width .01–.5（預設 .12）。ForceGraph 的幾何保持 `nodeVal(3)`，`AtlasTimeLens.attach` 包裝同一 renderer，在每幀 WebGL 前修改 node.__threeObj.scale。遠近補償強度 `c=clamp((maxGain-2)/6,0,1)`（塑形時取 profile 最大值，否則取 peak）；最終 scale=timeScale*(cameraDepth/referenceDepth)^c，referenceDepth 是 controls.target 的相機深度。behind-camera／無效深度不補償。c=1 時同日期的投影半徑一致；縮放改變參考深度，仍可縮放全圖。不呼叫 graphData、重抓資料或改相機／位置／連線／roots。吸附投影讀取 nodeVal 與 mesh.scale.x；密度格面積不變。此日期焦點與發布 cutoff 分開。

`time-lens.js` 提供曲線任意段的直接塑形，不再顯示波峰／波寬滑桿或側把手。滑鼠靠近曲線顯示日期／倍率，按住上下拖動塑形附近日期；左右拖動伸縮該側，中央 offset < .025 時雙側一起伸縮，factor 限制 .2–5；每筆 stroke 從按下時的形狀計算，不累加 pointermove 次數。相對焦點的 offset 範圍 [-1,1]，129 點等距取樣，倍率 1–12；插值在 log(gain) 空間，區間外為 1。局部 cosine brush 半徑為日期跨度的 .12（最小跨度一天），垂直位移以 SVG 高度映射 log 增益，邊界一階導數為 0。可以分次塑出不對稱或多峰，不要求保持單一 Gaussian。日期滑桿帶著形狀移動；未塑形的舊設定仍用上述 Gaussian。

Pointer capture 支援移出、反向拖動、cancel／lostcapture；按下不改值，拉回起始座標還原原形；取消／失去 capture 保留最後顯示結果並解除 busy。「復原上一步」還原上一筆 stroke 或 reset，不改焦點日期／開關；只在目前頁面保留一步。白點左右鍵選一天、上下鍵 ±.2× 局部調整，Home/End 往 1/12× 塑形；Shift＋左右鍵調寬度。控制點使用依 SVG rect 反算的 ellipse rx/ry，在畫面上維持 16px 圓形，描邊 non-scaling，ResizeObserver 在面板尺寸變化時重算。按住曲線暫停單 root 閒置計時。高頻更新只調 mesh scale，不能呼叫 graphData 或重建球體 geometry。曲線可收合；時間軸模式預設收合。設計取捨與測試見 [直接塑形紀錄](references/lesson-20261029-curve-sculpting.md)。

## 面板與瀏覽器保存

`AtlasUI.initFloatingPanel` 共用於來源和時間焦點：標題與非互動空白區拖曳、方向鍵移動、▽ 收成 36px 圖示、點圖示展開、↺ 歸位、限制在 stage 範圍；不修改來源或搜尋內容。同一 stage 的兩面板協調位置，保持 8px 間距；展開／歸位／還原／resize 都避讓，空間不足先收合另一面板，再視需要收合目前面板。互動控制項（含 label、summary、SVG 曲線）不啟動面板拖曳。左／右 sidebar 可拖分隔線調寬。JSON tree 預設隱藏值，展開才建子欄位。

localStorage 前綴 `graphnews.`：

| key | 用途 |
| --- | --- |
| searchDraft | query、ticker、sources、rss_region、dates（mode/months/custom）；不保存 forceRefresh |
| rememberKey / massiveKey | 金鑰獨立記憶／忘記；另透過 API 保存主機私有檔，不在草稿或 DB |
| exploration / glow / stickyStrength | 探索、光暈、吸附偏好 |
| timeFocus | 時間大小開關、日期、peak、width、可選 profile；快照為 view.time_focus |
| timeCurveOpen | 3D 中鐘形曲線面板的展開偏好 |
| language | 繁中或英文；時間軸固定 density，不再讀取 timelineStyle 偏好 |
| leftWidth / rightWidth / sourcePanel / timePanel | 面板寬度、位置／收合 |

`AtlasDates` 保存自訂日期草稿，快速區間重開／搜尋時按 UTC 今天更新。storage 不可用有提示。同 origin 才共享，不承諾跨裝置或跨網址同步。新聞／證據 `.raw` 不翻譯，新增 UI 文字須加入 i18n。

時間曲線是可選視覺模組：若 AtlasTimeLens 未載入，顯示重啟提示、停用曲線控制，但仍註冊搜尋、語言與 API 說明事件。修改 script 引用時須檢查實際 HTTP 路由，見首頁初始化測試。

RSS dropdown 預設 TW，選擇持久化在 searchDraft.rss_region；Yahoo 顯示相同國別與語系代碼，提交包含 rss_region，快照 restore 不改草稿。Quick range 每次點擊（即使已選中）、月份切換和 submit 都刷新 start/end；custom 草稿仍獨立保留。

金鑰輸入暫時為空不會刪記錄，記住時先保存 localStorage，change／submit／既有瀏覽器歷史載入會同步主機。伺服器只回 configured boolean，跨 port 新頁面顯示主機已配置並由後端沿用，不取回 key。保存／忘記以佇列順序執行，防止在途保存把剛刪掉的 key 復活。

## Edge 定義設定（2026-11-02）

`relation-settings.js` 是右上角原生 dialog 控制器；app.js 透過 get/put/view hooks 接上 basePayload。先編輯草稿，再按單一套用。POST `/api/graph/build` 傳各來源已載入文章及 relation_settings；回應僅替換 source_graphs.*.relations、relations、cross_relations 與設定 metadata，保留原文章物件／排序。rebuild 沿用原 3D node 物件、位置、root；不刪孤立節點、不重抓新聞、不重設相機。

新資料進來會取消／作廢舊重算，依目前已套用偏好重算新資料；等待期間標示實際原規則。API 失敗保留舊圖／已套用標示。`graphnews.relationSettings` 保存已套用值。快照載入恢復凍結設定，舊快照缺設定視為 defaults，不重新推論。快照／匯出記錄 view.relation_settings。

每條相關新聞卡片讀 evidence 中的 rule_settings/base_score/time_factor 解釋規則；預設 rules-v1 證據格式保持相容。dialog 開啟時單 root idle 視為 busy，Esc 關 dialog 不清 root。關聯設定與節點大小／視圖門檻／channel 分類彼此獨立。


圖示點擊以原生 pointer capture 行為驗證：capture 到 panel 時 click target 是 panel，故 panel 本身也處理 collapsed click，拖曳後的 click 仍抑制。避讓在必要時將已收合的另一工具移到邊角，讓正在展開的工具優先。設定 UI 已移除 A/B 與 preset select。預設 unified 自適應先保留 strict edges，再針對孤立點補上寬條件內有證據的線。Apply 在途停用並呈現 spinner／不定量 progress；成功不輸出統計摘要。欄位 tooltip 在 pointermove 顯示，靜止 2 秒後以 opacity 淡出，移動再顯示；鍵盤 focus 亦可查看。沒有保存偏好的新使用者採 unified；明確保存的偏好與載入快照的凍結設定保留。

## 時間軸精簡與跨年（2026-11-02）

UI 固定 renderDensity，移除 timelineStyle／timelinePlay 及播放計時器。舊快照的資料／cutoff 保留，呈現統一為 density。Channel 右側是 −／range／＋／倍率，縮放按固定 170px 泳道標籤與目前可視中心換算，保留時間位置。密度格日期完整 YYYY-MM-DD；發布 cutoff 保留手動操作。自訂分類入口展開側欄並捲到表單、聚焦名稱；內建分類唯讀，自訂名稱／詞／any或all／色彩可增刪改，快照規則不變。

後端及前端不裁切、不取樣，所選來源／日期內全部已取得文章皆進入圖譜；混合模式合併同 ID，來源分組保留各來源。分類與 cutoff 僅是使用者明確的篩選。超過舊 800 上限亦支援重算、分類、快照、JSON 匯出。

來源調色盤保存 graphnews.sourceColors（經 #RRGGBB 驗證），套用到 3D、glow、時間軸、來源色標及進度；預設藍／橙／紫紅，可重設，不重建節點／不重新推論。forceRefresh 不再保存到 searchDraft，初始化一律 false，保留當次明確勾選。

### GPU budget and recovery (2026-11-02)

Search, timeline, article list, snapshots and export retain complete results. On every
page initialization, 3D draws at most 800 nodes and 2,400 edges. Visible sources offers
100/200/400/800/1200/1600/2000/2400 budgets. Selection/roots and their traced neighbors (or chosen channel)
take priority, then newest articles with deterministic ID tie-breaking. Selecting a
non-rendered article from the list brings it into the GPU slice. Only edges whose two
endpoints are rendered are drawn. The status bar reports rendered/total counts; this
is not a news-retrieval cap and not a promise of GPU support.

Context loss selects an offered budget at most half the previous budget, with a minimum of 100, preserves the complete payload,
and opens Timeline. Retry destroys/recreates the renderer and reattaches interactions
and glow/time-size behavior. Failed retries remain available. Chrome graphics acceleration
and `chrome://gpu` troubleshooting remain in the failure details. No automatic retry loop.

Search first reads a matching complete graph cache; misses stream lightweight news
first, then final edges, with a phase heartbeat while computing. Previous results remain until replacement news arrives. Apply is unavailable
while search owns the payload, with a reason; views and source controls remain available.
Stop waiting immediately releases the UI and rejects stale responses. Server computation
may finish in the background. Applying errors/progress are also visible outside Settings.

Below the root search, Root constellation is the default. Channel constellation uses
channel membership without changing roots. Clicking a category node opens details;
returning to Root restores its selection. Category glow applies only to 3D.

### 3D-only correction (2026-11-02)

The requested graph renderer remains WebGL 3D. Removed the unsolicited Canvas 2D
fallback. Failures show the original error, preserve data and keep retry available;
the existing Timeline remains available. Cleanup exceptions cannot block a new 3D
constructor. The sliding switch remains 「單一指定」/「分群渲染」.

## 3D 預算與關聯偏好（2026-11-02）

渲染預算預設 800，每次頁面載入重設；選項包含 100/200/400/800/1200/1600/2000/2400。
`renderSlice` 上限 2400、edge 顯示上限為預算三倍；不改完整文章與後端選線。
GPU 故障退到不超過原預算一半的既有選項，最低 100。

右上 Edge settings 的欄位為草稿，按套用成功才寫入同 origin 的 relationSettings。
刷新從保存值原樣正規化，不把使用者明確保存的 original/general 覆寫成 unified。
新使用者無保存值才使用 unified。搜尋使用 preferred；快取同時核對文章與規則。
快照載入可在本次頁面還原自己的設定，但不是跨頁面保存偏好的替代品。

相關操作順序見 [WORKFLOWS.md](WORKFLOWS.md)，診斷證據見 [渲染／快取／設定紀錄](references/lesson-20261102-rendering-cache-settings.md)。

## 2026-11-04 探索展示預設

新頁面使用 800 節點渲染預算，三個搜尋來源預設全選。探索預設為來源內／跨來源最低分數 0.5／0.5、深度 2、每節點分支 6、累積門檻 0.4、最多高亮 150 節點。光暈開啟、亮度 1.55、半徑 25px、每層保留 90%、非關聯節點亮度 18%。

`graphnews.explorationPresetVersion` 一次性更新既有瀏覽器的 exploration、glow 與搜尋來源；保留 query、ticker、日期等草稿。之後手動變更仍持久化，不會每次刷新覆寫。重設探索／光暈回到這組預設。凍結快照仍按原設定還原，不改寫既有快照或新聞／關聯證據；載入舊快照後可使用重設探索、重設光暈套用新版視覺預設。分數不是機率，路徑不是因果；只篩已載入的有依據連線。

800 節點分類高亮時，節點光暈使用 source-over 疊色，避免數百個漸層以 additive 相加變成白色塊；關聯線仍使用 additive。亮度／半徑／深度設定與節點／證據集合不變。

## 2026-11-04 大量節點的計算與 DOM 邊界

3D上限仍為預設800點／2400線；新聞清單與時間桶詳情改每頁100篇，完整結果可翻頁、圖內搜尋、Chat選取與匯出。分類priority不會覆蓋已選取節點，相同GPU切片不重新設定graphData。關聯樹使用目前邊版本的索引及最多16組結果／cache，hover不反覆重建固定root；單點吸附只投影該點。關鍵字規則每查詢建立，Top N排名保持原語意。實測與界線見 [大量圖譜效能紀錄](references/bugfix-20261104-large-graph-performance.md)。

目前視圖優先建圖與四項狀態說明：見 [視圖關聯流程](references/view-first-relations-20261104.md)。預算外新聞延後計算；四個狀態標籤滑鼠靜止650ms顯示說明。

視圖重用：狀態列區分「新算／重用」配對數及完整視圖命中。快照保存渲染預算與最多12組完成視圖，載入同範圍可直接使用edge；顯示門檻不裁切保存的原始關聯。詳見[增量重用與快照](references/view-first-relations-20261104.md)。
