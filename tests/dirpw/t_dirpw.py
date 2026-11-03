# t_dirpw.py VERSION - the cap of wrong directory passwords per person (1.0.230): 0 is as until now;
# on, after so many wrong passwords for one name from anywhere - the enrolment pages, a new token there,
# the administrators' sign-in from the directory - the directory is not asked for that name; a right
# password does not count; cleared under Locked out. Its own mock AD and daemon (SQLite).
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.232'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-pw-'); run = D + '/run'; os.makedirs(run)
LPORT, RPORT, APORT = 23959, 31952, 29911
mock = subprocess.Popen([sys.executable, HERE + '/../cz/mockldap_cz.py', V, str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
atexit.register(mock.terminate)
mock.stdout.readline()
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run,
           OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'pw'},
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
               'auth_mode': 'password_otp', 'enabled': 1, 'groups': [{'group': 'Uživatelé VPN', 'reply': ''}]})
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()
IP = [10]


def call(path, body=None, sess=None, ip=None):
    if ip is None:
        IP[0] += 1
        ip = '10.0.%d.%d' % (IP[0] // 250, IP[0] % 250)     # each try from an address of its own
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': ip}
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


R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}, ip='127.0.0.1'); S = a['token']
adm = lambda path, body=None: call(path, body, S, ip='127.0.0.1')
c, x = adm('/api/settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'names_czsk_letters': 1}})
ok('portal on: %s' % c, c == 200, x)
pl = lambda pw, who='jcermak': call('/api/portal/login', {'name': who, 'password': pw})

# ---- 0: as until now --------------------------------------------------------------------------------
codes = [pl('wrong-%d' % i)[0] for i in range(8)]
ok('off: eight wrong passwords from eight addresses all asked of the directory (401 each): %s' % codes, codes == [401] * 8)
c, x = pl('Heslo-Žluťoučký-1')
ok('off: the right one still lets in (%s)' % c, c == 200, x)
c, lo = adm('/api/lockouts')
ok('off: nothing of it among Locked out', not any(r.get('kind') == 'dir-passwords' for r in [r for n in lo.get('nodes') or [] if n.get('shared') for r in n.get('rows') or []]), lo)

# ---- on: 3 -----------------------------------------------------------------------------------------------
c, x = adm('/api/settings', {'settings': {'dir_pw_tries': 3, 'dir_pw_window_min': 30}})
ok('a cap of 3 saved: %s' % c, c == 200, x)
codes = [pl('wrong-a%d' % i, 'žofie')[0] for i in range(3)]
ok('three wrong passwords for žofie from three addresses: asked, 401 each: %s' % codes, codes == [401] * 3)
c, x = pl('wrong-a4', 'žofie')
ok('the fourth, from yet another address: not asked - 429 (%s)' % c, c == 429 and 'this name' in str(x.get('error')), x)
c, x = pl('Heslo-Ďábel-2', 'žofie')
ok('...nor the right one meanwhile (%s)' % c, c == 429, x)
c, x = pl('Heslo-Ďábel-2', 'ŽOFIE@corpnet.cz')
ok('...nor under another spelling (%s)' % c, c == 429, x)
c, x = pl('Heslo-Žluťoučký-1')
ok('somebody else unaffected (%s)' % c, c == 200, x)
for i in range(5):
    pl('Heslo-Žluťoučký-1')
c, x = pl('Heslo-Žluťoučký-1')
ok('right passwords do not count (six in a row, all in) (%s)' % c, c == 200, x)
c, lo = adm('/api/lockouts')
rows = [r for r in ([r for n in lo.get('nodes') or [] if n.get('shared') for r in n.get('rows') or []]) if r.get('kind') == 'dir-passwords']
ZW = next((r['who'] for r in rows if r['who'].startswith('žofie řeháková#') and r['who'].endswith('|domena')), '')
ok('Locked out lists žofie (by her account: name and DN hash, 1.0.234): 3 of 3, locked', any(r['who'] == ZW and r['locked'] and r['fails'] == 3 for r in rows), rows)
c, x = adm('/api/lockouts', {'action': 'clear', 'kind': 'dir-passwords', 'who': ZW})
ok('cleared: %s' % c, c == 200, x)
c, x = pl('Heslo-Ďábel-2', 'žofie')
ok('then the right password lets in (%s)' % c, c == 200, x)

# ---- the administrators' sign-in from the directory counts with them -------------------------------
adm('/api/settings', {'settings': {'admin_directory': 'Domena', 'admin_group_full': 'Správci OTP'}})
pl('wrong-b1', 'žofie'); pl('wrong-b2', 'žofie')
c, x = call('/api/auth/login', {'name': 'žofie@corpnet.cz', 'password': 'wrong-b3'})
ok('a wrong one at the administrators\' sign-in: asked (%s)' % c, c == 401, x)
c, x = call('/api/auth/login', {'name': 'žofie@corpnet.cz', 'password': 'Heslo-Ďábel-2'})
ok('...the fourth there: not asked - 429 (%s)' % c, c == 429, x)
c, x = pl('Heslo-Ďábel-2', 'žofie')
ok('...nor on the enrolment pages (%s)' % c, c == 429, x)
adm('/api/lockouts', {'action': 'clear', 'kind': 'dir-passwords', 'who': ZW})
c, x = call('/api/auth/login', {'name': 'žofie@corpnet.cz', 'password': 'Heslo-Ďábel-2'})
ok('cleared: the administrator from the directory signs in (%s)' % c, c == 200, x)

# ---- a new token on the enrolment pages: its password counts too -----------------------------------
c, x = pl('Heslo-Žluťoučký-1'); P = x.get('token')
call('/api/portal/enroll', {'kind': 'totp'}, P)
g = st.db.row("SELECT 1 FROM tokens WHERE name = 'jcermak@corpnet.cz'")
codes = [call('/api/portal/reissue', {'password': 'wrong-c%d' % i, 'code': '000000'}, P)[0] for i in range(3)]
ok('three wrong passwords for a new token: refused (%s)' % codes, all(c in (403,) for c in codes), codes)
c, x = pl('Heslo-Žluťoučký-1')
ok('...and then the sign-in is not asked either (%s)' % c, c == 429, x)
# ---- 1.0.234: counted by the account, a name not there as any other, nothing never asked ----------
dn = 'CN=Jan Novák,OU=Lidé,DC=corp,DC=cz'
ok('one account under its two names (novakj, jan.novak@corp.cz): one count',
   otp.dir_pw_who('novakj', {'dn': dn}) == otp.dir_pw_who('jan.novak@corp.cz', {'dn': dn.upper()}) and
   otp.dir_pw_who('novakj', {'dn': dn}) != otp.dir_pw_who('novakj', {'dn': 'CN=Jan Novák 2,OU=Lidé,DC=corp,DC=cz'}),
   (otp.dir_pw_who('novakj', {'dn': dn}), otp.dir_pw_who('jan.novak@corp.cz', {'dn': dn.upper()})))
adm('/api/lockouts', {'action': 'clear', 'kind': 'dir-passwords', 'who': next((r['who'] for r in ([r for n in adm('/api/lockouts')[1].get('nodes') or [] if n.get('shared') for r in n.get('rows') or []]) if r.get('kind') == 'dir-passwords' and r['who'].startswith('jiří')), '')})
codes = [pl('wrong-n%d' % i, 'nikdo')[0] for i in range(3)]
c, x = pl('wrong-n4', 'nikdo')
ok('a name the directory does not have: held back as any other (401 x3, then 429) - the answer says nothing of who exists: %s %s' % (codes, c),
   codes == [401] * 3 and c == 429 and 'this name' in str(x.get('error')), x)
codes = [pl('', 'jcermak')[0] for i in range(5)]
c, x = pl('Heslo-Žluťoučký-1')
ok('empty passwords (never asked of the directory) do not count: five, then the right one lets in (%s %s)' % (codes, c), c == 200, x)
c, x = adm('/api/settings', {'settings': {'dir_pw_tries': 0}})
c, x = pl('Heslo-Žluťoučký-1')
ok('back to 0: as until now at once (%s)' % c, c == 200, x)
# ---- each directory's own cap, the domain's policy (1.0.232) ------------------------------------
c, x = adm('/api/directories', {'action': 'pw_caps'})
dd = {d_['name']: d_ for d_ in x.get('directories') or []}
ok('each directory listed with its cap, as the setting by default: %s' % list(dd), 'Domena' in dd and dd['Domena']['tries'] is None, x)
c, x = adm('/api/directories', {'action': 'policy', 'name': 'Domena'})
pol = x.get('policy') or {}
ok('the domain\'s policy read: lockout after %s in %s s' % ((pol.get('lockout') or {}).get('threshold'), (pol.get('lockout') or {}).get('window_s')),
   (pol.get('lockout') or {}).get('threshold') == 5 and (pol.get('lockout') or {}).get('window_s') == 1800, x)
ok('...the password policy: 8 characters, complex, 24 remembered', (pol.get('password') or {}).get('min_length') == 8 and pol['password'].get('complex') and pol['password'].get('history') == 24)
ok('...the fine-grained policy Admins PSO, locking after 3', any(p_['name'] == 'Admins PSO' and p_['threshold'] == 3 for p_ in pol.get('psos') or []))
rec = pol.get('recommend') or {}
ok('...recommended below the lowest lockout: %s in %s min' % (rec.get('tries'), rec.get('window_min')), rec.get('tries') == 2 and rec.get('window_min') == 30 and rec.get('why', '').startswith('The policy Admins PSO locks'), rec)
c, x = adm('/api/directories', {'action': 'pw_caps'})
ok('the policy read is kept beside the directory, not as a setting', (({d_['name']: d_ for d_ in x['directories']}['Domena']).get('policy') or {}).get('lockout'))
c, x = adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Domena': {'tries': 1, 'window_min': 30}}})
ok('its own cap saved: %s' % x.get('saved'), c == 200 and x.get('saved'), x)
c, x = pl('wrong-d1', 'cizi')
c, x = pl('Heslo-Cizí-5', 'cizi')
ok('one wrong password with a cap of 1 for this directory: the next is not asked (%s)' % c, c == 429, x)
c, x = adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Domena': {'tries': 0}}})
c, x = pl('Heslo-Cizí-5', 'cizi')
ok('no cap for this directory: asked at once, the password right (%s)' % c, c in (200, 403) and 'not have a token' in str(x.get('error', 'not have a token')), x)
c, x = adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Domena': {'tries': 999}}})
ok('a cap over 100: refused (%s)' % c, c == 400, x)
c, x = adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Nowhere': {'tries': 3}}})
ok('a directory that is not there: refused (%s)' % c, c == 400, x)
# a directory renamed takes its own cap with it (1.0.234)
adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Domena': {'tries': 2, 'window_min': 20}}})
did = st.db.value("SELECT id FROM directories WHERE name = 'Domena'")
st2 = otp.Storage(otp.open_db())
row = dict(st2.directories(with_secret=True)[0]); row.update(id=did, name='Domena2', bind_pw='•' * 8)
try:
    st2.directory_save({k: row[k] for k in ('id', 'name', 'hosts', 'port', 'tls', 'base', 'bind_dn', 'bind_pw', 'timeout_s', 'user_attr')}, by='test')
    renamed = True
except Exception as e:
    renamed = str(e)
caps = json.loads(st2.get_meta('dirpw:conf') or '{}')
ok('renamed: its own cap under the new name, not the old one (%s)' % renamed, renamed is True and (caps.get('domena2') or {}).get('tries') == 2 and 'domena' not in caps, caps)
row.update(name='Domena')
st2.directory_save({k: row[k] for k in ('id', 'name', 'hosts', 'port', 'tls', 'base', 'bind_dn', 'bind_pw', 'timeout_s', 'user_attr')}, by='test')
adm('/api/directories', {'action': 'pw_caps_save', 'caps': {'Domena': {'tries': None, 'window_min': None}}})
c, x = adm('/api/directories', {'action': 'pw_caps'})
ok('back to as the setting', ({d_['name']: d_ for d_ in x['directories']}['Domena']).get('tries') is None)
# ---- the same from the command line (1.0.236) ---------------------------------------------------------
def cli(*a):
    g = subprocess.run([sys.executable, V + '/otp.py'] + list(a), env=env, capture_output=True, text=True, timeout=120)
    return g.returncode, g.stdout + g.stderr
rc, out = cli('--dir-cap', 'Domena=2/20')
ok('otp --dir-cap Domena=2/20: saved (%s)' % rc, rc == 0 and 'Domena: 2 in 20 min' in out, out)
rc, out = cli('--dir-caps')
ok('otp --dir-caps: the setting and each directory\'s own', rc == 0 and 'Domena' in out and '2 in 20 min' in out, out)
rc, out = cli('--dir-cap', 'Domena=setting')
rc2, out2 = cli('--dir-cap', 'Nowhere=3')
ok('otp --dir-cap back to the setting; a directory not there refused', rc == 0 and 'as the setting' in out and rc2 != 0 and 'no directory' in out2, (out, out2))
rc, out = cli('--dir-cap', 'Domena=nonsense')
ok('otp --dir-cap with words it does not know: refused (%s)' % rc, rc != 0, out)
rc, out = cli('--dir-policy', 'Domena')
ok('otp --dir-policy Domena: the lockout, the passwords, the fine-grained policy and the recommendation',
   rc == 0 and '5 wrong passwords' in out and 'Admins PSO' in out and 'recommended: 2' in out and '--dir-cap Domena=2/30' in out, out)
rc, out = cli('--dir-sample', 'Domena', 'jcermak')
ok('otp --dir-sample Domena jcermak: every attribute, mail marked', rc == 0 and 'mail ' in out and 'userPrincipalName' in out, out[:400])
rc, out = cli('--guard-status')
ok('otp --guard-status: off here, said so', rc == 0 and 'off' in out, out)
ev = st.db.rows("SELECT words FROM events WHERE words LIKE '%cleared the count of wrong directory passwords%'")
ok('a clearing written in the events', len(ev) >= 2)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
