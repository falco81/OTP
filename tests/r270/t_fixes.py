# t_fixes.py VERSION - the fixes of 1.0.270, on the otp.py of that version loaded as a module (a private
# state folder - the live installation is never touched):
#  - the chain walk starts from the top of the certificate's own chain: an authority beside it of another
#    chain (the second key's, an old one) is not taken for the top - a public chain was a "private CA";
#  - a root reached that does not make the chain check is not called private: openssl's reason is said;
#  - a bad answer at a CA Issuers address never breaks cert_bundle (upload, ACME, acme push);
#  - CA Issuers addresses of this machine, link-local or on other ports are not asked (SSRF);
#  - a copy put back with a host:selinux:was row before the host:selinux:now row: no duplicate key;
#  - the root helper: Debian's group-writable anchors folder taken when its parent is as writable,
#    a sync with the files as wanted but the system's list without one runs the tool again;
#  - the SELinux report: a long audit log cut is not taken for a missing tool;
#  - the root helper never gives its own stdin to a program (ausearch read the otp command's pipe).
import atexit, gzip, http.server, importlib.util, json, os, re, shutil, socketserver, stat, subprocess, sys, tempfile
import threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.270'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t270-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
P = TOP + '/pki'
os.makedirs(P)
os.makedirs(TOP + '/www')


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, cwd=P)


class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=TOP + '/www', **k)

    def log_message(self, *a):
        pass


httpd = socketserver.TCPServer(('127.0.0.1', 0), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
AIA = 'http://127.0.0.1:%d/int.cer' % httpd.server_address[1]
open(P + '/ca.ext', 'w').write('basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
open(P + '/leaf.ext', 'w').write('basicConstraints=CA:FALSE\nsubjectAltName=DNS:portal.example.test\n'
                                 'authorityInfoAccess=caIssuers;URI:%s\n' % AIA)
for n in ('root', 'oroot'):
    sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', n + '.key', '-out', n + '.pem', '-days', '3650',
       '-subj', '/CN=T270 %s' % n, '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
for n, up in (('int', 'root'), ('oint', 'oroot')):
    sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', n + '.key', '-out', n + '.csr', '-subj', '/CN=T270 %s' % n)
    sh('openssl', 'x509', '-req', '-in', n + '.csr', '-CA', up + '.pem', '-CAkey', up + '.key', '-CAcreateserial', '-out', n + '.pem',
       '-days', '1825', '-extfile', 'ca.ext')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'leaf.key', '-out', 'leaf.csr', '-subj', '/CN=portal.example.test')
sh('openssl', 'x509', '-req', '-in', 'leaf.csr', '-CA', 'int.pem', '-CAkey', 'int.key', '-CAcreateserial', '-out', 'leaf.pem',
   '-days', '200', '-extfile', 'leaf.ext')
sh('openssl', 'x509', '-in', 'int.pem', '-outform', 'DER', '-out', TOP + '/www/int.cer')
rd = lambda f: open(P + '/' + f).read()

D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx270', 'api_port': 29971}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D,
                  OTP_CHAIN_CA=P + '/root.pem', OTP_AIA_LOCAL='1')
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)

# -- the chain
got = m.cert_bundle(cert=rd('leaf.pem') + rd('oint.pem'), key=rd('leaf.key'))
st = got['chain_state']
ok('an authority of another chain beside it: the walk fetches the certificate\'s own intermediate, complete',
   st.get('ok') is True and 'T270 int' in ' '.join(st.get('fetched') or []), st)
ok('...not called a private CA', not st.get('private_root'), st)
ok('...nginx gets the intermediate first', got['chain'].index(rd('int.pem').strip()) == 0 if rd('int.pem').strip() in got['chain'] else False)

# A root reached that does not make it check: the intermediate fetched is not this root's (a chain that
# does not verify) - its reason said, not "a private CA".
os.environ['OTP_CHAIN_CA'] = P + '/oroot.pem'
m.CHAIN_FETCHED.clear()
order, rest = m.chain_order(rd('leaf.pem'), [rd('oint.pem'), rd('int.pem')])
ok('chain_order: the certificate\'s own first, the other aside', order == [rd('int.pem')] and rest == [rd('oint.pem')])
os.environ['OTP_CHAIN_CA'] = P + '/root.pem'

# A bad answer at the address: nothing breaks.
open(TOP + '/www/int.cer', 'w').write('-----BEGIN CERTIFICATE-----\nnot base64 at all\n-----END CERTIFICATE-----\n')
m.CHAIN_FETCHED.clear()
try:
    got = m.cert_bundle(cert=rd('leaf.pem'), key=rd('leaf.key'))
    ok('a broken answer at the CA Issuers address: the upload goes on, the chain incomplete',
       got['chain_state'].get('ok') in (False, None), got['chain_state'])
except Exception as e:                                  # noqa: BLE001
    ok('a broken answer at the CA Issuers address: the upload goes on', False, e)
sh('openssl', 'x509', '-in', 'int.pem', '-outform', 'DER', '-out', TOP + '/www/int.cer')

# SSRF
os.environ.pop('OTP_AIA_LOCAL')
for url, why in (('http://127.0.0.1/x.cer', 'this machine'), ('http://169.254.169.254/latest/meta-data/', 'link-local'),
                 ('http://[::1]/x.cer', 'this machine (IPv6)'), ('http://example.test:8080/x.cer', 'another port'),
                 ('ftp://example.test/x.cer', 'not http')):
    try:
        m.aia_url_ok(url)
        ok('a CA Issuers address of %s refused' % why, False, url)
    except ValueError:
        ok('a CA Issuers address of %s refused' % why, True)
try:
    m.aia_url_ok('http://10.20.30.40/pki/int.cer')
    ok('a company\'s own address (10.x) is asked', True)
except ValueError as e:
    ok('a company\'s own address (10.x) is asked', False, e)
m.CHAIN_FETCHED.clear()
got = m.cert_bundle(cert=rd('leaf.pem'), key=rd('leaf.key'))
ok('...the local address from a certificate: not fetched, said', got['chain_state'].get('ok') is False and
   re.search(r'not asked|only 80 and 443 are asked', got['chain_state'].get('words', '')), got['chain_state'])
os.environ['OTP_AIA_LOCAL'] = '1'

# -- a copy put back: the was row before the now row
st_ = m.Storage(m.open_db())
st_.db.make_tables()
src = TOP + '/copy.json.gz'
with gzip.open(src, 'wt', encoding='utf-8') as f:
    f.write(json.dumps({'otp': '1.0.268'}) + '\n')
    f.write(json.dumps({'table': 'meta'}) + '\n')
    f.write(json.dumps({'k': 'host:selinux:was:fx270', 'v': json.dumps({'mode': 'Permissive', 'at': 1})}) + '\n')
    f.write(json.dumps({'k': 'something', 'v': '1'}) + '\n')
    f.write(json.dumps({'k': 'host:selinux:now:fx270', 'v': json.dumps({'data': {'mode': 'Enforcing'}})}) + '\n')
try:
    m._load_tables(st_.db, src, True, None, gzip)
    row = st_.db.value("SELECT v FROM meta WHERE k = 'host:selinux:was:fx270'")
    ok('a copy with the was row before the now row: put back, no duplicate key', True)
    ok('...the mode the copy\'s node had then is kept (Enforcing)', json.loads(row or '{}').get('mode') == 'Enforcing', row)
except Exception as e:                                  # noqa: BLE001
    ok('a copy with the was row before the now row: put back, no duplicate key', False, e)

# -- the root helper
spec2 = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
w = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(w)
A = TOP + '/local'
os.makedirs(A + '/ca-certificates')
if os.geteuid() == 0:
    os.chown(A, 0, 50 if os.path.exists('/etc/group') else 0)
    os.chmod(A, 0o2775)
    os.chown(A + '/ca-certificates', 0, 50)
    os.chmod(A + '/ca-certificates', 0o2775)
    try:
        ok('Debian: an anchors folder as writable by the group as its parent (2775 root:staff) is taken',
           w.osroots_dir_ok(A + '/ca-certificates') is True)
    except w.Refused as e:
        ok('Debian: an anchors folder as writable by the group as its parent (2775 root:staff) is taken', False, e)
    os.chmod(A, 0o755)
    try:
        w.osroots_dir_ok(A + '/ca-certificates')
        ok('...one writable by a group its parent is not: refused', False)
    except w.Refused:
        ok('...one writable by a group its parent is not: refused', True)
    os.chmod(A + '/ca-certificates', 0o777)
    try:
        w.osroots_dir_ok(A + '/ca-certificates')
        ok('...one writable by everybody: refused', False)
    except w.Refused:
        ok('...one writable by everybody: refused', True)
    os.chmod(A + '/ca-certificates', 0o755)

    # the files as wanted, the system's list without them: the tool run again
    tool = TOP + '/tool.sh'
    bundle = TOP + '/bundle.pem'
    open(tool, 'w').write('#!/bin/sh\necho ran >> %s/ran\ncat %s/*.crt > %s\n' % (TOP, A + '/ca-certificates', bundle))
    os.chmod(tool, 0o755)
    flav = {'flavour': 'debian', 'dir': A + '/ca-certificates', 'ext': '.crt', 'tool': [tool], 'bundle': bundle}
    pem = w.osroots_blocks(rd('root.pem'))[0][0]
    w.osroots_sync(flav, [pem])
    n1 = open(TOP + '/ran').read().count('ran')
    w.osroots_sync(flav, [pem])
    n2 = open(TOP + '/ran').read().count('ran')
    ok('a sync with nothing changed and the list as wanted: the tool not run again', n1 == 1 and n2 == 1, (n1, n2))
    open(bundle, 'w').write('')
    said, _r = w.osroots_sync(flav, [pem])
    n3 = open(TOP + '/ran').read().count('ran')
    ok('the files as wanted, the system\'s list without one (the tool failed before): the tool run again',
       n3 == 2 and any('lacked' in x for x in said), (n3, said))
else:
    ok('the root helper\'s folder checks (root only - skipped)', True)

# -- the SELinux report: a long log cut
src_ = open(V + '/deploy/otp_web.py').read()
ok('the report: a cut log is not taken for a missing tool', "not raw.startswith('(the first ')" in src_)
ok('the root helper gives programs /dev/null, never its own stdin', src_.count('stdin=subprocess.DEVNULL, capture_output=True') >= 2)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
