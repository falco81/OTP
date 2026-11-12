# t_chain_ha.py VERSION - the whole chain in a cluster of two with the VIP address (VRRP) (1.0.269): the VIP's
# certificate and node a's own uploaded without their intermediate while its CA Issuers address is down; then on
# the OTHER node "Complete the chain" (fetched) - both nodes hold the same chain (replication); nginx's files on
# the nodes get the certificate + the intermediate; the page's state says complete; node b's own certificate
# completed by "Upload the missing authority" asked on node a. A new sandbox (newsb.sh), keepalived on.
import os, sys, json, time, subprocess, tempfile, threading, http.server, socketserver, shutil
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.269'
H = '/home/claude/work/hasb'
SB = '/tmp/sbc%s' % time.strftime('%m%d%H%M%S')
P = tempfile.mkdtemp(prefix='t269ha-')
WWW = P + '/www'
os.makedirs(WWW)


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, cwd=P)


class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WWW, **k)

    def log_message(self, *a):
        pass


httpd = socketserver.TCPServer(('127.0.0.1', 0), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
AIA = 'http://127.0.0.1:%d/int.cer' % httpd.server_address[1]
open(P + '/ca.ext', 'w').write('basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'root.key', '-out', 'root.pem', '-days', '3650',
   '-subj', '/CN=T269HA Root CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'int.key', '-out', 'int.csr', '-subj', '/CN=T269HA Issuing CA')
sh('openssl', 'x509', '-req', '-in', 'int.csr', '-CA', 'root.pem', '-CAkey', 'root.key', '-CAcreateserial', '-out', 'int.pem',
   '-days', '1825', '-extfile', 'ca.ext')
for name, cn in (('vip', 'vip.example.test'), ('na', 'nodea.example.test'), ('nb', 'nodeb.example.test')):
    open(P + '/%s.ext' % name, 'w').write('basicConstraints=CA:FALSE\nsubjectAltName=DNS:%s\nauthorityInfoAccess=caIssuers;URI:%s\n' % (cn, AIA))
    sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', name + '.key', '-out', name + '.csr', '-subj', '/CN=' + cn)
    sh('openssl', 'x509', '-req', '-in', name + '.csr', '-CA', 'int.pem', '-CAkey', 'int.key', '-CAcreateserial', '-out', name + '.pem',
       '-days', '200', '-extfile', name + '.ext')
sh('openssl', 'x509', '-in', 'int.pem', '-outform', 'DER', '-out', P + '/int.cer.away')
rd = lambda f: open(P + '/' + f).read()
os.environ['OTP_CHAIN_CA'] = P + '/root.pem'          # the system's roots, for the daemons started below

def sandbox_daemons_stop():
    # The sandboxes' own daemons only (OTP_CONFIG under /tmp) - one left from a run before held the ports.
    for pid in subprocess.run(['pgrep', '-f', 'otp.py --daemon'], capture_output=True, text=True).stdout.split():
        try:
            if 'OTP_CONFIG=/tmp/' in open('/proc/%s/environ' % pid, 'rb').read().decode('utf-8', 'replace'):
                os.kill(int(pid), 15)
        except OSError:
            pass
    time.sleep(3)


sandbox_daemons_stop()
r = subprocess.run(['bash', H + '/newsb.sh', SB, VER], capture_output=True, text=True)
print(r.stdout.strip()[-200:], flush=True)
sys.argv = ['x', VER]
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
import halib  # noqa: E402
from halib import ok, call, login, start, up, in_node, helpers_on, ka_on, vip_master, done, S, ADMIN_PW  # noqa: E402
assert S == SB
ok('the sandbox made and joined', r.returncode == 0, r.stderr[-300:])
helpers_on()
for n in 'ab':
    start(n)
in_node('a', 'st.add_account("local", "fulladmin", %r, must_change=0)' % ADMIN_PW)
time.sleep(3)
ok('both nodes up, the administrator signs in', all(up(n) and login(n) for n in 'ab'))
st_, x = call('a', '/api/web', {'action': 'vip_save', 'address': '10.99.0.200/24', 'fqdn': 'vip.example.test', 'vrid': 63, 'ifaces': {}, 'address6': ''})
st2, x2 = call('a', '/api/web', {'action': 'vip_on'})
ok('the VIP address (VRRP) set and on', st_ == 200 and st2 == 200, (x, x2))
ka_on()
for _ in range(60):
    if vip_master():
        break
    time.sleep(2)
HOLD = vip_master()
ok('keepalived: one node holds the VIP address (%s)' % HOLD, bool(HOLD))


def tls(n, target):
    _, d = call(n, '/api/web')
    return (d.get('tls') or {}).get(target) or {}


# ---- the VIP's certificate: uploaded alone on a, completed on b ---------------------------------
st_, x = call('a', '/api/web', {'action': 'tls_upload', 'target': 'vip', 'cert': rd('vip.pem'), 'key': rd('vip.key')})
ok('node a: the VIP\'s certificate uploaded alone, the CA Issuers address down - kept, incomplete',
   st_ == 200 and x.get('complete') is False and 'incomplete' in x.get('message', ''), x)
def until(fn, secs=60):
    end = time.time() + secs
    while time.time() < end:
        if fn():
            return True
        time.sleep(2)
    return False


ok('...node b sees it incomplete too (replication)', until(lambda: (tls('b', 'vip').get('chain_state') or {}).get('ok') is False))
os.rename(P + '/int.cer.away', WWW + '/int.cer')
st_, x = call('b', '/api/web', {'action': 'tls_chain', 'target': 'vip'})
ok('node b: Complete the chain - the intermediate fetched, complete', st_ == 200 and x.get('complete') is True and
   'fetched: T269HA Issuing CA' in x.get('message', ''), x)


def same_chain(target, want):
    for _ in range(40):
        a, b = tls('a', target), tls('b', target)
        if want in (a.get('chain') or '') and want in (b.get('chain') or ''):
            return True
        time.sleep(2)
    return False


INT = rd('int.pem').strip()
ok('both nodes hold the completed chain of the VIP\'s certificate', same_chain('vip', INT))


def file_has(n, name, wait=120):
    p = '%s/%s/certs/%s' % (S, n, name)
    for _ in range(wait // 2):
        try:
            t = open(p).read()
            if t.count('BEGIN CERTIFICATE') == 2 and INT in t:
                return True
        except OSError:
            pass
        time.sleep(2)
    return False


hold_n = 'a' if 'a' in str(HOLD) else 'b'
ok('nginx\'s file of the VIP on the node holding it (%s): the certificate and the intermediate' % hold_n, file_has(hold_n, 'otp-vip.pem'))


def web_of(via, node):
    _, d = call(via, '/api/web')
    return next((n.get('web') or {} for n in d.get('nodes') or [] if n.get('name') == node), {})


ok('the page: the VIP\'s file in place on the holder checked complete (vip_cert_now.chain_ok)',
   until(lambda: all((web_of(v, 'node' + hold_n).get('vip_cert_now') or {}).get('chain_ok') is True for v in 'ab'), 120))
# ---- node a's own certificate, completed online asked on b; node b's by hand asked on a ------------
os.rename(WWW + '/int.cer', P + '/int.cer.away')
st_, x = call('a', '/api/web', {'action': 'tls_upload', 'target': 'nodea', 'cert': rd('na.pem'), 'key': rd('na.key')})
st2, x2 = call('a', '/api/web', {'action': 'tls_upload', 'target': 'nodeb', 'cert': rd('nb.pem'), 'key': rd('nb.key')})
ok('both nodes\' own certificates uploaded alone (the address down, nothing kept from before): incomplete',
   x.get('complete') is False and x2.get('complete') is False, (x.get('message'), x2.get('message')))
st_, x = call('a', '/api/web', {'action': 'tls_chain_add', 'target': 'nodeb', 'text': rd('int.pem')})
ok('node a: Upload the missing authority for node b\'s certificate - complete', st_ == 200 and x.get('complete') is True, x)
os.rename(P + '/int.cer.away', WWW + '/int.cer')
st_, x = call('b', '/api/web', {'action': 'tls_chain', 'target': 'nodea'})
ok('node b: Complete the chain of node a\'s certificate - complete', st_ == 200 and x.get('complete') is True, x)
ok('node a\'s nginx file: the certificate and the intermediate', file_has('a', 'otp.pem'))
ok('node b\'s nginx file: the certificate and the intermediate', file_has('b', 'otp.pem'))
ok('the page of either node: each node\'s file in place checked complete (cert_now.chain_ok)',
   until(lambda: all((web_of(v, 'node' + n).get('cert_now') or {}).get('chain_ok') is True for v in 'ab' for n in 'ab'), 120))
httpd.shutdown()
shutil.rmtree(P, ignore_errors=True)
sandbox_daemons_stop()
done()
