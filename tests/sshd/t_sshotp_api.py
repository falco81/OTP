# SSH tokens of their own (1.0.181): made on the page (the QR once), listed without
# the secret, sealed, a second one refused unless in its place, removed; full
# administrators only. Usage (as root): python3 t_sshotp_api.py VERSION
import os, sys, json, time, re, subprocess, urllib.request, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.181'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-sshotp-')
os.makedirs(D + '/run')
API, RAD = 30993, 36950
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RAD, 'radius_acct_port': RAD + 1,
           'api_port': API, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-173!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def call(path, body=None, sess=None, extra=None, client='127.0.0.1'):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': client}
    if sess:
        h['X-Otp-Session'] = sess
    h.update(extra or {})
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-173!'})[1]['token']
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'jan', 'note': 'Jan, the admin'}, S)
m = x.get('made') or {}
ok('made (%s): a QR and the secret, shown once' % c, c == 200 and m.get('qr', '').startswith('data:image') and len(m.get('secret', '')) > 20, x)
sec = m.get('secret', '').replace(' ', '')
ok('... listed, without the secret', [t['name'] for t in x.get('sshotp') or []] == ['jan'] and sec not in json.dumps(x.get('sshotp')))
ok('... kept sealed', sec and sec not in json.dumps(st.db.rows('SELECT * FROM meta')))
c, x = call('/api/sshd', None, S)
ok('the page reads it again: no secret, no QR', 'jan' in json.dumps(x.get('sshotp')) and sec not in json.dumps(x) and 'made' not in x)
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'jan'}, S)
ok('a second for jan: refused (%s)' % c, c == 400)
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'jan', 'replace': True}, S)
ok('in its place: a new secret', c == 200 and (x.get('made') or {}).get('secret', '').replace(' ', '') != sec)
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'jan smith'}, S)
ok('a name that is not an account: refused (%s)' % c, c == 400)
K2 = call('/api/sshd', {'action': 'sshotp_add', 'name': 'eva'}, S)[1]['made']['secret'].replace(' ', '')
got = otp.sshotp_check(st, 'eva', otp.totp(__import__('base64').b32decode(K2), time.time()))
ok('a code checks', got[0], got)
c, x = call('/api/sshd', {'action': 'sshotp_remove', 'name': 'jan'}, S)
ok('removed', c == 200 and [t['name'] for t in x.get('sshotp') or []] == ['eva'])
ev = json.dumps(call('/api/events?limit=30', None, S)[1])
ev = json.dumps(st.db.rows("SELECT words FROM events WHERE kind = 'settings'"))
ok('made, made anew and removed: events', 'made an SSH token for jan' in ev and 'made a new SSH token for jan' in ev and 'removed the SSH token of jan' in ev, ev[:400])
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'petr', 'kind': 'sms', 'dest': '+420777123456'}, S)
ok('by SMS while SMS is not set up: refused (%s)' % c, c == 400, x)
call('/api/settings', {'settings': {'sms_mode': 'spool', 'sms_spool_dir': '/tmp'}}, S)
time.sleep(2)
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'petr', 'kind': 'sms', 'dest': 'not a number'}, S)
ok('by SMS to something not a number: refused (%s)' % c, c == 400, x)
c, x = call('/api/sshd', {'action': 'sshotp_add', 'name': 'petr', 'kind': 'sms', 'dest': '+420777123456'}, S)
m = x.get('made') or {}
ok('by SMS: made, no QR, the number masked (%s)' % c, c == 200 and m.get('kind') == 'sms' and 'qr' not in m and '777123' not in json.dumps(x), x)
ok('... the channels the page offers', 'sms' in (x.get('channels') or []))
print('ALL %d / %d' % (sum(R), len(R)))
