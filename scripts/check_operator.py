"""Opt-in live checks using synthetic data only. No owner pixels or daily apps.

Default: local fixture mission. --web retrieves public Python docs; --model
summarizes synthetic evidence and recognizes a generated test image. --blender
starts only an isolated background Blender process with a generated scene.
"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import time
from unittest.mock import patch
from core.assistant_platform.jobs import JobManager
from core.assistant_platform.service import PlatformService
from core.assistant_platform.store import PlatformStore,now_text


class Context:
    def check(self): pass
    def progress(self,*args,**kwargs): pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--web',action='store_true');parser.add_argument('--model',action='store_true');parser.add_argument('--blender',action='store_true');args=parser.parse_args()
    report={'checkedAt':now_text(),'scope':'Synthetic data and public sources only; no owner data, pixels or daily browser.','checks':[]}
    def check(name,work):
        begin=time.monotonic()
        try:
            result=work();report['checks'].append({'name':name,'ok':True,'seconds':round(time.monotonic()-begin,2),'evidence':result})
        except Exception as error: report['checks'].append({'name':name,'ok':False,'seconds':round(time.monotonic()-begin,2),'error':type(error).__name__+': '+str(error)[:250]})
        print(json.dumps(report['checks'][-1],ensure_ascii=True),flush=True)
    with ExitStack() as stack:
        root=Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='zae-operator-check-',dir=Path(__file__).resolve().parents[1])))
        stack.enter_context(patch('core.assistant_platform.store.protect_storage'))
        platform=PlatformService(PlatformStore(root/'private/store.sqlite3'),JobManager());operator=platform.operator
        work=root/'work';work.mkdir();grant=platform.store.put('operator_root',{'name':'Synthetic test outputs','path':str(work)})
        def mission():
            row=operator.create('Synthetic document mission',[{'tool':'document.create','args':{'rootId':grant['id'],'path':'check.docx','content':'ZAENIA synthetic verification: 42.'}},
                {'tool':'document.read','args':{'rootId':grant['id'],'path':'check.docx'}}])
            started=operator.start(row['id'],row['revision'],row['planHash'],lambda op:True)
            if not platform.jobs.settled[started['job']['id']].wait(20): raise TimeoutError('Mission did not settle.')
            final=platform.store.get('mission',row['id'])
            if final['status']!='completed':raise ValueError(final['status'])
            return {'status':final['status'],'steps':len(final['steps']),'allVerified':all(s['result']['verified'] for s in final['steps'])}
        check('real_docx_mission',mission)
        if args.web:
            from core.assistant_operator.web import read_page,research
            def direct():
                r=read_page('https://www.python.org/about/')
                return {k:r[k] for k in ('url','title','checkedAt','verified')}|{'characters':len(r['text'])}
            check('public_https_read',direct)
            def search():
                r=research('Python official documentation pathlib',Context());return {'sourceUrls':[s['url'] for s in r['sources']],'checkedAt':r['checkedAt']}
            check('public_research',search)
        if args.model:
            def summary():
                r=operator.tools.execute('evidence.summarize',{'sourceStep':0,'instruction':'State the measured value and cite the supplied source.'},Context(),[
                    {'text':'The synthetic measured value is 42.','url':'https://example.com/synthetic-fixture','checkedAt':now_text()}])
                if '42' not in r['text']: raise ValueError('The summary lost the supplied measurement.')
                return {'answer':r['text'],'modelGenerated':True,'independentClaimVerification':False}
            check('local_evidence_summary',summary)
            def draft():
                job=operator.draft('Synthetic public-source plan','Read https://docs.python.org/3/library/pathlib.html and summarize the page. Use web.read followed by evidence.summarize. No files or app actions.',lambda op:True,priority=True)
                if not platform.jobs.settled[job['id']].wait(180): raise TimeoutError('Local planner timed out.')
                saved=platform.store.get('job',job['id'])
                if saved['status']!='completed': raise ValueError(saved.get('detail') or saved['status'])
                mission=platform.store.get('mission',saved['result']['missionId'])
                if [s['tool'] for s in mission['plan']]!=['web.read','evidence.summarize']:raise ValueError('The proposed draft omitted a requested operation.')
                return {'status':mission['status'],'priority':mission['priority'],'tools':[s['tool'] for s in mission['plan']],'executed':False}
            check('local_controlled_mission_draft',draft)
            def vision():
                from PIL import Image,ImageDraw,ImageFont
                from core.assistant_operator.screen import Screen
                frame=Image.new('RGB',(600,250),'white');draw=ImageDraw.Draw(frame)
                draw.text((30,50),'ZAENIA TEST: 42',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',42),fill='black')
                screen=Screen();window={'handle':1,'pid':1,'created':1,'title':'Generated synthetic fixture','process':'fixture.exe'}
                with patch('core.assistant_operator.screen.windows',return_value=[window]),patch('PIL.ImageGrab.grab',return_value=frame):
                    grant=screen.grant(1);r=screen.inspect(grant['id'],'What number is printed in this generated test image?')
                if '42' not in r['text']: raise ValueError('The vision model did not recognize the synthetic number.')
                return {'answer':r['text'],'rawImageSaved':r['imageSaved'],'actualOwnerScreenCaptured':False}
            check('local_synthetic_vision',vision)
        if args.blender:
            def blend():
                base=Path('C:/Program Files/Blender Foundation');executable=sorted(base.glob('Blender*/blender.exe'),reverse=True)[0]
                script=root/'make_fixture.py';scene=work/'fixture.blend'
                script.write_text('import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.ops.mesh.primitive_cube_add()\nbpy.context.object.name="FixtureCube"\nbpy.ops.wm.save_as_mainfile(filepath='+repr(str(scene))+')\n',encoding='utf-8')
                subprocess.run([str(executable),'--background','--factory-startup','--disable-autoexec','--python-exit-code','5','--python',str(script)],check=True,timeout=90,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                result=operator.tools.execute('blender.move_copy',{'rootId':grant['id'],'path':'fixture.blend','output':'moved.blend','objectName':'FixtureCube','location':[1.,2.,3.]},Context(),[])
                return {'verified':result['verified'],'objects':result['objects'],'originalPreserved':scene.exists(),'outputBytes':result['bytes']}
            check('isolated_blender_copy_edit',blend)
    destination=Path(__file__).resolve().parents[1]/'docs/operator-live-check.json'
    destination.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    if any(not item['ok'] for item in report['checks']):raise SystemExit(1)

if __name__=='__main__':main()
