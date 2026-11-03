# t_sso.py VERSION - signed in by a load balancer or WAF on the enrolment pages (1.0.239). Off: as until now
# (404, and the password sign-in as it was). On only with the balancers named and a key. Refused: not from a
# balancer named, no peer said (nginx not set up), the key wrong or not there, no name, a name the directory
# does not know, one in none of the realm's groups. Signed in: the same session goes on, another person's
# replaces it, the one-time code before the first token is still sent and asked, replacing a token asks no
# password but still the old one's code. Switched off: such sessions end. The last sign-in noted per node.
# The root helper's nginx line (OTP_PEER): put in, taken out, nginx -t takes it.
# Starts its own mock AD, SMS spool and daemon (SQLite).
import os, sys, json, time, subprocess, urllib.request, tempfile, base64, atexit, re, glob, importlib.util
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.239'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-sso-'); run = D + '/run'; os.makedirs(run)
SPOOL = D + '/sms'; os.makedirs(SPOOL)
LPORT, RPORT, APORT = 23991, 31952, 29895
mock = subprocess.Popen([sys.executable, HERE + '/../cz/mockldap_cz.py', V, str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
atexit.register(mock.terminate)
mock.stdout.readline()
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run,
           OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'sso1'},
          open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.directory_save({'name': 'Domena', 'hosts': '127.0.0.1:%d' % LPORT, 'tls': 'none', 'port': 389,
                   'base': 'OU=Česká Lípa,DC=corpnet,DC=loc',
                   'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password',
                   'timeout_s': 5, 'user_attr': 'sAMAccountName'})
st.realm_save({'name': 'corpnet.cz', 'suffix': 'corpnet.cz', 'directory': 'Domena', 'lookup': 'upn',
               'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp', 'mail', 'sms'],
               'groups': [{'group': 'Uživatelé VPN', 'reply': ''}]})
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
st.add_account('ro', 'readonly', 'Read-Only-Pass-153!', must_change=0)
st.save_setting('names_czsk_letters', 1, 'test'); st.set_meta('names:letters:checked', '1')
tk = otp.Tokens(st)
g = tk.enroll('ostastny@corpnet.cz', 'test')          # one who has a token already
SEC = base64.b32decode(g['secret'] + '=' * (-len(g['secret']) % 8))
tk.check('ostastny@corpnet.cz', otp.totp(SEC), how='test')
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()


def call(path, body=None, sess=None, peer=None, client='198.51.100.20'):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': client}
    if sess:
        h['X-Otp-Session'] = sess
    if peer:
        h['X-Otp-Peer'] = peer
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sms_code():
    time.sleep(0.5)
    files = sorted(glob.glob(SPOOL + '/otp-*'), key=os.path.getmtime)
    if not files:
        return None, ''
    t = open(files[-1]).read()
    for f in files:
        os.remove(f)
    m = re.search(r'\b(\d{6})\b', t.split('\n\n', 1)[-1])
    return (m.group(1) if m else None), t


LB = '10.40.0.5'
_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}, client='127.0.0.1'); S = a['token']
_, a = call('/api/auth/login', {'name': 'ro', 'password': 'Read-Only-Pass-153!'}, client='127.0.0.1'); SR = a['token']
c, x = call('/api/settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'portal_tries': 100,
                                           'code_send_max': 20, 'portal_reissue': 1}}, S)
ok('portal on: %s' % c, c == 200, x)

# ---- off: as until now ------------------------------------------------------------------------------
c, x = call('/api/portal/info')
ok('off: the page is told nothing of it', c == 200 and x.get('sso') is None, x)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': 'x' * 40}, peer=LB)
ok('off: a sign-in by the balancer refused (%s)' % c, c == 404, x)
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
ok('off: the password sign-in as until now', c == 200 and x.get('token') and not x.get('gate'), x)
call('/api/portal/logout', {}, x.get('token'))
ok('off: nothing of it in nginx asked (web state carries no sso_peer)', 'sso_peer' not in otp.web_desired(st), otp.web_desired(st).keys())

# ---- switched on only with the balancers and a key -------------------------------------------------------
c, x = call('/api/settings', {'settings': {'portal_sso': 1}}, S)
ok('on without the balancers named: refused (%s)' % c, c == 400 and 'balancers' in str(x.get('error')), x)
c, x = call('/api/settings', {'settings': {'portal_sso_from': LB + '/32 10.41.0.0/24'}}, S)
ok('the balancers named: saved (%s)' % c, c == 200, x)
c, x = call('/api/settings', {'settings': {'portal_sso': 1}}, S)
ok('on without a key: refused (%s)' % c, c == 400 and 'key' in str(x.get('error')), x)
for k, v in (('portal_sso_from', '10.0.0.0/8; evil'), ('portal_sso_header', 'Cookie'), ('portal_sso_header', 'X-Otp-Sso-Key'),
             ('portal_sso_header', 'X-A:b'), ('portal_sso_key', 'short'), ('portal_sso_logout', 'javascript:alert(1)'),
             ('portal_sso_logout', '//evil.example/x'), ('portal_sso_logout', 'https://lb.example/a b')):
    c, x = call('/api/settings', {'settings': {k: v}}, S)
    ok('%s=%r refused (%s)' % (k, v, c), c == 400, x)
c, x = call('/api/portal-sso', {'action': 'key'}, SR)
ok('a key: not for a read-only administrator (%s)' % c, c == 403, x)
c, x = call('/api/portal-sso', {'action': 'key'}, S)
KEY = x.get('key') or ''
ok('a key made, shown once (%s)' % c, c == 200 and len(KEY) >= 40 and x['view']['key_set'], x)
raw = json.loads(st.db.value("SELECT v FROM settings WHERE k = 'portal_sso_key'") or '""')
ok('...kept sealed in the database', KEY not in raw and raw.startswith('sealed:'), raw[:30])
c, x = call('/api/settings', None, S)
shown = [s_ for s_ in x.get('settings', []) if s_['key'] == 'portal_sso_key']
ok('...not shown in the settings (masked)', shown and KEY not in json.dumps(shown), shown)
c, x = call('/api/settings', {'settings': {'portal_sso': 1, 'portal_sso_logout': '/cgi/tmlogout'}}, S)
ok('on: saved (%s)' % c, c == 200, x)
c, x = call('/api/portal/info')
ok('the page is told the header and where signing out goes', (x.get('sso') or {}).get('header') == 'X-Otp-User'
   and x['sso']['logout'] == '/cgi/tmlogout' and KEY not in json.dumps(x), x)
otp.CONFIG['portal_sso'] = 1        # as the daemon has it now
ok('nginx asked for OTP_PEER now', otp.web_desired(st).get('sso_peer') is True)

# ---- refused: spoofed -------------------------------------------------------------------------------------
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY})
ok('no peer said (nginx not set up): refused (%s), said why' % c, c == 503 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, peer='203.0.113.66')
ok('the right key from a machine that is not a balancer: refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, peer='203.0.113.66', client=LB)
ok('...even with the balancer\'s address as the client (X-Forwarded-For): refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY[:-2] + 'xx'}, peer=LB)
ok('a wrong key from the balancer: refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': ''}, peer=LB)
ok('no key from the balancer: refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': '', 'key': KEY}, peer=LB)
ok('no name: refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'nikdo', 'key': KEY}, peer=LB)
ok('a name the directory does not know: refused (%s)' % c, c == 401 and not x.get('token'), x)
c, x = call('/api/portal/sso', {'name': 'cizi', 'key': KEY}, peer='10.41.0.9')
ok('in none of the realm\'s groups: refused as on the sign-in (%s)' % c, c == 403 and not x.get('token'), x)
ev = json.dumps(call('/api/events?limit=100', None, S)[1], ensure_ascii=False)
ok('the refusals are in the events with their reasons', 'not from the balancers named' in ev and 'not the one set' in ev
   and 'not there' in ev and 'no such account' in ev, ev[:600])

# ---- signed in ---------------------------------------------------------------------------------------------
c, x = call('/api/portal/sso', {'name': 'ostastny', 'key': KEY}, peer=LB)
P = x.get('token')
ok('ostastny (has a token) signed in by the balancer: a session, no gate (%s)' % c, c == 200 and P and not x.get('gate'), x)
c, m = call('/api/portal/me', None, P)
ok('...the pages open, marked as signed in by the balancer, its sign-out named', (m.get('me') or {}).get('sso') is True
   and m['me'].get('sso_logout') == '/cgi/tmlogout' and m['me'].get('methods'), m)
c, y = call('/api/portal/sso', {'name': 'OSTASTNY', 'key': KEY}, P, peer=LB)
ok('the next page by the balancer, the same person: the same session goes on (%s)' % c, c == 200 and y.get('same') and not y.get('token'), y)
c, y = call('/api/portal/reissue', {'password': '', 'code': '000000'}, P)
ok('replacing the token: no password asked - but a wrong old code refused (%s)' % c, c == 403 and 'code' in str(y.get('error')), y)
time.sleep(31 - time.time() % 30)
c, y = call('/api/portal/reissue', {'password': '', 'code': otp.totp(SEC)}, P)
ok('...the old token\'s code: a new one is made (%s)' % c, c == 200 and (y.get('made') or {}).get('uri'), y)
c, y = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, P, peer=LB)
P2 = y.get('token')
ok('somebody else by the balancer on the same browser: a new session (%s)' % c, c == 200 and P2 and P2 != P, y)
c, m = call('/api/portal/me', None, P)
ok('...the one before ended', not m.get('me'), m)
call('/api/portal/logout', {}, P2)
c, x = call('/api/portal/login', {'name': 'ostastny', 'password': 'Heslo-Vnořený-4'})
PW = x.get('token')
ok('with it on, the password sign-in still works', c == 200 and PW, x)
c, y = call('/api/portal/reissue', {'password': '', 'code': '000000'}, PW)
ok('...and replacing a token signed in so still asks the password (%s)' % c, c == 403 and 'password' in str(y.get('error')), y)
call('/api/portal/logout', {}, PW)

# ---- the one-time code before the first token is still asked ------------------------------------------------
c, x = call('/api/settings', {'settings': {'sms_mode': 'spool', 'sms_spool_dir': SPOOL}}, S)
c, x = call('/api/settings', {'settings': {'portal_first_code': 'sms'}}, S)
ok('the code before the first token on: %s' % c, c == 200, x)
sms_code()
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, peer=LB)
G = x.get('token')
ok('jcermak (no token) signed in by the balancer: the gate, by SMS (%s)' % c, c == 200 and (x.get('gate') or {}).get('kind') == 'sms', x)
code, spool = sms_code()
ok('...the SMS went', code, spool[:200])
c, m = call('/api/portal/me', None, G)
ok('...gated: nothing of the person, the gate says signed in by the balancer', (m.get('me') or {}).get('gate', {}).get('sso') is True and not m['me'].get('methods'), m)
c, y = call('/api/portal/enroll', {'kind': 'totp'}, G)
ok('...no token made before the code (%s)' % c, c == 401, y)
c, y = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, G, peer=LB)
ok('...the next page by the balancer: the same session, no second SMS', c == 200 and y.get('same') and sms_code()[0] is None, y)
c, y = call('/api/portal/gate', {'code': code}, G)
ok('...the code typed: in (%s)' % c, c == 200 and (y.get('me') or {}).get('methods'), y)
c, y = call('/api/portal/enroll', {'kind': 'totp'}, G)
ok('...then a token is made (%s)' % c, c == 200 and (y.get('made') or {}).get('uri'), y)

# ---- the card's view, switched off -----------------------------------------------------------------------
c, v = call('/api/portal-sso', None, SR)
last = (v.get('last') or [{}])[0]
ok('the last sign-in noted for the node, readable by a read-only administrator', c == 200 and last.get('node') == 'sso1' and last.get('peer') == LB
   and last.get('ok') and 'jcermak' in str(last.get('name')), v)
ok('...no key in the view', KEY not in json.dumps(v))
c, x = call('/api/settings', {'settings': {'portal_sso': 0}}, S)
ok('switched off: %s' % c, c == 200, x)
c, m = call('/api/portal/me', None, G)
c2, y = call('/api/portal/enroll', {'kind': 'totp'}, G)
ok('...a session signed in by the balancer ends (%s)' % c2, c2 == 401, y)
c, x = call('/api/portal/sso', {'name': 'jcermak', 'key': KEY}, peer=LB)
ok('...and nobody is signed in by it (%s)' % c, c == 404, x)
otp.CONFIG['portal_sso'] = 0
ok('...nginx asked to take OTP_PEER out again', otp.web_desired(st).get('sso_peer') is False, [r['k'] for r in st.db.rows("SELECT k FROM settings WHERE k LIKE 'portal_sso%'")])
c, x = call('/api/portal/info')
ok('...the page is told nothing of it', x.get('sso') is None, x)

# ---- the CLI --------------------------------------------------------------------------------------------
r = subprocess.run([sys.executable, V + '/otp.py', '--sso-status'], env=env, capture_output=True, text=True, timeout=60)
ok('otp --sso-status: says off, the balancers, the last sign-in', r.returncode == 0 and 'off' in r.stdout and LB in r.stdout and 'jcermak' in r.stdout
   and KEY not in r.stdout, r.stdout + r.stderr)
r = subprocess.run([sys.executable, V + '/otp.py', '--sso-key', '--yes', '--json'], env=env, capture_output=True, text=True, timeout=60)
k2 = (json.loads(r.stdout or '{}') if r.returncode == 0 else {}).get('key', '')
ok('otp --sso-key: a new key, the one before no longer the one', len(k2) >= 40 and k2 != KEY, r.stdout + r.stderr)

# ---- the root helper's line in nginx ------------------------------------------------------------------
os.environ['OTP_VIP_NO_SERVICES'] = '1'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
CONF = '/etc/nginx/conf.d/otp.conf'
orig = open(CONF).read()
a1 = W.sso_peer_into(orig, True)
w = W.server_block(a1)
blk = a1[w[0]:w[1]]
loc = re.search(r'location = / \{(.*?)\n    \}', blk, re.S)
ok('on: OTP_PEER in the enrolment pages\' location of the HTTPS server, once', a1.count('OTP_PEER') == 1 and loc and 'OTP_PEER $realip_remote_addr' in loc.group(1), a1[:200])
adm = re.search(r'location = /admin/ \{(.*?)\n    \}', blk, re.S)
ok('...not in the administration\'s', adm and 'OTP_PEER' not in adm.group(1))
ok('...put in twice: still once', W.sso_peer_into(a1, True) == a1)
ok('off: the file as it was', W.sso_peer_into(a1, False) == orig)
ok('off where it never was: nothing changed', W.sso_peer_into(orig, False) == orig)
both = W.realip_into(a1, {'from': ['10.40.0.5/32'], 'header': 'X-Forwarded-For', 'recursive': True})
try:
    open(CONF, 'w').write(both)
    t = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    ok('nginx -t takes it, with the balancer\'s real_ip as well', t.returncode == 0, t.stderr[-300:])
finally:
    open(CONF, 'w').write(orig)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
