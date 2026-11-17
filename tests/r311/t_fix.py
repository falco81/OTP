"""t_fix.py - 1.0.311: a node marked failed by the other one that comes back on the new version is checked
and back in service; a token of another spelling whose directory cannot be asked now is "the directory is
away", not "no token". The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.311'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r311_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx311', 'api_port': 29941}, open(D + '/config.json', 'w'))
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


# ==== 1 marked failed, back on the new version
me = m.node_name()
plan = {'id': 'p1', 'version': m.__version__, 'by': 'admin', 'state': 'failed'}


class D(object):
    def __init__(self, bound):
        self.radius = type('R', (), {'bound': bound})()


for bound, back in ((False, False), (True, True)):
    st.set_meta('maint:' + me, json.dumps({'on': True, 'why': 'upgrade to ' + m.__version__}))
    st.set_meta('upgrade:node:' + me, json.dumps({'id': 'p1', 'state': 'failed', 'marked_by': 'nb', 'was_maint': False}))
    m.MAINT_CACHE['at'] = 0
    m._back_after_marked(st, plan, D(bound))
    row = json.loads(st.get_meta('upgrade:node:' + me))
    on = json.loads(st.get_meta('maint:' + me)).get('on')
    ok('1 RADIUS %s: %s' % ('listening' if bound else 'not listening', 'back in service, the step done' if back else 'kept out, tried again later'),
       (on is False and row.get('state') == 'done' and row.get('back')) if back else (on is True and row.get('state') == 'failed'), (on, row))
plan_old = dict(plan, version='9.9.9')
st.set_meta('maint:' + me, json.dumps({'on': True, 'why': 'upgrade to 9.9.9'}))
st.set_meta('upgrade:node:' + me, json.dumps({'id': 'p1', 'state': 'failed', 'marked_by': 'nb', 'was_maint': False}))
m._back_after_marked(st, plan_old, D(True))
ok('1 back on the old version: back in service, as before', json.loads(st.get_meta('maint:' + me)).get('on') is False)

# ==== 2 the token of another spelling, its directory away
RS = m.Authenticator
srv = object.__new__(RS)
srv.store = st
calls = []
srv.directory = lambda name: object()
st.realm_for = lambda name: {'directory': 'ad1', 'lookup': 'upn'}


def find(ad, user, how, realm):
    calls.append(user)
    if len(calls) == 1:
        return {'dn': 'CN=falco,DC=corp', 'many': False}
    raise m.LdapUnreachable('dc1 did not answer within 5 s')


srv.find_person = find
m.portal_same_person = lambda store, realm, entry: 'falco@corp.cz'
gone = []
got = srv.same_person('falco@corp.loc', {'directory': 'ad1', 'lookup': 'upn'}, gone)
ok('2 the second lookup not reached: said as the directory away (the caller answers so), no token taken',
   got == '' and len(gone) == 1 and isinstance(gone[0], m.LdapUnreachable), (got, gone))
calls[:] = []
srv.find_person = lambda ad, user, how, realm: (calls.append(user), {'dn': 'CN=falco,DC=corp'} if len(calls) == 1 else (_ for _ in ()).throw(m.LdapError('no such object')))[1]
gone = []
got = srv.same_person('falco@corp.loc', {'directory': 'ad1', 'lookup': 'upn'}, gone)
ok('2 the directory said no: no token, nothing said as away - as before', got == '' and gone == [], (got, gone))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
