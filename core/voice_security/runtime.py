"""Owner-verified local speech runtime with confirmed local assistant actions."""
from collections import deque
import queue
import threading
import time
from core.voice_security.gate import VerifiedPipeline
from core.voice_security.identity import OwnerIdentity,microphone_identity
from core.voice_security.actions import ActionSession,SpokenActionReply
from core.assistant_platform.performance import measure

class SecureRuntime:
    # Ambient awareness is optional; these defaults keep it off when unset.
    ambient=None;judge=None;activity=None;_ambient_turn=0;_ambient_lock=threading.Lock()
    def sample_activity(self,now=None):
        """Foreground-window sampling for background context; memory only."""
        if self.activity is not None:self.activity.sample(now)
    def __init__(self,identity,*,followthrough=None):
        from core.conversation_runtime.turn_detector import TurnDetector
        from core.conversation_runtime.partial_transcriber import PartialTranscriber
        from core.brain.brain_service import BrainService
        from core.voice_listener.attention import ConversationAttention
        from core.voice_listener.cognitive_filter import load_config
        self.identity=identity;self.detector=TurnDetector()
        if self.detector.sample_rate!=16000:raise RuntimeError('The secured voice runtime requires 16 kHz mono PCM.')
        self.transcriber=PartialTranscriber(sample_rate=16000)
        self.brain=BrainService(memory_authorizer=identity.authorize);self.brain.learning_channel='verified_voice';self.response=None
        auto=(load_config().get('voice_authorization',{}) or {}).get('auto_confirm',[]) or []
        from core.assistant_platform.service import platform
        self.actions=ActionSession(identity,remember=self.brain.remember_exchange,auto_confirm=tuple(str(kind) for kind in auto),approval_policy=lambda:platform().history.policy()['voiceAutomatic'])
        self.attention=ConversationAttention((load_config().get('attention',{}) or {}).get('follow_up_seconds',30))
        from core.voice_listener.ambient import AmbientContext,AmbientJudge,AmbientSettings
        ambient_settings=AmbientSettings.from_config(load_config().get('ambient',{}))
        self.ambient=AmbientContext(settings=ambient_settings);self.judge=AmbientJudge(ambient_settings)
        from core.voice_listener.activity import ActivitySettings,ActivityTracker
        self.activity=ActivityTracker(settings=ActivitySettings.from_config(load_config().get('activity',{})))
        if self.activity.settings.enabled:self.ambient.activity=self.activity.describe
        self.brain.ambient_context=self.ambient.describe
        try:
            from core.personal_memory.insights import learner
            if self.activity.settings.enabled:learner().activity=self.activity.describe
        except Exception:pass
        self._ambient_turn=0;self._ambient_lock=threading.Lock()
        self._reply_was_active=False
        self.followthrough=followthrough;self.next_followthrough_check=0.0
        self.prefix=deque(maxlen=8);self.audio=[];self.collecting=False
        self.pipeline=VerifiedPipeline(identity.gate,self.transcribe,self.deliver)
    @measure("verified_transcription")
    def transcribe(self,pcm):
        self.transcriber.reset();parts=[]
        for start in range(0,len(pcm),16000):
            result=self.transcriber.feed(pcm[start:start+16000])
            if result['type']=='final' and result['text']:parts.append(result['text'])
        remaining=self.transcriber.finalize()
        if remaining:parts.append(remaining)
        self.transcriber.reset()
        return ' '.join(parts)
    def deliver(self,text):
        from core.voice_listener.cognitive_filter import filter_utterance
        from core.conversation.conversation_state import activate_conversation,record_user_speech
        from core.brain.dialogue_manager import return_to_background
        from core.conversation_runtime.fluid_runtime_test import StreamingResponse
        from core.voice_listener.attention import is_quiet_acknowledgement
        self.identity.authorize()
        # Ædaptive: how he sounds this turn (numbers only), before the turn is answered or handed to the app.
        audio=getattr(self,'_turn_audio',None);self._turn_audio=None
        if audio:
            try:
                from core.personal_memory.voice_tone import observe
                observe(audio,len(str(text).split()))
            except Exception:pass
        # Finish bookkeeping here as well as in the heartbeat: a follow-up can
        # arrive before the next half-second heartbeat after a long reply.
        if self._reply_was_active and self.response is not None and self.response.finished_event.is_set():
            self._reply_was_active=False;self.attention.open()
        was_active=self.attention.is_active(replying=self.response is not None and not self.response.finished_event.is_set())
        # Calm view: a wake-up call (while calm) or sleep phrase (while not) goes to the app; while calm,
        # everything else is ignored, as with the app mic (core/voice_listener/calm_state.py).
        try:
            from core.voice_listener.calm_state import calm_turn
            if calm_turn(text):return
        except Exception:pass
        result=filter_utterance(text,approved_voice=True)
        decision=result['decision']
        if decision=='background':
            with self._ambient_lock:self._ambient_turn+=1
            self.attention.close();self.actions.clear();self.stop_response();return_to_background(reason='verified_owner_background');return
        if decision=='attention':
            activate_conversation()
            self.attention.open()
            reply_text=result.get('command_text','').strip()
            if not reply_text:return
        elif self.attention.accepts(text,pending=self.actions.has_pending(),
                                    replying=self.response is not None and not self.response.finished_event.is_set()):
            self.attention.open();reply_text=text
        else:
            # Ambient speech never clears a reviewed, unexpired owner action,
            # and never reaches the action parser. The brain only decides
            # whether a short spoken offer would help.
            self.consider_ambient(text);return
        # The app mic may have heard and answered the same sentence: answer once.
        try:
            from core.voice_listener.service_status import claim_turn
            if not claim_turn('pc',text):return
        except Exception:pass
        record_user_speech(signals=list(result.get('signals',{})))
        with self._ambient_lock:self._ambient_turn+=1
        if was_active and is_quiet_acknowledgement(reply_text):
            # A simple "cool" or "thanks" keeps the conversation available;
            # it does not provoke another answer or consume a reviewed action.
            self.attention.open();return
        # Unknown speakers never reach this callback, and therefore cannot stop
        # a response, update conversation state, or submit text to the brain.
        # With the app open, the request runs in the app's chat like a typed one, so in-app actions
        # (logging, saving, opening things) happen and their result shows on screen (2026-10-31).
        if not self.actions.has_pending():
            try:
                from core.voice_listener.calm_state import hand_to_app
                if hand_to_app(reply_text):
                    self.stop_response();self.attention.open();return
            except Exception:pass
        self._answer(reply_text)
    def _answer(self,reply_text):
        from core.conversation_runtime.fluid_runtime_test import StreamingResponse
        self.stop_response()
        # Attention stripping preserves punctuation and removes a vocative even
        # at the end of the sentence, before the strict shared action parser.
        action_reply=self.actions.handle(reply_text)
        response_brain=SpokenActionReply(action_reply) if action_reply is not None else self.brain
        self.response=StreamingResponse(brain=response_brain,user_text=reply_text)
        self.response.start()
        self._reply_was_active=True
    def consider_ambient(self,text):
        """Owner speech not meant for ZAE: remember briefly; maybe offer help."""
        if self.ambient is None:return
        self.ambient.observe(text)
        try:
            from core.personal_memory.insights import learner
            learner().observe(text, source="ambient")  # transient ambient context is not a durable personal fact
        except Exception:pass
        if not self.ambient.settings.enabled:return
        with self._ambient_lock:self._ambient_turn+=1;turn=self._ambient_turn
        def judge():
            try:offer()
            except Exception:pass  # Denials and model failures stay silent.
        def offer():
            decision=self.judge.decide(text,self.ambient.recent(),self.ambient.activity_summary())
            if decision['action']=='note' and decision.get('reason'):self.ambient.note_need(text,decision['reason'])
            if decision['action']=='direct':
                # No wake word: the brain judged this was meant for ZAE, so it
                # is a normal turn (actions still need spoken review + confirm).
                with self._ambient_lock:
                    if turn!=self._ambient_turn or self.collecting:return
                    from core.conversation.conversation_state import activate_conversation,record_user_speech
                    self.identity.authorize();self.ambient.unobserve(text)
                    activate_conversation();record_user_speech(signals=[])
                    self.attention.open();self._answer(text)
                return
            if decision['action']!='respond':return
            with self._ambient_lock:
                # Anything newer (a request, more speech) wins over a stale offer.
                if turn!=self._ambient_turn or self.collecting or self.actions.has_pending():return
                if self.response is not None and not self.response.finished_event.is_set():return
                from core.conversation_runtime.fluid_runtime_test import StreamingResponse
                self.identity.authorize('chat.reply')
                self.ambient.offer_for=text
                self.response=StreamingResponse(brain=self.brain,user_text=text)
                self.response.start();self._reply_was_active=True
        self._start_ambient(judge)
    def _start_ambient(self,judge):
        threading.Thread(target=judge,name='zaenia-ambient',daemon=True).start()
    def deliver_followthrough(self,now=None):
        """Claim one opted-in inbox announcement while idle; never run its worker."""
        now=time.monotonic() if now is None else now
        if now<self.next_followthrough_check:return False
        if self.collecting or self.actions.has_pending():return False
        if self.response is not None and not self.response.finished_event.is_set():return False
        self.next_followthrough_check=now+15.0
        try:
            self.identity.authorize('chat.reply')
            self.identity.authorize('notifications.read')
            self.identity.authorize('calendar.read')
            self.identity.authorize('tasks.read')
            if self.followthrough is None:
                from core.assistant_followthrough import FollowThroughService
                self.followthrough=FollowThroughService()
            inbox=self.followthrough.list_notifications()
            settings=inbox.get('settings',{})
            if settings.get('enabled') is not True or settings.get('spoken') is not True or inbox.get('quiet') is not False:
                return False
            for notification in inbox.get('notifications',[]):
                if notification.get('canSpeak') is not True:continue
                self.identity.authorize('notifications.write')
                claim=self.followthrough.claim_delivery(notification['id'],channel='speech')
                if claim.get('claimed') is not True:continue
                # Recheck revocation after the durable cross-device claim.
                self.identity.authorize('chat.reply')
                self.identity.authorize('notifications.read')
                self.identity.authorize('calendar.read')
                self.identity.authorize('tasks.read')
                if self.collecting or (self.response is not None and not self.response.finished_event.is_set()):
                    return False
                from core.conversation_runtime.fluid_runtime_test import StreamingResponse
                text='Reminder. '+str(notification['message'])
                self.response=StreamingResponse(brain=SpokenActionReply(text),user_text='Local follow-through announcement')
                self.response.start();return True
        except Exception:
            # Scoped denials and unavailable storage remain silent. No source
            # snapshots, notification content, or credential data are logged.
            return False
        return False
    def state(self):
        # For the UI heartbeat only; never used for authorization.
        response=self.response
        if response is not None and not response.finished_event.is_set():return 'replying'
        if self._reply_was_active:
            self._reply_was_active=False;self.attention.open()
        return 'hearing' if self.collecting else 'listening'
    def stop_response(self):
        self._reply_was_active=False
        if self.response is not None:self.response.interrupt();self.response=None
    def clear(self):
        self.audio=[];self.prefix.clear();self.collecting=False;self.detector.reset()
    def feed(self,pcm):
        events=self.detector.feed_pcm16(pcm)
        for event in events:
            if event['type']=='speech_start' and not self.collecting:
                self.collecting=True;self.audio=list(self.prefix)
        if self.collecting:self.audio.append(pcm)
        else:self.prefix.append(pcm)
        if sum(map(len,self.audio))>640000:
            self.identity.gate.audit('turn_too_long');self.clear();return
        if any(e['type']=='speech_end' for e in events) and self.collecting:
            audio=b''.join(self.audio);self.audio=[];self.collecting=False;self.prefix.clear()
            self.identity.authorize()
            # Still "hearing" while the clip is checked and transcribed, so the app mic waits for this
            # sentence instead of answering it too (Grey heard two replies at once, 2026-10-31).
            heartbeat=getattr(self,'heartbeat',None)
            if heartbeat is not None:
                try:heartbeat.report('hearing',force=True)
                except Exception:pass
            self._turn_audio=audio
            self.pipeline.process(audio,microphone_identity())
            # Track whether the owner's voice is being recognised, so the app
            # can keep its own mic on when PC Voice keeps rejecting him.
            verified=self.pipeline.last_verified
            if verified is True:self.voice_misses=0;self.voice_verified_once=True
            elif verified is False:self.voice_misses=getattr(self,'voice_misses',0)+1
    def close(self):
        if self.ambient is not None:self.ambient.clear()
        if self.activity is not None:self.activity.clear()
        self.attention.close();self.actions.clear();self.stop_response();self.clear();self.identity.close()

def run():
    import sounddevice as sd
    from core.voice_listener.service_status import Heartbeat
    identity=OwnerIdentity();runtime=None;heartbeat=Heartbeat()
    try:
        runtime=SecureRuntime(identity)
        microphone=identity.mic
        pending=queue.Queue(maxsize=128);gap=threading.Event()
        def callback(indata,frames,time_info,status):
            if status:gap.set();return
            try:pending.put_nowait(bytes(indata))
            except queue.Full:gap.set()
        print('ZÆNIA verified voice: approved microphone, local Vosk/ECAPA/Piper. Local actions require spoken review and a new verified confirmation.')
        settings=runtime.ambient.settings
        if settings.enabled and not settings.require_name:
            print('No wake word: just talk. ZAE decides what is meant for her, answers it, and may offer help when it is clearly useful. Ctrl+C stops voice.')
        else:
            print('Address ZAE anywhere in a request, or say “hey assistant”. Continue naturally for 30 seconds after her reply. Ctrl+C stops voice.')
        heartbeat.report('listening',force=True);runtime.heartbeat=heartbeat
        with sd.RawInputStream(samplerate=16000,blocksize=runtime.detector.frame_samples,device=microphone[0],
                               dtype='int16',channels=1,callback=callback) as stream:
            checked=0.0
            while True:
                now=time.monotonic()
                if now-checked>=.5:
                    if not stream.active or microphone_identity()!=microphone:
                        raise RuntimeError('Approved microphone disconnected or changed. Voice stopped; no fallback.')
                    identity.authorize();checked=now
                    heartbeat.report(runtime.state(),recognising=getattr(runtime,'voice_misses',0)<3)
                    runtime.deliver_followthrough(now)
                    runtime.sample_activity(now)
                if gap.is_set():
                    runtime.clear()
                    while True:
                        try:pending.get_nowait()
                        except queue.Empty:break
                    gap.clear();identity.gate.audit('audio_gap')
                try:runtime.feed(pending.get(timeout=.05))
                except queue.Empty:pass
    finally:
        heartbeat.report('off',force=True)
        if runtime is not None:runtime.close()
        else:identity.close()

def confirm():
    """One live acceptance test: real owner and a different speaker, RAM only."""
    import sounddevice as sd
    from core.foundation.auth.speaker_calibration import run_calibration
    from core.voice_security.calibrate import main as calibrate
    from core.conversation_runtime.partial_transcriber import PartialTranscriber
    from core.voice_listener.cognitive_filter import contains_attention_call
    from core.voice_security.identity import CALIBRATION_FILE
    from core.foundation.storage.paths import SPEAKER_PROFILE_FILE
    import yaml
    if not SPEAKER_PROFILE_FILE.exists() or not CALIBRATION_FILE.exists() or not (yaml.safe_load(CALIBRATION_FILE.read_text()) or {}).get('profile_cipher_digest'):
        calibrate()
    identity=OwnerIdentity()
    try:
        transcriber=PartialTranscriber(sample_rate=16000)
        accepted=[]
        def transcribe(pcm):
            transcriber.reset();parts=[]
            for i in range(0,len(pcm),16000):
                r=transcriber.feed(pcm[i:i+16000])
                if r['type']=='final' and r['text']:parts.append(r['text'])
            parts.append(transcriber.finalize());return ' '.join(parts).strip()
        pipeline=VerifiedPipeline(identity.gate,transcribe,accepted.append)
        for expected,prompt in [(True,'Zack: say “Zay, this is Zack testing my microphone” for about four seconds.'),
                                 (False,'Different speaker: say a full sentence for about four seconds. Use another person or a recording of another person; do not use silence.')]:
            input(prompt+' Press Enter when ready. ')
            before=microphone_identity()
            frames=sd.rec(4*16000,samplerate=16000,channels=1,dtype='int16',device=identity.mic[0])
            sd.wait();after=microphone_identity()
            if before!=identity.mic or after!=identity.mic:raise RuntimeError('Microphone changed during confirmation.')
            pcm=frames.astype('<i2').tobytes()
            # Prevent silence from falsely satisfying the unknown-speaker test.
            import numpy as np
            if float(np.sqrt(np.mean((frames.astype(np.float32)/32768.0)**2)))<.008:
                raise RuntimeError('Live clip too quiet; repeat the combined confirmation.')
            started=time.monotonic()
            if expected:
                ok=pipeline.process(pcm,after)
            else:
                proof=identity.gate.verify(pcm,after)
                ok=proof is not None
                if proof is not None:identity.gate.consume(proof,pcm,after)
            elapsed=time.monotonic()-started
            if ok!=expected:raise RuntimeError('Live speaker acceptance/rejection failed; recalibration is required.')
            print('Owner accepted.' if expected else 'Different speaker rejected before transcription.')
            print(f'Processing after capture: {elapsed:.2f}s. No subsecond latency claim is made.')
        if not accepted or not contains_attention_call(accepted[0]):
            raise RuntimeError('Owner was verified, but the wake call was not recognized. Adjust wake aliases before live use.')
        identity.authorize()
        print('PASS: live owner accepted, wake call recognized, different speaker rejected. No tools or real reminders executed.')
    finally:identity.close()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','confirm'])
    try:
        command=parser.parse_args().command
        confirm() if command=='confirm' else run()
    except KeyboardInterrupt:print('Voice stopped.')
