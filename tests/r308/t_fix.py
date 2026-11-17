"""t_fix.py - 1.0.308: an administrator's second step - wrong codes counted on the account across
sign-ins and nodes (past 20 a day refused, a reset forgets them); codes by mail or SMS limited per
account and per address, also when the step is set up. The parts loaded as a module over SQLite.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.308'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r308_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx308', 'api_port': 29938}, open(D + '/config.json', 'w'))
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


# ==== 1 wrong codes across sign-ins
class HF(object):
    def __init__(self):
        self.store = st
        self.n = 0

    def failed(self, key):
        self.n += 1


said = []
for sign_in in range(4):
    st.session_new('admin', 'boss', 'fulladmin', '127.0.0.1', 1, data={'mfa': 'check'})
    sid = st.db.value('SELECT id FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1', ('boss',))
    for _ in range(5):
        try:
            m._mfa_wrong(HF(), {'id': sid, 'name': 'boss'}, 'k', 'that code is not right')
        except m.ApiError as e:
            said.append(str(e))
ok('1 four sign-ins, five wrong codes each: 20 counted on the account', m.mfa_wrong_today(st, 'boss') == 20, m.mfa_wrong_today(st, 'boss'))
src = open(TOP + '/otp.py').read()
i_ck = src.find("if mfa_wrong_today(h.store, name) >= MFA_WRONG_DAY_MOST:")
ok('1 the check refuses at 20 a day, before the code is looked at', i_ck > 0
   and i_ck < src.find("key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),", i_ck) < i_ck + 600)
m.mfa_reset(st, 'boss', 'admin')
ok('1 a reset of the second step forgets them', m.mfa_wrong_today(st, 'boss') == 0)

# ==== 2 codes sent: limited per account and per address
sent = []
m.code_send = lambda store, kind, dest, code, **kw: sent.append(dest) or 'sent'
m.CONFIG['code_send_max'] = 5


class HS(object):
    def __init__(self):
        self.store = st
        self.headers = {}


errs = []
for i in range(7):
    st.session_new('admin', 'boss2', 'fulladmin', '127.0.0.1', 1, data={'mfa': 'check'})
    s = st.db.rows('SELECT * FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1', ('boss2',))[0]
    s = dict(s)
    s['data'] = json.loads(s.get('data') or '{}') if isinstance(s.get('data'), str) else (s.get('data') or {})
    try:
        m._mfa_send(HS(), s, 'mail', 'boss2@corp.cz', 'mfa_code')
    except m.ApiError as e:
        errs.append((e.status, str(e)))
ok('2 a new sign-in each time: no more than five codes to the account', len(sent) == 5 and errs and errs[0][0] == 429, (len(sent), errs[:2]))
sent[:] = []
errs[:] = []
for i in range(7):
    st.session_new('admin', 'new%d' % i, 'fulladmin', '127.0.0.1', 1, data={'mfa': 'enrol'})
    s = dict(st.db.rows('SELECT * FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1', ('new%d' % i,))[0])
    s['data'] = {}
    try:
        m._mfa_send(HS(), s, 'sms', '+420603000111', 'mfa_new')
    except m.ApiError as e:
        errs.append(e.status)
ok('2 setting the step up, one number typed in by many accounts: no more than five codes to it', len(sent) == 5 and errs.count(429) == 2, (len(sent), errs))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
