# Prometheus (1.0.173): one daemon; /api/metrics as metrics.php asks it - off,
# without the token, a wrong one, from a network not let in, then the text:
# every line Prometheus' format, the families there, RADIUS counted.
# Usage (as root): python3 t_metrics.py VERSION
import os, sys, json, time, re, subprocess, urllib.request, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.173'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-metrics-')
os.makedirs(D + '/run')
API, RAD = 30891, 36910
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
st.client_save({'name': 'lo', 'address': '127.0.0.1', 'secret': 'radius-secret-173-long', 'enabled': 1})
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
c, x = call('/api/metrics', extra={'X-Otp-Metrics': 'x' * 30})
ok('off: 404 (%s)' % c, c == 404)
c, x = call('/api/settings', {'settings': {'metrics': 1}}, S)
ok('switched on (%s)' % c, c == 200, x)
c, x = call('/api/metrics', extra={'X-Otp-Metrics': 'x' * 30})
ok('no token set yet: 401 (%s)' % c, c == 401)
c, x = call('/api/metrics', {'action': 'token'}, S)
T = x.get('token') or ''
ok('a token made and shown once (%d characters)' % len(T), c == 200 and len(T) >= 32)
saved = json.dumps(st.db.rows('SELECT * FROM settings'))
ok('... kept sealed', T not in saved)
c, x = call('/api/settings', None, S)
shown = [s for s in x['settings'] if s['key'] == 'metrics_token'][0]
ok('... the pages see it masked', T not in json.dumps(shown) and shown.get('set'))
c, x = call('/api/metrics', extra={'X-Otp-Metrics': T[:-1] + ('a' if T[-1] != 'a' else 'b')})
ok('a wrong token: 401 (%s)' % c, c == 401)
c, x = call('/api/metrics')
ok('no token: 401 (%s)' % c, c == 401)
# RADIUS asked, to be counted.
for i in range(3):
    try:
        otp.radius_ask('127.0.0.1', RAD, 'radius-secret-173-long', 'nobody%d' % i, 'x', timeout=3, tries=1)
    except Exception:  # noqa: BLE001
        pass
time.sleep(1)
c, x = call('/api/metrics', extra={'X-Otp-Metrics': T})
text = x.get('text') or ''
ok('with the token: 200 and a text (%s, %d bytes)' % (c, len(text)), c == 200 and len(text) > 300)
bad = []
fams = set()
for line in text.rstrip('\n').split('\n'):
    if line.startswith('# HELP ') or line.startswith('# TYPE '):
        fams.add(line.split()[2])
        continue
    if not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{([a-zA-Z_][a-zA-Z0-9_]*="([^"\\\n]|\\.)*",?)*\})? -?[0-9.eE+-]+$', line):
        bad.append(line)
ok('every line in Prometheus\' text format', not bad, bad[:3])
for f in ('otp_info', 'otp_database_up', 'otp_radius_requests_total', 'otp_tokens', 'otp_clients',
          'otp_radius_listening', 'otp_alerts_open', 'otp_scrape_seconds', 'otp_high_security'):
    ok('... %s' % f, f in fams, sorted(fams))
m = re.search(r'otp_radius_requests_total\{kind="packets"\} (\d+)', text)
ok('RADIUS counted: %s packet(s)' % (m.group(1) if m else '?'), m and int(m.group(1)) >= 3)
ok('the version and node in otp_info', 'otp_info{engine="sqlite",node="otp1",site=' in text and 'version="%s"' % VER in text)
# Only from these networks.
call('/api/settings', {'settings': {'metrics_from': '10.0.5.0/24, 2001:db8::/64'}}, S)
c, x = call('/api/metrics', extra={'X-Otp-Metrics': T}, client='192.0.2.7')
ok('from a network not let in: 403 (%s)' % c, c == 403)
c, x = call('/api/metrics', extra={'X-Otp-Metrics': T}, client='10.0.5.9')
ok('from one let in: 200 (%s)' % c, c == 200)
c, x = call('/api/settings', {'settings': {'metrics_from': 'not a network'}}, S)
ok('a network that is not one: refused (%s)' % c, c == 400)
c, x = call('/api/metrics', {'action': 'preview'}, S)
ok('the page sees what it answers (%s)' % c, c == 200 and 'otp_info' in x.get('text', ''))
c, x = call('/api/metrics', {'action': 'preview'})
ok('... but not without signing in (%s)' % c, c in (401, 403))
ev = json.dumps(call('/api/events?limit=20', None, S)[1])
ok('a new token is an event', 'new token for Prometheus' in ev)
print('ALL %d / %d' % (sum(R), len(R)))
