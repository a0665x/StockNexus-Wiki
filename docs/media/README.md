# README architecture figures

The [English README](../../README.md) uses [the English figure](stocknexus-architecture-en.png). The [Traditional Chinese README](../../README.zh-TW.md) uses [the Traditional Chinese figure](stocknexus-architecture-zh-TW.png). Both PNGs keep their original public paths.

## Update the figures

Edit the labels and connectors in [architecture.svg](architecture.svg). Both languages share one layout and one [unlettered illustration](architecture-art.png). The blue, green and purple panels follow stock news through L1 and L2. The document import below them has its own collection database. [Research contract](../../spec/RESEARCH_LAYERS.md) · [Tree workers](../../spec/WIKI_RUNTIME.md) · [Document import](../../spec/DOCUMENT_IMPORT.md)

With librsvg, DejaVu Sans and Noto Sans CJK TC installed, run these commands from the repository root.

```bash
rsvg-convert --accept-language en --width 1800 --output docs/media/stocknexus-architecture-en.png docs/media/architecture.svg
rsvg-convert --accept-language zh-TW --width 1800 --output docs/media/stocknexus-architecture-zh-TW.png docs/media/architecture.svg
```

Inspect both exports at README width after editing. The [illustration notes](architecture-prompts.md) record the artwork's provenance.

## 歷史影片資產

依 2026-11-08 使用者要求，影片已從兩份 README 移除；原資產留存，沒有刪除原片。

- `research-demo.mp4`：影片 C / Research Desk，約 62 秒，源自使用者的 `stocknexus-promo/out/v3/stocknexus-research.webm`。
- `research-preview.gif`：原片 20–27 秒的 800px／6fps 預覽。
- 原始影片 SHA-256：`ee64048bcda11916ad5d275cfedc97bad8f727979990c7e9a88c558f58e667b4`。
- 音樂：Close Up — Michael Ramir C. / Mixkit。[來源](https://mixkit.co/free-stock-music/tag/technology/) · [授權](https://mixkit.co/license/modal/musicFree/)。
