"""Read-only installed-service acceptance checks, using only a synthetic photo."""
import base64
import json
from pathlib import Path
import urllib.request
from core.api.desktop_key import _stored


def main():
    key = _stored()
    if not key: raise RuntimeError('The installed desktop app must be paired first.')
    def read(path, body=None):
        request=urllib.request.Request('http://127.0.0.1:8766'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-ZAENIA-DESKTOP-KEY':key,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=180) as response:
            return response.read(300000)
    status=json.loads(read('/api/platform/scripture/status'))
    passage=json.loads(read('/api/platform/scripture?reference=Genesis%201%3A1'))
    library=json.loads(read('/api/platform/knowledge'))
    image=base64.b64encode((Path(__file__).resolve().parents[1]/'docs/photo-test.png').read_bytes()).decode()
    events=[json.loads(line) for line in read('/api/chat/stream',{
        'message':'In one sentence, name the two shapes and their colors.',
        'requestId':'installed-photo-check','images':[image]}).splitlines()]
    last=events[-1]
    assert status['books']==66 and passage['words']
    assert last['type']=='done' and last['route']=='photo' and not last['interrupted'],last
    assert all(word in last['reply'].lower() for word in ('red','blue','square','circle')),last
    print(json.dumps({'bibleBooks':status['books'],'hebrewWordsVerified':len(passage['words']),
                      'learningLibraryReady':isinstance(library['sources'],list),
                      'photoAnalysis':last['reply']},ensure_ascii=False))


if __name__=='__main__':main()
