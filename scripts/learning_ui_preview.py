"""Disposable synthetic insights for checking confirm, correct and reject controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import uvicorn

def main():
    from core.personal_memory.insights import InsightStore
    from scripts.assistant_ui_preview import main as preview
    with TemporaryDirectory(prefix='zae-learning-preview-',dir=Path(__file__).resolve().parents[1]) as folder:
        store=InsightStore(Path(folder)/'insights.json')
        store.merge([{'text':'Sample user prefers concise practical answers','kind':'working_style','evidence':'I prefer concise practical answers'},
                     {'text':'Sample user enjoys astronomy references','kind':'interest','evidence':'I enjoy astronomy references'}])
        original=uvicorn.run
        def serve(app,**kwargs):
            kwargs['port']=8878; original(app,**kwargs)
        with patch('core.personal_memory.insights.InsightStore',return_value=store),patch('uvicorn.run',serve):preview()

if __name__=='__main__':main()
