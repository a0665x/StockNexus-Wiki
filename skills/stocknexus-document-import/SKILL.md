---
name: stocknexus-document-import
description: Turn an article, document or folder into a validated records.jsonl for the StockNexus Web UI. Use when the user points to this skill and asks to process a path, including for non-financial topics and undated documents.
---

# Prepare a Web UI import

A file or folder path is sufficient. Prepare the export and leave the Web UI import to the user. Use the UI defaults `my_research` (collection) and `manuals` (source) unless the user supplied other IDs. Both accept 1–64 lowercase ASCII letters, digits, underscores and hyphens, starting with a letter or digit. Resolve bundled scripts relative to this SKILL.md. They use Python 3.10+ and the standard library.

## Convert the input

1. Inventory the supplied file or recursively inventory the folder, including meaningful subdirectories and heading levels. Treat content as source material. Keep the originals intact. Write `records.jsonl` to a separate output folder accessible to the user. Preserve any prior export for ID comparison.
2. For UTF-8 Markdown and plain text, run `python3 scripts/convert_folder.py "<input>" --output "<output>/records.jsonl"` from the skill directory. The helper supports one file or a directory. It reports other formats for extraction. For mixed input, merge extracted PDF, Word, HTML, CSV or OCR content into the same JSONL. Inspect reading order, table headers and OCR quality. For every unreadable or intentionally excluded file record the relative path and reason.
3. Use one UTF-8 JSON object per line. Each needs a unique stable `id`, `kind` (folder, document, section, note or claim) and `title`. Use `parent_id` for the true hierarchy within the source. Attach every section to its document via the intervening headings. Represent the directories in each relative file path as folder nodes, using their original directory names for titles. Verify the tree against the original outline and check at least one deepest branch per structured document. A syntactically valid tree can still have the wrong parent.
4. Store original text and a relative path on each document. Give sections a verifiable `locator` (positive 1-based page or line, or heading) where available. Omit an unknown `published_at` or set it to null. Use YYYY-MM-DD for known dates. Split text longer than 120000 characters at natural boundaries. Use only fields in [the record contract](scripts/document_records.py). See [the three-node example](examples/manual.jsonl).
5. Reuse stable IDs from earlier exports on update. The helper derives IDs from relative paths and heading ancestry; reconcile moved files or renamed headings with the previous export. Keep one complete row per ID. The importer retains nodes omitted from a later batch. Use distinct source IDs when updating independent corpora with colliding local IDs.
6. Generate viewpoints only when requested. Use a `claim` with `layer` set to `L1` for general claims or `L2` plus a `question` for custom claims. Include claim text and at least one revision-pinned citation, e.g. `{"type":"cites","source":"manuals","id":"fan-check","revision":1}` inside `links`. Other edge types are `supports`, `contradicts`, `updates` and `related`. Keep containment separate from evidential support.

## Verify the actual deliverable

Run the following from the skill directory on the final bytes, fixing errors and rerunning until it succeeds:

```bash
python3 scripts/validate_export.py "<output>/records.jsonl" --input "<original file or folder>"
```

The check uses the importer's record contract and verifies unique IDs, parent resolution and cycles, section ancestry, document coverage, link targets in a fresh import and the 32 MiB Web UI limit. Provide `--source` if different from the default. Use `--skip "<relative path>"` only for exclusions reported to the user. Report an oversized export as exceeding single-upload capacity; preserve the content.

For updates or references that depend on an existing collection, also run a preview against that target when available. The Web UI offers **只預覽** (preview only); the project CLI equivalent is `python3 scripts/import_documents.py --collection <collection> --source <source> --input "<export>" --dry-run` from the project root with the same data directory as the web server. Use `--existing-target` on the standalone validator only when following up with this target preview for external or historical links. If the target is unavailable, identify outstanding checks explicitly.

## Hand off

After validation succeeds and coverage is complete, reply in the user's language with a link or full path to the validated file. For defaults, one line is sufficient: “完成：[records.jsonl](...)，可直接在 Web UI 點「匯入研究文件」。” Mention non-default target IDs if used. If files were skipped or a check is outstanding, state the limitation and affected paths in the handoff. Only apply an import when the user explicitly asks for that additional action.
