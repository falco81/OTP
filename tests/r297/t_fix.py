"""t_fix.py - 1.0.297 hunt: the portal's "Another address or way" while replacing keeps the proof of
the old token (back to choosing the way); without a token being replaced, as before. The parts
loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.297'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r297_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx297', 'api_port': 29997}, open(D + '/config.json', 'w'))
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


# ==== 1 the portal cancel
SET = []
m.portal_me = lambda h: h._s
m.portal_state = lambda h, s: {'data': dict(s['data'])}


def _set(h, s, **kw):
    SET.append(kw)
    for k, v in kw.items():
        if v is None:
            s['data'].pop(k, None)
        else:
            s['data'][k] = v


m.portal_data_set = _set
d = Daemon(st, None)
s = {'name': 'u1', 'data': {'verify': {'addr': 'a@b.c'}, 'may_replace': True, 'may_replace2': True, 'old': 'x'}}
r, e = api(m._portal_cancel, H(st, d, s))
ok('1 replacing, the address given up: back to choosing the way', e is None and r and 'verify' not in r['me']['data'], e)
ok('1 ...the proof of the old token kept', r and r['me']['data'].get('may_replace') is True and r['me']['data'].get('may_replace2') is True
   and r['me']['data'].get('old') == 'x', r)
SET[:] = []
s = {'name': 'u1', 'data': {'may_replace': True, 'old': 'x'}}
r, e = api(m._portal_cancel, H(st, d, s))
ok('1 choosing a new way given up: all of it forgotten, as before', e is None and SET and SET[0] == {'verify': None, 'may_replace': None, 'may_replace2': None, 'old': None}, SET)
SET[:] = []
s = {'name': 'u1', 'data': {'verify': {'addr': 'a@b.c'}}}
r, e = api(m._portal_cancel, H(st, d, s))
ok('1 an address being checked (no replacing): given up, as before', e is None and SET and SET[0].get('may_replace', 0) is None, SET)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
