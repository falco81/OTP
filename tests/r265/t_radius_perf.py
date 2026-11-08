"""t_radius_perf.py - 1.0.265: RADIUS under load, the integrator's fixes.
P1 accounting workers on a database lane of their own (radius-acct-N), not the main one.
P2 Directory.held(): only the time waiting on the directory counts as the directory's; this node's
   own limit refuses with "this node is busy: N requests wait for the directory", never "gone away".
P3 requests older than 4 s in the queue are dropped (radius_stale_s still sets it, 1-60 s); the
   queue takes each client and realm in turn.
P4 cheap per request: the key file looked at once a second; the isemon files not stat'ed per line.
P5 the reading account's directory connections kept (looked at, given back clean, a stale one
   asked again on a new one, a person's bind never kept).
P6 the directory's cache lets the oldest go, not all of it.
P7b the workers follow radius_workers live; held() counts the ones running.
P7c mail and SMS each their own send limits; a code whose turn came after code_ttl_s not sent.
P7d ma_known looks up exact keys per node, not LIKE per request.
The built otp.py loaded with exec (nothing started, no ports).

    python3 t_radius_perf.py [1.0.265]
"""
import os, sys, time, socket, tempfile, threading, queue
from pathlib import Path
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.265'
OUT = '/home/claude/build/out/otp-%s/otp.py' % VER
tmp = tempfile.mkdtemp(prefix='t_r265perf_')
os.environ['OTP_CONFIG'] = tmp + '/otp.conf'
os.environ['OTP_STATE'] = tmp + '/state'          # never the live /var/lib/otp
os.environ['OTP_STATE_DIR'] = tmp + '/state'
g = {'__name__': 'otp_t265perf', '__file__': OUT}
exec(compile(open(OUT).read(), OUT, 'exec'), g)
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


LOGS = []
g['log'] = lambda w, level='info': LOGS.append((level, w))
g['log_sparing'] = lambda k, w, level='warn', every=30: LOGS.append((level, w))
CONFIG = g['CONFIG']


def in_thread(name, fn, *a):
    box = {}

    def run():
        try:
            box['v'] = fn(*a)
        except BaseException as e:          # noqa: BLE001
            box['e'] = e
    t = threading.Thread(target=run, name=name)
    t.start()
    t.join(30)
    if 'e' in box:
        raise box['e']
    return box.get('v')


# ---- P1 accounting lane ---------------------------------------------------------------
Db = g['Db']
db = Db(engine='sqlite', path=tmp + '/p1.db')
db.lanes_on = True
db.run('CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)')
main = db._lanes['main']
la = in_thread('radius-acct-2', db._pick)
lr = in_thread('radius-5', db._pick)
lw = in_thread('web-1', db._pick)
ok('P1 accounting worker: a lane of its own', la is db._lanes.get('radius-acct') and la is not main
   and la is not lr, list(db._lanes))
ok('P1 sign-in worker: the RADIUS lane as before', lr is db._lanes.get('radius'))
ok('P1 pages: the main lane', lw is main)
in_thread('radius-acct-0', db.run, "INSERT INTO t (v) VALUES ('x')")
ok('P1 accounting wrote on its own connection', la.conn is not None and la.conn is not main.conn
   and db.value('SELECT COUNT(*) FROM t') == 1)
src = open(OUT).read()
ok('P1 the accounting workers are named radius-acct-N', "name='radius-acct-%d' % i" in src
   and "name='acct-%d'" not in src)

# ---- P2 held() ------------------------------------------------------------------------
Directory = g['Directory']
row = {'name': 'ad', 'hosts': 'dc1,dc2', 'port': 636, 'tls': 'ldaps', 'base': 'DC=x,DC=cz',
       'bind_dn': 'CN=svc,DC=x,DC=cz', 'bind_pw': 'pw', 'timeout_s': 5}
ad = Directory(row)
Directory.BUSY.clear(); Directory.BUSY_TOOK.clear(); Directory.BUSY_WAITING.clear()
CONFIG['radius_workers'] = 64
g['RADIUS_WORKERS_RUNNING'][0] = 4       # most = 2 at once, whatever the setting says
Directory.BUSY_WAIT_S = 0.3


def local_work():
    with ad.held():
        time.sleep(0.6)                    # this node's own time: CPU, locks - no LDAP I/O
in_thread('radius-1', local_work)
ok('P2 local time is not the directory\'s', Directory.BUSY_TOOK.get('ad', 1) < 0.05,
   Directory.BUSY_TOOK)


def io_work():
    with ad.held():
        g['_ldap_io'](time.monotonic() - 0.7)   # 0.7 s waiting on the socket
in_thread('radius-1', io_work)
ok('P2 the directory\'s own time is counted', 0.15 < Directory.BUSY_TOOK.get('ad', 0) < 0.3,
   Directory.BUSY_TOOK)
Directory.BUSY_TOOK['ad'] = 0.01
gate = threading.Event()
inside = []


def hold():
    with ad.held():
        inside.append(1)
        gate.wait(10)
hs = [threading.Thread(target=hold, name='radius-%d' % (10 + i)) for i in range(2)]
for t in hs:
    t.start()
while len(inside) < 2:
    time.sleep(0.01)


def third():
    with ad.held():
        return 'in'
try:
    in_thread('radius-12', third)
    err = None
except g['LdapError'] as e:
    err = e
ok('P2 the limit counts the 4 workers running, not radius_workers=64',
   err is not None and getattr(err, 'held', False), err)
said = getattr(err, 'busy_said', '')
ok('P2 refused as "this node is busy: 2 requests wait for the directory ad"',
   said.startswith('this node is busy: 2 requests wait for the directory ad'), said)
Directory.BUSY_TOOK['ad'] = 0.9
t0 = time.time()
try:
    in_thread('radius-13', third)
    err2 = None
except g['LdapError'] as e:
    err2 = e
ok('P2 slow directory: refused at once, said with how slow', err2 is not None and
   time.time() - t0 < 0.25 and 'answers slowly (900 ms' in getattr(err2, 'busy_said', ''),
   (getattr(err2, 'busy_said', ''), time.time() - t0))
gate.set()
for t in hs:
    t.join()
g['clock_dir_failover'] = lambda store: ''
auth = g['Authenticator'](None, None, {})
d = auth.ldap_gone(g['Decision'](), err)
ok('P2 RADIUS refusal reason: this node is busy, not gone away', d.result == 'reject' and
   d.reason.startswith('this node is busy') and 'gone away' not in d.reason and not d.silent, d.reason)
ok('P2 ... and the sign-in protection does not count it', not g['guard_is_guess'](d))
d2 = auth.ldap_gone(g['Decision'](), g['LdapUnreachable']('no server of ad could be reached'))
ok('P2 a directory really away: still "gone away"', d2.reason == 'LDAP server(s) have gone away')
Directory.BUSY_TOOK.clear()

# ---- P3 stale and the fair queue -------------------------------------------------------
CONFIG.pop('radius_stale_s', None)
ok('P3 default 4 s', g['radius_stale_s']() == 4.0)
for v, want in ((10, 10.0), (0.2, 1.0), (999, 60.0), ('x', 4.0), (0, 4.0)):
    CONFIG['radius_stale_s'] = v
    ok('P3 radius_stale_s=%r -> %s' % (v, want), g['radius_stale_s']() == want, g['radius_stale_s']())
CONFIG.pop('radius_stale_s', None)


class FakeDaemon:
    store = None
    shipper = None


RS = g['RadiusServer']
rs = RS(FakeDaemon())
handled = []
rs.handle = lambda kind, sock, data, peer, arrived: handled.append(data)
now = time.time()
rs.jobs.put_nowait(('auth', None, b'old', ('192.0.2.1', 1), now - 5), key='a')
rs.jobs.put_nowait(('auth', None, b'new', ('192.0.2.1', 1), now), key='a')
quit = threading.Event()
t = threading.Thread(target=rs.work, kwargs={'quit': quit}, name='radius-0')
t.start()
for _ in range(100):
    if handled:
        break
    time.sleep(0.02)
quit.set(); t.join(3)
ok('P3 a request 5 s old dropped, a new one answered', handled == [b'new'] and rs.counts['stale'] == 1,
   (handled, dict(rs.counts)))
q = g['RadiusQueue'](maxsize=10)
for i in range(4):
    q.put_nowait('A%d' % i, key='A')
for i in range(2):
    q.put_nowait('B%d' % i, key='B')
order = [q.get(timeout=0.1) for _ in range(6)]
ok('P3 each line in turn, each in its order', order == ['A0', 'B0', 'A1', 'B1', 'A2', 'A3'], order)
for i in range(5):
    q.put_nowait(i, key='A')
try:
    q.put_nowait(5, key='A'); full = False
except queue.Full:
    full = True
q.put_nowait('b', key='B')
ok('P3 one line holds at most half: another still gets in', full and q.qsize() == 6)
try:
    for _ in range(6):
        q.get(timeout=0.01)
    q.get(timeout=0.05); empty = False
except queue.Empty:
    empty = True
ok('P3 empty: queue.Empty after the timeout', empty and q.qsize() == 0)
q2 = g['RadiusQueue'](maxsize=5000)
q2.KEYS_MOST = 3
for k in 'abcdef':
    q2.put_nowait(k, key=k)
ok('P3 past KEYS_MOST the rest share one line', q2.lines_now() == 4 and q2.qsize() == 6)


def pkt(name):
    attr = bytes([1, len(name) + 2]) + name
    body = bytes([1, 7]) + (20 + len(attr)).to_bytes(2, 'big') + b'\0' * 16 + attr
    return body
fk = g['radius_fair_key']
ok('P3 key: realm after @', fk(pkt(b'novak@Corp.CZ'), '10.0.0.1') == '10.0.0.1|corp.cz')
ok('P3 key: domain before \\', fk(pkt(b'CORP\\novak'), '10.0.0.1') == '10.0.0.1|corp')
ok('P3 key: plain name', fk(pkt(b'novak'), '10.0.0.1') == '10.0.0.1|')
ok('P3 key: junk is the address', fk(b'\x01\x02', '10.0.0.1') == '10.0.0.1' and
   fk(b'\x01\x07\x00\x30' + b'\0' * 16 + b'\x05\x00', '10.0.0.1') == '10.0.0.1')

# ---- P4 the key file, the isemon files --------------------------------------------------
state = Path(g['STATE_DIR'])
state.mkdir(parents=True, exist_ok=True)
kp = g['sealing_key_path']()
kp.write_text('11' * 32 + '\n')
g['sealing_key_forget']()
k1 = g['sealing_key']()
real_stat = os.stat
calls = []
g['os'].stat = lambda p, *a, **k: (calls.append(str(p)), real_stat(p, *a, **k))[1]
try:
    for _ in range(50):
        g['sealing_key']()
finally:
    g['os'].stat = real_stat
ok('P4 the key file not stat\'ed for each secret', k1 == bytes.fromhex('11' * 32) and
   len([c for c in calls if c.endswith('secrets.key')]) == 0, len(calls))
g['write_replacing'](kp, '22' * 32 + '\n', 0o600)
ok('P4 a key written by this process taken at once', g['sealing_key']() == bytes.fromhex('22' * 32))
kp.write_text('33' * 32 + '\n')
time.sleep(1.1)
ok('P4 one changed by hand taken within a second', g['sealing_key']() == bytes.fromhex('33' * 32))
sh = object.__new__(g['Shipper'])
sh.files, sh.trouble = {}, {}
logs = Path(tmp) / 'logs'
g['LOG_DIR'] = logs
calls = []
g['os'].stat = lambda p, *a, **k: (calls.append(str(p)), real_stat(p, *a, **k))[1]
try:
    for i in range(20):
        sh._to_file('radius-detail.log', 'line %d' % i)
finally:
    g['os'].stat = real_stat
ok('P4 isemon file: written, its folder made, not stat\'ed per line',
   (logs / 'radius-detail.log').read_text().count('\n') == 20 and len(calls) <= 1, len(calls))
(logs / 'radius-detail.log').rename(logs / 'radius-detail.log.1')
time.sleep(1.05)
sh._to_file('radius-detail.log', 'after')
ok('P4 isemon file: a rotation still noticed', (logs / 'radius-detail.log').read_text() == 'after\n')

# ---- P5 kept directory connections -------------------------------------------------------
class FakeLdap(object):
    opened, binds, searched = [], [], []
    fail_next = []

    def __init__(self, host, port=389, tls='none', ca_pem='', verify=True, timeout=10, weak=False):
        self.host, self.port, self.timeout = host, port, timeout
        self.buffer, self.sock, self.peer, self._deadline = b'', None, None, 0
        self.closed = False

    def open(self):
        self.sock, self.peer = socket.socketpair()
        FakeLdap.opened.append(self)
        return self

    def bind(self, dn, pw):
        FakeLdap.binds.append(dn)
        return True

    def search(self, base, flt, attrs=(), scope=2, limit=200, paged=False):
        if FakeLdap.fail_next:
            FakeLdap.fail_next.pop()
            raise g['LdapUnreachable']('the connection to %s failed: reset' % self.host)
        FakeLdap.searched.append(self)
        return [{'dn': 'CN=novak,DC=x,DC=cz', 'attrs': {'sAMAccountName': ['novak'],
                                                       'userAccountControl': ['512']}}]

    def close(self):
        self.closed = True
        for s in (self.sock, self.peer):
            try:
                s and s.close()
            except OSError:
                pass
        self.sock = None


g['Ldap'] = FakeLdap
Directory.POOL.clear(); Directory.DEAD.clear()
ad = Directory(row)
ad.find_user('a@x.cz'); ad.find_user('b@x.cz'); ad.find_user('c@x.cz')
ok('P5 three look-ups: one connection, one bind of the reading account',
   len(FakeLdap.opened) == 1 and FakeLdap.binds == ['CN=svc,DC=x,DC=cz'] and
   len(FakeLdap.searched) == 3, (len(FakeLdap.opened), FakeLdap.binds))
FakeLdap.opened[0].peer.close()            # the server closed it while kept
ad.find_user('d@x.cz')
ok('P5 one closed by the server is seen before use: a new one', len(FakeLdap.opened) == 2 and
   FakeLdap.opened[0].closed)
FakeLdap.fail_next.append(1)               # looks fine, fails on use
ad.find_user('e@x.cz')
ok('P5 a kept one failing: asked again on a new one, the server not marked down',
   len(FakeLdap.opened) == 3 and not any(v > time.time() for k, v in Directory.DEAD.items()
                                         if not k.startswith('probe:')), Directory.DEAD)
ad.password_ok({'dn': 'CN=novak,DC=x,DC=cz'}, 'Heslo')
ok('P5 a person\'s password on a connection of its own, not kept',
   len(FakeLdap.opened) == 4 and FakeLdap.opened[3].closed and FakeLdap.binds[-1] == 'CN=novak,DC=x,DC=cz'
   and sum(len(v) for v in Directory.POOL.values()) == 1)
Directory.POOL_IDLE_S = 0.0
time.sleep(0.01)
ad.find_user('f@x.cz')
ok('P5 one kept longer than the idle time: closed, a new one', len(FakeLdap.opened) == 5)
Directory.POOL_IDLE_S = 30.0
ad2 = Directory(dict(row, bind_pw='other'))
ad2.find_user('g@x.cz')
ok('P5 another reading account never gets a kept connection of the first', len(FakeLdap.opened) == 6)
ad._down('dc1')
ok('P5 a server marked down: its kept connections closed',
   not any(k[0] == 'dc1' for k in Directory.POOL))
Directory.DEAD.clear()

# ---- P6 the cache ------------------------------------------------------------------------
c = Directory(row)
c.CACHE_MOST = 5
for i in range(7):
    c._cache_put(('u', 'upn', 'p%d' % i), {'n': i})
ok('P6 the oldest let go, the rest kept', len(c.cache) == 5 and ('u', 'upn', 'p0') not in c.cache
   and ('u', 'upn', 'p6') in c.cache and ('u', 'upn', 'p2') in c.cache, list(c.cache))
c._cache_put(('u', 'upn', 'p2'), {'n': 2})
c._cache_put(('u', 'upn', 'p7'), {'n': 7})
ok('P6 written again counts as new', ('u', 'upn', 'p2') in c.cache and ('u', 'upn', 'p3') not in c.cache,
   list(c.cache))

# ---- P7b workers live ----------------------------------------------------------------------
rs = RS(FakeDaemon())
rs.handle = lambda *a: None
rs.resize_workers(3)
names = sorted(t.name for t, _q in rs.auth_workers)
ok('P7b three workers', rs.workers_running() == 3 and g['RADIUS_WORKERS_RUNNING'][0] == 3 and
   names == ['radius-0', 'radius-1', 'radius-2'], names)
rs.resize_workers(1)
ok('P7b down to one at once', rs.workers_running() == 1 and g['RADIUS_WORKERS_RUNNING'][0] == 1)
time.sleep(1.3)
ok('P7b the others ended', len([t for t in rs.workers if t.is_alive()]) == 1, [t.name for t in rs.workers])
CONFIG['radius_workers'] = 5
rs.resize_workers()
names = sorted(t.name for t, _q in rs.auth_workers)
ok('P7b up to radius_workers=5, names apart', rs.workers_running() == 5 and len(set(names)) == 5, names)
ok('P7b a reload resizes (open_sockets calls resize_workers)',
   'self.resize_workers()' in src.split('def open_sockets(self):', 1)[1].split('def _open_sockets', 1)[0])
ok('P7b the help says so', 'starts or stops workers at once' in g['SAYS'].get('radius_workers', ''))
rs.stop_flag = True
time.sleep(1.2)
CONFIG['radius_workers'] = 16

# ---- P7c sending codes ---------------------------------------------------------------------
class CStore:
    def __init__(self):
        self.rows = []

    def otp_add(self, r):
        self.rows.append(r)

    def add_event(self, *a, **k):
        pass
gave = []
g['node_key_give_back'] = lambda store, prefix, name, when=None: gave.append(name)
release = threading.Event()
sent = []


def fake_send(store, kind, to, code, name='', **k):
    if kind == 'mail' and to.startswith('hang'):
        release.wait(10)
    if kind == 'sms' and to.startswith('slow'):
        time.sleep(1.5)
    sent.append((kind, to))
    return 'sent'
g['code_send'] = fake_send
g['CODE_WAITING_MOST'] = 3
st = CStore()
for i in range(3):
    g['code_send_later'](st, 'mail', 'hang%d@x.cz' % i, '123456', 'm%d' % i)
r4 = g['code_send_later'](st, 'mail', 'm4@x.cz', '123456', 'm4')
ok('P7c mail full: the fourth not taken, given back, said', r4 is False and 'm4' in gave and
   any('too many codes are waiting' in r['said'] for r in st.rows))
r5 = g['code_send_later'](st, 'sms', '+420603000000', '123456', 's1')
for _ in range(100):
    if ('sms', '+420603000000') in sent:
        break
    time.sleep(0.02)
ok('P7c SMS still sent while mail hangs', r5 is True and ('sms', '+420603000000') in sent, sent)
release.set()
for _ in range(100):
    if g['CODE_WAITING_BY']['mail'] == 0:
        break
    time.sleep(0.02)
ok('P7c mail drained', g['CODE_WAITING_BY']['mail'] == 0 and g['CODE_WAITING'][0] == 0,
   (g['CODE_WAITING_BY'], g['CODE_WAITING']))
CONFIG['code_ttl_s'] = 1
g['CODE_SENDING_BY']['sms'] = threading.BoundedSemaphore(1)
gave.clear(); st.rows.clear(); sent.clear()
g['code_send_later'](st, 'sms', 'slow1', '111111', 's2')
time.sleep(0.1)
g['code_send_later'](st, 'sms', '+420603111111', '222222', 's3')
for _ in range(200):
    if g['CODE_WAITING_BY']['sms'] == 0:
        break
    time.sleep(0.02)
ok('P7c a code whose turn came after code_ttl_s: not sent, given back, said',
   ('sms', '+420603111111') not in sent and 's3' in gave and
   any(r['name'] == 's3' and r['ok'] == 0 and 'longer than a code is good for' in r['said']
       for r in st.rows), (sent, gave, st.rows))
ok('P7c ... the one in time was sent', ('sms', 'slow1') in sent)
CONFIG['code_ttl_s'] = 300

# ---- P7d ma_known ----------------------------------------------------------------------------
class MDb:
    def __init__(self, keys):
        self.keys, self.sql, self.fail = set(keys), [], False

    def rows(self, sql, args=()):
        self.sql.append(sql)
        if self.fail:
            raise RuntimeError('database is locked')
        if "LIKE 'maseen:%'" in sql:
            return [{'k': k} for k in self.keys if k.startswith('maseen:')]
        if ' IN (' in sql:
            return [{'k': k} for k in args if k in self.keys]
        return []


class MStore:
    def __init__(self, keys):
        self.db = MDb(keys)


class MDaemon:
    def __init__(self, keys):
        self.store = MStore(keys)
g['node_name'] = lambda: 'otp1'
g['ha_nodes'] = lambda store: [{'name': 'otp1'}, {'name': 'otp2'}]
md = MDaemon(['maseen:otp2:7:10.0.0.5', 'maseen:old:7:2001:db8::9', 'maseen:otp1:8:10.0.0.6'])
rs = RS(md)
ok('P7d a key of the other node found', rs.ma_known(7, '10.0.0.5') is True)
ok('P7d a key under a node gone (only in the keys) found', rs.ma_known(7, '2001:db8::9') is True)
ok('P7d another client\'s address: not known', rs.ma_known(7, '10.0.0.6') is False)
likes = [s for s in md.store.db.sql if 'LIKE' in s]
ins = [s for s in md.store.db.sql if ' IN (' in s]
ok('P7d LIKE read once for all of them, exact keys per request', len(likes) == 1 and len(ins) == 3,
   md.store.db.sql)
md.store.db.fail = True
rs._ma_nodes = None
try:
    rs.ma_known(9, '10.0.0.9'); raised = False
except g['DbError']:
    raised = True
ok('P7d database not answering: not taken as "never signed"', raised and (9, '10.0.0.9') not in rs.ma_asked)

print('%d/%d passed' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
