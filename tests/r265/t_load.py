#!/usr/bin/env python3
# t_load.py VERSION [--quick] [--keep] [--phases R,M,H,B,S]
#
# The LIVE install under load, over RADIUS and over HTTP/S through nginx, as root.
#   R  RADIUS ramp, password+TOTP (realm in password_otp mode, a directory behind it) and the
#      code alone (otp mode): 50, 100, 200, 400 (600, 800 while it keeps up) requests a second,
#      every one a right code not used before -> the knee.
#   M  RADIUS mixed at about half the knee: 20 % wrong codes and 10 % replayed codes among the
#      right ones, challenge flows (password, then State + code), an accounting flood
#      (Start/Interim/Stop) and retransmissions of the very same packet, all at once.
#   H  HTTP/S: 20, 50, 100 clients, each from an address of its own (10.255.65.x put on lo for
#      the test; nginx lets 10/8 in and keys its limits by address; the config trusts no
#      X-Forwarded-For): portal page loads, portal sign-ins with a wrong password, admin pages
#      signed in once and then polling status, dashboard, events, tokens, the log, /api/load,
#      and the static assets.
#   B  Both at once: RADIUS at ~70 % of the knee while 100 HTTP/S clients hammer the pages.
#   S  Soak: 10 minutes (--quick: 2) of moderate mixed load; memory, threads, FDs of the daemon,
#      php-fpm and nginx, and the rows the database gains per request.
# PASS/FAIL on: no wrong answer, no code let in twice, no unanswered request below the knee,
# RADIUS p99 < 50 ms at the moderate level (alone, mixed, and with the pages hammered), no 5xx
# except documented limits, no unbounded growth. Everything it made is named zzr265* / zz-r265-*
# and removed at the end (--keep leaves it).
import os, sys, json, time, socket, struct, hashlib, hmac, base64, random, threading, subprocess
import gzip, selectors, heapq, collections, ssl, http.client, multiprocessing as mp, signal, re, traceback

VER = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else '1.0.265'
QUICK = '--quick' in sys.argv
KEEP = '--keep' in sys.argv
PHASES = 'RMHBS'
if '--phases' in sys.argv:
    PHASES = sys.argv[sys.argv.index('--phases') + 1].upper().replace(',', '')
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = HERE + '/out'
os.makedirs(OUTDIR, exist_ok=True)
SECRET = open(HERE + '/.nas_secret').read().strip().encode()
ADMIN_PW = open('/home/claude/run/adminpw').read().strip()
MOCKDIR = '/home/claude/build/out/otp-%s' % VER
PY_OTP = '/usr/local/lib/otp/python'
LDAP_PORT = 3901
N_LDAP = 16000                      # load people in the mock directory
N_BAD = 1000                        # the last of them take the wrong codes
N_CH = 2000                         # tokens of the challenge realm
NAS_IPS = ['127.0.0.%d' % i for i in range(16, 32)]       # the client zz-r265-nas: 127.0.0.16/28
HTTP_NET = '10.255.65.'
HTTP_IPS = [HTTP_NET + str(i) for i in range(1, 201)]
RAD_HOST, AUTH_PORT, ACCT_PORT = '127.0.0.1', 1812, 1813
TIMEOUT = 5.0                       # what a VPN gateway waits, about
LEVEL_S = 20 if QUICK else 60
LEVELS = [50, 100, 200, 300, 400, 600, 800]
MIX_S = 30 if QUICK else 90
HTTP_S = 20 if QUICK else 45
BOTH_S = 30 if QUICK else 90
SOAK_S = 120 if QUICK else 600
P99_MODERATE_MS = 50.0
REALM = {'otp': 'r265otp.test', 'pw': 'r265pw.test', 'ch': 'r265ch.test'}
LOG = open(OUTDIR + '/t_load-%s.log' % time.strftime('%Y%m%d-%H%M%S'), 'w')


def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + '\n')
    LOG.flush()


def sh(cmd, inp=None, env=None, timeout=600):
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True, env=env, timeout=timeout,
                       shell=isinstance(cmd, str))
    return r.returncode, r.stdout, r.stderr


# ==== TOTP and RADIUS packets ==================================================================
def totp(key, step):
    h = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    o = h[-1] & 15
    return '%06d' % ((struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 1000000)


def b32(sec):
    s = sec.replace(' ', '').upper()
    return base64.b32decode(s + '=' * (-len(s) % 8))


def attr(t, v):
    if isinstance(v, str):
        v = v.encode()
    return bytes([t, len(v) + 2]) + v


def pap(pw, secret, auth):
    pw = pw.encode()
    pw += b'\0' * (-len(pw) % 16 or (16 if not pw else 0))
    out, last = b'', auth
    for i in range(0, len(pw), 16):
        b = hashlib.md5(secret + last).digest()
        c = bytes(x ^ y for x, y in zip(pw[i:i + 16], b))
        out += c
        last = c
    return out


def access_request(ident, user, password, nas_ip, state=None):
    auth = os.urandom(16)
    a = attr(1, user) + attr(2, pap(password, SECRET, auth)) + attr(4, socket.inet_aton(nas_ip)) + \
        attr(5, struct.pack('>I', ident)) + attr(61, struct.pack('>I', 5)) + \
        attr(31, '192.0.2.%d' % random.randint(1, 254))
    if state:
        a += attr(24, state)
    a += bytes([80, 18]) + b'\0' * 16
    hdr = bytes([1, ident]) + struct.pack('>H', 20 + len(a)) + auth
    ma = hmac.new(SECRET, hdr + a, hashlib.md5).digest()
    return hdr + a[:-16] + ma, auth


def acct_request(ident, user, status, sid, nas_ip, secs):
    a = attr(1, user) + attr(40, struct.pack('>I', status)) + attr(44, sid) + \
        attr(4, socket.inet_aton(nas_ip)) + attr(8, socket.inet_aton('10.%d.%d.%d' % (
            random.randint(0, 255), random.randint(0, 255), random.randint(1, 254)))) + \
        attr(31, '192.0.2.%d' % random.randint(1, 254))
    if status != 1:
        a += attr(46, struct.pack('>I', secs)) + attr(42, struct.pack('>I', secs * 1000)) + \
            attr(43, struct.pack('>I', secs * 3000))
    L = 20 + len(a)
    auth = hashlib.md5(bytes([4, ident]) + struct.pack('>H', L) + b'\0' * 16 + a + SECRET).digest()
    return bytes([4, ident]) + struct.pack('>H', L) + auth + a, auth


def reply_ok(data, req_auth):
    if len(data) < 20:
        return False
    L = struct.unpack('>H', data[2:4])[0]
    return hashlib.md5(data[:4] + req_auth + data[20:L] + SECRET).digest() == data[4:20]


def reply_attr(data, t):
    at, L = 20, struct.unpack('>H', data[2:4])[0]
    while at + 2 <= L:
        tt, ll = data[at], data[at + 1]
        if ll < 2:
            break
        if tt == t:
            return data[at + 2:at + ll]
        at += ll
    return None


# ==== the RADIUS load generator: one process per stream ========================================
class Rad(object):
    """Many UDP sockets (a NAS address each), one reader; requests matched by socket and
    ident, latency from the send to the first answer."""

    def __init__(self, nsock=16, port=AUTH_PORT):
        self.port = port
        self.socks, self.free = [], []
        self.sel = selectors.DefaultSelector()
        for i in range(nsock):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
            s.bind((NAS_IPS[i % len(NAS_IPS)], 0))
            s.setblocking(False)
            self.socks.append(s)
            self.free.append(collections.deque(random.sample(range(256), 256)))
            self.sel.register(s, selectors.EVENT_READ, i)
        self.pending = {}
        self.lock = threading.Lock()
        self.rr = 0
        self.timers = []
        self.stop = False
        self.saturated = 0
        self.bad_auth = 0
        self.stray = 0
        threading.Thread(target=self._read, daemon=True).start()

    def send(self, build, rec, want=1):
        """build(ident, nas_ip) -> (packet, req_auth). rec gets t0, then code/t1/replies."""
        with self.lock:
            for _ in range(len(self.socks)):
                i = self.rr % len(self.socks)
                self.rr += 1
                if self.free[i]:
                    ident = self.free[i].popleft()
                    break
            else:
                self.saturated += 1
                return False
            pkt, auth = build(ident, NAS_IPS[i % len(NAS_IPS)])
            rec.update(si=i, ident=ident, auth=auth, pkt=pkt, want=want, replies=[], t0=time.time())
            self.pending[(i, ident)] = rec
        try:
            self.socks[i].sendto(pkt, (RAD_HOST, self.port))
        except OSError as e:
            rec['err'] = str(e)
        return True

    def resend(self, rec):
        try:
            self.socks[rec['si']].sendto(rec['pkt'], (RAD_HOST, self.port))
        except OSError:
            pass

    def later(self, delay, fn):
        with self.lock:
            heapq.heappush(self.timers, (time.time() + delay, id(fn), fn))

    def _read(self):
        while not self.stop:
            for key, _ in self.sel.select(0.05):
                s = key.fileobj
                while True:
                    try:
                        data = s.recv(4096)
                    except (BlockingIOError, OSError):
                        break
                    t1 = time.time()
                    if len(data) < 20:
                        continue
                    k = (key.data, data[1])
                    with self.lock:
                        rec = self.pending.get(k)
                        if rec is None:
                            self.stray += 1
                            continue
                        if not reply_ok(data, rec['auth']):
                            self.bad_auth += 1
                            continue
                        rec['replies'].append(data)
                        first = len(rec['replies']) == 1
                        if first:
                            rec['t1'], rec['rcode'] = t1, data[0]
                        if len(rec['replies']) >= rec['want']:
                            self.pending.pop(k, None)
                            self.free[key.data].append(data[1])
                    cb = rec.get('cb')
                    if cb and first:
                        try:
                            cb(rec, data)
                        except Exception:              # noqa: BLE001
                            traceback.print_exc()
            self.tick()

    def tick(self):
        now = time.time()
        due = []
        with self.lock:
            while self.timers and self.timers[0][0] <= now:
                due.append(heapq.heappop(self.timers)[2])
            gone = [k for k, r in self.pending.items() if now - r['t0'] > TIMEOUT]
            for k in gone:
                r = self.pending.pop(k)
                if not r['replies']:
                    r['timeout'] = True
                self.free[k[0]].append(k[1])
        for fn in due:
            try:
                fn()
            except Exception:                           # noqa: BLE001
                traceback.print_exc()
        return gone


def pct(v, p):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


def stream_main(cfg, conn):
    """One stream of requests, paced; its records summed up and sent back."""
    try:
        random.seed(os.getpid() ^ int(time.time() * 1000))
        kind = cfg['kind']
        rad = Rad(nsock=cfg.get('nsock', 16), port=ACCT_PORT if kind == 'acct' else AUTH_PORT)
        keys = {n: b32(s) for n, s in cfg.get('keys', {}).items()}
        good, bad = list(cfg.get('good', [])), list(cfg.get('bad', []))
        random.shuffle(good)
        last = dict(cfg.get('last', {}))          # token -> the last step this test used
        cur = [0]
        lat = collections.defaultdict(list)
        cnt = collections.Counter()
        wrong, accepted, fresh_rej = [], [], []
        recent_ok = collections.deque(maxlen=2000)
        recs = []
        realm = cfg.get('realm', 'otp')
        lk = threading.Lock()

        def user_of(tok):
            return tok if realm == 'otp' else tok      # the token name is what the user types

        def pw_of(tok):
            i = int(tok[7:12])
            return 'Pw-r265-%05d' % i

        def alloc():
            st = int(time.time()) // 30
            n = len(good)
            for _ in range(n):
                t = good[cur[0] % n]
                cur[0] += 1
                if last.get(t, -1) < st:
                    last[t] = st
                    return t, st
            cnt['pool_short'] += 1
            return None, st

        def one_auth(what):
            if what == 'replay':
                with lk:
                    if not recent_ok:
                        what = 'fresh'
                    else:
                        tok, code, pw = random.choice(list(recent_ok))
            if what == 'fresh':
                tok, st = alloc()
                if tok is None:
                    return
                code = totp(keys[tok], st)
                pw = (pw_of(tok) + code) if realm == 'pw' else code
            elif what == 'wrong':
                tok = random.choice(bad)
                st = int(time.time()) // 30
                near = {totp(keys[tok], st + d) for d in (-2, -1, 0, 1, 2)}
                while True:
                    code = '%06d' % random.randrange(1000000)
                    if code not in near:
                        break
                pw = (pw_of(tok) + code) if realm == 'pw' else code
            rec = {'what': what, 'tok': tok, 'code': code}

            def done(rec, data):
                with lk:
                    if data[0] == 2 and rec['what'] == 'fresh':
                        recent_ok.append((rec['tok'], rec['code'], pw))
            rec['cb'] = done
            if rad.send(lambda i, ip: access_request(i, user_of(tok), pw, ip), rec):
                recs.append(rec)

        def one_chal():
            tok, st = alloc()
            if tok is None:
                return
            rec = {'what': 'chal1', 'tok': tok}

            def leg2(r1, data):
                if data[0] != 11:
                    return
                state = reply_attr(data, 24)
                code = totp(keys[tok], int(time.time()) // 30)
                r2 = {'what': 'chal2', 'tok': tok, 'code': code}
                if rad.send(lambda i, ip: access_request(i, tok, code, ip, state), r2):
                    recs.append(r2)
            rec['cb'] = leg2
            if rad.send(lambda i, ip: access_request(i, tok, pw_of(tok), ip), rec):
                recs.append(rec)

        sessions = collections.deque()
        sid_n = [0]

        def one_acct():
            # a session: Start, then Interim-Updates, then a Stop
            if sessions and (len(sessions) > 200 or random.random() < 0.6):
                s = sessions.popleft()
                s['n'] += 1
                status = 3 if s['n'] < 3 else 2
                if status == 3:
                    sessions.append(s)
            else:
                sid_n[0] += 1
                s = {'sid': '%x-%d-%d' % (os.getpid(), sid_n[0], int(time.time())), 'n': 0,
                     'user': 'zzr265u%05d@%s' % (random.randrange(N_LDAP), REALM['otp'])}
                status = 1
                sessions.append(s)
            rec = {'what': {1: 'start', 2: 'stop', 3: 'interim'}[status]}
            if rad.send(lambda i, ip: acct_request(i, s['user'], status, s['sid'], ip, 60 * s['n']), rec):
                recs.append(rec)

        def one_retr():
            tok, st = alloc()
            if tok is None:
                return
            code = totp(keys[tok], st)
            flavour = random.choice(['now', 'after'])
            rec = {'what': 'retr_' + flavour, 'tok': tok, 'code': code}
            if flavour == 'now':
                # the NAS's repeat right behind the first: answered once (or the same twice)
                ok = rad.send(lambda i, ip: access_request(i, tok, code, ip), rec, want=2)
                if ok:
                    rad.resend(rec)
            else:
                # the repeat after the answer was lost on the way: the same answer again
                def again(r, data):
                    rad.later(0.2, lambda: rad.resend(r))
                rec['cb'] = again
                ok = rad.send(lambda i, ip: access_request(i, tok, code, ip), rec, want=2)
            if ok:
                recs.append(rec)

        mix = cfg.get('mix', {'fresh': 1.0})
        kinds, weights = zip(*mix.items())
        rate, dur = float(cfg['rate']), float(cfg['duration'])
        while time.time() < cfg['start_at']:
            time.sleep(0.005)
        t0 = time.time()
        i = 0
        while True:
            now = time.time()
            if now - t0 >= dur:
                break
            due = t0 + i / rate
            if due > now:
                time.sleep(min(due - now, 0.05))
                continue
            i += 1
            if kind == 'auth':
                one_auth(random.choices(kinds, weights)[0])
            elif kind == 'chal':
                one_chal()
            elif kind == 'acct':
                one_acct()
            elif kind == 'retr':
                one_retr()
        sent_s = time.time() - t0
        # the last answers, and the chal2 / repeats they start
        end = time.time() + TIMEOUT + 1.0
        while time.time() < end:
            with rad.lock:
                left = len(rad.pending) + len(rad.timers)
            if not left:
                break
            time.sleep(0.05)
        time.sleep(0.1)
        rad.tick()
        rad.stop = True
        # ---- sum up -----------------------------------------------------------------------
        tl = []
        oks = collections.Counter()
        for r in recs:
            w = r['what']
            cnt['sent'] += 1
            cnt['sent_' + w] += 1
            if r.get('timeout') or 'rcode' not in r and not r['replies']:
                cnt['timeout'] += 1
                cnt['timeout_' + w] += 1
                continue
            code = r['replies'][0][0] if r['replies'] else None
            ms = (r['t1'] - r['t0']) * 1000
            lat[w].append(ms)
            lat['all'].append(ms)
            tl.append((round(r['t0'], 2), round(ms, 1)))
            got = {2: 'accept', 3: 'reject', 11: 'challenge', 5: 'acct-ok'}.get(code, 'code%s' % code)
            cnt[w + ':' + got] += 1
            want = {'fresh': 'accept', 'wrong': 'reject', 'replay': 'reject', 'chal1': 'challenge',
                    'chal2': 'accept', 'start': 'acct-ok', 'interim': 'acct-ok', 'stop': 'acct-ok',
                    'retr_now': 'accept', 'retr_after': 'accept'}[w]
            if w.startswith('retr'):
                if len(set(r['replies'])) > 1:
                    cnt['retr_different_answer'] += 1
                    wrong.append((w, r['tok'], 'answers differ: %s' % [x[0] for x in r['replies']]))
                cnt['retr_replies_%d' % len(r['replies'])] += 1
            if got == 'accept' and 'code' in r and w != 'retr_now' and w != 'retr_after':
                oks[(r['tok'], r['code'])] += 1
                accepted.append((r['tok'], r['code'], round(r['t0'], 3), w))
            elif got == 'accept' and w.startswith('retr'):
                oks[(r['tok'], r['code'])] += 1
                accepted.append((r['tok'], r['code'], round(r['t0'], 3), w))
            if got != want:
                if want == 'accept' and got == 'reject':
                    fresh_rej.append((r['tok'], r['t0'], w))
                else:
                    wrong.append((w, r.get('tok'), 'expected %s, got %s' % (want, got)))
        cnt['double_accept'] = sum(1 for v in oks.values() if v > 1)
        res = {'kind': kind, 'realm': realm, 'rate': rate, 'sent_s': sent_s, 'counts': dict(cnt),
               'lat': {k: v for k, v in lat.items()}, 'wrong': wrong[:50], 'n_wrong': len(wrong),
               'accepted': accepted, 'fresh_rej': fresh_rej, 'tl': tl, 'last': last,
               'client': {'saturated': rad.saturated, 'bad_auth': rad.bad_auth, 'stray': rad.stray}}
        conn.send(res)
    except Exception:                                   # noqa: BLE001
        conn.send({'error': traceback.format_exc()})
    conn.close()


# ==== the HTTP/S load generator ================================================================
SSLCTX = ssl.create_default_context()
SSLCTX.check_hostname = False
SSLCTX.verify_mode = ssl.CERT_NONE

ADMIN_APIS = ['status', 'dashboard&hours=24', 'activity&hours=24&limit=50&offset=%d',
              'events&limit=50&offset=%d', 'tokens&limit=50&offset=%d&sort=last_used&desc=1', 'load',
              'status']
STATIC = ['/assets/otp.css', '/assets/core.js', '/assets/portal.js', '/assets/admin.js',
          '/assets/i18n.js', '/assets/favicon.svg', '/assets/hload.js']


class Web(object):
    def __init__(self, ip):
        self.ip = ip
        self.c = None
        self.cookie = ''

    def conn(self):
        if self.c is None:
            self.c = http.client.HTTPSConnection('127.0.0.1', 443, timeout=30, context=SSLCTX,
                                                 source_address=(self.ip, 0))
        return self.c

    def req(self, method, path, body=None):
        h = {'Host': 'otp.example.local', 'Accept-Encoding': 'gzip'}
        if self.cookie:
            h['Cookie'] = self.cookie
        if body is not None:
            body = json.dumps(body)
            h['Content-Type'] = 'application/json'
        for attempt in (0, 1):
            try:
                c = self.conn()
                c.request(method, path, body=body, headers=h)
                r = c.getresponse()
                data = r.read()
                for k, v in r.getheaders():
                    if k.lower() == 'set-cookie':
                        part = v.split(';', 1)[0]
                        name = part.split('=', 1)[0]
                        jar = dict(x.split('=', 1) for x in self.cookie.split('; ') if '=' in x)
                        jar[name] = part.split('=', 1)[1]
                        self.cookie = '; '.join('%s=%s' % kv for kv in jar.items())
                if r.getheader('connection', '').lower() == 'close':
                    self.close()
                return r.status, data
            except (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError,
                    http.client.CannotSendRequest, http.client.ResponseNotReady):
                self.close()
                if attempt:
                    raise
        return 0, b''

    def close(self):
        try:
            if self.c:
                self.c.close()
        except Exception:                               # noqa: BLE001
            pass
        self.c = None


PACE = {'how': 'flood'}


def http_client(role, ip, stop_at, out, lk, n):
    w = Web(ip)
    lat = collections.defaultdict(list)
    st = collections.Counter()
    try:
        if role == 'admin':
            t = time.time()
            s, d = w.req('POST', '/admin/?api=login', {'name': 'admin', 'password': ADMIN_PW})
            lat['admin:login'].append((time.time() - t) * 1000)
            st['admin:login:%d' % s] += 1
            if s != 200:
                # one more try after the login limit's minute, at most
                time.sleep(3.2)
                s, d = w.req('POST', '/admin/?api=login', {'name': 'admin', 'password': ADMIN_PW})
                st['admin:login-again:%d' % s] += 1
        k = 0
        while time.time() < stop_at:
            k += 1
            if role == 'admin':
                a = ADMIN_APIS[k % len(ADMIN_APIS)]
                if '%d' in a:
                    a = a % (random.randrange(20) * 50)
                path, key = '/admin/?api=' + a, 'admin:' + a.split('&')[0]
                method, body = 'GET', None
            elif role == 'portal':
                path, key, method, body = '/', 'portal:page', 'GET', None
            elif role == 'signin':
                path, key, method = '/?api=login', 'portal:signin', 'POST'
                body = {'name': 'zzr265nobody%d@%s' % (n, REALM['pw']), 'password': 'wrong-%d' % k, 'lang': ''}
            else:
                path, key, method, body = random.choice(STATIC), 'static', 'GET', None
            t = time.time()
            try:
                s, d = w.req(method, path, body)
            except Exception as e:                      # noqa: BLE001
                s, d = 0, str(e).encode()
                w.close()
            ms = (time.time() - t) * 1000
            st['%s:%d' % (key, s)] += 1
            if s == 200:
                lat[key].append(ms)
            elif s >= 500 or s == 0:
                st['err_said:%s:%d:%s' % (key, s, d[:80].decode('utf-8', 'replace'))] += 1
            # a page in a browser asks a few times a second at most; a sign-in is typed
            if PACE['how'] == 'real':
                # as people and browsers do (1.0.265): an admin tab asks a few things every
                # 5 s, a person on the enrolment page reads before the next click
                time.sleep({'admin': 1.0, 'portal': 4.0, 'signin': 8.0, 'static': 0.3}[role] * (0.5 + random.random()))
            else:
                time.sleep({'admin': 0.02, 'portal': 0.05, 'signin': 0.5, 'static': 0.01}[role] * random.random() * 2)
        if role == 'admin':
            try:
                w.req('POST', '/admin/?api=logout', {})
            except Exception:                           # noqa: BLE001
                pass
    except Exception as e:                              # noqa: BLE001
        st['client_broke:%s' % str(e)[:60]] += 1
    w.close()
    with lk:
        for k2, v in lat.items():
            out['lat'].setdefault(k2, []).extend(v)
        for k2, v in st.items():
            out['st'][k2] = out['st'].get(k2, 0) + v


def http_main(cfg, conn):
    try:
        out = {'lat': {}, 'st': {}}
        lk = threading.Lock()
        while time.time() < cfg['start_at']:
            time.sleep(0.005)
        stop_at = time.time() + cfg['duration']
        th = [threading.Thread(target=http_client, args=(role, ip, stop_at, out, lk, n))
              for role, ip, n in cfg['clients']]
        for t in th:
            t.start()
        for t in th:
            t.join()
        conn.send(out)
    except Exception:                                   # noqa: BLE001
        conn.send({'error': traceback.format_exc()})
    conn.close()


def http_roles(nclients):
    """Who the clients are: 40 % administrators on the pages, 25 % the portal's page, 15 %
    portal sign-ins with a wrong password, 20 % the static files. An address each."""
    out = []
    for i in range(nclients):
        f = i / float(nclients)
        if PACE['how'] == 'real':
            # a few administrators and many people enrolling (1.0.265)
            role = 'admin' if f < 0.05 else 'portal' if f < 0.65 else 'signin' if f < 0.85 else 'static'
        else:
            role = 'admin' if f < 0.40 else 'portal' if f < 0.65 else 'signin' if f < 0.80 else 'static'
        out.append((role, HTTP_IPS[i], i))
    return out


# ==== the machine: processes to watch ==========================================================
def pids():
    out = {'daemon': None, 'fpm': [], 'nginx': []}
    for p in os.listdir('/proc'):
        if not p.isdigit():
            continue
        try:
            cmd = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\0', b' ').decode().strip()
        except OSError:
            continue
        if cmd.startswith('/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'):
            out['daemon'] = int(p)
        elif cmd.startswith('php-fpm: pool otp'):
            out['fpm'].append(int(p))
        elif cmd.startswith('nginx: worker'):
            out['nginx'].append(int(p))
    return out


def proc_of(pid):
    try:
        st = open('/proc/%d/status' % pid).read()
        rss = int(re.search(r'VmRSS:\s+(\d+)', st).group(1))
        th = int(re.search(r'Threads:\s+(\d+)', st).group(1))
        fds = len(os.listdir('/proc/%d/fd' % pid))
        f = open('/proc/%d/stat' % pid).read().rsplit(')', 1)[1].split()
        cpu = int(f[11]) + int(f[12])
        return {'rss': rss, 'th': th, 'fds': fds, 'cpu': cpu}
    except (OSError, AttributeError, ValueError):
        return None


def sys_cpu():
    v = [int(x) for x in open('/proc/stat').readline().split()[1:9]]
    return sum(v), v[3] + v[4]


HZ = os.sysconf('SC_CLK_TCK')


class Sampler(threading.Thread):
    def __init__(self, every=1.0):
        threading.Thread.__init__(self, daemon=True)
        self.every = every
        self.rows = []
        self.stop_ev = threading.Event()

    def run(self):
        last = None
        while not self.stop_ev.is_set():
            p = pids()
            t = time.time()
            d = proc_of(p['daemon']) if p['daemon'] else None
            fpm = [x for x in (proc_of(q) for q in p['fpm']) if x]
            ngx = [x for x in (proc_of(q) for q in p['nginx']) if x]
            allc, idle = sys_cpu()
            row = {'t': t, 'd': d, 'fpm_n': len(fpm), 'fpm_rss': sum(x['rss'] for x in fpm),
                   'fpm_cpu': sum(x['cpu'] for x in fpm),
                   'ngx_rss': sum(x['rss'] for x in ngx), 'ngx_fds': sum(x['fds'] for x in ngx),
                   'ngx_cpu': sum(x['cpu'] for x in ngx), 'sys': (allc, idle)}
            if last and d and last['d']:
                dt = t - last['t']
                row['d_cpu_pct'] = (d['cpu'] - last['d']['cpu']) / HZ / dt * 100
                da, di = allc - last['sys'][0], idle - last['sys'][1]
                row['sys_busy_pct'] = 100.0 * (da - di) / da if da else 0
            self.rows.append(row)
            last = row
            self.stop_ev.wait(self.every)

    def summary(self):
        r = [x for x in self.rows if x['d']]
        if not r:
            return {}
        cp = [x['d_cpu_pct'] for x in r if 'd_cpu_pct' in x]
        sb = [x['sys_busy_pct'] for x in r if 'sys_busy_pct' in x]
        return {'d_rss0': r[0]['d']['rss'], 'd_rss1': r[-1]['d']['rss'], 'd_rss_max': max(x['d']['rss'] for x in r),
                'd_th0': r[0]['d']['th'], 'd_th1': r[-1]['d']['th'], 'd_th_max': max(x['d']['th'] for x in r),
                'd_fds0': r[0]['d']['fds'], 'd_fds1': r[-1]['d']['fds'], 'd_fds_max': max(x['d']['fds'] for x in r),
                'd_cpu_avg': sum(cp) / len(cp) if cp else 0, 'd_cpu_max': max(cp) if cp else 0,
                'sys_busy_avg': sum(sb) / len(sb) if sb else 0,
                'fpm_n_max': max(x['fpm_n'] for x in r), 'fpm_rss_max': max(x['fpm_rss'] for x in r),
                'ngx_rss0': r[0]['ngx_rss'], 'ngx_rss1': r[-1]['ngx_rss'], 'ngx_fds_max': max(x['ngx_fds'] for x in r)}


# ==== the install: what it is, what the test adds to it =======================================
def tokhelper(*args, inp=None):
    rc, out, err = sh(['runuser', '-u', 'otp', '--', PY_OTP, HERE + '/r265tok.py'] + list(args), inp=inp)
    if rc:
        raise RuntimeError('r265tok %s: %s' % (args[0], err.strip()[-400:]))
    return json.loads(out)


def otp_cli(*args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return sh(['otp', '--no-color'] + list(args), env=e)


class Admin(object):
    """One signed-in administrator from 127.0.0.1, for the counters of the daemon."""

    def __init__(self):
        self.w = Web('127.0.0.1')
        s, _ = self.w.req('POST', '/admin/?api=login', {'name': 'admin', 'password': ADMIN_PW})
        if s != 200:
            raise RuntimeError('admin sign-in: HTTP %d' % s)

    def get(self, api):
        s, d = self.w.req('GET', '/admin/?api=' + api)
        try:
            if d[:2] == b'\x1f\x8b':
                d = gzip.decompress(d)
            return json.loads(d) if s == 200 else {'http': s}
        except ValueError:
            return {'http': s}

    def post(self, api, body):
        s, d = self.w.req('POST', '/admin/?api=' + api, body)
        try:
            return json.loads(d)
        except ValueError:
            return {'http': s}


CREATED = {'ldap_pid': None, 'ips': [], 'perf_meter': None}


def setup():
    rc, out, _ = otp_cli('--version')
    if VER not in out:
        raise SystemExit('the live install is not %s: %s' % (VER, out.strip()))
    rc, out, _ = otp_cli('--status')
    eng = re.search(r'the database: (.*)', out)
    db_engine = eng.group(1).strip() if eng else '?'
    if not pids()['daemon']:
        raise SystemExit('the daemon is not running')
    # the mock directory with the load people
    if not sh("pgrep -f 'r265ldap[.]py %d'" % LDAP_PORT)[1].strip():
        p = subprocess.Popen(['python3', HERE + '/r265ldap.py', str(LDAP_PORT), str(N_LDAP), MOCKDIR],
                             stdout=open(OUTDIR + '/ldap.out', 'w'), stderr=subprocess.STDOUT,
                             start_new_session=True)
        CREATED['ldap_pid'] = p.pid
        for _ in range(60):
            time.sleep(0.5)
            try:
                socket.create_connection(('127.0.0.1', LDAP_PORT), 1).close()
                break
            except OSError:
                pass
    # the directory, the realms, the client (the CLI, as an administrator would)
    _, dirs, _ = otp_cli('--directories')
    if 'zz-r265-dir' not in dirs:
        rc, o, e = otp_cli('--add-directory', 'zz-r265-dir', '--hosts', '127.0.0.1', '--port', str(LDAP_PORT),
                           '--tls', 'none', '--base', 'DC=corpnet,DC=loc', '--bind-dn', 'otp@corpnet.loc',
                           '--bind-pw', '-', env={'OTP_BIND_PW': 'the-otp-service-password'})
        assert rc == 0, o + e
    _, realms, _ = otp_cli('--realms')
    for name, suf, mode, dr in (('zz-r265-otp', REALM['otp'], 'otp', None),
                                ('zz-r265-pw', REALM['pw'], 'password_otp', 'zz-r265-dir'),
                                ('zz-r265-ch', REALM['ch'], 'challenge', 'zz-r265-dir')):
        if name in realms:
            continue
        a = ['--add-realm', name, '--suffix', suf, '--mode', mode]
        a += ['--directory', dr, '--lookup', 'sam'] if dr else ['--lookup', 'none']
        rc, o, e = otp_cli(*a)
        assert rc == 0, o + e
    _, cl, _ = otp_cli('--clients')
    if 'zz-r265-nas' not in cl:
        rc, o, e = otp_cli('--add-client', 'zz-r265-nas', '--address', '127.0.0.16/28', '--secret', '-',
                           env={'OTP_SECRET': SECRET.decode()})
        assert rc == 0, o + e
    # addresses for the HTTP clients, on lo, taken away at the end
    have = sh('ip -4 -o addr show dev lo')[1]
    for ip in HTTP_IPS:
        if ' %s/' % ip not in have:
            sh(['ip', 'addr', 'add', ip + '/32', 'dev', 'lo'])
            CREATED['ips'].append(ip)
    adm = Admin()
    pm = otp_cli('--get', 'perf_meter')[1].strip().lower()
    CREATED['perf_meter'] = pm in ('1', 'true', 'on', 'yes')
    otp_cli('--set', 'perf_meter=1')
    # the tokens: the old ones of this test away first
    tokhelper('drop')
    keys = {}
    t = time.time()
    for suf, n in ((REALM['otp'], N_LDAP), (REALM['pw'], N_LDAP), (REALM['ch'], N_CH)):
        for first in range(0, n, 4000):
            keys.update(tokhelper('make', suf, str(first), str(min(4000, n - first))))
    say('setup: %d tokens in %.1f s; the database: %s' % (len(keys), time.time() - t, db_engine))
    for _ in range(30):             # the performance meter on, for /api/load as the pages poll it
        if adm.get('load').get('http') is None:
            break
        time.sleep(1)
    return keys, db_engine, adm


def cleanup():
    say('cleanup ...')
    if CREATED['perf_meter'] is not None:
        otp_cli('--set', 'perf_meter=%s' % (1 if CREATED['perf_meter'] else 0))
    if KEEP:
        say('  --keep: the zzr265* tokens, zz-r265-* realms/client/directory and the lo addresses stay')
    else:
        try:
            say('  removed:', tokhelper('drop'))
        except Exception as e:                          # noqa: BLE001
            say('  token removal failed:', e)
        for a in (('--del-realm', 'zz-r265-otp'), ('--del-realm', 'zz-r265-pw'), ('--del-realm', 'zz-r265-ch'),
                  ('--del-client', 'zz-r265-nas'), ('--del-directory', 'zz-r265-dir')):
            rc, o, e = otp_cli(*(a + ('--yes',)))
            if rc:
                rc, o, e = otp_cli(*a)
            say('  %s %s: %s' % (a[0], a[1], 'ok' if rc == 0 else (o + e).strip()[-120:]))
        have = sh('ip -4 -o addr show dev lo')[1]
        for ip in HTTP_IPS:                 # this test's own 10.255.65.x, whoever put them there
            if ' %s/' % ip in have:
                sh(['ip', 'addr', 'del', ip + '/32', 'dev', 'lo'])
        if CREATED['ldap_pid']:
            try:
                os.kill(CREATED['ldap_pid'], signal.SIGTERM)
            except OSError:
                pass


# ==== running a phase ==========================================================================
class Book(object):
    """What each phase found, the rows of the table, and the verdicts."""

    def __init__(self):
        self.rows = []
        self.checks = []
        self.last = {}              # token -> the last step used, across phases
        self.accepted = collections.defaultdict(list)

    def check(self, what, ok, more=''):
        self.checks.append((what, bool(ok), more))
        say(('  ok   ' if ok else '  FAIL ') + what + (('   [%s]' % (more,)) if more else ''))


BOOK = Book()


def settle(adm, extra=0):
    """Between phases: the daemon's queue empty, and a breath."""
    time.sleep(extra)
    t = time.time()
    while time.time() - t < 40:
        q = (adm.get('status').get('radius') or {}).get('queued')
        if q == 0:
            break
        time.sleep(1)
    time.sleep(2)


ADM = []


def run(name, streams, http=None, duration=60, sample_every=1.0):
    if ADM:
        settle(ADM[0])
    start_at = time.time() + 1.5
    procs = []
    ctx = mp.get_context('fork')
    for s in streams:
        s = dict(s, start_at=start_at, duration=duration)
        s['last'] = {t: BOOK.last[t] for t in s.get('good', []) if t in BOOK.last}
        a, b = ctx.Pipe(False)
        p = ctx.Process(target=stream_main, args=(s, b))
        p.start()
        procs.append(('rad', s, p, a))
    if http:
        cl = http_roles(http)
        per = (len(cl) + 3) // 4
        for k in range(0, len(cl), per):
            a, b = ctx.Pipe(False)
            p = ctx.Process(target=http_main, args=({'clients': cl[k:k + per], 'start_at': start_at,
                                                     'duration': duration}, b))
            p.start()
            procs.append(('http', None, p, a))
    sam = Sampler(sample_every)
    sam.start()
    t0 = time.time()
    res = []
    for kind, s, p, a in procs:
        r = a.recv()
        p.join()
        res.append((kind, s, r))
    sam.stop_ev.set()
    sam.join()
    out = {'name': name, 'rad': [], 'http': None, 'sys': sam.summary(), 'samples': sam.rows,
           'took': time.time() - t0}
    hl = {'lat': collections.defaultdict(list), 'st': collections.Counter()}
    for kind, s, r in res:
        if 'error' in r:
            say('  a load process broke:', r['error'])
            BOOK.check('%s: the load generator itself ran' % name, False, r['error'][-200:])
            continue
        if kind == 'rad':
            BOOK.last.update(r.pop('last'))
            for k in r['accepted']:
                BOOK.accepted[(k[0], k[1])].append((name, k[2], int(k[2]) // 30, k[3]))
            out['rad'].append(r)
        else:
            for k, v in r['lat'].items():
                hl['lat'][k].extend(v)
            hl['st'].update(r['st'])
    if http:
        out['http'] = hl
    return out


def acct_check(name, o):
    for r in o['rad']:
        if r['kind'] == 'acct':
            p = pct(r['lat'].get('all'), .99)
            BOOK.check('%s: accounting p99 < %.0f ms (%s)' % (name, P99_MODERATE_MS, fmt(p)), (p or 1e9) < P99_MODERATE_MS)


def classify_rejects(r, since):
    """Fresh right codes refused: why, by the daemon's own log (the reason column)."""
    if not r['fresh_rej']:
        return collections.Counter()
    names = sorted({x[0] for x in r['fresh_rej']})[:400]
    sql = ("SELECT username, reason, ts FROM radius_log WHERE ts >= %f AND result = 'reject' AND username IN (%s)"
           % (since - 2, ','.join("'%s'" % n for n in names)))
    rows = tokhelper('sql', inp=sql)
    c = collections.Counter()
    for row in rows:
        c[(row.get('reason') or '')[:90]] += 1
    return c


def lat_line(name, r, w='all'):
    v = r['lat'].get(w, [])
    c = r['counts']
    to = c.get('timeout', 0)
    return {'phase': name, 'stream': '%s/%s' % (r['kind'], r['realm']) + ('' if w == 'all' else ':' + w),
            'offered': r['rate'], 'done': len(v) / max(1.0, r['sent_s']), 'n': len(v),
            'p50': pct(v, .5), 'p95': pct(v, .95), 'p99': pct(v, .99), 'max': max(v) if v else None,
            'timeouts': to, 'wrong': r['n_wrong'], 'fresh_rej': len(r['fresh_rej']),
            'double': c.get('double_accept', 0), 'short': c.get('pool_short', 0)}


def fmt(x, d=1):
    return '-' if x is None else ('%.*f' % (d, x) if isinstance(x, float) else str(x))


def table(rows):
    hdr = ['phase', 'stream', 'offered', 'done/s', 'n', 'p50', 'p95', 'p99', 'max', 'tmo', 'wrong', 'rej!', '2x']
    lines = ['%-22s %-24s %7s %7s %7s %7s %7s %7s %8s %5s %5s %5s %3s' % tuple(hdr)]
    for r in rows:
        lines.append('%-22s %-24s %7s %7s %7s %7s %7s %7s %8s %5s %5s %5s %3s' % (
            r['phase'][:22], r['stream'][:24], fmt(r['offered'], 0), fmt(r['done'], 0), r['n'],
            fmt(r['p50']), fmt(r['p95']), fmt(r['p99']), fmt(r['max'], 0), r['timeouts'], r['wrong'],
            r['fresh_rej'], r['double']))
    return '\n'.join(lines)


def sys_line(name, o):
    s = o['sys']
    if not s:
        return '%-22s (no samples)' % name
    return ('%-22s daemon cpu avg %5.0f%% max %5.0f%%  rss %6.1f->%6.1f MB (max %6.1f)  threads %d->%d (max %d)  '
            'fds %d->%d  | machine busy %3.0f%% | php-fpm otp children max %d (rss %.0f MB) | nginx fds max %d' % (
                name, s['d_cpu_avg'], s['d_cpu_max'], s['d_rss0'] / 1024., s['d_rss1'] / 1024., s['d_rss_max'] / 1024.,
                s['d_th0'], s['d_th1'], s['d_th_max'], s['d_fds0'], s['d_fds1'], s['sys_busy_avg'],
                s['fpm_n_max'], s['fpm_rss_max'] / 1024., s['ngx_fds_max']))


def http_report(name, o):
    h = o['http']
    st = h['st']
    out = []
    keys = sorted({k.rsplit(':', 1)[0] for k in st if not k.startswith(('err_said', 'client_broke'))})
    agg = collections.Counter()
    for k in keys:
        by = {int(c.rsplit(':', 1)[1]): v for c, v in st.items() if c.rsplit(':', 1)[0] == k and
              not c.startswith(('err_said', 'client_broke'))}
        v = h['lat'].get(k, [])
        tot = sum(by.values())
        out.append('    %-22s n=%6d  %-44s ok p50 %6s p95 %6s p99 %6s ms' % (
            k, tot, ' '.join('%d:%d' % kv for kv in sorted(by.items())), fmt(pct(v, .5)), fmt(pct(v, .95)),
            fmt(pct(v, .99))))
        for code, n in by.items():
            agg[code] += n
    errs = [(k, v) for k, v in st.items() if k.startswith(('err_said', 'client_broke'))]
    say('  HTTP %s: %s' % (name, ' '.join('%d:%d' % kv for kv in sorted(agg.items()))))
    for line in out:
        say(line)
    for k, v in sorted(errs, key=lambda kv: -kv[1])[:8]:
        say('    !! %s x%d' % (k, v))
    return agg, st


def fpm_log_lines():
    try:
        return open('/var/log/php8.3-fpm.log', errors='replace').read().splitlines()
    except OSError:
        return []


# ==== the phases ===============================================================================
def main():
    say('t_load.py %s %s - %s' % (VER, '--quick' if QUICK else 'full', time.strftime('%Y-%m-%d %H:%M:%S')))
    keys, db_engine, adm = setup()
    ADM.append(adm)
    names = lambda suf, a, b: ['zzr265u%05d@%s' % (i, suf) for i in range(a, b)]
    GOOD = {'otp': names(REALM['otp'], 0, N_LDAP - N_BAD), 'pw': names(REALM['pw'], 0, N_LDAP - N_BAD)}
    BAD = {'otp': names(REALM['otp'], N_LDAP - N_BAD, N_LDAP), 'pw': names(REALM['pw'], N_LDAP - N_BAD, N_LDAP)}
    CH = names(REALM['ch'], 0, N_CH)

    def ks(lst):
        return {n: keys[n] for n in lst}

    def auth(realm, rate, mix=None, good=None, bad=None):
        g = good if good is not None else GOOD[realm]
        b = bad if bad is not None else BAD[realm]
        return {'kind': 'auth', 'realm': realm, 'rate': rate, 'mix': mix or {'fresh': 1.0}, 'good': g,
                'bad': b, 'keys': ks(g + b)}

    fpm0 = len(fpm_log_lines())
    rows0 = tokhelper('rows')
    st0 = adm.get('status').get('radius', {}).get('counts', {})
    say('daemon at start:', proc_of(pids()['daemon']), '| radius counters', st0, '| rows', rows0)
    knee = {}
    results = {}
    try:
        # ---- R: the ramp ------------------------------------------------------------------
        if 'R' in PHASES:
            for realm in ('pw', 'otp'):
                knee[realm] = None
                for rate in LEVELS:
                    if len(GOOD[realm]) < rate * 31 and rate > 400:
                        break
                    name = 'R %s %d/s' % (realm, rate)
                    t_start = time.time()
                    o = run(name, [auth(realm, rate)], duration=LEVEL_S)
                    r = o['rad'][0]
                    line = lat_line(name, r)
                    BOOK.rows.append(line)
                    why = classify_rejects(r, t_start)
                    say(table([line]).splitlines()[1])
                    say('  ' + sys_line(name, o))
                    if why:
                        say('  refused right codes, by the daemon\'s reason:', dict(why.most_common(5)))
                    BOOK.check('%s: no wrong answer, no code let in twice' % name,
                               r['n_wrong'] == 0 and r['counts'].get('double_accept', 0) == 0, r['wrong'][:3])
                    good_level = (line['timeouts'] == 0 and line['fresh_rej'] == 0 and line['p99'] is not None
                                  and line['p99'] < 100 and line['done'] >= 0.95 * rate)
                    results[name] = o
                    if good_level:
                        knee[realm] = rate
                    else:
                        settle(adm, 12)          # the requests the gateways gave up on, worked off
                        say('  -> past the knee (timeouts %d, refused right codes %d, p99 %s ms, %.0f/s done)'
                            % (line['timeouts'], line['fresh_rej'], fmt(line['p99']), line['done']))
                        break
                    if realm == 'pw' and rate >= 400 and QUICK:
                        break
                say('KNEE %s: %s requests a second (the highest level with every request answered, every right '
                    'code let in, p99 < 100 ms)' % (realm, knee[realm]))
        k_pw = knee.get('pw') or 200
        # ---- M: mixed, at about half the knee ----------------------------------------------------
        if 'M' in PHASES:
            rate = max(25, k_pw // 2)
            name = 'M mixed %d/s' % rate
            gp, go = GOOD['pw'], GOOD['otp']
            streams = [auth('pw', rate, {'fresh': 0.7, 'wrong': 0.2, 'replay': 0.1}, good=gp[:9000]),
                       {'kind': 'chal', 'realm': 'ch', 'rate': 10, 'good': CH, 'keys': ks(CH)},
                       {'kind': 'acct', 'realm': 'acct', 'rate': 300, 'nsock': 8},
                       {'kind': 'retr', 'realm': 'otp', 'rate': 5, 'good': go[:3000], 'keys': ks(go[:3000])},
                       auth('otp', max(10, rate // 4), {'fresh': 0.8, 'wrong': 0.2}, good=go[3000:])]
            t_start = time.time()
            o = run(name, streams, duration=MIX_S)
            results[name] = o
            for r in o['rad']:
                for w in (['all'] + sorted(k for k in r['lat'] if k != 'all')):
                    BOOK.rows.append(lat_line(name, r, w))
                why = classify_rejects(r, t_start)
                if why:
                    say('  %s/%s refused right codes, by reason: %s' % (r['kind'], r['realm'], dict(why.most_common(5))))
                say('  %s/%s counts: %s' % (r['kind'], r['realm'], {k: v for k, v in sorted(r['counts'].items())
                                                                   if not k.startswith('sent_')}))
            say(table([x for x in BOOK.rows if x['phase'] == name]))
            say('  ' + sys_line(name, o))
            allr = o['rad']
            BOOK.check('%s: no wrong answer (wrong codes and replays refused, retransmissions answered alike)' % name,
                       all(r['n_wrong'] == 0 for r in allr), [r['wrong'][:2] for r in allr if r['wrong']])
            BOOK.check('%s: no code let in twice' % name, all(r['counts'].get('double_accept', 0) == 0 for r in allr))
            BOOK.check('%s: nothing unanswered (auth, challenge, accounting)' % name,
                       all(r['counts'].get('timeout', 0) == 0 for r in allr),
                       {'%s/%s' % (r['kind'], r['realm']): r['counts'].get('timeout', 0) for r in allr})
            BOOK.check('%s: every right code let in' % name, all(not r['fresh_rej'] for r in allr),
                       {'%s/%s' % (r['kind'], r['realm']): len(r['fresh_rej']) for r in allr})
            a = [r for r in allr if r['kind'] == 'auth' and r['realm'] == 'pw'][0]
            p99 = pct(a['lat']['all'], .99)
            acct_check(name, o)
            BOOK.check('%s: password+code p99 < %.0f ms with accounting flood + challenges (%.1f)'
                       % (name, P99_MODERATE_MS, p99 or -1), p99 is not None and p99 < P99_MODERATE_MS)
        # ---- H: HTTP/S alone --------------------------------------------------------------------
        http_base = {}
        if 'H' in PHASES:
            for n in (20, 50, 100):
                name = 'H http %d clients' % n
                f0 = len(fpm_log_lines())
                probe = auth('otp', 10, good=GOOD['otp'][9000:12000])
                o = run(name, [probe], http=n, duration=HTTP_S)
                results[name] = o
                agg, st = http_report(name, o)
                r = o['rad'][0]
                BOOK.rows.append(lat_line(name, r))
                say('  ' + sys_line(name, o))
                fl = fpm_log_lines()[f0:]
                maxch = [x for x in fl if 'max_children' in x]
                if maxch:
                    say('  php-fpm said: %s (x%d)' % (maxch[-1][-160:], len(maxch)))
                http_base[n] = o
                n5 = sum(v for k, v in agg.items() if k >= 500 or k == 0)
                BOOK.check('%s: no 5xx and no failed connection' % name, n5 == 0,
                           {k: v for k, v in st.items() if k.startswith(('err_said', 'client_broke'))} if n5 else '')
                BOOK.check('%s: the RADIUS probe beside it (10/s): all answered, right, p99 < %.0f ms (%s)'
                           % (name, P99_MODERATE_MS, fmt(pct(r['lat'].get('all'), .99))),
                           r['n_wrong'] == 0 and not r['counts'].get('timeout') and not r['fresh_rej'] and
                           (pct(r['lat'].get('all'), .99) or 1e9) < P99_MODERATE_MS)
        # ---- B: both at once --------------------------------------------------------------------
        if 'B' in PHASES:
            rate = max(25, int(k_pw * 0.7))
            ref = 'B ref RADIUS alone %d/s' % rate
            o = run(ref, [auth('pw', rate, {'fresh': 0.9, 'wrong': 0.1}), {'kind': 'acct', 'realm': 'acct', 'rate': 50, 'nsock': 4}],
                    duration=min(BOTH_S, 45))
            results[ref] = o
            ra = [r for r in o['rad'] if r['kind'] == 'auth'][0]
            BOOK.rows.append(lat_line(ref, ra))
            say(table([BOOK.rows[-1]]).splitlines()[1])
            say('  ' + sys_line(ref, o))
            name = 'B RADIUS %d/s + http 100' % rate
            f0 = len(fpm_log_lines())
            t_start = time.time()
            PACE['how'] = 'real'                # 100 people and admin tabs as they really ask
            o = run(name, [auth('pw', rate, {'fresh': 0.9, 'wrong': 0.1}), {'kind': 'acct', 'realm': 'acct', 'rate': 50, 'nsock': 4}],
                    http=100, duration=BOTH_S)
            results[name] = o
            rb = [r for r in o['rad'] if r['kind'] == 'auth'][0]
            BOOK.rows.append(lat_line(name, rb))
            say(table([BOOK.rows[-1]]).splitlines()[1])
            agg, st = http_report(name, o)
            say('  ' + sys_line(name, o))
            why = classify_rejects(rb, t_start)
            if why:
                say('  refused right codes, by reason:', dict(why.most_common(5)))
            p_a, p_b = pct(ra['lat']['all'], .99), pct(rb['lat']['all'], .99)
            BOOK.check('%s: RADIUS all answered, right, none twice' % name,
                       rb['n_wrong'] == 0 and not rb['counts'].get('timeout') and not rb['fresh_rej'] and
                       not rb['counts'].get('double_accept'),
                       {'timeouts': rb['counts'].get('timeout', 0), 'refused right': len(rb['fresh_rej']), 'wrong': rb['wrong'][:2]})
            BOOK.check('%s: RADIUS p99 < %.0f ms while the pages are hammered (alone %s, with HTTP %s)'
                       % (name, P99_MODERATE_MS, fmt(p_a), fmt(p_b)), (p_b or 1e9) < P99_MODERATE_MS)
            BOOK.check('%s: HTTP load does not multiply RADIUS p99 (with/alone %.1fx <= 3x or +10 ms)'
                       % (name, (p_b or 0) / max(0.1, p_a or 0.1)), (p_b or 1e9) <= max(3 * (p_a or 0), (p_a or 0) + 10))
            acct_check(name, o)
            n5 = sum(v for k, v in agg.items() if k >= 500 or k == 0)
            BOOK.check('%s: no 5xx and no failed connection' % name, n5 == 0,
                       {k: v for k, v in st.items() if k.startswith(('err_said', 'client_broke'))} if n5 else '')
            PACE['how'] = 'flood'
            # The same with 100 clients asking as fast as they can (no person does): said, not
            # judged - one Python process works RADIUS and the pages, so a flood of pages slows it.
            namef = 'B RADIUS %d/s + http 100 flood (said only)' % rate
            o = run(namef, [auth('pw', rate, {'fresh': 0.9, 'wrong': 0.1}), {'kind': 'acct', 'realm': 'acct', 'rate': 50, 'nsock': 4}],
                    http=100, duration=min(BOTH_S, 45))
            results[namef] = o
            rf = [r for r in o['rad'] if r['kind'] == 'auth'][0]
            BOOK.rows.append(lat_line(namef, rf))
            say(table([BOOK.rows[-1]]).splitlines()[1])
            http_report(namef, o)
            say('  ' + sys_line(namef, o))
            whyf = classify_rejects(rf, time.time() - min(BOTH_S, 45) - 5)
            if whyf:
                say('  flood: refused right codes, by reason:', dict(whyf.most_common(5)))
        # ---- S: soak ----------------------------------------------------------------------------
        if 'S' in PHASES:
            rate = max(20, int(k_pw * 0.4))
            name = 'S soak %ds' % SOAK_S
            r0 = tokhelper('rows')
            f0 = len(fpm_log_lines())
            o = run(name, [auth('pw', rate, {'fresh': 0.8, 'wrong': 0.1, 'replay': 0.1}),
                           {'kind': 'chal', 'realm': 'ch', 'rate': 5, 'good': CH, 'keys': ks(CH)},
                           {'kind': 'acct', 'realm': 'acct', 'rate': 50, 'nsock': 4},
                           {'kind': 'retr', 'realm': 'otp', 'rate': 2, 'good': GOOD['otp'][:3000],
                            'keys': ks(GOOD['otp'][:3000])}],
                    http=20, duration=SOAK_S, sample_every=5.0) if not PACE.update(how='real') else None
            PACE['how'] = 'flood'
            results[name] = o
            r1 = tokhelper('rows')
            for r in o['rad']:
                BOOK.rows.append(lat_line(name, r))
            say(table([x for x in BOOK.rows if x['phase'] == name]))
            agg, st = http_report(name, o)
            say('  ' + sys_line(name, o))
            sent = sum(r['counts'].get('sent', 0) for r in o['rad'])
            say('  database rows gained: %s for %d RADIUS requests (%.2f radius_log rows / request)'
                % ({k: r1[k] - r0[k] for k in r1}, sent, (r1['radius_log'] - r0['radius_log']) / max(1.0, sent)))
            sm = [x for x in o['samples'] if x['d']]
            # growth: the first minute against the last minute, and the trend over the second half
            a = sm[:max(1, len(sm) // 10)]
            b = sm[-max(1, len(sm) // 10):]
            avg = lambda xs, f: sum(f(x) for x in xs) / float(len(xs))
            gr = {'daemon rss MB': (avg(a, lambda x: x['d']['rss']) / 1024, avg(b, lambda x: x['d']['rss']) / 1024),
                  'daemon threads': (avg(a, lambda x: x['d']['th']), avg(b, lambda x: x['d']['th'])),
                  'daemon fds': (avg(a, lambda x: x['d']['fds']), avg(b, lambda x: x['d']['fds'])),
                  'php-fpm rss MB': (avg(a, lambda x: x['fpm_rss']) / 1024, avg(b, lambda x: x['fpm_rss']) / 1024),
                  'php-fpm children': (avg(a, lambda x: x['fpm_n']), avg(b, lambda x: x['fpm_n'])),
                  'nginx rss MB': (avg(a, lambda x: x['ngx_rss']) / 1024, avg(b, lambda x: x['ngx_rss']) / 1024),
                  'nginx fds': (avg(a, lambda x: x['ngx_fds']), avg(b, lambda x: x['ngx_fds']))}
            for k, (x, y) in gr.items():
                say('  soak %-18s first %8.1f  last %8.1f' % (k, x, y))
            half = sm[len(sm) // 2:]
            mid_rss = half[0]['d']['rss'] / 1024. if half else 0
            end_rss = half[-1]['d']['rss'] / 1024. if half else 0
            say('  soak daemon rss over the second half: %.1f -> %.1f MB' % (mid_rss, end_rss))
            BOOK.check('%s: daemon memory bounded (last minute <= first minute + 25%% + 30 MB)' % name,
                       gr['daemon rss MB'][1] <= gr['daemon rss MB'][0] * 1.25 + 30, gr['daemon rss MB'])
            BOOK.check('%s: daemon threads bounded (+10 at most)' % name, gr['daemon threads'][1] <= gr['daemon threads'][0] + 10,
                       gr['daemon threads'])
            BOOK.check('%s: daemon FDs bounded (+50 at most)' % name, gr['daemon fds'][1] <= gr['daemon fds'][0] + 50, gr['daemon fds'])
            BOOK.check('%s: nginx/php-fpm memory bounded' % name,
                       gr['nginx rss MB'][1] <= gr['nginx rss MB'][0] * 1.5 + 20 and
                       gr['php-fpm rss MB'][1] <= gr['php-fpm rss MB'][0] * 1.5 + 100, (gr['nginx rss MB'], gr['php-fpm rss MB']))
            allr = o['rad']
            BOOK.check('%s: RADIUS no wrong answer, none twice, nothing unanswered' % name,
                       all(r['n_wrong'] == 0 and not r['counts'].get('timeout') and not r['counts'].get('double_accept')
                           and not r['fresh_rej'] for r in allr),
                       {'%s/%s' % (r['kind'], r['realm']): (r['n_wrong'], r['counts'].get('timeout', 0), len(r['fresh_rej']))
                        for r in allr})
            a = [r for r in allr if r['kind'] == 'auth'][0]
            BOOK.check('%s: password+code p99 < %.0f ms over the whole soak (%s)' % (name, P99_MODERATE_MS, fmt(pct(a['lat']['all'], .99))),
                       (pct(a['lat']['all'], .99) or 1e9) < P99_MODERATE_MS)
            acct_check(name, o)
            n5 = sum(v for k, v in agg.items() if k >= 500 or k == 0)
            BOOK.check('%s: no 5xx and no failed connection' % name, n5 == 0)
    finally:
        # ---- across the whole run ---------------------------------------------------------------
        try:
            twice = [(k, v) for k, v in BOOK.accepted.items() if len(v) > 1]
            BOOK.check('the whole run: no code let in twice (%d codes let in)' % len(BOOK.accepted), not twice, twice[:5])
            for k, v in twice[:5]:
                say('   let in twice:', k, v)
            srv = tokhelper('sql', inp="SELECT name, CAST(ts / 30 AS INTEGER) + COALESCE(step_off, 0) AS step, COUNT(*) AS n "
                                       "FROM otp_log WHERE name LIKE 'zzr265%' AND ok = 1 AND how = 'radius' "
                                       "GROUP BY name, CAST(ts / 30 AS INTEGER) + COALESCE(step_off, 0) HAVING COUNT(*) > 1")
            # otp_log is written after the answer: a code checked just before a step's end is logged in
            # the next one. Counted again with the time moved back 3 s; only a pair in both counts is one.
            srv_b = tokhelper('sql', inp="SELECT name, CAST((ts - 3) / 30 AS INTEGER) + COALESCE(step_off, 0) AS step, COUNT(*) AS n "
                                         "FROM otp_log WHERE name LIKE 'zzr265%' AND ok = 1 AND how = 'radius' "
                                         "GROUP BY name, CAST((ts - 3) / 30 AS INTEGER) + COALESCE(step_off, 0) HAVING COUNT(*) > 1")
            try:
                kb = set((r['name'], r['step']) for r in srv_b or [])
                srv = [r for r in srv or [] if (r['name'], r['step']) in kb]
            except (TypeError, KeyError):
                pass
            BOOK.check('the daemon\'s own log: no token let in twice for one 30 s step (otp_log)', not srv, srv[:5])
            st1 = adm.get('status').get('radius', {}).get('counts', {})
            say('daemon radius counters, start -> end:', st0, '->', st1)
            BOOK.check('the daemon dropped nothing for a full queue (overflow) or as too old (stale)',
                       not (st1.get('overflow', 0) - st0.get('overflow', 0)) and not (st1.get('stale', 0) - st0.get('stale', 0)),
                       {k: st1.get(k, 0) - st0.get(k, 0) for k in ('overflow', 'stale', 'no_database', 'repeated')})
            fl = fpm_log_lines()[fpm0:]
            say('php-fpm log lines during the run: %d; max_children reached: %d' % (len(fl), len([x for x in fl if 'max_children' in x])))
            for x in fl[-5:]:
                say('   ', x[-200:])
            say('daemon at end:', proc_of(pids()['daemon']))
            say('the database: %s (PostgreSQL not run: the live install is a standalone SQLite one; moving it to '
                'PostgreSQL is the HA wizard, not a switch - t_latency.py VERSION postgres measures the engine on a '
                'private daemon)' % db_engine)
            say('\n==== SUMMARY (latency ms; tmo = unanswered in %.0f s; wrong = a wrong answer; rej! = a right code '
                'refused; 2x = a code let in twice)' % TIMEOUT)
            say(table(BOOK.rows))
            say('KNEE: %s' % knee)
            json.dump({'rows': BOOK.rows, 'checks': BOOK.checks, 'knee': knee, 'db': db_engine,
                       'sys': {k: v['sys'] for k, v in results.items()}},
                      open(OUTDIR + '/t_load-summary.json', 'w'), indent=1, default=str)
        finally:
            cleanup()
    bad = [c for c in BOOK.checks if not c[1]]
    say('\nRESULT: %s - %d of %d checks passed' % ('PASS' if not bad else 'FAIL', len(BOOK.checks) - len(bad), len(BOOK.checks)))
    for c in bad:
        say('  FAIL', c[0], c[2] if c[2] else '')
    return 0 if not bad else 1


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('as root')
    sys.exit(main())
