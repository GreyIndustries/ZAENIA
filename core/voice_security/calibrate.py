"""One protected calibration commit; resume a saved result without new recordings."""
from pathlib import Path
from core.voice_security.identity import digest,CALIBRATION_FILE
from core.voice_security.gate import validate_calibration
from core.foundation.storage.paths import SPEAKER_PROFILE_FILE


def bind_existing():
    import yaml
    from core.foundation.auth.speaker_calibration import save_calibration
    if not CALIBRATION_FILE.exists() or not SPEAKER_PROFILE_FILE.exists():
        raise RuntimeError('No saved calibration/profile to resume. Run calibration normally.')
    before=digest(SPEAKER_PROFILE_FILE)
    saved_digest=digest(CALIBRATION_FILE)
    # Re-enrollment is a new ciphertext and must not reuse an older calibration.
    if CALIBRATION_FILE.stat().st_mtime < SPEAKER_PROFILE_FILE.stat().st_mtime:
        raise RuntimeError('Calibration predates the profile; record a fresh calibration.')
    results=yaml.safe_load(CALIBRATION_FILE.read_text(encoding='utf-8'))
    if not isinstance(results,dict):raise ValueError('Invalid saved calibration.')
    current=results.get('profile_cipher_digest')
    if current is not None and current!=before:
        raise RuntimeError('Saved calibration belongs to another profile; recalibrate.')
    results['profile_cipher_digest']=before
    validate_calibration(results,'zaenia-zack-speaker-profile',before)
    if digest(CALIBRATION_FILE)!=saved_digest or digest(SPEAKER_PROFILE_FILE)!=before:
        raise PermissionError('Calibration/profile changed while preparing the binding.')
    if current==before:
        print('Calibration is already bound to this profile.');return
    print('Reusing the saved calibration; no new recordings required.')
    print('Use the SAME Module 1 passkey for both prompts: owner session, then exact change approval.')
    save_calibration(results)
    if digest(SPEAKER_PROFILE_FILE)!=before:
        raise PermissionError('Profile changed during approval. Run a fresh calibration before voice use.')
    print('Saved calibration is now bound to the current encrypted profile.')


def main():
    from core.foundation.auth.speaker_profile import enroll_speaker_profile
    from core.foundation.auth.speaker_calibration import run_calibration,save_calibration
    if not SPEAKER_PROFILE_FILE.exists():enroll_speaker_profile()
    before=digest(SPEAKER_PROFILE_FILE)
    def persist(results):
        if digest(SPEAKER_PROFILE_FILE)!=before:raise PermissionError('Profile changed during calibration.')
        draft=dict(results);draft['profile_cipher_digest']=before
        validate_calibration(draft,'zaenia-zack-speaker-profile',before)
        path=save_calibration(draft)
        if digest(SPEAKER_PROFILE_FILE)!=before:raise PermissionError('Profile changed during commit.')
        return path
    if not run_calibration(persist=persist):raise RuntimeError('Live calibration did not pass.')
    print('Calibration and profile binding saved together. No raw recordings saved.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--bind-existing',action='store_true')
    args=parser.parse_args();bind_existing() if args.bind_existing else main()
