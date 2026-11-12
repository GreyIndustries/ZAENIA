"""Safety-gate regressions: no inference, candidate execution, network or private stores.

Only the fixed Node entry-point refusal/usage branches run in a subprocess. All
candidate execution paths and the trusted-fixture checker are mocked.
"""
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench
import check_answer_keys
import pilot_tasks


class ExecutionGateTests(unittest.TestCase):
    def test_python_checker_blocks_before_files_or_process(self):
        with mock.patch.object(pilot_tasks.tempfile, "TemporaryDirectory") as directory, mock.patch.object(pilot_tasks.subprocess, "run") as execute:
            ok, reason = pilot_tasks.check("candidate marker", "test marker")
        self.assertFalse(ok)
        self.assertIn(pilot_tasks.UNSAFE_FLAG, reason)
        directory.assert_not_called()
        execute.assert_not_called()

    def test_combined_checker_blocks_both_languages_before_dispatch(self):
        with mock.patch.object(pilot_tasks, "check") as python, mock.patch.object(bench.tempfile, "TemporaryDirectory") as directory, mock.patch.object(bench.subprocess, "run") as execute:
            for language in ("py", "ts"):
                with self.subTest(language=language):
                    ok, reason = bench.check(language, "candidate marker", "test marker")
                    self.assertFalse(ok)
                    self.assertIn(pilot_tasks.UNSAFE_FLAG, reason)
        python.assert_not_called()
        directory.assert_not_called()
        execute.assert_not_called()

    def test_run_blocks_before_loading_either_model_mode(self):
        with mock.patch.object(bench, "ask_fast") as fast, mock.patch.object(bench, "ask_think") as think:
            for thinking in (False, True):
                with self.assertRaisesRegex(PermissionError, "execution is disabled"):
                    bench.run("never-loaded", 1, thinking)
        fast.assert_not_called()
        think.assert_not_called()

    def test_cli_without_flag_blocks_before_run_or_results(self):
        with mock.patch.object(bench, "run") as run, mock.patch.object(bench, "OUT") as output:
            with self.assertRaisesRegex(SystemExit, "execution is disabled"):
                bench.main(["1", "fast", "never-loaded"])
        run.assert_not_called()
        self.assertEqual(output.mock_calls, [])

    def test_python_opt_in_is_propagated_without_executing(self):
        with mock.patch.object(pilot_tasks, "check", return_value=(True, "")) as python:
            self.assertEqual(bench.check("py", "candidate marker", "test marker", allow_unsafe_local_execution=True), (True, ""))
        python.assert_called_once_with("candidate marker", "test marker", allow_unsafe_local_execution=True)

    def test_typescript_opt_in_reaches_child_without_executing(self):
        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(bench.tempfile, "TemporaryDirectory") as directory, mock.patch.object(Path, "write_text") as write, mock.patch.object(bench.subprocess, "run", return_value=completed) as execute:
            directory.return_value.__enter__.return_value = "unused-mocked-directory"
            self.assertEqual(bench.check("ts", "candidate marker", "test marker", allow_unsafe_local_execution=True), (True, ""))
        self.assertEqual(write.call_count, 2)
        self.assertEqual(execute.call_args.args[0][:3], ["node", bench.RUN_TS, pilot_tasks.UNSAFE_FLAG])

    def test_trusted_verifier_only_checks_fixed_repository_fixtures(self):
        references = set(check_answer_keys.REF.values())
        buggy = {prompt.split("\n\n", 1)[1] for _, _, kind, prompt, _ in bench.TASKS if kind == "fix"}
        def fixed_only(language, code, tests, *, allow_unsafe_local_execution=False):
            self.assertTrue(allow_unsafe_local_execution)
            self.assertIn(code, references | buggy)
            return (code in references, "mocked fixture check")
        with mock.patch.object(bench, "check", side_effect=fixed_only) as check, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_answer_keys.main(), 0)
        self.assertEqual(check.call_count, len(bench.TASKS) + len(buggy))

    @unittest.skipUnless(shutil.which("node"), "Node is required to verify the direct child gate")
    def test_direct_typescript_child_refuses_before_input_reads(self):
        result = subprocess.run([shutil.which("node"), bench.RUN_TS, "nonexistent-candidate.ts", "nonexistent-tests.js"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("execution is disabled", result.stderr)
        self.assertNotIn("ENOENT", result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is required to verify child argument validation")
    def test_direct_typescript_child_validates_inputs_before_loading(self):
        result = subprocess.run([shutil.which("node"), bench.RUN_TS, pilot_tasks.UNSAFE_FLAG], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
