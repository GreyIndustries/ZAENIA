import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.brain.conversation_threads import ThreadTracker

TOPICS = {"saber": [1.0, 0.0, 0.0], "weather": [0.0, 1.0, 0.0], "pc": [0.0, 0.0, 1.0]}


def fake_embed(texts):
    vectors = []
    for text in texts:
        lowered = text.lower()
        hits = [vec for word, vec in (("saber", TOPICS["saber"]), ("djem", TOPICS["saber"]), ("weather", TOPICS["weather"]),
                                      ("jacket", TOPICS["weather"]), ("ram", TOPICS["pc"]), ("gpu", TOPICS["pc"])) if word in lowered]
        vectors.append([sum(v[i] for v in hits) or 0.01 for i in range(3)])
    return vectors


class ThreadTrackerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.memory = self.dir / "memory.jsonl"
        self.now = datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc)
        self.jobs = []
        self.judged = []
        self.tracker = ThreadTracker(self.dir / "threads.json", self.memory, embed=fake_embed,
                                     judge=lambda *args: self.judged.append(args) or None,
                                     summarize=lambda title, points, text: {"title": "Lightsaber forms", "key_points": ["Grey likes Djem So."]},
                                     run=self.jobs.append, clock=lambda: self.now)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def say(self, question, answer="ok", minutes=2):
        view = self.tracker.route(question)
        with self.memory.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": self.now.isoformat(), "role": "user", "content": question}) + "\n")
            handle.write(json.dumps({"timestamp": self.now.isoformat(), "role": "assistant", "content": answer}) + "\n")
        self.tracker.record(question, self.now)
        self.now += timedelta(minutes=minutes)
        return view

    def test_builds_switches_and_resumes(self):
        first = self.say("which saber form is aggressive")
        self.assertEqual(first.decision, "new")
        follow = self.say("why?")
        self.assertEqual((follow.decision, len(follow.history)), ("continue", 2))
        self.assertEqual(self.say("djem so for saber power").decision, "continue")
        switch = self.say("weather tomorrow")
        self.assertEqual((switch.decision, switch.history), ("new", []))
        self.assertIn("Just before this", switch.notes)
        self.assertEqual(self.say("should I bring a jacket for the weather").decision, "continue")
        back = self.say("back to saber forms, which fits me")
        self.assertEqual(back.decision, "resume")
        self.assertEqual(back.topic_id, first.topic_id)
        self.assertEqual([row["content"] for row in back.history if row["role"] == "user"][:1], ["which saber form is aggressive"])

    def test_explicit_topic_change_and_long_pause_start_fresh(self):
        self.say("which saber form is aggressive")
        self.assertEqual(self.say("new topic: something else entirely").decision, "new")
        self.say("ram for my pc", minutes=90)
        self.assertEqual(self.tracker.route("tell me a story").decision, "new")

    def test_key_points_are_kept_and_shown(self):
        for line in ("saber forms", "djem so saber", "saber stance", "saber again"):
            self.say(line)
        self.assertTrue(self.jobs)
        for job in self.jobs:
            job()
        view = self.tracker.route("more about saber djem so")
        self.assertIn("Grey likes Djem So.", view.notes)
        self.assertEqual(self.tracker.topics()[0]["title"], "Lightsaber forms")

    def test_unclear_case_asks_the_local_model_and_unsure_keeps_going(self):
        self.say("which saber form is aggressive")
        self.tracker.embed = lambda texts: [[1.0, 1.2, 0.0] for _ in texts[:1]] if "saber" not in texts[0] else [[1.0, 0.0, 0.0]]
        view = self.tracker.route("something kind of related here")
        self.assertTrue(self.judged)
        self.assertEqual(view.decision, "continue")

    def test_no_embeddings_keeps_old_behaviour(self):
        self.say("which saber form is aggressive")
        self.tracker.embed = lambda texts: (_ for _ in ()).throw(OSError("ollama down"))
        self.tracker._vectors.clear()
        self.assertEqual(self.tracker.route("a completely different long question about other things").decision, "continue")

    def test_route_uses_the_history_it_is_given(self):
        self.say("which saber form is aggressive")
        self.memory.write_text("", encoding="utf-8")  # the log is no longer read
        at = (self.now - timedelta(minutes=2)).isoformat()
        history = [{"role": "user", "content": "which saber form is aggressive", "at": at},
                   {"role": "assistant", "content": "Djem So.", "at": at}]
        view = self.tracker.route("why?", history)
        self.assertEqual(view.decision, "continue")
        self.assertEqual([row["content"] for row in view.history], ["which saber form is aggressive", "Djem So."])


    def test_recent_untracked_turns_become_the_current_topic(self):
        at = (self.now - timedelta(minutes=3)).isoformat()
        history = [{"role": "user", "content": "which saber form is aggressive", "at": at},
                   {"role": "assistant", "content": "Djem So.", "at": at}]
        view = self.tracker.route("why?", history)
        self.assertEqual(view.decision, "continue")
        self.assertEqual(len(view.history), 2)
        old = (self.now - timedelta(hours=3)).isoformat()
        stale = [{"role": "user", "content": "which saber form is aggressive", "at": old}]
        fresh = ThreadTracker(self.dir / "other.json", self.memory, embed=fake_embed, judge=lambda *a: None,
                              summarize=lambda *a: {}, run=self.jobs.append, clock=lambda: self.now)
        self.assertEqual(fresh.route("why?", stale).history, [])  # hours old: starts fresh

    def test_route_only_reads_and_record_saves(self):
        state = self.dir / "threads.json"
        at = (self.now - timedelta(minutes=3)).isoformat()
        history = [{"role": "user", "content": "which saber form is aggressive", "at": at},
                   {"role": "assistant", "content": "Djem So.", "at": at}]
        view = self.tracker.route("why?", history)
        self.assertFalse(state.exists())  # routing created no topic file
        self.assertEqual(self.jobs, [])   # and started no key-point summary
        self.tracker.record("why?", self.now)
        saved = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(saved["current"], view.topic_id)
        self.assertEqual(saved["topics"][0]["turns"], [at, self.now.isoformat()])

    def test_a_turn_that_is_not_recorded_leaves_topics_unchanged(self):
        self.say("which saber form is aggressive")
        self.say("djem so for saber power")
        state = self.dir / "threads.json"
        before, jobs = state.read_bytes(), len(self.jobs)
        switch = self.tracker.route("weather tomorrow")  # a new subject ends the saber topic
        self.assertEqual(switch.decision, "new")
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(len(self.jobs), jobs)
        self.tracker.record("weather tomorrow", self.now)  # saving the turn saves the switch
        saved = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(saved["current"], switch.topic_id)
        self.assertEqual(len(saved["topics"]), 2)
        self.assertEqual(len(self.jobs), jobs + 1)  # the ended topic's notes refresh now


class BrainServiceTopicTest(unittest.TestCase):
    """The brain uses topic tracking only for its own timed history."""

    def test_untimed_history_never_touches_topic_state(self):
        from unittest import mock
        from core.brain import brain_service, conversation_threads
        service = brain_service.BrainService(memory_authorizer=lambda operation: True)
        history = [{"role": "user", "content": "What's the weather today?"}, {"role": "assistant", "content": "Mild."}]
        with mock.patch.object(service, "load_recent_messages", return_value=history), \
                mock.patch.object(conversation_threads.ThreadTracker, "route", side_effect=AssertionError("tracker used")):
            turn = service.prepare_turn("What about tomorrow?")
        self.assertIn("What's the weather today?", json.dumps(turn.messages))

    def test_timed_history_goes_to_the_tracker_for_this_log(self):
        from unittest import mock
        from core.brain import brain_service, conversation_threads
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        log = folder / "memory.jsonl"
        stamp = datetime.now(timezone.utc).isoformat()
        log.write_text(json.dumps({"timestamp": stamp, "role": "user", "content": "saber forms"}) + "\n"
                       + json.dumps({"timestamp": stamp, "role": "assistant", "content": "Djem So."}) + "\n", encoding="utf-8")
        seen = {}

        def fake_route(tracker, question, history=None):
            seen.update(state=tracker.state_path, history=history)
            return conversation_threads.ThreadView(history or [], None, "t1", "continue")

        with mock.patch.object(brain_service, "MEMORY_PATH", log), \
                mock.patch.object(conversation_threads.ThreadTracker, "route", fake_route):
            brain_service.BrainService(memory_authorizer=lambda operation: True).prepare_turn("why?")
        self.assertEqual(seen["state"], folder / "conversation" / "threads.json")
        self.assertEqual([row["at"] for row in seen["history"]], [stamp, stamp])

    def test_preparing_a_turn_writes_no_topic_state(self):
        from unittest import mock
        from core.brain import brain_service, conversation_threads
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        log = folder / "memory.jsonl"
        stamp = datetime.now(timezone.utc).isoformat()
        log.write_text(json.dumps({"timestamp": stamp, "role": "user", "content": "saber forms"}) + "\n"
                       + json.dumps({"timestamp": stamp, "role": "assistant", "content": "Djem So."}) + "\n", encoding="utf-8")
        local = conversation_threads.ThreadTracker(folder / "conversation" / "threads.json", log, embed=fake_embed,
                                                   judge=lambda *a: None, summarize=lambda *a: {}, run=lambda job: None)
        with mock.patch.object(brain_service, "MEMORY_PATH", log), \
                mock.patch.object(conversation_threads, "tracker", return_value=local):
            turn = brain_service.BrainService(memory_authorizer=lambda operation: True).prepare_turn("why?")
        self.assertIn("Djem So.", json.dumps(turn.messages))
        self.assertEqual(sorted(p.name for p in folder.rglob("*")), ["memory.jsonl"])


if __name__ == "__main__":
    unittest.main()
