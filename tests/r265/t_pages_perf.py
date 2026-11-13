"""t_pages_perf.py - 1.0.265, the pages under load: the token counts and the DB part of the status
kept a few seconds (a hit within the time, made again after it and after a token made, deleted or
its state changed); the heavy pages a few at a time (503 busy past the wait, the light routes never
counted); the lists' connection busy -> 503 rather than queued; the sign-in throttles counting an
address loosely (ip_tries) and the name as before; a database put back refused (507) without room;
GET /api/mailq keeps the badge's count instead of throwing it away; core.js api() asking once more
on busy and apiLatest letting a superseded list go. The parts concatenated as build.sh does into a
temporary otp.py, loaded as a module over SQLite - no daemon, no ports.

    python3 t_pages_perf.py [version]
"""
import collections, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, threading
import time, atexit
_OUTV = sys.argv[1] if len(sys.argv) > 1 else '1.0.265'
BUILD = '/home/claude/build'
CORE = BUILD + '/out/otp-%s/web/assets/core.js' % _OUTV
ADMIN = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_pperf_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'pp1', 'api_port': 29962}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
                  OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', TOP + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.sealing_key(make=True)
S = m.Storage


def raw_token(name, state='active'):
    """A token written past token_write - as the other node's would come over."""
    st.db.insert('tokens', {'name': name, 'state': state, 'last_step': 0, 'failures': 0,
                            'fail_times': '[]', 'scratch': '[]', 'scratch_left': 0,
                            'created': time.time(), 'window_steps': -1})


def age(cache, by):
    cache['at'] -= by


# ==== 1. the token counts, kept a few seconds ============================================================
for i in range(3):
    st.token_write('pp%d' % i, {'secret': 'x'})
c1 = st.token_counts()
ok('1 counts: three tokens', c1['all'] == 3 and c1['active'] == 3, c1)
real = S._token_counts
calls = [0]


def counting(self):
    calls[0] += 1
    return real(self)


S._token_counts = counting
raw_token('pp-raw')
c2 = st.token_counts()
ok('1 within the time: kept (one written past the store not seen yet), not counted again',
   c2['all'] == 3 and calls[0] == 0, (c2, calls))
c2['all'] = 999
ok('1 a copy each time: changing an answer changes not the kept one', st.token_counts()['all'] == 3)
age(S.TOKEN_COUNTS, S.TOKEN_COUNTS_S + 1)
c3 = st.token_counts()
ok('1 after the time: counted again', c3['all'] == 4 and calls[0] == 1, (c3, calls))
st.token_write('pp-new', {'secret': 'x'})
c4 = st.token_counts()
ok('1 a token made: counted again at once', c4['all'] == 5 and calls[0] == 2, (c4, calls))
st.token_write('pp-new', {'last_used': time.time()})
st.token_counts()
ok('1 a field other than the state changed: kept', calls[0] == 2, calls)
tid = st.token('pp0')['id']
st.token_update(tid, {'state': 'disabled'})
c5 = st.token_counts()
ok('1 a state changed (token_update): counted again', c5['disabled'] == 1 and calls[0] == 3, (c5, calls))
st.token_write('pp1', {'state': 'disabled'})
c6 = st.token_counts()
ok('1 a state changed (token_write): counted again', c6['disabled'] == 2 and calls[0] == 4, (c6, calls))
st.token_drop('pp-new')
c7 = st.token_counts()
ok('1 a token deleted: counted again', c7['all'] == 4 and calls[0] == 5, (c7, calls))
# Many pages at once: one look at the table, the rest take its answer.
age(S.TOKEN_COUNTS, S.TOKEN_COUNTS_S + 1)
slow_calls = [0]


def slow(self):
    slow_calls[0] += 1
    time.sleep(0.2)
    return real(self)


S._token_counts = slow
got = []
ts = [threading.Thread(target=lambda: got.append(st.token_counts())) for _ in range(12)]
[t.start() for t in ts]
[t.join() for t in ts]
ok('1 twelve pages at once: counted once, all twelve answered alike',
   slow_calls[0] == 1 and len(got) == 12 and all(g == got[0] for g in got), (slow_calls, len(got)))
# Made stale while being counted: that count is not kept.
age(S.TOKEN_COUNTS, S.TOKEN_COUNTS_S + 1)


def stale_midway(self):
    out = real(self)
    S.token_counts_stale()
    return out


S._token_counts = stale_midway
st.token_counts()
ok('1 made stale while counted: not kept', S.TOKEN_COUNTS['at'] == 0.0, S.TOKEN_COUNTS)
S._token_counts = real
ok('1 the counts as before (identical to a fresh count)', st.token_counts() == real(st))
# Another database (put back, moved): never the other one's counts.
st2 = m.Storage.view(st.db)
ok('1 the same database through a view: the same counts', st2.token_counts() == st.token_counts())

# ==== 2. the DB part of the status, kept a few seconds ===================================================
Dm = m.Daemon


class FakeD(object):
    STATUS_DB_S = Dm.STATUS_DB_S
    STATUS_DB = {'db': None, 'at': 0.0, 'got': None}
    STATUS_DB_LOCK = threading.Lock()
    _status_db = Dm._status_db

    def __init__(self, store):
        self.store = store


now = time.time()
for i, res in enumerate(('accept', 'accept', 'reject', 'drop')):
    st.db.insert('radius_log', {'ts': now - 60 + i, 'packet': 'Access-Request', 'result': res,
                                'username': 'u%d' % i, 'node': 'pp1'})
fd = FakeD(st)
k1 = fd._status_db()
ok('2 status: the day counted', k1['acc'] == 2 and k1['rej'] == 2 and k1['last']['username'] == 'u3', k1)
st.db.insert('radius_log', {'ts': now, 'packet': 'Access-Request', 'result': 'accept',
                            'username': 'u9', 'node': 'pp1'})
k2 = fd._status_db()
ok('2 status within the time: kept', k2['acc'] == 2 and k2['last']['username'] == 'u3', k2)
age(FakeD.STATUS_DB, FakeD.STATUS_DB_S + 1)
k3 = fd._status_db()
ok('2 status after the time: counted again', k3['acc'] == 3 and k3['last']['username'] == 'u9', k3)
# The whole status, if it can be made here: its day and tokens as counted fresh.
try:
    full = Dm.__new__(Dm)
    full.store, full.radius, full.shipper, full.siem = st, None, None, None
    full.dirs, full.started = {}, time.time()
    Dm.STATUS_DB.update(at=0.0, got=None)
    sres = full.status()
    ok('2 daemon.status(): day and tokens as a fresh count',
       sres['day'] == {'accept': 3, 'reject': 2} and sres['tokens'] == real(st), (sres['day'], sres['tokens']))
    src = open(BUILD + '/parts/80_daemon.py').read()
    ok('2 status: the serial still read every time',
       re.search(r"def status\(self\):[\s\S]{0,400}MAX\(id\) AS n FROM radius_log", src) is not None)
except Exception as e:                                  # noqa: BLE001
    ok('2 daemon.status() could be made here (%s)' % type(e).__name__, False, e)

# ==== 3. the heavy pages a few at a time ===================================================================
m.PAGE_SLOT_WAIT_S = 0.15
held = []
try:
    for _ in range(m.PAGE_SLOTS_N):
        held.append(m.page_slot('GET', '/api/tokens'))
    ok('3 %d heavy pages at once: each a place' % m.PAGE_SLOTS_N, all(h is m.PAGE_SLOTS for h in held))
    t0 = time.time()
    try:
        m.page_slot('GET', '/api/activity')
        ok('3 one more: busy', False, 'given a place')
    except m.ApiError as e:
        ok('3 one more: 503 busy after the wait', e.status == 503 and (e.extra or {}).get('busy')
           and 0.1 <= time.time() - t0 < 2, (e.status, e.extra))
    for path in ('/api/health', '/api/auth/whoami', '/api/portal/me', '/api/portal/info',
                 '/api/metrics', '/api/acme/challenge', '/api/db/download'):
        ok('3 never counted: GET ' + path, m.page_slot('GET', path) is None)
    ok('3 never counted: a change (POST)', m.page_slot('POST', '/api/tokens') is None)
finally:
    for h in held:
        h.release()
ok('3 all places given back', all(m.PAGE_SLOTS.acquire(False) for _ in range(m.PAGE_SLOTS_N)))
for _ in range(m.PAGE_SLOTS_N):
    m.PAGE_SLOTS.release()

# Through the handler itself: the answer, and the place given back after an answer and an error.
TOKEN = m.api_token(make=True)


@m.route('GET', '/api/t-pp-heavy')
def _t_heavy(h):
    return {'n': 1}


@m.route('GET', '/api/t-pp-broken')
def _t_broken(h):
    raise m.ApiError(400, 'no')


class FakeServer(object):
    def __init__(self, daemon):
        self.daemon = daemon


def ask(path, daemon=None):
    hd = m.ApiHandler.__new__(m.ApiHandler)
    hd.server = FakeServer(daemon)
    hd.path = path
    hd.command = 'GET'
    hd.request_version = 'HTTP/1.1'
    hd.requestline = 'GET %s HTTP/1.1' % path
    hd.client_address = ('127.0.0.1', 1)
    hd.headers = {'X-Otp-Token': TOKEN}
    hd.wfile = io.BytesIO()
    hd.route('GET')
    raw = hd.wfile.getvalue().decode('utf-8', 'replace')
    status = int(raw.split(' ', 2)[1])
    return status, json.loads(raw.split('\r\n\r\n', 1)[1])


m.ApiHandler._signed_in = lambda self: True     # the places are taken by somebody signed in (1.0.271)
st_, body = ask('/api/t-pp-heavy')
ok('3 handler: a heavy page answered while there is room', st_ == 200 and body.get('n') == 1, (st_, body))
ask('/api/t-pp-broken')
ok('3 handler: the place given back after an error too',
   all(m.PAGE_SLOTS.acquire(False) for _ in range(m.PAGE_SLOTS_N)))
try:
    st_, body = ask('/api/t-pp-heavy')
    ok('3 handler: no room -> 503 {"busy": true} with the words',
       st_ == 503 and body.get('busy') is True and 'busy' in body.get('error', ''), (st_, body))
    st_, body = ask('/api/health')
    ok('3 handler: the health check answered with no room', st_ == 200, (st_, body))
finally:
    for _ in range(m.PAGE_SLOTS_N):
        m.PAGE_SLOTS.release()

# ==== 3b. the lists' connection: busy rather than queued ==================================================
m.READER_WAIT_S = 0.15


class PgDb(object):
    engine = 'postgres'


class PgStore(object):
    db = PgDb()


dmn = Dm.__new__(Dm)
dmn.store = PgStore()
dmn._reader = None
dmn._reader_lock = threading.Lock()
dmn._reader_lock.acquire()
t0 = time.time()
try:
    dmn.reader(wait=0.1)
    ok('3b reader opening elsewhere: busy', False, 'waited it out')
except m.ReaderBusy:
    ok('3b reader opening elsewhere: ReaderBusy after the wait', time.time() - t0 < 1)
dmn._reader_lock.release()
ok('3b reader on SQLite: the store itself, no wait', Dm.reader(type('X', (), {'store': st})(), wait=0.1) is st)
lane_lock = st.db._lanes['main'].lock
gate, done = threading.Event(), threading.Event()


def holder():
    with lane_lock:
        gate.set()
        done.wait(5)


th = threading.Thread(target=holder)
th.start()
gate.wait(2)
try:
    m.reader_free_or_busy(st)
    ok('3b a statement holding the lists\' connection: busy', False, 'waited')
except m.ApiError as e:
    ok('3b a statement holding the lists\' connection: 503 busy', e.status == 503 and e.extra.get('busy'))
done.set()
th.join()
try:
    m.reader_free_or_busy(st)
    ok('3b the connection free: no wait, no error', True)
except m.ApiError as e:
    ok('3b the connection free: no wait, no error', False, e)

# ==== 4. the sign-in throttles: the address loosely, the name as before ====================================
Handler = m.ApiHandler


class TD(object):
    def __init__(self):
        self.login_fails = collections.defaultdict(list)
        self.login_info = {}


class TH(object):
    throttle = Handler.throttle
    failed = Handler.failed
    _release = Handler._release
    THROTTLE_LOCK = Handler.THROTTLE_LOCK
    THROTTLE_TIDIED = [0.0]

    def __init__(self, d, ip='192.0.2.7'):
        self.d, self.ip, self._held, self._failed = d, ip, None, False

    def client_ip(self):
        return self.ip


# What the two sign-ins pass, from the routes themselves (the call recorded, nothing else run).
class Stop(Exception):
    pass


seen = {}


class RecH(object):
    headers = {}

    def __init__(self, body):
        self._body = body

    def body(self):
        return self._body

    def throttle(self, kind, tries, wait_min, **kw):
        seen[kind] = dict(kw, tries=tries)
        raise Stop()


m.CONFIG['portal'] = True
for fn, kind, key in ((m._login, 'admin', 'login_tries'), (m._portal_login, 'portal', 'portal_tries')):
    for tries in (5, 3, 8):
        m.CONFIG[key] = tries
        try:
            fn(RecH({'name': 'novak', 'password': 'x'}))
        except Stop:
            pass
        kw = seen.get(kind) or {}
        ok('4 %s sign-in, %s=%d: ip_tries %d, name as before' % (kind, key, tries, max(50, tries * 10)),
           kw.get('ip_tries') == max(50, tries * 10) and kw.get('tries') == tries
           and kw.get('name') == 'novak' and kw.get('name_tries') is None, kw)
    m.CONFIG[key] = 5
mfa_src = open(BUILD + '/parts/90m_mfa.py').read()
ok('4 the second step of the admin sign-in: the same loose count for the address',
   mfa_src.count("ip_tries=max(50, int(CONFIG.get('login_tries') or 5) * 10)") == 2)
# The counts themselves: twelve people behind one address with a typo each - none locked out.
d = TD()
locked = 0
for i in range(12):
    h = TH(d)
    try:
        k = h.throttle('portal', 5, 15, name='user%d' % i, ip_tries=50)
        h.failed(k)
    except m.ApiError:
        locked += 1
    h._release()
ok('4 twelve wrong passwords of twelve people at one address: nobody locked out', locked == 0, locked)
d = TD()
locked = 0
for i in range(12):
    h = TH(d)
    try:
        k = h.throttle('portal', 5, 15, name='user%d' % i)
        h.failed(k)
    except m.ApiError:
        locked += 1
    h._release()
ok('4 (as it was without ip_tries: the address locked after 5)', locked == 7, locked)
d = TD()
said = None
for i in range(25):
    h = TH(d, ip='192.0.2.%d' % (i % 250 + 1))
    try:
        k = h.throttle('portal', 5, 15, name='novak', ip_tries=50)
        h.failed(k)
    except m.ApiError as e:
        said = (i, e.status, str(e))
        break
ok('4 one name guessed from many addresses: locked after 20 (tries*4) as before',
   said and said[0] == 20 and said[1] == 429 and 'this name' in said[2], said)
d = TD()
said = None
for i in range(60):
    h = TH(d)
    try:
        k = h.throttle('portal', 5, 15, name='n%d' % i, ip_tries=50)
        h.failed(k)
    except m.ApiError as e:
        said = (i, e.status)
        break
ok('4 one address guessing many names: locked after 50', said == (50, 429), said)

# ==== 5. a database put back: room first =================================================================
class RestoreH(object):
    def __init__(self, length):
        self.headers = {'Content-Length': str(length)}
        self.args = {}
        self.wrote = False

    def me(self, role='readonly'):
        return {'name': 'admin', 'role': 'fulladmin'}

    def arg(self, k, default=''):
        return self.args.get(k, default)

    def body_to_file(self, path, most):
        self.wrote = True
        raise Stop()


def uploads():
    return [p for p in os.listdir(str(m.STATE_DIR)) if p.startswith('otp-upload-')]


free = shutil.disk_usage(str(m.STATE_DIR)).free
h = RestoreH(free)            # twice the free space needed and more
try:
    m._db_restore(h)
    ok('5 restore with no room: refused', False, 'went on')
except m.ApiError as e:
    ok('5 restore with no room: 507, said where and how much', e.status == 507 and
       str(m.STATE_DIR) in str(e) and 'MB free' in str(e) and not h.wrote, (e.status, str(e)))
ok('5 restore with no room: nothing left behind', not uploads(), uploads())
h = RestoreH(1024)
try:
    m._db_restore(h)
except Stop:
    pass
ok('5 restore with room: the file is taken as before', h.wrote and not uploads(), (h.wrote, uploads()))
h = RestoreH('x')
try:
    m._db_restore(h)
except Stop:
    pass
except Exception as e:                                  # noqa: BLE001
    h.err = e
ok('5 a length that is no number: left to body_to_file as before', h.wrote, getattr(h, 'err', None))

# ==== 6. GET /api/mailq: the badge's count kept, not thrown away ==========================================
class MqH(object):
    store = st

    def __init__(self):
        self.args = {}

    def me(self, role='readonly'):
        return {'name': 'admin', 'role': 'fulladmin'}

    def arg(self, k, default=''):
        return self.args.get(k, default)

    num = Handler.num


m.MAILQ_COUNT_CACHE[:] = [0.0, {}]
t0 = time.time()
got = m._mailq(MqH())
ok('6 GET mailq: the badge\'s count set from the same look (not reset)',
   m.MAILQ_COUNT_CACHE[0] >= t0 and m.MAILQ_COUNT_CACHE[1] == got['counts'], m.MAILQ_COUNT_CACHE)

# ==== 7. the pages: core.js and admin.js =================================================================
node = shutil.which('node')
if not node:
    ok('7 node is here to try core.js', False, 'no node')
else:
    core = open(CORE, encoding='utf-8').read()

    def grab(name):
        i = core.index('function %s(' % name)
        depth, j, started = 0, i, False
        while True:
            ch = core[j]
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
                if started and depth == 0:
                    return core[i:j + 1]
            j += 1

    js = ('var API_WAIT_GET = 20, API_WAIT_POST = 150;\n'
          'function signedOutForSure() { return Promise.resolve(false); }\n'
          'function signedOutNow() { throw new Error("signed out"); }\n'
          'var LATEST = {}; var LATEST_OUT = {};\n'
          + grab('api') + '\n' + grab('apiLatest') + '\n' + grab('apiLatestOut') + '\n' + r'''
var origST = setTimeout;
setTimeout = function (f, ms) { return origST(f, Math.min(ms, 5)); };
var calls = [], plan = [];
global.fetch = function (url, opts) {
  calls.push(url);
  var p = plan.shift() || {status: 200, body: {ok: true, n: calls.length}};
  if (p.hang) return new Promise(function (ok, bad) {
    opts.signal.addEventListener('abort', function () { bad(new Error('aborted')); });
  });
  return Promise.resolve({status: p.status, ok: p.status < 400,
                          text: function () { return Promise.resolve(JSON.stringify(p.body)); }});
};
var busy = {status: 503, body: {ok: false, busy: true, error: 'the server is busy - try again in a moment'}};
var out = {};
(async function () {
  plan = [busy, {status: 200, body: {ok: true, v: 7}}];
  var d = await api('status');
  out.retried = d.v === 7 && calls.length === 2;
  calls = []; plan = [busy, busy];
  try { await api('status'); out.twice = 'answered'; } catch (e) { out.twice = [e.busy, e.unreachable, e.status, e.message, calls.length]; }
  calls = []; plan = [busy];
  try { await api('tokens', {a: 1}); out.post = 'answered'; } catch (e) { out.post = [e.busy, calls.length]; }
  calls = []; plan = [{hang: true}, {status: 200, body: {ok: true, v: 2}}];
  var first = apiLatest('k', 'tokens&q=a');
  var outWhile = apiLatestOut('k');
  var second = apiLatest('k', 'tokens&q=b');
  var r1; try { await first; r1 = 'answered'; } catch (e) { r1 = e.stopped ? 'stopped' : e.message; }
  var r2 = await second;
  out.latest = [outWhile, r1, r2.v, apiLatestOut('k')];
  console.log(JSON.stringify(out));
})().catch(function (e) { console.log(JSON.stringify({err: String(e && e.stack || e)})); });
''')
    probe = TOP + '/probe.js'
    open(probe, 'w').write(js)
    p = subprocess.run([node, probe], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:                                   # noqa: BLE001
        o = {'err': p.stdout + p.stderr}
    ok('7 core.js: busy once -> asked again, answered', o.get('retried') is True, o)
    ok('7 core.js: busy twice -> an error with .busy and .unreachable, the daemon\'s words',
       o.get('twice') == [True, True, 503, 'the server is busy - try again in a moment', 2], o)
    ok('7 core.js: a change (POST) busy -> not sent again', o.get('post') == [True, 1], o)
    ok('7 core.js: apiLatest - out while asked, the older let go as stopped, the newer drawn, none out after',
       o.get('latest') == [True, 'stopped', 2, False], o)
    admin = open(ADMIN, encoding='utf-8').read()
    tick = admin[admin.index('function tick() {\n  if (!LIVE'):]
    tick = tick[:tick.index('\n}\n') + 3]
    ok('7 admin.js tick: one at a time, no list started while the last is out, busy not "down"',
       'TICK_OUT' in tick and '!apiLatestOut(TAB_LIST[TAB])' in tick and 'e.busy' in tick
       and 'TICK_OUT = 0' in tick)
    for f in (CORE, ADMIN):
        p = subprocess.run([node, '--check', f], capture_output=True, text=True)
        ok('7 node --check ' + os.path.basename(f), p.returncode == 0, p.stderr)

print('%d/%d passed' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
