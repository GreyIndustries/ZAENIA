"""Bounded public HTTPS retrieval. DNS is checked AND the connection is pinned.

No ambient proxy, owner cookies, credentials, private IPs or automatic redirects.
Retrieved text is evidence, never an instruction or authorization.
"""
from __future__ import annotations
import http.client
import ipaddress
import socket
import ssl
import zlib
from urllib.parse import urlsplit, urljoin, urlunsplit
from html.parser import HTMLParser
from core.assistant_platform.store import now_text

LIMIT = 2_000_000


def public_url(url):
    if not isinstance(url, str) or len(url)>2000 or any(ord(c)<33 for c in url) or '\\' in url:
        raise ValueError('Use a public HTTPS URL without whitespace.')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None,443):
        raise ValueError('Only public HTTPS URLs on port 443 are supported.')
    host = parts.hostname.encode('idna').decode('ascii')
    if host.endswith('.') or host.lower() in {'localhost','localhost.localdomain'}: raise ValueError('Private hosts are blocked.')
    addresses = list({item[4][0] for item in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('Private, local, reserved and mixed public/private addresses are blocked.')
    return urlunsplit(('https',host,parts.path or '/',parts.query,'')),host,addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address,443),self.timeout)
        try: self.sock = self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException: raw.close(); raise


def fetch_bytes(url, *, redirects=4):
    for _ in range(redirects+1):
        normalized,host,addresses = public_url(url)
        parts = urlsplit(normalized)
        connection = PinnedHTTPS(host,addresses[0])
        try:
            connection.request('GET',parts.path+('?' + parts.query if parts.query else ''),headers={
                'User-Agent':'ZAENIA/1.0 (owner-requested research)','Accept-Encoding':'identity','Accept':'text/html,text/plain,application/json'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location: raise ValueError('Redirect without a destination.')
                url=urljoin(normalized,location)
                continue
            if not 200<=response.status<300: raise ValueError(f'Public source returned HTTP {response.status}.')
            encoding=response.getheader('Content-Encoding','identity').lower()
            if encoding not in ('identity','','gzip','deflate'): raise ValueError('Unsupported content compression.')
            if int(response.getheader('Content-Length','0'))>LIMIT: raise ValueError('Source exceeds 2 MB.')
            data=response.read(LIMIT+1)
            if len(data)>LIMIT: raise ValueError('Source exceeds 2 MB.')
            if encoding in {'gzip','deflate'}:
                decoder=zlib.decompressobj(16+zlib.MAX_WBITS if encoding=='gzip' else zlib.MAX_WBITS)
                data=decoder.decompress(data,LIMIT+1)
                if len(data)>LIMIT or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
                    raise ValueError('Expanded or concatenated source exceeds the bounded format.')
            return normalized,response.getheader('Content-Type','text/plain'),data
        finally: connection.close()
    raise ValueError('Too many redirects.')


class TextPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.hidden=0; self.title=False; self.heading=[]; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript','svg'}: self.hidden+=1
        if tag=='title': self.title=True
        if tag in {'p','div','br','li','h1','h2','tr'}: self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','svg'}: self.hidden=max(0,self.hidden-1)
        if tag=='title': self.title=False
    def handle_data(self,data):
        if self.title: self.heading.append(data)
        if not self.hidden: self.parts.append(data)


def read_page(url):
    actual,kind,data=fetch_bytes(url)
    if not any(item in kind.lower() for item in ('text/','application/json','application/xhtml')):
        raise ValueError('Choose a text or HTML source; use Documents for PDFs.')
    decoded=data.decode('utf-8',errors='replace')
    parser=TextPage(); parser.feed(decoded)
    content='\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())
    return {'verified':True,'url':actual,'title':''.join(parser.heading).strip()[:250] or actual,'checkedAt':now_text(),
            'text':content[:24000],'truncated':len(content)>24000,'sourceType':'public webpage'}


def research(query,context):
    from ddgs import DDGS
    context.progress('Searching public sources',detail='Sending only the reviewed search query; no owner history or cookies.')
    # Engine snippets are discovery hints; claims below come from fetched pages.
    found=DDGS(timeout=12).text(query,max_results=5)
    sources=[]; unavailable=[]
    for item in found:
        context.check()
        try:
            source=read_page(item['href']); source['text']=source['text'][:8000]
            sources.append(source)
        except Exception as error: unavailable.append({'url':str(item.get('href',''))[:2000],'reason':type(error).__name__})
        if len(sources)>=3: break
    if not sources: raise ValueError('No source pages could be verified. Try a direct public URL.')
    return {'verified':True,'query':query,'checkedAt':now_text(),'sources':sources,'unavailable':unavailable,
            'text':'\n\n'.join(f"[{n}] {s['title']}\n{s['url']}\nChecked {s['checkedAt']}\n{s['text'][:12000]}" for n,s in enumerate(sources,1))}
