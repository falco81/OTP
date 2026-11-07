"""t_api_fix.py - 1.0.262 hunt, the API fixes: a bare realm not taken into a whole one (and the
other way); a directory account's role and password not changed here; the last local full
administrator kept while no directory signs administrators in; the balancer guide's lists kept
from a reader; enrolment/dashboard/otp on the long lists' connection, enrolment's default window
with all=1 for the whole; whoami as h.me() decides. The parts concatenated as build.sh does into a
temporary otp.py, loaded as a module over SQLite - no daemon, no ports.

    python3 t_api_fix.py
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.262'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_apifix_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx1', 'api_port': 29961}, open(D + '/config.json', 'w'))
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


# ==== 1. a bare realm is not taken into a whole one =================================================
base = {'directory': '', 'lookup': 'none', 'auth_mode': 'otp', 'methods': ['totp'], 'groups': []}
st.realm_save(dict(base, name='Old', suffix='old.cz', token_name='bare'), 't')
st.realm_save(dict(base, name='Main', suffix='main.cz', token_name='whole'), 't')
st.realm_save(dict(base, name='Old2', suffix='old2.cz', token_name='whole'), 't')
main = [r for r in st.realms() if r['name'] == 'Main'][0]
try:
    st.realm_save(dict(base, id=main['id'], name='Main', suffix='main.cz', token_name='whole',
                       aliases=['old.cz']), 't', absorb=['Old'])
    ok('1 bare into whole: refused', False, 'taken in')
except ValueError as e:
    ok('1 bare into whole: refused, said why', 'would not be found' in str(e) and 'Old' in str(e), e)
ok('1 bare into whole: Old is still a realm', 'Old' in [r['name'] for r in st.realms()])
st.realm_save(dict(base, id=main['id'], name='Main', suffix='main.cz', token_name='whole',
                   aliases=['old2.cz']), 't', absorb=['Old2'])
names = [r['name'] for r in st.realms()]
main = [r for r in st.realms() if r['name'] == 'Main'][0]
ok('1 whole into whole: taken in as before', 'Old2' not in names and 'old2.cz' in main['aliases'], names)
st.realm_save(dict(base, name='Bare2', suffix='b2.cz', token_name='bare'), 't')
st.realm_save(dict(base, name='Whole3', suffix='w3.cz', token_name='whole'), 't')
b2 = [r for r in st.realms() if r['name'] == 'Bare2'][0]
try:
    st.realm_save(dict(base, id=b2['id'], name='Bare2', suffix='b2.cz', token_name='bare',
                       aliases=['w3.cz']), 't', absorb=['Whole3'])
    ok('1 whole into bare: refused', False)
except ValueError as e:
    ok('1 whole into bare: refused', 'would not be found' in str(e), e)
st.realm_save(dict(base, id=b2['id'], name='Bare2', suffix='b2.cz', token_name='bare',
                   aliases=['old.cz']), 't', absorb=['Old'])
ok('1 bare into bare: taken in, novak@old.cz is the token novak as before',
   'Old' not in [r['name'] for r in st.realms()] and
   m.Authenticator.token_name('novak@old.cz', st.realm_for('novak@old.cz')) == 'novak')

# ==== 2. a directory account's role and password =====================================================
st.add_account('local1', 'fulladmin', 'Local-Admin-Pass-262!', must_change=0)
st.add_account('dirfull', 'fulladmin', None, source='directory')
st.add_account('dirro', 'readonly', None, source='directory')
dmn = Daemon(st, {})
S = {'name': 'local1', 'role': 'fulladmin', 'data': {'mfa_off': 1}}
_, e = api(m._users_do, H(st, dmn, S, {'action': 'role', 'name': 'dirro', 'role': 'tokenadmin'}))
ok('2 role of a directory account: refused, said why',
   e is not None and e.status == 400 and 'comes from its groups in the directory' in str(e), e)
ok('2 role of a directory account: unchanged', st.account('dirro')['role'] == 'readonly')
_, e = api(m._users_do, H(st, dmn, S, {'action': 'password', 'name': 'dirro', 'password': 'Xx-123456789'}))
ok('2 password of a directory account: refused', e is not None and e.status == 400, e)
st.add_account('local2', 'readonly', 'Local-Admin-Pass-262!', must_change=0)
got, e = api(m._users_do, H(st, dmn, S, {'action': 'role', 'name': 'local2', 'role': 'tokenadmin'}))
ok('2 role of a local account: changed as before', e is None and st.account('local2')['role'] == 'tokenadmin', e)

# ==== 3. the last local full administrator ===========================================================
m.CONFIG['admin_directory'] = ''
ok('3 no admin_directory: the directory full admin is not counted',
   st.fulladmins_left(but='local1', dirs={}) == 0)
_, e = api(m._users_do, H(st, dmn, S, {'action': 'disable', 'name': 'local1'}))
ok('3 no admin_directory: the last local one is not switched off',
   e is not None and 'last full administrator' in str(e) and not st.account('local1')['disabled'], e)
m.CONFIG['admin_directory'] = 'AD'
ok('3 admin_directory names a directory not there: not counted',
   st.fulladmins_left(but='local1', dirs={}) == 0)
ok('3 ... the command line (no daemon): no such directory in the database: not counted',
   st.fulladmins_left(but='local1') == 0)
ok('3 admin_directory with the directory there: counted as before',
   st.fulladmins_left(but='local1', dirs={'ad': object()}) == 1)
m.CONFIG['admin_directory'] = ''
ok('3 local ones counted as before', st.fulladmins_left(but='') == 1 and st.fulladmins_left() == 1)

# ==== 4. the balancer guide's lists for a reader =====================================================
lb = {'server_name': 'x', 'trusted': ['10.0.0.1'], 'access': {'admin': {'any': False, 'from': ['10.1.0.0/16']}},
      'web_proxy': {'on': True, 'from': ['10.0.0.1/32'], 'header': 'X-Forwarded-For', 'port': 8443}, 'clients': []}
ro = m.lb_unmapped(lb, {'role': 'readonly'})
ok('4 reader: no access, no trusted, no web_proxy.from',
   'access' not in ro and 'trusted' not in ro and 'from' not in ro['web_proxy'] and ro['web_proxy']['port'] == 8443, ro)
ok('4 the facts themselves unchanged', lb['web_proxy']['from'] == ['10.0.0.1/32'] and 'access' in lb)
for role in ('fulladmin', 'tokenadmin'):
    ok('4 %s: everything as before' % role, m.lb_unmapped(lb, {'role': role}) == lb)
src = open(os.path.join(BUILD, 'parts/90_api.py'), encoding='utf-8').read()
ok('4 /api/ha gives lb_unmapped', "'lb': lb_unmapped(lb_facts(h.store), me)" in src)

# ==== 6. the long reads on h.reader; enrolment's window ==============================================
SR = {'name': 'local1', 'role': 'fulladmin', 'data': {'mfa_off': 1}}
now = time.time()
for age_d in (1, 10, 60):
    st.db.insert('events', {'ts': now - age_d * 86400, 'kind': 'enrolment', 'level': 'info',
                            'who': 'p%d' % age_d, 'words': 'p%d signed in from 192.0.2.9' % age_d,
                            'node': 'fx1'})
d6 = Daemon(st, {})
got, e = api(m._enrolment, H(st, d6, SR, args={}))
ok('6 enrolment, no window: the last 30 days', e is None and got['total'] == 2, (e, got and got['total']))
ok('6 enrolment on h.reader', d6.read >= 1, d6.read)
got, e = api(m._enrolment, H(st, d6, SR, args={'all': '1', 'since': '0'}))
ok('6 enrolment all=1: the whole log, as the page\'s "all" showed it', e is None and got['total'] == 3, got and got['total'])
got, e = api(m._enrolment, H(st, d6, SR, args={'from': str(int(now - 90 * 86400))}))
ok('6 enrolment with a window: that window', e is None and got['total'] == 3)
got, e = api(m._enrolment, H(st, d6, SR, args={'since': str(7 * 86400)}))
ok('6 enrolment since: as asked', e is None and got['total'] == 1)
d6.read = 0
got, e = api(m._dashboard, H(st, d6, SR, args={'hours': '24'}))
ok('6 dashboard on h.reader', e is None and d6.read == 1 and 'series' in got, e)
d6.read = 0
got, e = api(m._otp, H(st, d6, SR, args={}))
ok('6 otp on h.reader', e is None and d6.read == 1 and got['total'] == 0, e)
js = open(ASSETS, encoding='utf-8').read()
ok('6 the page asks all=1 when the picker says all of it', "(tpQuery('en-since') || '&all=1')" in js)

# ==== 7. whoami as h.me() ============================================================================
m.CONFIG['admin_directory'] = 'AD'
SD = {'name': 'dirfull', 'role': 'fulladmin', 'data': {'mfa_off': 1}}
H.DIR_CHECKED = {}
got, e = api(m._whoami, H(st, Daemon(st, {}), SD))
ok('7 whoami: a directory account whose directory is gone is nobody', e is None and got == {'who': None}, (e, got))
H.DIR_CHECKED = {'dirfull': time.time()}           # looked at a minute ago: as it is
got, e = api(m._whoami, H(st, Daemon(st, {}), SD))
ok('7 whoami: a directory account looked at lately: as before', e is None and got['who']['role'] == 'fulladmin', (e, got))
got, e = api(m._whoami, H(st, Daemon(st, {}), S))
ok('7 whoami: a local account as before', e is None and got['who']['name'] == 'local1', e)
whoami_src = src[src.index('def _whoami'):src.index("@route('POST', '/api/auth/password')")]
ok('7 whoami reads the account checked', "account(s['name'], checked=True)" in whoami_src)
m.CONFIG['admin_directory'] = ''

# ==== the page ======================================================================================
ok('UI: a directory row\'s role list switched off', "role.disabled = true;" in js and
   'The role of a directory account comes from its groups in the directory' in js)
ok('UI: no take-in offer across bare and whole', 'Keep it a realm of its own.' in js)
ok('UI: the lists not warned about when not given', 'if (!lb.access) { /* not shown */ }' in js)
r = subprocess.run(['node', '--check', ASSETS], capture_output=True, text=True)
ok('UI: admin.js parses', r.returncode == 0, r.stderr)

print('%d/%d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
