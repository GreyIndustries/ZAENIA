"""Simulated audio/security tests, independent of live models and microphones."""
from array import array
import math
from core.voice_security.gate import IdentityGate,VerifiedPipeline,VoiceProof,validate_calibration

def run():
    checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    pcm=array('h',(int(6000*math.sin(i*.15)) for i in range(48000))).tobytes()
    generation=['original'];mic=('locked mic',1);events=[];calls=[];clock=[1.0]
    gate=IdentityGate(lambda b:.9,.7,mic,lambda:generation[0],events.append,lambda:clock[0])
    pipeline=VerifiedPipeline(gate,lambda b:calls.append('stt') or 'Zay test',lambda t:calls.append(t))
    check(pipeline.process(pcm,mic));check(calls==['stt','Zay test'])
    proof=gate.verify(pcm,mic);check(proof is not None)
    check(not gate.consume(True,pcm,mic))
    check(not gate.consume(VoiceProof(proof.token),pcm,mic))
    proof=gate.verify(pcm,mic);check(gate.consume(proof,pcm,mic));check(not gate.consume(proof,pcm,mic))
    proof=gate.verify(pcm,mic);check(not gate.consume(proof,pcm+b'\0\0',mic))
    proof=gate.verify(pcm,mic);clock[0]+=16;check(not gate.consume(proof,pcm,mic))
    proof=gate.verify(pcm,mic);generation[0]='changed';check(not gate.consume(proof,pcm,mic))
    check(gate.verify(pcm,mic) is None);generation[0]='original'
    check(gate.verify(pcm,('other mic',2)) is None)
    for bad in [b'',b'\0'*32000,b'a',pcm[:100],pcm*8]:check(gate.verify(bad,mic) is None)
    check(gate.verify(pcm,mic,48000) is None)
    for score in [.4,float('nan'),float('inf')]:
        rejected=IdentityGate(lambda b:score,.7,mic,lambda:'baseline',events.append)
        skipped=[];p=VerifiedPipeline(rejected,lambda b:skipped.append('stt') or 'text',skipped.append)
        check(not p.process(pcm,mic));check(skipped==[])
    mixed_scores=iter([.9,.2,.9,.9])
    mixed=IdentityGate(lambda b:next(mixed_scores),.7,mic,lambda:'baseline',events.append)
    skipped=[];check(not VerifiedPipeline(mixed,lambda b:skipped.append('stt') or 'text',skipped.append).process(pcm,mic));check(skipped==[])
    def broken(b):raise RuntimeError('model failed')
    failed=IdentityGate(broken,.7,mic,lambda:'baseline',events.append)
    check(failed.verify(pcm,mic) is None)
    check('verification_failed' in events)
    gate.revoke();check(gate.verify(pcm,mic) is None)
    gate=IdentityGate(lambda b:.9,.7,mic,lambda:generation[0],events.append)
    def revoke_in_stt(b):generation[0]='revoked while transcribing';return 'Zay'
    deliveries=[]
    check(not VerifiedPipeline(gate,revoke_in_stt,deliveries.append).process(pcm,mic));check(deliveries==[])
    generation[0]='original'
    def failed_stt(b):raise RuntimeError('transcriber failed')
    gate=IdentityGate(lambda b:.9,.7,mic,lambda:generation[0],events.append)
    check(not VerifiedPipeline(gate,failed_stt,deliveries.append).process(pcm,mic))
    check(not gate._proofs)
    check(not any('Zay' in reason for reason in events))
    for threshold in [-.1,0,2,float('nan'),True]:
        try:IdentityGate(lambda b:.9,threshold,mic,lambda:1)
        except ValueError:check(True)
        else:raise AssertionError('Invalid threshold accepted')
    import copy
    good={'profile_id':'owner','profile_cipher_digest':'cipher','threshold':.7,'minimum_required_gap':.05,
          'observed':{'genuine_min':.9,'impostor_max':.4,'genuine_sample_count':3,'impostor_sample_count':2}}
    check(validate_calibration(good,'owner','cipher')==.7)
    for key,value in [('profile_id','other'),('profile_cipher_digest','old'),('threshold',.3),('threshold',float('nan')),('minimum_required_gap',0),('minimum_required_gap','bad')]:
        bad=copy.deepcopy(good);bad[key]=value
        try:validate_calibration(bad,'owner','cipher')
        except ValueError:check(True)
        else:raise AssertionError('Invalid calibration accepted')
    for key,value in [('genuine_min',float('nan')),('impostor_max',float('inf')),('genuine_sample_count',1),('impostor_sample_count',True)]:
        bad=copy.deepcopy(good);bad['observed'][key]=value
        try:validate_calibration(bad,'owner','cipher')
        except ValueError:check(True)
        else:raise AssertionError('Invalid observation accepted')
    print(f'PASS: {checks} isolated voice checks. Scorers and transcripts are simulated; live acceptance and latency remain unverified.')

if __name__=='__main__':run()
