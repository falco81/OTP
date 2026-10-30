# isemon over TLS (1.0.172): one daemon, a TLS syslog receiver standing in
# for isemon's rsyslog (gtls) - the bundle for isemon made by otp and opened
# with its passphrase, tried, switched over, lines arriving encrypted with the
# node's own certificate (mutual TLS), a wrong authority and a missing client
# certificate said so, switched off. Usage (as root): python3 t_isemontls.py VERSION
import os, sys, json, time, ssl, socket, base64, io, zipfile, subprocess, urllib.request, tempfile, atexit, threading

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.172'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-isetls-')
os.makedirs(D + '/run')
API = 30791
PORT = 36514
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36810, 'radius_acct_port': 36811,
           'api_port': API, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1',
           OTP_HA_CA=D + '/ha-ca.pem')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-172!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-172!'})[1]['token']


def ask(body):
    c, x = call('/api/isemon', body, S)
    if c != 200:
        return c, x
    for _ in range(40):
        time.sleep(0.5)
        c, r = call('/api/isemon', {'action': 'tls_result', 'id': x['id']}, S)
        got = {k: v for k, v in r['nodes'].items() if v}
        if got:
            return 200, got
    return 0, {}


# ---- the bundle for isemon ----------------------------------------------------
c, x = call('/api/isemon', {'action': 'tls_bundle', 'host': 'localhost', 'port': PORT, 'names': 'localhost',
                            'mtls': True, 'passphrase': 'short'}, S)
ok('a bundle with a short passphrase refused (%s)' % c, c == 400)
PASS = 'a-long-passphrase-172'
c, x = call('/api/isemon', {'action': 'tls_bundle', 'host': 'localhost', 'port': PORT, 'names': 'localhost, 127.0.0.1',
                            'mtls': True, 'passphrase': PASS}, S)
ok('the bundle for isemon made (%s)' % c, c == 200 and x.get('name') == 'isemon-tls.zip', x)
raw = base64.b64decode(x.get('file') or '')
z = zipfile.ZipFile(io.BytesIO(raw))
names = sorted(i.filename for i in z.infolist())
ok('... ca.pem, isemon.crt, isemon.key, 10-otp-tls.conf, README.txt (%s)' % names,
   names == ['10-otp-tls.conf', 'README.txt', 'ca.pem', 'isemon.crt', 'isemon.key'])
ok('... every entry locked (AES)', all(i.compress_type == 99 for i in z.infolist()))
F = {i.filename: otp.zip_aes_open(raw, i, PASS).decode() for i in z.infolist()}
try:
    otp.zip_aes_open(raw, z.getinfo('isemon.key'), 'not-the-passphrase')
    wrong = False
except (ValueError, PermissionError):
    wrong = True
ok('... not opened with another passphrase', wrong)
conf = F['10-otp-tls.conf']
ok('... the rsyslog configuration: gtls on the port, the peers named', 'StreamDriver.Name="gtls"' in conf and
   'port="%d"' % PORT in conf and 'PermittedPeer=["otp1"]' in conf and 'x509/name' in conf, conf)
ok('... the key is not kept by otp', 'BEGIN' not in json.dumps(st.db.rows("SELECT v FROM meta WHERE k = 'isemon:server'")))
W = D + '/isemon'
os.makedirs(W)
for k, v in F.items():
    open(W + '/' + k, 'w').write(v)

# ---- isemon: a TLS syslog receiver ----------------------------------------------
LINES = []
PEERS = []


class Rx(threading.Thread):
    def __init__(self, require_client):
        super().__init__(daemon=True)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(W + '/isemon.crt', W + '/isemon.key')
        ctx.load_verify_locations(W + '/ca.pem')
        ctx.verify_mode = ssl.CERT_REQUIRED if require_client else ssl.CERT_NONE
        self.ctx = ctx
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(('127.0.0.1', PORT))
        self.s.listen(5)
        self.stop = False
        self.conns = []

    def run(self):
        while not self.stop:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            threading.Thread(target=self.one, args=(c,), daemon=True).start()

    def one(self, c):
        try:
            t = self.ctx.wrap_socket(c, server_side=True)
        except (ssl.SSLError, OSError):
            c.close()
            return
        self.conns.append(t)
        cert = t.getpeercert()
        PEERS.append(dict(x[0] for x in cert['subject'])['commonName'] if cert else None)
        buf = b''
        t.settimeout(30)
        try:
            while True:
                got = t.recv(65536)
                if not got:
                    break
                buf += got
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    LINES.append(line.decode('utf-8', 'replace'))
        except (OSError, ssl.SSLError):
            pass

    def close(self):
        self.stop = True
        for t in self.conns:
            try:
                t.shutdown(socket.SHUT_RDWR)        # as a restarted rsyslog: the connection closed
            except OSError:
                pass
            try:
                t.close()
            except OSError:
                pass
        try:
            self.s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.s.close()


rx = Rx(True)
rx.start()
c, got = ask({'action': 'tls_probe', 'host': 'localhost', 'port': PORT, 'ca_source': 'system', 'verify': True, 'mtls': True})
g = got.get('otp1') or {}
ok('tried with the system\'s authorities: isemon\'s certificate refused, said where', c == 200 and g.get('ok') is False and
   any(s['what'].startswith('TLS') and not s['ok'] for s in g.get('steps', [])), g)
c, got = ask({'action': 'tls_probe', 'host': 'localhost', 'port': PORT, 'ca_source': 'otp', 'verify': True, 'mtls': False})
g = got.get('otp1') or {}
ok('tried without a certificate of its own where isemon wants one: said so', c == 200 and g.get('ok') is False, g)
c, got = ask({'action': 'tls_probe', 'host': 'localhost', 'port': PORT, 'ca_source': 'otp', 'verify': True, 'mtls': True})
g = got.get('otp1') or {}
ok('tried with otp\'s authority and the node\'s own certificate: it goes', c == 200 and g.get('ok') is True and
   g.get('version', '').startswith('TLS'), g)
ok('... isemon\'s certificate shown (localhost, otp\'s authority)', 'localhost' in json.dumps(g.get('cert')), g.get('cert'))
ok('... the node\'s certificate made, its key 0600', os.path.exists(D + '/isemon-client.crt') and
   oct(os.stat(D + '/isemon-client.key').st_mode & 0o777) == '0o600')
ok('... isemon saw the node by its name', 'otp1' in PEERS, PEERS)
ok('... and took the test line', any('a TLS test from otp' in x for x in LINES), LINES[-3:])

c, x = call('/api/isemon', {'action': 'tls_apply', 'host': 'localhost', 'port': PORT, 'ca_source': 'otp', 'verify': True,
                            'mtls': True}, S)
ok('switched over (%s)' % c, c == 200, x)
time.sleep(4)
cfg = {r['key']: r for r in call('/api/settings', None, S)[1]['settings']}
ok('... targets: localhost:%d/tls' % PORT, cfg['isemon_targets']['value'] == 'localhost:%d/tls' % PORT, cfg['isemon_targets']['value'])
ok('... the authority kept is otp\'s, mutual TLS on', 'BEGIN CERTIFICATE' in str(cfg['isemon_ca']['value']) and
   cfg['isemon_mtls']['value'] in (1, True))
n0 = len(LINES)
c, x = call('/api/isemon', {}, S)
for _ in range(20):
    time.sleep(0.5)
    if len(LINES) > n0:
        break
ok('a test line from the node arrives over TLS', any('isemon reads nothing from this line' in l for l in LINES[n0:]), LINES[-2:])
v = call('/api/isemon', None, S)[1]
me = [n for n in v['nodes'] if n.get('me')][0]
ok('... counted as sent to localhost:%d/tls, no trouble' % PORT, me.get('sent', {}).get('localhost:%d/tls' % PORT) and
   not me.get('trouble'), me)
ok('... the page knows: TLS, verified, mutual, otp\'s authority', v['tls']['tls'] and v['tls']['verify'] and v['tls']['mtls']
   and v['tls']['ca_is_otp'], v['tls'])

# isemon restarted with a server that does not want the node's certificate - lines still go
rx.close()
time.sleep(1)
rx = Rx(False)
rx.start()
n0 = len(LINES)
call('/api/isemon', {}, S)
for _ in range(60):
    time.sleep(0.5)
    if len(LINES) > n0:
        break
ok('isemon gone and back: the shipper connects again', len(LINES) > n0,
   [x for x in call('/api/isemon', None, S)[1]['nodes'] if x.get('me')])

c, x = call('/api/isemon', {'action': 'tls_off', 'host': 'localhost'}, S)
time.sleep(2)
cfg = {r['key']: r for r in call('/api/settings', None, S)[1]['settings']}
ok('switched off: back to plain TCP on 514', c == 200 and cfg['isemon_targets']['value'] == 'localhost:514/tcp',
   cfg['isemon_targets']['value'])
rx.close()
print('ALL %d / %d' % (sum(R), len(R)))
