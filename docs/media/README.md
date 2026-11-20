# README architecture figures

The [English README](../../README.md) uses [the English figure](stocknexus-architecture-en.png). The [Traditional Chinese README](../../README.zh-TW.md) uses [the Traditional Chinese figure](stocknexus-architecture-zh-TW.png). Both PNGs keep their original public paths.

## Update the figures

The [English original](architecture-sources/original-en.png) and [Traditional Chinese original](architecture-sources/original-zh-TW.png) from commit `5c7e45e` are the visual masters. Keep them at their native 1536 × 1024 scale. Edit the [bilingual overlay](architecture.svg) for corrections or additions. It updates the Yahoo source badge and appends two illustrated insets for tree workers and personal document collections. The [document robot](architecture-sources/document-robot.png) matches the original L1 mascot.

With librsvg, Liberation Sans Narrow, DejaVu Serif and Noto CJK fonts installed, run these commands from the repository root.

```bash
rsvg-convert --accept-language en -o docs/media/stocknexus-architecture-en.png docs/media/architecture.svg
rsvg-convert --accept-language zh-TW -o docs/media/stocknexus-architecture-zh-TW.png docs/media/architecture.svg
```

Inspect both 1536 × 1186 exports. In each upper panel, a pixel comparison with its visual master should show differences only inside the edited Yahoo badge. Check the localized footer for clipping at full size and at README width. [Illustration notes](architecture-prompts.md) · [Tree workers](../../spec/WIKI_RUNTIME.md) · [Document import](../../spec/DOCUMENT_IMPORT.md)

## 歷史影片資產

依 2026-11-08 使用者要求，影片已從兩份 README 移除；原資產留存，沒有刪除原片。

- `research-demo.mp4`：影片 C / Research Desk，約 62 秒，源自使用者的 `stocknexus-promo/out/v3/stocknexus-research.webm`。
- `research-preview.gif`：原片 20–27 秒的 800px／6fps 預覽。
- 原始影片 SHA-256：`ee64048bcda11916ad5d275cfedc97bad8f727979990c7e9a88c558f58e667b4`。
- 音樂：Close Up — Michael Ramir C. / Mixkit。[來源](https://mixkit.co/free-stock-music/tag/technology/) · [授權](https://mixkit.co/license/modal/musicFree/)。
