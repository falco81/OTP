"""t_fix.py - 1.0.296 hunt: the RADIUS counters counted under a lock, once the answer is decided
(never taken back); the periodic report given back when its mail did not go, tried again in 30 min.
The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.296'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r296_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx296', 'api_port': 29996}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
                  OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', TOP + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.sealing_key(make=True)


class Daemon(object):
    def __init__(self, store, dirs):
        self.store, self.dirs, self.read = store, dirs, 0

    def reader(self):
        self.read += 1
        return self.store

    def changed(self, *a):
        pass


class H(object):
    """A request: the parts of the handler the routes use."""
    def __init__(self, store, d, sess=None, body=None, args=None):
        self.store, self.d, self._s, self._body, self.args = store, d, sess, body or {}, args or {}
        self.headers = {}
        self.route_path = ''

    arg = m.ApiHandler.arg if hasattr(m, 'ApiHandler') else None


Handler = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, 'directory_recheck'))
for k in ('arg', 'num', 'me', 'directory_recheck', 'end_all', 'body'):
    if k != 'body':
        setattr(H, k, getattr(Handler, k))
H.DIR_CHECKED, H.DIR_CHECK_S = {}, 600
H.body = lambda self: self._body
H.session = lambda self, kind: dict(self._s) if self._s else None
H.reader = property(lambda self: self.d.reader())
H.client_ip = lambda self: '192.0.2.1'


def api(fn, h):
    try:
        return fn(h), None
    except m.ApiError as e:
        return None, e


import threading, collections

# ==== 1. the RADIUS counters ========================================================================
rs = object.__new__(m.RadiusServer)
rs.counts = collections.Counter()
rs.counts_lock = threading.Lock()
rs.bound, rs.trouble, rs.rcvbuf = [], '', {}
rs.jobs = rs.acct_jobs = type('Q', (), {'qsize': lambda self: 0})()
stop = []
errs = []


def reader():
    while not stop:
        try:
            rs.state()
        except Exception as e:
            errs.append(repr(e))
            return


def bump(k):
    for i in range(20000):
        rs.count(k)
        if i % 500 == 0:
            rs.count('new_%s_%d' % (k, i))      # new keys while state() reads


ts = [threading.Thread(target=bump, args=(k,)) for k in ('packets', 'packets', 'accept', 'reject')] + [threading.Thread(target=reader)]
for t in ts:
    t.start()
for t in ts[:-1]:
    t.join()
stop.append(1)
ts[-1].join()
c = rs.state()['counts']
ok('1 four threads counting: none lost', c['packets'] == 40000 and c['accept'] == 20000 and c['reject'] == 20000, dict((k, v) for k, v in c.items() if not k.startswith('new')))
ok('1 read while counted: no "changed size" error', not errs, errs[:2])
src = open(TOP + '/otp.py').read()
body = src[src.index('class RadiusServer'):src.index('class RadiusServer') + 200000]
ok('1 no counter is taken back, none counted outside the lock',
   "self.counts['accept'] -= 1" not in body and body.count('self.counts[') == 1)
ok('1 accept/challenge/reject counted once, after the answer is built',
   "self.count({ACCESS_ACCEPT: 'accept', ACCESS_CHALLENGE: 'challenge'}.get(code, 'reject'))" in body and
   "self.counts['accept'] += 1" not in body)

# ==== 2. the report given back ======================================================================
m.CONFIG.update(report=True, alerts=False, snmp=False)
m.health_publish = lambda d: None
m.logs_start = lambda d: None
m.alerts_lead = lambda s: True
m.alerts_evaluate = lambda s, *a, **k: {'now': []}
m.report_due = lambda now=None: True
m.report_period = lambda now=None: (1000.0, 2000.0, 'P-1')
sent = []
answer = {'ok': False, 'said': 'mail is off', 'queued': ''}
m.report_send = lambda store, since=None, until=None, to=None, by='', reader=None: (sent.append(1), dict(answer))[1]


class D(object):
    store = st

    def reader(self):
        return st


def tick():
    m.ALERT_WORK['at'] = -1e9
    m.alerts_tick(D())
    for _ in range(100):
        time.sleep(0.05)
        if not m.ALERT_WORK['busy']:
            break


st.set_meta('report:sent', 'P-0')
tick()
ok('2 a report whose mail did not go: tried', len(sent) == 1, sent)
ok('2 ...the period given back (sent again later)', st.get_meta('report:sent') == 'P-0', st.get_meta('report:sent'))
tick()
ok('2 ...not again within 30 min', len(sent) == 1, sent)
m.ALERT_WORK['report_fail'] = time.monotonic() - 1801
answer = {'ok': False, 'said': 'waiting', 'queued': 'waiting'}
tick()
ok('2 30 min later: tried again; waiting in the outgoing mail counts as sent',
   len(sent) == 2 and st.get_meta('report:sent') == 'P-1', (sent, st.get_meta('report:sent')))
st.set_meta('report:sent', 'P-0')
m.ALERT_WORK['report_fail'] = None
answer = {'ok': True}
tick()
ok('2 sent: kept as sent, as before', len(sent) == 3 and st.get_meta('report:sent') == 'P-1')
tick()
ok('2 ...not sent twice', len(sent) == 3)

print('ALL %d / %d' % (sum(R), len(R)))
