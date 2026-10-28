import json, ssl, sys, time, urllib.request, http.cookiejar
PW=open('/home/claude/run/adminpw').read().strip()
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj))
B='https://127.0.0.1/admin/'
def call(api, body=None, raw=None):
    h={'Content-Type':'application/json'}
    data=json.dumps(body).encode() if body is not None else None
    if raw is not None: data=raw; h={'Content-Type':'application/octet-stream','X-Otp-Restore':'1'}
    req=urllib.request.Request(B+'?api='+api, data=data, headers=h)
    try:
        with op.open(req, timeout=120) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        t=e.read()
        try: return json.loads(t)
        except Exception: return {'http': e.code, 'text': t[:200]}
    except Exception as e: return {'err': str(e)}
print('login', call('login', {'name':'admin','password':PW}).get('ok', '?'))
if sys.argv[1]=='upload':
    d=call('upgrade-package', raw=open(sys.argv[2],'rb').read())
    print('upload:', d.get('message') or d.get('error') or d)
    print('ready:', d.get('ready'), d.get('not_ready'))
elif sys.argv[1]=='start':
    d=call('upgrade', {'action':'start'}); print('start:', d.get('message') or d.get('error'))
    t0=time.time()
    while time.time()-t0<600:
        d=call('upgrade')
        p=(d or {}).get('plan') or {}
        line=' | '.join('%s:%s(%s)'%(s['name'],s.get('state'),(s.get('said') or '')[:60]) for s in p.get('steps',[]))
        print('%4ds %s %s'%(time.time()-t0, p.get('state'), line or d.get('err') or d.get('error') or ''))
        if p.get('state') in ('done','failed','cancelled'): break
        time.sleep(5)
    print('nodes:', [(n['name'], n.get('version'), (n.get('maintenance') or {}).get('on')) for n in d.get('nodes',[])])
elif sys.argv[1]=='maint':
    d=call('upgrade', {'action':'maintenance','node':sys.argv[2],'on':sys.argv[3]=='on','why':'test'}); print(d.get('message') or d.get('error'))
elif sys.argv[1]=='view':
    d=call('upgrade'); d.pop('log',None); print(json.dumps(d, indent=1, default=str)[:3000])
