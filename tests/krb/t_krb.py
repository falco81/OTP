# t_krb.py VERSION - 1.0.274: signing in to the administration pages with Windows (Kerberos, SPNEGO),
# on the installed server, through nginx and PHP as a browser does it (the token made by the
# system's GSS-API from a ticket of the test realm, tests/krb/kdc.sh):
#  - off (as out of the box): not offered, ?api=kerberos-login 404, the sign-in page has no button;
#  - the keytab: refused when not one, or of no web service; put in, written 0600 for otp, its
#    principals shown, its keys never; taken away: the file goes;
#  - on: no ticket -> 401 with WWW-Authenticate: Negotiate; a person of the directory in a group
#    of a role -> signed in with that role (full admin, read only), the event says "with Kerberos";
#    no role, not in the directory, a local account of otp, another realm, the same ticket again,
#    a ticket for a name whose key is not in the keytab, NTLM (bare or in SPNEGO), garbage,
#    a header of 20 kB (nginx lets it through, the daemon refuses it): refused, 403 - never 401;
#  - one key for every name of an account: a ticket for svc2 taken by a keytab of svc1;
#  - the second step on: Kerberos takes the place of the password only - the step is still asked;
#  - "Try my browser's ticket" (signed in): who it would sign in, nothing opened;
#  - the command line: otp --kerberos status --json.
import base64, http.cookiejar, json, os, ssl, subprocess, sys, time, urllib.request
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.274'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
KDC = os.environ.get('KDC_DIR', '/tmp/claude-0/kdc2')
BASE = 'https://127.0.0.1/admin/'
PW = open('/home/claude/run/adminpw').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


subprocess.run(['bash', HERE + '/kdc.sh', KDC], check=True, capture_output=True)
if subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).returncode:
    subprocess.Popen(['setsid', 'python3', V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, cwd=V + '/test')
    time.sleep(1.5)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def tok(person, host='otp.corpnet.loc', mech='spnego'):
    sys.path.insert(0, HERE)
    import krbtok
    r = subprocess.run([sys.executable, HERE + '/krbtok.py', KDC, person, host] + (['krb5'] if mech != 'spnego' else []),
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('no token: %s' % r.stderr)
    return r.stdout.strip()


class Browser(object):
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX),
                                              urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, what, body=None, auth=None, method=None):
        h = {'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'}
        data = None
        if body is not None:
            h['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        if auth:
            h['Authorization'] = auth
        req = urllib.request.Request(BASE + ('?api=' + what if what else ''), data=data, headers=h, method=method)
        try:
            with self.op.open(req, timeout=60) as r:
                raw = r.read()
                return r.status, dict(r.headers), raw
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def j(self, what, body=None, auth=None):
        st, hd, raw = self.call(what, body, auth)
        try:
            return st, hd, json.loads(raw or b'{}')
        except ValueError:
            return st, hd, {'raw': raw[:200].decode('utf-8', 'replace')}


# As out of the box, whatever a run before left (root, on the server).
subprocess.run(['otp', '--set', 'admin_kerberos=0', '--set', 'admin_password_off=0', '--set', 'admin_2fa=0'],
               capture_output=True)
for _ in range(30):
    st, hd, page = Browser().call('')
    if b'id="krb-go"' not in page and b'id="in-name"' in page:
        break
    time.sleep(1)
admin = Browser()
st, _, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the local administrator signs in', st == 200, got)


def settings(**kv):
    st, _, got = admin.j('settings', {'settings': kv})
    return st, got


def neg(person, host='otp.corpnet.loc', mech='spnego'):
    return 'Negotiate ' + tok(person, host, mech)


# -- off, as out of the box
st, _, h = admin.j('health') if False else (None, None, None)
b = Browser()
st, hd, got = b.j('kerberos-login', {}, neg('falco'))
ok('off: ?api=kerberos-login is 404', st == 404, (st, got))
st, hd, page = b.call('')
ok('off: the sign-in page has no Windows button', b'id="krb-go"' not in page)

# -- the directory of the administrators
st, _, got = admin.j('directories')
had_corp = any(d.get('name') == 'corp' for d in (got.get('directories') or []))
corp_id = next((d.get('id') for d in (got.get('directories') or []) if d.get('name') == 'corp'), None)
st, _, got = admin.j('directories', {'action': 'save', 'directory': {
    'name': 'corp', 'hosts': '127.0.0.1:3899', 'tls': 'none', 'port': 389, 'base': 'DC=corpnet,DC=loc',
    'bind_dn': 'CN=otp,OU=Service,DC=corpnet,DC=loc', 'bind_pw': 'the-otp-service-password',
    'timeout_s': 5, 'user_attr': 'sAMAccountName', 'enabled': 1, **({'id': corp_id} if corp_id else {})}})
ok('the directory corp saved', st == 200, got)
st, got = settings(admin_directory='corp', admin_group_full='CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
                   admin_group_readonly='CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', admin_group_token='',
                   login_tries=100)
ok('administrators from the directory', st == 200, got)

# -- the keytab
st, _, got = admin.j('kerberos', {'action': 'keytab', 'data': base64.b64encode(b'not a keytab at all').decode()})
ok('not a keytab: refused', st == 400 and 'keytab' in (got.get('error') or ''), got)
st, _, got = admin.j('kerberos', {'action': 'keytab', 'data': base64.b64encode(open(KDC + '/falco.keytab', 'rb').read()).decode()})
ok('a keytab of a person, not of a web service: refused', st == 400 and 'HTTP/' in (got.get('error') or ''), got)
raw = open(KDC + '/http.keytab', 'rb').read()
st, _, got = admin.j('kerberos', {'action': 'keytab', 'data': base64.b64encode(raw).decode()})
ok('the keytab of the web service put in', st == 200 and len(got.get('keytab', {}).get('entries') or []) == 6, got)
ok('... its principals shown, its keys never', 'HTTP/otp.corpnet.loc@CORPNET.LOC' in json.dumps(got)
   and base64.b64encode(raw).decode()[:40] not in json.dumps(got))
kt = '/var/lib/otp/kerberos/http.keytab'
until = time.time() + 20
while time.time() < until and not os.path.exists(kt):
    time.sleep(0.5)
import hashlib, pwd
ok('... written on the node, the same bytes', os.path.exists(kt) and hashlib.sha256(open(kt, 'rb').read()).digest()
   == hashlib.sha256(raw).digest())
stt = os.stat(kt) if os.path.exists(kt) else None
ok('... 0600, otp\'s own', stt is not None and (stt.st_mode & 0o777) == 0o600 and pwd.getpwuid(stt.st_uid).pw_name == 'otp',
   stt and oct(stt.st_mode))
row = subprocess.run(['otp', '--kerberos', 'status', '--json'], capture_output=True, text=True)
try:
    cli = json.loads(row.stdout)
except ValueError:
    cli = {}
ok('otp --kerberos status --json: off, the keytab there, the realm from the directory',
   cli.get('on') is False and cli.get('keytab', {}).get('there') and cli.get('realm') == 'CORPNET.LOC', row.stdout[-300:] + row.stderr[-300:])

# -- on
st, got = settings(admin_kerberos=1)
ok('switched on', st == 200, got)
time.sleep(1.5)
b = Browser()
st, hd, page = b.call('')
ok('on: the sign-in page has "Sign in with Windows"', b'id="krb-go"' in page and b'Sign in with Windows' in page)
st, hd, got = b.j('kerberos-login', {})
ok('no ticket: 401 with WWW-Authenticate: Negotiate', st == 401 and hd.get('WWW-Authenticate') == 'Negotiate'
   and got.get('code') == 'no_ticket', (st, hd.get('WWW-Authenticate'), got))
t_falco = neg('falco')
st, hd, got = b.j('kerberos-login', {}, t_falco)
ok('falco@CORPNET.LOC (VPN_2FACT_USERS): signed in, read only', st == 200 and got.get('who', {}).get('role') == 'readonly'
   and not got.get('mfa'), (st, got))
ok('... the cookie of the sign-in set, the token never shown', any(c.name == 'otp_session' for c in b.jar)
   and 'token' not in got)
st, _, me = b.j('whoami')
ok('... whoami: falco, from the directory', st == 200 and (me.get('who') or {}).get('name') == 'falco'
   and (me.get('who') or {}).get('source') == 'directory', me)
st, hd, got = Browser().j('kerberos-login', {}, t_falco)
ok('the same ticket again (a replay): refused, 403', st == 403, (st, got))
st, _, got = Browser().j('kerberos-login', {}, neg('nested'))
ok('nested (VPN_SUPPLIER_X, within a group): full admin', st == 200 and got.get('who', {}).get('role') == 'fulladmin', (st, got))
for who, why in (('outsider', 'none of the groups'), ('pkolar', 'locked out'), ('ghost', 'directory'),
                 ('gone', 'may not sign in'), ('edvorak', 'cannot be read'),
                 ('admin', 'account of this server')):
    st, hd, got = Browser().j('kerberos-login', {}, neg(who))
    ok('%s: refused, 403 (%s)' % (who, why), st == 403 and why in (got.get('error') or ''), (st, got))
st, hd, got = Browser().j('kerberos-login', {}, neg('falco', 'other.corpnet.loc'))
ok('a ticket for a name whose key is not in the keytab: refused', st == 403 and 'not taken' in (got.get('error') or ''), (st, got))
st, hd, got = Browser().j('kerberos-login', {}, neg('falco', 'nodea.corpnet.loc'))
ok('a ticket for another name in the keytab (a node\'s): signed in', st == 200, (st, got))
st, hd, got = Browser().j('kerberos-login', {}, neg('falco', mech='krb5'))
ok('bare Kerberos (not SPNEGO): signed in', st == 200, (st, got))
ntlm = base64.b64encode(b'NTLMSSP\x00\x01\x00\x00\x00\x07\x82\x08\xa2' + b'\x00' * 16).decode()
st, hd, got = Browser().j('kerberos-login', {}, 'Negotiate ' + ntlm)
ok('NTLM: refused, 403, said so', st == 403 and 'NTLM' in (got.get('error') or ''), (st, got))
spnego_ntlm = base64.b64encode(bytes.fromhex('6082') + b'\x00\x40' + b'\x06\x06+\x06\x01\x05\x05\x02' + b'NTLMSSP\x00\x01' + b'\x00' * 40).decode()
st, hd, got = Browser().j('kerberos-login', {}, 'Negotiate ' + spnego_ntlm)
ok('NTLM inside SPNEGO: refused', st == 403 and 'NTLM' in (got.get('error') or ''), (st, got))
st, hd, got = Browser().j('kerberos-login', {}, 'Negotiate ' + base64.b64encode(os.urandom(300)).decode())
ok('garbage: refused, 403', st == 403, (st, got))
big = 'Negotiate ' + base64.b64encode(os.urandom(15000)).decode()
st, hd, got = Browser().j('kerberos-login', {}, big)
ok('a header of %d bytes: nginx lets it through, the daemon refuses it (403, not 400)' % len(big), st == 403, (st, got))
st, hd, got = Browser().j('kerberos-login', {}, 'Basic ' + base64.b64encode(b'falco:x').decode())
ok('Basic instead of Negotiate: 401 asking for Negotiate', st == 401 and hd.get('WWW-Authenticate') == 'Negotiate', (st, got))
# another realm only
st, got = settings(admin_kerberos_realm='OTHER.EXAMPLE')
time.sleep(1.2)
st, hd, got = Browser().j('kerberos-login', {}, neg('falco'))
ok('a realm set to OTHER.EXAMPLE: falco@CORPNET.LOC refused', st == 403 and 'realm' in (got.get('error') or ''), (st, got))
settings(admin_kerberos_realm='')
time.sleep(1.2)
# one key for every name of an account
st, _, got = admin.j('kerberos', {'action': 'keytab', 'data': base64.b64encode(open(KDC + '/svc1.keytab', 'rb').read()).decode()})
ok('a keytab of HTTP/svc1 alone put in', st == 200, got)
time.sleep(1.5)
st, hd, got = Browser().j('kerberos-login', {}, neg('falco', 'svc2.corpnet.loc'))
ok('a ticket for HTTP/svc2 (the same account\'s key): taken by it', st == 200, (st, got))
admin.j('kerberos', {'action': 'keytab', 'data': base64.b64encode(raw).decode()})
time.sleep(1.5)

# -- "Try my browser's ticket"
st, hd, got = admin.j('kerberos-check', {}, neg('nested'))
ok('try a ticket (signed in): nested would be full admin, nothing opened', st == 200 and got.get('ok')
   and got.get('role') == 'fulladmin' and got.get('principal') == 'nested@CORPNET.LOC', (st, got))
st, hd, got = admin.j('kerberos-check', {}, neg('outsider'))
ok('try a ticket: outsider would not, and why', st == 200 and got.get('ok') is False and 'none of the groups' in (got.get('said') or ''), (st, got))
st, hd, got = Browser().j('kerberos-check', {}, neg('falco'))
ok('try a ticket without signing in: not answered (403)', st in (401, 403), (st, got))

# -- the second step: still asked
st, got = settings(admin_2fa=1)
ok('the second step switched on', st == 200, got)
time.sleep(1.5)
b2 = Browser()
st, hd, got = b2.j('kerberos-login', {}, neg('falco'))
ok('Kerberos with the second step on: the step is asked (%s), no role yet' % got.get('mfa'),
   st == 200 and got.get('mfa') in ('enrol', 'check') and not got.get('who', {}).get('role'), (st, got))
st, _, me = b2.j('users')
ok('... and nothing is opened before it is given', st in (401, 403), (st, me))
settings(admin_2fa=0)
time.sleep(1.2)

# -- only Windows: no password on the sign-in page
st, got = settings(admin_password_off=1)
ok('no password: refused from a sign-in made with a password (so nobody locks themselves out)',
   st == 400 and 'first, then switch the password off' in (got.get('error') or ''), (st, got))
kb = Browser()
st, _, got = kb.j('kerberos-login', {}, neg('nested'))
ok('nested (full admin) signs in with Windows', st == 200 and got.get('who', {}).get('role') == 'fulladmin', (st, got))
st, _, got = kb.j('settings', {'settings': {'admin_password_off': 1}})
ok('... and switches the password off from that sign-in', st == 200, (st, got))
time.sleep(1.5)
st, hd, page = Browser().call('')
ok('the sign-in page: no name and password, "Windows only"', b'id="signin-form" autocomplete="on" hidden' in page
   and b'with Windows only' in page, page[:0])
st, _, got = Browser().j('login', {'name': 'admin', 'password': PW})
ok('a password (the local administrator\'s, right) is refused: 403', st == 403 and 'switched off' in (got.get('error') or ''), (st, got))
st, _, got = Browser().j('kerberos-login', {}, neg('falco'))
ok('Windows still signs in', st == 200, (st, got))
row = subprocess.run(['otp', '--kerberos', 'status'], capture_output=True, text=True)
ok('otp --kerberos status says the password is not offered', 'NOT offered' in row.stdout, row.stdout[-300:])
st, _, got = kb.j('settings', {'settings': {'admin_kerberos': 0}})
time.sleep(1.5)
st, _, got = Browser().j('login', {'name': 'admin', 'password': PW})
ok('Kerberos switched off: passwords are taken again (nobody locked out)', st == 200, (st, got))
row = subprocess.run(['otp', '--set', 'admin_password_off=0', '--set', 'admin_kerberos=1'], capture_output=True, text=True)
ok('root: otp --set admin_password_off=0 (the way back on the server)', row.returncode == 0, row.stdout[-200:] + row.stderr[-200:])
for _ in range(30):                 # the running service reads the command line's settings within seconds
    st, hd, page = Browser().call('')
    if b'id="krb-go"' in page:
        break
    time.sleep(1)
admin = Browser()
st, _, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('... the local administrator signs in with the password again', st == 200, got)

# -- the events
st, _, ev = admin.j('events')
words = json.dumps(ev)
ok('the events: signed in with Kerberos, refused ones with why', 'falco signed in from' in words and 'with Kerberos' in words
   and 'Kerberos sign-in from' in words, words[:300])

# -- taken away, and off again
st, _, got = admin.j('kerberos', {'action': 'drop'})
ok('the keytab taken away', st == 200 and not got.get('keytab', {}).get('there'), got)
until = time.time() + 20
while time.time() < until and os.path.exists(kt):
    time.sleep(0.5)
ok('... the file gone from the node', not os.path.exists(kt))
st, hd, got = Browser().j('kerberos-login', {}, neg('falco'))
ok('... and nobody signs in with Kerberos (403, this node has no keytab)', st == 403 and 'keytab' in (got.get('error') or ''), (st, got))
st, got = settings(admin_kerberos=0, admin_directory='', admin_group_full='', admin_group_readonly='', login_tries=5)
ok('off again, the directory let go', st == 200, got)
if not had_corp:
    st, _, got = admin.j('directories')
    for d in got.get('directories') or []:
        if d.get('name') == 'corp':
            admin.j('directories', {'action': 'delete', 'id': d['id']})
print('ALL %d / %d' % (sum(R), len(R)))
