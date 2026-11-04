# 實作與驗收計畫

入口：[設計](../../TEMPORAL_WIKI.md)／[契約](data_contract.md)。狀態：第一階段；2026-11-04。保留既有 main 本機修改，在 `llm_wiki` 進行。本文件描述下一階段工作，不代表功能已實作或20項測試已通過。

## 本階段實際交付

診斷報告、90篇本地結構抽樣、read-only audit CLI、領域詞彙、時間／資料／edge契約、互動流程、Relation strict JSON Schema、synthetic fixture及離線設計檢查。未呼叫 provider／LLM，沒有新建正式 Wiki DB、compiler、UI轉換按鈕或回測結果。

可執行：

```bash
python3 scripts/wiki_readiness.py --sample-size 30
python3 scripts/verify_wiki_design.py
python3 spec/scripts/verify_docs.py
```

`verify_wiki_design` 使用開發環境的 jsonschema（本次4.26.0），不新增正式服務相依。檢查例子的格式、拒絕CAUSES／混合分數／缺引用及fixture算式；不宣稱驗證引用在真實DB存在、無洩漏或金融效果。實際結果記在 [validation.md](validation.md)。

## 實作位置與模組邊界（名稱為提案）

| 模組 | 擬議接口／責任 | 整合位置 |
| --- | --- | --- |
| `news_atlas/wiki/store.py` | open(instrument), versions_as_of(), apply_patch(base_version, key), freeze_snapshot()；封裝SQLite／manifest隔離與原子性 | 新store，不改legacy `Store` 意義 |
| `news_atlas/wiki/ingest.py` | plan(selection), capture(outbox), changed_since(cursor)；把來源選取與修訂轉成durable工作 | `storage.py` outbox＋原query/membership；使用前需單獨migration及回歸 |
| `news_atlas/wiki/compiler.py` | run(plan,budget), resume(run), cancel(run)；排隊／cache／重試／依賴重評 | 獨立worker＋受限SDK bridge，重用chat的程序隔離經驗 |
| `news_atlas/wiki/retrieval.py` | candidates(instrument,as_of,run,claims,limit)；同股FTS/實體/時間 | 不依賴3D可見點，root只加候選hint |
| `news_atlas/wiki/render.py` | publish(graph_version)；MD/JSON同版本＋links lint | versioned exports，不覆蓋原snapshot |
| `news_atlas/wiki/labels.py` | mature(snapshot,horizon,price_cut) | 新行情adapter/calendar；不改price_lens原公式 |
| `news_atlas/wiki/research.py` | select_analogs(X,as_of), summarize(Y), evaluate(fold), ledger(config) | labels隔離讀取權限；LLM不寫數值 |
| `dist/wiki-view.js`＋API | plan/commit/jobs/graph/as_of頁面 | `server.py`明確路由、`app.js`新圖切換；不要默默支援任意路徑 |
| `prompts/wiki/<version>/`＋schema | 四個獨立prompt及I/O schema；mock與人工評估集 | runtime compiler功能階段再加入；本輪只定義契約 |
| `scripts/wiki.py` | 互動planner/preview/run/status/resume | `run.sh wiki`擬新增dispatch，目前尚不能執行 |

API提案：POST `/api/wiki/plan`→短效plan_id/hash與預估；POST `/api/wiki/jobs`帶plan_id/model/budget→202；GET job/status；POST cancel；GET graph含instrument/run/as_of；GET page按manifest版本。plan hash含選取revision、query scope與target graph version，失效時重預覽。所有mutation沿用並加強本機來源檢查、path validation、capability防重放；不得新增未認證的雲端花費入口。正式endpoint／OpenAPI要在實作時一起測試。

## 推進關卡

1. **診斷與契約（本輪）**：確定舊圖是規則候選圖、缺版本、摘要非全文；交付現在的文件與schema。資料夾更名後驗證runtime/DB及保留Git變更。
2. **單股20篇閉環**：先以本地synthetic/mock建立所有20篇capture→extract→patch→render→as_of流程，完成outbox migration、四prompt/schema、bounded worker、雙階段preview/run CLI；再由使用者在互動入口選定股票與模型預算執行真實pilot。以保留人工標記集確認引用與合併品質；通過1–8、18–19的自動測試才擴大。沒有新聞變動時不呼叫模型。
3. **標籤與類比**：鎖定calendar/provider版本，明定行情能力與缺口，建立price ledger、maturity worker、X/Y隔離、合格類比與描述性統計；通過9–16，不足時輸出null。先不輸出校準機率。
4. **驗證與模擬策略**：預登記fold/threshold/cost，三基準、purge/embargo、校準檢驗、試驗帳本及持倉帳本；通過17與全部反洩漏測試，再做前向紙上模擬。金融表現可能無提升，照實報告；沒有broker接入。
5. **網站與運維**：把已驗證CLI planner接到原圖選取，加入版本、coverage、jobs、取消與恢復、類比／結果對照；驗收HTTP資產路由、UI草稿保留與20的規模測試。CLI互動在階段二已有，完整視覺在本階段。

建議第一個pilot由互動入口明確選一股；先20篇跨時間含修訂、晚到、轉載及反證的樣本，而不是把目前33,017來源列一次送入模型。資料不夠完整時保留缺口，不為了展示完整而補造內容。

## Migration／rollback

- 新建研究庫自己的 `schema_migrations`，不能讓legacy Store初始化它；新版啟用flag預設關閉。bootstrap先preview並複製指定來源的不可變證據，記錄來源query及hash，不搬走原文章。
- 階段二必要的legacy outbox採獨立migration：交易內新增表／trigger或寫入hook，migration ledger與checksum；升版前以SQLite backup API取得一致備份（不能只複製正在寫入的.db而漏WAL）。備份需驗證integrity與row counts，記錄切換時間。
- 研究庫遷移在每股鎖內transaction執行；大版本copy-on-write到新庫，驗證後切manifest。途中取消時舊庫仍可讀，不刪pending紀錄。
- rollback：停止Wiki worker→關flag→保留研究庫／outbox作診斷→繼續舊NewsGraph。撤銷patch用compensating patch產生新版本，舊snapshot仍可讀。只有確定沒有新寫入才可整庫恢復備份，否則先reconcile，禁止直接覆蓋live DB。
- 目錄更名保留固定Compose project `news-atlas`，先停舊container/chat再改路徑，從新路徑重建mount/labels；資料不改名，不為品牌名稱改DB keys／瀏覽器偏好。失敗先保存錯誤，必要時停新程序後原子改回舊名並重啟。

## 20項驗收對照（runtime均待實作）

| # | 未來測試組／關鍵斷言 | 階段 |
| --- | --- | --- |
| 1 | idempotency：同batch重跑IDs/count不變；no-change LLM calls=0 | 2 |
| 2 | cross-root：同revision抽取cache hit；候選版本變仍重做關係判定 | 2 |
| 3 | revisions：同URL新hash有新revision；轉載不增episode獨立數 | 2/3 |
| 4 | late-arrival：今天補三月前新聞只進今天live latest | 2 |
| 5 | append-only：新增反證後舊forecast bytes/hash不變 | 2/3 |
| 6 | bounded-update：無依賴頁hash不變；不同branch仍可發現關係 | 2 |
| 7 | resilience：循環、有界傳播、kill/retry、CAS衝突／同股兩worker | 2 |
| 8 | isolation：兩股票同ID／相同query不能互讀DB/cache/index/statistics | 2 |
| 9 | calendar：週末/假日/DST/盤後/缺published/停牌/缺價與嚴格entry | 3 |
| 10 | returns：100→102,98,105；R3=.05,A3=1/60；N1、weighted mu | 3；目前只驗證fixture算式 |
| 11 | maturation：pending/null→matured；只新增outcome，forecast不變 | 3 |
| 12 | analog-cut：逐N排除晚成熟、後來事件描述 | 3 |
| 13 | future-insertion：插T後文章/edge/outcome，不改T的X/候選/forecast | 3 |
| 14 | future-label-mutation：把不可見Y改極端值，當時預測不變 | 3 |
| 15 | leakage-sentinel：故意注入latest摘要/全期分群/normalizer必須失敗 | 3/4 |
| 16 | missingness：API failure≠successful empty；類別缺失不得產生機率 | 2/3 |
| 17 | ledger：同日新聞不疊加收益；缺借券short hypothetical | 4 |
| 18 | provenance/render：每claim span可回讀；所有links/hash與graph版一致 | 2/5 |
| 19 | injection：惡意內容不能執行指令／讀憑證／擴工具權限 | 2 |
| 20 | scale：10k可恢復；20新文量測pages/tokens/cost/pending、非全庫prompt | 5 |

品質評估另有人工reference：事件merge/split、原子claim、span、contradiction scope、時間抽取；人工歧義也保存，不把schema pass當正確率。規模測試用synthetic或授權樣本，所有金融fixture標 `is_fixture=true`。

## 初始配置提案

```json
{
  "schema_version": "0.1",
  "instrument_id": "REQUIRE_EXPLICIT_SELECTION",
  "mode": "live_recorded",
  "timezone": "America/New_York",
  "cutoff_local": "17:00",
  "horizons": [1, 3, 5, 10, 20],
  "entry_policy": "next_regular_open_strictly_after_ready",
  "min_episodes": 20,
  "min_weight_effective_n": 10,
  "batch_articles": 20,
  "candidate_page_limit": 12,
  "max_input_tokens": 16000,
  "max_output_tokens": 4000,
  "max_run_tokens": 100000,
  "max_propagation_depth": 3,
  "model_revision": null,
  "daily_cost_limit": null,
  "execution_delay_seconds": null,
  "costs": {"commission": null, "spread": null, "slippage": null, "borrow": null},
  "thresholds_by_horizon": null,
  "automatic_schedule_enabled": false,
  "execution_enabled": false
}
```

null是必須補設定／資料，不能解釋成零成本或零延遲；沒有model revision不能開始LLM run，沒有execution/cost/threshold配置不能做策略績效。啟動器只展示尚未定義項目，日後由實際設定與測試鎖定。
