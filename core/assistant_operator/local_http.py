"""Loopback model transport never uses an ambient proxy or follows redirects."""
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        raise PermissionError('Local model redirects are blocked.')

def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
