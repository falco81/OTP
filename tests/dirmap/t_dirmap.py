# t_dirmap.py VERSION - where a person's e-mail address and mobile number are read from the directory
# (1.0.229): by default exactly as before (mail; mobile, then telephoneNumber); mapped to other
# attributes on the directory's card; a person's entry shown with what can hold which; the password kept
# goes only to the servers it was given for. Starts its own mock AD and daemon (SQLite).
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.229'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-dm-'); run = D + '/run'; os.makedirs(run)
LPORT, RPORT, APORT = 23969, 31942, 29901
mock = subprocess.Popen([sys.executable, HERE + '/../cz/mockldap_cz.py', V, str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
atexit.register(mock.terminate)
mock.stdout.readline()
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run,
           OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'dm'},
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
st.add_account('reader', 'readonly', 'Reader-Pass-153!x', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()


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


R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']
_, a = call('/api/auth/login', {'name': 'reader', 'password': 'Reader-Pass-153!x'}); RS = a['token']
c, x = call('/api/directories', None, S)
dirrow = x['directories'][0]
ok('a directory of before: its mapping empty - the default', not dirrow.get('mail_attr') and not dirrow.get('mobile_attr'), dirrow)


def lookup(who='jcermak'):
    c, x = call('/api/directories', {'action': 'lookup', 'name': 'Domena', 'user': who, 'how': 'sam'}, S)
    return x.get('entry') or {}


e = lookup()
ok('by default: the e-mail from mail, as before', e.get('mail') == 'jiri.cermak@corpnet.cz', e)
ok('by default: the mobile from mobile, as before', e.get('mobile') == '+420 603 111 222', e)

# ---- a person's entry, every attribute ------------------------------------------------------------
c, x = call('/api/directories', {'action': 'sample', 'user': 'jcermak', 'directory': {'id': dirrow['id']}}, S)
ok('a person\'s entry read: %s' % c, c == 200 and x.get('dn', '').startswith('CN=Jiří Čermák'), x)
by = {a['name'].lower(): a for a in x.get('attrs') or []}
ok('...every attribute of it', {'mail', 'mobile', 'displayname', 'samaccountname', 'userprincipalname'} <= set(by), sorted(by))
ok('...mail can hold an e-mail address, not a phone', by.get('mail', {}).get('mail') and not by['mail'].get('phone'), by.get('mail'))
ok('...mobile can hold a phone number, not an e-mail', by.get('mobile', {}).get('phone') and not by['mobile'].get('mail'), by.get('mobile'))
ok('...the UPN looks like an address too', by.get('userprincipalname', {}).get('mail'))
ok('...displayName fits neither', not by.get('displayname', {}).get('mail') and not by['displayname'].get('phone'))
ok('...the defaults said', x.get('defaults') == {'mail': 'mail', 'mobile': 'mobile, telephoneNumber'}, x.get('defaults'))
c, y = call('/api/directories', {'action': 'sample', 'user': 'jcermak', 'directory': {'id': dirrow['id']}}, RS)
ok('a reader may not look at a whole entry (%s)' % c, c == 403, y)
c, y = call('/api/directories', {'action': 'sample', 'user': 'nikdo', 'directory': {'id': dirrow['id']}}, S)
ok('nobody of that name: said so (%s)' % c, c == 404, y)
c, y = call('/api/directories', {'action': 'sample', 'user': 'jcermak',
                                 'directory': {'id': dirrow['id'], 'hosts': '10.9.9.9', 'bind_pw': dirrow['bind_pw']}}, S)
ok('other servers with the kept password: refused, the password not sent there (%s)' % c,
   c == 400 and 'password again' in str(y.get('error')), y)
c, y = call('/api/directories', {'action': 'sample', 'user': 'jcermak',
                                 'directory': {'hosts': '127.0.0.1:%d' % LPORT, 'tls': 'none', 'port': 389,
                                               'base': 'OU=Česká Lípa,DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                                               'bind_pw': 'the-otp-service-password'}}, S)
ok('a directory not saved yet, its password typed: read (%s)' % c, c == 200 and y.get('attrs'), y)
ev = st.db.rows("SELECT words FROM events WHERE kind = 'directories'")
ok('the look written in the events', any('looked at every attribute' in r['words'] for r in ev))

# ---- mapped to other attributes -----------------------------------------------------------------------
full = dict(dirrow, bind_pw=dirrow['bind_pw'], mail_attr='userPrincipalName', mobile_attr='telephoneNumber')
c, y = call('/api/directories', {'action': 'save', 'directory': full}, S)
ok('saved: the e-mail from userPrincipalName, the mobile from telephoneNumber (%s)' % c, c == 200, y)
time.sleep(1.5)
e = lookup()
ok('the e-mail now from userPrincipalName', e.get('mail') == 'jcermak@corpnet.cz', e)
ok('the mobile now from telephoneNumber - none there: empty', not e.get('mobile'), e)
c, x = call('/api/directories', None, S)
ok('the mapping kept on the card', x['directories'][0].get('mail_attr') == 'userPrincipalName'
   and x['directories'][0].get('mobile_attr') == 'telephoneNumber', x['directories'][0])
full = dict(full, mobile_attr='telephoneNumber, mobile')
call('/api/directories', {'action': 'save', 'directory': full}, S)
time.sleep(1.5)
e = lookup()
ok('two in order: the first with a value taken', e.get('mobile') == '+420 603 111 222', e)
c, y = call('/api/directories', {'action': 'save', 'directory': dict(full, mail_attr='1bad')}, S)
ok('a mapping that is no attribute name: refused (%s)' % c, c == 400, y)
c, y = call('/api/directories', {'action': 'save', 'directory': dict(full, mail_attr='mail', mobile_attr='mobile, telephoneNumber')}, S)
c, x = call('/api/directories', None, S)
ok('typed back to the default: kept as the default (empty)', not x['directories'][0].get('mail_attr') and not x['directories'][0].get('mobile_attr'), x['directories'][0])
# a save without the fields (an older page, the command line) keeps what is there
call('/api/directories', {'action': 'save', 'directory': dict(full)}, S)
nf = {k: v for k, v in dict(full).items() if k not in ('mail_attr', 'mobile_attr')}
call('/api/directories', {'action': 'save', 'directory': nf}, S)
c, x = call('/api/directories', None, S)
ok('a save without the mapping keeps it', x['directories'][0].get('mail_attr') == 'userPrincipalName', x['directories'][0])

# ---- an attribute of a schema of one's own -------------------------------------------------------------
c, x = call('/api/directories', {'action': 'sample', 'user': 'jcermak', 'directory': {'id': dirrow['id']}}, S)
by = {a['name'].lower(): a for a in x.get('attrs') or []}
ok('an attribute of a schema of one\'s own is in the entry', 'company-mobileno' in by, sorted(by))
full = dict(full, mail_attr='userPrincipalName', mobile_attr='company-MobileNo')
c, y = call('/api/directories', {'action': 'save', 'directory': full}, S)
time.sleep(1.5)
e = lookup()
ok('the mobile read from it (%s)' % c, e.get('mobile') == '777 555 444', e)
c, y = call('/api/directories', {'action': 'save', 'directory': dict(full, mobile_attr='1.2.840.113556.1.4.7000.102.1')}, S)
ok('an attribute given by its OID: taken (%s)' % c, c == 200, y)
full = dict(full, mobile_attr='mobile')
call('/api/directories', {'action': 'save', 'directory': full}, S)
time.sleep(1.5)

# ---- the enrolment pages fill in what the mapping reads ------------------------------------------------
call('/api/settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'portal_tries': 100,
                                    'names_czsk_letters': 1}}, S)
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
c, m = call('/api/portal/me', None, x.get('token'))
sug = (m.get('me') or {}).get('suggest') or {}
ok('the enrolment pages offer the mapped address and number: %s' % sug,
   sug.get('mail') == 'jcermak@corpnet.cz' and sug.get('sms') == '+420 603 111 222', m)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
