"""t_ftd_uag.py VERSION - otp against a Cisco FTD (RA VPN, Secure Client) and an Omnissa Horizon UAG
(RADIUS as the second factor), emulated on the wire.

Run as root in the build container:  python3 t_ftd_uag.py 1.0.264

What it starts, all of its own and all stopped again by their exact PIDs:
  - the mock Active Directory (test/mockldap.py) on a free port,
  - a "slow directory": a TCP proxy in front of it that holds every request from otp for a while,
  - an SMTP sink (in this process) for codes by mail; SMS go into a spool folder (smstools3 style),
  - otp daemon A and otp daemon B (SQLite, a temp state dir each - B starts from a copy of A's
    state, as a second RADIUS server in the FTD's server group), on free UDP/TCP ports,
    RADIUS bound to 127.0.0.1.
Nothing of the live install (/usr/local/lib/otp, the running service) or of the HA sandbox is used.

Every packet is built here, byte by byte (RFC 2865 / 2866 / 2869 / 3579): the Request
Authenticator, User-Password hidden the PAP way, Message-Authenticator (HMAC-MD5), and every reply
is checked: Identifier, length, Response Authenticator, Message-Authenticator. The NAS addresses
are loopback addresses of their own (FTD 127.0.0.21, UAG 127.0.0.31/.32), so otp tells the
RADIUS clients apart by source address as it does in real life.

What otp wrote is read back from the daemon's own SQLite (radius_log, otp_log, tokens, events).
"""
import atexit
import email
import email.policy
import hashlib
import hmac
import json
import os
import random
import re
import shutil
import signal
import socket
import socketserver
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import base64

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.264'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []
T0 = time.time()


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok   ' if cond else 'FAIL ') + what + ('' if cond else '   <-- %s' % str(more)[:600]),
          flush=True)
    return bool(cond)


def note(w):
    print('     ' + w, flush=True)


def section(w):
    print('\n== %s ==  (+%.0f s)' % (w, time.time() - T0), flush=True)


# ------------------------------------------------------------------------------------------------
# RADIUS on the wire, written here (not otp's own code)
# ------------------------------------------------------------------------------------------------
ACCESS_REQUEST, ACCESS_ACCEPT, ACCESS_REJECT = 1, 2, 3
ACCT_REQUEST, ACCT_RESPONSE, ACCESS_CHALLENGE, STATUS_SERVER = 4, 5, 11, 12
CODE_NAMES = {1: 'Access-Request', 2: 'Access-Accept', 3: 'Access-Reject', 4: 'Accounting-Request',
              5: 'Accounting-Response', 11: 'Access-Challenge', 12: 'Status-Server'}
CISCO, CISCO_ASA, MSFT = 9, 3076, 311


def A(t, v):
    v = v.encode('utf-8') if isinstance(v, str) else bytes(v)
    assert len(v) <= 253, (t, len(v))
    return bytes([t, len(v) + 2]) + v


def A_int(t, n):
    return A(t, struct.pack('>I', n))


def A_ip(t, ip):
    return A(t, socket.inet_aton(ip))


def VSA(vendor, t, v):
    v = v.encode('utf-8') if isinstance(v, str) else (struct.pack('>I', v) if isinstance(v, int) else bytes(v))
    return A(26, struct.pack('>I', vendor) + bytes([t, len(v) + 2]) + v)


def pap_hide(password, secret, ra):
    """RFC 2865 5.2."""
    pw = password.encode('utf-8')
    pw += b'\x00' * ((16 - len(pw) % 16) % 16 or (16 if not pw else 0))
    out, last = b'', ra
    for i in range(0, len(pw), 16):
        b = bytes(x ^ y for x, y in zip(pw[i:i + 16], hashlib.md5(secret + last).digest()))
        out += b
        last = b
    return out


class Req(object):
    def __init__(self, code, ident, attrs, secret, password=None, ma=True):
        self.code, self.ident, self.secret = code, ident, secret
        ra = os.urandom(16) if code in (ACCESS_REQUEST, STATUS_SERVER) else b'\x00' * 16
        body = b''.join(attrs)
        if password is not None:
            body += A(2, pap_hide(password, secret, ra))
        if ma:
            body += bytes([80, 18]) + b'\x00' * 16
        head = struct.pack('>BBH', code, ident, 20 + len(body))
        if code == ACCT_REQUEST:
            ra = hashlib.md5(head + b'\x00' * 16 + body + secret).digest()    # RFC 2866 3
        elif ma:
            mac = hmac.new(secret, head + ra + body, hashlib.md5).digest()     # RFC 3579 3.2
            body = body[:-16] + mac
        self.ra, self.data = ra, head + ra + body


class Reply(object):
    def __init__(self, data, req):
        self.raw = data
        self.code, self.ident, ln = struct.unpack('>BBH', data[:4])
        self.problems = []
        if ln != len(data) or ln < 20:
            self.problems.append('length %d, got %d bytes' % (ln, len(data)))
        if self.ident != req.ident:
            self.problems.append('identifier %d, asked %d' % (self.ident, req.ident))
        want = hashlib.md5(data[:4] + req.ra + data[20:ln] + req.secret).digest()
        if not hmac.compare_digest(want, data[4:20]):
            self.problems.append('Response Authenticator wrong')
        self.attrs, at = [], 20
        while at < ln:
            t, n = data[at], data[at + 1]
            if n < 2 or at + n > ln:
                self.problems.append('attribute cut off at %d' % at)
                break
            self.attrs.append((t, data[at + 2:at + n], at))
            at += n
        self.ma = None
        mas = [x for x in self.attrs if x[0] == 80]
        if len(mas) > 1:
            self.problems.append('two Message-Authenticators')
        if mas:
            t, v, pos = mas[0]
            z = bytearray(data[:ln])
            z[4:20] = req.ra
            z[pos + 2:pos + 18] = b'\x00' * 16
            self.ma = hmac.compare_digest(hmac.new(req.secret, bytes(z), hashlib.md5).digest(), v)
            if not self.ma:
                self.problems.append('Message-Authenticator wrong')

    @property
    def valid(self):
        return not self.problems

    def get(self, t):
        for k, v, _ in self.attrs:
            if k == t:
                return v
        return None

    def text(self, t):
        v = self.get(t)
        return v.decode('utf-8') if v is not None else None

    def types(self):
        return {k for k, _, _ in self.attrs}

    def vsa(self, vendor, t):
        out = []
        for k, v, _ in self.attrs:
            if k == 26 and len(v) > 6 and struct.unpack('>I', v[:4])[0] == vendor:
                at = 4
                while at + 2 <= len(v):
                    vt, vl = v[at], v[at + 1]
                    if vl < 2:
                        break
                    if vt == t:
                        out.append(v[at + 2:at + vl])
                    at += vl
        return out

    def __repr__(self):
        return '<%s id=%d %s%s>' % (CODE_NAMES.get(self.code, self.code), self.ident,
                                    [(k, v[:40]) for k, v, _ in self.attrs],
                                    (' PROBLEMS %s' % self.problems) if self.problems else '')


class Nas(object):
    """One RADIUS client (an FTD, a UAG) with its own source address and one UDP socket - a
    retransmission leaves from the same address and port, as on the real boxes."""

    def __init__(self, name, src, secret, ma=True):
        self.name, self.src, self.secret, self.ma = name, src, secret, ma
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((src, 0))
        self.ident = random.randrange(256)
        self.extra = []                 # replies that came for an earlier packet (late, repeats)

    def next_ident(self):
        self.ident = (self.ident + 1) % 256
        return self.ident

    def req(self, code, attrs, password=None, ma=None):
        return Req(code, self.next_ident(), attrs, self.secret, password,
                   self.ma if ma is None else ma)

    def send(self, req, port, timeout=10.0, retries=0, retry_every=None, host='127.0.0.1',
             keep_after=0.0):
        """Send `req`; resend the same bytes every `retry_every` s (default: `timeout`), at most
        `retries` times; return (Reply or None, sends, seconds). With `keep_after`, the replies
        coming within that long after the first are collected in self.extra too."""
        t0 = time.time()
        every = retry_every or timeout
        sends, deadline = 0, t0 + timeout * (retries + 1) if retry_every is None else \
            t0 + every * retries + timeout
        nxt = t0
        got = None
        while time.time() < deadline:
            if sends <= retries and time.time() >= nxt:
                self.sock.sendto(req.data, (host, port))
                sends += 1
                nxt = time.time() + every
            wait = max(0.01, min(deadline, nxt if sends <= retries else deadline) - time.time())
            self.sock.settimeout(wait)
            try:
                data, peer = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            rep = Reply(data, req)
            if rep.ident != req.ident or 'Response Authenticator wrong' in rep.problems:
                self.extra.append(rep)
                continue
            got = rep
            break
        took = time.time() - t0
        if got is not None and keep_after:
            end = time.time() + keep_after
            while time.time() < end:
                self.sock.settimeout(max(0.01, end - time.time()))
                try:
                    data, _ = self.sock.recvfrom(4096)
                    self.extra.append(Reply(data, req))
                except socket.timeout:
                    break
        return got, sends, took

    def drain(self, wait=0.05):
        self.sock.settimeout(wait)
        try:
            while True:
                self.sock.recvfrom(4096)
        except socket.timeout:
            pass


def totp(secret_b32, step, digits=6):
    key = base64.b32decode(secret_b32 + '=' * (-len(secret_b32) % 8), casefold=True)
    h = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    o = h[-1] & 15
    return '%0*d' % (digits, (struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 10 ** digits)


class Tok(object):
    """A token of the app, its codes worked out here. Every step is taken once (otp's
    last_step): the next code is always of a later step, within otp's window of 1."""

    def __init__(self, name, secret, scratch):
        self.name, self.secret, self.scratch, self.last = name, secret, list(scratch), 0

    def code(self, peek=False):
        while True:
            t = time.time()
            now = int(t // 30)
            # The step before is taken too while it has a good 5 s left in otp's window.
            s = max(self.last + 1, now - 1 if t % 30 < 25 else now)
            if s <= now + 1:
                break
            time.sleep(max(0.05, (now + 1) * 30 - time.time() + 0.05))
        if not peek:
            self.last = s
        return totp(self.secret, s)

    def wrong(self):
        """A six-digit code that is none of the steps otp would take now."""
        now = int(time.time() // 30)
        right = {totp(self.secret, s) for s in range(now - 2, now + 3)}
        while True:
            c = '%06d' % random.randrange(10 ** 6)
            if c not in right:
                return c


# ------------------------------------------------------------------------------------------------
# helpers around the daemon
# ------------------------------------------------------------------------------------------------
def free_port(kind=socket.SOCK_DGRAM):
    s = socket.socket(socket.AF_INET, kind)
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def free_pair():
    """Two free ports on UDP that are free on TCP too."""
    while True:
        a, b = free_port(), free_port()
        if a != b:
            return a, b


PROCS = []


def cleanup():
    for p in PROCS:
        try:
            if p.poll() is None:
                os.kill(p.pid, signal.SIGCONT)
                p.terminate()
        except OSError:
            pass
    for p in PROCS:
        try:
            p.wait(15)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
                p.wait(5)
            except OSError:
                pass
    if not os.environ.get('KEEP') and all(R):
        shutil.rmtree(TMP, ignore_errors=True)
    else:
        print('state kept in %s' % TMP)


def on_signal(sig, frame):
    raise SystemExit(130)


signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)

TMP = tempfile.mkdtemp(prefix='otp-ftduag-')
atexit.register(cleanup)
DA, DB = TMP + '/a', TMP + '/b'
SPOOL = TMP + '/spool'
for d in (DA, DA + '/run', SPOOL):
    os.makedirs(d)

# ---- the mock directory and the slow one --------------------------------------------------------
LPORT = free_port(socket.SOCK_STREAM)
mock = subprocess.Popen([sys.executable, V + '/test/mockldap.py', str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=TMP)
PROCS.append(mock)
first = mock.stdout.readline().decode()
assert str(LPORT) in first, first


class SlowProxy(object):
    """A directory that answers slowly: every request from otp held `delay` s before it goes on."""

    def __init__(self, upstream_port):
        self.up, self.delay, self.conns = upstream_port, 0.0, 0
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(64)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            self.conns += 1
            try:
                u = socket.create_connection(('127.0.0.1', self.up), timeout=10)
            except OSError:
                c.close()
                continue
            threading.Thread(target=self.pipe, args=(c, u, True), daemon=True).start()
            threading.Thread(target=self.pipe, args=(u, c, False), daemon=True).start()

    def pipe(self, a, b, slow):
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                if slow and self.delay:
                    time.sleep(self.delay)
                b.sendall(d)
        except OSError:
            pass
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


slow = SlowProxy(LPORT)

# ---- the SMTP sink -------------------------------------------------------------------------------
MAILS = []
MAIL_LOCK = threading.Lock()


class SmtpSink(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda t: self.wfile.write((t + '\r\n').encode())
        w('220 sink.test ESMTP')
        data, buf, rcpt = False, [], []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            if data:
                if line.rstrip(b'\r\n') == b'.':
                    data = False
                    with MAIL_LOCK:
                        MAILS.append((rcpt[:], b''.join(buf)))
                    buf, rcpt = [], []
                    w('250 2.0.0 queued as TEST')
                else:
                    buf.append(line[1:] if line.startswith(b'..') else line)
                continue
            c = line[:4].decode('ascii', 'replace').upper()
            if c == 'EHLO':
                w('250-sink.test')
                w('250 8BITMIME')
            elif c == 'HELO':
                w('250 sink.test')
            elif c == 'RCPT':
                rcpt.append(line.decode().split(':', 1)[1].strip().strip('<>').lower())
                w('250 2.1.5 ok')
            elif c == 'DATA':
                data = True
                w('354 go on')
            elif c == 'QUIT':
                w('221 bye')
                return
            else:
                w('250 ok')


socketserver.ThreadingTCPServer.allow_reuse_address = True
smtp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), SmtpSink)
smtp.daemon_threads = True
SMTP_PORT = smtp.server_address[1]
threading.Thread(target=smtp.serve_forever, daemon=True).start()

# ---- otp's state: made in this process, before either daemon runs ------------------------------
A_AUTH, A_ACCT = free_pair()
B_AUTH, B_ACCT = free_pair()
A_API, B_API = free_port(socket.SOCK_STREAM), free_port(socket.SOCK_STREAM)
S_FTD, S_UAG1, S_UAG2 = 'Ftd-Shared-Secret-7x!', 'Uag-Secret-One-2406', 'Uag-Secret-Two-2406'
COMMON = {'db_engine': 'sqlite', 'radius_bind': '127.0.0.1',
          'code_lang': 'en', 'mail_lang': 'en',
          'sms_mode': 'spool', 'sms_spool_dir': SPOOL,
          'mail_mode': 'smtp', 'mail_from': 'otp@corpnet.cz', 'smtp_host': '127.0.0.1',
          'smtp_port': SMTP_PORT, 'smtp_security': 'none', 'smtp_auth': 'none',
          'code_tries': 3, 'code_send_max': 20,
          # The token's limits as shipped (3 wrong codes / pause, lockout) - the pause made short
          # (8 s, not 30) and the lockout early (5, not 10) so the test does not sit and wait.
          'rate_limit_tries': 3, 'rate_limit_s': 8, 'lockout_after': 5, 'lockout_min': 15}


def config(d, auth, acct, api, node):
    c = dict(COMMON, radius_auth_port=auth, radius_acct_port=acct, api_port=api, node_name=node)
    with open(d + '/config.json', 'w') as f:
        json.dump(c, f)


config(DA, A_AUTH, A_ACCT, A_API, 'ftdA')
ENV_A = dict(os.environ, OTP_STATE=DA, OTP_CONFIG=DA + '/config.json', OTP_LOGDIR=DA,
             OTP_RUN=DA + '/run', OTP_STAY_ROOT='1')
os.environ.update(ENV_A)
sys.path.insert(0, V)
_argv, sys.argv = sys.argv, ['x']
import otp  # noqa: E402
sys.argv = _argv
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
tk = otp.Tokens(st)
st.directory_save({'name': 'AD', 'hosts': '127.0.0.1:%d' % LPORT, 'tls': 'none', 'port': 389,
                   'base': 'DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                   'bind_pw': 'the-otp-service-password', 'timeout_s': 5,
                   'user_attr': 'sAMAccountName'})
st.directory_save({'name': 'SLOWAD', 'hosts': '127.0.0.1:%d' % slow.port, 'tls': 'none',
                   'port': 389, 'base': 'DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                   'bind_pw': 'the-otp-service-password', 'timeout_s': 8,
                   'user_attr': 'sAMAccountName'})
GP_REPLY = 'ASA-Group-Policy = GP_VPN_USERS\nClass = OU=GP_VPN_USERS;'
# FTD realm 1: the password followed by the code; codes by mail/SMS in a second window.
st.realm_save({'name': 'corpnet.cz', 'suffix': 'corpnet.cz', 'aliases': ['corpnet.local'],
               'directory': 'AD', 'lookup': 'upn', 'auth_mode': 'password_otp', 'enabled': 1,
               'methods': ['totp', 'mail', 'sms'], 'reply': 'Session-Timeout = 43200',
               'groups': [{'group': 'VPN_2FACT_USERS', 'reply': GP_REPLY}]})
# FTD realm 2: the directory password, then the app's code in Secure Client's second window.
st.realm_save({'name': 'ftd-chal.cz', 'suffix': 'ftd-chal.cz', 'directory': 'AD', 'lookup': 'sam',
               'auth_mode': 'challenge', 'enabled': 1, 'methods': ['totp'],
               'groups': [{'group': 'VPN_2FACT_USERS', 'reply': 'ASA-Group-Policy = GP_CHAL'}]})
# FTD realm 2b: codes by mail, the realm's own group policy (no group filter).
st.realm_save({'name': 'ftd-mail.cz', 'suffix': 'ftd-mail.cz', 'directory': 'AD', 'lookup': 'sam',
               'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp', 'mail', 'sms'],
               'reply': 'ASA-Group-Policy = GP_MAIL'})
# FTD realm 3: on a directory that answers slowly.
st.realm_save({'name': 'slow.cz', 'suffix': 'slow.cz', 'directory': 'SLOWAD', 'lookup': 'sam',
               'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp']})
# UAG realm 1: the passcode alone (Horizon asks the AD password itself, after RADIUS).
st.realm_save({'name': 'uag.cz', 'suffix': 'uag.cz', 'aliases': ['uag.local'], 'directory': 'AD',
               'lookup': 'sam', 'auth_mode': 'otp', 'enabled': 1, 'methods': ['totp']})
# UAG realm 2: the AD password first (Horizon "same user name and password for RADIUS and
# Windows"), then the code in UAG's RADIUS challenge page.
st.realm_save({'name': 'uagc.cz', 'suffix': 'uagc.cz', 'directory': 'AD', 'lookup': 'sam',
               'auth_mode': 'challenge', 'enabled': 1, 'methods': ['totp']})
st.client_save({'name': 'ftd1', 'address': '127.0.0.21', 'secret': S_FTD,
                'note': 'Cisco FTD, RA VPN, RADIUS server group'})
st.client_save({'name': 'uag1', 'address': '127.0.0.31', 'secret': S_UAG1,
                'note': 'Horizon UAG, Name ID suffix @uag.cz, no Message-Authenticator'})
st.client_save({'name': 'uag2', 'address': '127.0.0.32', 'secret': S_UAG2, 'realm': 'uag.cz',
                'note': 'Horizon UAG, no suffix (otp adds @uag.cz), Message-Authenticator'})
TOK = {}
# (only the mock's accounts whose userAccountControl can be read: falco, marta, nested, outsider)
for n in ('falco@corpnet.cz', 'falco@ftd-chal.cz', 'falco@slow.cz', 'marta@uagc.cz',
          'falco@ftd-mail.cz', 'nested@ftd-mail.cz',
          'falco@uag.cz', 'marta@uag.cz', 'nested@uag.cz', 'outsider@uag.cz'):
    g = tk.enroll(n, 'test')
    TOK[n] = Tok(n, g['secret'], g.get('scratch') or [])
# nested is in VPN_2FACT_USERS through VPN_SUPPLIER_X (a nested group)
SMS = tk.enroll_sent('nested@corpnet.cz', 'test', 'sms', '+420 777 111 222', lang='cs')
MAILTOK = tk.enroll_sent('marta@ftd-mail.cz', 'test', 'mail', 'marta.mobilni@corpnet.cz', lang='en')
PW = {'falco': 'falco-password-1', 'marta': 'marta-password-1', 'nested': 'nested-password-1',
      'jnovak': 'a-good-long-password'}
del st, tk
# Daemon B: the second RADIUS server of the group - the same clients, realms and tokens.
shutil.copytree(DA, DB, ignore=shutil.ignore_patterns('run', '*.log', 'd.out'))
os.makedirs(DB + '/run', exist_ok=True)
config(DB, B_AUTH, B_ACCT, B_API, 'ftdB')
ENV_B = dict(os.environ, OTP_STATE=DB, OTP_CONFIG=DB + '/config.json', OTP_LOGDIR=DB,
             OTP_RUN=DB + '/run', OTP_STAY_ROOT='1')
dA = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=ENV_A, cwd=TMP,
                      stdout=open(DA + '/d.out', 'w'), stderr=subprocess.STDOUT)
PROCS.insert(0, dA)
dB = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=ENV_B, cwd=TMP,
                      stdout=open(DB + '/d.out', 'w'), stderr=subprocess.STDOUT)
PROCS.insert(0, dB)

ftd = Nas('FTD', '127.0.0.21', S_FTD.encode(), ma=True)
uag1 = Nas('UAG-1', '127.0.0.31', S_UAG1.encode(), ma=False)
uag2 = Nas('UAG-2', '127.0.0.32', S_UAG2.encode(), ma=True)


def wait_up(port, proc, d):
    end = time.time() + 60
    probe = Nas('probe', '127.0.0.21', S_FTD.encode())
    while time.time() < end:
        if proc.poll() is not None:
            break
        r, _, _ = probe.send(probe.req(STATUS_SERVER, []), port, timeout=0.5)
        if r is not None:
            probe.sock.close()
            return r
    print(open(d + '/d.out').read()[-3000:])
    raise SystemExit('the daemon on %d did not come up' % port)


r = wait_up(A_AUTH, dA, DA)
ok('daemon A answers Status-Server (RFC 5997) with a signed Access-Accept',
   r.code == ACCESS_ACCEPT and r.valid and r.ma, r)
r = wait_up(B_AUTH, dB, DB)
ok('daemon B answers too', r.code == ACCESS_ACCEPT and r.valid and r.ma, r)
note('started in %.1f s; A pid %d (auth %d, acct %d), B pid %d (auth %d), LDAP pid %d'
     % (time.time() - T0, dA.pid, A_AUTH, A_ACCT, dB.pid, B_AUTH, mock.pid))


# ---- reading what otp wrote ---------------------------------------------------------------------
def q(d, sql, args=()):
    for _ in range(50):
        try:
            c = sqlite3.connect('file:%s/otp.db?mode=ro' % d, uri=True, timeout=10)
            c.row_factory = sqlite3.Row
            try:
                return [dict(x) for x in c.execute(sql, args).fetchall()]
            finally:
                c.close()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(0.1)
    raise last


def mark(d=DA):
    """The last row written - once the rows of the requests before have all come (each is
    written just after its answer goes out)."""
    last, since = None, time.time()
    while True:
        m = q(d, 'SELECT MAX(id) AS m FROM radius_log')[0]['m'] or 0
        if m != last:
            last, since = m, time.time()
        elif time.time() - since >= 0.3:
            return m
        time.sleep(0.05)


def rows(since, n=1, d=DA, timeout=8.0, user=None):
    end = time.time() + timeout
    while True:
        got = q(d, 'SELECT * FROM radius_log WHERE id > ? ORDER BY id', (since,))
        if user is not None:
            got = [x for x in got if x['username'] == user]
        if len(got) >= n or time.time() > end:
            for x in got:
                x['steps_l'] = json.loads(x['steps'] or '[]')
                x['attrs_l'] = json.loads(x['attrs'] or '[]')
                x['reply_l'] = json.loads(x['reply'] or '[]')
            return got
        time.sleep(0.1)


def token_row(name, d=DA):
    got = q(d, 'SELECT * FROM tokens WHERE name = ?', (name,))
    return got[0] if got else {}


def otp_log(name, since_ts, d=DA):
    return q(d, 'SELECT * FROM otp_log WHERE name = ? AND ts >= ? ORDER BY id', (name, since_ts))


# ---- what each box sends ------------------------------------------------------------------------
SESSION = [0x5000]


def ftd_attrs(user, client_ip='198.51.100.23', tg='TG-Employees'):
    """An Access-Request of FTD 7.x (FMC RA VPN, AAA Only, a RADIUS server group) for a Secure
    Client 5.x sign-in: the user name as typed, NAS-IP-Address of the interface facing the server,
    NAS-Port (the session's number), NAS-Port-Type Virtual, Called-Station-Id the outside address,
    Calling-Station-Id the client's public address, Tunnel-Client-Endpoint, the ASA vendor
    attributes (tunnel group name 146, client type 150 = AnyConnect, session type 151) and
    Cisco-AVPairs (mdm-tlv=..., audit-session-id, ip:source-ip). No Class. The
    Message-Authenticator is added by Nas (FTD sends it with 'Message-Authenticator' on in the
    server group - the default since the BlastRADIUS fixes)."""
    SESSION[0] += 1
    return [A(1, user), A_ip(4, '127.0.0.21'), A_int(5, SESSION[0]), A_int(61, 5),
            A(30, '203.0.113.1'), A(31, client_ip), A(66, client_ip),
            VSA(CISCO_ASA, 146, tg), VSA(CISCO_ASA, 150, 2), VSA(CISCO_ASA, 151, 1),
            VSA(CISCO, 1, 'mdm-tlv=device-platform=win'),
            VSA(CISCO, 1, 'mdm-tlv=device-mac=00-50-56-aa-bb-cc'),
            VSA(CISCO, 1, 'mdm-tlv=ac-user-agent=AnyConnect Windows 5.1.4.74'),
            VSA(CISCO, 1, 'mdm-tlv=device-platform-version=10.0.19045'),
            VSA(CISCO, 1, 'mdm-tlv=device-uid=8A3F6E0C1B2D4E5F6A7B8C9D0E1F2A3B4C5D6E7F'),
            VSA(CISCO, 1, 'audit-session-id=0a0a0a15000%x6543abcd' % SESSION[0]),
            VSA(CISCO, 1, 'ip:source-ip=%s' % client_ip),
            VSA(CISCO, 1, 'coa-push=true')]


def uag_attrs(user, nas_ip='10.20.0.5', nas_id=None):
    """An Access-Request of a Horizon UAG (Edge Service → Authentication Methods → RADIUS):
    User-Name (with its "Name ID suffix" where one is set), User-Password (PAP) and the
    NAS-IP-Address typed into the UAG's RADIUS settings. A NAS-Identifier where a variant sends one."""
    out = [A(1, user)]
    if nas_ip:
        out.append(A_ip(4, nas_ip))
    if nas_id:
        out.append(A(32, nas_id))
    return out


CHALLENGE_OK = {18, 24, 80, 33, 26, 27, 28}      # RFC 2865 4.4 (+ Message-Authenticator)
REJECT_OK = {18, 80, 33}                         # RFC 2865 4.3


def sane(r, nas, what):
    """The checks every answer passes: authenticators right, signed (otp's radius_reply_ma)."""
    ok('%s: Response Authenticator and Message-Authenticator right' % what,
       r is not None and r.valid and r.ma is True, r)
    if r is not None and r.code == ACCESS_CHALLENGE:
        ok('%s: the challenge carries only what RFC 2865 allows' % what,
           r.types() <= CHALLENGE_OK, r.types())
    if r is not None and r.code == ACCESS_REJECT:
        ok('%s: the reject carries only what RFC 2865 allows, and no reason (radius_reject_reason '
           'off)' % what, r.types() <= REJECT_OK and r.get(18) is None, r.types())


def code_of_sms(before):
    end = time.time() + 15
    while time.time() < end:
        new = sorted(f for f in os.listdir(SPOOL) if f.startswith('otp-') and f not in before)
        if new:
            body = open(os.path.join(SPOOL, new[-1]), encoding='utf-8').read()
            text = body.split('\n\n', 1)[1] if '\n\n' in body else body
            m = re.search(r'(?<!\d)(\d{3}) ?(\d{3})(?!\d)', text)
            return (m.group(1) + m.group(2)) if m else None, body, new
        time.sleep(0.1)
    return None, '', []


def code_of_mail(n_before):
    end = time.time() + 20
    while time.time() < end:
        with MAIL_LOCK:
            if len(MAILS) > n_before:
                rcpt, raw = MAILS[-1]
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                text = ''
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        text += part.get_content()
                m = re.search(r'(?<!\d)(\d{3}) ?(\d{3})(?!\d)', text)
                return (m.group(1) + m.group(2)) if m else None, rcpt, msg
        time.sleep(0.1)
    return None, [], None


def step_said(row, what):
    return [s for s in row.get('steps_l', []) if what in (s.get('what') or '')]


# ================================================================================================
section('FTD (a): the password followed by the code in one field - realm corpnet.cz, password_otp')
# ================================================================================================
falco = TOK['falco@corpnet.cz']
m0 = mark()
c = falco.code()
rq = ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'), PW['falco'] + c)
r, sends, took = ftd.send(rq, A_AUTH)
sane(r, ftd, 'FTD a1')
ok('FTD a1: password+code -> Access-Accept (%.2f s)' % took, r and r.code == ACCESS_ACCEPT, r)
gp = r.vsa(CISCO_ASA, 25) if r else []
ok('FTD a1: ASA-Group-Policy (3076/25) = GP_VPN_USERS from the group VPN_2FACT_USERS',
   gp == [b'GP_VPN_USERS'], gp)
ok('FTD a1: Class = "OU=GP_VPN_USERS;" (the older way, FTD takes either)',
   r and r.get(25) == b'OU=GP_VPN_USERS;', r)
ok('FTD a1: Session-Timeout 43200 from the realm',
   r and r.get(27) == struct.pack('>I', 43200), r)
ok('FTD a1: no State and no Reply-Message in the Accept', r and r.get(24) is None and r.get(18) is None)
lg = rows(m0)
ok('FTD a1: one radius_log row: accept, client ftd1, realm corpnet.cz', len(lg) == 1 and
   lg[0]['result'] == 'accept' and lg[0]['client'] == 'ftd1' and lg[0]['realm'] == 'corpnet.cz',
   lg)
if lg:
    x = lg[0]
    ok('FTD a1: Log columns: Calling 198.51.100.23, Called 203.0.113.1, NAS 127.0.0.21, '
       'tunnel group TG-Employees, the code "Valid token used"',
       x['calling'] == '198.51.100.23' and x['called'] == '203.0.113.1' and
       x['nas_ip'] == '127.0.0.21' and x['tunnel'] == 'TG-Employees' and
       x['otp'] in ('Valid token used', 'Valid token within window size used'), {k: x[k] for k in ('calling', 'called', 'nas_ip', 'tunnel', 'otp')})
    ok('FTD a1: the password never written down (User-Password <suppressed>)',
       ['User-Password', '<suppressed>'] in x['attrs_l'] and PW['falco'] not in x['attrs'] and
       c not in x['attrs'], x['attrs'][:300])
    ok('FTD a1: the reply written down: ASA-Group-Policy and Class',
       ['ASA-Group-Policy', 'GP_VPN_USERS'] in x['reply_l'] and ['Class', 'OU=GP_VPN_USERS;'] in x['reply_l'],
       x['reply_l'])
    ok('FTD a1: steps: found the account, the directory password, the group, the code',
       step_said(x, 'the directory password') and step_said(x, 'a member of VPN_2FACT_USERS')
       and step_said(x, 'the code for the token falco@corpnet.cz'), [s['what'] for s in x['steps_l']])

m0 = mark()
c = falco.code()
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'), 'wrong-password' + c), A_AUTH)
sane(r, ftd, 'FTD a2')
ok('FTD a2: a wrong password with a right code -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('FTD a2: logged "the directory refused the password", the code not tried',
   lg and 'the directory refused the password' in lg[0]['reason'] and not lg[0]['otp'], lg and lg[0]['reason'])
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'), PW['falco'] + c), A_AUTH)
ok('FTD a2: ... that same code with the right password -> Accept (it was not used up)',
   r and r.code == ACCESS_ACCEPT, r)

m0 = mark()
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'),
                           PW['falco'] + falco.wrong()), A_AUTH)
sane(r, ftd, 'FTD a3')
ok('FTD a3: right password, wrong code -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('FTD a3: logged "Denied by the token server: Not a valid token"',
   lg and lg[0]['reason'] == 'Denied by the token server: Not a valid token' and
   lg[0]['otp'] == 'Not a valid token', lg and lg[0]['reason'])
ok('FTD a3: one wrong code counted on the token', token_row('falco@corpnet.cz')['failures'] == 1,
   token_row('falco@corpnet.cz')['failures'])
# a right code clears the count (and the pause) again
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'), PW['falco'] + falco.code()), A_AUTH)
ok('FTD a3: the next right code -> Accept, the count back to 0',
   r and r.code == ACCESS_ACCEPT and token_row('falco@corpnet.cz')['failures'] == 0, r)

m0 = mark()
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.local'), PW['falco'] + falco.code()), A_AUTH)
ok('FTD a4: falco@corpnet.local (another suffix of the realm) -> Accept with the group policy',
   r and r.code == ACCESS_ACCEPT and r.vsa(CISCO_ASA, 25) == [b'GP_VPN_USERS'], r)
lg = rows(m0)
ok('FTD a4: the token used is falco@corpnet.cz (one token for both suffixes)',
   lg and step_said(lg[0], 'the code for the token falco@corpnet.cz'), lg and [s['what'] for s in lg[0]['steps_l']])

m0 = mark()
r, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('gone@corpnet.cz'), 'gone-password-1123456'), A_AUTH)
ok('FTD a5: an account disabled in AD -> Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('FTD a5: logged "the account is disabled in the directory"',
   lg and lg[0]['reason'] == 'the account is disabled in the directory', lg and lg[0]['reason'])

# ================================================================================================
section('FTD (b): Secure Client\'s second window - Access-Challenge, State, Reply-Message')
# ================================================================================================
fc = TOK['falco@ftd-chal.cz']
m0 = mark()
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz'), PW['falco']), A_AUTH)
sane(r1, ftd, 'FTD b1 (app) first request')
st1 = r1.get(24) if r1 else None
ok('FTD b1: the AD password alone -> Access-Challenge with a State',
   r1 and r1.code == ACCESS_CHALLENGE and st1 and 1 <= len(st1) <= 253, r1)
ok('FTD b1: Reply-Message (the second window\'s prompt) "Type the code from the app on your phone"',
   r1 and r1.text(18) == 'Type the code from the app on your phone', r1 and r1.text(18))
ok('FTD b1: nothing that grants anything in the challenge (no group policy, no Class)',
   r1 and not r1.vsa(CISCO_ASA, 25) and r1.get(25) is None, r1)
# Secure Client's second window: the same user, the code, the State echoed, a new Identifier and
# Request Authenticator - and FTD sends its full attribute set again.
r2, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz') + [A(24, st1 or b'x')],
                            fc.code()), A_AUTH)
sane(r2, ftd, 'FTD b1 (app) second request')
ok('FTD b1: the code with the State -> Access-Accept with ASA-Group-Policy GP_CHAL',
   r2 and r2.code == ACCESS_ACCEPT and r2.vsa(CISCO_ASA, 25) == [b'GP_CHAL'], r2)
ok('FTD b1: the State is not sent back in the Accept', r2 and r2.get(24) is None)
lg = rows(m0, 2)
ok('FTD b1: two log rows: challenge "the code is asked for in a second window", then accept',
   [x['result'] for x in lg] == ['challenge', 'accept'] and
   lg[0]['reason'] == 'the code is asked for in a second window' and lg[0]['otp'] == 'Code asked for',
   [(x['result'], x['reason'], x['otp']) for x in lg])
if len(lg) == 2:
    ok('FTD b1: the second row says what the first request proved',
       step_said(lg[1], 'checked with the first request'), [s['what'] for s in lg[1]['steps_l']])

# wrong codes in the second window: asked again (same State), refused after code_tries (3)
m0 = mark()
f0 = int(token_row('falco@ftd-chal.cz')['failures'] or 0)
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz'), PW['falco']), A_AUTH)
st1 = r1.get(24)
seen = []
for i in range(3):
    rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz') + [A(24, st1)],
                                fc.wrong()), A_AUTH)
    sane(rr, ftd, 'FTD b2 wrong code %d' % (i + 1))
    seen.append(rr)
ok('FTD b2: wrong code 1 and 2 -> Access-Challenge again, the same State',
   all(x and x.code == ACCESS_CHALLENGE and x.get(24) == st1 for x in seen[:2]), seen[:2])
ok('FTD b2: ... with Reply-Message "That code was not right - type it again"',
   all(x and x.text(18) == 'That code was not right - type it again' for x in seen[:2]),
   [x and x.text(18) for x in seen[:2]])
ok('FTD b2: wrong code 3 (code_tries) -> Access-Reject', seen[2] and seen[2].code == ACCESS_REJECT, seen[2])
rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz') + [A(24, st1)],
                            fc.code(peek=True)), A_AUTH)
ok('FTD b2: the right code on that State afterwards -> Reject (the question is gone)',
   rr and rr.code == ACCESS_REJECT, rr)
lg = rows(m0, 5)
ok('FTD b2: log: challenge, challenge x2 "asked again (n of 3)", reject, reject "sign in again"',
   [x['result'] for x in lg] == ['challenge', 'challenge', 'challenge', 'reject', 'reject'] and
   'asked again (1 of 3)' in lg[1]['reason'] and 'asked again (2 of 3)' in lg[2]['reason'] and
   'Not a valid token' in lg[3]['reason'] and 'sign in again' in lg[4]['reason'],
   [(x['result'], x['reason']) for x in lg])
f1 = int(token_row('falco@ftd-chal.cz')['failures'] or 0)
ok('FTD b2: the three wrong codes counted on the token (lockout counting): %d -> %d' % (f0, f1),
   f1 - f0 == 3, (f0, f1))
time.sleep(max(0, 8.3 - (time.time() - lg[3]['ts'] if lg else 0)))    # the pause (rate_limit_s) runs out
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz'), PW['falco']), A_AUTH)
rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-chal.cz') + [A(24, r1.get(24))],
                            fc.code()), A_AUTH)
ok('FTD b2: signed in again with the right code -> Accept, the count back to 0',
   rr and rr.code == ACCESS_ACCEPT and int(token_row('falco@ftd-chal.cz')['failures'] or 0) == 0, rr)

# a code by SMS (spool), in the password_otp realm: the token's kind decides
before = set(os.listdir(SPOOL))
m0 = mark()
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz', '198.51.100.40'),
                            PW['nested']), A_AUTH)
sane(r1, ftd, 'FTD b3 (SMS) first request')
ok('FTD b3: SMS token, password alone -> Access-Challenge', r1 and r1.code == ACCESS_CHALLENGE, r1)
msg = r1.text(18) if r1 else ''
ok('FTD b3: Reply-Message in Czech (the token\'s language), UTF-8, masked number: %r' % msg,
   msg == 'Zadejte kód z SMS poslané na +420******222' and len(r1.get(18)) <= 253, msg)
smscode, body, files = code_of_sms(before)
ok('FTD b3: one SMS written to the spool, To: 420777111222', smscode and len(files) == 1 and
   body.startswith('To: 420777111222'), body[:80])
rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz', '198.51.100.40') +
                            [A(24, r1.get(24))], smscode or '000000'), A_AUTH)
sane(rr, ftd, 'FTD b3 (SMS) second request')
ok('FTD b3: the SMS code -> Accept with the realm\'s and the group\'s attributes',
   rr and rr.code == ACCESS_ACCEPT and rr.vsa(CISCO_ASA, 25) == [b'GP_VPN_USERS'] and
   rr.get(25) == b'OU=GP_VPN_USERS;' and rr.get(27) == struct.pack('>I', 43200), rr)
again, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz', '198.51.100.40') +
                               [A(24, r1.get(24))], smscode or '000000'), A_AUTH)
ok('FTD b3: the same State and code in a new packet -> Reject (a sent code is good once)',
   again and again.code == ACCESS_REJECT, again)
lg = rows(m0, 3)
ok('FTD b3: log: challenge "Code sent by SMS", accept "Code sent by SMS accepted", reject',
   [x['result'] for x in lg] == ['challenge', 'accept', 'reject'] and lg[0]['otp'] == 'Code sent by SMS'
   and lg[1]['otp'] == 'Code sent by SMS accepted', [(x['result'], x['otp'], x['reason']) for x in lg])
ol = otp_log('nested@corpnet.cz', T0)
ok('FTD b3: the token\'s history: "A code was sent by SMS to +420******222"',
   any(x['said'] == 'A code was sent by SMS to +420******222' for x in ol), [x['said'] for x in ol])

# a recovery code in the second window, then a wrong password (no SMS sent)
before = set(os.listdir(SPOOL))
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz'), PW['nested']), A_AUTH)
code_of_sms(before)
m0 = mark()
rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz') + [A(24, r1.get(24))],
                            SMS['scratch'][0]), A_AUTH)
ok('FTD b4: a recovery code in the second window -> Accept', rr and rr.code == ACCESS_ACCEPT, rr)
lg = rows(m0)
ok('FTD b4: logged "Scratch-token used"', lg and lg[0]['otp'] == 'Scratch-token used', lg and lg[0]['otp'])
before = set(os.listdir(SPOOL))
m0 = mark()
rr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('nested@corpnet.cz'), 'not-her-password'), A_AUTH)
time.sleep(1.0)
ok('FTD b5: a wrong AD password -> Reject, no SMS sent',
   rr and rr.code == ACCESS_REJECT and not (set(os.listdir(SPOOL)) - before), rr)
lg = rows(m0)
ok('FTD b5: logged "the directory refused the password"',
   lg and 'the directory refused the password' in lg[0]['reason'], lg and lg[0]['reason'])

# a code by mail (the SMTP sink)
n0 = len(MAILS)
m0 = mark()
r1, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('marta@ftd-mail.cz', '198.51.100.41'),
                            PW['marta']), A_AUTH)
sane(r1, ftd, 'FTD b6 (mail) first request')
ok('FTD b6: mail token -> Access-Challenge "Type the code mailed to m******@corpnet.cz"',
   r1 and r1.code == ACCESS_CHALLENGE and r1.text(18) == 'Type the code mailed to m******@corpnet.cz',
   r1 and r1.text(18))
mcode, rcpt, mmsg = code_of_mail(n0)
ok('FTD b6: the mail reached the SMTP server, to marta@ftd-mail.cz', mcode and rcpt == ['marta.mobilni@corpnet.cz'],
   (mcode, rcpt))
wr, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('marta@ftd-mail.cz', '198.51.100.41') +
                            [A(24, r1.get(24))], '000000' if mcode != '000000' else '111111'), A_AUTH)
ok('FTD b6: a wrong code -> challenge again', wr and wr.code == ACCESS_CHALLENGE and wr.get(24) == r1.get(24), wr)
ok('FTD b6: the wrong mailed code counted on the token (lockout)',
   int(token_row('marta@ftd-mail.cz')['failures'] or 0) == 1, token_row('marta@ftd-mail.cz')['failures'])
# The answer with the code, sent twice by FTD (its retry while the first was on the way):
rq = ftd.req(ACCESS_REQUEST, ftd_attrs('marta@ftd-mail.cz', '198.51.100.41') + [A(24, r1.get(24))],
             mcode or '000000')
rr, sends, _ = ftd.send(rq, A_AUTH)
ftd.extra[:] = []
ftd.sock.sendto(rq.data, ('127.0.0.1', A_AUTH))
ftd.sock.settimeout(3)
try:
    dup = Reply(ftd.sock.recvfrom(4096)[0], rq)
except socket.timeout:
    dup = None
sane(rr, ftd, 'FTD b6 (mail) second request')
ok('FTD b6: the mailed code -> Accept with the realm\'s GP_MAIL', rr and rr.code == ACCESS_ACCEPT and
   rr.vsa(CISCO_ASA, 25) == [b'GP_MAIL'], rr)
ok('FTD b6: a retransmission of that answer (same Identifier and Authenticator) -> the same '
   'Accept, byte for byte', dup is not None and rr is not None and dup.raw == rr.raw, dup)
lg = rows(m0, 3)
ok('FTD b6: log: challenge, challenge (asked again), accept - one accept, the repeat not logged',
   [x['result'] for x in lg] == ['challenge', 'challenge', 'accept'], [(x['result'], x['reason']) for x in lg])
ok('FTD b6: ... and the right code that followed cleared the count, as for the app',
   int(token_row('marta@ftd-mail.cz')['failures'] or 0) == 0, token_row('marta@ftd-mail.cz')['failures'])

# ================================================================================================
section('FTD (c): retransmissions within the duplicate window (radius_dup_window_s 30)')
# ================================================================================================
m0 = mark()
t_c = time.time()
fm = TOK['falco@ftd-mail.cz']
c = fm.code()
rq = ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-mail.cz', '198.51.100.50'), PW['falco'] + c)
r, _, _ = ftd.send(rq, A_AUTH)
reps = []
for i in range(3):
    time.sleep(0.3)
    ftd.sock.sendto(rq.data, ('127.0.0.1', A_AUTH))
    ftd.sock.settimeout(3)
    try:
        reps.append(Reply(ftd.sock.recvfrom(4096)[0], rq))
    except socket.timeout:
        reps.append(None)
ok('FTD c1: the first -> Accept', r and r.code == ACCESS_ACCEPT, r)
ok('FTD c1: three retransmissions -> the same Accept each, byte for byte',
   all(x is not None and x.raw == r.raw for x in reps), reps)
lg = rows(m0, 1, timeout=2)
ok('FTD c1: one log row only (the repeats are answered from memory)', len(lg) == 1, [(x['result'], x['reason']) for x in lg])
ol = [x for x in otp_log('falco@ftd-mail.cz', t_c) if x['how'] == 'radius']
ok('FTD c1: the code checked once in the token\'s history', len(ol) == 1, [(x['ok'], x['said']) for x in ol])
r2, _, _ = ftd.send(ftd.req(ACCESS_REQUEST, ftd_attrs('falco@ftd-mail.cz', '198.51.100.50'),
                            PW['falco'] + c), A_AUTH)
ok('FTD c2: the same code in a NEW packet (another Identifier) -> Reject', r2 and r2.code == ACCESS_REJECT, r2)
lg = rows(m0, 2)
ok('FTD c2: logged "Token has already been used once"',
   len(lg) == 2 and 'Token has already been used once' in lg[1]['reason'], lg and lg[-1]['reason'])
# The same Identifier and Authenticator but different contents is not a repeat (otp keys the
# whole packet): never answered with the cached Accept.
fake = bytearray(rq.data)
i = fake.find(b'198.51.100.50')
fake[i:i + 13] = b'198.51.100.99'
ftd.sock.sendto(bytes(fake), ('127.0.0.1', A_AUTH))
ftd.sock.settimeout(3)
try:
    fr = Reply(ftd.sock.recvfrom(4096)[0], rq)
except socket.timeout:
    fr = None
ok('FTD c3: same Identifier+Authenticator, changed contents -> not the cached Accept '
   '(its Message-Authenticator is now wrong: dropped)', fr is None or fr.raw != r.raw, fr)

# ================================================================================================
section('FTD (d): a slow directory, FTD\'s timeout and retries')
# ================================================================================================
fs = TOK['falco@slow.cz']
slow.delay = 0.8
m0 = mark()
c = fs.code()
rq = ftd.req(ACCESS_REQUEST, ftd_attrs('falco@slow.cz', '198.51.100.60'), PW['falco'] + c)
# An impatient retry (every 1 s, 3 retries) - otp is still working on the first; then FTD's
# usual 10 s timeout: the answer must come within it.
ftd.extra[:] = []
r, sends, took = ftd.send(rq, A_AUTH, timeout=10, retries=3, retry_every=1.0, keep_after=2.5)
note('slow directory: %d send(s), answered after %.2f s, %d more answer(s) after it'
     % (sends, took, len(ftd.extra)))
ok('FTD d1: answered within FTD\'s 10 s timeout (%.1f s), Accept' % took,
   r is not None and r.code == ACCESS_ACCEPT and took < 10, (r, took))
ok('FTD d1: the directory was slow enough for FTD to retransmit (took %.1f s, %d sends)' % (took, sends),
   sends >= 2, sends)
ok('FTD d1: any later answer to those retransmissions is the same Accept',
   all(x.raw == r.raw for x in ftd.extra if x.ident == rq.ident), ftd.extra)
lg = rows(m0, 1, timeout=3)
ok('FTD d1: one accept in the log, the code used once', len(lg) == 1 and lg[0]['result'] == 'accept'
   and lg[0]['took_ms'] >= 1000, [(x['result'], x['took_ms']) for x in lg])
# A NAS that retries from ANOTHER source port (a new socket per attempt) sends, by RFC 5080
# 2.2.2, a new request - not a retransmission. Shown here so the checklist can warn about it.
fs2 = Nas('FTD-other-port', '127.0.0.21', S_FTD.encode())
m0 = mark()
c = fs.code()
rq = ftd.req(ACCESS_REQUEST, ftd_attrs('falco@slow.cz', '198.51.100.61'), PW['falco'] + c)
fs2.ident = rq.ident
ftd.sock.sendto(rq.data, ('127.0.0.1', A_AUTH))
time.sleep(1.0)
r_b, _, _ = fs2.send(rq, A_AUTH, timeout=10)
ftd.sock.settimeout(10)
try:
    r_a = Reply(ftd.sock.recvfrom(4096)[0], rq)
except socket.timeout:
    r_a = None
lg = rows(m0, 2)
ok('FTD d2: the same packet from another source port while the first is still worked on: '
   'one Accept, one Reject "already been used once" (two requests to otp)',
   sorted([getattr(r_a, 'code', None), getattr(r_b, 'code', None)]) == [ACCESS_ACCEPT, ACCESS_REJECT]
   and sorted(x['result'] for x in lg) == ['accept', 'reject'],
   (r_a, r_b, [(x['result'], x['reason']) for x in lg]))
note('d2: first port got %s, the other port got %s' % (CODE_NAMES.get(getattr(r_a, 'code', 0)),
                                                       CODE_NAMES.get(getattr(r_b, 'code', 0))))
fs2.sock.close()
slow.delay = 0.0

# ================================================================================================
section('FTD (e): accounting Start and Stop')
# ================================================================================================
acct_sid = 'C0A80A15%08X' % random.randrange(1 << 32)


def ftd_acct(kind, extra=()):
    return [A_int(40, kind), A(44, acct_sid), A(1, 'falco@corpnet.cz'), A_ip(4, '127.0.0.21'),
            A_int(5, SESSION[0]), A_int(61, 5), A(30, '203.0.113.1'), A(31, '198.51.100.23'),
            A_ip(8, '10.10.20.15'), A(25, 'OU=GP_VPN_USERS;'), A_int(45, 1), A_int(41, 0),
            A_int(55, int(time.time())), VSA(CISCO_ASA, 146, 'TG-Employees'),
            VSA(CISCO_ASA, 25, 'GP_VPN_USERS'), VSA(CISCO_ASA, 150, 2), VSA(CISCO_ASA, 151, 1),
            VSA(CISCO, 1, 'audit-session-id=0a0a0a15000%x6543abcd' % SESSION[0])] + list(extra)


m0 = mark()
ra = ftd.req(ACCT_REQUEST, ftd_acct(1), ma=False)
r, _, _ = ftd.send(ra, A_ACCT)
ok('FTD e1: Accounting-Request Start -> Accounting-Response, authenticator right',
   r and r.code == ACCT_RESPONSE and r.valid, r)
ok('FTD e1: the response carries no attributes', r and not [a for a in r.attrs if a[0] != 80], r)
ra = ftd.req(ACCT_REQUEST, ftd_acct(2, [A_int(46, 125), A_int(42, 123456), A_int(43, 654321),
                                         A_int(47, 300), A_int(48, 400), A_int(49, 1)]), ma=False)
r, _, _ = ftd.send(ra, A_ACCT)
ok('FTD e2: Stop -> Accounting-Response', r and r.code == ACCT_RESPONSE and r.valid, r)
lg = rows(m0, 2)
ok('FTD e: log: two "acct" rows, Start and Stop, with the session\'s Class echoed',
   [(x['result'], x['reason']) for x in lg] == [('acct', 'Start'), ('acct', 'Stop')] and
   all(['Class', 'OU=GP_VPN_USERS;'] in x['attrs_l'] for x in lg),
   [(x['result'], x['reason']) for x in lg])
bad = Req(ACCT_REQUEST, ftd.next_ident(), ftd_acct(3), b'not-the-secret', ma=False)
r, _, _ = ftd.send(bad, A_ACCT, timeout=2)
ok('FTD e3: an accounting request with another secret -> no answer', r is None, r)
# Status-Server on the accounting port (RFC 5997 4)
r, _, _ = ftd.send(ftd.req(STATUS_SERVER, []), A_ACCT)
ok('FTD e4: Status-Server on the accounting port -> Accounting-Response',
   r and r.code == ACCT_RESPONSE and r.valid, r)

# ================================================================================================
section('FTD (f): a server group of two - one otp hangs, the other answers')
# ================================================================================================
mb = mark(DB)
os.kill(dA.pid, signal.SIGSTOP)
try:
    c = TOK['nested@ftd-mail.cz'].code()
    rq = ftd.req(ACCESS_REQUEST, ftd_attrs('nested@ftd-mail.cz', '198.51.100.70'), PW['nested'] + c)
    t_f = time.time()
    r, sends, took = ftd.send(rq, A_AUTH, timeout=2, retries=1)
    ok('FTD f1: node A stopped (SIGSTOP): no answer after %d sends' % sends, r is None, r)
    # FTD marks the server failed and sends the request to the next one of the group - a new
    # packet: another Identifier and Request Authenticator, the password hidden anew.
    rq2 = ftd.req(ACCESS_REQUEST, ftd_attrs('nested@ftd-mail.cz', '198.51.100.70'), PW['nested'] + c)
    r, _, took = ftd.send(rq2, B_AUTH)
    sane(r, ftd, 'FTD f2 (node B)')
    ok('FTD f2: node B -> Accept with the realm\'s group policy (%.2f s)' % took,
       r and r.code == ACCESS_ACCEPT and r.vsa(CISCO_ASA, 25) == [b'GP_MAIL'], r)
    lg = rows(mb, 1, d=DB)
    ok('FTD f2: node B wrote the accept in its own log', lg and lg[0]['result'] == 'accept', lg)
finally:
    os.kill(dA.pid, signal.SIGCONT)
note('node A continued; its late answer to the stale request is no business of FTD (it gave up '
     'on it). In a real cluster both nodes share one database, and the code would be refused '
     'there as used - covered by the HA tests.')
ftd.drain(1.0)

# ================================================================================================
section('UAG (a): the passcode alone (realm uag.cz, mode otp), PAP, Name ID suffix @uag.cz')
# ================================================================================================
ed = TOK['falco@uag.cz']
m0 = mark()
r, _, took = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('falco@uag.cz'), ed.code()), A_AUTH, timeout=5, retries=2)
sane(r, uag1, 'UAG a1')
ok('UAG a1: the passcode -> Access-Accept (%.2f s)' % took, r and r.code == ACCESS_ACCEPT, r)
ok('UAG a1: the Accept is signed though UAG sent no Message-Authenticator (UAG ignores it)', r and r.ma, r)
lg = rows(m0)
ok('UAG a1: log: accept, client uag1, realm uag.cz, NAS-IP 10.20.0.5 (as UAG says), '
   '"Valid token used"', lg and lg[0]['result'] == 'accept' and lg[0]['client'] == 'uag1' and
   lg[0]['realm'] == 'uag.cz' and lg[0]['nas_ip'] == '10.20.0.5' and lg[0]['otp'].startswith('Valid token'),
   lg and {k: lg[0][k] for k in ('result', 'client', 'realm', 'nas_ip', 'otp')})
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('falco@uag.cz'), ed.wrong()), A_AUTH, timeout=5)
sane(r, uag1, 'UAG a2')
ok('UAG a2: a wrong passcode -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('UAG a2: logged "Not a valid token"', lg and lg[0]['otp'] == 'Not a valid token', lg and lg[0]['reason'])
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('falco@uag.cz'), PW['falco']),
                    A_AUTH, timeout=5)
ok('UAG a3: the AD password typed as the passcode -> Reject (the realm takes the code alone)',
   r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('UAG a3: logged "Not a valid token", the password not in the log',
   lg and 'Not a valid token' in lg[0]['reason'] and PW['falco'] not in json.dumps(lg[0], default=str),
   lg and lg[0]['reason'])

m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('pkolar@uag.cz'), ed.code(peek=True)), A_AUTH, timeout=5)
lg = rows(m0)
ok('UAG a4: an account locked out in AD -> Reject before any code is looked at',
   r and r.code == ACCESS_REJECT and lg and lg[0]['reason'].startswith('the account') and not lg[0]['otp'],
   lg and lg[0]['reason'])
note('logged as: %r' % (lg and lg[0]['reason']))

# ================================================================================================
section('UAG (b): AD password first, then the code in UAG\'s RADIUS challenge page')
# ================================================================================================
jc = TOK['marta@uagc.cz']
m0 = mark()
r1, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz'), PW['marta']), A_AUTH, timeout=5)
sane(r1, uag1, 'UAG b1 first request')
ok('UAG b1: AD password -> Access-Challenge, State, Reply-Message (UAG shows it above the field)',
   r1 and r1.code == ACCESS_CHALLENGE and r1.get(24) and
   r1.text(18) == 'Type the code from the app on your phone', r1)
r2, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz') + [A(24, r1.get(24))],
                              jc.code()), A_AUTH, timeout=5)
sane(r2, uag1, 'UAG b1 second request')
ok('UAG b1: the code with the State -> Accept', r2 and r2.code == ACCESS_ACCEPT, r2)
lg = rows(m0, 2)
ok('UAG b1: log: challenge then accept', [x['result'] for x in lg] == ['challenge', 'accept'], lg)
r1, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz'), 'wrong-ad-password'), A_AUTH, timeout=5)
ok('UAG b2: a wrong AD password -> Reject, no challenge', r1 and r1.code == ACCESS_REJECT, r1)
# the State of one UAG answered through the other one (a second UAG behind a balancer)
r1, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz'), PW['marta']), A_AUTH, timeout=5)
m0 = mark()
r2, _, _ = uag2.send(uag2.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz') + [A(24, r1.get(24))],
                              jc.code(peek=True)), A_AUTH, timeout=5)
ok('UAG b3: the answer to UAG-1\'s challenge coming from UAG-2 -> Reject', r2 and r2.code == ACCESS_REJECT, r2)
lg = rows(m0)
ok('UAG b3: logged "the answer does not belong to the question it names"',
   lg and lg[0]['reason'] == 'the answer does not belong to the question it names', lg and lg[0]['reason'])
r2, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uagc.cz') + [A(24, r1.get(24))],
                              jc.code()), A_AUTH, timeout=5)
ok('UAG b3: ... the same State through UAG-1 -> Accept (the code was not used)',
   r2 and r2.code == ACCESS_ACCEPT, r2)

# ================================================================================================
section('UAG (c): CHAP, MS-CHAPv1, MS-CHAPv2 - refused, the reason in the log')
# ================================================================================================
m0 = mark()
cid, chal = 7, os.urandom(16)
resp = hashlib.md5(bytes([cid]) + b'123456' + chal).digest()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('edvorak@uag.cz') +
                             [A(3, bytes([cid]) + resp), A(60, chal)]), A_AUTH, timeout=5)
sane(r, uag1, 'UAG c1 CHAP')
ok('UAG c1: "Authentication type" CHAP -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('UAG c1: logged "the request carries no User-Password (PAP)", step "CHAP or no User-Password"',
   lg and lg[0]['reason'] == 'the request carries no User-Password (PAP)' and
   step_said(lg[0], 'a password') and 'CHAP' in json.dumps(lg[0]['steps_l']), lg and lg[0]['reason'])
ok('UAG c1: CHAP-Password and CHAP-Challenge not written down',
   lg and ['CHAP-Password', '<suppressed>'] in lg[0]['attrs_l'] and
   ['CHAP-Challenge', '<suppressed>'] in lg[0]['attrs_l'], lg and lg[0]['attrs_l'])
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('edvorak@uag.cz') +
                             [VSA(MSFT, 11, os.urandom(8)), VSA(MSFT, 1, bytes([0, 1]) + os.urandom(48))]),
                    A_AUTH, timeout=5)
sane(r, uag1, 'UAG c2 MS-CHAPv1')
ok('UAG c2: MS-CHAPv1 -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0, 1, timeout=2)
ok('UAG c2: not written again within the minute (unsigned, no password: one row a minute per '
   'client and reason - 1.0.186)', lg == [], [x['reason'] for x in lg])
m0 = mark()
r, _, _ = uag2.send(uag2.req(ACCESS_REQUEST, uag_attrs('edvorak') +
                             [VSA(MSFT, 11, os.urandom(16)),
                              VSA(MSFT, 25, bytes([0, 0]) + os.urandom(16) + b'\x00' * 8 + os.urandom(24))]),
                    A_AUTH, timeout=5)
sane(r, uag2, 'UAG c3 MS-CHAPv2')
ok('UAG c3: MS-CHAPv2 (signed, from UAG-2) -> Access-Reject', r and r.code == ACCESS_REJECT, r)
lg = rows(m0)
ok('UAG c3: logged "the request carries no User-Password (PAP)", the MS-CHAP attributes suppressed',
   bool(lg) and lg[0]['reason'] == 'the request carries no User-Password (PAP)' and
   sum(1 for n, v in lg[0]['attrs_l'] if v == '<suppressed>' and ('311' in n or 'MS-CHAP' in n)) == 2,
   lg and (lg[0]['reason'], lg[0]['attrs_l']))
note('UAG shows its own "authentication failed"; the reason is in Log → RADIUS (Reply-Message only '
     'with radius_reject_reason on)')

# ================================================================================================
section('UAG (d): the user name with and without a domain, the Name ID suffix')
# ================================================================================================
cases = [
    (uag2, 'nested', 'nested@uag.cz', 'UAG-2, no suffix: otp adds the client\'s realm uag.cz'),
    (uag2, 'CORP\\marta', 'marta@uag.cz', 'UAG-2, DOMAIN\\name (Connection Server realm prefix)'),
    (uag1, 'falco@uag.local', 'falco@uag.cz', 'UAG-1, Name ID suffix @uag.local: another suffix of the realm'),
    (uag1, 'NESTED@UAG.CZ', 'nested@uag.cz', 'UAG-1, the name in capitals'),
]
for nas, user, tname, what in cases:
    m0 = mark()
    r, _, _ = nas.send(nas.req(ACCESS_REQUEST, uag_attrs(user), TOK[tname].code()), A_AUTH, timeout=5)
    sane(r, nas, 'UAG d %s' % user)
    lg = rows(m0)
    ok('UAG d: %s: %r -> Accept, token %s' % (what, user, tname),
       r and r.code == ACCESS_ACCEPT and lg and lg[0]['result'] == 'accept' and
       step_said(lg[0], 'the code for the token %s' % tname), (r, lg and lg[0]['reason']))
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('jnovak'), TOK['falco@uag.cz'].code(peek=True)),
                    A_AUTH, timeout=5)
lg = rows(m0)
ok('UAG d: UAG-1 without its Name ID suffix, client with no realm: "jnovak" -> Reject, '
   '"no realm takes the name jnovak"', r and r.code == ACCESS_REJECT and lg and
   lg[0]['reason'] == 'no realm takes the name jnovak', lg and lg[0]['reason'])
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uag.cz@uag.cz'),
                             TOK['marta@uag.cz'].code(peek=True)), A_AUTH, timeout=5)
lg = rows(m0)
ok('UAG d: the user typed the whole UPN and UAG appended its suffix again '
   '("marta@uag.cz@uag.cz") -> Reject', r and r.code == ACCESS_REJECT, r)
DOUBLE_AT_REASON = lg[0]['reason'] if lg else ''
ok('... the Log says why: more than one @ (1.0.264)', 'more than one @' in DOUBLE_AT_REASON, DOUBLE_AT_REASON)
note('logged as: %r; step: %r' % (DOUBLE_AT_REASON, lg and lg[0]['steps_l']))

# ================================================================================================
section('UAG (e): UAG retries a wrong passcode ("number of attempts"); pause and lockout counted right')
# ================================================================================================
ot = TOK['outsider@uag.cz']
name = 'outsider@uag.cz'
m0 = mark()
f_start = int(token_row(name)['failures'] or 0)
w1 = uag1.req(ACCESS_REQUEST, uag_attrs(name), ot.wrong())
r, sends, _ = uag1.send(w1, A_AUTH, timeout=5)
# UAG's "number of attempts to the RADIUS server": the same packet again (it did not see the reply)
uag1.sock.sendto(w1.data, ('127.0.0.1', A_AUTH))
uag1.sock.settimeout(3)
try:
    rep = Reply(uag1.sock.recvfrom(4096)[0], w1)
except socket.timeout:
    rep = None
ok('UAG e1: wrong passcode -> Reject; its retransmission -> the same Reject',
   r and r.code == ACCESS_REJECT and rep is not None and rep.raw == r.raw, (r, rep))
ok('UAG e1: counted once', int(token_row(name)['failures'] or 0) - f_start == 1, token_row(name)['failures'])
for i in range(2):
    r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs(name), ot.wrong()), A_AUTH, timeout=5)
ok('UAG e2: wrong passcodes 2 and 3 -> Reject; 3 counted', r and r.code == ACCESS_REJECT and
   int(token_row(name)['failures'] or 0) - f_start == 3, token_row(name)['failures'])
right = ot.code(peek=True)
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs(name), right), A_AUTH, timeout=5)
lg = rows(m0, 4)
ok('UAG e3: within the pause (3 wrong in rate_limit_s) even the right code -> Reject '
   '"Rate-limit reached", not counted', r and r.code == ACCESS_REJECT and lg and
   'Rate-limit reached' in lg[-1]['reason'] and int(token_row(name)['failures'] or 0) - f_start == 3,
   (lg and lg[-1]['reason'], token_row(name)['failures']))
time.sleep(max(0, 8.3 - (time.time() - lg[2]['ts'] if len(lg) > 2 else 0)))
for i in range(2):
    r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs(name), ot.wrong()), A_AUTH, timeout=5)
tr = token_row(name)
ok('UAG e4: after the pause, wrong 4 and 5 -> Reject; the token locked at lockout_after (5)',
   r and r.code == ACCESS_REJECT and int(tr['failures'] or 0) - f_start == 5 and
   float(tr['locked_until'] or 0) > time.time() + 600, (tr['failures'], tr['locked_until']))
m1 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs(name), ot.code(peek=True)), A_AUTH, timeout=5)
lg = rows(m1)
ok('UAG e5: the right passcode now -> Reject "Locked out after too many wrong codes"',
   r and r.code == ACCESS_REJECT and lg and 'Locked out after too many wrong codes' in lg[0]['reason'],
   lg and lg[0]['reason'])
ev = q(DA, "SELECT words FROM events WHERE words LIKE ?", ('%%token of %s is locked out%%' % name,))
ok('UAG e5: the lockout is in Events', len(ev) == 1, ev)

# ================================================================================================
section('UAG (f): NAS-IP-Address / NAS-Identifier; the client is found by the source address')
# ================================================================================================
fu = TOK['falco@uag.cz']
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('falco@uag.cz', nas_ip='192.0.2.99'), fu.code()),
                    A_AUTH, timeout=5)
lg = rows(m0)
ok('UAG f1: NAS-IP-Address 192.0.2.99 (not the source) -> Accept as client uag1; the Log\'s NAS '
   'column shows 192.0.2.99', r and r.code == ACCESS_ACCEPT and lg and lg[0]['client'] == 'uag1'
   and lg[0]['nas_ip'] == '192.0.2.99' and lg[0]['src'].startswith('127.0.0.31:'),
   lg and {k: lg[0][k] for k in ('client', 'nas_ip', 'src')})
ma_ = TOK['marta@uag.cz']
m0 = mark()
r, _, _ = uag1.send(uag1.req(ACCESS_REQUEST, uag_attrs('marta@uag.cz', nas_ip=None, nas_id='uag-dmz-01'),
                             ma_.code()), A_AUTH, timeout=5)
lg = rows(m0)
ok('UAG f2: NAS-Identifier only (no NAS-IP-Address) -> Accept; the NAS column falls back to the '
   'source address', r and r.code == ACCESS_ACCEPT and lg and lg[0]['nas_ip'] == '127.0.0.31' and
   ['NAS-Identifier', 'uag-dmz-01'] in lg[0]['attrs_l'], lg and (lg[0]['nas_ip'], lg[0]['attrs_l']))
stranger = Nas('UAG-unknown', '127.0.0.39', S_UAG1.encode(), ma=False)
m0 = mark()
r, _, _ = stranger.send(stranger.req(ACCESS_REQUEST, uag_attrs('nested@uag.cz', nas_ip='127.0.0.31'),
                                     TOK['nested@uag.cz'].code(peek=True)), A_AUTH, timeout=2)
lg = rows(m0)
ok('UAG f3: from an address that is no client, though NAS-IP-Address names uag1 -> no answer',
   r is None, r)
ok('UAG f3: logged as dropped: "the address 127.0.0.39 is not one of the clients"',
   lg and lg[0]['result'] == 'drop' and lg[0]['reason'] == 'the address 127.0.0.39 is not one of the clients',
   lg and (lg[0]['result'], lg[0]['reason']))
ev = q(DA, "SELECT words FROM events WHERE words LIKE '%127.0.0.39, which is not a client%'")
ok('UAG f3: and in Events', len(ev) >= 1, ev)
stranger.sock.close()
m0 = mark()
r, _, _ = uag2.send(uag2.req(ACCESS_REQUEST, uag_attrs('nested'), TOK['nested@uag.cz'].code(peek=True),
                             ma=False), A_AUTH, timeout=2)
lg = rows(m0)
ok('UAG f4: UAG-2 signed its requests before; one without a Message-Authenticator -> dropped '
   '(BlastRADIUS rule), the reason logged', r is None and lg and lg[0]['result'] == 'drop' and
   'there is no Message-Authenticator' in lg[0]['reason'], lg and lg[0]['reason'])
r, _, _ = uag2.send(uag2.req(ACCESS_REQUEST, uag_attrs('nested'), TOK['nested@uag.cz'].code()), A_AUTH, timeout=5)
ok('UAG f4: signed again -> Accept', r and r.code == ACCESS_ACCEPT, r)

# ================================================================================================
section('the daemons')
# ================================================================================================
ok('daemon A still running', dA.poll() is None)
ok('daemon B still running', dB.poll() is None)
out = open(DA + '/d.out', errors='replace').read() + open(DB + '/d.out', errors='replace').read()
leak = [w for w in (S_FTD, S_UAG1, S_UAG2, PW['falco'], PW['marta'], PW['jnovak']) if w in out]
logs = ''
for d in (DA, DB):
    for f in os.listdir(d):
        if f.endswith('.log'):
            logs += open(os.path.join(d, f), errors='replace').read()
leak += [w for w in (S_FTD, S_UAG1, S_UAG2, PW['falco'], PW['marta'], PW['jnovak']) if w in logs]
ok('no shared secret and no password in the daemons\' output and logs', not leak, leak)
tb = [ln for ln in (out + logs).splitlines() if 'Traceback' in ln]
ok('no traceback in the daemons\' output and logs', not tb, tb[:3])
note('double-suffix name logged as: %r' % DOUBLE_AT_REASON)
print('\nALL %d / %d  (%.0f s)' % (sum(R), len(R), time.time() - T0))
sys.exit(0 if all(R) else 1)
