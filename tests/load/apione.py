import sys, json, time, ssl, urllib.request, http.cookiejar
PW=open('/home/claude/run/adminpw').read().strip()
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(a, body=None):
    req=urllib.request.Request('https://127.0.0.1/admin/?api='+a, data=json.dumps(body).encode() if body else None, headers={'Content-Type':'application/json'})
    with op.open(req, timeout=120) as r: return r.read()
call('login',{'name':'admin','password':PW})
for p in sys.argv[1:]:
    t=time.time(); n=len(call(p)); print('%-40s %6d B %6.0f ms'%(p,n,(time.time()-t)*1000), flush=True)
