"""The live transcript: one voice, in the order the conductor decides (2026-11-03)."""
import threading
import time
import unittest

from core.brain import conductor
from core.brain.transcript import Transcript


class OrderTest(unittest.TestCase):
    def test_lines_come_out_in_stage_order_not_arrival_order(self):
        t = Transcript()
        t.post("impression", "This looks like a weather file.")
        t.post("start", "I'm looking at it now.")
        t.close()
        self.assertEqual([l.stage for l in t.lines()], ["start", "impression"])

    def test_a_late_earlier_stage_is_dropped_once_a_later_one_was_said(self):
        t = Transcript()
        t.post("start", "Looking.")
        seen = []
        consumer = threading.Thread(target=lambda: [seen.append(l.stage) for l in t.lines()])
        consumer.start()
        time.sleep(0.4)
        t.post("summary", "It explains thunderstorms.")
        time.sleep(0.4)
        self.assertFalse(t.post("impression", "This looks like..."))   # too late: the summary was already said
        t.close()
        consumer.join(2)
        self.assertEqual(seen, ["start", "summary"])
        self.assertEqual([l.stage for l in t.dropped], ["impression"])

    def test_only_talk_may_speak_and_a_stage_is_said_once(self):
        t = Transcript()
        self.assertFalse(t.post("impression", "Seek wants to talk", source="seek"))
        self.assertTrue(t.post("impression", "First wins."))
        self.assertFalse(t.post("impression", "Second loses."))
        self.assertFalse(t.post("nonsense", "x"))
        self.assertFalse(t.post("start", "   "))
        t.close()
        self.assertEqual([l.text for l in t.lines()], ["First wins."])

    def test_nothing_is_said_after_close(self):
        t = Transcript()
        t.close()
        self.assertFalse(t.post("start", "too late"))
        self.assertEqual(list(t.lines()), [])


class WorkloadTest(unittest.TestCase):
    def test_talk_speaks_and_the_others_think(self):
        self.assertEqual(conductor.model_for("speak"), conductor.TALK_MODEL)
        self.assertEqual(conductor.model_for("chat"), conductor.TALK_MODEL)
        self.assertEqual(conductor.model_for("read_file"), conductor.SEEK_MODEL)
        self.assertEqual(conductor.model_for("find_in_file"), conductor.SEEK_MODEL)
        self.assertEqual(conductor.model_for("code"), conductor.STUDY_MODEL)
        self.assertEqual(conductor.model_for("research"), conductor.STUDY_MODEL)
        self.assertEqual(conductor.model_for("summarize_small"), conductor.KEEP_MODEL)
        self.assertEqual(conductor.model_for("something unknown"), conductor.TALK_MODEL)
        self.assertNotIn("speak", conductor.THINKING_WORKLOADS)
        self.assertNotIn(conductor.TALK_MODEL, {conductor.model_for(w) for w in conductor.THINKING_WORKLOADS})


if __name__ == "__main__":
    unittest.main()
