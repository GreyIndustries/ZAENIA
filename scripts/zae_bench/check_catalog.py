"""Validate historical task provenance without executing any model or generated code."""
import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
def validate():
    data=json.loads(Path(__file__).with_name('catalog.json').read_text())
    for task in data['tasks']:
        actual=subprocess.check_output(['git','-C',str(root),'rev-parse',task['commit']+'^'],text=True).strip()
        if actual!=task['parent']:raise ValueError('Wrong parent: '+task['id'])
        if not task['files']:raise ValueError('No source files: '+task['id'])
    return {'tasks':len(data['tasks']),'provenanceValidated':True,'modelRuns':0,'successRate':None,'nextGate':'Review acceptance cases and held-out tests, then run the local coding loop in its approved safe copy.'}
if __name__=='__main__':print(json.dumps(validate(),indent=2))
