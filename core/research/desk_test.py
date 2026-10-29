import tempfile
import time
import unittest
from pathlib import Path

from core.research import analyze, desk
from core.research.notebook import Notebook


class DeskTest(unittest.TestCase):
    def test_every_source_answers_on_its_own(self):
        def broken(query):
            raise RuntimeError("down")

        def slow(query):
            time.sleep(2)
            return []

        finders = {"library": lambda q: ([{"kind": "library", "title": "Field manual"}], {"title": "ACFT", "summary": "A test."}),
                   "news": broken, "scripture": slow, "notebook": lambda q: [{"kind": "notebook", "title": "My topic"}]}
        found = desk.search("  army   fitness test ", finders=finders, timeout=0.5)
        self.assertEqual(found["query"], "army fitness test")
        self.assertEqual([item["title"] for item in found["results"]], ["Field manual", "My topic"])
        self.assertEqual(found["failed"], ["news", "scripture"])
        self.assertEqual(found["overview"]["title"], "ACFT")
        self.assertEqual(found["counts"], {"library": 1, "news": 0, "scripture": 0, "notebook": 1})

    def test_only_chosen_sources_run(self):
        ran = []
        finders = {name: (lambda name: lambda q: ran.append(name) or [])(name) for name in desk.SOURCES}
        desk.search("x", ("news",), finders=finders)
        self.assertEqual(ran, ["news"])
        with self.assertRaises(ValueError):
            desk.search("   ", finders=finders)

    def test_notebook_matches_rank_by_shared_words(self):
        topics = [{"id": "t1", "name": "Army fitness test", "sources": [{"id": "s1", "title": "ACFT scoring tables", "url": ""},
                                                                         {"id": "s2", "title": "Fitness test history", "url": "u"}]},
                  {"id": "t2", "name": "Hebrew calendar", "sources": []}]
        found = desk.notebook_matches("the fitness test", topics)
        self.assertEqual([(m["title"], m["sourceId"]) for m in found], [("Army fitness test", None), ("Fitness test history", "s2")])
        self.assertEqual(desk.notebook_matches("to", topics), [])


class BoardTest(unittest.TestCase):
    def test_question_claims_and_reading_a_source(self):
        with tempfile.TemporaryDirectory() as folder:
            from core.assistant_platform.store import PlatformStore
            book = Notebook(Path(folder) / "notebook.json", store=PlatformStore(Path(folder) / "p.sqlite3"))
            topic = book.create("2025 test")
            source_id = book.add_source(topic["id"], title="army.mil", text="The run stays last.")["sources"][0]["id"]
            self.assertEqual(book.source(topic["id"], source_id)["text"], "The run stays last.")
            self.assertEqual(book.set_question(topic["id"], " Did the  run change? ")["question"], "Did the run change?")
            shown = book.add_claim(topic["id"], "The run stays last.", "supports", "army.mil")
            claim = shown["claims"][0]
            self.assertEqual((claim["column"], claim["source"]), ("supports", "army.mil"))
            self.assertEqual(book.add_claim(topic["id"], "Odd", "sideways")["claims"][1]["column"], "open")
            self.assertEqual(book.update_claim(topic["id"], claim["id"], column="contradicts")["claims"][0]["column"], "contradicts")
            with self.assertRaises(ValueError):
                book.update_claim(topic["id"], claim["id"], column="maybe")
            self.assertEqual(len(book.remove_claim(topic["id"], claim["id"])["claims"]), 1)
            self.assertEqual(book.raw_topics()[0]["sources"][0].get("text"), None)
            with self.assertRaises(KeyError):
                book.source(topic["id"], "f" * 32)

    def test_suggested_claims_keep_only_well_formed_lines(self):
        reply = "Here you go:\nSUPPORTS | The run stays last. | army.mil\n- open | Plank timing? \nMAYBE | nope | x\nCONTRADICTS | Row replaced run | blog"
        prompts = []
        found = analyze.suggest_claims("SOURCE 1: text", "Did the run change?", run=lambda prompt: prompts.append(prompt) or reply)
        self.assertEqual([(c["column"], c["text"], c["source"]) for c in found],
                         [("supports", "The run stays last.", "army.mil"), ("open", "Plank timing?", ""), ("contradicts", "Row replaced run", "blog")])
        self.assertIn("Did the run change?", prompts[0])
        self.assertIn("untrusted", prompts[0])
        with self.assertRaises(ValueError):
            analyze.suggest_claims("", "q", run=lambda prompt: "")

    def test_routes_have_capabilities(self):
        from core.api.ui_routes import operation_for
        tid, cid = "a" * 32, "b" * 32
        self.assertEqual(operation_for("GET", "/api/research/desk"), "memory.read")
        self.assertEqual(operation_for("GET", f"/api/research/notebook/{tid}/sources/{cid}"), "memory.read")
        self.assertEqual(operation_for("PUT", f"/api/research/notebook/{tid}/question"), "memory.write")
        self.assertEqual(operation_for("POST", f"/api/research/notebook/{tid}/claims"), "memory.write")
        self.assertEqual(operation_for("POST", f"/api/research/notebook/{tid}/claims/suggest"), "chat.reply")
        self.assertEqual(operation_for("PUT", f"/api/research/notebook/{tid}/claims/{cid}"), "memory.write")
        self.assertEqual(operation_for("DELETE", f"/api/research/notebook/{tid}/claims/{cid}"), "memory.write")


if __name__ == "__main__":
    unittest.main()
