"""Fixture checks for read-only scans, privacy, containment and stale snapshots."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.cleanup_audit import (
    candidates, compare_inventory, is_reparse, ordinary_path, reference_audit,
    render_review, report_destination, scan,
)


class CleanupAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def file(self, relative, content=b"fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def complete(self):
        inventory = scan(self.root)
        inventory["usage"] = reference_audit(self.root, inventory)
        inventory["candidates"] = candidates(inventory, inventory["usage"])
        return inventory

    def test_metadata_scan_includes_hidden_files_without_opening_contents(self):
        self.file(".hidden/private.bin", b"this is never read")
        self.file("data/secure/private-user-token", b"NEVER COPY THIS CONTENT")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("content read")), \
             patch.object(Path, "read_text", side_effect=AssertionError("content read")):
            inventory = scan(self.root)
        self.assertEqual(inventory["totals"]["files"], 2)
        self.assertEqual(inventory["totals"]["bytes"], 41)
        self.assertEqual(inventory["directories"]["data"]["bytes"], 23)
        self.assertNotIn("NEVER COPY", json.dumps(inventory))

    def test_symlink_directory_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "outside-private.bin").write_bytes(b"do not traverse")
            try:
                os.symlink(outside, self.root / "linked-folder", target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks is unavailable for this Windows account")
            inventory = scan(self.root)
        self.assertEqual(inventory["totals"]["files"], 0)
        self.assertEqual(inventory["skipped_reparse_points"], ["linked-folder"])

    def test_windows_junction_flag_is_recognized(self):
        self.assertTrue(is_reparse(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))
        self.assertFalse(is_reparse(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0)))

    def test_junction_flag_stops_walker_before_reading_children(self):
        self.file("junction-folder/do-not-traverse.bin")
        original = Path.lstat

        def junction_stat(path):
            metadata = original(path)
            if path == self.root / "junction-folder":
                return SimpleNamespace(st_mode=metadata.st_mode, st_file_attributes=0x400,
                                       st_mtime_ns=metadata.st_mtime_ns)
            return metadata

        with patch.object(Path, "lstat", junction_stat):
            inventory = scan(self.root)
        self.assertEqual(inventory["totals"]["files"], 0)
        self.assertEqual(inventory["skipped_reparse_points"], ["junction-folder"])

    def test_protected_state_models_release_app_and_runtime_tests_are_not_candidates(self):
        for path in (
            "data/secure/owner-key.hash", "data/personal_memory/private-fact.sqlite3",
            "data/assistant_followthrough/inbox.sqlite3", "data/models/speech/model.bin",
            ".venv/Scripts/python.exe", "desktop/src-tauri/target/release/desktop.exe",
            "core/conversation_runtime/fluid_runtime_test.py",
        ):
            self.file(path)
        self.file("desktop/src-tauri/target/release/deps/cache.rlib")
        self.file("core/voice_output/voice_config.yaml", b'piper:\n  model_path: "data/voices/piper/current.onnx"\n  config_path: "data/voices/piper/current.onnx.json"\n')
        self.file("data/voices/piper/current.onnx")
        self.file("data/voices/piper/current.onnx.json")
        self.file("data/voices/piper/alternate.onnx")
        inventory = self.complete()
        selected = [path for group in inventory["candidates"] for path in group["paths"]]
        for path in selected:
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("..", Path(path).parts)
            ordinary_path(self.root, path).resolve().relative_to(self.root.resolve())
        for protected in ("data/secure", "data/personal_memory", "data/assistant_followthrough", "data/models", ".venv"):
            self.assertFalse(any(path == protected or path.startswith(protected + "/") for path in selected))
        self.assertNotIn("desktop/src-tauri/target/release/desktop.exe", selected)
        self.assertNotIn("core/conversation_runtime/fluid_runtime_test.py", selected)
        self.assertNotIn("data/voices/piper/current.onnx", selected)
        self.assertIn("data/voices/piper/alternate.onnx", selected)

    def test_no_voice_model_candidates_when_config_cannot_be_verified(self):
        self.file("data/voices/piper/possibly-active.onnx")
        inventory = self.complete()
        self.assertFalse(any(group["id"] == "C02" for group in inventory["candidates"]))

    def test_reference_pass_does_not_open_private_data_or_credential_configs(self):
        self.file("core/private_config.yaml", b"token: NEVER_OPEN_PRIVATE_CONFIG")
        self.file("data/secure/token.json", b'{"value":"NEVER_OPEN_USER_TOKEN"}')
        self.file("core/runtime.py", b"from core.conversation_runtime.fluid_runtime_test import StreamingResponse\n")
        inventory = scan(self.root)
        original = Path.read_text

        def guarded_read(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertNotIn(relative, {"core/private_config.yaml", "data/secure/token.json"})
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            usage = reference_audit(self.root, inventory)
        self.assertEqual(usage["references"]["runtime_test_dependency"], [{"path": "core/runtime.py", "line": 1}])
        self.assertNotIn("NEVER_OPEN", json.dumps(usage))

    def test_markdown_hides_owner_filenames_and_full_comparison_paths(self):
        self.file("data/personal_memory/PRIVATE_OWNER_FILENAME.sqlite3")
        self.file("data/carplay_sessions/PRIVATE_SESSION_UUID.wav")
        inventory = self.complete()
        inventory["comparison"] = {"baseline_finished_at": "fixture", "added": ["data/PRIVATE_CHANGE"], "missing": [], "changed": [], "limitations": "fixture"}
        review = render_review(inventory)
        self.assertNotIn("PRIVATE_OWNER_FILENAME", review)
        self.assertNotIn("PRIVATE_SESSION_UUID", review)
        self.assertNotIn("PRIVATE_CHANGE", review)
        self.assertIn("data/carplay_sessions/*.wav", review)
        self.assertEqual(review, render_review(inventory))

    def test_comparison_marks_added_missing_and_changed_paths(self):
        changed = self.file("changed.txt", b"old")
        baseline = scan(self.root)
        # A historical path absent from today's fixture exercises disappearance
        # without granting this scanner or its tests a project-file delete mode.
        baseline["files"].append({"path": "gone.txt", "bytes": 7, "mtime_ns": 0})
        self.file("added.txt")
        changed.write_bytes(b"new version")
        comparison = compare_inventory(scan(self.root), baseline)
        self.assertEqual(comparison["added"], ["added.txt"])
        self.assertEqual(comparison["missing"], ["gone.txt"])
        self.assertEqual(comparison["changed"], ["changed.txt"])
        baseline["root"] = str(self.root / "other-project")
        with self.assertRaises(ValueError):
            compare_inventory(scan(self.root), baseline)

    def test_report_destinations_cannot_overwrite_source_or_escape_project(self):
        for relative, kind in (("core/brain/brain_config.yaml", "report"), ("../elsewhere.json", "json"),
                               ("data/secure/inventory.json", "json"), ("docs/cleanup_inventory.json", "json")):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                report_destination(self.root, relative, kind=kind)
        self.assertEqual(report_destination(self.root, "data/cleanup_review/inventory.json", kind="json"), self.root / "data/cleanup_review/inventory.json")
        self.file("docs/CLEANUP_REVIEW.md", b"User-authored document\n")
        with self.assertRaises(ValueError):
            report_destination(self.root, "docs/CLEANUP_REVIEW.md", kind="report")


if __name__ == "__main__":
    unittest.main()
