# ui_cert_setup.py up | on | only | mfa | nomfa | down - the installed server set up for ui_cert.js
# through its own pages as the local administrator (the directory corp on the mock LDAP 3899, its
# groups, the authorities of tests/cert/pki.sh, the CRL served on 18890), and root's helper run by
# hand until nginx listens (or no longer) on the certificate's port.
import base64, http.cookiejar, json, os, socket, ssl, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
PKI = os.environ.get('PKI_DIR', '/tmp/claude-0/pki2')
MARK = '/tmp/claude-0/ui_cert_corp_made'
CRLPID = '/tmp/claude-0/ui_cert_crl.pid'
PW = open('/home/claude/run/adminpw').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(jar))


def call(what, body=None):
    h = {'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'}
    data = None
    if body is not None:
        h['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    req = urllib.request.Request('https://127.0.0.1/admin/?api=' + what, data=data, headers=h)
    try:
        with op.open(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def settings(**kv):
    st, got = call('settings', {'settings': kv})
    if st != 200:
        raise SystemExit('settings %s: %s' % (kv, got))


def listening(port=8443):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


def helper(until, wait=150):
    end = time.time() + wait
    while time.time() < end:
        subprocess.run([sys.executable, '-I', '/usr/local/lib/otp/otp_web.py'], capture_output=True, timeout=120)
        if until():
            return True
        time.sleep(1.5)
    return False


what = sys.argv[1:]
if what[0] in ('nomfa', 'down', 'up'):
    subprocess.run(['otp', '--admin-2fa', 'off'], capture_output=True)
    subprocess.run(['otp', '--set', 'admin_password_off=0', '--set', 'admin_kerberos=0'], capture_output=True)
    for _ in range(40):           # signed in with no second step to give: the daemon has read it
        st, got = call('login', {'name': 'admin', 'password': PW})
        if st == 200 and not got.get('mfa'):
            break
        time.sleep(1)
st, got = call('login', {'name': 'admin', 'password': PW})
if st != 200:
    raise SystemExit('admin sign-in: %s' % got)
if what[0] == 'up':
    subprocess.run(['bash', HERE + '/pki.sh', PKI], check=True, capture_output=True)
    if not (os.path.exists(CRLPID) and os.path.exists('/proc/' + open(CRLPID).read().strip())):
        p = subprocess.Popen([sys.executable, '-m', 'http.server', '18890', '--bind', '127.0.0.1', '--directory',
                              PKI + '/www'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        open(CRLPID, 'w').write(str(p.pid))
    st, got = call('directories')
    if not any(d.get('name') == 'corp' for d in got.get('directories') or []):
        open(MARK, 'w').write('1')
    call('directories', {'action': 'save', 'directory': {
        'name': 'corp', 'hosts': '127.0.0.1:3899', 'tls': 'none', 'port': 389, 'base': 'DC=corpnet,DC=loc',
        'bind_dn': 'CN=otp,OU=Service,DC=corpnet,DC=loc', 'bind_pw': 'the-otp-service-password',
        'timeout_s': 5, 'user_attr': 'sAMAccountName', 'enabled': 1}})
    settings(admin_directory='corp', admin_group_full='CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
             admin_group_readonly='CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', admin_group_token='',
             login_tries=100, acme_node_name='otp.corpnet.loc', admin_cert_map='compat', admin_cert_crl=1)
    st, got = call('certlogin', {'action': 'ca_add', 'data': base64.b64encode(open(PKI + '/cas.pem', 'rb').read()).decode()})
    if st != 200:
        raise SystemExit('authorities: %s' % got)
    settings(admin_cert=1)
    if not helper(lambda: listening()):
        raise SystemExit('nginx does not listen on 8443')
elif what[0] == 'on':
    settings(admin_cert=1)
elif what[0] == 'mfa':
    settings(admin_2fa=1)
elif what[0] == 'nomfa':
    pass
elif what[0] == 'down':
    settings(admin_cert=0, admin_kerberos=0, admin_2fa=0)
    helper(lambda: not listening())
    for c in call('certlogin')[1].get('cas') or []:
        call('certlogin', {'action': 'ca_drop', 'sha256': c['sha256']})
    settings(admin_directory='', admin_group_full='', admin_group_readonly='', login_tries=5, acme_node_name='')
    if os.path.exists(MARK):
        for d in call('directories')[1].get('directories') or []:
            if d.get('name') == 'corp':
                call('directories', {'action': 'delete', 'id': d['id']})
        os.unlink(MARK)
    if os.path.exists(CRLPID):
        try:
            os.kill(int(open(CRLPID).read().strip()), 15)
        except (OSError, ValueError):
            pass
        os.unlink(CRLPID)
time.sleep(1.2)
print('done', ' '.join(what))
