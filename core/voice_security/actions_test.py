"""No microphones, live owner credentials, speech models, or owner data."""
from __future__ import annotations

from array import array
from datetime import datetime
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from core.api.assistant_actions import propose_action
from core.voice_security.actions import ActionHandler, ActionSession, SpokenActionReply, default_handlers
from core.voice_security.gate import IdentityGate, VerifiedPipeline
from core.voice_security.identity import OwnerIdentity, VOICE_CAPABILITIES


NOW = datetime(2026, 10, 16, 16, tzinfo=ZoneInfo('America/Los_Angeles'))


class FakeIdentity:
    def __init__(self):
        self.baseline = ('owner-generation', 'approved-mic')
        self.current = self.baseline
        self.calls = []
        self.denied = set()

    def authorize(self, operation='chat.reply'):
        self.calls.append(operation)
        if operation not in VOICE_CAPABILITIES or operation in self.denied or self.current != self.baseline:
            raise PermissionError('Denied test operation.')


class VoiceActionsTest(unittest.TestCase):
    def setUp(self):
        self.identity = FakeIdentity()
        self.clock = [100.0]
        self.executions = []
        self.history = []
        handlers = default_handlers()
        for kind in ('task.create', 'calendar.create', 'memory.remember', 'memory.forget'):
            handler = handlers[kind]
            def execute(params, kind=kind):
                self.executions.append((kind, params))
                if kind == 'calendar.create':
                    return {'id': 'saved-event', 'title': params['title'], 'start': f"{params['date']}T{params['time']}:00-07:00"}
                if kind == 'memory.forget':
                    return {'key': params['key'], 'deleted': True}
                return {'id': 'saved-record', **params}
            handlers[kind] = ActionHandler(handler.operation, handler.describe, execute, handler.receipt)
        self.handlers = handlers
        self.session = self.make_session()

    def make_session(self, **kwargs):
        return ActionSession(self.identity, propose=lambda text: propose_action(text, now=NOW),
                             recall=lambda text, authorize: None, handlers=self.handlers,
                             remember=lambda **record: self.history.append(record),
                             clock=lambda: self.clock[0], **kwargs)

    def test_proposal_does_not_execute_and_spells_out_parameters(self):
        reply = self.session.handle('Zae, add a task to inspect the car.')
        self.assertIn('inspect the car', reply)
        self.assertIn('Normal priority and no deadline', reply)
        self.assertIn('confirm that action within 90 seconds', reply)
        self.assertEqual(self.executions, [])
        self.assertEqual(self.history, [])

    def test_exact_verified_confirmation_writes_one_real_receipt(self):
        self.session.handle('Add a task to inspect the car')
        reply = self.session.handle('Zay, confirm that action.')
        self.assertEqual(reply, 'Added the task: inspect the car.')
        self.assertEqual(self.executions, [('task.create', {'title': 'inspect the car', 'priority': 'Normal', 'deadline': None})])
        self.assertEqual(self.identity.calls[-1], 'ui.tasks.write')
        self.assertEqual(self.history[0]['answer'], reply)
        self.session.handle('confirm that action')
        self.assertEqual(len(self.executions), 1)

    def test_verified_voice_authorizes_creates_but_never_a_forget(self):
        session = self.make_session(auto_confirm=('task.create', 'calendar.create', 'memory.forget'))
        self.assertEqual(session.handle('Add a task to inspect the car'), 'Added the task: inspect the car.')
        self.assertEqual(self.executions[-1][0], 'task.create')
        self.assertFalse(session.has_pending())
        self.assertNotIn('memory.forget', session.auto_confirm)

    def test_calendar_uses_shared_parser_and_real_stored_start(self):
        reply = self.session.handle('Schedule car inspection on 2026-10-20 at 15:30')
        self.assertIn('2026-10-20 at 15:30 Pacific', reply)
        reply = self.session.handle('confirm that action')
        self.assertEqual(reply, 'Scheduled car inspection on 2026-10-20 at 15:30 Pacific.')
        self.assertEqual(self.identity.calls[-1], 'ui.calendar.write')
        self.assertEqual(self.executions[0][1]['time'], '15:30')

    def test_receipt_uses_actual_store_title(self):
        handler = self.handlers['task.create']
        self.handlers['task.create'] = ActionHandler(handler.operation, handler.describe,
                                                    lambda params: {'id': 'actual-id', 'title': 'actual saved task'}, handler.receipt)
        session = self.make_session()
        session.handle('Add a task to inspect the car')
        self.assertEqual(session.handle('confirm that action'), 'Added the task: actual saved task.')

    def test_yes_or_embedded_confirmation_never_executes(self):
        for phrase in ('yes', 'okay', 'please confirm that action', 'do not confirm that action',
                       'someone said confirm that action', 'confirm that action and delete files',
                       'confirm that action?', '"confirm that action"'):
            with self.subTest(phrase=phrase):
                self.session.handle('Add a task to inspect the car')
                self.session.handle(phrase)
                self.session.handle('confirm that action')
                self.assertEqual(self.executions, [])

    def test_expiry_at_boundary_consumes_pending(self):
        self.session.handle('Add a task to inspect the car')
        self.clock[0] += 90
        self.assertIn('expired', self.session.handle('confirm that action'))
        self.clock[0] -= 10
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])

    def test_cancel_and_clear_consume_pending(self):
        self.session.handle('Add a task to inspect the car')
        self.assertIn('Cancelled', self.session.handle('cancel that action'))
        self.session.handle('confirm that action')
        self.session.handle('Add a task to inspect the car')
        self.session.clear()
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])

    def test_new_request_replaces_old_pending(self):
        self.session.handle('Add a task to inspect the car')
        self.session.handle('Add a task to wash the car')
        self.session.handle('confirm that action')
        self.assertEqual(self.executions[0][1]['title'], 'wash the car')

    def test_same_generation_different_session_cannot_confirm(self):
        self.session.handle('Add a task to inspect the car')
        other = self.make_session()
        other.handle('confirm that action')
        self.assertEqual(self.executions, [])
        other._pending = self.session._pending
        self.assertIn('another voice session', other.handle('confirm that action'))
        self.assertEqual(self.executions, [])

    def test_reauthentication_or_credential_change_invalidates_pending(self):
        self.session.handle('Add a task to inspect the car')
        self.identity.current = ('new-generation', 'approved-mic')
        with self.assertRaises(PermissionError):
            self.session.handle('confirm that action')
        self.identity.current = self.identity.baseline
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])

    def test_identity_rebind_does_not_transfer_pending(self):
        self.session.handle('Add a task to inspect the car')
        self.identity.baseline = self.identity.current = ('new-authenticated-generation', 'approved-mic')
        with self.assertRaises(PermissionError):
            self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])

    def test_scoped_policy_denial_blocks_and_consumes_action(self):
        self.session.handle('Add a task to inspect the car')
        self.identity.denied.add('ui.tasks.write')
        self.assertIn('does not allow', self.session.handle('confirm that action'))
        self.identity.denied.clear()
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])
        self.assertEqual(self.history, [])

    def test_external_proposal_mutation_cannot_change_confirmed_body(self):
        result = propose_action('Add a task to inspect the car', now=NOW)
        self.session.propose = lambda text: result
        self.session.handle('create task')
        result['proposal']['parameters']['title'] = 'mutated after review'
        self.session.handle('confirm that action')
        self.assertEqual(self.executions[0][1]['title'], 'inspect the car')

    def test_unregistered_and_sensitive_actions_never_execute(self):
        self.session.propose = lambda text: {'reply': 'model text', 'proposal': {'kind': 'files.delete', 'parameters': {'path': 'anything'}}}
        self.assertIn('not available', self.session.handle('delete files'))
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])
        with self.assertRaises(ValueError):
            ActionSession(self.identity, propose=lambda text: None, recall=lambda *args: None,
                          handlers={'arbitrary': ActionHandler('files.delete', str, Mock(), str)})

    def test_failure_never_claims_success_or_retries(self):
        handler = self.handlers['task.create']
        broken = Mock(side_effect=OSError('test failure'))
        self.handlers['task.create'] = ActionHandler(handler.operation, handler.describe, broken, handler.receipt)
        session = self.make_session()
        session.handle('Add a task to inspect the car')
        self.assertIn("couldn't confirm", session.handle('confirm that action'))
        session.handle('confirm that action')
        self.assertEqual(broken.call_count, 1)
        self.assertEqual(self.history, [])

    def test_missing_store_receipt_does_not_claim_success(self):
        handler = self.handlers['task.create']
        self.handlers['task.create'] = ActionHandler(handler.operation, handler.describe, lambda p: {'title': 'not verified'}, handler.receipt)
        session = self.make_session()
        session.handle('Add a task to inspect the car')
        self.assertIn("couldn't confirm", session.handle('confirm that action'))
        self.assertEqual(self.history, [])

    def test_success_survives_conversation_receipt_failure(self):
        self.session.remember = Mock(side_effect=OSError('test history failure'))
        self.session.handle('Add a task to inspect the car')
        reply = self.session.handle('confirm that action')
        self.assertIn('Added the task', reply)
        self.assertIn("couldn't save", reply)
        self.assertEqual(len(self.executions), 1)

    def test_memory_proposal_needs_confirmation_and_keeps_values_out_of_history(self):
        self.session.propose = lambda text: {'reply': 'review', 'proposal': {
            'kind': 'memory.remember', 'parameters': {'key': 'favorite drink', 'value': 'oolong tea', 'category': 'preference'}}}
        self.assertIn('favorite drink with the value: oolong tea', self.session.handle('remember my drink'))
        self.assertEqual(self.executions, [])
        self.assertIn('Remembered favorite drink: oolong tea', self.session.handle('confirm that action'))
        self.assertEqual(self.identity.calls[-1], 'memory.write')
        self.assertNotIn('oolong', str(self.history))

    def test_memory_forget_uses_exact_key_and_confirmation(self):
        self.session.propose = lambda text: {'reply': 'review', 'proposal': {
            'kind': 'memory.forget', 'parameters': {'key': 'favorite drink'}}}
        self.assertIn('exact name: favorite drink', self.session.handle('forget my drink'))
        self.assertIn('Forgot', self.session.handle('confirm that action'))
        self.assertEqual(self.executions, [('memory.forget', {'key': 'favorite drink'})])

    def test_recall_calls_shared_authorizer_and_cancels_pending(self):
        self.session.handle('Add a task to inspect the car')
        def recall(text, authorize):
            if text == 'what do you remember':
                authorize('memory.read')
                return 'Your favorite drink is oolong tea.'
        self.session.recall = recall
        self.assertIn('oolong', self.session.handle('what do you remember'))
        self.assertEqual(self.identity.calls[-1], 'memory.read')
        self.session.handle('confirm that action')
        self.assertEqual(self.executions, [])

    def test_recall_policy_denial_is_not_sent_to_model(self):
        def denied_recall(text, authorize):
            authorize('memory.read')
        self.identity.denied.add('memory.read')
        self.session.recall = denied_recall
        self.session.propose = Mock()
        self.assertIn('cannot read personal memory', self.session.handle('what do you remember'))
        self.session.propose.assert_not_called()

    def test_slow_authorization_cannot_execute_after_expiry(self):
        self.session.handle('Add a task to inspect the car')
        original = self.identity.authorize
        def slow_authorize(operation='chat.reply'):
            original(operation)
            if operation == 'ui.tasks.write':
                self.clock[0] += 90
        self.identity.authorize = slow_authorize
        self.assertIn('expired', self.session.handle('confirm that action'))
        self.assertEqual(self.executions, [])

    def test_unverified_speaker_cannot_transcribe_or_confirm_pending(self):
        pcm = array('h', (int(6000 * math.sin(i * .15)) for i in range(48000))).tobytes()
        accepted = [True]
        transcripts = iter(('Add a task to inspect the car', 'confirm that action'))
        transcribe = Mock(side_effect=lambda audio: next(transcripts))
        mic = ('test mic', 1)
        gate = IdentityGate(lambda audio: .9 if accepted[0] else .2, .7, mic, lambda: 'generation')
        pipeline = VerifiedPipeline(gate, transcribe, self.session.handle)
        self.assertTrue(pipeline.process(pcm, mic))
        accepted[0] = False
        self.assertFalse(pipeline.process(pcm, mic))
        self.assertEqual(transcribe.call_count, 1)
        self.assertEqual(self.executions, [])
        accepted[0] = True
        self.assertTrue(pipeline.process(pcm, mic))
        self.assertEqual(len(self.executions), 1)

    def test_spoken_reply_is_exact_and_never_calls_or_remembers_model(self):
        reply = SpokenActionReply('Added the real task.')
        events = list(reply.stream_ask('ignored user input'))
        self.assertEqual(events[1]['text'], 'Added the real task.')
        self.assertEqual(events[-1]['answer'], events[1]['text'])
        self.assertIsNone(reply.remember_exchange(question='private value'))

    def test_ttl_is_finite_positive_and_bounded(self):
        for value in (0, -1, 91, float('inf'), float('nan'), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make_session(ttl=value)


class OwnerOperationTest(unittest.TestCase):
    def setUp(self):
        self.identity = OwnerIdentity.__new__(OwnerIdentity)
        self.identity.capabilities = VOICE_CAPABILITIES
        self.identity.baseline = ('test-generation',)
        self.identity.generation = lambda: self.identity.baseline
        self.identity.rules = []

    def test_allowed_operations_are_narrow_and_nonsensitive(self):
        for operation in VOICE_CAPABILITIES:
            self.assertIsNone(self.identity.authorize(operation))
        for operation in ('files.delete', 'calendar.write', 'ui.tasks.delete', 'auth.token.create', 'voice.service.open', '*', None, []):
            with self.subTest(operation=operation), self.assertRaises(PermissionError):
                self.identity.authorize(operation)

    def test_deny_and_reauth_apply_to_exact_scope(self):
        for action in ('deny', 'require_reauth'):
            for scope in ('ui.tasks.write', '*'):
                self.identity.rules = [{'id': 'test-policy', 'enabled': True, 'action': action, 'operations': [scope]}]
                with self.subTest(action=action, scope=scope), self.assertRaises(PermissionError):
                    self.identity.authorize('ui.tasks.write')
                if scope != '*':
                    self.assertIsNone(self.identity.authorize('ui.calendar.write'))

    def test_policy_generation_change_revokes_all_operations(self):
        self.identity.generation = lambda: ('changed-generation',)
        with self.assertRaises(PermissionError):
            self.identity.authorize()

    def test_startup_binds_narrow_capabilities_and_requires_owner_passkey(self):
        identity = OwnerIdentity.__new__(OwnerIdentity)
        modules = {
            'numpy': SimpleNamespace(), 'torch': SimpleNamespace(),
            'core.foundation.auth.speaker_profile': SimpleNamespace(load_encrypted_profile=Mock()),
            'core.foundation.auth.speaker_verifier': SimpleNamespace(SpeakerVerifier=Mock()),
        }
        with patch.dict(sys.modules, modules), \
             patch('core.voice_security.identity.microphone_identity', return_value=('approved test mic', 1)), \
             patch('core.voice_security.identity.digest', return_value='test-profile-digest'), \
             patch('core.voice_security.identity.require_passkey', side_effect=PermissionError('Owner passkey required')) as passkey:
            with self.assertRaisesRegex(PermissionError, 'Owner passkey required'):
                identity.__init__()
        self.assertEqual(passkey.call_args.kwargs['operation'], 'voice.service.open')
        binding = passkey.call_args.kwargs['payload']
        self.assertEqual(set(binding['capabilities']), VOICE_CAPABILITIES)
        self.assertEqual(binding['microphone'], ['approved test mic', 1])


class SharedMemoryIntegrationTest(unittest.TestCase):
    def test_voice_memory_survives_restart_and_forget_uses_the_same_store(self):
        from core.personal_memory import MemoryStore
        identity = FakeIdentity()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'voice-memory.sqlite3'
            store = MemoryStore(path)
            with patch('core.personal_memory.MemoryStore', return_value=store):
                session = ActionSession(identity)
                self.assertIn('oolong tea', session.handle('Zae, remember my favorite drink is oolong tea.'))
                self.assertEqual(store.list(), [])
                self.assertIn('Remembered favorite drink: oolong tea', session.handle('confirm that action'))
            # Reopening the same SQLite file simulates a new voice process.
            reopened = MemoryStore(path)
            with patch('core.personal_memory.MemoryStore', return_value=reopened):
                restarted = ActionSession(identity)
                self.assertIn('oolong tea', restarted.handle('Zae, what do you remember about my favorite drink?'))
                self.assertIn('exact name: favorite drink', restarted.handle('Zae, forget my favorite drink.'))
                self.assertIsNotNone(reopened.get('favorite drink'))
                self.assertIn('Forgot', restarted.handle('confirm that action'))
                self.assertIsNone(reopened.get('favorite drink'))
                self.assertIn("don't have a saved", restarted.handle('what do you remember about my favorite drink'))


class RuntimeDispatchTest(unittest.TestCase):
    def runtime_fixture(self, result=None):
        from core.voice_security.runtime import SecureRuntime
        from core.voice_listener.attention import ConversationAttention
        runtime = SecureRuntime.__new__(SecureRuntime)
        runtime.identity = FakeIdentity()
        runtime.brain = Mock()
        runtime.actions = Mock()
        runtime.actions.has_pending.return_value = False
        runtime.actions.handle.return_value = None
        runtime.attention = ConversationAttention(clock=lambda: 1000)
        runtime.response = None
        runtime._reply_was_active = False
        runtime.collecting = False
        response = Mock()
        response.finished_event.is_set.return_value = False
        factory = Mock(return_value=response)
        gate = Mock(return_value=result or {'decision': 'ignored', 'signals': {}})
        modules = {
            'core.voice_listener.cognitive_filter': SimpleNamespace(filter_utterance=gate),
            'core.conversation.conversation_state': SimpleNamespace(activate_conversation=Mock(), record_user_speech=Mock()),
            'core.brain.dialogue_manager': SimpleNamespace(return_to_background=Mock()),
            'core.conversation_runtime.fluid_runtime_test': SimpleNamespace(StreamingResponse=factory),
            # The desktop app is closed in these tests: the PC voice answers by itself.
            'core.voice_listener.calm_state': SimpleNamespace(calm_turn=lambda text: False, hand_to_app=lambda text: False),
        }
        return runtime, modules, gate, factory

    def test_with_the_app_open_a_verified_request_runs_in_the_app_instead(self):
        runtime, modules, _, factory = self.runtime_fixture({'decision': 'attention', 'command_text': 'log two eggs for breakfast'})
        handed = []
        modules['core.voice_listener.calm_state'] = SimpleNamespace(calm_turn=lambda text: False,
                                                                    hand_to_app=lambda text: handed.append(text) or True)
        with patch.dict(sys.modules, modules):
            runtime.deliver('ZAE log two eggs for breakfast')
        self.assertEqual(handed, ['log two eggs for breakfast'])
        factory.assert_not_called()
        runtime.actions.handle.assert_not_called()

    def test_wake_removal_preserves_original_dates_and_times_for_action_parser(self):
        from core.voice_security.runtime import SecureRuntime
        from core.voice_listener.attention import ConversationAttention
        runtime = SecureRuntime.__new__(SecureRuntime)
        runtime.identity = FakeIdentity()
        runtime.brain = Mock()
        runtime.actions = Mock()
        runtime.actions.handle.return_value = 'Review the event at 15:30.'
        runtime.response = None
        runtime.attention = ConversationAttention()
        runtime._reply_was_active = False
        response = Mock()
        response_factory = Mock(return_value=response)
        modules = {
            'core.voice_listener.cognitive_filter': SimpleNamespace(filter_utterance=lambda *args, **kwargs: {'decision': 'attention', 'command_text': 'schedule inspection on 2026-10-20 at 15:30'}),
            'core.conversation.conversation_state': SimpleNamespace(activate_conversation=Mock(), record_user_speech=Mock()),
            'core.brain.dialogue_manager': SimpleNamespace(return_to_background=Mock()),
            'core.conversation_runtime.fluid_runtime_test': SimpleNamespace(StreamingResponse=response_factory),
        }
        # The app being open must not matter (and must never queue this test sentence into the live app's chat).
        with patch.dict(sys.modules, modules), patch('builtins.print'), patch('core.voice_listener.calm_state.hand_to_app', return_value=False):
            runtime.deliver('Zae, schedule inspection on 2026-10-20 at 15:30')
        runtime.actions.handle.assert_called_once_with('schedule inspection on 2026-10-20 at 15:30')
        response.start.assert_called_once()
        self.assertIsInstance(response_factory.call_args.kwargs['brain'], SpokenActionReply)
        runtime.brain.stream_ask.assert_not_called()

    def ambient_fixture(self, action):
        from core.voice_listener.ambient import AmbientContext, AmbientSettings
        runtime, modules, gate, factory = self.runtime_fixture()
        runtime.ambient = AmbientContext(settings=AmbientSettings())
        runtime.judge = Mock()
        runtime.judge.decide.return_value = {'action': action, 'reason': 'finding keys'}
        runtime._start_ambient = lambda judge: judge()  # run the judge inline
        return runtime, modules, factory

    def test_unaddressed_owner_speech_can_get_a_brain_offer_but_never_an_action(self):
        runtime, modules, factory = self.ambient_fixture('respond')
        with patch.dict(sys.modules, modules):
            runtime.deliver('where did I put my keys')
        runtime.actions.handle.assert_not_called()
        factory.assert_called_once()
        self.assertIs(factory.call_args.kwargs['brain'], runtime.brain)
        self.assertEqual(runtime.ambient.recent(), ['where did I put my keys'])

    def test_without_a_wake_word_a_request_for_zae_is_a_normal_turn(self):
        runtime, modules, factory = self.ambient_fixture('direct')
        runtime.actions.handle.return_value = 'Review the task: buy milk.'
        with patch.dict(sys.modules, modules):
            runtime.deliver('add a task to buy milk')
        runtime.actions.handle.assert_called_once_with('add a task to buy milk')
        self.assertIsInstance(factory.call_args.kwargs['brain'], SpokenActionReply)
        self.assertTrue(runtime.attention.is_active())
        self.assertEqual(runtime.ambient.recent(), [])

    def test_unaddressed_speech_the_brain_declines_is_only_remembered(self):
        runtime, modules, factory = self.ambient_fixture('note')
        with patch.dict(sys.modules, modules):
            runtime.deliver('where did I put my keys')
        factory.assert_not_called()
        self.assertIn('finding keys', runtime.ambient.describe())

    def test_ambient_offer_waits_while_an_action_is_pending(self):
        runtime, modules, factory = self.ambient_fixture('respond')
        runtime.actions.has_pending.return_value = True
        with patch.dict(sys.modules, modules):
            runtime.deliver('where did I put my keys')
        factory.assert_not_called()
        runtime.actions.clear.assert_not_called()

    def test_question_without_live_attention_does_not_reach_actions_or_brain(self):
        runtime, modules, _, factory = self.runtime_fixture()
        with patch.dict(sys.modules, modules):
            runtime.deliver('What time is it?')
        runtime.actions.handle.assert_not_called()
        runtime.actions.clear.assert_not_called()
        factory.assert_not_called()

    def test_quiet_receipt_keeps_listening_without_model_action_or_pending_review_changes(self):
        for text in ['Cool', 'Thanks', 'Got it', 'Okay']:
            with self.subTest(text=text):
                runtime, modules, _, factory = self.runtime_fixture()
                runtime.attention.open()
                runtime.actions.has_pending.return_value = True
                runtime.response = Mock()
                runtime.response.finished_event.is_set.return_value = False
                with patch.dict(sys.modules, modules):
                    runtime.deliver(text)
                runtime.actions.handle.assert_not_called()
                runtime.actions.clear.assert_not_called()
                runtime.response.interrupt.assert_not_called()
                factory.assert_not_called()
                self.assertTrue(runtime.attention.is_active())

    def test_ambient_statement_during_conversation_does_not_interrupt_or_clear_pending_action(self):
        runtime, modules, _, factory = self.runtime_fixture()
        runtime.attention.open()
        runtime.actions.has_pending.return_value = True
        runtime.response = Mock()
        runtime.response.finished_event.is_set.return_value = False
        with patch.dict(sys.modules, modules):
            runtime.deliver('Dinner is ready')
        runtime.response.interrupt.assert_not_called()
        runtime.actions.handle.assert_not_called()
        runtime.actions.clear.assert_not_called()
        factory.assert_not_called()

    def test_user_question_follows_reply_without_repeating_name(self):
        runtime, modules, _, factory = self.runtime_fixture()
        runtime.attention.open()
        with patch.dict(sys.modules, modules):
            runtime.deliver('What about tomorrow?')
        runtime.actions.handle.assert_called_once_with('What about tomorrow?')
        self.assertIs(factory.call_args.kwargs['brain'], runtime.brain)

    def test_fresh_pending_confirmation_can_outlive_short_conversation_window(self):
        runtime, modules, _, factory = self.runtime_fixture()
        runtime.actions.has_pending.return_value = True
        runtime.actions.handle.return_value = 'Added the task: Test.'
        with patch.dict(sys.modules, modules):
            runtime.deliver('confirm that action')
        runtime.actions.handle.assert_called_once_with('confirm that action')
        self.assertIsInstance(factory.call_args.kwargs['brain'], SpokenActionReply)

    def test_background_closes_attention_without_later_reopening_from_interrupted_reply(self):
        runtime, modules, _, _ = self.runtime_fixture({'decision': 'background'})
        runtime.attention.open()
        runtime._reply_was_active = True
        runtime.response = Mock()
        with patch.dict(sys.modules, modules):
            runtime.deliver('ZAE go quiet')
        runtime.actions.clear.assert_called_once()
        self.assertEqual(runtime.state(), 'listening')
        self.assertFalse(runtime.attention.accepts('What else?'))

    def test_follow_up_window_begins_after_reply_finishes(self):
        runtime, _, _, _ = self.runtime_fixture()
        runtime.response = Mock()
        runtime.response.finished_event.is_set.return_value = True
        runtime._reply_was_active = True
        self.assertFalse(runtime.attention.accepts('What else?'))
        self.assertEqual(runtime.state(), 'listening')
        self.assertTrue(runtime.attention.accepts('What else?'))
        self.assertFalse(runtime._reply_was_active)

    def test_revoked_owner_is_rejected_before_attention_or_storage(self):
        runtime, modules, gate, factory = self.runtime_fixture()
        runtime.identity.current = ('revoked-generation',)
        with patch.dict(sys.modules, modules), self.assertRaises(PermissionError):
            runtime.deliver('ZAE, create a task to test')
        gate.assert_not_called()
        runtime.actions.handle.assert_not_called()
        factory.assert_not_called()


class ProactiveVoiceTest(unittest.TestCase):
    def setUp(self):
        from core.voice_security.runtime import SecureRuntime
        self.runtime = SecureRuntime.__new__(SecureRuntime)
        self.runtime.identity = FakeIdentity()
        self.runtime.actions = SimpleNamespace(has_pending=lambda: False)
        self.runtime.collecting = False
        self.runtime.response = None
        self.runtime.next_followthrough_check = 0
        self.service = Mock()
        self.notification = {'id': 'saved-notification', 'canSpeak': True, 'message': 'Car inspection starts in 15 minutes.'}
        self.inbox = {'settings': {'enabled': True, 'spoken': True}, 'quiet': False, 'notifications': [self.notification]}
        self.service.list_notifications.return_value = self.inbox
        self.service.claim_delivery.return_value = {'id': 'saved-notification', 'claimed': True}
        self.runtime.followthrough = self.service
        self.response = Mock()
        self.response.finished_event.is_set.return_value = False
        self.response_factory = Mock(return_value=self.response)
        self.modules = {'core.conversation_runtime.fluid_runtime_test': SimpleNamespace(StreamingResponse=self.response_factory)}

    def announce(self, at=100):
        with patch.dict(sys.modules, self.modules):
            return self.runtime.deliver_followthrough(at)

    def test_opted_in_idle_delivery_claims_then_speaks_exact_saved_message(self):
        self.assertTrue(self.announce())
        self.service.claim_delivery.assert_called_once_with('saved-notification', channel='speech')
        self.response.start.assert_called_once()
        brain = self.response_factory.call_args.kwargs['brain']
        self.assertIsInstance(brain, SpokenActionReply)
        self.assertEqual(brain.text, 'Reminder. Car inspection starts in 15 minutes.')
        self.assertEqual(self.runtime.identity.calls, ['chat.reply', 'notifications.read', 'calendar.read', 'tasks.read', 'notifications.write', 'chat.reply', 'notifications.read', 'calendar.read', 'tasks.read'])
        self.service.poll.assert_not_called()
        self.service.start.assert_not_called()

    def test_no_speech_without_explicit_spoken_preference_or_during_quiet_hours(self):
        for setting, value in (('spoken', False), ('enabled', False)):
            with self.subTest(setting=setting):
                self.inbox['settings'][setting] = value
                self.assertFalse(self.announce())
                self.runtime.next_followthrough_check = 0
                self.inbox['settings'][setting] = True
        self.inbox['quiet'] = True
        self.assertFalse(self.announce())
        self.service.claim_delivery.assert_not_called()
        self.response_factory.assert_not_called()

    def test_ineligible_read_snoozed_or_expired_item_cannot_speak(self):
        self.notification['canSpeak'] = False
        self.assertFalse(self.announce())
        self.service.claim_delivery.assert_not_called()
        self.response_factory.assert_not_called()

    def test_other_device_claim_prevents_duplicate_voice(self):
        self.service.claim_delivery.return_value['claimed'] = False
        self.assertFalse(self.announce())
        self.response_factory.assert_not_called()

    def test_busy_listening_replying_and_reviewing_action_do_not_read_inbox(self):
        self.runtime.collecting = True
        self.assertFalse(self.announce())
        self.runtime.collecting = False
        self.runtime.response = self.response
        self.assertFalse(self.announce())
        self.runtime.response = None
        self.runtime.actions.has_pending = lambda: True
        self.assertFalse(self.announce())
        self.service.list_notifications.assert_not_called()
        self.service.claim_delivery.assert_not_called()
        self.response_factory.assert_not_called()

    def test_scoped_policy_denial_is_silent_and_never_prompts(self):
        for operation in ('chat.reply', 'notifications.read', 'notifications.write'):
            with self.subTest(operation=operation):
                self.runtime.identity.denied = {operation}
                self.runtime.next_followthrough_check = 0
                self.assertFalse(self.announce())
        self.service.claim_delivery.assert_not_called()
        self.response_factory.assert_not_called()

    def test_credential_revocation_after_claim_prevents_speech(self):
        def revoke(notification_id, *, channel):
            self.runtime.identity.current = ('revoked-generation',)
            return {'id': notification_id, 'claimed': True}
        self.service.claim_delivery.side_effect = revoke
        self.assertFalse(self.announce())
        self.response_factory.assert_not_called()

    def test_polling_is_throttled_and_store_errors_stay_silent(self):
        self.service.list_notifications.side_effect = OSError('test store failure')
        self.assertFalse(self.announce())
        self.assertFalse(self.announce(at=110))
        self.assertEqual(self.service.list_notifications.call_count, 1)
        self.assertFalse(self.announce(at=115))
        self.assertEqual(self.service.list_notifications.call_count, 2)
        self.response_factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
