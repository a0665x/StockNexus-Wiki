# Wiki timeline and comparison workbench

## Reading a published Wiki

The L1 chart counts viewpoint groups by the UTC date of their latest cited news in the chosen interval. A multi-label viewpoint contributes once to each of its classifications. The original sidebar date interval continues to govern the available chart dates. Chart navigation and window geometry run entirely in the browser.

The chart starts below the graph. Drag its title or use the expand icon to open a floating window. Its edges and corners resize it. The dock icon returns it below the graph. Minimize releases the lower pane height and leaves a square chart button that can move across the Wiki workbench. Reopening restores the previous presentation, classification and dates. The window mode and floating geometry also survive a page reload in the same browser. An open L2 report has its own lower pane.

Select a legend entry to isolate its series and filter the graph. Select it again to see all classifications. Other legend entries stay available for a direct switch. The return arrow restores all series and the full sidebar interval. It preserves the separate node-type selection. A wheel gesture zooms around the pointer. Drag horizontally to change the visible days without changing their count. Horizontal wheel input also pans. The focused plot supports the arrow keys, plus, minus and Home. A deliberate bar click or keyboard activation opens the dated viewpoints in the details tab.

The six graph filters center their labels and values and wrap as the center column narrows. The header displays the user-supplied ribbon and wordmark from `dist/stocknexus-wiki.png`. The chart, settings dialog, L1 archive and comparison reader use the same icon controls with localized names and tooltips for reset, close and paging. Selecting viewpoints and submitting a model comparison retain visible action labels. The comparison reader accommodates long selections and history on desktop and fits the phone viewport.

## Movable tools and replaceable header artwork

The News source filters, News time and size focus, and Wiki citation timeline share a square launcher with a named line icon. The button measures 40 CSS pixels on desktop and 44 at viewport widths up to 800 pixels. Drag a title across the workbench, including over a sidebar, or drag the minimized icon by itself. Click, tap, or press Enter or Space to reopen. Arrow keys move a focused launcher in 20-pixel steps. The window and its launcher have independent positions in this browser profile. The visible viewport below the header bounds both.

News initially places its tools below the graph controls. A user-positioned tool can use the entire News workbench. If tools collide, the active tool gets priority. An expanded tool can still resize from an edge or corner. Minimizing a docked tool temporarily releases its split space. Reopening returns it to the same split with the saved ratio. Switching to Wiki hides News tools. L2 reports retain their own reading pane.

Replace the active file `dist/stocknexus-wiki.png` and run `./run.sh up` from the project root. Reload the browser to see the replacement. Both surfaces use the same header and asset URL. The HTTP handler serves the PNG with revalidation, and the normal launcher rebuilds the image from `dist/`. The release includes the broader wordmark at the active path and the earlier ribbon as `dist/stocknexus-wiki_v2.png`. Both original PNGs retain their transparent padding.

## Resizing the shared header

The left-aligned wordmark scales with the header. Drag anywhere along its bottom edge. Double-click the edge to restore the responsive default. The separator also accepts the up/down arrow keys in 8-pixel steps and Home to reset. The browser saves a completed resize under `graphnews.headerHeight`. Cancelling a touch restores the prior height. Shrinking the viewport temporarily limits the rendered height and preserves the saved preference.

`frameBrand` samples the PNG's alpha channel on image load. It frames the visible artwork and leaves a small margin for antialiased edges. Opaque replacements use their full bounds. The logo keeps its proportions up to the available width. At phone widths, or when a second row gives the wordmark more room, the controls sit below it. News sources use a stacked database icon. The time and size focus tool uses a magnifier around a curve. The same glyph appears beside each expanded title and at the center of its minimized square.

| Given | When | Then |
| --- | --- | --- |
| A fresh profile and the active wordmark at 1223 × 914 | Drag the global edge down 52 px while reading L1, then to its limit | Header height changes from 68 to 120 CSS px. Visible artwork grows from 53.2 to 73.9 px. At the 180 px limit it can occupy the full first row. Wiki and News remain aligned to the bottom edge. |
| A saved header height | Reload, briefly shorten the viewport, use the arrow keys, then press Home | Reload restores the height. The saved value survives the temporary viewport clamp. Home clears the preference and restores the responsive default. |
| A 690 × 914 touch viewport | Cancel a drag, then complete a 66 px drag and open the News search drawer | Cancellation restores 60 px. The completed drag gives a 126 px header. Visible artwork grows from 34.5 to 62.0 px. The drawer starts below it. Double-click restores the default. |
| A 390 × 844 phone | Enlarge the header, switch languages and substitute an opaque 2:1 PNG in the fixture | The wide wordmark already spans the available 374 px. Its measured ink height stays at 34.8 px as the header goes from 94 to 114 px. Chinese and English controls stay reachable, including at 320 px. The replacement retains its whole image and aspect ratio. |
| An expanded or minimized News tool | Open, minimize, move, reload and reopen it at desktop and compact widths | The database and magnifier stay paired with their tools. The center of each drawn path is within one CSS pixel of its icon slot or square button center. The Wiki timeline retains its centered bar-chart icon. |

The measured heights come from visible pixels in a separately sampled copy of the served image. Use the dedicated header and timeline journeys from the repository root. [Header gestures and replacement](../../tests/browser_workbench_header.py) · [Launcher geometry and chart navigation](../../tests/browser_wiki_timeline.py) · [Release test commands](../TESTING.md#workbench-release-verification)

### Browser acceptance for the three tools

| Given | When | Verified result |
| --- | --- | --- |
| A 1223 × 914 News workbench with both tools | Drag each expanded title into the left sidebar, minimize, drag the square into the right side, reopen, minimize and reload | The windows reached their chosen sidebar coordinates. Both icons measured 40 × 40. Reopening restored each window's position and dimensions. Reloading restored the two distinct launcher positions. |
| A 690 × 914 viewport with an open News drawer | Drag the source icon by touch, cancel a second drag, tap it, then drag the time window over the open drawer | Both launchers fit within the viewport at 44 × 44. Cancellation restored the source icon. The tap opened its window and the time window received input over the drawer. The header image and actions fit in one row. |
| Two nested News splits | Dwell on two different pane edges, reload, cancel a touch undock, then collapse both tools and move a launcher before reloading again | The originally expanded tools stay open in their leaves. Minimizing releases the space to News. Each launcher reopens its original split. A committed undock gives the space to the sibling. |
| A filtered and zoomed Wiki timeline | Move its minimized icon with mouse, arrow key and emulated touch, scroll the Wiki, reopen and reload | Dragging keeps it closed. The square retains its viewport position during scrolling. Reopening restores the chart geometry, dates and filter. The gesture journey submitted zero Wiki jobs. |
| A PNG at the documented source path | Request the header and its referenced image through the HTTP handler | The image response has the PNG media type, cache revalidation and the source file's exact bytes. A 690-pixel browser displays the full wordmark. |

The BDD journey is in `tests/browser_wiki_timeline.py`. `tests/browser_floating_resize.py` additionally exercises edge and corner resizing, scrolling and graph data identity. Touch results come from Chromium emulation.

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

## Tailscale delivery of the resizable header and icons

The standard launcher rebuilt the service after a read-only check of 18 idle Wiki stores. Docker reported a healthy container on image `44833af77b6a96c474c2de4e4c736b4f884c421a9788ad2e1756f6f770f28fc4`. The pre-release image is tagged `news-atlas:before-resizable-header-20261120`.

HTTPS delivered the new header markup and exact checkout bytes for the workbench stylesheet, explorer UI, translations and active PNG. The active PNG's SHA-256 is `bde6524d12e6dd80c969f338ca8a06789f39d132347c061277bdcb623cb65866`. A fresh Chromium profile measured both News launcher path centers, dragged the shared header while reading published TSLA v124 and restored its height after reloading. Desktop and compact artwork heights matched the fixture above. Workspace writes, price lookups and graph previews were isolated for the smoke. It recorded zero model submissions and zero browser errors.

## Earlier Tailscale delivery of the floating tools and logo

The normal launcher rebuilt the web service after a read-only check of 18 idle Wiki stores. Docker reported a healthy container with image `d23da706d74cb6f09a3c1b4426081a91ccd012401ae79e8e0de66c602d0d4d2e`. The previous production image is tagged `news-atlas:before-floating-tools-20261120`.

HTTPS returned the same bytes as the checkout for the ten changed frontend assets. The served ribbon, the tracked PNG and the user attachment all had SHA-256 `fef1aae9420f97d32a3e1bbcde0ec0266d76117a0b174c0058d91e97e9c428e2`.

A fresh Chromium profile opened the production News workbench and the published TSLA Wiki v124. Both News tools crossed into the sidebar and reopened at their previous geometry. At 690 × 914 the header PNG used 164 CSS pixels of width. The Wiki launcher measured 44 × 44 and reopened on tap after a touch drag. The smoke isolated workspace saves, price requests and graph preview calls. It observed zero browser errors and zero model submissions.

## Earlier production verification of chart navigation


A fresh Chromium profile opened TSLA v124 through Tailscale HTTPS. It rendered 17 series. Energy toggled on and off, and a horizontal drag advanced the zoomed window by 30 days. The floating window measured 720 × 400 CSS px and reopened on the same day after minimizing to a 40 × 40 launcher. Comparison measured 920 px at a 1223 px viewport and 366 px at a 390 px viewport. The smoke isolated shared workspace writes and observed zero model submissions or browser errors.

The deployment preflight found 18 idle Wiki stores with maintenance and catch-up disabled. The normal launcher returned a healthy container using image `25e52f949f7b48751c3592a980496a37769ccf98c4c4116bbfd9f371162823a9`. The prior image is tagged `news-atlas:before-wiki-timeline-20261120`.
