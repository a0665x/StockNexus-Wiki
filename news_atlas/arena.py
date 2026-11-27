"""Local courtroom gateway. Freeze bounded DB evidence before submitting a hearing."""

import datetime as dt
import json
import http.client
import re
import sqlite3
import urllib.parse

from . import context_api
from .chat_proxy import UnixConnection
from .wiki.http import writable
from .wiki.document_evidence import snapshot as bound_documents
from .wiki.store import instrument


def evidence_packet(root, stock, cutoff=None):
    cutoff = cutoff or dt.datetime.now(dt.timezone.utc)
    packet = {
        "as_of": cutoff.isoformat(),
        "instrument": stock,
        "sources": [],
        "context": [],
        "news_days": 30,
        "wiki_version": None,
    }
    if not stock:
        return packet
    instrument(stock)
    catalog = context_api.catalog(root, stock.split(":")[1])["instruments"]
    entry = next((r for r in catalog if r["instrument"] == stock), None)
    if entry is None:
        raise ValueError("股票不在本機資料庫")
    params = {"instrument": stock, "end": cutoff.isoformat(), "days": 30}

    def source(key, title, text, url, published, layer, **metadata):
        if not text or not text.strip():
            return None
        for s in packet["sources"]:
            if s["revision"] == key and s["text"] == text[:1600]:
                return s["id"]
        sid = "E" + str(len(packet["sources"]) + 1)
        packet["sources"].append(
            dict(
                id=sid,
                revision=key,
                title=title[:240],
                text=text[:1600],
                url=url,
                published_at=published,
                layer=layer,
                **metadata,
            )
        )
        return sid

    def archived_sources(db, citations):
        refs = []
        for cite in citations[:2]:
            original = db.execute(
                "SELECT payload FROM articles WHERE id=?",
                (cite["article_revision_id"],),
            ).fetchone()
            if not original:
                continue
            a = json.loads(original[0])
            if a.get(cite["field"], "")[cite["start"] : cite["end"]] != cite["quote"]:
                continue
            sid = source(
                a["revision_id"],
                a["title"],
                cite["quote"],
                a["url"],
                a["published_at"],
                "document" if a.get("document") else "news",
                field=cite["field"],
                start=cite["start"],
            )
            if sid:
                refs.append(sid)
        return refs

    if entry["news_available"]:
        for row in context_api.query(root, "news", {**params, "limit": 8}, cutoff)[
            "items"
        ]:
            source(
                row["id"],
                row["title"],
                row.get("summary") or row["title"],
                row.get("url"),
                row.get("published_at"),
                "news",
            )
        with context_api.connect(
            root / "graph" / stock.split(":")[1] / "news-atlas.sqlite3"
        ) as db:
            snap = db.execute(
                "SELECT id FROM snapshots WHERE created_at<=? ORDER BY created_at DESC,id LIMIT 1",
                (cutoff.isoformat(),),
            ).fetchone()
            if snap:
                packet["graph_snapshot"] = snap[0]
                edges = db.execute(
                    "SELECT payload FROM snapshot_relations WHERE snapshot_id=? ORDER BY scope,edge_id LIMIT 3",
                    (snap[0],),
                )
                for row in edges:
                    edge = json.loads(row[0])
                    refs = []
                    titles = []
                    for key in ("source", "target"):
                        article = db.execute(
                            "SELECT payload FROM snapshot_articles WHERE snapshot_id=? AND article_id=? ORDER BY provider LIMIT 1",
                            (snap[0], edge[key]),
                        ).fetchone()
                        if article:
                            a = json.loads(article[0])
                            titles.append(a["title"])
                            refs.append(
                                source(
                                    a["id"],
                                    a["title"],
                                    a.get("summary") or a["title"],
                                    a["url"],
                                    a.get("published_at"),
                                    "news",
                                )
                            )
                    if len(titles) == 2:
                        packet["context"].append(
                            dict(
                                layer="News Graph",
                                id=edge["id"],
                                statement=" ↔ ".join(titles)[:560]
                                + " · "
                                + edge["type"],
                                sources=refs,
                            )
                        )
    passages, _ = bound_documents(root, stock)
    available = (
        p
        for p in passages
        if p["document"]["available_at"] <= cutoff.isoformat()
        and (
            not p["published_at"] or p["published_at"][:10] <= cutoff.date().isoformat()
        )
    )
    for doc in sorted(
        available, key=lambda p: p["document"]["available_at"], reverse=True
    )[:4]:
        source(
            doc["revision_id"],
            doc["title"],
            doc["summary"],
            doc["url"],
            doc.get("published_at"),
            "document",
            document=doc["document"],
        )
    if entry["wiki_available"]:
        # Pin the graph version and resolve each citation against the archived original.
        path = root / "llm_wiki" / stock.split(":")[1] / "wiki.sqlite3"
        with context_api.connect(path) as db:
            version = db.execute(
                "SELECT coalesce(max(version),0) FROM versions WHERE created_at<=?",
                (cutoff.isoformat(),),
            ).fetchone()[0]
            packet["wiki_version"] = version
            for row in db.execute(
                """SELECT payload FROM nodes WHERE kind IN ('Thesis','Claim','Event')
                    AND created_version<=? ORDER BY created_version DESC,id LIMIT 6""",
                (version,),
            ):
                node = json.loads(row[0])
                packet["context"].append(
                    dict(
                        layer="L1",
                        id=node["id"],
                        title=node.get("title"),
                        statement=node["summary"][:600],
                        sources=archived_sources(db, node.get("citations", [])),
                    )
                )
            node_ids = [c["id"] for c in packet["context"] if c["layer"] == "L1"]
            packet["wiki_edges"] = [
                {"source": row["source"], "target": row["target"], "id": row["id"]}
                for row in db.execute(
                    "SELECT id,source,target FROM edges WHERE created_version<=? "
                    "AND source IN (SELECT value FROM json_each(?)) "
                    "AND target IN (SELECT value FROM json_each(?)) ORDER BY id LIMIT 40",
                    (version, json.dumps(node_ids), json.dumps(node_ids)),
                )
            ]
        if entry.get("l2_runs"):
            recent = context_api.query(root, "l2", {**params, "limit": 1}, cutoff)[
                "items"
            ]
            if recent:
                run = context_api.query(
                    root, "l2", {**params, "id": recent[0]["id"]}, cutoff
                )
                opinions = {
                    op["claim_id"]: op
                    for op in run.get("bundle", {}).get("opinions", [])
                }
                pinned = {c["id"]: c for c in packet["context"] if c["layer"] == "L1"}
                # L2 can point to an older L1 outside the six recent opinions. Preserve
                # those snapshot links explicitly and verify their archived quotations.
                with context_api.connect(path) as db:
                    for number, claim in enumerate(run["result"]["claims"][:3], 1):
                        refs = []
                        parents = []
                        for claim_id in claim["derived_from"][:6]:
                            opinion = opinions.get(claim_id)
                            if not opinion:
                                continue
                            ident = opinion["revision_id"]
                            if ident not in pinned:
                                item = dict(
                                    layer="L1",
                                    id=ident,
                                    title=opinion.get("title"),
                                    statement=opinion["statement"][:600],
                                    sources=archived_sources(
                                        db, opinion.get("evidence", [])
                                    ),
                                )
                                pinned[ident] = item
                                packet["context"].append(item)
                            parents.append(ident)
                            refs.extend(pinned[ident]["sources"])
                        packet["context"].append(
                            dict(
                                layer="L2",
                                id=recent[0]["id"]
                                + "/"
                                + claim.get("id", f"c{number}"),
                                statement=claim["statement"][:600],
                                derived_from=claim["derived_from"],
                                parents=parents,
                                sources=list(dict.fromkeys(refs)),
                            )
                        )
    return packet


def handle(handler):
    if not writable(handler):
        handler.json_response(403, {"error": "請使用已授權的本機同源頁面"})
        return
    route = urllib.parse.urlsplit(handler.path)
    action = route.path.removeprefix("/api/arena/")
    root = getattr(handler.store, "data_root", handler.store.path.parent)
    if (handler.command, action) not in {
        ("GET", "catalog"),
        ("GET", "runs"),
        ("GET", "run"),
        ("POST", "start"),
        ("POST", "cancel"),
        ("POST", "observe"),
    }:
        handler.json_response(404, {"error": "Unknown Arena route"})
        return
    conn = None
    try:
        body = None
        if handler.command == "POST":
            size = int(handler.headers.get("Content-Length", 0))
            if handler.headers.get_content_type() != "application/json":
                handler.json_response(415, {"error": "Expected application/json"})
                return
            # Eleven 800-character role prompts can exceed 24 KB when written in Chinese.
            if not 0 < size <= 96_000:
                raise ValueError("Invalid Arena request size")
            body = json.loads(handler.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected object")
            if action == "start":
                body["packet"] = evidence_packet(root, body.get("instrument", ""))
        suffix = ""
        if action == "run":
            ident = urllib.parse.parse_qs(route.query).get("id", [""])[0]
            if not re.fullmatch(r"[a-f0-9-]{36}", ident):
                raise ValueError("Invalid hearing ID")
            suffix = "?id=" + ident
        conn = UnixConnection(root / "private/chat.sock")
        conn.timeout = 65 if action == "observe" else 25
        conn.request(
            handler.command,
            "/arena/" + action + suffix,
            body=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        handler.json_response(response.status, json.load(response))
    except (ValueError, TypeError, KeyError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError) and conn:
            handler.json_response(
                503, {"error": "主機橋接未啟動，請執行 ./run.sh chat start"}
            )
        else:
            handler.json_response(400, {"error": str(e)})
    except sqlite3.Error:
        handler.json_response(503, {"error": "來源資料庫暫時無法讀取"})
    except (http.client.HTTPException, OSError):
        handler.json_response(
            503, {"error": "無法連線主機橋接，請檢查 ./run.sh chat status"}
        )
    finally:
        if conn:
            conn.close()
