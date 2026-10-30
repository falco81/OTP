# Alerts by mail and the report (1.0.162), end to end: two daemons (node1,
# node2) over one SQLite database as a shared cluster, a mail sink keeping
# each mail. The alerts looked at every 3 s (OTP_ALERTS_EVERY).
# Usage (as root): python3 t_alerts.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, glob, email, signal
from email import policy

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.163'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = tempfile.mkdtemp(prefix='otp-alerts-')
SINK = TOP + '/mail'
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 33810 + 10 * i,
               'radius_acct_port': 33811 + 10 * i, 'api_port': 29990 + i, 'node_name': name,
               'ha_mode': 'shared'}, open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 29990 + i,
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
sink = subprocess.Popen([sys.executable, HERE + '/mailsink.py', '32925', SINK])
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
SET = lambda node, d: call(node, '/api/settings', {'settings': d}, S)
c, x = SET('node1', {'mail_mode': 'smtp', 'smtp_host': '127.0.0.1', 'smtp_port': 32925,
                     'smtp_security': 'none', 'smtp_auth': 'none', 'mail_from': 'otp@example.cz',
                     'mail_lang': 'en', 'alerts_disk_pct': 1, 'alerts_delay_min': 0,
                     'alerts_to': 'admin@example.cz, boss@example.cz'})
ok('mail and the alerts set: %s %s' % (c, x.get('error', '')), c == 200)
c, x = SET('node1', {'alerts_to': 'not an address'})
ok('a wrong address refused: %s' % c, c == 400)
ok('alerts are off by default', not otp.DEFAULTS['alerts'] and not otp.DEFAULTS['report'])
v = until(lambda: (lambda x: x if any(p['key'].startswith('disk:') for p in x.get('problems', [])) else None)(
    call('node1', '/api/alerts', None, S)[1]), 30)
ok('the problems seen: a disk fuller than 1 %% on both nodes (%s)' % [p['key'] for p in (v or {}).get('problems', [])],
   v and {p['node'] for p in v['problems'] if p['key'].startswith('disk:')} == {'node1', 'node2'})
time.sleep(8)
ok('nothing mailed while the alerts are off', not mails())
SET('node1', {'alerts': 1})
got = until(lambda: mails(), 30)
time.sleep(8)
m = mails()
ok('switched on: one mail (%s)' % [x['subject'] for x in m], len(m) == 1 and '[otp]' in m[0]['subject'])
ok('... to both addresses, in HTML', m and 'boss@example.cz' in m[0]['to'] and 'running out of room' in m[0]['html'])
time.sleep(6)
ok('... and not again', len(mails()) == 1)
# A node gone: node1 tells.
procs['node2'].send_signal(signal.SIGKILL); procs['node2'].wait()
got = until(lambda: [x for x in mails() if 'node2 is not heard from' in x['html']], 90)
ok('node2 gone: mailed by node1', got)
ok('... in one mail (%d mails in all)' % len(mails()), len([x for x in mails() if 'node2 is not heard from' in x['html']]) == 1)
start('node2')
got = until(lambda: [x for x in mails() if 'Back to normal' in x['subject'] or ('Over' in x['html'] and 'node2' in x['html'])], 90)
ok('node2 back: said it is over (%s)' % subjects()[-1:], got)
# The other way round: node1 gone, node2 tells.
n0 = len(mails())
procs['node1'].send_signal(signal.SIGKILL); procs['node1'].wait()
got = until(lambda: [x for x in mails()[n0:] if 'node1 is not heard from' in x['html']], 90)
ok('node1 gone: mailed by node2, which sends now', got)
start('node1')
time.sleep(10)
TOK['node1'] = open(N['node1']['dir'] + '/run/api-token').read().strip()
_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-162!'})
S = a['token']
until(lambda: [x for x in mails()[n0:] if 'Back to normal' in x['subject'] or 'Over' in x['html']], 90)
# A test, the report.
c, x = call('node1', '/api/alerts', {'action': 'test'}, S)
ok('a test alert: %s %s' % (c, x.get('message')), c == 200 and until(lambda: [y for y in mails() if 'A test alert' in y['subject']], 20))
SET('node1', {'alerts_lang': 'cs', 'report_lang': 'en'})
c, x = call('node1', '/api/alerts', {'action': 'test'}, S)
ok('the alerts in Czech: %s' % c, c == 200 and until(lambda: [y for y in mails() if 'Zkušební upozornění' in y['subject']], 20))
c, x = call('node1', '/api/alerts', {'action': 'preview', 'period': 'last'}, S)
c2, x2 = call('node1', '/api/alerts', {'action': 'preview', 'period': 'now'}, S)
h = (x.get('html') or '') + (x2.get('html') or '')
ok('the report looked at, in English as asked: %s' % x.get('subject'), c == 200 and 'Weekly report' in (x.get('subject') or ''))
ok('... who was refused and why', 'novak' in h and 'svoboda' in h and 'wrong code' in h)
ok('... the sign-ins by day, the servers', 'Sign-ins by day' in h and 'The servers' in h)
c, x = call('node1', '/api/alerts', {'action': 'report', 'period': 'last'}, S)
ok('the report sent: %s' % c, c == 200 and until(lambda: [y for y in mails() if 'report' in y['subject']], 20))
n1 = len([y for y in mails() if 'report' in y['subject']])
SET('node1', {'report': 1, 'report_every': 'daily', 'report_at': '00:00'})
time.sleep(25)
n2 = len([y for y in mails() if 'report' in y['subject']])
ok('the daily report due: sent once by the two nodes (%d)' % (n2 - n1), n2 - n1 == 1)
v = call('node1', '/api/alerts', None, S)[1]
ok('the mails sent are listed', len(v.get('log') or []) >= 5 and any(e['kind'] == 'report' for e in v['log']))
ev = json.dumps(call('node1', '/api/events?limit=200', None, S)[1])
ok('the test and the report are in the events', 'sent a test alert' in ev and 'sent the report' in ev)
print('ALL %d / %d' % (sum(R), len(R)))
