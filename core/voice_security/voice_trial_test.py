import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.api.ui_routes import operation_for
from core.voice_security import voice_trial as trial_module
from core.voice_security.app_mic import AppMicGate
from core.voice_security.voice_trial import VoiceTrial


class VoiceTrialTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.trial = VoiceTrial(Path(self.folder.name) / "t.json")

    def tearDown(self):
        self.folder.cleanup()

    def test_only_notes_during_a_round_and_stops_at_the_target(self):
        self.trial.note(True, "recognised", .8)
        self.assertEqual(self.trial.view()["summary"]["owner"]["tries"], 0)
        self.trial.start("owner", 2)
        self.trial.note(True, "recognised", .81)
        self.trial.note(False, "not_recognised", .41)
        self.trial.note(True, "recognised", .9)                 # round already finished
        view = self.trial.view()
        self.assertIsNone(view["round"])
        self.assertEqual((view["summary"]["owner"]["checked"], view["summary"]["owner"]["accepted"]), (2, 1))
        self.assertEqual(view["summary"]["owner"]["scoreMin"], .41)
        self.assertNotIn("text", view["attempts"][0])           # no words or audio are kept

    def test_verdict_needs_both_rounds_and_flags_any_other_speaker_acceptance(self):
        self.trial.start("owner", 5)
        for _ in range(5):
            self.trial.note(True, "recognised", .8)
        self.assertEqual(self.trial.view()["verdict"], "in_progress")
        self.trial.start("other", 6)
        for _ in range(5):
            self.trial.note(False, "not_recognised", .3)
        self.assertEqual(self.trial.view()["verdict"], "pass")
        self.trial.note(True, "short_reply_in_conversation", None)
        view = self.trial.view()
        self.assertEqual(view["summary"]["other"]["acceptedWithoutCheck"], 1)
        self.assertEqual(view["verdict"], "fail")
        self.assertEqual(self.trial.clear()["summary"]["owner"]["tries"], 0)

    def test_the_gate_reports_to_the_trial_without_changing_its_verdict(self):
        gate = AppMicGate(verify=lambda pcm: False, score=lambda pcm: .2, configured=lambda: True, audit=lambda r: None)
        with patch.object(trial_module, "_TRIAL", self.trial):
            self.trial.start("other", 3)
            import array, math
            pcm = array.array("h", (int(8000 * math.sin(i * .2)) for i in range(16000 * 3))).tobytes()
            self.assertFalse(gate.check(pcm)["accepted"])
        self.assertEqual(self.trial.view()["summary"]["other"]["checked"], 1)
        with self.assertRaises(ValueError):
            self.trial.start("nobody")

    def test_the_pc_voice_process_records_into_the_same_round(self):
        pc_voice = VoiceTrial(self.trial.path)          # another process, same file
        self.trial.start("owner", 3)
        pc_voice.note(True, "recognised", .7)
        pc_voice.note(False, "not_recognised", .1)
        view = self.trial.view()
        self.assertEqual((view["summary"]["owner"]["checked"], view["round"]["count"]), (2, 2))
        self.trial.stop()
        pc_voice.note(True, "recognised", .7)            # no round: ignored
        self.assertEqual(self.trial.view()["summary"]["owner"]["tries"], 2)

    def test_starting_a_round_needs_the_desktop(self):
        self.assertEqual(operation_for("POST", "/api/voice/trial"), "assistant.desktop.manage")
        self.assertEqual(operation_for("GET", "/api/voice/trial"), "status.read")


if __name__ == "__main__":
    unittest.main()
