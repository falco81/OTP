"""t_cert_ha.py VERSION - 1.0.275: signing in to the pages with a client certificate on the cluster of two
(tests/hasb sandbox: PostgreSQL replicated both ways, the VIP address by keepalived/VRRP), the certificate
handed to each node's daemon as its page does (nginx's $ssl_client_escaped_cert):
  - the authorities put in on node a: node b has them (the database), each node writes them out;
  - root's helper of each node makes nginx's server on the certificate's port: the node's own name and
    certificate, and the VIP address's server (its address, its name, its certificate) beside it;
  - signing in on node a, node b and the node holding the VIP address; a sign-in made on one node good
    on the other; refused ones refused on both (revoked, another account's SID, no group of a role);
  - the node holding the VIP address taken away (keepalived and the daemon stopped): the VIP moves and
    a certificate signs in there; the node back: signs in again;
  - the second step on (switched on node b): asked after a certificate on node a;
  - off on node b: both nodes' helpers take the port away.

Usage (root, the sandbox made and joined): python3 t_cert_ha.py VERSION
"""
import base64, json, os, subprocess, sys, time
os.environ['OTP_CDP_LOCAL'] = '1'          # the test's CRL on 127.0.0.1 (the daemons inherit it)
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

HERE = '/home/claude/ws/tests/cert'
PKI = os.environ.get('PKI_DIR', '/tmp/claude-0/pki2')
PORT = 8443
subprocess.run(['bash', HERE + '/pki.sh', PKI], check=True, capture_output=True)
if not subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).stdout:
    subprocess.Popen([sys.executable, V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1.5)
crl = subprocess.Popen([sys.executable, '-m', 'http.server', '18890', '--bind', '127.0.0.1', '--directory',
                        PKI + '/www'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
PEM = lambda n: open('%s/%s.pem' % (PKI, n)).read()


def cert(n, who):
    return call(n, '/api/auth/cert', {'cert': PEM(who)}, sess=False)


SETUP = '''
try:
    st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
except Exception:
    pass
if not [d for d in st.directories() if d['name'] == 'MOCK']:
    st.directory_save({'name': 'MOCK', 'hosts': '127.0.0.1:3899', 'port': 389, 'tls': 'none',
                       'base': 'DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                       'bind_pw': 'the-otp-service-password', 'user_attr': 'sAMAccountName'})
print('ok')
''' % {'pw': ADMIN_PW}
ok('set up on node a: an administrator, the directory', in_node('a', SETUP).strip().endswith('ok'))
helpers_on()
for n in 'ab':
    stop(n)
    start(n)
for n in 'ab':
    up(n)
    login(n)
st_, got = call('a', '/api/settings', {'settings': {
    'admin_directory': 'MOCK', 'admin_group_full': 'CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
    'admin_group_readonly': 'CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', 'login_tries': 100}})
ok('administrators from the directory, on node a', st_ == 200, got)
st_, got = call('a', '/api/certlogin', {'action': 'ca_add', 'data': base64.b64encode(open(PKI + '/cas.pem', 'rb').read()).decode()})
ok('the two authorities put in on node a', st_ == 200 and len(got.get('cas') or []) == 2, got)
CA = {n: in_node(n, 'print(otp.CERT_CA_FILE)').strip() for n in 'ab'}
for _ in range(60):
    if all(os.path.exists(CA[n]) and open(CA[n]).read().count('BEGIN CERT') == 2 for n in 'ab'):
        break
    time.sleep(1)
ok('both nodes wrote them out (%s, %s)' % (CA['a'], CA['b']), all(os.path.exists(CA[n]) and
   open(CA[n]).read().count('BEGIN CERT') == 2 for n in 'ab'))
# the VIP address with a name and a certificate of its own
st_, got = call('a', '/api/web', {'action': 'vip_save', 'address': VIP + '/24', 'vrid': 63, 'fqdn': 'otp.corpnet.loc'})
ok('the VIP address with its name (%s)' % st_, st_ == 200, got)
st_, got = call('a', '/api/web', {'action': 'tls_selfsigned', 'target': 'vip', 'cn': 'otp.corpnet.loc',
                                  'names': 'otp.corpnet.loc', 'days': 400})
ok('... and a certificate of its own (%s)' % st_, st_ == 200, got)
st_, got = call('a', '/api/web', {'action': 'vip_on'})
ka_on()
st_, got = call('b', '/api/settings', {'settings': {'admin_cert': 1}})
ok('signing in with a certificate switched on, on node b', st_ == 200, got)
NG = {n: '%s/%s/nginx/otp_certlogin.conf' % (S, n) for n in 'ab'}
for _ in range(120):
    if all(os.path.exists(NG[n]) and 'otp.corpnet.loc' in open(NG[n]).read() for n in 'ab'):
        break
    time.sleep(1)
for n in 'ab':
    t = open(NG[n]).read() if os.path.exists(NG[n]) else ''
    ok('node %s: nginx\'s server on %d asking for a certificate, its own certificate' % (n, PORT),
       ('listen %d ssl' % PORT) in t and 'ssl_verify_client optional_no_ca;' in t and
       'otp.pem;' in t, t[:300])
    ok('node %s: ... and the VIP address\'s server: its address, name and certificate' % n,
       ('listen %s:%d ssl' % (VIP, PORT)) in t and 'server_name otp.corpnet.loc;' in t and 'otp-vip.pem' in t, t[-600:])
    ca = '%s/%s/certs/otp-certlogin-ca.pem' % (S, n)
    ok('node %s: the authorities for nginx (the names the browser is told)' % n,
       os.path.exists(ca) and open(ca).read().count('BEGIN CERTIFICATE') == 2)
for _ in range(30):
    if call('a', '/api/health', sess=False)[1].get('cert') and call('b', '/api/health', sess=False)[1].get('cert'):
        break
    time.sleep(1)
ok('both nodes offer the button (health: cert, port %d)' % PORT,
   all(call(n, '/api/health', sess=False)[1].get('cert_port') == PORT for n in 'ab'))

# each node
for n in 'ab':
    st_, got = cert(n, 'falco')
    ok('node %s: falco signs in with a certificate, read only' % n, st_ == 200 and got.get('who', {}).get('role') == 'readonly', (st_, got))
st_, got = cert('b', 'nested')
ok('node b: nested, full admin', st_ == 200 and got.get('who', {}).get('role') == 'fulladmin', (st_, got))
tok = got.get('token')
saved = dict(halib.SESS)
halib.SESS['a'] = tok
st_, me = call('a', '/api/auth/whoami')
halib.SESS.update(saved)
ok('the sign-in made on node b is good on node a', st_ == 200 and str((me.get('who') or {}).get('name') or '').split('@')[0] == 'nested', (st_, me))
for who, words in (('falco-rev', 'revoked'), ('falco-sid2', 'another account'), ('outsider', 'none of the groups')):
    for n in 'ab':
        st_, got = cert(n, who)
        ok('node %s: %s refused (%s)' % (n, who, words), st_ == 401 and words in (got.get('error') or ''), (st_, got))
st_, v = call('b', '/api/certlogin')
nodes = {x['name']: x for x in v.get('nodes') or []}
ok('node b\'s card: both nodes have the authorities written', len(nodes) == 2 and all(x['file'] and x['cas'] == 2 for x in nodes.values()), v.get('nodes'))

# the VIP address
for _ in range(90):
    if vip_master():
        break
    time.sleep(1)
m = vip_master()
ok('the VIP address up (VRRP), held by node %s' % m, m is not None)
if m:
    st_, got = cert(m, 'falco')
    ok('on the node holding the VIP address (%s): signed in' % m, st_ == 200, (st_, got))
    other = 'b' if m == 'a' else 'a'
    ka_stop(m)
    stop(m)
    for _ in range(60):
        if vip_master() == other:
            break
        time.sleep(1)
    ok('the VIP address moved to node %s' % other, vip_master() == other, (vip_role('a'), vip_role('b')))
    st_, got = cert(other, 'nested')
    ok('on the VIP address, now node %s: a certificate signs in' % other, st_ == 200, (st_, got))
    st_, got = cert(other, 'falco-rev')
    ok('... and a revoked one is refused there too', st_ == 401 and 'revoked' in (got.get('error') or ''), (st_, got))
    start(m)
    up(m)
    login(m)
    halib.KA_OFF.discard(m)
    for _ in range(60):
        if vip_master():
            break
        time.sleep(1)
    st_, got = cert(m, 'falco')
    ok('node %s back: signs in with a certificate again' % m, st_ == 200, (st_, got))
else:
    ok('the VIP address could not be raised here - the rest of the VIP checks skipped', False)

# the second step, switched on on node b
for n in 'ab':
    up(n)
    login(n)
st_, got = call('b', '/api/settings', {'settings': {'admin_2fa': 1}})
ok('the second step switched on, on node b', st_ == 200, got)
for _ in range(30):
    st_, got = cert('a', 'falco')
    if got.get('mfa'):
        break
    time.sleep(1)
ok('node a: after the certificate the second step is asked (%s)' % got.get('mfa'),
   st_ == 200 and got.get('mfa') in ('enrol', 'check') and not got.get('who', {}).get('role'), (st_, got))
# off as root does it (otp --admin-2fa off): the local administrator could not save it now
subprocess.run([sys.executable, '-I', V + '/otp.py', '--no-color', '--admin-2fa', 'off'], env=halib.E['b'],
               capture_output=True)
for _ in range(60):
    if all(login(n) and call(n, '/api/ha')[0] == 200 for n in 'ab'):
        break
    time.sleep(1)

# off, on node b
st_, got = call('b', '/api/settings', {'settings': {'admin_cert': 0}})
ok('switched off, on node b', st_ == 200, got)
for _ in range(120):
    if not any(os.path.exists(NG[n]) for n in 'ab'):
        break
    time.sleep(1)
ok('both nodes\' helpers took the port away', not any(os.path.exists(NG[n]) for n in 'ab'))
st_, got = cert('a', 'falco')
ok('... and node a signs nobody in with a certificate (404)', st_ == 404, (st_, got))
for n in 'ab':
    up(n)
    login(n)
st_, got = call('a', '/api/settings', {'settings': {'admin_directory': '', 'admin_group_full': '', 'admin_group_readonly': ''}})
ok('the directory let go (%s)' % st_, st_ == 200, got)
ok('replication healthy at the end on both nodes',
   all((call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab'))
crl.terminate()
done()
