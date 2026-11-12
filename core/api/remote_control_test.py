import unittest

from core.api import remote_control as remote


class RemoteControlTest(unittest.TestCase):
    def setUp(self):
        remote._queue.clear()
        remote._state.update({"windows": [], "active": None, "calm": False, "section": "overview", "at": 0.0})

    def test_only_listed_actions_and_real_tab_names(self):
        with self.assertRaises(ValueError):
            remote.queue_command("delete_files", "notes")
        with self.assertRaises(ValueError):
            remote.queue_command("launch_app", "notepad")
        with self.assertRaises(ValueError):
            remote.queue_command("open", "../../etc")
        self.assertTrue(remote.queue_command("open", "Music", now=100)["queued"])
        self.assertEqual(remote.queue_command("calm", "ignored", now=100)["pcOnline"], False)

    def test_commands_are_handed_out_once_and_stale_ones_dropped(self):
        remote.queue_command("open", "notes", now=100)
        remote.queue_command("calm", now=290)
        fresh = remote.collect(now=300)
        self.assertEqual([c["action"] for c in fresh], ["calm"])  # the 200-second-old "open" was dropped
        self.assertEqual(fresh[0]["target"], "")
        self.assertEqual(remote.collect(now=301), [])

    def test_state_reports_what_is_open_and_whether_the_pc_is_connected(self):
        remote.report_state([{"id": "music", "title": "Music"}, {"id": "BAD ID!", "title": "x"}, {"id": "notes", "minimized": True}],
                            "music", False, "music", now=1000)
        shown = remote.state(now=1005)
        self.assertEqual([w["id"] for w in shown["windows"]], ["music", "notes"])
        self.assertTrue(shown["online"])
        self.assertFalse(remote.state(now=1100)["online"])
        self.assertIn("wake", shown["actions"])

    def test_snap_layout_targets_stay_screen_only_and_bounded(self):
        for count, targets in [(2, "notes,research"), (3, "notes,research,music"), (4, "notes,research,music,workbench")]:
            remote.queue_command(f"arrange_{count}", targets, now=100)
            command = remote.collect(now=101)[0]
            self.assertEqual(command["target"], targets)
            self.assertEqual(command["action"], f"arrange_{count}")
        for action, target in [("arrange_5", ""), ("arrange_2", "notes,notes"), ("arrange_2", "notes,../../private"), ("arrange_4", "notes,research"), ("arrange_2", "notes,notepad")]:
            with self.assertRaises(ValueError):
                remote.queue_command(action, target)
        remote.queue_command("undo_arrange", now=100)
        self.assertEqual(remote.collect(now=250), [])

    def test_routes_have_capabilities(self):
        from core.api.ui_routes import operation_for
        self.assertEqual(operation_for("POST", "/api/remote/commands"), "assistant.desktop.manage")
        self.assertEqual(operation_for("GET", "/api/remote/state"), "status.read")
        self.assertEqual(operation_for("GET", "/api/remote/collect"), "files.read")
        self.assertEqual(operation_for("POST", "/api/remote/state"), "files.read")


if __name__ == "__main__":
    unittest.main()
