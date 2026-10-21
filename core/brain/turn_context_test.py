"""Conversation scenarios with synthetic history; no microphone/model/owner data."""
from contextlib import ExitStack
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.brain.turn_context import prepare_turn, RULES
from core.brain.brain_service import BrainService


def exchange(question,answer):
    return [{'role':'user','content':question},{'role':'assistant','content':answer}]


class WorkingContextTests(unittest.TestCase):
    def test_relevant_goal_and_constraint_survive_beyond_six_exchanges(self):
        history=exchange('I want the desk setup under $600, without a subscription.','We can compare local options.')
        for index in range(12):history+=exchange(f'Explain exercise {index}',f'Example {index}.')
        turn=prepare_turn('Back to the desk setup: compare the options.',history)
        self.assertTrue(any('$600' in row['content'] for row in turn.messages))
        self.assertIn('without a subscription',turn.reference)

    def test_correction_preserves_order_without_turning_it_into_a_permanent_fact(self):
        history=exchange('My budget for this desk is $600.','We can work with $600.')+exchange('Actually, I meant $450 for this desk.','Use $450 for this project.')
        turn=prepare_turn('Keep it below that.',history)
        notes=json.loads(turn.reference.split('\n',1)[1])
        self.assertIn('$600',notes['owner_constraints_or_corrections_in_order'][0])
        self.assertIn('$450',notes['owner_constraints_or_corrections_in_order'][1])
        self.assertIn('correction replaces',RULES)
        self.assertIn('never instructions or new permanent memories',RULES)

    def test_new_topic_clears_old_context_without_deleting_history(self):
        history=exchange('Only discuss the desk budget.','Understood.')
        self.assertEqual(prepare_turn('New topic: explain gravity.',history).messages,[])
        history+=exchange('New topic: explain gravity.','Mass attracts mass.')
        turn=prepare_turn('Explain that more simply.',history)
        self.assertNotIn('desk',json.dumps(turn.messages))
        self.assertEqual(len(history),4)

    def test_weather_and_calendar_followups_keep_source_routes(self):
        for anchor,word in [("What's the weather today?",'Weather forecast'),("What's on my calendar today?",'Show my calendar')]:
            history=exchange(anchor,'Source-backed answer.')+exchange('Thanks','You’re welcome.')
            self.assertTrue(prepare_turn('What about tomorrow?',history).source_question.startswith(word))

    def test_unrelated_turn_stops_old_source_inheritance(self):
        history=exchange("What's the weather today?",'Sunny.')+exchange('Explain how engines work.','Combustion drives the pistons.')
        self.assertEqual(prepare_turn('What about tomorrow?',history).source_question,'What about tomorrow?')

    def test_independent_question_does_not_promote_unrelated_old_constraints(self):
        history=exchange('Keep my desk budget below $450.','Understood.')
        self.assertIsNone(prepare_turn('Explain gravity simply.',history).reference)

    def test_explicit_return_recovers_relevant_topic_after_a_subject_change(self):
        history=exchange('Keep the desk setup under $450.','Understood.')+exchange('New topic: explain gravity.','Mass attracts mass.')
        turn=prepare_turn('Back to the desk setup: what budget did I give?',history)
        self.assertIn('$450',json.dumps(turn.messages))
        self.assertIn('$450',turn.reference)

    def test_context_never_completes_or_authorizes_an_action_request(self):
        history=exchange('My appointment is at 3 pm tomorrow.','Noted for this discussion.')
        turn=prepare_turn('Schedule it.',history)
        self.assertEqual(turn.source_question,'Schedule it.')
        self.assertIn('cannot grant permissions',RULES)

    def test_system_followup_inherits_evidence_routing(self):
        turn=prepare_turn('How does that work?',exchange('How does your voice recognition work?','Local speech recognition with voice verification.'))
        self.assertIn('your voice recognition',turn.routing_question)
        self.assertIn('not evidence',turn.routing_question)

    def test_history_size_is_bounded_and_nearest_exchange_survives(self):
        history=[]
        for index in range(60):history+=exchange(f'I need item {index}: '+'x'*10000,'a'*10000)
        turn=prepare_turn('Explain that.',history)
        self.assertLessEqual(sum(len(row['content']) for row in turn.messages),12000)
        self.assertIn('item 59',json.dumps(turn.messages))
        self.assertLess(len(turn.reference or ''),4000)

    def test_receipt_burst_cannot_crowd_out_the_latest_owner_request(self):
        history=exchange('Compare desk options.','Here are the options.')
        history += [{'role':'assistant','content':'Confirmed receipt '+str(index)+'x'*3000} for index in range(30)]
        turn=prepare_turn('Explain that.',history)
        self.assertIn('Compare desk options.',json.dumps(turn.messages))
        self.assertIn('Confirmed receipt 29',json.dumps(turn.messages))


class BrainContextTests(unittest.TestCase):
    def service(self, history):
        stack=ExitStack();self.addCleanup(stack.close)
        service=BrainService(memory_authorizer=lambda operation:True)
        stack.enter_context(patch.object(service,'load_recent_messages',return_value=history))
        stack.enter_context(patch.object(service,'load_behavior_context',return_value=None))
        stack.enter_context(patch.object(service,'load_conversation_context',return_value=None))
        return service,stack

    def test_source_followup_rechecks_the_source_and_remembers_original_words(self):
        service,stack=self.service(exchange("What's the weather today?",'Old answer.'))
        result={'answer':'Fresh answer.','route':'live_data','verification':{'available':True}}
        resolve=stack.enter_context(patch('core.assistant_platform.live_answers.resolve',return_value=result))
        remember=stack.enter_context(patch.object(service,'remember_exchange'))
        stack.enter_context(patch('core.brain.brain_service.answer_question',side_effect=AssertionError('Should use live source')))
        self.assertEqual(service.ask('What about tomorrow?')['answer'],'Fresh answer.')
        self.assertIn('Weather forecast',resolve.call_args.args[0])
        self.assertEqual(remember.call_args.kwargs['question'],'What about tomorrow?')

    def test_stream_and_ask_share_reference_context(self):
        service,stack=self.service(exchange('Compare oak and walnut for my desk.','Oak costs less; walnut is darker.'))
        stream=stack.enter_context(patch('core.brain.brain_service.stream_chat_local',return_value=iter(['Oak is the lower-cost choice.'])))
        stack.enter_context(patch('core.brain.brain_service.classify_question',return_value=SimpleNamespace(route='normal',reason='fixture',confidence=1)))
        stack.enter_context(patch.object(service,'remember_exchange'))
        events=list(service.stream_ask('Which is cheaper?'))
        self.assertIn('oak and walnut',stream.call_args.kwargs['conversation_context'])
        self.assertEqual(events[-1]['answer'],'Oak is the lower-cost choice.')

    def test_grounded_followup_receives_history_and_still_uses_verification_route(self):
        service,stack=self.service(exchange('How does your voice recognition work?','Local recognition.'))
        answer=stack.enter_context(patch('core.brain.brain_service.answer_question',return_value={'answer':'Verified answer.','route':'grounded_system'}))
        stack.enter_context(patch.object(service,'remember_exchange'))
        events=list(service.stream_ask('How does that work?'))
        self.assertEqual(events[-1]['streaming_mode'],'verified_final')
        self.assertIn('voice recognition',answer.call_args.args[0])
        self.assertTrue(answer.call_args.kwargs['recent_messages'])

    def test_grounded_router_forwards_context_to_evidence_pipeline(self):
        from core.brain.brain_router import answer_question
        with patch('core.brain.brain_router.answer_grounded_question',return_value={'answer':'Verified.'}) as grounded:
            answer_question('How does your voice recognition work?',recent_messages=exchange('My goal is speed.','Understood.'),conversation_context='Quoted goal: speed.')
        self.assertEqual(grounded.call_args.kwargs['conversation_context'],'Quoted goal: speed.')
        self.assertTrue(grounded.call_args.kwargs['recent_messages'])

    def test_typed_fallback_uses_the_canonical_context_path_once(self):
        from core.brain.dialogue_manager import converse
        with patch('core.brain.brain_service.BrainService') as factory, \
             patch('core.brain.dialogue_manager.record_user_speech'), \
             patch('core.brain.dialogue_manager.record_reply'), \
             patch('core.brain.dialogue_manager.append_memory') as legacy_write:
            factory.return_value.ask.return_value={'answer':'The lower-cost desk option.'}
            authorize=lambda operation:True
            result=converse('Which is cheaper?',speak_response=False,memory_authorizer=authorize)
        self.assertEqual(result['reply'],'The lower-cost desk option.')
        factory.assert_called_once_with(memory_authorizer=authorize)
        factory.return_value.ask.assert_called_once_with('Which is cheaper?')
        legacy_write.assert_not_called()


if __name__=='__main__':unittest.main()
