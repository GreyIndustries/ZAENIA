import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core.voice_listener import service_status as status


class OneAnswerPerTurnTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [mock.patch.object(status, "TURN_FILE", root / "voice_turn.json"),
                        mock.patch.object(status, "STATUS_FILE", root / "voice_service.json")]
        for patch in self.patches:
            patch.start()
        self.now = 1000.0

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.folder.cleanup()

    def clock(self):
        return self.now

    def pc_state(self, state):
        status.STATUS_FILE.write_text(json.dumps({"state": state, "updatedAt": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")

    def test_second_listener_drops_the_same_sentence(self):
        self.assertTrue(status.claim_turn("pc", "what's the weather tomorrow", clock=self.clock))
        self.now += 2
        self.assertFalse(status.claim_turn("app", "whats the weather tomorrow", clock=self.clock))

    def test_app_first_means_pc_stays_quiet(self):
        self.assertTrue(status.claim_turn("app", "open my calendar", clock=self.clock))
        self.assertFalse(status.claim_turn("pc", "open my calendar", clock=self.clock))

    def test_different_sentence_or_later_turn_is_answered(self):
        status.claim_turn("pc", "what's the weather tomorrow", clock=self.clock)
        self.assertTrue(status.claim_turn("app", "add milk to my list", clock=self.clock))
        status.claim_turn("pc", "what's the weather tomorrow", clock=self.clock)
        self.now += status.SAME_TURN_SECONDS + 1
        self.assertTrue(status.claim_turn("app", "what's the weather tomorrow", clock=self.clock))

    def test_same_source_can_repeat_itself(self):
        status.claim_turn("pc", "say that again", clock=self.clock)
        self.assertTrue(status.claim_turn("pc", "say that again", clock=self.clock))

    def test_app_waits_while_the_pc_is_still_hearing(self):
        self.pc_state("hearing")

        def sleep(seconds):
            self.now += seconds
            if self.now >= 1000.6 and not status.TURN_FILE.exists():
                status.claim_turn("pc", "turn the music down", clock=self.clock)
        self.assertFalse(status.claim_turn("app", "turn the music down", wait_for_pc=True, clock=self.clock, sleep=sleep))

    def test_check_only_does_not_block_the_pc(self):
        self.assertTrue(status.claim_turn("app", "background chatter here", record=False, clock=self.clock))
        self.assertTrue(status.claim_turn("pc", "background chatter here", clock=self.clock))

    def test_claim_holds_no_words(self):
        status.claim_turn("pc", "my secret plans", clock=self.clock)
        self.assertNotIn("secret", status.TURN_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
