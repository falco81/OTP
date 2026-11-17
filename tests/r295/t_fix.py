"""t_fix.py - 1.0.295 hunt: the database servers' rows of a node forgotten or no longer of the cluster
left out (and dropped with it); the meter's database row timed by this node's clock. The parts
loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.295'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r295_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx295', 'api_port': 29995}, open(D + '/config.json', 'w'))
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


# ==== 1. the rows of nodes there are ===============================================================
now = time.time()
me = m.node_name()
row = lambda n, ok_=True: json.dumps({'at': now, 'ok': ok_, 'host': '192.0.2.9', 'port': 9443})
st.set_meta('dbagent:node:' + me, row(me))
st.set_meta('dbagent:node:gone', row('gone', False))
names = sorted(s['node'] for s in m.db_agent_servers(st))
ok('1 standalone: only this node\'s server, not a node that is not one', names == [me], names)
st.set_meta('node:peer', json.dumps({'at': now, 'name': 'peer'}))
st.set_meta('dbagent:node:peer', row('peer'))
names = sorted(s['node'] for s in m.db_agent_servers(st))
ok('1 a node of the cluster: its server is there', names == sorted([me, 'peer']), names)
st.set_meta('load:db:peer', json.dumps({'at': now - 5, 'kind': 'db', 'node': 'peer'}))
st.set_meta('load:db:gone', json.dumps({'at': now - 5, 'kind': 'db', 'node': 'gone'}))
m.db_agent_on = lambda: False
got = sorted(r['node'] for r in m.db_agent_load_rows(st))
ok('1 the meter: the peer\'s server, not the one of a node that is not one', got == ['peer'], got)

# ==== 2. forgetting a node drops its server's rows =================================================
st.set_meta('node:old', json.dumps({'at': now - 9999, 'name': 'old'}))
st.set_meta('dbagent:node:old', row('old', False))
st.set_meta('load:db:old', json.dumps({'at': now - 9999, 'node': 'old'}))
m.ha_forget(st, 'old')
ok('2 forgotten: its server\'s rows gone', st.get_meta('dbagent:node:old') is None and st.get_meta('load:db:old') is None,
   (st.get_meta('dbagent:node:old'), st.get_meta('load:db:old')))
ok('2 the others\' rows stay', st.get_meta('dbagent:node:peer') is not None and st.get_meta('dbagent:node:' + me) is not None)

# ==== 3. the meter's row by this node's clock ======================================================
m.db_agent_call = lambda op, args=None, timeout=90, conf=None, _ack=True, retry=True: {'at': time.time() - 4000, 'cpu': 1.0, 'said': 'x'}
m.DBAGENT_STATE.update(load=None, load_at=0)
v = m.db_agent_load(fresh=True)
ok('3 read an hour behind by the server\'s clock: timed now, by this node\'s', abs(v['at'] - time.time()) < 2 and 'said' not in v, v)

print('ALL %d / %d' % (sum(R), len(R)))
