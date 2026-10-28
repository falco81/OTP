import json, sys, urllib.request
TOK = open('/run/otp/api-token').read().strip()
def call(path, body=None, sess=None):
    req = urllib.request.Request('http://127.0.0.1:9861' + path, data=json.dumps(body).encode() if body is not None else None,
        headers={'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1', **({'X-Otp-Session': sess} if sess else {})},
        method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=300) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e: return {'HTTP': e.code, **json.loads(e.read() or b'{}')}
S = call('/api/auth/login', {'name': 'admin', 'password': 'Admin-Pass-123'})['token']
