"""t_fix.py - 1.0.298 hunt: the weekly backup check not started with no destination switched on;
forgetting a check's row of another node by UPDATE only; SNMP's certificate end as an Integer32.
The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.298'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r298_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx298', 'api_port': 29998}, open(D + '/config.json', 'w'))
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


# ==== 1 the weekly check
m.CONFIG['rbackup_verify'] = 'weekly'
st.set_meta('rbackup:targets', json.dumps([{'id': 't1', 'enabled': False, 'kind': 'dir'}]))
ok('1 weekly, no destination switched on: not due', m.rb_verify_due(st) is False)
st.set_meta('rbackup:targets', json.dumps([{'id': 't1', 'enabled': True, 'kind': 'dir'}]))
ok('1 ...one switched on, never tried: due, as before', m.rb_verify_due(st) is True)
st.set_meta('rbackup:verified:' + m.node_name(), json.dumps([{'at': time.time() - 3600}]))
ok('1 ...tried an hour ago: not due, as before', m.rb_verify_due(st) is False)
st.set_meta('rbackup:verified:' + m.node_name(), json.dumps(['junk']))
ok('1 ...a row that is not a dict: due, no error', m.rb_verify_due(st) is True)
m.CONFIG['rbackup_verify'] = 'off'
ok('1 off: not due', m.rb_verify_due(st) is False)

# ==== 2 forgetting a check
now = time.time()
st.set_meta('rbackup:verified:' + m.node_name(), json.dumps([{'at': now}, {'at': now - 10}]))
st.set_meta('rbackup:verified:other1', json.dumps([{'at': now - 20}, {'at': now - 30}]))
SETK = []
_sm = st.set_meta
st.set_meta = lambda k, v, *a, **kw: (SETK.append(k), _sm(k, v, *a, **kw))[1]
n = m.rb_verified_forget(st, now - 20)
ok('2 another node\'s row: one taken off', n == 1 and len(json.loads(st.get_meta('rbackup:verified:other1'))) == 1, n)
ok('2 ...by UPDATE, not set_meta', 'rbackup:verified:other1' not in SETK, SETK)
n = m.rb_verified_forget(st, now)
ok('2 this node\'s row: by set_meta, as before', n == 1 and ('rbackup:verified:' + m.node_name()) in SETK, SETK)
n = m.rb_verified_forget(st)
ok('2 all forgotten', n == 2 and json.loads(st.get_meta('rbackup:verified:other1')) == [], n)
st.set_meta = _sm

# ==== 3 SNMP certificate end
END = {'a': 2 ** 33, 'b': 1700000000}
m.tls_targets = lambda store: ['a', 'b']
m.tls_profile = lambda store, t: {'info': {'not_after': END[t], 'cn': t}}


class Ag(object):
    started, engine, boots = time.monotonic(), b'x', 1


class Dm(object):
    store, radius, started = st, None, time.time()


rows = m.snmp_mib(Dm(), Ag())
B = m.SNMP_BASE
got = dict((o, v) for o, k, v in rows if o[:len(B) + 4] == B + (6, 1, 1, 5))
ok('3 a certificate ending after 2038: 2^31-1', got.get(B + (6, 1, 1, 5, 1)) == 2 ** 31 - 1, got)
ok('3 ...one before: as it is', got.get(B + (6, 1, 1, 5, 2)) == 1700000000, got)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
