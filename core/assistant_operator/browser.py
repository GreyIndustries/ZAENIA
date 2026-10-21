"""Separate, ephemeral browser for public reading and reviewed form preparation.

All page requests use the pinned public-HTTPS fetcher. JavaScript, downloads,
service workers and non-GET requests are blocked. No daily-browser cookies.
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import re
from .web import fetch_bytes, public_url


class Browser:
    def __init__(self):
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='zae-browser')
        self.playwright=None; self.browser=None; self.page=None; self.origin=None

    def run(self,tool,args):
        # Calls must stay on the same worker because Playwright objects have thread affinity.
        return self.worker.submit(self._run,tool,args).result(timeout=50)

    def _route(self,route):
        request=route.request
        try:
            if request.method!='GET' or urlsplit(request.url).hostname!=self.origin: return route.abort()
            actual,kind,data=fetch_bytes(request.url)
            if urlsplit(actual).hostname!=self.origin: return route.abort()
            route.fulfill(status=200,content_type=kind,body=data,headers={
                'Content-Security-Policy':"default-src 'self'; script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; connect-src 'none'"})
        except Exception: route.abort()

    def _run(self,tool,args):
        if tool=='browser.close':
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
            self.browser=self.page=self.playwright=None
            return {'verified':True,'text':'The ZAE browser was closed.'}
        if tool=='browser.open':
            normalized,host,_=public_url(args['url'])
            if self.page is None or self.page.is_closed():
                from playwright.sync_api import sync_playwright
                if self.playwright: self.playwright.stop()
                self.playwright=sync_playwright().start()
                self.browser=self.playwright.chromium.launch(channel='msedge',headless=False,chromium_sandbox=True)
                ctx=self.browser.new_context(java_script_enabled=False,service_workers='block',accept_downloads=False)
                ctx.route('**/*',self._route); self.page=ctx.new_page(); self.page.set_default_timeout(10000)
            self.origin=host
            self.page.goto(normalized,wait_until='domcontentloaded',timeout=25000)
        if self.page is None or self.page.is_closed(): raise ValueError('Open a public page in the ZAE browser first.')
        if tool=='browser.fill':
            if re.search(r'password|passkey|credential|token|secret|payment|card.?number|security.?code|one.?time|social.?security',args['label'],re.I):
                raise PermissionError('Credential, payment and sensitive identity fields are blocked.')
            element=self.page.get_by_label(args['label'],exact=True)
            if element.count()!=1: raise ValueError('The field label must identify exactly one field.')
            kind=element.get_attribute('type') or 'text'
            if kind not in {'text','search','url','email','tel'} or element.get_attribute('autocomplete') in {'current-password','new-password','one-time-code','cc-number'}:
                raise PermissionError('Only ordinary text fields may be prepared; credentials and payment fields are blocked.')
            element.fill(args['value'])
            if element.input_value()!=args['value']: raise ValueError('Field readback did not match.')
            return {'verified':True,'url':self.page.url,'field':args['label'],'text':'Field prepared and checked. Nothing was submitted.'}
        return {'verified':True,'url':self.page.url,'title':self.page.title(),
                'text':self.page.locator('body').inner_text()[:24000],
                'mode':'Public reader; JavaScript, cross-site resources, downloads and form submission disabled.'}
