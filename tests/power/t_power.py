# Restarts that keep the service (1.0.165): two daemons over one SQLite database
# as a shared cluster, no root helper (a restart asked of it never comes).
# Usage (as root): python3 t_power.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, glob, email, signal
from email import policy

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.163'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = tempfile.mkdtemp(prefix='otp-power-')
SINK = TOP + '/mail'
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 35810 + 10 * i,
               'radius_acct_port': 35811 + 10 * i, 'api_port': 31990 + i, 'node_name': name,
               'ha_mode': 'shared'}, open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 31990 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1', OTP_ALERTS_EVERY='3')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-162!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
# Sign-ins of a week, for the report.
now = time.time()
for i in range(40):
    st.db.run("INSERT INTO radius_log (ts, client, packet, username, result, reason) VALUES (?, ?, ?, ?, ?, ?)",
              (now - 3600 * (i * 3 + 1), 'vpn1', 'Access-Request', 'novak' if i % 3 else 'svoboda',
               'reject' if i % 4 == 0 else 'accept', 'wrong code' if i % 4 == 0 else ''))
sink = subprocess.Popen(['sleep', '1'])
procs = {}


def start(name):
    procs[name] = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=N[name]['env'],
                                   stdout=open(N[name]['dir'] + '/d.out', 'a'), stderr=subprocess.STDOUT)


for name in N:
    start(name)
atexit.register(lambda: ([p.terminate() for p in procs.values()], sink.terminate()))
time.sleep(7)
TOK = {n: open(N[n]['dir'] + '/run/api-token').read().strip() for n in N}


def call(node, path, body=None, sess=None):
    h = {'X-Otp-Token': TOK[node], 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % N[node]['api'] + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


def until(fn, secs=60):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(1)
    return None


def mails():
    out = []
    for f in sorted(glob.glob(SINK + '/*.eml')):
        m = email.message_from_string(open(f).read(), policy=policy.default)
        html = ''
        for part in m.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_content()
        out.append({'subject': str(m['Subject']), 'to': str(m['To']), 'html': html})
    return out


def subjects():
    return [m['subject'] for m in mails()]


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-162!'})
S = a['token']
ok('both nodes heard', until(lambda: all(n.get('alive') or n.get('me') for n in otp.ha_nodes(st)) and len(otp.ha_nodes(st)) == 2, 30))
# One after the other: the first does not come back (its root helper never answers) - the second stays up.
c, x = call('node1', '/api/power', {'how': 'reboot', 'targets': ['node1', 'node2'], 'order': 'rolling'}, S)
ok('a restart one after the other asked: %s %s' % (c, x.get('error', '')), c == 200)
pid = otp.power_plan(st).get('id')
row = lambda n: otp._meta_json(st, 'power:node:' + n) or {}
ok('node2 first: out of service, then failed (nothing restarts it here)', until(
    lambda: row('node2').get('id') == pid and row('node2').get('state') == 'failed', 90))
ok('... node1 not restarted after it: %s' % row('node1').get('said'), until(
    lambda: row('node1').get('id') == pid and row('node1').get('state') == 'failed' and 'did not restart' in (row('node1').get('said') or ''), 30))
ok('... and both in service again', until(lambda: not (otp._meta_json(st, 'maint:node1') or {}).get('on') and
                                          not (otp._meta_json(st, 'maint:node2') or {}).get('on'), 30))
ev = json.dumps(call('node1', '/api/events?limit=50', None, S)[1])
ok('... said in the events', 'node1 was not restarted: node2 did not come back' in ev)
st.set_meta('power:plan', json.dumps({}))
# The other node gone: a restart that keeps the service is refused.
procs['node2'].send_signal(signal.SIGKILL); procs['node2'].wait()
ok('node2 gone', until(lambda: not [n for n in otp.ha_nodes(st) if n['name'] == 'node2'][0]['alive'], 90))
c, x = call('node1', '/api/power', {'how': 'reboot', 'targets': ['node1', 'node2'], 'order': 'rolling'}, S)
ok('one after the other refused while only node1 answers: %s %s' % (c, x.get('error')), c == 400 and 'only node1 answers' in json.dumps(x))
try:
    otp.power_ask(st, 'reboot', ['node1'], 'one', 'test', keep_service=True)
    ok('a restart after an update refused too', False)
except ValueError as e:
    ok('a restart after an update refused too: %s' % e, 'would stop the service' in str(e))
print('ALL %d / %d' % (sum(R), len(R)))
