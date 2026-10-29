import json, sys, urllib.request
tok = open('/run/otp/api-token').read().strip(); B = 'http://127.0.0.1:9861'; S = ['']
def call(path, body=None):
    h = {'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1', 'X-Otp-Token': tok}
    if S[0]: h['X-Otp-Session'] = S[0]
    req = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=300) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'http': e.code, 'text': e.read()[:400]}
L = call('/api/auth/login', {'name': 'admin', 'password': 'Install-Admin-Pw-2026'}); print({k: v for k, v in L.items() if k != 'session'}); S[0] = L.get('session') or L.get('token', '')
x = call('/api/upgrade', {'action': 'downgrade_list'}); print(str(x)[:300]); d = x['downgrade']
print('list:', [(v['version'], 'ok' if not v['why'] else 'no') for v in d['versions']], 'floor', d['floor'], d['root_floor'])
r = call('/api/upgrade', {'action': 'downgrade_get', 'version': '1.0.141'})
print('get 1.0.141:', r.get('message') or r, '| package', (r.get('package') or {}).get('version'), (r.get('package') or {}).get('downgrade'), '| ready', r.get('ready'), r.get('not_ready'))
r = call('/api/upgrade', {'action': 'downgrade_get', 'version': '1.0.137'})
print('get 1.0.137:', r)
r = call('/api/upgrade', {'action': 'forget'}); print('forget:', r.get('message'))
