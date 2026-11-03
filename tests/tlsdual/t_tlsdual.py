# t_tlsdual.py VERSION - an RSA and an ECDSA certificate of the same names (1.0.240): uploaded together (both keys
# in the PEM, or two PFX files) - the RSA one the main, the ECDSA one beside; one alone as until now (and the second
# one dropped); two RSA, other names, three keys refused. Downloaded: the main one, the ECDSA one, or both in a .zip,
# each key locked; the second asked of a certificate without one refused. The CLI's --tls-import the same.
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, base64, io, zipfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.240'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-dual-'); run = D + '/run'; os.makedirs(run)
APORT = 29897
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run, OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 31962, 'radius_acct_port': 31963,
           'api_port': APORT, 'node_name': 'dual1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


W = D + '/pki'; os.makedirs(W)


def ossl(*a, inp=None):
    r = subprocess.run(['openssl'] + list(a), capture_output=True, input=inp, cwd=W)
    if r.returncode:
        raise SystemExit('openssl %s: %s' % (a[:3], r.stderr.decode()[-300:]))
    return r.stdout


ossl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '30', '-subj', '/CN=Dual Test CA')
open(W + '/ext', 'w').write('subjectAltName=DNS:dual.example.cz,DNS:www.dual.example.cz\n')
open(W + '/ext2', 'w').write('subjectAltName=DNS:other.example.cz\n')


def leaf(name, kind, ext='ext'):
    if kind == 'rsa':
        ossl('genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', name + '.key')
    else:
        ossl('genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-384', '-out', name + '.key')
    ossl('req', '-new', '-key', name + '.key', '-out', name + '.csr', '-subj', '/CN=dual.example.cz')
    ossl('x509', '-req', '-in', name + '.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial', '-out', name + '.pem',
         '-days', '20', '-extfile', ext)
    ossl('pkcs12', '-export', '-inkey', name + '.key', '-in', name + '.pem', '-certfile', 'ca.pem', '-passout', 'pass:pfxpass12',
         '-out', name + '.pfx')
    return open(W + '/' + name + '.pem').read(), open(W + '/' + name + '.key').read(), open(W + '/' + name + '.pfx', 'rb').read()


R1, RK1, RP1 = leaf('r1', 'rsa'); E1, EK1, EP1 = leaf('e1', 'ec'); R2, RK2, _ = leaf('r2', 'rsa')
X1, XK1, _ = leaf('x1', 'ec', 'ext2')
CA = open(W + '/ca.pem').read()
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']


def up(**kw):
    return call('/api/web', dict({'action': 'tls_upload', 'target': 'dual1'}, **kw), S)


def prof():
    return otp.tls_profile(st, 'dual1') or {}


c, x = up(cert=R1 + RK1 + CA)
ok('one RSA certificate alone: in, as until now (%s)' % c, c == 200 and not (x.get('tls') or {}).get('alt'), x)
c, x = up(cert=R1 + RK1 + E1 + EK1 + CA)
alt = (x.get('tls') or {}).get('alt') or {}
ok('RSA and ECDSA in one PEM: both in (%s)' % c, c == 200 and alt.get('info', {}).get('key', '').startswith('EC'), x)
p = prof()
ok('...the RSA one the main, the ECDSA one beside, tied to it', (p.get('info') or {}).get('key', '').startswith('RSA') and otp.tls_alt(p)
   and 'BEGIN CERTIFICATE' in otp.tls_alt(p)['cert'], p.get('info'))
ok('...the ECDSA key sealed, not in the clear', 'PRIVATE KEY' not in json.dumps(p.get('alt') or {}))
ok('...nginx would be handed both', 'alt' in (otp.tls_resolved(p) or {}))
va = otp.tls_view(p).get('alt') or {}
ok('...the view shows the second one, never its key', va.get('info') and set(va) == {'info'} and 'PRIVATE KEY' not in json.dumps(va), va)
c, x = up(cert=E1 + EK1 + R1 + RK1)
ok('the other order: the same (%s)' % c, c == 200 and (x.get('tls') or {}).get('alt') and prof()['info']['key'].startswith('RSA'))
c, x = up(pfx=base64.b64encode(RP1).decode(), pfx2=base64.b64encode(EP1).decode(), password='pfxpass12')
ok('two PFX files: both in (%s)' % c, c == 200 and (x.get('tls') or {}).get('alt'), x)
c, x = up(pfx=base64.b64encode(EP1).decode(), pfx2=base64.b64encode(RP1).decode(), password='pfxpass12')
ok('...the ECDSA one first: still RSA the main (%s)' % c, c == 200 and prof()['info']['key'].startswith('RSA'), prof().get('info'))
c, x = up(pfx=base64.b64encode(RP1).decode(), cert=E1 + EK1, password='pfxpass12')
ok('a PFX and a PEM: both in (%s)' % c, c == 200 and (x.get('tls') or {}).get('alt'), x)
for what, kw in (('two RSA', dict(cert=R1 + RK1 + R2 + RK2)), ('other names', dict(cert=R1 + RK1 + X1 + XK1)),
                 ('three keys', dict(cert=R1 + RK1 + E1 + EK1 + R2 + RK2)), ('a key without its certificate', dict(cert=R1 + RK1 + EK1))):
    c, x = up(**kw)
    ok('%s: refused (%s) - %s' % (what, c, x.get('error')), c == 400, x)
ok('...what was in stays (both)', otp.tls_alt(prof()) is not None)
# downloads
def ex(kind, which, pw='a-long-passphrase'):
    return call('/api/web', {'action': 'tls_export', 'target': 'dual1', 'kind': kind, 'which': which, 'passphrase': pw}, S)


c, x = ex('pemkey', 'rsa')
t = base64.b64decode(x.get('file', '')).decode()
ok('download the main one with its key: RSA, the key locked', c == 200 and 'ENCRYPTED PRIVATE KEY' in t and x['name'].endswith('-with-key.pem'), x.get('name'))
c, x = ex('pemkey', 'ec')
t = base64.b64decode(x.get('file', '')).decode()
k = subprocess.run(['openssl', 'pkey', '-passin', 'pass:a-long-passphrase', '-noout', '-text'], input=t.encode(), capture_output=True).stdout.decode()
ok('download the ECDSA one: its own key, locked (%s)' % x.get('name'), c == 200 and 'ENCRYPTED PRIVATE KEY' in t and 'ASN1 OID' in k and '-ecdsa' in x['name'], k[:100])
c, x = ex('pfx', 'both')
z = zipfile.ZipFile(io.BytesIO(base64.b64decode(x.get('file', ''))))
ok('both: a .zip of rsa.pfx and ecdsa.pfx (%s)' % x.get('name'), c == 200 and sorted(z.namelist()) == ['ecdsa.pfx', 'rsa.pfx'] and x['name'].endswith('.zip')
   and x['type'] == 'application/zip', z.namelist())
pk = subprocess.run(['openssl', 'pkcs12', '-nodes', '-passin', 'pass:a-long-passphrase'], input=z.read('ecdsa.pfx'), capture_output=True).stdout.decode()
ok('...each opens with the password, the ECDSA one holds the EC key', 'PRIVATE KEY' in pk and 'dual.example.cz' in pk, pk[:80])
c, x = ex('pem', 'ec', '')
ok('the ECDSA certificate alone, no key, no password asked', c == 200 and 'PRIVATE' not in base64.b64decode(x['file']).decode())
c, x = ex('pfx', 'both', 'short')
ok('a short password: refused (%s)' % c, c == 400)
ev = json.dumps(call('/api/events?limit=40', None, S)[1])
ok('the events say which, and with the key', 'both: RSA and ECDSA' in ev and 'WITH ITS PRIVATE KEY' in ev and 'a second one beside it' in ev, ev[:300])
c, x = up(cert=R1 + RK1 + CA)
ok('one alone again: the second one dropped', c == 200 and not (x.get('tls') or {}).get('alt') and 'alt' not in prof())
c, x = ex('pem', 'ec', '')
ok('...the ECDSA one asked of it: refused (%s)' % c, c == 400 and 'second' in str(x.get('error')), x)
c, x = ex('pem', 'nonsense', '')
ok('which: nonsense refused (%s)' % c, c == 400)
# the CLI
open(W + '/both.pem', 'w').write(R2 + RK2 + CA)
r = subprocess.run([sys.executable, V + '/otp.py', '--tls-import', W + '/r1.pfx', W + '/e1.pfx', '--tls-for', 'dual1'],
                   env=dict(env, OTP_TLS_PASSWORD='pfxpass12'), capture_output=True, text=True, timeout=120)
otp.load_config(saved=None)
ok('otp --tls-import two .pfx: both, said', r.returncode == 0 and 'second one beside it' in r.stdout and otp.tls_alt(prof()), r.stdout + r.stderr)
r = subprocess.run([sys.executable, V + '/otp.py', '--tls-import', W + '/both.pem', '--tls-for', 'dual1'], env=env, capture_output=True, text=True, timeout=120)
ok('...one alone: the second dropped', r.returncode == 0 and 'alt' not in prof(), r.stdout + r.stderr)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
