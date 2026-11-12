"""Deterministic actions for turns already accepted by VerifiedPipeline.

Only the registered local handlers can execute. A language-model response is
never parsed as a proposal or confirmation. Pending requests live in this voice
session's RAM and require a new verified owner turn before execution.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import re
import time
from typing import Any, Callable


ACTION_OPERATIONS = frozenset({'ui.tasks.write', 'ui.calendar.write', 'memory.write','assistant.apps.launch','assistant.platform.write'})
_CONTROL = re.compile(
    r'^(?:(?:hey\s+)?(?:zay|zae|zænia|zaenia)[,!:]?\s+)?'
    r'(?P<command>confirm|cancel)\s+that\s+action[.!]?$', re.IGNORECASE,
)


@dataclass(frozen=True)
class ActionHandler:
    operation: str
    describe: Callable[[dict[str, Any]], str]
    execute: Callable[[dict[str, Any]], Any]
    receipt: Callable[[Any], str]


@dataclass(frozen=True)
class _Pending:
    session: object
    generation: Any
    expires: float
    request: str
    kind: str
    parameters: dict[str, Any]


def _task(params):
    from core.api.ui_tasks import create_task
    _, task = create_task(**params)
    return task


def _calendar(params):
    from core.api.ui_calendar import add_event
    return add_event(params['title'], params['date'], params['time'], params['recurrence'])


def _remember(params):
    from core.personal_memory import MemoryStore
    return MemoryStore().upsert(**params, source='explicit_owner')


def _forget(params):
    from core.personal_memory import MemoryStore
    return {'key': params['key'], 'deleted': MemoryStore().delete(key=params['key'])}

def _app(params):
    from core.assistant_platform.service import platform
    service=platform()
    result=service.apps.open(params['id'])
    service.history.receipt('app.launch',f"Opened {result['name']}",target=params['id'])
    return result


def _task_receipt(task):
    if not isinstance(task.get('id'), str) or not task['id']:
        raise ValueError('Missing task receipt.')
    return f"Added the task: {task['title']}."


def _calendar_receipt(event):
    if not isinstance(event.get('id'), str) or not event['id']:
        raise ValueError('Missing event receipt.')
    # Use the actual stored start rather than reconstructing the requested time.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    start = datetime.fromisoformat(event['start']).astimezone(ZoneInfo('America/Los_Angeles'))
    return f"Scheduled {event['title']} on {start:%Y-%m-%d} at {start:%H:%M} Pacific."


def _memory_receipt(memory):
    return f"Remembered {memory['key']}: {memory['value']}."


def _forget_receipt(result):
    if result['deleted']:
        return f"Forgot the saved personal memory named {result['key']}."
    return f"There is no saved personal memory named {result['key']}."


def default_handlers():
    return {
        'task.create': ActionHandler(
            'ui.tasks.write',
            lambda p: f"Add the task: {p['title']}, with {p['priority']} priority and no deadline.",
            _task, _task_receipt,
        ),
        'calendar.create': ActionHandler(
            'ui.calendar.write',
            lambda p: f"Schedule {p['title']} on {p['date']} at {p['time']} Pacific, once.",
            _calendar, _calendar_receipt,
        ),
        'memory.remember': ActionHandler(
            'memory.write',
            lambda p: f"Save the personal {p['category']} named {p['key']} with the value: {p['value']}.",
            _remember, _memory_receipt,
        ),
        'memory.forget': ActionHandler(
            'memory.write',
            lambda p: f"Forget the saved personal memory with the exact name: {p['key']}.",
            _forget, _forget_receipt,
        ),
        'app.launch': ActionHandler('assistant.apps.launch',lambda p:f"Open the registered target: {p['name']}.",_app,
            lambda result:f"Opened {result['name']}."),
    }


class ActionSession:
    """Call handle only from the consumed voice-proof delivery callback."""

    def __init__(self, identity, *, propose=None, recall=None, handlers=None,
                 remember=None, clock=time.monotonic, ttl=90.0, auto_confirm=(), approval_policy=None):
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool) or not math.isfinite(ttl) or not 0 < ttl <= 90:
            raise ValueError('Voice proposals expire within 90 seconds.')
        self.dialogue = None
        if propose is None:
            from core.assistant_dialogue import ActionDialogue
            self.dialogue = ActionDialogue(clock=clock)
            propose = self.dialogue.prepare
        if recall is None:
            from core.assistant_service import recall_memory
            recall = recall_memory
        self.identity, self.propose, self.recall = identity, propose, recall
        self.handlers = dict(default_handlers() if handlers is None else handlers)
        if handlers is None:
            def restore_workspace(params):
                from core.assistant_platform.service import platform
                return platform().restore_workspace(params['id'],identity.authorize,launch_apps=True,revision=params['revision'])
            self.handlers['workspace.restore']=ActionHandler('assistant.platform.write',
                lambda p:f"Restore the saved workspace {p['name']} and open its registered apps.",restore_workspace,
                lambda result:f"Requested workspace {result['workspace']['name']}. " + ("Some registered apps could not be opened; review Assistant." if any(item['status']=='failed' for item in result['apps']) else "Its layout will appear in the connected app."))
        if any(handler.operation not in ACTION_OPERATIONS for handler in self.handlers.values()):
            raise ValueError('Voice action handlers must use an approved local operation.')
        self.remember, self.clock, self.ttl = remember, clock, float(ttl)
        # Kinds the verified owner voice authorizes by itself (no "confirm that action").
        self.auto_confirm = frozenset(kind for kind in auto_confirm if kind in self.handlers and kind != 'memory.forget')
        self.approval_policy = approval_policy
        self._session = object()
        self._generation = deepcopy(identity.baseline)
        self._pending = None

    def clear(self):
        self._pending = None
        if self.dialogue is not None:self.dialogue.clear()

    def has_pending(self):
        pending = self._pending
        return bool((pending is not None and pending.session is self._session
                    and pending.generation == self._generation and self.clock() < pending.expires)
                    or (self.dialogue is not None and self.dialogue.has_draft()))

    def handle(self, text: str) -> str | None:
        try:
            self.identity.authorize('chat.reply')
            if self.identity.baseline != self._generation:
                raise PermissionError('The voice session changed; request the action again.')
        except Exception:
            self.clear()
            raise
        if not isinstance(text, str):
            self.clear()
            return None
        control = _CONTROL.fullmatch(text.strip())
        if control:
            if control['command'].lower() == 'cancel':
                existed = self._pending is not None
                self.clear()
                return 'Cancelled the pending action.' if existed else 'There is no pending voice action to cancel.'
            return self._confirm()

        # A fresh request or a conversational turn supersedes the old proposal.
        self._pending = None
        try:
            recall_reply = self.recall(text, self.identity.authorize)
        except PermissionError:
            # An operation-specific denial should not send the request through
            # the model or stop an otherwise approved conversation service.
            self.identity.authorize('chat.reply')
            if self.dialogue is not None:self.dialogue.clear()
            return 'I cannot read personal memory under the active owner policy.'
        if recall_reply is not None:
            if self.dialogue is not None:self.dialogue.clear()
            return recall_reply
        from core.assistant_platform.conversation import read_or_start, prepare
        platform_reply = read_or_start(text,self.identity.authorize)
        if platform_reply is not None: return platform_reply
        result = self.propose(text)
        if result is None: result=prepare(text,self.identity.authorize)
        if result is None:
            return None
        proposal = result.get('proposal')
        if proposal is None:
            return str(result['reply'])
        handler = self.handlers.get(proposal.get('kind'))
        if handler is None:
            return 'That action is not available through verified voice.'
        # Detach the exact confirmed body from the parser and caller objects.
        parameters = json.loads(json.dumps(proposal['parameters'], allow_nan=False))
        details = handler.describe(parameters)
        self._pending = _Pending(self._session, deepcopy(self._generation),
                                 self.clock() + self.ttl, text, proposal['kind'], parameters)
        automatic = self.auto_confirm
        if self.approval_policy is not None:
            automatic = frozenset(self.approval_policy()) - {'memory.forget'}
        if proposal['kind'] in automatic:
            # The verified owner voice is the authorization: do it now.
            return self._confirm()
        return f'{details} Say confirm that action within {self.ttl:g} seconds, or cancel that action.'

    def _confirm(self):
        pending = self._pending
        self.clear()  # Consume before authorization/execution: retries need a new request.
        if pending is None:
            return 'There is no pending voice action. State the full request first.'
        if pending.session is not self._session or pending.generation != self._generation:
            return 'That action belongs to another voice session. State the full request again.'
        if self.clock() >= pending.expires:
            return 'That action expired. State the full request again.'
        handler = self.handlers.get(pending.kind)
        if handler is None:
            return 'That action is no longer available. State the full request again.'
        try:
            self.identity.authorize(handler.operation)
        except PermissionError:
            return 'The active owner policy does not allow this action. Nothing was changed.'
        if self.clock() >= pending.expires:
            return 'That action expired. State the full request again.'
        try:
            result = handler.execute(deepcopy(pending.parameters))
            receipt = handler.receipt(result)
        except Exception:
            # A store may have written before returning an invalid receipt.
            # Do not claim either success or rollback, and never auto-retry.
            return "I couldn't confirm the result. Check your saved data before requesting the action again."
        if self.remember is not None:
            try:
                if pending.kind.startswith('memory.'):
                    # Saved values live only in the personal-memory store so a
                    # later forget cannot revive them from conversation history.
                    question = f"Confirmed personal memory action: {pending.parameters['key']}"
                    saved_answer = f"Personal memory action completed: {pending.parameters['key']}"
                else:
                    question, saved_answer = pending.request, receipt
                self.remember(question=question, answer=saved_answer, route='voice_action')
            except Exception:
                return receipt + " The action completed, but I couldn't save its conversation receipt."
        return receipt


class SpokenActionReply:
    """Use the existing Piper streaming pipeline without asking a model."""

    def __init__(self, text):
        self.text = text

    def stream_ask(self, question, *, remember=False):
        yield {'type': 'route', 'route': 'voice_action', 'streaming_mode': 'verified_action'}
        yield {'type': 'text', 'text': self.text, 'verified': True}
        yield {'type': 'final', 'answer': self.text, 'route': 'voice_action', 'memory_written': False}

    def remember_exchange(self, **kwargs):
        # Actual writes are recorded synchronously by ActionSession, including
        # when the spoken receipt is interrupted. Proposals are never history.
        pass
