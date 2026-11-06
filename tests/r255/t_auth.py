"""t_auth.py - 1.0.255 (auth): A2 the marks of the second step signed with the guard on and a way
taken away by somebody else held ('blocked'); A3 sign-ins opened while the second step was off give
it once it is on (either node); A5 the send slot reserved before a code goes, given back when it
fails; P1 the gate's SMS only to the attributes named; P2 the enrolment pages' lockout kinds; P3 the
throttle's name key NFC; P5 /api/portal/me runs portal_me's checks. No daemon, no ports: the parts'
functions exec'd over SQLite in memory, with stubs."""
import ast, os, sys, json, time, hashlib, hmac, secrets, re, sqlite3, tempfile, threading, unicodedata
import contextlib, pathlib, collections

PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok   ' if c else 'FAIL ') + n + ('' if c else ' ' + str(m)[:300]))


def src_of(f):
    return open(os.path.join(PARTS, f), encoding='utf-8').read()


def pick(f, names, cls=None):
    """The source of top-level defs/assignments `names` of a part (or methods of class `cls`)."""
    src = src_of(f)
    tree = ast.parse(src)
    body = tree.body
    if cls:
        body = [n for n in body if isinstance(n, ast.ClassDef) and n.name == cls][0].body
    out = []
    lines = src.splitlines()
    for n in body:
        nm = getattr(n, 'name', None)
        if nm is None and isinstance(n, ast.Assign):
            nm = getattr(n.targets[0], 'id', None)
        if nm in names:
            start = (n.decorator_list[0].lineno if getattr(n, 'decorator_list', None) else n.lineno) - 1
            seg = '\n'.join(lines[start:n.end_lineno])
            seg = re.sub(r'^\s*@route\(.*$', '', seg, flags=re.M)
            if cls:
                seg = '\n'.join(l[4:] if l.startswith('    ') else l for l in seg.splitlines())
            out.append(seg)
    missing = set(names) - set(re.findall(r'^(?:def |class )?(\w+)', '\n'.join(out), re.M))
    return '\n\n'.join(out)


# ---- a database of SQLite in memory, as 20_db's surface is used here --------------------------
class DB(object):
    engine = 'sqlite'

    def __init__(self):
        self.c = sqlite3.connect(':memory:', isolation_level=None, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)')
        for t in ('settings (k TEXT, v TEXT)', 'accounts (name TEXT)', 'directories (name TEXT)'):
            self.c.execute('CREATE TABLE ' + t)
        self.c.execute('CREATE TABLE sessions (id INTEGER PRIMARY KEY, token_hash TEXT, kind TEXT, '
                       'name TEXT, role TEXT, created REAL, last REAL, expires REAL, ip TEXT, data TEXT)')
        self.in_tx = False
        self.lock = threading.RLock()

    def run(self, sql, args=()):
        return self.c.execute(sql, args).rowcount

    def value(self, sql, args=()):
        r = self.c.execute(sql, args).fetchone()
        return None if r is None else r[0]

    def row(self, sql, args=()):
        r = self.c.execute(sql, args).fetchone()
        return dict(r) if r else None

    def rows(self, sql, args=()):
        return [dict(r) for r in self.c.execute(sql, args).fetchall()]

    def insert(self, t, row):
        ks = list(row)
        return self.c.execute('INSERT INTO %s (%s) VALUES (%s)' % (t, ','.join(ks), ','.join('?' * len(ks))),
                              [row[k] for k in ks]).lastrowid

    def upsert(self, t, key, row):
        self.c.execute('INSERT OR REPLACE INTO %s (k, v) VALUES (?, ?)' % t, (row['k'], row['v']))

    @contextlib.contextmanager
    def transaction(self):
        if self.in_tx:
            yield
            return
        self.c.execute('BEGIN')
        self.in_tx = True
        try:
            yield
            self.c.execute('COMMIT')
        except Exception:
            self.c.execute('ROLLBACK')
            raise
        finally:
            self.in_tx = False


class ApiError(Exception):
    def __init__(self, status, msg, detail=None):
        Exception.__init__(self, msg); self.status = status; self.msg = msg


TMP = tempfile.mkdtemp()
CONFIG = {'db_guard': 0, 'admin_2fa': 0, 'code_ttl_s': 300, 'portal': 1, 'portal_sso': 0,
          'portal_first_code': 'off', 'portal_first_sms_attr': ''}
LOGS = []
g = {'__name__': 'auth', 'CONFIG': CONFIG, 'STATE_DIR': pathlib.Path(TMP), 'json': json, 'time': time,
     'hmac': hmac, 'hashlib': hashlib, 'secrets': secrets, 're': re, 'threading': threading,
     'unicodedata': unicodedata, 'os': os,
     'fnum': lambda x, d=0.0: float(x or d), 'node_name': lambda: 'otp1',
     'sealing_key': lambda: b'k' * 32, 'log': lambda *a, **k: LOGS.append(a),
     'log_sparing': lambda *a, **k: LOGS.append(a), 'ApiError': ApiError,
     'json_obj': lambda raw: (lambda v: v if isinstance(v, dict) else None)(json.loads(raw or 'null')),
     'odict': lambda v: v if isinstance(v, dict) else {}, 'route': lambda *a, **k: (lambda f: f)}
exec(src_of('50g_guard.py'), g)

store_src = pick('50_storage.py', ['session_new', 'session_get', 'session_take', 'session_merge',
                                   'session_marks', 'session_bump', 'session_drop', 'session_end',
                                   'get_meta', 'set_meta', 'drop_meta'], cls='Storage')
exec('class Store(object):\n    def __init__(self, db):\n        self.db = db\n        self.events = []\n'
     '    def add_event(self, *a, **k):\n        self.events.append(a)\n'
     '    def account(self, name, checked=False):\n        return {"name": name, "role": "fulladmin", "display": ""}\n'
     + '\n'.join('    ' + l for l in store_src.splitlines()), g)

# The second step: the whole part, its helpers stubbed.
SENT = []
FAIL_SEND = [False]


class MailError(Exception):
    pass


class SmsError(Exception):
    pass


def code_send(store, kind, dest, code, purpose='', name='', display='', lang=None):
    if FAIL_SEND[0]:
        raise SmsError('the gateway said no')
    SENT.append((kind, dest, code))
    return 'sent'


g.update(MailError=MailError, SmsError=SmsError, code_send=code_send,
         code_new=lambda: '123456', code_hash=lambda salt, c: hashlib.sha256((salt + c).encode()).hexdigest(),
         dest_masked=lambda k, d: '***', code_channels=lambda c=None: ['mail', 'sms'],
         wa_host_ok=lambda h: True, ha_nodes=lambda s: [], _ver_tuple=lambda v: (1, 0, 255),
         CODE_TEXTS={'en': 1, 'cs': 1})
exec(src_of('90m_mfa.py'), g)
Store = g['Store']


class H(object):
    def __init__(self, store, s=None):
        self.store = store; self.headers = {}; self._s = s

    def client_ip(self):
        return '192.0.2.1'

    def session(self, kind):
        return self._s


def fresh():
    db = DB()
    st = Store(db)
    with g['DBGUARD']['lock']:
        g['DBGUARD'].update(seen={}, seen_h={}, good={}, refused={}, dirty=0.0)
    return st


def sess(st, tok, kind='admin'):
    return st.session_get(tok, kind, 3600)


# ==== A3: the marks, and a sign-in opened while the step was off ================================
CONFIG.update(db_guard=0, admin_2fa=0)
st = fresh()
tok_off = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa_off': 1})
s = sess(st, tok_off)
ok('A3 off: a sign-in opened with the second step off is whole while it is off',
   g['mfa_pending'](s, st) == '')
CONFIG['admin_2fa'] = 1
ok('A3 on: the same sign-in now gives the step (enrol: none set up)', g['mfa_pending'](s, st) == 'enrol', g['mfa_pending'](s, st))
st.set_meta('adm2fa:novak', json.dumps({'kind': 'app', 'secret': 'x'}))
ok('A3 on: ... check, once a way is set up', g['mfa_pending'](s, st) == 'check')
ok('A3 on: without the store still pending', g['mfa_pending'](s) == 'check')
tok_old = st.session_new('admin', 'old', 'fulladmin', '::1', 1, data=None)
ok('A3 upgrade: a sign-in of 1.0.254 (no marks) is whole as before', g['mfa_pending'](sess(st, tok_old), st) == '')
# the step given: a sign-in of its own, marked ok
h = H(st, s)
tok2 = g['_mfa_done'](h, s, 'test')
s2 = sess(st, tok2)
ok('A3 done: the new sign-in is marked past the step, mfa_off gone',
   s2['data'].get('mfa_ok') == 1 and 'mfa_off' not in s2['data'] and g['mfa_pending'](s2, st) == '', s2['data'])
ok('A3 done: the sign-in the password opened is ended', sess(st, tok_off) is None)
tok_p = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
ok('A3 a pending sign-in stays pending', g['mfa_pending'](sess(st, tok_p), st) == 'check')
CONFIG['admin_2fa'] = 0
ok('A3 step off: nothing pending', g['mfa_pending'](sess(st, tok_p), st) == '')

# ==== A2: the guard on - the marks signed =======================================================
CONFIG.update(db_guard=1, admin_2fa=1)
st = fresh()
tp = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
ok('A2 a pending sign-in reads with the guard on', sess(st, tp) is not None)
row = st.db.row('SELECT * FROM sessions WHERE token_hash = ?', (hashlib.sha256(tp.encode()).hexdigest(),))
st.db.run('UPDATE sessions SET data = ? WHERE id = ?', ('{}', row['id']))
ok('A2 the step taken out of its data by somebody else: the sign-in reads as none', sess(st, tp) is None)
t_off = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa_off': 1})
row = st.db.row('SELECT * FROM sessions WHERE token_hash = ?', (hashlib.sha256(t_off.encode()).hexdigest(),))
st.db.run('UPDATE sessions SET data = ? WHERE id = ?', (json.dumps({'mfa_ok': 1}), row['id']))
ok('A2 "past the step" written in by somebody else: none', sess(st, t_off) is None)
t_ok = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa_off': 1})
s = sess(st, t_ok)
st.session_merge(s['id'], {'mfa_sent': 3, 'mfa_code': {'hash': 'x'}})
ok('A2 other data changed by otp (codes, counts): still read', sess(st, t_ok) is not None)
st.session_marks(s['id'], {'mfa_ok': 1, 'mfa_off': None})
s = sess(st, t_ok)
ok('A2 marks changed by otp (session_marks) are signed: read, and whole',
   s is not None and g['mfa_pending'](s, st) == '', s)
# a sign-in of 1.0.254: only the 'x' signature
t254 = secrets.token_urlsafe(32)
r254 = {'token_hash': hashlib.sha256(t254.encode()).hexdigest(), 'kind': 'admin', 'name': 'novak',
        'role': 'fulladmin', 'created': time.time(), 'last': time.time(), 'expires': time.time() + 3600,
        'ip': '', 'data': json.dumps({'mfa': 'check'})}
st.db.insert('sessions', r254)
g['dbguard_sign'](st.db, 'x', r254['token_hash'], g['dbguard_session_text'](r254))
ok('A2 upgrade, step on: a sign-in of 1.0.254 (no marks signed) signs in again', sess(st, t254) is None)
CONFIG['admin_2fa'] = 0
ok('A2 upgrade, step off: a sign-in of 1.0.254 is kept', sess(st, t254) is not None)
CONFIG['db_guard'] = 0
st.db.run('UPDATE sessions SET data = ? WHERE token_hash = ?', ('{}', r254['token_hash']))
CONFIG['admin_2fa'] = 1
ok('A2 guard off: nothing checked as until now', sess(st, tp) is not None)
# the old signature stays as 1.0.254 reads it
CONFIG['db_guard'] = 1
rowp = st.db.row('SELECT * FROM sessions WHERE token_hash = ?', (hashlib.sha256(tp.encode()).hexdigest(),))
ok("A2 the 'x' signature is the one 1.0.254 checks, unchanged",
   g['dbguard_ok'](st.db, 'x', rowp['token_hash'], json.dumps(['admin', 'novak', 'fulladmin',
                                                                '%.3f' % rowp['created'], '%.3f' % rowp['expires']])))

# ---- A2: a way taken away by somebody else is held -------------------------------------------
st = fresh()
CONFIG.update(db_guard=1, admin_2fa=1)
ok('A2 no way ever set up: enrol', g['mfa_stage'](st, 'novak') == 'enrol')
st.set_meta('adm2fa:novak', json.dumps({'kind': 'app', 'secret': 'x'}))
ok('A2 a way set up: check', g['mfa_stage'](st, 'novak') == 'check')
st.db.run("DELETE FROM meta WHERE k = 'adm2fa:novak'")
ok('A2 its row not there (as an older version\'s reset left it): enrol, not held', g['mfa_stage'](st, 'novak') == 'enrol')
st.db.run("INSERT INTO meta (k, v) VALUES ('adm2fa:novak', 'garbage')")
ok('A2 its row put back unsigned: blocked', g['mfa_stage'](st, 'novak') == 'blocked')
st.drop_meta('adm2fa:novak')
ok('A2 reset by otp (its going signed): enrol', g['mfa_stage'](st, 'novak') == 'enrol')
st.db.run("INSERT INTO meta (k, v) VALUES ('adm2fa:eve', ?)", (json.dumps({'kind': 'app'}),))
ok('A2 an unsigned row of an account never signed: blocked', g['mfa_stage'](st, 'eve') == 'blocked')
CONFIG['db_guard'] = 0
st.db.run("DELETE FROM meta WHERE k = 'adm2fa:eve'")
st.set_meta('adm2fa:ann', json.dumps({'kind': 'app'}))
st.db.run("DELETE FROM meta WHERE k = 'adm2fa:ann'")
ok('A2 guard off: a deleted row is enrol as until now', g['mfa_stage'](st, 'ann') == 'enrol')
CONFIG['db_guard'] = 1
st.db.run("INSERT INTO meta (k, v) VALUES ('adm2fa:ann', 'garbage')")
tb = st.session_new('admin', 'ann', 'fulladmin', '::1', 1, data={'mfa': g['mfa_stage'](st, 'ann')})
sb = sess(st, tb)
ok('A2 the sign-in of a held account is pending (blocked)', g['mfa_pending'](sb, st) == 'blocked')


class HB(H):
    def body(self):
        return {'action': 'enrol_start', 'kind': 'app'}

    def throttle(self, *a, **k):
        return 'k'

    def failed(self, k):
        pass


try:
    g['_mfa_do'](HB(st, sb))
    ok('A2 nothing set up over a held one', False)
except ApiError as e:
    ok('A2 nothing set up over a held one (409, reset)', e.status == 409 and 'reset-2fa ann' in e.msg, e.msg)
ok('A2 the words of the refusal are in the cs file',
   "otp --reset-2fa {0}" in open('/home/claude/i18n/cs_255_auth.py', encoding='utf-8').read())

# ==== A5: the send slot reserved ===============================================================
CONFIG.update(db_guard=0, admin_2fa=1)
st = fresh()
tk = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
s_a = sess(st, tk)
s_b = sess(st, tk)              # a second request, read at the same moment
SENT[:] = []
h = H(st, s_a)
g['_mfa_send'](h, s_a, 'sms', '+420777000111', 'mfa_code')
try:
    g['_mfa_send'](H(st, s_b), s_b, 'sms', '+420777000111', 'mfa_code')
    ok('A5 the second request at once sends nothing', False)
except ApiError as e:
    ok('A5 the second request at once sends nothing (429)', e.status == 429 and len(SENT) == 1, (e.status, SENT))
d = sess(st, tk)['data']
ok('A5 counted once, the code kept', d.get('mfa_sent') == 1 and d.get('mfa_code'), d)
# a failed send gives the place back
tk2 = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
s2 = sess(st, tk2)
FAIL_SEND[0] = True
try:
    g['_mfa_send'](H(st, s2), s2, 'sms', '+420777000111', 'mfa_code')
except ApiError as e:
    ok('A5 a send that fails: 502', e.status == 502)
FAIL_SEND[0] = False
d = sess(st, tk2)['data']
ok('A5 ... and its place given back', 'mfa_sent' not in d and 'mfa_sent_at' not in d, d)
s2 = sess(st, tk2)
g['_mfa_send'](H(st, s2), s2, 'sms', '+420777000111', 'mfa_code')
ok('A5 the next one goes at once', sess(st, tk2)['data'].get('mfa_sent') == 1)

# ==== 90_api: P2, P3, P5, P1 ==================================================================
api = src_of('90_api.py')
m = re.search(r'^LOCKOUT_KINDS = \{.*?^\}', api, re.M | re.S)
lk = {}
exec(m.group(0), lk)
for k in ('portal-gate', 'portal-sso', 'portal-sso-peer'):
    ok('P2 %s is a lockout kind with words' % k, k in lk['LOCKOUT_KINDS'] and lk['LOCKOUT_KINDS'][k])
cs = open('/home/claude/i18n/cs_255_auth.py', encoding='utf-8').read()
csg = {}
exec(cs, csg)
ok('P2 their words are in Czech', all(lk['LOCKOUT_KINDS'][k] in csg['S255_AUTH']
                                       for k in ('portal-gate', 'portal-sso', 'portal-sso-peer')))
ok('P3 the throttle name key is NFC', "who = unicodedata.normalize('NFC', str(name)).strip().lower()" in api)
# the throttle method exec'd for the key
thr = pick('90_api.py', ['throttle'], cls='ApiHandler')
tg = {'time': time, 'ipaddress': __import__('ipaddress'), 'unicodedata': unicodedata, 'ApiError': ApiError,
      'human_span': lambda s: '%ds' % s}
exec('class T(object):\n    THROTTLE_LOCK = __import__("threading").Lock()\n    THROTTLE_TIDIED = [0.0]\n'
     + '\n'.join('    ' + l for l in thr.splitlines()), tg)


class D(object):
    def __init__(self):
        self.login_fails = collections.defaultdict(list); self.login_info = {}


t = tg['T'](); t.d = D(); t.client_ip = lambda: '192.0.2.9'
k1 = t.throttle('portal', 5, 15, name=unicodedata.normalize('NFC', 'Novák'))
k2 = t.throttle('portal', 5, 15, name=unicodedata.normalize('NFD', 'Novák'))
ok('P3 composed and decomposed spellings are one count', k1 == k2 and len(t.d.login_fails[k1[1]]) == 2, (k1, k2))

# P5 and P1: portal_me / _portal_whoami / portal_gate_where exec'd
pg = dict(g)
pg.update(PORTAL_FIRST_WAYS={'mail': ('mail',), 'sms': ('sms',), 'sms_mail': ('sms', 'mail'), 'mail_sms': ('mail', 'sms')},
          DIR_MOBILE_DEFAULT=('mobile', 'telephoneNumber'),
          dir_attr_list=lambda v, d: tuple(w for w in re.split(r'[,;\s]+', str(v or '')) if w)[:4] or tuple(d),
          dest_checked=lambda k, raw: raw, ldap_present=lambda a: ('present', a))


class LdapError(RuntimeError):
    pass


class LdapUnreachable(LdapError):
    pass


pg.update(LdapError=LdapError, LdapUnreachable=LdapUnreachable)
exec(pick('90_api.py', ['portal_me', 'portal_gated', 'portal_gate_needed', 'portal_gate_view', '_portal_whoami',
                        'PORTAL_SELF_PHONES', 'portal_first_sms_attrs', 'portal_first_sms_read',
                        'portal_first_sms_warning', 'portal_gate_where', 'portal_state']), pg)
ENDED = []


class PS(object):
    def __init__(self, tok):
        self.tok = tok

    def token(self, name):
        return self.tok

    def session_end(self, t):
        ENDED.append(t)

    def directories(self):
        return [{'name': 'ad', 'mobile_attr': ''}]


class HP(object):
    def __init__(self, s, tok=None):
        self._s = s; self.store = PS(tok); self.headers = {'X-Otp-Session': 'T'}

    def session(self, kind):
        return self._s


pg['portal_state'] = lambda h, s: {'name': s['name']}
pg['portal_gate_view'] = lambda s: {'kind': 'sms'}
CONFIG.update(portal=1, portal_sso=0, portal_first_code='off')
ENDED[:] = []
ok('P5 a plain sign-in is shown', pg['_portal_whoami'](HP({'name': 'novak', 'data': {}})) == {'me': {'name': 'novak'}})
r = pg['_portal_whoami'](HP({'name': 'novak', 'data': {'sso': 1}}))
ok('P5 a sign-in by the balancer with SSO switched off: none, and ended', r == {'me': None} and ENDED == ['T'], (r, ENDED))
ENDED[:] = []
CONFIG['portal_first_code'] = 'sms'
r = pg['_portal_whoami'](HP({'name': 'novak', 'data': {}}, tok=None))
ok('P5 a sign-in that needs the one-time code now (no token): none, and ended', r == {'me': None} and ENDED == ['T'], (r, ENDED))
ENDED[:] = []
r = pg['_portal_whoami'](HP({'name': 'novak', 'data': {'gate_wait': {'kind': 'sms'}}}, tok=None))
ok('P5 a sign-in waiting for its code is still shown its gate', r == {'me': {'name': 'novak', 'gate': {'kind': 'sms'}}} and not ENDED, (r, ENDED))
r = pg['_portal_whoami'](HP({'name': 'novak', 'data': {'gate_ok': 1}}, tok=None))
ok('P5 a sign-in past its code is shown', r == {'me': {'name': 'novak'}}, r)
r = pg['_portal_whoami'](HP({'name': 'novak', 'data': {}}, tok={'state': 'active'}))
ok('P5 somebody with a token in use is shown', r == {'me': {'name': 'novak'}}, r)


class AD(object):
    def __init__(self, attrs):
        self.attrs = attrs; self.asked_for = None

    def asked(self, do):
        return do(self)

    def search(self, base, flt, attrs, scope=2, limit=200):
        self.asked_for = (base, tuple(attrs), scope)
        return [{'dn': base, 'attrs': self.attrs}]


entry = {'dn': 'CN=Novak,DC=x', 'mail': 'novak@x.cz', 'mobile': '+420777111222'}
CONFIG.update(portal_first_code='sms', portal_first_sms_attr='')
ad = AD({'extensionAttribute5': ['+420600000001']})
ok('P1 default: the mobile number as the card reads it (as until now), the directory not asked again',
   pg['portal_gate_where'](entry, ad) == ('sms', '+420777111222', '') and ad.asked_for is None)
ok('P1 default: the Settings page warns of mobile, telephoneNumber',
   'mobile, telephoneNumber' in pg['portal_first_sms_warning'](PS(None)))
CONFIG['portal_first_sms_attr'] = 'extensionAttribute5'
ok('P1 named: the number of that attribute, read from the entry (base scope)',
   pg['portal_gate_where'](entry, ad) == ('sms', '+420600000001', '') and ad.asked_for == ('CN=Novak,DC=x', ('extensionAttribute5',), 0), ad.asked_for)
ok('P1 named, not self-writable: no warning', pg['portal_first_sms_warning'](PS(None)) == '')
r = pg['portal_gate_where'](entry, AD({}))
ok('P1 named and empty: not the mobile number - nothing to send to', r[0] is None and 'extensionAttribute5' in r[2], r)
CONFIG['portal_first_code'] = 'sms_mail'
ok('P1 named and empty, SMS then mail: the mail', pg['portal_gate_where'](entry, AD({}))[:2] == ('mail', 'novak@x.cz'))
CONFIG['portal_first_code'] = 'mail'
ok('P1 mail only: no warning', pg['portal_first_sms_warning'](PS(None)) == '')

# The setting in 00_head
head = src_of('00_head.py')
for what, pat in (('default', r"'portal_first_sms_attr': '',"), ('name', r"'portal_first_sms_attr': 'Its SMS only"),
                  ('help', r"'portal_first_sms_attr': 'The attributes of the directory"),
                  ('pane', r"'portal_first_code', 'portal_first_sms_attr',"),
                  ('depends', r"'portal_first_sms_attr': \['portal_first_code', 'off-not'\]")):
    ok('P1 00_head: %s' % what, re.search(pat, head), pat)
blk = re.search(r"^    if key == 'portal_first_sms_attr'.*?(?=^    if key == )", head, re.M | re.S).group(0)
cg = {'re': re, 'BadSetting': ValueError}
exec('def check_setting(key, value):\n    got = value\n' + blk + '    return got\n', cg)


def chk(v):
    try:
        cg['check_setting']('portal_first_sms_attr', v)
        return True
    except ValueError:
        return False


ok('P1 check: names and OIDs taken', chk('') and chk('extensionAttribute5, employeeMobile') and chk('1.2.840.113556.1.4.7000'))
ok('P1 check: junk and more than four refused', not chk('mobile)(cn=*') and not chk('a b c d e'))

# ---- the marks' signatures tidied as the sign-ins' own, signed again by dbguard_resign -------------
CONFIG.update(db_guard=1, admin_2fa=1)
st = fresh()
tt = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
th = hashlib.sha256(tt.encode()).hexdigest()
st.db.run('DELETE FROM sessions')
old = json.dumps({'n': int((time.time() - 7200) * 1000), 'm': 'x'})
st.db.run("UPDATE meta SET v = ? WHERE k LIKE 'sig:x%'", (old,))
g['dbguard_tidy'](st)
ok('A2 tidy: the signatures of a sign-in over, both kinds, are gone',
   st.db.value("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:x%'") == 0,
   st.db.rows("SELECT k FROM meta"))
tt = st.session_new('admin', 'novak', 'fulladmin', '::1', 1, data={'mfa': 'check'})
st.db.run("DELETE FROM meta WHERE k LIKE 'sig:xm:%'")
ok('A2 its marks unsigned: refused', sess(st, tt) is None)
g['dbguard_resign'](g['SimpleStore'](st.db) if 'SimpleStore' in g else st)
ok('A2 dbguard_resign signs the marks too', sess(st, tt) is not None)

for f in ('00_head.py', '50g_guard.py', '50_storage.py', '90m_mfa.py', '90_api.py', '90o_sso.py'):
    try:
        compile(src_of(f), f, 'exec')
        ok('compiles: %s' % f, True)
    except SyntaxError as e:
        ok('compiles: %s' % f, False, e)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
