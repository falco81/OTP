# t_dbguard.py VERSION - root's actions only from rows otp signed (1.0.231). With db_guard off (the default)
# everything is as before - only signatures are written beside the rows. On: a session, an account, a setting,
# a row of meta, a node's heartbeat or a directory written straight into the database (as anybody who can
# write it would) is not acted on; an older signed row put back neither; RADIUS goes on; a copy put back and
# switching it off work. Its own daemon (SQLite), the database written straight as an attacker would.
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, hashlib, secrets, sqlite3, base64
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.231'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-dg-'); run = D + '/run'; os.makedirs(run)
RPORT, APORT = 31962, 29921
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run, OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'dg'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
st.client_save({'name': 'nas', 'address': '127.0.0.1', 'secret': 'nas-secret-1', 'enabled': 1})
st.realm_save({'name': 'local', 'suffix': '*', 'directory': '', 'lookup': 'none', 'auth_mode': 'otp', 'enabled': 1})
tk = otp.Tokens(st)
T = tk.enroll('novak', 'test')
DBF = D + '/otp.db'
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def raw(sql, args=()):
    """The database written straight, as somebody who can write it would."""
    c = sqlite3.connect(DBF, timeout=30)
    try:
        cur = c.execute(sql, args); c.commit()
        return cur.fetchall()
    finally:
        c.close()


def forged_session():
    tok = secrets.token_urlsafe(32)
    t = time.time()
    raw("INSERT INTO sessions (token_hash, kind, name, role, created, last, expires, ip, data) VALUES (?,?,?,?,?,?,?,?,?)",
        (hashlib.sha256(tok.encode()).hexdigest(), 'admin', 'local', 'fulladmin', t, t, t + 3600, '127.0.0.1', '{}'))
    return tok


def radius_ok():
    k = T['secret']
    c, words, _ = otp.radius_ask('127.0.0.1', RPORT, 'nas-secret-1', 'novak',
                                 otp.totp(base64.b32decode(k + '=' * (-len(k) % 8))), timeout=8, tries=1)
    return c


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']

# ---- off (as until now) -----------------------------------------------------------------------------
c, x = call('/api/status', None, forged_session())
ok('off: a session written straight into the database is taken, as before 1.0.231 (%s)' % c, c == 200, x)
ok('off: the signatures are written beside the rows (accounts, the sign-in)', raw("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:a:%:dg'")[0][0] >= 1 and raw("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:x:%:dg'")[0][0] >= 1)
c, x = call('/api/settings', {'settings': {'proxy_url': 'http://proxy.good:3128', 'proxy': 0}}, S)
ok('a setting that reaches root saved: %s' % c, c == 200, x)
ok('...signed', raw("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:s:%:dg'")[0][0] >= 1)

# ---- on ----------------------------------------------------------------------------------------------------
c, x = call('/api/settings', {'settings': {'db_guard': 1}}, S)
ok('switched on: %s %s' % (c, x.get('message', '')), c == 200, x)
ok('...in config.json, not in the database', json.load(open(D + '/config.json')).get('db_guard') == 1
   and not raw("SELECT 1 FROM settings WHERE k = 'db_guard'"))
c, x = call('/api/status', None, S)
ok('the sign-in made before it goes on (signed when it was switched on) (%s)' % c, c == 200, x)
c, x = call('/api/status', None, forged_session())
ok('a session written straight into the database: refused (%s)' % c, c == 401, x)
pw = otp.password_hash('Attacker-Pass-99!')
raw("INSERT INTO accounts (name, role, pw, source, disabled, must_change, note, created, prefs) VALUES (?,?,?,?,?,?,?,?,?)",
    ('mallory', 'fulladmin', pw, 'local', 0, 0, '', time.time(), '{}'))
c, x = call('/api/auth/login', {'name': 'mallory', 'password': 'Attacker-Pass-99!'})
ok('an account written straight into the database: cannot sign in (%s)' % c, c == 401, x)
raw("UPDATE accounts SET pw = ? WHERE name = 'local'", (pw,))
c, x = call('/api/auth/login', {'name': 'local', 'password': 'Attacker-Pass-99!'})
ok('a password hash changed in the database: not taken (%s)' % c, c == 401, x)
c, x = call('/api/status', None, S)
ok('...and the admin\'s own sign-in refused while its account is not as otp wrote it (%s)' % c, c == 401, x)
raw("DELETE FROM accounts WHERE name = 'mallory'")
# put the right hash back through otp itself (as root would: the command line)
st2 = otp.Storage(otp.open_db())
st2.set_account('local', password='Local-Admin-Pass-153!')
_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a.get('token')
ok('the password set again by otp: the admin signs in', bool(S), a)

# settings
raw("UPDATE settings SET v = ? WHERE k = 'proxy_url'", (json.dumps('http://evil:3128'),))
call('/api/settings', {'settings': {'radius_reject_reason': 1}}, S)       # any save: everything read again
time.sleep(1)
c, x = call('/api/settings', None, S)
got = {s_['key']: s_['value'] for s_ in x.get('settings') or []}
ok('a setting that reaches root changed in the database: its last good value stays (%s)' % got.get('proxy_url'),
   got.get('proxy_url') == 'http://proxy.good:3128', got.get('proxy_url'))
c, x = call('/api/settings', {'settings': {'proxy_url': 'http://proxy.new:3128'}}, S)
time.sleep(1)
c, x = call('/api/settings', None, S)
got = {s_['key']: s_['value'] for s_ in x.get('settings') or []}
ok('...changed on the pages: taken', got.get('proxy_url') == 'http://proxy.new:3128', got.get('proxy_url'))

# meta, in this process with the guard on, as the daemon reads it
otp.CONFIG['db_guard'] = 1
otp.DBGUARD['seen'] = None
st.set_meta('web:vip', json.dumps({'on': False, 'address': '10.0.0.5'}))
ok('a row of meta written by otp: read', st.get_meta('web:vip') is not None)
v1 = raw("SELECT k, v FROM meta WHERE k = 'web:vip' OR k LIKE 'sig:m:%:dg'")
raw("UPDATE meta SET v = ? WHERE k = 'web:vip'", (json.dumps({'on': True, 'address': '192.168.1.1'}),))
ok('...changed in the database: reads as not there', st.get_meta('web:vip') is None)
st.set_meta('web:vip', json.dumps({'on': False, 'address': '10.0.0.6'}))
ok('...written again by otp: read', json.loads(st.get_meta('web:vip'))['address'] == '10.0.0.6')
for k_, v_ in v1:
    raw("UPDATE meta SET v = ? WHERE k = ?", (v_, k_))
ok('an older signed row put back with its signature: reads as not there', st.get_meta('web:vip') is None)
raw("INSERT INTO meta (k, v) VALUES (?, ?)", ('host:sshkeys:want:dg', json.dumps([{'id': 'x1', 'do': 'add', 'line': 'ssh-ed25519 AAAA attacker', 'at': time.time()}])))
ok('a request to add a key to root\'s authorized_keys, written straight: not seen', otp.node_key_rows(st, 'host:sshkeys:want', 'dg') == [])
raw("INSERT INTO meta (k, v) VALUES (?, ?)", ('web:tls:dg', json.dumps({'cert': '-----BEGIN CERTIFICATE-----x', 'key': 'plain-key'})))
ok('a certificate and a plain key for nginx, written straight: not taken', st.get_meta('web:tls:dg') is None)
raw("INSERT INTO meta (k, v) VALUES (?, ?)", ('node:evil', json.dumps({'at': time.time(), 'address': '203.0.113.66', 'version': otp.__version__})))
ok('a node\'s heartbeat written straight: not let through the firewall', '203.0.113.66' not in otp.cluster_addresses(st, 'dg'))
ok('...the guard says what it refused', len(otp.dbguard_view()['refused']) >= 3, otp.dbguard_view())
ok('RADIUS goes on with the guard on: accepted', radius_ok() == 2)

# a copy put back
c, x = call('/api/backup', {'action': 'make'}, S) if False else (0, {})
cp = otp.make_backup(st, 'test')
call('/api/settings', {'settings': {'proxy_url': 'http://proxy.after:3128'}}, S)
try:
    otp.db_file_restore(st, str(cp), by='test', need_admin=False)
    restored = True
except Exception as e:                              # noqa: BLE001
    restored = str(e)
ok('a copy put back: %s' % restored, restored is True)
otp.DBGUARD['seen'] = None
ok('...its rows signed again: what it holds is read', st.get_meta('web:vip') is not None)
ok('...the account in it signs in', otp.dbguard_account_ok(st.db, st.account('local')))

# off again
c, x = call('/api/settings', {'settings': {'db_guard': 0}}, S if call('/api/status', None, S)[0] == 200 else None)
if c != 200:
    _, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a.get('token')
    c, x = call('/api/settings', {'settings': {'db_guard': 0}}, S)
ok('switched off: %s' % c, c == 200, x)
c, x = call('/api/status', None, forged_session())
ok('off again: everything as before 1.0.231 (a session written straight is taken) (%s)' % c, c == 200, x)
ev = st.db.rows("SELECT words, level FROM events WHERE kind = 'security'")
ok('switching it on and off written in Events', any('switched off the guard' in e['words'] for e in ev) and any('switched on' in e['words'] for e in ev))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
