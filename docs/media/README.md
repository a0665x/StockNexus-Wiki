# README 研究流程媒體

- `research-demo.mp4`：由使用者本機 `stocknexus-research.webm` 轉成 H.264／AAC，保留完整約62秒內容；原始檔未修改。
- `research-preview.gif`：原片20–27秒，800px寬、6fps，作README內嵌動畫；點擊可開完整MP4。
- 已依使用者提供的 `stocknexus-promo/out/v3/index.html` 確認：影片 C 為 **C / Research Desk**，來源是同目錄的 `stocknexus-research.webm`。與本次轉檔使用的來源逐位元相同，SHA-256：`ee64048bcda11916ad5d275cfedc97bad8f727979990c7e9a88c558f58e667b4`。README媒體隨儲存庫版本保存；未另行上傳GitHub影片附件。
- 原片音樂：Close Up — Michael Ramir C. / Mixkit；來源頁列有 [音樂來源](https://mixkit.co/free-stock-music/tag/technology/) 與 [授權說明](https://mixkit.co/license/modal/musicFree/)。
- 影片的Chat對話是示意；不能用來宣稱Temporal LLM Wiki runtime、研究結論或真實模型回答已完成。

本地README使用儲存庫相對路徑，提交時需一併包含兩個媒體檔。若要GitHub原生影片播放器，可將MP4附加到GitHub的Markdown編輯器，再以回傳的附件URL取代目前的預覽連結；不要填入虛構附件URL。GitHub支援影片附件並建議H.264；詳見 [官方附件說明](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files) 及 [README影片支援公告](https://github.blog/changelog/2021-05-13-video-uploads-now-generally-available/)。目前未取得GitHub託管附件URL，因此README使用動畫預覽與影片連結，並未宣稱有原生影片播放器。

## 中英文三層架構圖（2026-11-07）

- `stocknexus-architecture-zh-TW.png`：繁體中文；README 首屏架構介紹。
- `stocknexus-architecture-en.png`：英文；README 可展開及直接開啟。
- 兩圖由內建 imagegen 依使用者確認的構圖製作，屬向量插畫風格的 PNG，不是可編輯 SVG。生成指令見 [architecture-prompts.md](architecture-prompts.md)。
- 三層指 News → L1 → L2；Classifier／Taxonomy 是 L1 支援元件。圖示與連線為概念示意，不代表逐欄 DB schema、每個 root 都符合抽取條件，或已驗證的市場結論。
- 維護箭頭是更新調度，不是 L2 回灌成新聞。候選詞需審核；價格與語意解析等實作限制與 README／RESEARCH_LAYERS 同步。
