# t_cert.py VERSION - 1.0.275: signing in to the administration pages with a client certificate, on the
# installed server: root (otp_web.py, run here by hand) puts nginx's server on the certificate's own
# port, nginx asks for the certificate, the page hands it to the daemon, which checks it - with the
# authority of tests/cert/pki.sh (an AD CS of its own: UPN, EKU, CDP, the SID of KB5014754), its CRL
# served on 127.0.0.1:18890, the mock directory on 3899.
#  - off (as out of the box): no button, ?api=cert-nonce 404, no server on the port;
#  - the authorities: a person's certificate refused, the two put in (once), written for otp 0600;
#  - the port: 443 and RADIUS's refused; nginx listens on 8443 asking for a certificate, only
#    cert-login and cert-check answered there, the CA list given to the browser;
#  - signed in: falco (read only), nested (full admin, a group within a group), the session cookie set
#    on the way back to 443;
#  - refused, each with why, never signed in: no certificate, not started from the sign-in page (no or a
#    wrong nonce), revoked, run out, Server Authentication only, no UPN, no group of a role, switched off
#    in AD, not in AD, another authority, the SID of another account, a CRL that cannot be had;
#  - which account: compat takes one without a SID, strong refuses it, upn takes the other SID;
#  - revocation off: the revoked one and the one without a CRL taken;
#  - the second step on: still asked after the certificate;
#  - "Try my certificate": who it would sign in, nothing opened;
#  - certificate only: switched on from a certificate's sign-in only, every password refused then,
#    the sign-in page with no password; the way back on the command line;
#  - off again: the server on the port taken away.
import base64, http.cookiejar, json, os, re, ssl, subprocess, sys, time, urllib.parse, urllib.request
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.275'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
PKI = os.environ.get('PKI_DIR', '/tmp/claude-0/pki2')
PORT = 8443
PW = open('/home/claude/run/adminpw').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


subprocess.run(['bash', HERE + '/pki.sh', PKI], check=True, capture_output=True)
if subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).returncode:
    subprocess.Popen(['setsid', 'python3', V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, cwd=V + '/test')
    time.sleep(1.5)
crl = subprocess.Popen([sys.executable, '-m', 'http.server', '18890', '--bind', '127.0.0.1',
                        '--directory', PKI + '/www'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)


def helper(until, wait=150):
    """root's helper run as otp-web.path would (no systemd here), until the condition holds."""
    end = time.time() + wait
    while time.time() < end:
        subprocess.run([sys.executable, '-I', '/usr/local/lib/otp/otp_web.py'], capture_output=True, timeout=120)
        if until():
            return True
        time.sleep(1.5)
    return False


def listening(port):
    import socket
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Browser(object):
    def __init__(self, cert=None, jar=None):
        self.jar = jar if jar is not None else http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if cert:
            ctx.load_cert_chain(PKI + '/%s.pem' % cert, PKI + '/%s.key' % cert)
        self.op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                              urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def raw(self, url, body=None):
        h = {'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'}
        data = None
        if body is not None:
            h['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with self.op.open(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def j(self, what, body=None):
        st, hd, raw = self.raw('https://127.0.0.1/admin/?api=' + what, body)
        try:
            return st, json.loads(raw or b'{}')
        except ValueError:
            return st, {'raw': raw[:200]}

    def cert_login(self, nonce=True, wrong=False):
        """The button: a nonce, then the certificate's port; the way back. (said, signed in)"""
        st, got = self.j('cert-nonce', {})
        if st != 200:
            return 'nonce: %s %s' % (st, got), False
        url = got['url'].replace('https://127.0.0.1:', 'https://127.0.0.1:')
        if not nonce:
            url = re.sub(r'&n=[0-9a-f]+', '', url)
        if wrong:
            url = re.sub(r'&n=[0-9a-f]+', '&n=' + '0' * 32, url)
        st, hd, raw = self.raw(url)
        loc = hd.get('Location', '')
        said = urllib.parse.parse_qs(urllib.parse.urlsplit(loc).query).get('certsaid', [''])[0]
        if not loc and st != 303:
            said = 'HTTP %d: %s' % (st, re.sub(rb'\s+', b' ', raw[:160]).decode('utf-8', 'replace'))
        st2, me = self.j('whoami')
        who = (me.get('who') or {}) if st2 == 200 else {}
        return said, who


admin = Browser()
# as out of the box, whatever a run before left
subprocess.run(['otp', '--set', 'admin_cert=0', '--set', 'admin_password_off=0', '--set', 'admin_2fa=0',
                '--set', 'admin_cert_map=compat', '--set', 'admin_cert_crl=1'], capture_output=True)
time.sleep(4)
helper(lambda: not os.path.exists('/etc/nginx/conf.d/otp_certlogin.conf'), 60)
st, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the local administrator signs in', st == 200, got)


def settings(b=admin, **kv):
    st, got = b.j('settings', {'settings': kv})
    return st, got


st, got = Browser().j('cert-nonce', {})
ok('off: ?api=cert-nonce 404', st == 404, (st, got))
st, hd, page = Browser().raw('https://127.0.0.1/admin/')
ok('off: no "Sign in with a certificate"', b'id="cert-go"' not in page)
ok('off: nothing on port %d' % PORT, not listening(PORT) or not os.path.exists('/etc/nginx/conf.d/otp_certlogin.conf'))

# the directory of the administrators
st, got = admin.j('directories')
had_corp = any(d.get('name') == 'corp' for d in (got.get('directories') or []))
corp_id = next((d.get('id') for d in (got.get('directories') or []) if d.get('name') == 'corp'), None)
admin.j('directories', {'action': 'save', 'directory': {
    'name': 'corp', 'hosts': '127.0.0.1:3899', 'tls': 'none', 'port': 389, 'base': 'DC=corpnet,DC=loc',
    'bind_dn': 'CN=otp,OU=Service,DC=corpnet,DC=loc', 'bind_pw': 'the-otp-service-password',
    'timeout_s': 5, 'user_attr': 'sAMAccountName', 'enabled': 1, **({'id': corp_id} if corp_id else {})}})
st, got = settings(admin_directory='corp', admin_group_full='CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
                   admin_group_readonly='CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', admin_group_token='',
                   login_tries=100)
ok('administrators from the directory', st == 200, got)

# the authorities
b64 = lambda p: base64.b64encode(open(p, 'rb').read()).decode()
st, got = admin.j('certlogin', {'action': 'ca_add', 'data': b64(PKI + '/falco.pem')})
ok('a person\'s certificate as an authority: refused', st == 400 and 'not the certificate of an authority' in (got.get('error') or ''), got)
st, got = admin.j('certlogin', {'action': 'ca_add', 'data': b64(PKI + '/cas.pem')})
ok('the issuing authority and the root put in', st == 200 and len(got.get('cas') or []) == 2, got)
st, got = admin.j('certlogin', {'action': 'ca_add', 'data': b64(PKI + '/root.pem')})
ok('... the root again: nothing added', st == 200 and len(got.get('cas') or []) == 2 and 'in already' in got.get('message', ''), got)
der = subprocess.run(['openssl', 'x509', '-in', PKI + '/root.pem', '-outform', 'DER'], capture_output=True).stdout
ok('DER is read too', admin.j('certlogin', {'action': 'ca_add', 'data': base64.b64encode(der).decode()})[0] == 200)
time.sleep(1)
ca_file = '/var/lib/otp/certlogin/ca.pem'
ok('the authorities written for otp, 0600', os.path.exists(ca_file) and (os.stat(ca_file).st_mode & 0o777) == 0o600
   and open(ca_file).read().count('BEGIN CERTIFICATE') == 2)

# the port
for bad, why in ((443, 'pages'), (1812, 'RADIUS')):
    st, got = settings(admin_cert=1, admin_cert_port=bad)
    ok('admin_cert_port %d refused (%s)' % (bad, why), st == 400 and 'admin_cert_port' in (got.get('error') or ''), got)
st, got = settings(admin_cert=1, admin_cert_port=PORT)
ok('switched on, port %d' % PORT, st == 200, got)
conf = '/etc/nginx/conf.d/otp_certlogin.conf'
ok('root puts nginx\'s server on port %d' % PORT, helper(lambda: os.path.exists(conf) and listening(PORT)))
text = open(conf).read() if os.path.exists(conf) else ''
ok('... asking for a certificate of the authorities put in', 'ssl_verify_client optional_no_ca;' in text
   and 'ssl_client_certificate /etc/nginx/certs/otp-certlogin-ca.pem;' in text
   and open('/etc/nginx/certs/otp-certlogin-ca.pem').read().count('BEGIN CERTIFICATE') == 2)
ok('... only cert-login and cert-check, the certificate to the page, everything else 404',
   '$arg_api !~ "^cert-(login|check)$"' in text and 'SSL_CLIENT_CERT $ssl_client_escaped_cert' in text
   and 'location / { return 404; }' in text and 'OTP_CERT_PORT 1' in text)
ok('... the administrators\' allow list as on 443', 'allow 10.0.0.0/8;' in text and 'deny  all;' in text)
st, hd, page = Browser('falco').raw('https://127.0.0.1:%d/admin/' % PORT)
ok('the port: the administration itself not served (404)', st == 404, st)
st, hd, page = Browser('falco').raw('https://127.0.0.1:%d/' % PORT)
ok('the port: the enrolment page not served (404)', st == 404, st)
p = subprocess.run(['openssl', 's_client', '-connect', '127.0.0.1:%d' % PORT, '-servername', 'otp'],
                   input=b'', capture_output=True, timeout=20).stdout.decode('utf-8', 'replace')
ok('the port asks for a certificate, naming the two authorities', 'Acceptable client certificate CA names' in p
   and 'Corpnet Issuing CA' in p and 'Corpnet Root CA' in p, p[-600:])
p443 = subprocess.run(['openssl', 's_client', '-connect', '127.0.0.1:443'], input=b'', capture_output=True,
                      timeout=20).stdout.decode('utf-8', 'replace')
ok('443 asks nobody for a certificate', 'Acceptable client certificate CA names' not in p443
   and 'No client certificate CA names sent' in p443)
st, hd, page = Browser().raw('https://127.0.0.1/admin/')
ok('on: "Sign in with a certificate" on the sign-in page', b'id="cert-go"' in page and b'Sign in with a certificate' in page)

# signing in
said, who = Browser('falco').cert_login()
ok('falco: signed in, read only, back on 443 (%s)' % said, who.get('name') == 'falco' and who.get('role') == 'readonly', (said, who))
said, who = Browser('nested').cert_login()
ok('nested: full admin (a group within a group)', who.get('name') == 'nested' and who.get('role') == 'fulladmin', (said, who))
cases = (('no certificate', None, 'no certificate was sent'),
         ('revoked', 'falco-rev', 'revoked'),
         ('run out', 'falco-old', 'expired'),
         ('Server Authentication only', 'falco-srv', 'purpose'),
         ('no UPN', 'noupn', 'names no user'),
         ('no group of a role', 'outsider', 'none of the groups'),
         ('switched off in AD', 'gone', 'may not sign in'),
         ('not in AD', 'ghost', 'has nobody'),
         ('another authority', 'stranger', 'not taken'),
         ('the SID of another account', 'falco-sid2', 'another account'),
         ('a CRL that cannot be had', 'falco-nocdp', 'CRL'))
for what, cert, words in cases:
    said, who = Browser(cert).cert_login()
    ok('%s: refused, and why (%s)' % (what, said[:110]), not who and words in said, (said, who))
said, who = Browser('falco').cert_login(nonce=False)
ok('not started from the sign-in page (no nonce): refused', not who and 'not started' in said, (said, who))
said, who = Browser('falco').cert_login(wrong=True)
ok('a nonce of somebody else\'s: refused', not who and 'not started' in said, (said, who))

# which account
said, who = Browser('falco-nosid').cert_login()
ok('compat: a certificate without a SID signs in by its UPN', who.get('name') == 'falco', (said, who))
settings(admin_cert_map='strong')
time.sleep(1.2)
said, who = Browser('falco-nosid').cert_login()
ok('strong: one without a SID refused', not who and 'names no SID' in said, (said, who))
said, who = Browser('falco').cert_login()
ok('strong: one with the account\'s SID signs in', who.get('name') == 'falco', (said, who))
settings(admin_cert_map='upn')
time.sleep(1.2)
said, who = Browser('falco-sid2').cert_login()
ok('upn: the SID is not looked at', who.get('name') == 'falco', (said, who))
settings(admin_cert_map='compat', admin_cert_crl=0)
time.sleep(1.2)
said, who = Browser('falco-rev').cert_login()
ok('revocation off: the revoked one signs in (as said on the card)', who.get('name') == 'falco', (said, who))
said, who = Browser('falco-nocdp').cert_login()
ok('revocation off: no CRL to be had is no matter', who.get('name') == 'falco', (said, who))
settings(admin_cert_crl=1)
time.sleep(1.2)

# "Try my certificate"
tb = Browser('nested', jar=admin.jar)
st, hd, page = tb.raw('https://127.0.0.1:%d/admin/?api=cert-check' % PORT)
said_t = (re.search(rb'id="said">([^<]*)', page) or [b'', b''])[1].decode()
ok('try my certificate (signed in): nested would sign in as full admin (%s)' % said_t, st == 200 and 'would sign in nested@corpnet.cz as fulladmin' in said_t, said_t)
st, hd, page = Browser('nested').raw('https://127.0.0.1:%d/admin/?api=cert-check' % PORT)
ok('try my certificate without signing in: not answered', b'would sign in' not in page)

# the second step
st, got = settings(admin_2fa=1)
ok('the second step switched on', st == 200, got)
time.sleep(1.5)
said, who = Browser('falco').cert_login()
ok('a certificate with the second step on: the step still asked, no role yet', who.get('name') == 'falco' and not who.get('role'), (said, who))
subprocess.run(['otp', '--admin-2fa', 'off'], capture_output=True)
time.sleep(4)
admin = Browser()
admin.j('login', {'name': 'admin', 'password': PW})

# certificate only
st, got = settings(admin_password_off=1)
ok('no password: refused from a password\'s sign-in', st == 400 and 'first, then switch the password off' in (got.get('error') or ''), got)
cb = Browser('nested')
said, who = cb.cert_login()
st, got = settings(cb, admin_password_off=1)
ok('switched on from a certificate\'s sign-in (nested, full admin)', st == 200, got)
time.sleep(1.5)
st, hd, page = Browser().raw('https://127.0.0.1/admin/')
ok('the sign-in page: no password, "a certificate only"', b'id="signin-form" autocomplete="on" hidden' in page
   and b'with a certificate only' in page and b'id="cert-go"' in page, page[:0])
st, got = Browser().j('login', {'name': 'admin', 'password': PW})
ok('a password refused (403)', st == 403, (st, got))
said, who = Browser('falco').cert_login()
ok('a certificate still signs in', who.get('name') == 'falco', (said, who))
row = subprocess.run(['otp', '--cert', 'status'], capture_output=True, text=True)
ok('otp --cert status: on, the password not offered, the node listening', 'is ON' in row.stdout and 'NOT offered' in row.stdout
   and 'listening' in row.stdout, row.stdout[-400:])
subprocess.run(['otp', '--set', 'admin_password_off=0'], capture_output=True)
for _ in range(30):
    if Browser().j('login', {'name': 'admin', 'password': PW})[0] == 200:
        break
    time.sleep(1)
admin = Browser()
st, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the way back as root: otp --set admin_password_off=0', st == 200, got)

# the events
st, ev = admin.j('events')
words = json.dumps(ev)
ok('the events: signed in with a certificate (its subject, serial), refused ones with why',
   'the certificate CN=falco' in words and 'a sign-in with a certificate from' in words, words[:200])

# off again
st, got = settings(admin_cert=0)
ok('switched off', st == 200, got)
ok('root takes the port away again', helper(lambda: not os.path.exists(conf) and not listening(PORT)))
st, got = Browser().j('cert-nonce', {})
ok('... and the button: 404', st == 404, st)
# leave as found
for c in (admin.j('certlogin')[1].get('cas') or []):
    admin.j('certlogin', {'action': 'ca_drop', 'sha256': c['sha256']})
settings(admin_directory='', admin_group_full='', admin_group_readonly='', login_tries=5)
if not had_corp:
    for d in admin.j('directories')[1].get('directories') or []:
        if d.get('name') == 'corp':
            admin.j('directories', {'action': 'delete', 'id': d['id']})
crl.terminate()
print('ALL %d / %d' % (sum(R), len(R)))
