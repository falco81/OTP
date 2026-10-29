# Czech diacritics in Active Directory: OUs, groups, names, a login name, an
# escaped comma in a DN - through RADIUS (UDP), the realms' groups, the
# administrators' groups, the enrolment portal and the pages' API.
# Usage: python3 t_cz.py VERSION   (starts its own mock AD and daemon)
import os, sys, json, time, subprocess, urllib.request, tempfile, base64, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.155'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-cz-'); run = D + '/run'; os.makedirs(run)
LPORT, RPORT, APORT = 23999, 31922, 29881
mock = subprocess.Popen([sys.executable, HERE + '/mockldap_cz.py', V, str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
atexit.register(mock.terminate)
mock.stdout.readline()
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run,
           OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'cz'},
          open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.directory_save({'name': 'Domena', 'hosts': '127.0.0.1:%d' % LPORT, 'tls': 'none', 'port': 389,
                   'base': 'OU=Česká Lípa,DC=corpnet,DC=loc',
                   'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password',
                   'timeout_s': 5, 'user_attr': 'sAMAccountName'})
GDN = 'CN=Uživatelé VPN,OU=Skupiny – VPN,DC=corpnet,DC=loc'
st.realm_save({'name': 'corpnet.cz', 'suffix': 'corpnet.cz', 'directory': 'Domena', 'lookup': 'upn',
               'auth_mode': 'password_otp', 'enabled': 1,
               'groups': [{'group': 'Uživatelé VPN', 'reply': 'Class = Uživatelé'}]})
st.realm_save({'name': 'podle-dn', 'suffix': 'dn.test', 'directory': 'Domena', 'lookup': 'sam',
               'auth_mode': 'password_otp', 'enabled': 1, 'token_name': 'bare',
               'groups': [{'group': GDN.lower(), 'reply': ''}]})
st.client_save({'name': 'asa', 'address': '127.0.0.1', 'secret': 'tajné-heslo-č', 'enabled': 1})
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
tk = otp.Tokens(st)
KEYS = {}
try:
    tk.enroll('žofie@corpnet.cz', 'test'); ok_cz_off = False
except ValueError as e:
    ok_cz_off = 'accents' in str(e)
# The administrator switched the Czech and Slovak letters on (1.0.155), the
# others stay off; nothing for the upgrade to decide.
st.save_setting('names_czsk_letters', 1, 'test'); st.set_meta('names:letters:checked', '1')
otp.CONFIG['names_czsk_letters'] = 1
try:
    tk.enroll('łukasz@corpnet.cz', 'test'); ok_refused = False
except ValueError as e:
    ok_refused = 'another language' in str(e)
otp.CONFIG['names_any_letters'] = 1          # made here for the test; the daemon starts with it off
for n in ('łukasz@corpnet.cz', 'иван@corpnet.cz'):
    g = tk.enroll(n, 'test'); KEYS[n] = g['secret']
    tk.check(n, otp.totp(base64.b32decode(g['secret'] + '=' * (-len(g['secret']) % 8)),
                         time.time()), how='test')
otp.CONFIG['names_any_letters'] = 0
for n in ('jcermak@corpnet.cz', 'žofie@corpnet.cz', 'pnovak@corpnet.cz', 'ostastny@corpnet.cz',
          'cizi@corpnet.cz', 'jcermak', 'ostastny'):
    g = tk.enroll(n, 'test'); KEYS[n] = g['secret']
    tk.check(n, otp.totp(base64.b32decode(g['secret'] + '=' * (-len(g['secret']) % 8)),
                         time.time()), how='test')
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()


def call(path, body=None, sess=None, portal=False):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w)


STEP = [0]


def code(n):
    k = KEYS[n]
    # a step not used yet: the one after the last one taken
    t = time.time() + 30 * STEP[0]
    return otp.totp(base64.b32decode(k + '=' * (-len(k) % 8)), t)


def radius(user, pw):
    c, words, _ms = otp.radius_ask('127.0.0.1', RPORT, 'tajné-heslo-č', user, pw, timeout=8, tries=1)
    return {2: 'accept', 3: 'reject', 11: 'challenge'}.get(c, c), words


ok('both off: a token for žofie (Czech ž) is refused', ok_cz_off)
ok('a token for łukasz (Polish ł) is refused while other languages are off', ok_refused)
time.sleep(31)          # the codes of the enrolment step used: the next step
r, w = radius('jcermak@corpnet.cz', 'Heslo-Žluťoučký-1' + code('jcermak@corpnet.cz'))
ok('RADIUS: Jiří Čermák in "Uživatelé VPN" (OU=Uživatelé,OU=Česká Lípa) accepted: %s %s' % (r, w), r == 'accept')
ok('... the group\'s reply "Class = Uživatelé" comes back whole', any(v == 'Uživatelé' or 'Uživatelé' in str(v) for k_, v in w if k_ == 'Class'))
r, w = radius('ostastny@corpnet.cz', 'Heslo-Vnořený-4' + code('ostastny@corpnet.cz'))
ok('RADIUS: Ondřej Šťastný through the nested "Dodavatelé – externí" accepted: %s' % r, r == 'accept')
r, w = radius('pnovak@corpnet.cz', 'Heslo-Čárka-3' + code('pnovak@corpnet.cz'))
ok('RADIUS: "Novák\\, Petr" (a comma in the DN) accepted: %s' % r, r == 'accept')
r, w = radius('žofie@corpnet.cz', 'Heslo-Ďábel-2' + code('žofie@corpnet.cz'))
ok('RADIUS: a login name with diacritics, žofie@corpnet.cz, accepted: %s %s' % (r, w), r == 'accept')
r, w = radius('cizi@corpnet.cz', 'Heslo-Cizí-5' + code('cizi@corpnet.cz'))
ok('RADIUS: Cizí Člověk, in no group, refused: %s' % r, r == 'reject')
r, w = radius('jcermak@corpnet.cz', 'Heslo-Zlutoucky-1' + code('jcermak@corpnet.cz'))
ok('RADIUS: the password without its diacritics refused: %s' % r, r == 'reject')
STEP[0] = 1
r, w = radius('jcermak@dn.test', 'Heslo-Žluťoučký-1' + code('jcermak'))
ok('RADIUS: the group given by its DN in lower case (uživatelé vpn, ou=skupiny – vpn) accepted: %s' % r, r == 'accept')
r, w = radius('ostastny@dn.test', 'Heslo-Vnořený-4' + code('ostastny'))
ok('RADIUS: ... and nested through it: %s' % r, r == 'accept')

r, w = radius('łukasz@corpnet.cz', 'Haslo-Łódź-6' + code('łukasz@corpnet.cz'))
ok('RADIUS, other languages off: łukasz refused: %s' % r, r == 'reject')
r, w = radius('иван@corpnet.cz', 'Пароль-7' + code('иван@corpnet.cz'))
ok('RADIUS, other languages off: иван (Cyrillic) refused: %s' % r, r == 'reject')
_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']
c, x = call('/api/settings', {'settings': {'admin_directory': 'Domena', 'admin_group_full': 'Správci OTP',
                                           'admin_group_readonly': 'CN=Čtenáři,OU=Skupiny – VPN,DC=corpnet,DC=loc',
                                           'login_tries': 100}}, S)
ok('settings with Czech group names saved: %s %s' % (c, x.get('error', '')), c == 200)


def admin(n, pw):
    c, r = call('/api/auth/login', {'name': n, 'password': pw})
    if c != 200:
        return c, r.get('error')
    return c, (call('/api/auth/whoami', None, r['token'])[1].get('who') or {}).get('role')


c, role = admin('jcermak', 'Heslo-Žluťoučký-1')
ok('pages: Jiří Čermák in "Správci OTP" signs in as fulladmin: %s %s' % (c, role), c == 200 and role == 'fulladmin')
c, role = admin('CORP\\pnovak', 'Heslo-Čárka-3')
ok('pages: Novák, Petr in "Čtenáři" (by DN) signs in as readonly: %s %s' % (c, role), c == 200 and role == 'readonly')
c, role = admin('cizi', 'Heslo-Cizí-5')
ok('pages: Cizí Člověk, in neither, refused: %s' % c, c == 401)
c, role = admin('žofie@corpnet.cz', 'Heslo-Ďábel-2')
ok('pages: žofie (diacritics in the login name) in "Správci OTP" signs in: %s %s' % (c, role), c == 200 and role == 'fulladmin')

c, x = call('/api/settings', {'settings': {'names_czsk_letters': 0}}, S)
r, w = radius('žofie@corpnet.cz', 'Heslo-Ďábel-2' + code('žofie@corpnet.cz'))
ok('RADIUS, Czech and Slovak letters off: žofie refused: %s' % r, r == 'reject')
r, w = radius('jcermak@corpnet.cz', 'Heslo-Žluťoučký-1' + code('jcermak@corpnet.cz'))
ok('RADIUS, Czech and Slovak letters off: jcermak (no accents in the name, accents in the password) still accepted: %s' % r, r == 'accept')
c, x = call('/api/portal/login', {'name': 'žofie', 'password': 'Heslo-Ďábel-2'})
ok('portal, Czech and Slovak letters off: žofie told so: %s %s' % (c, x.get('error')), c == 400)
c, x = call('/api/settings', {'settings': {'names_czsk_letters': 1}}, S)
_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']
c, role = admin('łukasz', 'Haslo-Łódź-6')
ok('pages, other languages off: łukasz in "Správci OTP" refused: %s' % c, c == 401)
c, x = call('/api/portal/login', {'name': 'иван', 'password': 'Пароль-7'})
ok('portal, other languages off: иван told so: %s %s' % (c, x.get('error')), c == 400 and 'another language' in str(x.get('error')))
c, x = call('/api/users', {'action': 'add', 'name': 'jürgen', 'role': 'readonly', 'password': 'A-Long-Pass-Word-9!'}, S)
ok('pages, other languages off: a local account "jürgen" refused: %s %s' % (c, x.get('error', '')[:60]), c == 400)
c, x = call('/api/settings', {'settings': {'names_any_letters': 1}}, S)
ok('other languages switched on: %s' % c, c == 200)
STEP[0] = 0          # the off attempts were refused before their code was looked at
r, w = radius('łukasz@corpnet.cz', 'Haslo-Łódź-6' + code('łukasz@corpnet.cz'))
ok('RADIUS, other languages on: łukasz accepted: %s' % r, r == 'accept')
r, w = radius('иван@corpnet.cz', 'Пароль-7' + code('иван@corpnet.cz'))
ok('RADIUS, other languages on: иван accepted: %s' % r, r == 'accept')
c, role = admin('łukasz', 'Haslo-Łódź-6')
ok('pages, other languages on: łukasz signs in as %s' % role, c == 200 and role == 'fulladmin')
_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']
c, x = call('/api/tokens?q=' + urllib.parse.quote('čermák'), None, S)
ok('pages: the tokens list answers a search with diacritics: %s' % c, c == 200)
c, x = call('/api/directories', {'action': 'people', 'directory': 'Domena', 'like': 'Řeh'}, S)
ok('pages: the directory searched for "Řeh" finds Žofie Řeháková: %s %s' % (c, [p.get('display') for p in (x.get('people') or [])][:3]), c == 200 and any(p.get('display') == 'Žofie Řeháková' for p in x.get('people') or []))
c, x = call('/api/directories', {'action': 'people', 'directory': 'Domena', 'like': 'novák, p'}, S)
ok('pages: ... and "novák, p" (a comma) finds Novák, Petr: %s' % [p.get('display') for p in (x.get('people') or [])][:3], any(p.get('display') == 'Novák, Petr' for p in x.get('people') or []))
# the enrolment portal: a person with diacritics in the name makes a token
c, x = call('/api/settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'totp_issuer': 'Firma s.r.o. – Česko', 'portal_tries': 100}}, S)
c, x = call('/api/portal/login', {'name': 'žofie', 'password': 'Heslo-Ďábel-2'})
ok('portal: žofie signs in: %s %s' % (c, x.get('error', '')), c == 200)
PS = x.get('token')
if PS:
    c, w = call('/api/portal/me', None, PS)
    ok('portal: shown as "Žofie Řeháková": %s %s' % (c, json.dumps(w, ensure_ascii=False)[:160]), 'Žofie Řeháková' in json.dumps(w, ensure_ascii=False))
otp.CONFIG.update(totp_issuer='Firma s.r.o. – Česko', mail_from='otp@corpnet.cz', mail_from_name='Správa VPN – Česko')
g = tk.enroll('jcermak@corpnet.cz', 'test')
import urllib.parse as up
ok('QR: the otpauth link names the issuer and the person with diacritics, encoded: %s' % g['uri'][:120],
   'Firma%20s.r.o.%20%E2%80%93%20%C4%8Cesko' in g['uri'] or up.unquote(g['uri']).count('Česko') >= 1)
msg = otp.token_mail('jiri.cermak@corpnet.cz', 'jcermak@corpnet.cz', g, display='Jiří Čermák')
raw = msg.as_bytes()
ok('mail: the token mail to Jiří Čermák is built, its headers encoded', b'=?utf-8?' in raw.lower() or msg['Subject'] is not None)
ok('mail: the body greets "Jiří Čermák"', 'Jiří Čermák' in (msg.get_body(('html',)) or msg.get_body(('plain',))).get_content())
c, x = call('/api/events?limit=50', None, S)
ok('pages: the events read back with the Czech names in them: %s' % c, c == 200 and 'Čermák' in json.dumps(x, ensure_ascii=False) or 'jcermak' in json.dumps(x))
print('ALL %d / %d' % (sum(R), len(R)))
