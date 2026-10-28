import json, urllib.request, os
class D:
    def __init__(s, port, run, user, pw):
        s.base='http://127.0.0.1:%d'%port; s.tok=open(os.path.join(run,'api-token')).read().strip(); s.sess=''
        r=s.call('/api/auth/login', {'name':user,'password':pw}); s.sess=r.get('token','')
        assert s.sess, r
    def call(s, path, body=None, raw=None, ctype='application/json'):
        h={'X-Otp-Token':s.tok,'X-Otp-Session':s.sess,'X-Otp-Client':'127.0.0.1'}
        data=None
        if body is not None: data=json.dumps(body).encode(); h['Content-Type']='application/json'
        if raw is not None: data=raw; h['Content-Type']='application/octet-stream'
        req=urllib.request.Request(s.base+path, data=data, headers=h, method='POST' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                b=r.read()
                return json.loads(b) if r.headers.get('Content-Type','').startswith('application/json') else b
        except urllib.error.HTTPError as e:
            t=e.read()
            try: return json.loads(t)
            except Exception: return {'http':e.code,'text':t[:300]}
