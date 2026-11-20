# Wiki timeline and comparison workbench

## Reading a published Wiki

The L1 chart counts viewpoint groups by the UTC date of their latest cited news in the chosen interval. A multi-label viewpoint contributes once to each of its classifications. The original sidebar date interval continues to govern the available chart dates. Chart navigation and window geometry run entirely in the browser.

The chart starts below the graph. Drag its title or use the expand icon to open a floating window. Its edges and corners resize it. The dock icon returns it below the graph. Minimize leaves a square chart icon inside the graph and releases the lower pane height. Reopening restores the previous presentation, classification and dates. The window mode and floating geometry also survive a page reload in the same browser. An open L2 report has its own lower pane.

Select a legend entry to isolate its series and filter the graph. Select it again to see all classifications. Other legend entries stay available for a direct switch. The return arrow restores all series and the full sidebar interval. It preserves the separate node-type selection. A wheel gesture zooms around the pointer. Drag horizontally to change the visible days without changing their count. Horizontal wheel input also pans. The focused plot supports the arrow keys, plus, minus and Home. A deliberate bar click or keyboard activation opens the dated viewpoints in the details tab.

The six graph filters center their labels and values and wrap as the center column narrows. The brand pairs a connected-node mark with a readable StockNexus Wiki wordmark. The chart, settings dialog, L1 archive and comparison reader use the same icon controls with localized names and tooltips for reset, close and paging. Selecting viewpoints and submitting a model comparison retain visible action labels. The comparison reader accommodates long selections and history on desktop and fits the phone viewport.

## Acceptance evidence, November 20, 2026

| Given | When | Observed outcome |
| --- | --- | --- |
| Previous commit `43fb921` at 1223 × 914 | Click Energy twice, wheel then drag, and open comparison | Chromium still showed only Energy after the second click. Dragging replaced the SVG receiving the gesture. The dialog measured 440 CSS px wide. |
| A TSLA fixture with two series over 100 dated viewpoints | Press Energy, refresh the graph while the pointer is down, release, then click Energy again | The same button receives the release and filters the bars. The second click restores both series and the toolbar selection. The independent node-type filter survives. |
| A zoomed plot | Perform real mouse drags in opposite directions, then press Home | The start day moves in both directions with constant interval length. The SVG retains identity. No bar opens during the drag. Home restores the full interval. A separate click on a bar opens its own dated list. |
| A docked chart | Drag its title, move it again, resize its corner, minimize and reopen with Enter | Geometry changes with the pointer. The graph gains height, focus moves to the square launcher, and reopening restores position, dimensions, dates and series. Minimized mode survives reload. |
| A saved comparison and a long selected viewpoint | Open, select, inspect and press Escape at desktop and phone widths | The selection has a separate remove action. The dialog fits at 390 × 844 without horizontal overflow. Escape restores focus to its opener. Icon names and tooltips are available in English and Traditional Chinese. |
| A phone-width floating chart | Pan a zoomed window with Chromium touch input | The window stays in bounds and the dates advance without selecting a bar. The reading journey submits zero Wiki POSTs. |
| The L1 chart is minimized | Open a completed L2 run | The report and citations are visible. Returning to L1 restores the chart launcher. |
| A Wiki layout, selected model and date interval saved on the server | Open a second fresh Chromium profile | The host returns the selected controls and pane dimensions. The previous server rejected the frontend's `research_run`, `wikiWorkers` and `layout.changes` fields. Their types and bounds are now validated. |

The focused browser journey is `python3 tests/browser_wiki_timeline.py`. Related coverage lives in `browser_wiki_layout.py`, `browser_wiki.py`, `browser_research.py` and `browser_workspace.py`. The workspace fixture dates follow the UTC clock so its news rows stay in the startup search interval. The stock, chart data and comparison history used for this fixture belong to the test. Touch results come from Chromium emulation.

Physical input also exposed a layout shift when the graph regenerated its 3D legend above the timeline. The reader now preserves that legend across refreshes and reserves each thumbnail's final dimensions before WebGL paints it. The L2 argument suite verifies the rendered images for the actual supporting and opposing meshes.

## Production verification

A fresh Chromium profile opened TSLA v124 through Tailscale HTTPS. It rendered 17 series. Energy toggled on and off, and a horizontal drag advanced the zoomed window by 30 days. The floating window measured 720 × 400 CSS px and reopened on the same day after minimizing to a 40 × 40 launcher. Comparison measured 920 px at a 1223 px viewport and 366 px at a 390 px viewport. The smoke isolated shared workspace writes and observed zero model submissions or browser errors.

The deployment preflight found 18 idle Wiki stores with maintenance and catch-up disabled. The normal launcher returned a healthy container using image `25e52f949f7b48751c3592a980496a37769ccf98c4c4116bbfd9f371162823a9`. The prior image is tagged `news-atlas:before-wiki-timeline-20261120`.
