"""t_fix.py - 1.0.309: the clock guard times its own work by a clock that is not stepped; the other node's
heartbeat read in its database judged by that machine's clock; keepalived's check takes no word dated
ahead; the sign-in pages' tidying never ends a RADIUS guard's block early. Parts over SQLite, and the
check script run with a file of its own.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.309'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r309_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx309', 'api_port': 29939}, open(D + '/config.json', 'w'))
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


# ==== 1 the clock guard: marks by the monotonic clock
src = open(TOP + '/otp.py').read()
ok('1 its writes and the directory timed by time.monotonic() when the time is not given',
   "mark = time.monotonic() if now is None else now" in src and "mark - CLOCK.get('written_mark', -1e12) > 10" in src
   and "mark - CLOCK.get('dir_mark', -1e12) > CLOCK_DIR_EVERY_S" in src)

# ==== 2 the other node's heartbeat by its machine's clock
class Far(object):
    engine = 'postgres'

    def __init__(self, now):
        self.n = now

    def value(self, q, a=()):
        if 'EXTRACT' in q:
            return self.n
        return json.dumps({'at': self.n - 30})

    def close(self):
        pass


m.PEER_THERE.clear()
m.CONFIG['ha_mode'] = 'replicated'
m.ha_peer_db = lambda: Far(time.time() - 200)       # its clock 200 s behind this node's, it beat 30 s ago by it
ok('2 the other node 200 s behind, beating: alive (it was "gone" by this node\'s clock)', m._peer_alive_there('nb') is True)
m.PEER_THERE.clear()
m.ha_peer_db = lambda: type('F', (Far,), {'value': lambda self, q, a=(): self.n if 'EXTRACT' in q else json.dumps({'at': self.n - 300})})(time.time())
ok('2 not beating for 5 min by its own clock: not alive', m._peer_alive_there('nb') is False)
m.CONFIG['ha_mode'] = ''

# ==== 3 the RADIUS guard's block not tidied away
d = Daemon(st, None)
import collections
d.login_fails = collections.defaultdict(list)
d.login_info = {}
t = time.time()
for i in range(20005):
    d.login_fails[('10.0.%d.%d' % (i // 250, i % 250), 'radius-src')] = [t - 7 * 3600]
blk = ('192.0.2.77', 'radius-src')
d.login_fails[blk] = [t - 7 * 3600]
d.login_info[blk] = {'blocked_until': t + 86400}
h = H(st, d, {'name': 'x', 'role': 'fulladmin'})
H.THROTTLE_TIDIED = [0.0]
H.THROTTLE_LOCK = Handler.THROTTLE_LOCK
try:
    Handler.throttle(h, 'admin', 5, 15, name='someone')
except Exception as e:                                  # noqa: BLE001
    pass
ok('3 the pages\' tidying: quiet places gone, a place blocked for a day kept', blk in d.login_fails and blk in d.login_info
   and len(d.login_fails) < 1000, len(d.login_fails))

# ==== 4 keepalived's check: a word dated ahead is no
import subprocess
VC = BUILD + '/out/otp-%s/deploy/otp-vip-check' % _OUTV
sh = open(VC).read().replace('/run/otp/vip-state', TOP + '/vip-state').replace('/var/lib/otp/otp.lock', TOP + '/nolock')
open(TOP + '/vc.sh', 'w').write(sh)
open(TOP + '/vip-state', 'w').write('ok prefer\n')
r1 = subprocess.run(['sh', TOP + '/vc.sh', 'ok']).returncode
os.utime(TOP + '/vip-state', (time.time() + 300, time.time() + 300))
r2 = subprocess.run(['sh', TOP + '/vc.sh', 'ok']).returncode
ok('4 a fresh word: yes; one dated 5 min ahead: no', r1 == 0 and r2 != 0, (r1, r2))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
