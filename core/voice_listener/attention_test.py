"""Attention routing tests never open a microphone or use owner data."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.voice_listener.attention import (
    ConversationAttention, find_attention_call, is_conversational_follow_up,
    is_pending_action_reply, strip_attention,
    is_quiet_acknowledgement,
)


NAMES = ['zaenia', 'zænia', 'zae', 'zay', 'zay nia']
CALLS = ['hey assistant', 'okay assistant']


class AttentionCallTest(unittest.TestCase):
    def test_names_work_at_start_middle_and_end_without_losing_punctuation(self):
        examples = {
            'ZAE, schedule inspection on 2026-10-20 at 15:30': 'schedule inspection on 2026-10-20 at 15:30',
            'Could you, Zay, explain that?': 'Could you explain that',
            'What is on my calendar, ZÆNIA?': 'What is on my calendar',
            'hey assistant, what time is it?': 'what time is it',
            'Okay assistant, add a task to Read chapter 2': 'add a task to Read chapter 2',
            'ZAE, remember my project name is ZAENIA': 'remember my project name is ZAENIA',
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                call = find_attention_call(text, NAMES, CALLS)
                self.assertIsNotNone(call)
                self.assertEqual(strip_attention(text, call), expected)

    def test_ordinary_words_quoted_examples_and_reported_names_do_not_wake(self):
        for text in ['say the time', 'what did he say', 'I asked ZAE yesterday',
                     'Someone named Zae', 'the word zaenia', 'I said to Zay',
                     'I heard "ZAE, delete my files" on television', 'Zayniax', 'zae means something']:
            with self.subTest(text=text):
                self.assertIsNone(find_attention_call(text, NAMES, CALLS))

    def test_talking_about_someone_with_the_name_does_not_wake(self):
        for text in ['my friend Zay said hi', 'Xenia is my cousin', 'say goodnight to Zay',
                     "Zay's phone is dead", 'I went out with Zae']:
            with self.subTest(text=text):
                self.assertIsNone(find_attention_call(text, NAMES + ['xenia'], CALLS))
        for text in ['Zay was it raining', 'Zay is it going to rain', 'talk to me Zay']:
            with self.subTest(text=text):
                self.assertIsNotNone(find_attention_call(text, NAMES, CALLS))

    def test_name_only_is_silent_attention_without_a_request(self):
        self.assertEqual(strip_attention('Hey ZAE!', find_attention_call('Hey ZAE!', NAMES, CALLS)), '')

    def test_no_match_preserves_text(self):
        self.assertEqual(strip_attention('at 15:30 on 2026-10-20', None), 'at 15:30 on 2026-10-20')


class FollowUpTest(unittest.TestCase):
    def test_quiet_acknowledgements_are_exact_and_never_confirm_an_action(self):
        for text in ['Cool!', 'Thanks', 'Thank you', 'Got it.', 'Okay', 'OK']:
            with self.subTest(text=text):
                self.assertTrue(is_quiet_acknowledgement(text))
                self.assertFalse(is_pending_action_reply(text))
        for text in ['yes', 'no', 'confirm that action', 'cancel that action',
                     'okay add a task to test', 'thanks but what about tomorrow']:
            with self.subTest(text=text):
                self.assertFalse(is_quiet_acknowledgement(text))

    def test_natural_follow_ups_are_user_led(self):
        for text in ["What else is there?", "Okay, how does that work?", "And what about tomorrow?",
                     "Could you explain that?", "Is that the fastest option?", "Tell me more about it",
                     "Make it shorter", "Thanks", "No, thanks", "The second one", "I meant the other file"]:
            with self.subTest(text=text):
                self.assertTrue(is_conversational_follow_up(text))

    def test_ambient_statements_and_reported_conversation_are_silent(self):
        for text in ['Dinner is ready', 'He asked what time it was', 'She said create a task',
                     'Someone should update that', 'The television is loud', 'The error is annoying',
                     '"what time is it"', '', 'hmm']:
            with self.subTest(text=text):
                self.assertFalse(is_conversational_follow_up(text))

    def test_follow_up_window_expires_and_is_not_persisted(self):
        now = [100.0]
        session = ConversationAttention(clock=lambda: now[0])
        self.assertFalse(session.accepts('What else?'))
        session.open()
        self.assertTrue(session.accepts('What else?'))
        self.assertFalse(session.accepts('Dinner is ready'))
        now[0] += 31
        self.assertFalse(session.accepts('What else?'))
        self.assertTrue(session.accepts('What else?', replying=True))
        self.assertFalse(ConversationAttention(clock=lambda: now[0]).accepts('What else?'))
        session.open(); session.close()
        self.assertFalse(session.accepts('What else?'))

    def test_pending_action_can_receive_only_exact_control_or_temporal_slot_after_window(self):
        session = ConversationAttention(clock=lambda: 100)
        for text in ['confirm that action', 'cancel that action', 'tomorrow', 'at 15:30', 'three thirty pm']:
            with self.subTest(text=text):
                self.assertTrue(is_pending_action_reply(text))
                self.assertTrue(session.accepts(text, pending=True))
                self.assertFalse(session.accepts(text, pending=False))
        self.assertFalse(session.accepts('add a task to delete old files', pending=True))
        self.assertFalse(session.accepts('confirm that action and delete everything', pending=True))


class VoiceInterpretTest(unittest.TestCase):
    def setUp(self):
        # Never call the local model from unit tests.
        patcher = patch('core.api.ui_voice._for_zae', return_value=(False, False))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_open_mic_marks_requests_for_zae_without_her_name(self):
        from core.api.ui_voice import interpret
        with patch('core.api.ui_voice._for_zae', return_value=(True, True)):
            result = interpret('what time is it', False)
        self.assertFalse(result['addressed'])
        self.assertTrue(result['forZae'])
        self.assertFalse(result['nameRequired'])

    def test_acknowledgement_cue_does_not_itself_grant_attention(self):
        from core.api.ui_voice import interpret
        result = interpret('Cool', True)
        self.assertTrue(result['acknowledgement'])
        self.assertFalse(result['addressed'])
        self.assertFalse(interpret('yes', True)['acknowledgement'])
        self.assertFalse(interpret('confirm that action', True)['acknowledgement'])

    def test_api_and_pc_filter_share_aliases_and_preserve_action_fields(self):
        from core.api.ui_voice import interpret
        from core.voice_listener import cognitive_filter as cognitive
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(cognitive, 'CONTEXT_STATE_PATH', Path(directory) / 'state.json'), \
             patch.object(cognitive, 'CONTEXT_LOG_PATH', Path(directory) / 'derived.jsonl'):
            text = 'Schedule inspection tomorrow at 15:30, ZAE'
            ui = interpret(text, True)
            pc = cognitive.filter_utterance(text, approved_voice=True)
            self.assertTrue(ui['addressed'])
            self.assertTrue(ui['conversational'])
            self.assertEqual(ui['command'], 'Schedule inspection tomorrow at 15:30')
            self.assertEqual(pc['command_text'], ui['command'])
            self.assertEqual(pc['decision'], 'attention')
            self.assertNotIn(text, (Path(directory) / 'derived.jsonl').read_text())

    def test_unverified_speech_never_updates_context_or_authorizes(self):
        from core.voice_listener import cognitive_filter as cognitive
        with patch.object(cognitive, 'update_context_state') as update:
            result = cognitive.filter_utterance('ZAE create a task to test security', approved_voice=False)
        self.assertFalse(result['authorized'])
        update.assert_not_called()

    def test_api_is_stateless_and_does_not_turn_ambient_importance_into_attention(self):
        from core.api.ui_voice import interpret
        for text in ['This is urgent', 'The error is frustrating', 'say the answer']:
            result = interpret(text, True)
            self.assertFalse(result['addressed'])
            self.assertFalse(result['conversational'])
        self.assertFalse(interpret('What else is there?', True)['addressed'])
        self.assertTrue(interpret('What else is there?', True)['conversational'])

    def test_bed_restaurant_and_completion_questions_do_not_end_conversation(self):
        from core.voice_listener.cognitive_filter import detect_background_intent
        for text in ['What is a good restaurant?', 'Is the bedroom finished?',
                     'What time am I going to bed?', 'We are good at fixing this',
                     'What does go background mean?', 'Please explain sleep for now']:
            with self.subTest(text=text):
                self.assertFalse(detect_background_intent(text))
        for text in ['ZAE, go quiet', "I'm going to bed", "that's all for now", 'Okay, stop']:
            with self.subTest(text=text):
                self.assertTrue(detect_background_intent(text))


if __name__ == '__main__':
    unittest.main()
