"""t_fix.py - 1.0.317: an unsigned EAP request dropped; the administrator's second step gives its places
back; an address the server cannot take said at once; a directory's authorities signed; a PostgreSQL
restore numbered under the lock. The built otp.py loaded as a module over SQLite - a mail server of its
own on a free port of 127.0.0.1, no daemon.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, socket, sys, tempfile, threading, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.317'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r317_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx317', 'api_port': 29947}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 RADIUS: EAP-Message, no Message-Authenticator - discarded; the rest as before
class Pkt:
    def __init__(self, attrs, code=None):
        self.code = code or m.ACCESS_REQUEST
        self.attrs = attrs

    def message_authenticator_ok(self, secret):
        return None

    def all(self, n):
        return [v for k, v in self.attrs if k == n]

    def text(self, n):
        return 'jan'


class Srv:
    def __init__(self):
        self.dropped = []
        self.ma_seen = set()

    def drop(self, ip, port, user, why, **k):
        self.dropped.append(why)

    def ma_known(self, cid, ip):
        return False


ma = m.RadiusServer.ma_check if hasattr(m, 'RadiusServer') else None
if ma is None:
    ma = next(v.ma_check for v in vars(m).values() if isinstance(v, type) and hasattr(v, 'ma_check'))
s1 = Srv()
ok('1 EAP-Message, no Message-Authenticator: dropped', ma(s1, Pkt([(1, b'jan'), (79, b'\x02')]), {'id': 1}, b's', '10.0.0.1', 1) is False
   and 'EAP-Message' in s1.dropped[-1], s1.dropped)
s2 = Srv()
ok('1 a plain PAP request, no Message-Authenticator: let through as before',
   ma(s2, Pkt([(1, b'jan'), (2, b'x' * 16)]), {'id': 1}, b's', '10.0.0.1', 1) is True and not s2.dropped, s2.dropped)
s3 = Srv()
ok('1 Proxy-State still dropped as before', ma(s3, Pkt([(1, b'jan'), (33, b'p')]), {'id': 1}, b's', '10.0.0.1', 1) is False
   and 'Proxy-State' in s3.dropped[-1])

# ==== 2 the administrator's second step: nothing went, nothing counted
m.CONFIG.update({'code_send_max': 3, 'code_send_window_min': 15})
st.add_account('alice', 'fulladmin', 'Alice-Pass-317-long!', must_change=0)


class H:
    def __init__(self):
        self.store = st
        self.headers = {}


def session():
    tok = st.session_new('admin', 'alice', 'fulladmin', '127.0.0.1', 1, {})
    return st.session_get(tok, 'admin', 3600)


calls = {'n': 0}


def failing(*a, **k):
    calls['n'] += 1
    raise m.MailError('the server is away', [])


real_send = m.code_send
m.code_send = failing
codes = []
for i in range(5):
    try:
        m._mfa_send(H(), session(), 'mail', 'alice@example.cz', 'mfa')
    except m.ApiError as e:
        codes.append(e.status)
ok('2 five tries in an outage: each tried to send (502), none refused as too many', codes == [502] * 5 and calls['n'] == 5, (codes, calls))
ok('2 ...the account counts nothing', not [x for x in m.node_key_times(st, 'codesent', 'adm:alice')], m.node_key_times(st, 'codesent', 'adm:alice'))
ok('2 ...nor the address', not m.node_key_times(st, 'codesent', 'to:mail:alice@example.cz'))
sent = []
m.code_send = lambda *a, **k: sent.append(a) or 'sent'
try:
    m._mfa_send(H(), session(), 'mail', 'alice@example.cz', 'mfa'); got = 'went'
except m.ApiError as e:
    got = e.status
ok('2 the outage over: the code goes at once', got == 'went' and sent, got)
ok('2 ...and is counted, once each', len(m.node_key_times(st, 'codesent', 'adm:alice')) == 1
   and len(m.node_key_times(st, 'codesent', 'to:mail:alice@example.cz')) == 1)
# the address full, the account not: the account's place given back
for i in range(3):
    m.node_key_add(st, 'codesent', 'to:mail:full@example.cz', 900, limit=99)
try:
    m._mfa_send(H(), session(), 'mail', 'full@example.cz', 'mfa'); got = 'went'
except m.ApiError as e:
    got = e.status
ok('2 the address at its limit: 429', got == 429, got)
ok('2 ...the account\'s place given back', len(m.node_key_times(st, 'codesent', 'adm:alice')) == 1,
   m.node_key_times(st, 'codesent', 'adm:alice'))
m.code_send = real_send

# ==== 3 a server without SMTPUTF8, an address with á before the @
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(5)
PORT = srv.getsockname()[1]
said = []


def smtp_server():
    while True:
        try:
            c, _ = srv.accept()
        except OSError:
            return
        f = c.makefile('rb')
        c.sendall(b'220 test ESMTP\r\n')
        for line in f:
            said.append(line.strip())
            u = line.strip().upper()
            if u.startswith(b'EHLO'):
                c.sendall(b'250-test\r\n250 8BITMIME\r\n')
            elif u == b'DATA':
                c.sendall(b'354 go on\r\n')
                for l2 in f:
                    if l2.rstrip(b'\r\n') == b'.':
                        break
                c.sendall(b'250 taken\r\n')
            elif u.startswith(b'QUIT'):
                c.sendall(b'221 bye\r\n'); break
            else:
                c.sendall(b'250 ok\r\n')
        c.close()


threading.Thread(target=smtp_server, daemon=True).start()
from email.message import EmailMessage
msg = EmailMessage(); msg['From'] = 'otp@example.cz'; msg['To'] = 'jiří@example.cz'; msg['Subject'] = 'x'; msg.set_content('x')
try:
    m.smtp_talk(st, '127.0.0.1', PORT, 'none', None, msg, ['jiří@example.cz'], [])
    e = None
except m.MailError as x:
    e = x
ok('3 no SMTPUTF8: failed for good, not to be tried again', e is not None and e.permanent, (e, getattr(e, 'permanent', None)))
ok('3 ...said as that', e is not None and 'SMTPUTF8' in str(e) and 'plain letters' in str(e), e)
msg2 = EmailMessage(); msg2['From'] = 'otp@example.cz'; msg2['To'] = 'jiri@example.cz'; msg2['Subject'] = 'x'; msg2.set_content('x')
try:
    m.smtp_talk(st, '127.0.0.1', PORT, 'none', None, msg2, ['jiri@example.cz'], []); e2 = None
except m.MailError as x:
    e2 = x
ok('3 a plain address goes as before', e2 is None, e2)
srv.close()
cs = json.load(open(V + '/web/lang/cs.json'))
ok('3 its words in Czech', any(v['source'].startswith('{0} does not take an address with letters') and v['text']
                                for v in cs['patterns'].values()))

# ==== 4 the guard: a directory's authorities signed when changed, its removal signed
m.CONFIG['db_guard'] = 1
ident = st.directory_save({'name': 'corp', 'hosts': 'dc1.corp.example', 'base': 'DC=corp,DC=example'})
ok('4 a directory saved: signed', m.dbguard_directory_ok(st.db, 'corp'))
PEM = open('/etc/ssl/certs/ca-certificates.crt').read().split('-----END CERTIFICATE-----')[0] + '-----END CERTIFICATE-----'
try:
    st.directory_set_ca(ident, PEM, 'add')
    added = True
except Exception as x:
    added = x
ok('4 an authority added', added is True, added)
ok('4 ...still signed: its administrators sign in', m.dbguard_directory_ok(st.db, 'corp'))
st.directory_set_ca(ident, '', 'clear')
ok('4 cleared: still signed', m.dbguard_directory_ok(st.db, 'corp'))
row = st.db.row('SELECT * FROM directories WHERE id = ?', (ident,))
st.directory_drop(ident)
cols = [k for k in row.keys()]
st.db.run('INSERT INTO directories (%s) VALUES (%s)' % (', '.join(cols), ', '.join('?' * len(cols))), tuple(row[k] for k in cols))
ok('4 taken out, the row put back as it was by hand: refused', not m.dbguard_directory_ok(st.db, 'corp'))
m.CONFIG['db_guard'] = 0

# ==== 5 a PostgreSQL restore numbers on before the lock is let go
src = open(V + '/otp.py').read()
body = src[src.index('def _load_tables_held('):]
body = body[:body.index('\ndef ')]
lock_at = body.index('    with db.lock:')
inner = [l for l in body.splitlines() if 'setval(' in l or 'ha_sequences(' in l]
ok('5 the numbering set inside the lock', inner and all(l.startswith(' ' * 16) for l in inner), inner)
ok('5 ...after the COMMIT', body.index("db.run('COMMIT')") < body.index('setval('))

# ==== 6 the pages
js = open(V + '/web/assets/admin.js').read()
ok('6 one ask at a time, ended once (askNodes and dbtPoll)', js.count('if (asking || over) return;') >= 2 and js.count('if (over) return;') >= 4)
ok('6 IPv6 prefix counted', 'function lbV6(' in js)
ok('6 a pasted colour escaped', "'<span style=\"color:' + htmlText(n.getAttribute('color'))" in js)
ok('6 Show all from the first page', "all.onclick = function () { RQ_SINCE = null; PAGE.requests = 0; loadRequests(); };" in js)
import subprocess
a, b = js.index('function lbV6'), js.index('function lbListHas')
t = subprocess.run(['node', '-e', js[a:b] + """
var T=[['2001:db8::5','2001:db8::/64',true],['2001:db8:0:1::5','2001:db8::/64',false],['fe80::1','fe80::/10',true],
['fec0::1','fe80::/10',false],['10.1.2.3','10.0.0.0/8',true],['10.1.2.3','2001:db8::/64',false],['2001:db8::5','2001:db8::5',true]];
var bad=T.filter(function(x){return lbIpIn(x[0],x[1])!==x[2];}); console.log(JSON.stringify(bad));"""], capture_output=True, text=True)
ok('6 ...each case right', t.stdout.strip() == '[]', t.stdout + t.stderr)

print('ALL %d / %d' % (sum(R), len(R)))
