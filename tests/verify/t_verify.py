# A backup tried without putting it back (1.0.169): made to a folder, fetched,
# opened, read through, the tokens tried against the key; then a damaged one
# and the wrong password. Usage (as root): python3 t_verify.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, glob

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.168'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-vf-'); os.makedirs(D + '/run'); os.makedirs(D + '/dest')
APORT = 30491
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36110, 'radius_acct_port': 36111,
           'api_port': APORT, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-169!', must_change=0)
tk = otp.Tokens(st)
for i in range(12):
    tk.enroll('user%d@x.cz' % i, 'test')
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


def job():
    end = time.time() + 120
    while time.time() < end:
        j = call('/api/rbackup', {'action': 'job'}, S)[1]['job']
        if not j.get('running'):
            return j
        time.sleep(0.5)
    return {}


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-169!'})[1]['token']
SET = lambda dd: call('/api/settings', {'settings': dd}, S)
c, x = SET({'rbackup_password': 'Backup-Pass-169-xyz'})
ok('the password of the backups: %s %s' % (c, x.get('error', '')), c == 200)
c, x = call('/api/rbackup', {'action': 'save', 'target': {'kind': 'folder', 'name': 'here', 'path': D + '/dest', 'enabled': 1}}, S)
ok('a folder as the destination: %s %s' % (c, x.get('error', '')), c == 200)
c, x = call('/api/rbackup', {'action': 'run'}, S)
j = job()
ok('a backup made: %s' % (j.get('error') or 'ok'), not j.get('error') and glob.glob(D + '/dest/otp-backup-*.enc'))
c, x = call('/api/rbackup', {'action': 'verify'}, S)
ok('tried: %s %s' % (c, x.get('message')), c == 200)
j = job()
v = j.get('result') or {}
ok('... it can be put back: %s' % [(k['what'][:30], k['ok'], k['said'][:30]) for k in v.get('checks', [])], v.get('ok') and len(v['checks']) >= 6)
ok('... the 12 tokens counted and tried against the key', any('12 of 12' in k['said'] for k in v['checks']) and
   any(k['what'].startswith('the tokens open') and k['ok'] for k in v['checks']))
ok('... nothing was put back: the database as it was', len(st.db.rows('SELECT id FROM tokens')) == 12)
c, x = call('/api/rbackup', None, S)
ok('the page has the try (%s)' % len(x.get('verified', [])), x.get('verified') and x['verified'][0]['ok'])
# Damaged.
f = sorted(glob.glob(D + '/dest/otp-backup-*.enc'))[-1]
raw = bytearray(open(f, 'rb').read()); raw[len(raw) // 2] ^= 0xFF; open(f, 'wb').write(bytes(raw))
call('/api/rbackup', {'action': 'verify'}, S)
j = job()
v = j.get('result') or {}
ok('a damaged backup: not good (%s)' % [(k['what'][:40], k['said'][:50]) for k in v.get('checks', []) if not k['ok']], not v.get('ok') and j.get('error'))
ev = json.dumps(call('/api/events?limit=50', None, S)[1])
ok('... written down as NOT GOOD', 'NOT GOOD' in ev)
SET({'alerts_delay_min': 0})
c, a = call('/api/alerts', {'action': 'check'}, S)
ok('... and the alerts say so (%s)' % [p['key'] for p in a.get('problems', [])], any(p['key'].startswith('rbverify:') for p in a.get('problems', [])))
# A good one again, then the wrong password.
call('/api/rbackup', {'action': 'run'}, S); job()
SET({'rbackup_password': 'Another-Pass-169-abc'})
call('/api/rbackup', {'action': 'verify'}, S)
j = job()
v = j.get('result') or {}
ok('the wrong password: not good (%s)' % [k['said'][:60] for k in v.get('checks', []) if not k['ok']], not v.get('ok') and any('password' in k['said'] for k in v['checks'] if not k['ok']))
# After every backup.
SET({'rbackup_password': 'Backup-Pass-169-xyz', 'rbackup_verify': 'after'})
time.sleep(1.5)
n0 = len(call('/api/rbackup', None, S)[1].get('verified', []))
call('/api/rbackup', {'action': 'run'}, S)
j = job()
x = call('/api/rbackup', None, S)[1]
ok('after every backup: the one just sent tried (%d -> %d, %s)' % (n0, len(x['verified']), x['verified'][0].get('file') == (j.get('result') or {}).get('file')),
   len(x['verified']) == n0 + 1 and x['verified'][0]['ok'] and x['verified'][0]['file'] == j['result']['file'])
c, a = call('/api/alerts', {'action': 'check'}, S)
ok('... the alert over (%s)' % [p['key'] for p in a.get('problems', [])], not any(p['key'].startswith('rbverify:') for p in a.get('problems', [])))
print('ALL %d / %d' % (sum(R), len(R)))
