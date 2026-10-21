"""Fixed Blender commands; originals and the user's running editor are preserved."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def operate(path,output,args):
    base=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Blender Foundation'
    choices=sorted(base.glob('Blender*/blender.exe'),reverse=True)
    if not choices: raise ValueError('Blender is not installed in the supported location.')
    with tempfile.TemporaryDirectory(prefix='zae-blender-') as folder:
        folder=Path(folder); receipt=folder/'receipt.json'; job=folder/'job.json'
        # Save to a private intermediate file, then publish exclusively after verification.
        temporary=folder/'edited.blend'
        spec={'receipt':str(receipt)}
        if output: spec.update(output=str(temporary),objectName=args['objectName'],location=args['location'])
        job.write_text(json.dumps(spec),encoding='utf-8')
        def run(scene):
            subprocess.run([str(choices[0]),'--background','--factory-startup','--disable-autoexec',str(scene),
                '--python-exit-code','5','--python',str(Path(__file__).with_name('blender_worker.py')),'--',str(job)],
                check=True,timeout=90,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        original=hashlib.sha256(path.read_bytes()).hexdigest()
        run(path)
        if output:
            job.write_text(json.dumps({'receipt':str(receipt)}),encoding='utf-8')
            run(temporary) # Independent reopen, with automatic scripts still disabled.
        result=json.loads(receipt.read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=original: raise ValueError('Source scene changed during the operation.')
        if output:
            obj=next((x for x in result['objects'] if x['name']==args['objectName']),None)
            if not obj or any(abs(a-b)>1e-4 for a,b in zip(obj['location'],args['location'])): raise ValueError('Blender object transform did not verify.')
            from .tools import write_new
            result.update(write_new(output,temporary.read_bytes()))
        return {**result,'verified':True,'source':str(path),'text':json.dumps(result['objects'])[:24000]}
