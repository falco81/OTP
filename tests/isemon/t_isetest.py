# isemon's test sign-in (1.0.178): one daemon sending to a UDP receiver here;
# Send a test line (otp, as before) and a test sign-in (totp.cgi, a name given,
# Failure), a name not allowed refused. Usage (as root): python3 t_isetest.py VERSION
import os, sys, json, time, socket, subprocess, urllib.request, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.178'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-isetest-')
os.makedirs(D + '/run')
API, RAD, ISE = 30995, 36930, 36940
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx.bind(('127.0.0.1', ISE))
rx.settimeout(1)
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RAD, 'radius_acct_port': RAD + 1,
           'api_port': API, 'node_name': 'otp1', 'isemon': 1, 'isemon_targets': '127.0.0.1:%d/udp' % ISE},
          open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-178!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def drain():
    got = []
    while True:
        try:
            got.append(rx.recv(9000).decode())
        except socket.timeout:
            return got


def ask(body):
    c, x = call('/api/isemon', body, S)
    if c != 200:
        return c, x
    for _ in range(30):
        time.sleep(0.5)
        c2, r = call('/api/isemon', {'action': 'result', 'id': x.get('id')}, S)
        if (r.get('nodes') or {}).get('otp1'):
            return c2, r['nodes']['otp1']
    return 0, {}


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-178!'})[1]['token']
drain()
c, r = ask({'action': 'test'})
lines = drain()
ok('a test line: went (%s)' % c, r.get('ok'), r)
ok('... as otp, isemon reads nothing of it', any(' otp[' in l and 'isemon reads nothing' in l for l in lines), lines)
c, r = ask({'action': 'test', 'as_user': 'jan.test', 'ok': False})
lines = drain()
ok('a test sign-in: went', r.get('ok'), r)
t = [l for l in lines if ' totp.cgi[' in l]
ok('... totpcgi\'s own line: Failure, the name, PAM_SM_AUTH, a rid, said a test', t and
   'totp.cgi[' in t[0] and ': Failure: user=jan.test, mode=PAM_SM_AUTH, host=127.0.0.1, rid=otp-test-otp1-' in t[0]
   and 'not a real sign-in' in t[0], lines)
ok('... not into the node\'s files', not os.path.exists(D + '/totp.cgi.log') or 'jan.test' not in open(D + '/totp.cgi.log').read())
c, r = ask({'action': 'test', 'as_user': 'jan'})
t = [l for l in drain() if ' totp.cgi[' in l]
ok('Success by default', t and ': Success: user=jan,' in t[0], t)
c, x = call('/api/isemon', {'action': 'test', 'as_user': 'jan, x=y'}, S)
ok('a name with a comma: refused (%s)' % c, c == 400)
print('ALL %d / %d' % (sum(R), len(R)))
