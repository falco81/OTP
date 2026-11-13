# ui_krb_setup.py up off|on | on button|auto | mfa | nomfa | down - the installed server set up for
# ui_krb.js through its own pages, as the local administrator: the directory corp (mock LDAP 3899),
# its groups (VPN_SUPPLIER_X full, VPN_2FACT_USERS read only), the keytab of tests/krb/kdc.sh.
import base64, http.cookiejar, json, os, ssl, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
KDC = os.environ.get('KDC_DIR', '/tmp/claude-0/kdc2')
MARK = '/tmp/claude-0/ui_krb_corp_made'
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


what = sys.argv[1:]
if what[0] in ('nomfa', 'down'):
    # The second step on: the local administrator would have to give it first - root turns it off.
    subprocess.run(['otp', '--admin-2fa', 'off'], capture_output=True)
    subprocess.run(['otp', '--set', 'admin_password_off=0'], capture_output=True)
    time.sleep(5)
st, got = call('login', {'name': 'admin', 'password': PW})
if st != 200:
    raise SystemExit('admin sign-in: %s' % got)
if what[0] == 'up':
    subprocess.run(['bash', HERE + '/kdc.sh', KDC], check=True, capture_output=True)
    st, got = call('directories')
    if not any(d.get('name') == 'corp' for d in got.get('directories') or []):
        open(MARK, 'w').write('1')
    call('directories', {'action': 'save', 'directory': {
        'name': 'corp', 'hosts': '127.0.0.1:3899', 'tls': 'none', 'port': 389, 'base': 'DC=corpnet,DC=loc',
        'bind_dn': 'CN=otp,OU=Service,DC=corpnet,DC=loc', 'bind_pw': 'the-otp-service-password',
        'timeout_s': 5, 'user_attr': 'sAMAccountName', 'enabled': 1}})
    settings(admin_directory='corp', admin_group_full='CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
             admin_group_readonly='CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', admin_group_token='',
             admin_kerberos=1 if what[1:] == ['on'] else 0, admin_kerberos_auto=0, admin_2fa=0, login_tries=100,
             acme_node_name='otp.corpnet.loc')
    st, got = call('kerberos', {'action': 'keytab', 'data': base64.b64encode(open(KDC + '/http.keytab', 'rb').read()).decode()})
    if st != 200:
        raise SystemExit('keytab: %s' % got)
    for _ in range(30):
        if os.path.exists('/var/lib/otp/kerberos/http.keytab'):
            break
        time.sleep(0.5)
elif what[0] == 'on':
    settings(admin_kerberos=1, admin_kerberos_auto=1 if what[1:] == ['auto'] else 0)
elif what[0] == 'mfa':
    settings(admin_kerberos=1, admin_kerberos_auto=0, admin_2fa=1)
elif what[0] == 'nomfa':
    pass
elif what[0] == 'down':
    settings(admin_kerberos=0, admin_kerberos_auto=0, admin_2fa=0)
    call('kerberos', {'action': 'drop'})
    settings(admin_directory='', admin_group_full='', admin_group_readonly='', login_tries=5, acme_node_name='')
    if os.path.exists(MARK):
        st, got = call('directories')
        for d in got.get('directories') or []:
            if d.get('name') == 'corp':
                call('directories', {'action': 'delete', 'id': d['id']})
        os.unlink(MARK)
time.sleep(1.2)
print('done', ' '.join(what))
