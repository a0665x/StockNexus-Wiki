import datetime as dt
import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from news_atlas.arena import evidence_packet, handle
from news_atlas.documents import import_stream
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.research import put
from test_server import row
from test_wiki import proposal


class ArenaGatewayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.stock = "NASDAQ:TSLA"
        self.repo = GraphRepository(self.root / "news-atlas.sqlite3")
        self.news = self.repo.for_query(
            {"ticker": "TSLA", "instrument": self.stock, "sources": []}
        )
        self.day = (
            (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).date().isoformat()
        )
        self.rows = [
            row(title=name, suffix=name, day=self.day)
            for name in ("Orders", "Forecast")
        ]
        self.news.save("massive", "q", self.rows, [])

    def test_reproducible_graph_sources_and_bound_document_before_wiki(self):
        a, b = self.rows
        sample = {
            "id": "edge-a",
            "source": a["id"],
            "target": b["id"],
            "type": "shared_entity",
        }
        with self.news.connection() as db:
            db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?)",
                ("saved", "graph", self.day, "{}", "{}"),
            )
            for article in self.rows:
                db.execute(
                    "INSERT INTO snapshot_articles VALUES(?,?,?,?)",
                    ("saved", "massive", article["id"], json.dumps(article)),
                )
            db.execute(
                "INSERT INTO snapshot_relations VALUES(?,?,?,?)",
                ("saved", "massive", "edge-a", json.dumps(sample)),
            )
        for source, stock in (("own", self.stock), ("other", "NASDAQ:AAPL")):
            document = {
                "id": "note",
                "kind": "document",
                "title": source,
                "text": "Original " + source,
            }
            import_stream(
                self.root,
                "research",
                source,
                io.StringIO(json.dumps(document)),
                False,
                stock,
            )
        with patch(
            "news_atlas.providers.fetch",
            side_effect=AssertionError("unexpected network read"),
        ):
            packet = evidence_packet(self.root, self.stock)
        self.assertEqual(packet["graph_snapshot"], "saved")
        self.assertEqual(
            len(
                next(c for c in packet["context"] if c["layer"] == "News Graph")[
                    "sources"
                ]
            ),
            2,
        )
        docs = [s for s in packet["sources"] if s["layer"] == "document"]
        self.assertEqual([s["text"] for s in docs], ["Original own"])
        self.assertIn("revision=1", docs[0]["url"])
        self.assertFalse((self.root / "llm_wiki" / "TSLA" / "wiki.sqlite3").exists())
        self.assertEqual(evidence_packet(self.root, "")["sources"], [])
        with self.assertRaises(ValueError):
            evidence_packet(self.root, "NYSE:TSLA")

    def test_pinned_l1_original_and_l2_interpretation_read_without_wiki_write(self):
        service = WikiService(
            self.repo,
            runner=lambda s, j, a, c: {"proposal": proposal(a)},
            start_worker=False,
        )
        plan = service.plan(
            {"instrument": self.stock, "articles": self.rows[:1], "model": "fixture"}
        )
        service.start({"plan_id": plan["plan_id"]})
        store = service.store(self.stock)
        service.process(store)
        with store.connection() as db:
            target = db.execute(
                "SELECT payload FROM nodes WHERE kind='Claim' LIMIT 1"
            ).fetchone()
            citations = json.loads(target[0])["citations"]
            archived_opinion = {
                "claim_id": "old-claim",
                "revision_id": "archived-view-v1",
                "title": "Earlier outlook",
                "statement": "Earlier estimate",
                "evidence": citations,
            }
            snapshot = put(
                db,
                "snapshot",
                {
                    "lens": {"instrument": self.stock, "query": "demand"},
                    "opinions": [archived_opinion],
                },
            )
            put(
                db,
                "run",
                {
                    "snapshot": snapshot,
                    "result": {
                        "claims": [
                            {"statement": "Hypothesis", "derived_from": ["old-claim"]}
                        ]
                    },
                },
            )
        before = store.path.read_bytes()
        packet = evidence_packet(self.root, self.stock)
        self.assertEqual(before, store.path.read_bytes())
        claim = next(c for c in packet["context"] if c["layer"] == "L1")
        evidence = next(s for s in packet["sources"] if s["id"] == claim["sources"][0])
        self.assertEqual(evidence["text"], self.rows[0]["title"])
        interpretation = next(c for c in packet["context"] if c["layer"] == "L2")
        self.assertEqual(interpretation["statement"], "Hypothesis")
        self.assertEqual(interpretation["parents"], ["archived-view-v1"])
        older = next(c for c in packet["context"] if c["id"] == "archived-view-v1")
        self.assertTrue(older["sources"])
        self.assertEqual(interpretation["sources"], older["sources"])
        self.assertNotIn("Hypothesis", [s["text"] for s in packet["sources"]])

    def test_web_gateway_rejects_foreign_origin_and_overwrites_browser_evidence(self):
        body = json.dumps(
            {"instrument": self.stock, "packet": {"sources": [{"text": "fabricated"}]}}
        ).encode()
        headers = Message()
        for name, value in {
            "Host": "127.0.0.1:8765",
            "Origin": "https://foreign.example",
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }.items():
            headers[name] = value
        replies = []
        handler = SimpleNamespace(
            command="POST",
            path="/api/arena/start",
            headers=headers,
            client_address=("127.0.0.1", 1),
            rfile=io.BytesIO(body),
            store=self.repo,
            json_response=lambda code, data: replies.append((code, data)),
        )
        with patch("news_atlas.arena.UnixConnection") as bridge:
            handle(handler)
            bridge.assert_not_called()
            self.assertEqual(replies[-1][0], 403)
            headers.replace_header("Origin", "http://127.0.0.1:8765")
            response = io.BytesIO(b'{"status":"running"}')
            response.status = 202
            bridge.return_value.getresponse.return_value = response
            handle(handler)
            self.assertEqual(replies[-1][0], 202)
            packet = json.loads(bridge.return_value.request.call_args.kwargs["body"])[
                "packet"
            ]
            self.assertEqual(len(packet["sources"]), 2)
            self.assertNotIn("fabricated", str(packet))
