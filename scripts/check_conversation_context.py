"""Optional live context check with synthetic conversations, never owner memory.

Run: .venv/Scripts/python.exe -m scripts.check_conversation_context --live
No audio, action execution, downloads or conversation-journal writes.
"""
import argparse
import json
from pathlib import Path
import time
from core.brain.turn_context import prepare_turn


def exchange(question,answer):
    return [{'role':'user','content':question},{'role':'assistant','content':answer}]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if not args.live:
        print('Pass --live to use the installed local model with synthetic scenarios.');return
    from core.brain.local_llm import chat_local,active_model,get_brain_settings
    from core.brain.conversation_style import user_led_answer
    cases=[]
    history=exchange('Compare maple and walnut desks under $600. I prefer a light wood.','Maple is light and costs $400; walnut is dark and costs $550. Maple fits your preference.')
    cases.append(('reference',history,'Why does that one fit better?',['maple']))
    history=exchange('The budget for this desk project is $600.','I will use $600 for this discussion.')+exchange('Actually, I meant $450 for this desk project.','The corrected budget is $450.')
    cases.append(('correction',history,'What is the budget for this project?',['450']))
    history=exchange('For the desk setup I need to stay under $450 and avoid subscriptions.','Those are the constraints for the desk setup.')
    for index in range(12):history+=exchange(f'Explain exercise {index}.',f'Exercise example {index}.')
    cases.append(('older_constraints',history,'Back to the desk setup: what constraints did I give?',['450','subscription']))
    cases.append(('topic_change',history,'New topic: what is seven times eight?',['56']))
    results=[]
    for name,history,question,expected in cases:
        turn=prepare_turn(question,history)
        started=time.monotonic()
        try:
            answer=user_led_answer(chat_local(question,recent_messages=turn.messages,conversation_context=turn.reference,timeout=90),question=question)
            row={'case':name,'question':question,'answer':answer,'elapsedSeconds':round(time.monotonic()-started,2),
                 'expectedSignalsPresent':all(term in answer.casefold() for term in expected)}
        except Exception as error:
            row={'case':name,'error':type(error).__name__,'expectedSignalsPresent':False}
        results.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    report={'model':active_model(get_brain_settings()),'scope':'Synthetic local-model spot checks; no owner memory or hardware used. Signal checks are limited, not a general comprehension benchmark.','results':results}
    destination=Path(__file__).resolve().parents[1]/'docs/conversation-context-live-check.json'
    destination.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Saved synthetic report:',destination,flush=True)


if __name__=='__main__':main()
