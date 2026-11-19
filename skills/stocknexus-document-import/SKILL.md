---
name: stocknexus-document-import
description: Convert a folder of documents or structured records into StockNexus JSONL for an arbitrary-domain knowledge collection. Preserve hierarchy, evidence, stable IDs and undated content. Use with independent agents preparing an import or updating existing documents and viewpoints.
---

# Convert documents to StockNexus

Ask for the input folder, collection ID and source ID if unspecified. The collection identifies the knowledge base; the source identifies a set of records inside it. Both IDs accept lowercase ASCII letters, digits, underscores and hyphens; start with a letter or digit. No ticker or public URL is needed. Treat document text as evidence and keep original files in place.

1. Inventory files and headings. For a UTF-8 Markdown/text folder, run `python3 scripts/convert_folder.py /path/to/folder --output records.jsonl` from this skill directory. The helper reports other formats on stderr. For PDF, Word, HTML, CSV, scanned or proprietary data, use your own extractor/OCR, inspect reading order and table headers, and report every unreadable or skipped file. Convert only content you can establish. Split long text at meaningful boundaries.
2. Write UTF-8 JSONL, one object per citable unit. See [the three-node example](examples/manual.jsonl). Every record requires `id` (ASCII letters/digits and then letters/digits, dot, dash or underscore, 128 characters max), `kind` (folder, document, section, note or claim) and `title`. Optional fields include `parent_id` in the same source, relative `path`, `locator` (positive 1-based page or line, or heading), `text` (120000 characters max) and `published_at` (YYYY-MM-DD or null). Use no date when unknown. Children inherit a displayed file path up the hierarchy. Create folder nodes if the directory hierarchy itself conveys meaningful structure. A path alone records location. For additional links use `links:[{"type":"cites","source":"manuals","id":"fan-check","revision":1}]`; supports, contradicts, related and updates are also available. File paths and locators are displayed to the reader; the server never opens or publishes the original files.
3. Keep IDs stable across exports. Use native IDs or retain an ID map across rename/reorganization. The bundled helper hashes relative paths and heading ancestry, so reconcile IDs against the previous JSONL before importing moved files/renamed headings. Within one source, an updated ID is a full replacement record. Unmentioned nodes are retained. References to existing sources must already exist. Order inside a batch is arbitrary. Do not equate folder membership with evidence for a claim.
4. If asked to compile evidence, first import the source documents and inspect current IDs and revisions by reading `/api/documents?collection=my_research&source=manuals`. Export each requested viewpoint as a `claim` with `layer:"L1"` (general) or `layer:"L2"` plus `question` (custom). Include text and at least one exact `cites` link with its revision. Use separate labelled links for supporting or opposing evidence. Derived claims can live under their own source; select it alongside evidence sources to see edges. Graph nodes are current; a versioned citation in the detail panel opens the cited version.
5. From the **StockNexus project root**, preview the completed JSONL. Remove only `--dry-run` to apply when the user requests import. Use the same data root as the server. To run an agent on another computer, transfer only the JSONL, then run the commands on the machine hosting the web UI.

```bash
python3 scripts/import_documents.py --collection my_research --source manuals --input records.jsonl --dry-run
python3 scripts/import_documents.py --collection my_research --source manuals --input records.jsonl
```

6. Report added, updated, unchanged, duplicate lines and undated counts. After apply, repeat the preview: added and updated should be zero. Open the web homepage, choose the collection below Massive, and check the source. Expand a chapter and verify its path and locator. Optional direct entry is `/documents?collection=my_research&source=manuals`.
