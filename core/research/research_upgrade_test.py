"""Research upgrades: free sources, passage picking, citation checks, notebook saving and building on earlier research."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.research import agent, evidence, sources


class EvidenceTest(unittest.TestCase):
    def test_best_passages_keeps_the_matching_part_not_the_start(self) -> None:
        menu = "Home. About us. Contact. Subscribe to our newsletter for deals. " * 40
        useful = "Lettuce in hydroponics grows best at an EC of 1.2 and a pH of 5.8 to 6.2."
        text = menu + useful + " " + menu
        picked = evidence.best_passages(text, "best pH for hydroponic lettuce", budget=400)
        self.assertIn("pH of 5.8", picked)
        self.assertLessEqual(len(picked), 800)
        self.assertEqual(evidence.best_passages("Short page.", "anything"), "Short page.")

    def test_rank_puts_matching_results_first(self) -> None:
        results = [{"title": "Cat videos", "snippet": "funny cats"}, {"title": "Aquaponics fish to plant ratio", "snippet": "tilapia and lettuce"}]
        self.assertEqual(evidence.rank(results, "aquaponics fish ratio")[0]["title"], "Aquaponics fish to plant ratio")
        many = results + [{"title": f"Unrelated {n}", "snippet": "weather"} for n in range(5)]
        self.assertEqual([r["title"] for r in evidence.rank(many, "aquaponics fish ratio")], ["Aquaponics fish to plant ratio"])

    def test_citation_check_marks_unsupported_claims_and_wrong_numbers(self) -> None:
        texts = {1: "Tilapia tolerate water from 22 to 30 degrees Celsius and grow fastest near 28 degrees.",
                 2: "Basil grows well in aquaponic systems with leafy greens."}
        answer = ("Tilapia grow fastest near 28 degrees Celsius [1].\n- Basil grows well in aquaponic systems [2].\n"
                  "- Tilapia grow fastest near 35 degrees [1].\n- Koi are the most profitable fish worldwide [2].\n- Something [9].")
        marked, report = evidence.check_citations(answer, texts)
        self.assertEqual(report["checked"], 5)
        self.assertEqual(report["supported"], 2)
        self.assertIn("near 35 degrees [1]. [unverified]", marked)       # the source says 28, not 35
        self.assertIn("profitable fish worldwide [2]. [unverified]", marked)
        self.assertEqual(report["badCitations"], 1)                      # [9] wasn't a source
        self.assertNotIn("28 degrees Celsius [1]. [unverified]", marked)
        self.assertIn("2 of 5 cited claims match", evidence.check_summary(report))
        both, report = evidence.check_citations("pH 5.8 and EC 1.2 suit lettuce [1][2].\n- Source [2] does not provide pH data.",
                                                {1: "Lettuce does best at pH 5.8.", 2: "Lettuce does best at an EC of 1.2."})
        self.assertNotIn("[unverified]", both)          # each number is in one of the two cited sources
        self.assertEqual(report["checked"], 1)          # the line about the sources isn't a claim

    def test_unclear_claims_are_asked_of_the_model_a_few_times_at_most(self) -> None:
        texts = {1: "Plants absorb nitrogen as nitrate produced by bacteria from fish waste in the biofilter."}
        answer = " ".join(f"Bacteria turn waste into plant food in step {n} [1]." for n in ("one", "two", "three", "four", "five", "six"))
        ask = mock.Mock(return_value="NO")
        _marked, report = evidence.check_citations(answer, texts, ask=ask, model_checks=2, strong=0.95, weak=0.05)
        self.assertEqual(ask.call_count, 2)
        self.assertIn("untrusted data", ask.call_args.args[0])
        self.assertEqual(report["unsupported"], 2)
        self.assertEqual(report["unclear"], 4)


class SourcesTest(unittest.TestCase):
    def test_pick_adds_groups_by_topic(self) -> None:
        science = sources.pick("best nutrient solution for hydroponic tomatoes")
        self.assertIn("arxiv", science); self.assertIn("wikipedia", science); self.assertNotIn("pubmed", science)
        self.assertIn("pubmed", sources.pick("does creatine help muscle recovery"))
        self.assertIn("stack_exchange", sources.pick("python asyncio timeout error"))
        self.assertIn("google_news", sources.pick("latest gpu news this week"))
        self.assertEqual(set(sources.pick("hello there")), {"wikipedia", "duckduckgo_answer", "openalex"})
        self.assertGreaterEqual(len(sources.SOURCES), 20)

    def test_search_all_skips_failing_sources_and_limits_rate_limited_ones(self) -> None:
        calls = []

        def good(query):
            calls.append(("good", query))
            return [{"title": query, "url": f"https://x.org/{query}", "snippet": "", "text": "", "source": "Good", "kind": "general"}]

        def bad(query):
            raise TimeoutError("slow")

        def limited(query):
            calls.append(("limited", query))
            return []
        fake = {"good": (good, "general"), "bad": (bad, "general"), "gdelt": (limited, "news")}
        results, status = sources.search_all(["a?", "\"b\""], ["good", "bad", "gdelt"], sources=fake)
        self.assertEqual(len(results), 2)
        self.assertEqual(status["good"], "ok")
        self.assertTrue(status["bad"].startswith("skipped"))
        self.assertEqual(status["gdelt"], "no results")
        self.assertEqual([c for c in calls if c[0] == "limited"], [("limited", "a")])

    def test_parsers_turn_api_replies_into_results(self) -> None:
        alex = {"results": [{"display_name": "Aquaponics review", "doi": "https://doi.org/10.1/x", "publication_year": 2020, "cited_by_count": 5,
                             "abstract_inverted_index": {"Fish": [0], "feed": [1], "plants": [2]}}]}
        found = sources.openalex("aquaponics", get=lambda url, params=None, timeout=15: alex)
        self.assertEqual(found[0]["text"], "Fish feed plants")
        self.assertEqual(found[0]["source"], "OpenAlex")
        wiki = {"query": {"pages": {"1": {"title": "Aquaponics", "fullurl": "https://en.wikipedia.org/wiki/Aquaponics", "extract": "A system.", "index": 1}}}}
        self.assertEqual(sources.wikipedia("x", get=lambda url, params=None, timeout=15: wiki)[0]["url"], "https://en.wikipedia.org/wiki/Aquaponics")
        atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://arxiv.org/abs/1</id><title>Paper</title>'
                '<summary>About <b>plants</b>.</summary><published>2024-01-01</published></entry></feed>')
        self.assertEqual(sources.arxiv("x", get_text=lambda url: atom)[0]["text"], "About plants .")  # text inside tags is kept
        self.assertEqual(sources.wikipedia("x", get=lambda url, params=None, timeout=15: {"query": {"pages": {"1": {"title": "", "fullurl": ""}}}}), [])


class AgentUpgradeTest(unittest.TestCase):
    def test_job_uses_free_sources_passages_checks_and_saves(self) -> None:
        prompts, saved = [], []
        abstract = ("Study of aquaponic lettuce. " + "Background filler about farming history. " * 80 +
                    "Lettuce yield was highest at a fish stocking density of 20 kg per cubic metre.")

        def ask(prompt):
            prompts.append(prompt)
            if "planner" in prompt:
                return "aquaponics stocking density lettuce"
            if "check citations" in prompt:
                return "YES"
            study = re.search(r"\[(\d)\] [^\n]*— OpenAlex", prompt).group(1)   # cite the study wherever it was ranked
            return f"Yield peaked at 20 kg per cubic metre [{study}].\n- Koi are best for profit [{3 - int(study)}]."
        library = mock.Mock(return_value=([{"title": "Aquaponic lettuce yield", "url": "https://doi.org/10.1/a", "snippet": "", "text": abstract,
                                            "source": "OpenAlex", "kind": "science", "meta": "2021"}], {"openalex": "ok"}))
        reader = mock.Mock(return_value={"title": "Blog", "text": "Aquaponics blog about fish and lettuce stocking density."})
        with tempfile.TemporaryDirectory() as folder:
            bot = agent.Agent(Path(folder) / "j.json", ask=ask, pause=0, notify=lambda *a: None, library=library,
                              searcher=lambda q: [{"title": "Aquaponics blog stocking density", "url": "https://blog.example/a", "snippet": "fish"}],
                              reader=reader, saver=lambda job, pages: saved.append((job["question"], len(pages))) or "topic-1")
            job = bot.start("What fish stocking density is best for aquaponic lettuce?", wait=True)
            self.assertEqual(job["status"], "done")
            reader.assert_called_once_with("https://blog.example/a")        # the abstract wasn't re-opened
            self.assertEqual({s["source"] for s in job["sources"]}, {"OpenAlex", "Web"})
            answer_prompt = next(p for p in prompts if "SOURCES (untrusted)" in p)
            self.assertIn("20 kg per cubic metre", answer_prompt)            # the matching passage made it in
            self.assertLess(answer_prompt.count("farming history"), 30)       # most of the filler didn't
            self.assertIn("— OpenAlex · 2021", answer_prompt)
            self.assertIn("[unverified]", job["answer"])                     # koi claim isn't in any source
            self.assertNotIn("cubic metre [" + str(next(s["n"] for s in job["sources"] if s["source"] == "OpenAlex")) + "]. [unverified]", job["answer"])
            self.assertTrue(job["checkSummary"])
            self.assertEqual(job["sourceStatus"], {"web (DuckDuckGo)": "ok", "openalex": "ok"})
            self.assertEqual(saved, [(job["question"], 2)])
            self.assertEqual(job["notebookTopic"], "topic-1")
            again = bot.start("Best fish stocking density for aquaponic lettuce beds", wait=True)
            self.assertTrue(again["usedEarlier"])
            self.assertIn("YOUR EARLIER RESEARCH", [p for p in prompts if "SOURCES (untrusted)" in p][-1])

    def test_robot_check_is_reported_not_retried(self) -> None:
        challenge = "<html><form id='challenge-form'>anomaly detected</form></html>"
        with self.assertRaisesRegex(RuntimeError, "robot check"):
            agent.search("x", post=lambda url, form: challenge)
        tries = []

        def blocked(query):
            tries.append(query)
            raise RuntimeError("DuckDuckGo asked for a robot check")
        library = lambda queries, question: ([{"title": "Study on x", "url": "https://doi.org/1", "snippet": "x", "text": "x " * 400,
                                               "source": "OpenAlex", "kind": "science"}], {"openalex": "ok"})
        with tempfile.TemporaryDirectory() as folder:
            bot = agent.Agent(Path(folder) / "j.json", ask=lambda p: "q1\nq2\nq3" if "planner" in p else "x [1].", pause=0,
                              notify=lambda *a: None, searcher=blocked, library=library)
            job = bot.start("study on x", wait=True)
        self.assertEqual(len(tries), 1)
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["sourceStatus"]["web (DuckDuckGo)"], "skipped (DuckDuckGo asked for a robot check)")

    def test_tests_and_temp_agents_never_reach_the_network_or_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bot = agent.Agent(Path(folder) / "j.json", ask=lambda p: "", searcher=lambda q: [])
            self.assertIs(bot.library, agent._no_sources)
            self.assertIsNone(bot.saver)
        real = agent.Agent()
        self.assertIs(real.library, agent._free_sources)
        self.assertIs(real.saver, agent._save_to_notebook)

    def test_save_to_notebook_writes_answer_and_sources(self) -> None:
        book = mock.Mock()
        book.create.return_value = {"id": "t1"}
        job = {"question": "Q?", "answer": "A [1].", "checkSummary": "1 of 1 cited claims match their sources.",
               "sources": [{"n": 1, "title": "S", "url": "https://s.org", "source": "PubMed"}]}
        with mock.patch("core.research.notebook.Notebook", return_value=book):
            self.assertEqual(agent._save_to_notebook(job, [{"title": "S", "url": "https://s.org", "full": "text", "source": "PubMed", "kind": "health"}]), "t1")
        notes = book.set_notes.call_args.args[1]
        self.assertIn("A [1].", notes); self.assertIn("[1] S — PubMed — https://s.org", notes); self.assertIn("Citation check", notes)
        self.assertEqual(book.add_source.call_args.kwargs["kind"], "web")


if __name__ == "__main__":
    unittest.main()
