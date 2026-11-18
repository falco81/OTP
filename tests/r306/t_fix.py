"""t_fix.py - 1.0.306: an alert or report that some recipients took is sent (not mailed again every
15-30 min to everybody); the report's "Who was refused" counts refusals, not the challenges of a
sign-in in two windows; SNMP's clock values and the last backup's time kept in an Integer32.
The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.306'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r306_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx306', 'api_port': 29936}, open(D + '/config.json', 'w'))
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


# ==== 1 an alert some recipients took
import email.message


def deliver_partly(store, msg, to, **kw):
    e = m.MailError('550 no such user', permanent=True)
    e.left = [to[-1]]
    e.queued = 'failed'
    raise e


def deliver_none(store, msg, to, **kw):
    e = m.MailError('550 no such user', permanent=True)
    e.left = list(to)
    e.queued = 'failed'
    raise e


m.alerts_lead = lambda store: True
msg = email.message.EmailMessage()
msg['Subject'] = 'x'
m.mail_deliver = deliver_partly
e1 = m.alert_send(st, msg, ['ops@corp.cz', 'gone@corp.cz'], 'alert', ['k'])
ok('1 one of two recipients took it: sent (not again in 15 min), the other said', e1['ok'] is True and 'gone@corp.cz' in e1.get('said', '')
   and not json.loads(st.get_meta('alerts:state')).get('fail_at'), e1)
m.mail_deliver = deliver_none
e2 = m.alert_send(st, msg, ['ops@corp.cz', 'gone@corp.cz'], 'alert', ['k'])
ok('1 nobody took it: not sent, as before', e2['ok'] is False, e2)

# ==== 2 the report's "Who was refused"
now = time.time()
for i, (who, res) in enumerate([('ann', 'challenge'), ('ann', 'accept'), ('ann', 'challenge'), ('ann', 'accept'),
                                ('bob', 'reject'), ('bob', 'reject'), ('cid', 'drop')]):
    st.db.run("INSERT INTO radius_log (ts, packet, username, result, reason, node) VALUES (?, 'Access-Request', ?, ?, ?, 'n1')",
              (now - 3600 + i, who, res, {'challenge': 'the code is asked for in a second window', 'reject': 'wrong code',
                                          'accept': '', 'drop': 'no client'}[res]))
subject, html, text = m.report_build(st, now - 86400, now + 60, 'en')
t = '\n'.join(text) if isinstance(text, list) else str(text)
ok('2 a user who signed in through a challenge twice: not "refused"', '- ann:' not in t, t[-600:])
ok('2 refused (reject, drop): listed, with why', '- bob: 2 (wrong code)' in t and '- cid: 1' in t, t[-600:])

# ==== 3 SNMP: Integer32
m.clock_state_here = lambda: {'engaged': True, 'mode': 'guard', 'ref': 86400 * 90.0, 'skew': -86400 * 365.0, 'correction': 86400 * 30.0}
rows = m.snmp_mib_clock(None, st, True)
vals = [v for o, k, v in rows if k == 'int']
ok('3 a clock 90 days, a year off: within an Integer32', all(-2 ** 31 <= v <= 2 ** 31 - 1 for v in vals) and 2 ** 31 - 1 in vals and -2 ** 31 in vals, vals)
ok('3 ...small values as before (ms)', m._sn_i32(1.234 * 1000) == 1234)
ok('3 the last backup\'s time after 2038: within an Integer32', m._sn_i32(2 ** 31 + 5) == 2 ** 31 - 1)
# ==== 4 RADIUS: a late refusal kept for a repeat when it is scheduled
import inspect
src = inspect.getsource(m.RadiusServer.access) if hasattr(m, 'RadiusServer') else ''
if not src:
    src = open(m.__file__).read()
i = src.find('reply.late_until = time.time()')
j = src.find('self.later(min(delay, 10000)', i)
ok('4 the late refusal is remembered (with its time) before it is put off', i > 0 and 'remember(bytes(reply), reply.late_until)' in src[i:j], src[i:j][:300])
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
