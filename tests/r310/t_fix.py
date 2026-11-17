"""t_fix.py - 1.0.310: a node's own upgrade rows sent to the other node's database again while an upgrade
runs; a node forgotten while it still beats in its own database keeps its maintenance and upgrade row.
The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.310'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r310_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx310', 'api_port': 29940}, open(D + '/config.json', 'w'))
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


# ==== 1 the rows sent again
me = m.node_name()
sent = []
m._peer_update = lambda k, v: sent.append(k) or True
m.CONFIG['ha_mode'] = 'replicated'
st.set_meta('upgrade:node:' + me, json.dumps({'id': 'p1', 'state': 'done'}))
st.set_meta('maint:' + me, json.dumps({'on': False}))
m.UPG_RESENT[0] = -1e9
m.upgrade_resend_mine(st, {'state': 'running', 'id': 'p1'})
ok('1 a plan running: this node\'s step and maintenance written to the other node again', sorted(sent) == sorted(['upgrade:node:' + me, 'maint:' + me]), sent)
sent[:] = []
m.upgrade_resend_mine(st, {'state': 'running', 'id': 'p1'})
ok('1 ...every 30 s, not every tick', sent == [])
m.UPG_RESENT[0] = -1e9
m.upgrade_resend_mine(st, {'state': 'done', 'id': 'p1'})
ok('1 a plan done: nothing more', sent == [])
m.CONFIG['ha_mode'] = ''
m.UPG_RESENT[0] = -1e9
m.upgrade_resend_mine(st, {'state': 'running', 'id': 'p1'})
ok('1 not a replicated pair: nothing', sent == [])

# ==== 2 forgetting a node that still beats in its own database
for beats, keep in ((True, True), (False, False)):
    st.set_meta('node:nb', json.dumps({'at': time.time() - 9999, 'name': 'nb'}))
    st.set_meta('maint:nb', json.dumps({'on': True, 'why': 'kept out on purpose'}))
    st.set_meta('upgrade:node:nb', json.dumps({'id': 'p1', 'state': 'installing'}))
    m._peer_alive_there = lambda name, b=beats: b
    m.ha_forget(st, 'nb')
    kept = st.get_meta('maint:nb') is not None and st.get_meta('upgrade:node:nb') is not None
    ok('2 %s: its maintenance and upgrade row %s' % ('beating in its own database' if beats else 'gone indeed',
                                                     'kept' if keep else 'dropped, as before'), kept == keep)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
