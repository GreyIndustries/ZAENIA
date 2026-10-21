"""Isolated plumbing checks. These tests do not measure a real model's reasoning."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from .benchmark import load_cases, request_for_case, run_benchmark, score_decision
from .engine import ReasoningEngine
from .models import Decision, InvalidDecision, ReasoningRequest, decision_schema, strict_json
from .providers import ExistingLocalProvider, OpenAIProvider, ProviderError, ProviderReply


def decision_data(kind="answer", message="2", actions=None, questions=None, evidence_ids=None):
    return {"kind": kind, "message": message, "explanation": "Brief conclusion.",
            "questions": questions or [], "evidence_ids": evidence_ids or [],
            "actions": actions or [], "execution_status": "not_executed"}


def action_data(operation="calendar.write", **changes):
    params = {"kind": "reminder", "title": "Formation reminder",
              "trigger_at": "2026-10-14T06:15:00-07:00",
              "event_at": "2026-10-14T06:30:00-07:00", "lead_minutes": 15,
              "timezone": "America/Los_Angeles"}
    params.update(changes)
    return {"operation": operation, "parameters_json": json.dumps(params)}


class FixedProvider:
    name, model = "simulation", "fixture-only"

    def __init__(self, value=None, error=None):
        self.value = value or decision_data()
        self.error = error
        self.seen = []

    def generate(self, system, user, schema):
        self.seen.append((system, strict_json(user), schema))
        if self.error:
            raise self.error
        return ProviderReply(json.dumps(self.value), {"total_tokens": 1})


class ResponseBytes:
    def __init__(self, value):
        self.bytes = json.dumps(value).encode("utf-8")

    def read(self, limit):
        return self.bytes[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def response_data(text=None, **changes):
    value = {"status": "completed", "output": [
        {"type": "reasoning", "content": "private internal content"},
        {"type": "message", "content": [{"type": "output_text",
                                            "text": text or json.dumps(decision_data())}]}],
        "usage": {"input_tokens": 12, "output_tokens": 20, "total_tokens": 32,
                  "output_tokens_details": {"reasoning_tokens": 5}}}
    value.update(changes)
    return value


class ReasoningChecks(unittest.TestCase):
    def setUp(self):
        self.corpus, self.digest = load_cases()
        self.cases = {case["id"]: case for case in self.corpus["cases"]}
        self.request = request_for_case(self.cases["formation_reminder"])

    def parse(self, value, request=None):
        return Decision.parse(json.dumps(value), request or self.request)

    def test_reminder_is_only_a_proposal(self):
        result = self.parse(decision_data("proposal", "I propose a reminder.", [action_data()]))
        self.assertEqual(result.execution_status, "not_executed")
        self.assertTrue(score_decision(self.cases["formation_reminder"], result)[0])

    def test_wrong_lead_time_rejected(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action_data(trigger_at="2026-10-14T06:20:00-07:00")]))

    def test_past_reminder_rejected(self):
        later = ReasoningRequest("Set it.", "2026-10-14T07:00:00-07:00")
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action_data()]), later)

    def test_dst_uses_elapsed_minutes(self):
        case = self.cases["dst_elapsed_reminder"]
        action = action_data(trigger_at="2026-03-08T01:40:00-08:00",
                             event_at="2026-03-08T03:10:00-07:00", lead_minutes=30)
        result = self.parse(decision_data("proposal", actions=[action]), request_for_case(case))
        self.assertTrue(score_decision(case, result)[0])

    def test_nonexistent_dst_time_rejected(self):
        case = self.cases["dst_elapsed_reminder"]
        action = action_data(trigger_at="2026-03-08T02:40:00-08:00",
                             event_at="2026-03-08T03:10:00-07:00", lead_minutes=30)
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action]), request_for_case(case))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action_data(trigger_at="2026-10-14T06:15:00")]))

    def test_boolean_is_not_a_lead_time(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action_data(lead_minutes=True)]))

    def test_unknown_operation_rejected(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action_data(operation="shell.execute")]))

    def test_extra_callback_field_rejected(self):
        action = action_data()
        action["callback"] = "dangerous callback"
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action]))

    def test_model_cannot_mark_execution_complete(self):
        value = decision_data()
        value["execution_status"] = "completed"
        with self.assertRaises(InvalidDecision):
            self.parse(value)

    def test_unavailable_evidence_rejected(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data(evidence_ids=["invented_source"]))

    def test_clarification_cannot_also_propose_action(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("clarify", actions=[action_data()], questions=["When?"]))

    def test_clarification_requires_a_question(self):
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("clarify"))

    def test_duplicate_fields_rejected(self):
        raw = json.dumps(decision_data()).replace('"kind": "answer"', '"kind": "answer", "kind": "refuse"')
        with self.assertRaises(InvalidDecision):
            Decision.parse(raw, self.request)

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):
            strict_json('{"value": NaN}')

    def test_markdown_wrapped_output_rejected(self):
        with self.assertRaises(InvalidDecision):
            Decision.parse("```json\n" + json.dumps(decision_data()) + "\n```", self.request)

    def test_caller_evidence_is_snapshotted(self):
        evidence = {"schedule": {"formation_at": "original"}}
        source = ReasoningRequest("Question", self.request.now, evidence=evidence)
        copy = source.snapshot()
        evidence["schedule"]["formation_at"] = "changed"
        self.assertEqual(copy.evidence["schedule"]["formation_at"], "original")

    def test_calendar_read_range_rejected_if_inverted(self):
        action = {"operation": "calendar.read", "parameters_json": json.dumps({
            "start_at": "2026-10-14T07:00:00-07:00", "end_at": "2026-10-14T06:00:00-07:00",
            "timezone": "America/Los_Angeles"})}
        with self.assertRaises(InvalidDecision):
            self.parse(decision_data("proposal", actions=[action]))

    def test_rename_is_explicit_and_advisory(self):
        action = {"operation": "files.rename", "parameters_json": json.dumps({
            "source": "C:/example/one.txt", "destination": "C:/example/two.txt"})}
        result = self.parse(decision_data("proposal", actions=[action]))
        self.assertEqual(result.actions[0].parameters["source"], "C:/example/one.txt")
        self.assertEqual(result.execution_status, "not_executed")

    def test_wrong_arithmetic_fails_scorer(self):
        wrong = self.parse(decision_data(message="24 vehicles"))
        self.assertFalse(score_decision(self.cases["equipment_count"], wrong)[0])

    def test_wrong_weather_location_fails_scorer(self):
        wrong = self.parse(decision_data("proposal", actions=[{
            "operation": "weather.read", "parameters_json": '{"location":"JBLM, WA"}'}]))
        self.assertFalse(score_decision(self.cases["evening_weather_location"], wrong)[0])

    def test_expected_answers_never_reach_provider(self):
        provider = FixedProvider(error=ProviderError("simulated outage"))
        run_benchmark(ReasoningEngine(provider), limit=2)
        for system, request, schema in provider.seen:
            self.assertEqual(set(request), {"question", "current_time", "timezone", "reference_evidence"})
            self.assertNotIn("expected", request)
            self.assertNotIn("case_id", request)

    def test_provider_errors_count_as_attempts(self):
        provider = FixedProvider(error=ProviderError("simulated outage"))
        result = run_benchmark(ReasoningEngine(provider), limit=3, repeats=2)
        self.assertEqual((result["attempted"], result["passed"], result["score_percent"]), (6, 0, 0))
        self.assertEqual(len(provider.seen), 6)
        self.assertEqual(result["executed_actions"], 0)

    def test_invalid_output_is_not_a_pass(self):
        provider = FixedProvider(value={"kind": "answer"})
        result = run_benchmark(ReasoningEngine(provider), limit=1)
        self.assertEqual(result["results"][0]["status"], "invalid_output")
        self.assertEqual(result["passed"], 0)

    def test_all_cases_have_parseable_reference_decisions(self):
        # This tests fixtures and scorer compatibility, not model capability.
        for case in self.corpus["cases"]:
            wanted = case["expected"]
            actions = []
            for target in wanted.get("actions", []):
                params = dict(target["parameters"])
                if target["operation"] == "calendar.write":
                    params["title"] = "Synthetic reminder"
                actions.append({"operation": target["operation"], "parameters_json": json.dumps(params)})
            message = {
                "equipment_count": "2", "untrusted_document": "17:00",
                "pacific_date_rollover": "2026-10-14", "missing_dependency": "pygame",
            }.get(case["id"], "Synthetic decision")
            questions = ["What time should I use?"] if wanted["kind"] == "clarify" else []
            result = self.parse(decision_data(wanted["kind"], message, actions, questions), request_for_case(case))
            self.assertTrue(score_decision(case, result)[0], case["id"])


class ProviderChecks(unittest.TestCase):
    def test_openai_request_uses_strict_schema_and_ephemeral_key(self):
        seen = []
        def transport(request, timeout):
            seen.append((request, timeout))
            return ResponseBytes(response_data())
        provider = OpenAIProvider("synthetic-key", transport=transport)
        reply = provider.generate("system", "user", decision_schema())
        request, timeout = seen[0]
        payload = strict_json(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-key")
        self.assertNotIn("synthetic-key", request.data.decode("utf-8"))
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertNotIn("tools", payload)
        self.assertEqual(timeout, 45)
        self.assertEqual(reply.usage["reasoning_tokens"], 5)

    def test_http_error_does_not_echo_credentials_or_remote_body(self):
        def transport(request, timeout):
            raise HTTPError(request.full_url, 401, "synthetic-key", {}, io.BytesIO(b"sensitive remote response"))
        with self.assertRaises(ProviderError) as caught:
            OpenAIProvider("synthetic-key", transport=transport).generate("system", "user", decision_schema())
        self.assertNotIn("synthetic-key", str(caught.exception))
        self.assertNotIn("sensitive", str(caught.exception))

    def test_timeout_has_no_retry_or_automatic_provider_switch(self):
        calls = []
        def transport(request, timeout):
            calls.append(1)
            raise URLError("synthetic-key")
        with self.assertRaises(ProviderError):
            OpenAIProvider("synthetic-key", transport=transport).generate("s", "u", decision_schema())
        self.assertEqual(len(calls), 1)

    def test_incomplete_response_rejected(self):
        with self.assertRaises(ProviderError):
            OpenAIProvider._read_response(response_data(status="incomplete"))

    def test_api_refusal_is_not_parsed_as_a_decision(self):
        output = [{"type": "message", "content": [{"type": "refusal", "refusal": "declined"}]}]
        with self.assertRaises(ProviderError):
            OpenAIProvider._read_response(response_data(output=output))

    def test_raw_reasoning_is_not_in_reply(self):
        reply = OpenAIProvider._read_response(response_data())
        self.assertNotIn("private internal content", reply.text)

    def test_existing_local_interface_is_reused(self):
        seen = []
        def chat(prompt, timeout):
            seen.append((prompt, timeout))
            return json.dumps(decision_data())
        provider = ExistingLocalProvider(chat=chat, model="synthetic-local", timeout=15)
        reply = provider.generate("instruction", "request", decision_schema())
        self.assertIn("instruction", seen[0][0])
        self.assertIn("OUTPUT JSON SCHEMA", seen[0][0])
        self.assertEqual(seen[0][1], 15)
        self.assertEqual(strict_json(reply.text)["kind"], "answer")

    def test_local_error_does_not_echo_exception_body(self):
        def chat(*args, **kwargs):
            raise RuntimeError("synthetic-sensitive-text")
        with self.assertRaises(ProviderError) as caught:
            ExistingLocalProvider(chat=chat).generate("s", "u", decision_schema())
        self.assertNotIn("synthetic-sensitive-text", str(caught.exception))


class AuthenticationChecks(unittest.TestCase):
    def setUp(self):
        from . import __main__ as cli
        self.cli = cli
        self.options = {"command": "benchmark", "provider": "openai", "model": "test",
                        "effort": "medium", "timeout": 45, "max_output_tokens": 4096,
                        "question": "", "limit": 1, "repeats": 1, "progress": False}

    def modules(self, gate):
        foundation = ModuleType("core.foundation")
        foundation.__path__ = []
        entry = ModuleType("core.foundation.local_entry")
        entry.owner_execute = gate
        return {"core.foundation": foundation, "core.foundation.local_entry": entry}

    def test_denied_authentication_prevents_provider_creation(self):
        def gate(*args):
            raise PermissionError("denied")
        with patch.dict(sys.modules, self.modules(gate)), patch.object(self.cli, "_provider") as factory:
            with self.assertRaises(PermissionError):
                self.cli.authorised_run(self.options)
            factory.assert_not_called()

    def test_gate_receives_reviewed_scope_and_no_key(self):
        seen = []
        def gate(operation, params, handler):
            seen.append((operation, params))
            return {"stopped_before_handler": True}
        with patch.dict(sys.modules, self.modules(gate)):
            self.cli.authorised_run(self.options)
        self.assertEqual(seen[0][0], "chat.reply")
        self.assertNotIn("api_key", seen[0][1])

    def test_handler_runs_only_after_gate_and_guidance(self):
        steps = []
        def gate(operation, params, handler):
            steps.append("owner_gate")
            return handler(params)
        def guidance():
            steps.append("guidance")
            return "Protected guidance"
        def factory(params):
            steps.append("provider")
            return FixedProvider(error=ProviderError("simulation"))
        with patch.dict(sys.modules, self.modules(gate)), patch.object(self.cli, "_protected_guidance", guidance), patch.object(self.cli, "_provider", factory):
            self.cli.authorised_run(self.options)
        self.assertEqual(steps, ["owner_gate", "guidance", "provider"])

    def test_failed_guidance_prevents_provider_creation(self):
        def gate(operation, params, handler):
            return handler(params)
        with patch.dict(sys.modules, self.modules(gate)), patch.object(self.cli, "_protected_guidance", side_effect=RuntimeError("simulation")), patch.object(self.cli, "_provider") as factory:
            with self.assertRaises(RuntimeError):
                self.cli.authorised_run(self.options)
            factory.assert_not_called()

    def test_invalid_cli_limits_prevent_authentication_and_network(self):
        with patch.object(self.cli, "authorised_run") as authorised, redirect_stderr(io.StringIO()):
            code = self.cli.main(["benchmark", "--provider", "openai", "--limit", "0"])
        self.assertEqual(code, 2)
        authorised.assert_not_called()


def run_self_test() -> bool:
    suite = unittest.TestSuite()
    for checks in (ReasoningChecks, ProviderChecks, AuthenticationChecks):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(checks))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print("PASS: " + str(result.testsRun) + " isolated reasoning checks.")
        print("Simulated providers only. Live model reasoning and Windows integration remain unverified.")
    return result.wasSuccessful()


if __name__ == "__main__":
    raise SystemExit(0 if run_self_test() else 1)
