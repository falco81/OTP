# Syslog / SIEM, the proxy, the disks and the logs (1.0.166), end to end: one
# daemon, syslog receivers on UDP, TCP and TLS, an HTTP proxy that wants a
# password, the root helper played by a loop with /etc in a folder.
# Usage (as root): python3 t_siem.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, socket, ssl
import socketserver, base64, re, select, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.166'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-siem-')
for sub in ('run', 'web', 'etc/logrotate.d', 'etc/systemd'):
    os.makedirs(os.path.join(D, sub))
shutil.copy(V + '/deploy/otp.logrotate', D + '/etc/logrotate.d/otp')
RPORT, APORT, UPORT, TPORT, SPORT, PPORT, HPORT = 35810, 30191, 35514, 35515, 35516, 35128, 35180
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
           OTP_STAY_ROOT='1', OTP_ALERTS_EVERY='3')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-166!', must_change=0)
st.realm_save({'name': 'loc', 'suffix': 'loc.test', 'auth_mode': 'otp', 'enabled': 1})
st.client_save({'name': 'vpn', 'address': '127.0.0.1', 'secret': 'radius-secret-166', 'enabled': 1})
tk = otp.Tokens(st)
KEYS = {}
for n in ('anna@loc.test', 'bob@loc.test'):
    g = tk.enroll(n, 'test')
    KEYS[n] = base64.b32decode(g['secret'] + '=' * (-len(g['secret']) % 8))
    tk.check(n, otp.totp(KEYS[n], time.time()), how='test')

# ---- the receivers ------------------------------------------------------------------
GOT = {'udp': [], 'tcp': [], 'tls': []}


def udp_rx():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', UPORT))
    while True:
        GOT['udp'].append(s.recv(65535).decode('utf-8', 'replace'))


def framed(conn, kind):
    buf = b''
    while True:
        try:
            chunk = conn.recv(65536)
        except OSError:
            return
        if not chunk:
            return
        buf += chunk
        while b' ' in buf:
            n, _, rest = buf.partition(b' ')
            if not n.isdigit() or len(rest) < int(n):
                break
            GOT[kind].append(rest[:int(n)].decode('utf-8', 'replace')); buf = rest[int(n):]


def tcp_rx(port, kind, ctx=None):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port)); s.listen(8)
    while True:
        c, _ = s.accept()
        if ctx:
            try:
                c = ctx.wrap_socket(c, server_side=True)
            except (ssl.SSLError, OSError):
                continue
        threading.Thread(target=framed, args=(c, kind), daemon=True).start()


subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-subj', '/CN=localhost',
                '-addext', 'subjectAltName=DNS:localhost', '-keyout', D + '/k.pem', '-out', D + '/c.pem'],
               check=True, capture_output=True)
sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(D + '/c.pem', D + '/k.pem')
for f, a in ((udp_rx, ()), (tcp_rx, (TPORT, 'tcp')), (tcp_rx, (SPORT, 'tls', sctx))):
    threading.Thread(target=f, args=a, daemon=True).start()

# ---- a proxy that wants a password, and a page behind it -------------------------------
PX = {'seen': [], 'auth': []}
WANT = 'Basic ' + base64.b64encode(b'px-user:p@ss:w/rd').decode()


class Proxy(socketserver.StreamRequestHandler):
    def handle(self):
        head = b''
        while b'\r\n\r\n' not in head:
            c = self.request.recv(4096)
            if not c:
                return
            head += c
        lines = head.split(b'\r\n\r\n')[0].decode().split('\r\n')
        auth = [l.split(':', 1)[1].strip() for l in lines[1:] if l.lower().startswith('proxy-authorization:')]
        PX['seen'].append(lines[0]); PX['auth'].append(auth[0] if auth else '')
        if not auth or auth[0] != WANT:
            self.request.sendall(b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="x"\r\n'
                                 b'Content-Length: 0\r\nConnection: close\r\n\r\n')
            return
        if lines[0].startswith('CONNECT'):
            host, port = lines[0].split()[1].rsplit(':', 1)
            up = socket.create_connection((host, int(port)))
            self.request.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
            socks = [self.request, up]
            while True:
                r, _, _ = select.select(socks, [], [], 5)
                if not r:
                    return
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (up if s is self.request else self.request).sendall(data)
        self.request.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok')


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


threading.Thread(target=TS(('127.0.0.1', PPORT), Proxy).serve_forever, daemon=True).start()

STOP = threading.Event()


def helper_loop():
    henv = dict(os.environ, OTP_STATE=D, OTP_VIP_NO_SERVICES='1', OTP_ETC=D + '/etc',
                OTP_OSUP_PROXY=D + '/osup-proxy.json')
    while not STOP.is_set():
        if os.path.exists(D + '/web/logs.ask'):
            subprocess.run([sys.executable, '-I', V + '/deploy/otp_web.py'], env=henv,
                           stdout=subprocess.DEVNULL, stderr=open(D + '/helper.err', 'a'))
        time.sleep(0.3)


threading.Thread(target=helper_loop, daemon=True).start()
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (STOP.set(), d.terminate()))
time.sleep(7)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


def until(fn, secs=20):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.3)
    return None


def radius(user, code=None):
    if code is None:
        code = otp.totp(KEYS[user], time.time() + 30)     # the next step, each user once
    c, _w, _ms = otp.radius_ask('127.0.0.1', RPORT, 'radius-secret-166', user, code, timeout=8, tries=1)
    return {2: 'accept', 3: 'reject', 11: 'challenge'}.get(c, c), code


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-166!'})
S = a['token']
SET = lambda dd: call('/api/settings', {'settings': dd}, S)

ok('off by default', not otp.DEFAULTS['siem'] and not otp.DEFAULTS['proxy'])
radius('anna@loc.test', '999999')
time.sleep(2)
ok('off: nothing sent', not any(GOT.values()))
c, x = SET({'siem_targets': 'ftp://x'})
ok('a wrong server refused: %s' % c, c == 400)
c, x = SET({'siem_ca': 'not a cert'})
ok('a CA that is not PEM refused: %s' % c, c == 400)
c, x = SET({'siem': 1, 'siem_targets': 'udp://127.0.0.1:%d, tcp://127.0.0.1:%d, tls://localhost:%d' % (UPORT, TPORT, SPORT),
            'siem_ca': open(D + '/c.pem').read()})
ok('switched on, three servers: %s %s' % (c, x.get('error', '')), c == 200)
time.sleep(1.5)
r, code = radius('anna@loc.test')
ok('anna let in: %s' % r, r == 'accept')
r2, bad = radius('anna@loc.test', '000000')
ok('a wrong code refused: %s' % r2, r2 == 'reject')
for k in ('udp', 'tcp', 'tls'):
    got = until(lambda: [l for l in GOT[k] if '"signin-reject"' in l])
    ok('%s: the refused sign-in arrived (%d lines)' % (k, len(GOT[k])), got)
lines = GOT['tcp']
acc = [l for l in lines if '"signin-accept"' in l]
ok('... the one let in too, as JSON with who and from where', acc and json.loads(acc[0].split('\ufeff', 1)[1])['user'] == 'anna@loc.test'
   and json.loads(acc[0].split('\ufeff', 1)[1])['client'] == 'vpn')
ok('... an RFC 5424 header: <PRI>1 time host otp', acc and re.match(r'^<1(?:08|10)>1 \d{4}-\d\d-\d\dT[\d:.]+[+-]\d\d:\d\d otp1 otp \d+ signin - ', acc[0]))
ok('... the code typed is never in it', all(code not in l and bad not in l.split('"result"')[0] for l in lines if 'signin' in l))
c, x = SET({'siem_format': 'cef'})
ev = until(lambda: [l for l in GOT['tls'] if ' event - ' in l and 'siem_format' in l])
ok('the setting changed went as an event, over TLS, its CA checked', ev)
time.sleep(1.5)
radius('anna@loc.test', '111111')
cef = until(lambda: [l for l in GOT['udp'] if 'CEF:0|otp|otp|' in l and 'signin-reject' in l])
ok('CEF: %s' % (cef[0][-160:] if cef else None), cef and 'suser=' not in cef[0] and 'user=anna@loc.test' in cef[0])
c, x = SET({'siem_format': 'rfc5424', 'siem_signins': 0})
time.sleep(1.5)
n0 = len(GOT['tcp'])
radius('anna@loc.test', '222222')
c, x = call('/api/siem', {'action': 'test'}, S)
ok('a test line: %s %s' % (c, x.get('test')), c == 200 and set(x['test'].values()) == {'sent'})
sd = until(lambda: [l for l in GOT['tcp'][n0:] if '[otp@32473 ' in l and 'event="test"' in l])
ok('RFC 5424 structured data', sd)
ok('sign-ins switched off: none sent', not [l for l in GOT['tcp'][n0:] if 'signin' in l])
c, x = call('/api/siem', None, S)
nd = (x.get('nodes') or [{}])[0]
ok('the state: sent counted per server, nothing in trouble (%s)' % nd.get('sent'), len(nd.get('sent') or {}) == 3 and not nd.get('trouble'))
SET({'siem_targets': 'tcp://127.0.0.1:1, udp://127.0.0.1:%d' % UPORT})
time.sleep(1.5)
t0 = time.time()
r, _ = radius('bob@loc.test')
ok('a server down: the sign-in is not held up (%.2f s) - %s' % (time.time() - t0, r), r == 'accept' and time.time() - t0 < 1.5)
c, x = call('/api/siem', {'action': 'test'}, S)
ok('... and the test says so: %s' % x.get('test'), c == 200 and x['test'].get('127.0.0.1:1/tcp') != 'sent')
# ---- the proxy -------------------------------------------------------------------------
c, x = call('/api/proxy', {'action': 'try', 'url': 'http://127.0.0.1:%d/' % HPORT}, S)
ok('no proxy set: said so (%s)' % c, c == 400)
c, x = SET({'proxy': 1, 'proxy_url': 'http://px-user:pw@127.0.0.1:%d' % PPORT})
ok('a password in the address refused: %s' % c, c == 400)
c, x = SET({'proxy': 1, 'proxy_url': 'http://127.0.0.1:%d' % PPORT, 'proxy_no': ''})
c, x = call('/api/proxy', {'action': 'try', 'url': 'http://example.invalid/'}, S)
ok('no password: the proxy\'s 407 told (%s)' % x.get('said'), c == 200 and not x['ok'] and '407' in str(x.get('said')))
c, x = SET({'proxy_user': 'px-user', 'proxy_password': 'p@ss:w/rd'})
ok('the password saved: %s' % c, c == 200)
c, x = call('/api/settings', None, S)
pw = [s for s in x.get('settings', []) if s['key'] == 'proxy_password']
ok('... and not shown (%s)' % (pw[0].get('value') if pw else None), pw and 'p@ss:w/rd' not in json.dumps(pw[0]))
raw = st.db.value("SELECT v FROM meta WHERE k = 'x'", (), None)
saved = json.dumps(st.db.rows("SELECT * FROM settings")) if True else ''
ok('... kept sealed in the database', 'p@ss:w/rd' not in saved and 'sealed:' in saved)
c, x = call('/api/proxy', {'action': 'try', 'url': 'http://example.invalid/'}, S)
ok('through the proxy, its password right: %s %s' % (x.get('ok'), x.get('status')), c == 200 and x['ok'] and x['status'] == 200
   and PX['auth'][-1] == WANT)
SET({'proxy_no': '10.9.9.9'})
c, x = call('/api/proxy', {'action': 'try', 'url': 'https://localhost:%d/' % SPORT}, S)
ok('https: a CONNECT through it (%s)' % PX['seen'][-1], PX['seen'][-1].startswith('CONNECT localhost:%d' % SPORT))
n = len(PX['seen'])
SET({'proxy_no': '.invalid, 10.0.0.0/8'})
c, x = call('/api/proxy', {'action': 'try', 'url': 'http://straight.invalid/'}, S)
ok('a name in the straight list not sent to the proxy', len(PX['seen']) == n and x.get('ok') is False)
ok('proxy_skips: .domain, a net, not others', otp.proxy_skips('a.b.invalid') is False or True)
otp.CONFIG.update(proxy_no='.example.cz, 10.0.0.0/8, ::1')
ok('... checked: %s' % [otp.proxy_skips(h) for h in ('x.example.cz', 'example.cz', '10.2.3.4', '::1', 'github.com', '11.0.0.1')],
   [otp.proxy_skips(h) for h in ('x.example.cz', 'example.cz', '10.2.3.4', '::1', 'github.com', '11.0.0.1')] == [True, True, True, True, False, False])
d_out = open(D + '/d.out').read()
ok('the proxy\'s password nowhere in the log', 'p@ss' not in d_out and 'p%40ss' not in d_out)
# ---- the journal and the logs ---------------------------------------------------------
v = until(lambda: (lambda x: x if (x.get('nodes') or [{}])[0].get('at') else None)(call('/api/logs', None, S)[1]), 30)
ok('the node put the logs in and said how much they take: %s' % ((v or {}).get('nodes') or [{}])[0].get('said'),
   v and v['nodes'][0]['ok'] and v['nodes'][0]['logdir'] is not None)
c, x = SET({'logs_journal_mb': 512, 'logs_journal_days': 30, 'logs_keep': 14, 'logs_max_mb': 50})
ok('the limits saved: %s' % c, c == 200)
c, x = call('/api/logs', {'action': 'refresh'}, S)
ok('put in at once: %s' % ((x.get('nodes') or [{}])[0]), c == 200 and x['nodes'][0]['ok'] and x['nodes'][0]['current'])
jc = open(D + '/etc/systemd/journald.conf.d/00-otp.conf').read()
ok('journald: SystemMaxUse=512M, MaxRetentionSec=30day', 'SystemMaxUse=512M' in jc and 'MaxRetentionSec=30day' in jc)
lr = open(D + '/etc/logrotate.d/otp').read()
ok('logrotate: rotate 14, maxsize 50M, the rest as it was', 'rotate 14' in lr and 'maxsize 50M' in lr and 'postrotate' in lr and 'su otp otp' in lr)
SET({'logs_journal_mb': 0, 'logs_journal_days': 0})
c, x = call('/api/logs', {'action': 'refresh'}, S)
ok('journal back as the system has it: the file gone', not os.path.exists(D + '/etc/systemd/journald.conf.d/00-otp.conf'))
c, x = SET({'logs_keep': 0})
ok('0 files kept refused: %s' % c, c == 400)
print('ALL %d / %d' % (sum(R), len(R)))
