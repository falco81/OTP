# t_chain.py VERSION - the whole chain of the pages' certificates (1.0.269): a hierarchy of our own (a root,
# an intermediate published at a local CA Issuers address, a certificate), the system's roots replaced by our
# root (OTP_CHAIN_CA). Uploaded alone it is completed by fetching; with the intermediate nothing is fetched;
# with the root the root stays aside; the address down: incomplete, and the missing authority uploaded by hand
# completes it; a private CA without the root: incomplete, its root uploaded: complete "a private root";
# self-signed: no chain; the file nginx has is checked; nginx checked as a client that fetches nothing (a local
# TLS server sending the certificate alone, then with its chain); the actions answer 'complete', never ok:false.
# A private state folder (OTP_STATE) - the live installation is never touched.
import os, sys, json, subprocess, tempfile, shutil, atexit, threading, http.server, socketserver, ssl, socket, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.269'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:500]))


TOP = tempfile.mkdtemp(prefix='t269-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
P = TOP + '/pki'
os.makedirs(P)
os.makedirs(TOP + '/www')


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, cwd=P, **k)


# -- a web server for the CA Issuers address
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=TOP + '/www', **k)

    def log_message(self, *a):
        pass


httpd = socketserver.TCPServer(('127.0.0.1', 0), Q)
HPORT = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
AIA = 'http://127.0.0.1:%d/int.cer' % HPORT

open(P + '/ca.ext', 'w').write('basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
open(P + '/leaf.ext', 'w').write('basicConstraints=CA:FALSE\nsubjectAltName=DNS:portal.example.test\n'
                                 'authorityInfoAccess=caIssuers;URI:%s\n' % AIA)
open(P + '/leaf2.ext', 'w').write('basicConstraints=CA:FALSE\nsubjectAltName=DNS:portal.example.test\n')
sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'root.key', '-out', 'root.pem', '-days', '3650',
   '-subj', '/CN=T269 Root CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'int.key', '-out', 'int.csr', '-subj', '/CN=T269 Issuing CA')
sh('openssl', 'x509', '-req', '-in', 'int.csr', '-CA', 'root.pem', '-CAkey', 'root.key', '-CAcreateserial', '-out', 'int.pem',
   '-days', '1825', '-extfile', 'ca.ext')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'leaf.key', '-out', 'leaf.csr', '-subj', '/CN=portal.example.test')
sh('openssl', 'x509', '-req', '-in', 'leaf.csr', '-CA', 'int.pem', '-CAkey', 'int.key', '-CAcreateserial', '-out', 'leaf.pem',
   '-days', '200', '-extfile', 'leaf.ext')
sh('openssl', 'x509', '-in', 'int.pem', '-outform', 'DER', '-out', TOP + '/www/int.cer')
# a private CA (its root not among the system's), no CA Issuers address
sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'proot.key', '-out', 'proot.pem', '-days', '3650',
   '-subj', '/CN=T269 Private Root', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'leaf2.key', '-out', 'leaf2.csr', '-subj', '/CN=portal.example.test')
sh('openssl', 'x509', '-req', '-in', 'leaf2.csr', '-CA', 'proot.pem', '-CAkey', 'proot.key', '-CAcreateserial', '-out', 'leaf2.pem',
   '-days', '200', '-extfile', 'leaf2.ext')
rd = lambda f: open(P + '/' + f).read()
ok('the hierarchy made (root, intermediate at %s, certificate; a private root)' % AIA,
   all(os.path.exists(P + '/' + f) for f in ('root.pem', 'int.pem', 'leaf.pem', 'proot.pem', 'leaf2.pem')))

os.makedirs(TOP + '/run')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32960, 'radius_acct_port': 32961,
           'api_port': 29961, 'node_name': 't269'}, open(TOP + '/config.json', 'w'))
ENV = {'OTP_STATE': TOP, 'OTP_CONFIG': TOP + '/config.json', 'OTP_LOGDIR': TOP, 'OTP_RUN': TOP + '/run',
       'OTP_STAY_ROOT': '1', 'OTP_CHAIN_CA': P + '/root.pem', 'OTP_VIP_CERT_DIR': TOP + '/certs'}
os.environ.update(ENV)
sys.path.insert(0, V); sys.argv = ['x']
import otp
assert str(otp.STATE_DIR) == TOP
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)

# ---- cert_bundle: every way a certificate comes in --------------------------------------------
g = otp.cert_bundle(rd('leaf.pem'), rd('leaf.key'))
cs = g['chain_state']
ok('the certificate alone: its chain completed from the CA Issuers address', cs.get('ok') is True and
   cs.get('fetched') == ['T269 Issuing CA'] and 'T269 Issuing CA' in g['chain'] or rd('int.pem').strip() in g['chain'], cs)
ok('...nginx gets the certificate and the intermediate, never the root',
   otp.PEM_CERT.findall(g['chain']) and rd('root.pem').strip() not in g['chain'] and g['verify'] == 'ok', g['chain'][:80])
ok('...said: complete, 2 certificates up to the root, fetched', cs.get('words', '').startswith('complete - 2 certificates up to T269 Root CA (fetched: T269 Issuing CA'), cs.get('words'))
os.rename(TOP + '/www/int.cer', TOP + '/www/int.cer.away')
otp.CHAIN_FETCHED.clear()
g = otp.cert_bundle(rd('leaf.pem') + rd('int.pem'), rd('leaf.key'))
ok('with the intermediate: complete, nothing fetched (the address is down)', g['chain_state'].get('ok') is True and not g['chain_state'].get('fetched'), g['chain_state'])
g = otp.cert_bundle(rd('root.pem') + rd('leaf.pem') + rd('int.pem'), rd('leaf.key'))
ok('with the root, in any order: the root aside, the chain the intermediate alone',
   g['chain_state'].get('ok') is True and len(otp.PEM_CERT.findall(g['chain'])) == 1 and 'T269 Root CA' in json.dumps(g['root_info']), g['chain_state'])
g = otp.cert_bundle(rd('leaf.pem'), rd('leaf.key'))
cs = g['chain_state']
ok('the address down: incomplete, the missing authority named, why said', cs.get('ok') is False and cs.get('missing') == 'T269 Issuing CA'
   and 'could not be fetched' in cs.get('words', ''), cs)
g = otp.cert_bundle(rd('leaf2.pem'), rd('leaf2.key'))
cs = g['chain_state']
ok('a private CA without its root: incomplete - no CA Issuers address', cs.get('ok') is False and 'names no CA Issuers address' in cs.get('words', ''), cs)
g = otp.cert_bundle(rd('leaf2.pem') + rd('proot.pem'), rd('leaf2.key'))
cs = g['chain_state']
ok('...with its root given: complete, "a private root"', cs.get('ok') is True and 'a private root' in cs.get('words', ''), cs)
key, crt = otp.make_selfsigned('self.example.test', ['self.example.test'])
g = otp.cert_bundle(crt, key)
ok('self-signed: no chain (ok null), nothing said wrong', g['chain_state'].get('ok') is None and g['verify'] == '', g['chain_state'])

# ---- the file nginx has --------------------------------------------------------------------------
os.makedirs(TOP + '/certs', exist_ok=True)
f1 = TOP + '/certs/a.pem'
open(f1, 'w').write(rd('leaf.pem'))
ok('the file nginx has, the certificate alone: chain_ok false', otp.cert_now(f1).get('chain_ok') is False)
time.sleep(1.1)
open(f1, 'w').write(rd('leaf.pem') + rd('int.pem'))
ok('...with its intermediate: chain_ok true (read again when the file changed)', otp.cert_now(f1).get('chain_ok') is True)


# ---- the actions, as the pages ask them (the node's own certificate) -----------------------------
def api(body):
    g = subprocess.run([sys.executable, V + '/otp.py', '--api', 'POST', '/api/web', '-'], input=json.dumps(body),
                       capture_output=True, text=True, env=dict(os.environ, **ENV), timeout=120)
    try:
        return json.loads(g.stdout), g
    except ValueError:
        return {'_raw': g.stdout[-300:] + g.stderr[-300:]}, g


x, g = api({'action': 'tls_upload', 'target': 't269', 'cert': rd('leaf.pem'), 'key': rd('leaf.key')})
ok('upload of the certificate alone, the address down: kept, its chain said incomplete', x.get('complete') is False and
   'incomplete' in x.get('message', '') and 'ok' not in x, x)
ok('...the card has it: chain_state incomplete, missing T269 Issuing CA', (x.get('tls') or {}).get('chain_state', {}).get('missing') == 'T269 Issuing CA', x.get('tls'))
x, g = api({'action': 'tls_chain_add', 'target': 't269', 'text': rd('leaf.key')})
ok('the missing authority: a private key refused', 'no private key' in json.dumps(x), x)
x, g = api({'action': 'tls_chain_add', 'target': 't269', 'text': rd('proot.pem')})
ok('...an authority that is not the one missing refused, named', "none of these is the authority" in json.dumps(x) and 'T269 Issuing CA' in json.dumps(x), x)
x, g = api({'action': 'tls_chain_add', 'target': 't269', 'text': rd('int.pem')})
ok('...the intermediate uploaded by hand: complete', x.get('complete') is True and x.get('message', '').startswith('complete - 2 certificates'), x)
prof = otp.tls_profile(st, 't269')
ok('...kept in the chain nginx is given', rd('int.pem').strip() in (prof.get('chain') or '') and rd('root.pem').strip() not in (prof.get('chain') or ''))
x, g = api({'action': 'tls_upload', 'target': 't269', 'cert': rd('leaf.pem'), 'key': rd('leaf.key')})
os.rename(TOP + '/www/int.cer.away', TOP + '/www/int.cer')
x, g = api({'action': 'tls_chain', 'target': 't269'})
ok('Complete the chain with the address up again: fetched, complete', x.get('complete') is True and 'fetched: T269 Issuing CA' in x.get('message', ''), x)
x, g = api({'action': 'tls_chain', 'target': 't269'})
ok('Check the chain again: complete, nothing more fetched', x.get('complete') is True and 'fetched' not in x.get('message', ''), x)
x, g = api({'action': 'tls_upload', 'target': 't269', 'cert': rd('leaf2.pem'), 'key': rd('leaf2.key')})
ok('a private CA uploaded without its root: incomplete', x.get('complete') is False, x)
x, g = api({'action': 'tls_chain_add', 'target': 't269', 'text': rd('proot.pem')})
ok('...its root uploaded by hand: complete, a private root, the root named on the card', x.get('complete') is True and
   'a private root' in x.get('message', '') and 'T269 Private Root' in json.dumps((x.get('tls') or {}).get('root_info')), x)
ok('...the root kept to check with, never in the chain', rd('proot.pem').strip() not in (otp.tls_profile(st, 't269').get('chain') or ''))


# ---- nginx as a client that fetches nothing sees it -----------------------------------------------
def tls_server(certfile, keyfile):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(4)

    def run():
        while True:
            try:
                c, _ = s.accept()
            except OSError:
                return
            try:
                ctx.wrap_socket(c, server_side=True).close()
            except (OSError, ssl.SSLError):
                c.close()
    threading.Thread(target=run, daemon=True).start()
    return s, s.getsockname()[1]


prof1 = {'cert': rd('leaf.pem'), 'info': otp.cert_info(rd('leaf.pem'))}
open(P + '/alone.pem', 'w').write(rd('leaf.pem'))
s1, p1 = tls_server(P + '/alone.pem', P + '/leaf.key')
got = otp.web_self_check(prof1, port=p1)
ok('nginx sending the certificate alone: a client that fetches nothing refuses it', got and got.get('ok') is False and 'refuses' in got.get('words', ''), got)
open(P + '/full.pem', 'w').write(rd('leaf.pem') + rd('int.pem'))
s2, p2 = tls_server(P + '/full.pem', P + '/leaf.key')
got = otp.web_self_check(prof1, port=p2)
ok('...with its chain: the whole chain is sent', got and got.get('ok') is True, got)
s1.close(); s2.close(); httpd.shutdown()
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
