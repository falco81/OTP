# t_latency.py VERSION [ENGINE] - how fast RADIUS answers, and whether rightly, alone and
# while everything else runs at once: the dashboard, the log, the events and the
# Prometheus scrape asked over and over, a backup and a dump, the log files rotated
# with a SIGHUP as logrotate does at night, settings saved, a big radius_log.
# Every right code not used before must be let in, every wrong or used one refused;
# no request may go unanswered. Prints p50/p95/p99/max per phase.
# Usage (as root): python3 t_latency.py VERSION
import os, sys, json, time, base64, hmac, hashlib, struct, random, threading, subprocess, signal
import urllib.request, tempfile, atexit, collections

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.186'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-lat-')
os.makedirs(D + '/run')
API, RAD = 31091, 37010
SECRET = 'latency-secret-0123456789'
N_TOK = int(os.environ.get('N_TOK', '400'))
THREADS = int(os.environ.get('THREADS', '24'))
PHASE_S = float(os.environ.get('PHASE_S', '25'))
ENGINE = sys.argv[2] if len(sys.argv) > 2 else 'sqlite'
SLOW = 3 if ENGINE != 'sqlite' else 1      # a database over the network: each write a round trip and an fsync
conf = {'db_engine': ENGINE, 'radius_bind': '127.0.0.1', 'radius_auth_port': RAD, 'radius_acct_port': RAD + 1,
        'api_port': API, 'node_name': 'otp1'}
if ENGINE == 'postgres':
    # A PostgreSQL of its own for the test, on a port of its own.
    PGB = '/usr/lib/postgresql/16/bin'
    PG = D + '/pg'
    os.makedirs(PG)
    os.system('chown postgres %s %s' % (D, PG))
    os.chmod(D, 0o755)
    subprocess.run(['runuser', '-u', 'postgres', '--', PGB + '/initdb', '-D', PG, '-A', 'trust', '-U', 'postgres'],
                   check=True, capture_output=True)
    subprocess.run(['runuser', '-u', 'postgres', '--', PGB + '/pg_ctl', '-D', PG, '-o', '-p 35432 -k ' + PG +
                    (' -c log_min_duration_statement=0 -c log_line_prefix=%m:' if os.environ.get('PGLOG') else ''), '-l',
                    PG + '/log', '-w', 'start'], check=True, capture_output=True)
    atexit.register(lambda: subprocess.run(['runuser', '-u', 'postgres', '--', PGB + '/pg_ctl', '-D', PG, '-m', 'fast',
                                            'stop'], capture_output=True))
    for q in ("CREATE USER otp PASSWORD 'otp-test-pass'", 'CREATE DATABASE otp OWNER otp'):
        subprocess.run(['runuser', '-u', 'postgres', '--', PGB + '/psql', '-h', PG, '-p', '35432', '-c', q],
                       check=True, capture_output=True)
    conf.update(db_host='127.0.0.1', db_port=35432, db_name='otp', db_user='otp', db_password='otp-test-pass')
json.dump(conf, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-186!', must_change=0)
st.client_save({'name': 'lo', 'address': '127.0.0.1', 'secret': SECRET, 'enabled': 1})
st.realm_save({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'})
tk = otp.Tokens(st)
KEYS = {}
t0 = time.time()
for i in range(N_TOK):
    n = 'user%04d' % i
    s = tk.enroll(n, 'load')['secret'].replace(' ', '')
    KEYS[n] = base64.b32decode(s + '=' * (-len(s) % 8))
print('%d tokens in %.1f s' % (N_TOK, time.time() - t0), flush=True)
# Months of requests already there: the pages' queries are not free.
import sqlite3  # noqa: E402
now = time.time()
LOGROWS = [(now - random.random() * 86400 * 60, 'user%04d' % random.randrange(N_TOK), 'lo', '127.0.0.1',
            random.choice(['accept', 'reject']), 'Access-Request', 'otp1', random.randrange(40))
           for _ in range(int(os.environ.get('N_LOG', '200000')))]
if ENGINE == 'sqlite':
    dbf = [os.path.join(D, f) for f in os.listdir(D) if f.endswith('.db')][0]
    cx = sqlite3.connect(dbf)
    cx.executemany("INSERT INTO radius_log (ts, username, client, src, result, packet, node, took_ms) VALUES (?,?,?,?,?,?,?,?)",
                   LOGROWS)
    cx.commit()
    cx.close()
else:
    import psycopg2, psycopg2.extras  # noqa: E401,E402
    cx = psycopg2.connect(host='127.0.0.1', port=35432, dbname='otp', user='otp', password='otp-test-pass')
    psycopg2.extras.execute_values(cx.cursor(), "INSERT INTO radius_log (ts, username, client, src, result, packet, node, took_ms) VALUES %s",
                                   LOGROWS, page_size=5000)
    cx.commit()
    cx.close()
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(lambda: d.poll() is None and d.terminate())
time.sleep(7)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None, extra=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    h.update(extra or {})
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-186!'})[1]['token']
call('/api/settings', {'settings': {'metrics': 1}}, S)
MT = call('/api/metrics', {'action': 'token'}, S)[1]['token']


def code_of(key, step):
    h = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    o = h[-1] & 15
    return '%06d' % ((struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 1000000)


USED = set()
ULOCK = threading.Lock()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def phase(name, seconds):
    stop = time.time() + seconds
    lat, res, bad = [], collections.Counter(), []
    lk = threading.Lock()

    def worker():
        rnd = random.Random()
        while time.time() < stop:
            # Wrong codes only for the last quarter of the names: ten of them lock a
            # name out (lockout_after), and a right code is then refused - rightly.
            want = rnd.random() < 0.7
            n = 'user%04d' % (rnd.randrange(N_TOK * 3 // 4) if want else rnd.randrange(N_TOK * 3 // 4, N_TOK))
            step = int(time.time()) // 30
            with ULOCK:
                fresh = (n, step) not in USED
                if want and fresh:
                    USED.add((n, step))
            code = code_of(KEYS[n], step) if want else '%06d' % rnd.randrange(1000000)
            expect = 'accept' if (want and fresh) else 'reject'
            if not want and code == code_of(KEYS[n], step):
                continue
            t = time.time()
            try:
                c, said, _ms = otp.radius_ask('127.0.0.1', RAD, SECRET, n, code, timeout=5, tries=1)
                got = {2: 'accept', 3: 'reject'}.get(c, str(c))
            except Exception as e:                      # noqa: BLE001
                got, said = 'timeout', str(e)
            dt = (time.time() - t) * 1000
            # A right code sent at the very edge of a 30 s step may be checked in the next:
            # still one of the window - accepted; never a wrong one.
            with lk:
                res[got] += 1
                if got != 'timeout':
                    lat.append(dt)
                if got != expect and not (got == 'reject' and expect == 'accept' and int(time.time()) // 30 != step):
                    bad.append((n, expect, got, str(said)[:120]))
    th = [threading.Thread(target=worker) for _ in range(THREADS)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))] if lat else -1
    print('%-34s %6d req (%5.0f/s)  p50 %6.1f  p95 %6.1f  p99 %6.1f  max %7.1f ms  %s' % (
        name, len(lat), len(lat) / seconds, q(.5), q(.95), q(.99), lat[-1] if lat else -1, dict(res)), flush=True)
    return lat, res, bad


def paced(name, rate, seconds):
    """Requests at a steady rate (as many VPN gateways asking), each in a thread of
    the pool - the latency each sees, not how many fit."""
    import concurrent.futures as cf
    lat, res, bad = [], collections.Counter(), []
    lk = threading.Lock()
    rnd = random.Random()

    def one(n, code, expect, step):
        t = time.time()
        try:
            c, said, _ms = otp.radius_ask('127.0.0.1', RAD, SECRET, n, code, timeout=5, tries=1)
            got = {2: 'accept', 3: 'reject'}.get(c, str(c))
        except Exception as e:                          # noqa: BLE001
            got, said = 'timeout', str(e)
        dt = (time.time() - t) * 1000
        with lk:
            res[got] += 1
            if got != 'timeout':
                lat.append(dt)
            if got != expect and not (expect == 'accept' and int(time.time()) // 30 != step):
                bad.append((n, expect, got, str(said)[:100]))
    with cf.ThreadPoolExecutor(max_workers=200) as ex:
        t0 = time.time()
        i = 0
        while time.time() - t0 < seconds:
            due = t0 + i / float(rate)
            w = due - time.time()
            if w > 0:
                time.sleep(w)
            i += 1
            want = rnd.random() < 0.7
            n = 'user%04d' % (rnd.randrange(N_TOK * 3 // 4) if want else rnd.randrange(N_TOK * 3 // 4, N_TOK))
            step = int(time.time()) // 30
            with ULOCK:
                fresh = (n, step) not in USED
                if want and fresh:
                    USED.add((n, step))
            if want and not fresh:
                continue
            code = code_of(KEYS[n], step) if want else '%06d' % rnd.randrange(1000000)
            if not want and code == code_of(KEYS[n], step):
                continue
            ex.submit(one, n, code, 'accept' if want else 'reject', step)
    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))] if lat else -1
    print('%-34s %6d req (%5.0f/s)  p50 %6.1f  p95 %6.1f  p99 %6.1f  max %7.1f ms  %s' % (
        name, len(lat), len(lat) / seconds, q(.5), q(.95), q(.99), lat[-1] if lat else -1, dict(res)), flush=True)
    return lat, res, bad


def races_out(bad):
    """Two asking with the same code at once: exactly one let in, whichever came
    first - a pair (one let in that the test thought second, one refused that it
    thought first) is right; anything else is not."""
    out = []
    for b in bad:
        if b[1] == 'reject' and b[2] == 'accept' and any(x[0] == b[0] and x[1] == 'accept' and x[2] == 'reject' for x in bad):
            continue
        if b[1] == 'accept' and b[2] == 'reject' and any(x[0] == b[0] and x[1] == 'reject' and x[2] == 'accept' for x in bad):
            continue
        out.append(b)
    return out


if os.environ.get('PGLOG'):
    # One accepted and one refused, and what the database was asked for each.
    time.sleep(3)
    for n, right in (('user0001', True), ('user0002', False)):
        mark = time.time()
        open(D + '/pg/log', 'a').write('=== %s %s\n' % (n, right))
        st_ = int(time.time()) // 30
        print(n, otp.radius_ask('127.0.0.1', RAD, SECRET, n, code_of(KEYS[n], st_) if right else '000000', timeout=5, tries=1)[0])
        time.sleep(1.5)
    os.system("grep -n 'statement\\|===' %s/pg/log | tail -60" % D)
    sys.exit(0)
TH = THREADS
THREADS = 1
latS, resS, badS = phase('one client at a time', 10)
ok('one client: p99 under 20 ms', latS and latS[int(len(latS) * .99)] < 20, latS[int(len(latS) * .99)] if latS else None)
THREADS = TH
if os.environ.get('SPY'):
    spy = subprocess.Popen(['py-spy', 'record', '-p', str(d.pid), '-d', str(int(PHASE_S)), '-f', 'raw', '-o',
                            os.environ['SPY'], '-t'], stdout=subprocess.DEVNULL, stderr=open(D + '/spy.err', 'w'))
lat0, res0, bad0 = phase('alone', PHASE_S)
ok('alone: no request unanswered', not res0.get('timeout'), res0)
bad0 = races_out(bad0)
ok('alone: every answer right', not bad0, bad0[:5])
ok('alone, at its fullest (%d at once): p99 under %d ms' % (THREADS, 100 * SLOW), lat0 and lat0[int(len(lat0) * .99)] < 100 * SLOW, lat0[int(len(lat0) * .99)] if lat0 else None)
for rate, most in ((50, 10 * SLOW), (150, 15 * SLOW), (300, 40 * SLOW)):
    la, re_, ba = paced('alone, %d a second' % rate, rate, PHASE_S / 2)
    ok('alone, %d a second: all answered and right, p99 under %d ms' % (rate, most), not re_.get('timeout') and not ba and
       la and la[int(len(la) * .99)] < most, (la[int(len(la) * .99)] if la else None, ba[:3]))

# ---- everything else at once -----------------------------------------------------------
STORM = {'stop': False}
done = collections.Counter()


def loop(name, fn, pause):
    def go():
        while not STORM['stop']:
            try:
                fn()
                done[name] += 1
            except Exception as e:                      # noqa: BLE001
                done[name + ' error'] += 1
                done[name + ' said'] = str(e)[:80]
            time.sleep(pause)
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t


def rotate():
    for f in os.listdir(D):
        if f.endswith('.log'):
            os.rename(os.path.join(D, f), os.path.join(D, f + '.%d' % int(time.time() * 1000)))
    d.send_signal(signal.SIGHUP)


def backup():
    subprocess.run([sys.executable, V + '/otp.py', '--backup'], env=env, capture_output=True, timeout=300)


def save():
    call('/api/settings', {'settings': {'radius_reject_delay_ms': random.choice([0, 1])}}, S)


tasks = [loop('dashboard', lambda: call('/api/dashboard?hours=720', None, S), 0.05),
         loop('log', lambda: call('/api/log?limit=200', None, S), 0.05),
         loop('events', lambda: call('/api/events?limit=200', None, S), 0.1),
         loop('metrics', lambda: call('/api/metrics', extra={'X-Otp-Metrics': MT}), 0.2),
         loop('rotate+HUP', rotate, 3.0),
         loop('backup', backup, 1.0),
         loop('save settings', save, 2.0)]
lat1, res1, bad1 = phase('with everything else at once', PHASE_S * 2)
for rate, most in ((50, 15 * SLOW), (150, 30 * SLOW)):
    la, re_, ba = paced('everything else, %d a second' % rate, rate, PHASE_S / 2)
    ok('everything else, %d a second: all answered and right, p99 under %d ms' % (rate, most), not re_.get('timeout') and not ba and
       la and la[int(len(la) * .99)] < most, (la[int(len(la) * .99)] if la else None, ba[:3]))
STORM['stop'] = True
time.sleep(2)
print('    background done: %s' % dict(done), flush=True)
ok('storm: no request unanswered', not res1.get('timeout'), res1)
bad1 = races_out(bad1)
ok('storm: every answer right', not bad1, bad1[:5])
p99 = lat1[int(len(lat1) * .99)] if lat1 else 1e9
ok('storm, at its fullest: p99 under %d ms (%.1f)' % (150 * SLOW, p99), p99 < 150 * SLOW)
ok('storm: the background did its work', done['dashboard'] > 5 and done['backup'] > 0 and done['rotate+HUP'] > 3, dict(done))
ok('the daemon is still running', d.poll() is None)
# The next line after the last rotation goes into a new otp.log (looked at every 10 s);
# logrotate itself makes the new file (create), this test does not.
time.sleep(11)
call('/api/settings', {'settings': {'radius_reject_delay_ms': 0}}, S)
time.sleep(1)
ok('its log goes on after the rotations', os.path.exists(D + '/otp.log') and os.path.getsize(D + '/otp.log') > 0)
print('ALL %d / %d' % (sum(R), len(R)))
