# halib.py - the HA sandbox (tests/hasb, replicated, PostgreSQL 16 A 5432 / B 5433) for the
# full HA tests: the daemons started and stopped, the API asked as a signed-in admin,
# RADIUS asked on either node or on the VIP address, a prober asking all the time.
import os, sys, json, time, subprocess, threading, urllib.request, collections, base64, glob, re

VER = os.environ.get('OTP_VER') or (sys.argv[1] if len(sys.argv) > 1 else '1.0.187')
V = '/home/claude/build/out/otp-%s' % VER
H = '/home/claude/work/hasb'
S = open(H + '/current').read().strip()
SECRET = 'radius-secret-ha-187'
ADMIN_PW = 'Local-Admin-Pass-187!'
R = []
VIP = '10.99.0.200'


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % (more,)) if more and not cond else ''),
          flush=True)


def done():
    print('ALL %d / %d' % (sum(R), len(R)), flush=True)


def env(n):
    out = subprocess.run(['bash', '-c', '. %s/env.sh %s; env -0' % (H, n)], capture_output=True).stdout
    return dict(x.split('=', 1) for x in out.decode().split('\0') if '=' in x)


E = {n: env(n) for n in 'ab'}
CONF = {n: json.load(open('%s/%s/config.json' % (S, n))) for n in 'ab'}
PORT = {n: CONF[n]['api_port'] for n in 'ab'}
RPORT = {n: CONF[n]['radius_auth_port'] for n in 'ab'}
NAME = {'a': 'nodea', 'b': 'nodeb'}
sys.path.insert(0, V)
sys.argv = ['x']
os.environ.update(E['a'])
import otp  # noqa: E402


def psql(port, sql, db=None):
    cmd = ['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-XAtq', '-c', sql]
    if db:
        cmd[5:5] = ['-d', db]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def dbq(n, sql):
    return psql(5432 if n == 'a' else 5433, sql, CONF[n]['db_name'])


def in_node(n, code):
    """Python run with node n's environment, otp imported as `otp`, its Storage as `st`."""
    pre = ('import sys, os, json, time; sys.path.insert(0, %r); sys.argv = ["x"]\nimport otp\n'
           'otp.load_config(saved=None)\nst = otp.Storage(otp.open_db())\n'
           'otp.load_config(saved=st.settings_saved())\n' % V)
    r = subprocess.run([sys.executable, '-c', pre + code], env=E[n], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return r.stdout


helpers = None


def helpers_on():
    """One loop of the root helpers, as one otp-web.path: any left from before stopped."""
    global helpers
    if helpers is None:
        for p in subprocess.run(['pgrep', '-f', 'helpers[.]sh'], capture_output=True, text=True).stdout.split():
            try:
                os.kill(int(p), 15)
            except OSError:
                pass
    if helpers is None or helpers.poll() is not None:
        helpers = subprocess.Popen(['bash', H + '/helpers.sh', VER], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)


def running(n):
    out = []
    for p in subprocess.run(['pgrep', '-f', 'otp.py --daemon'], capture_output=True, text=True).stdout.split():
        try:
            envs = open('/proc/%s/environ' % p, 'rb').read().split(b'\0')
        except OSError:
            continue
        if ('OTP_CONFIG=%s/%s/config.json' % (S, n)).encode() in envs:
            out.append(int(p))
    return out


def start(n, reboot=False):
    subprocess.run(['bash', H + '/start.sh', n, VER] + (['reboot'] if reboot else []))
    return up(n)


def stop(n):
    for p in running(n):
        try:
            os.kill(p, 15)
        except OSError:
            pass
    for _ in range(40):
        if not running(n):
            return True
        time.sleep(0.25)
    for p in running(n):
        os.kill(p, 9)
    return True


TOK, SESS = {}, {}


def up(n, wait=90):
    for _ in range(wait):
        time.sleep(1)
        try:
            TOK[n] = open('%s/%s/run/api-token' % (S, n)).read().strip()
            st, _ = call(n, '/api/health', sess=False)
            # /api/health takes any token: the token read before the daemon wrote it anew
            # is the one an asked-for page refuses (403).
            if st in (200, 401, 403, 503) and call(n, '/api/ha', sess=False)[0] != 403:
                return True
        except Exception:                               # noqa: BLE001
            pass
    return False


def call(n, path, body=None, sess=True, timeout=60):
    h = {'X-Otp-Token': TOK.get(n, ''), 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess and SESS.get(n):
        h['X-Otp-Session'] = SESS[n]
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (PORT[n], path),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}
    except Exception as e:                              # noqa: BLE001
        return 0, {'error': str(e)}


def login(n):
    for _ in range(3):
        st, got = call(n, '/api/auth/login', {'name': 'local', 'password': ADMIN_PW}, sess=False)
        if st == 200:
            SESS[n] = got.get('token')
            return True
        time.sleep(2)
    return False


# ---- RADIUS -------------------------------------------------------------------------------
def where(target):
    """(address, port) of a node, or of the VIP address: whichever node holds it."""
    if target == 'vip':
        m = vip_master()
        return VIP, RPORT[m] if m else RPORT['a']
    return '127.0.0.1', RPORT[target]


def rad(target, user, password, state=None, timeout=4):
    """(result, {attr: value}) - result accept|reject|challenge|timeout."""
    host, port = where(target)
    extra = [('State', state)] if state else []
    try:
        c, attrs, _ms = otp.radius_ask(host, port, SECRET, user, password, timeout=timeout, tries=1, extra=extra)
    except Exception as e:                              # noqa: BLE001
        return 'timeout', {'error': str(e)[:120]}
    return {2: 'accept', 3: 'reject', 11: 'challenge'}.get(c, str(c)), dict(attrs)


def totp_of(secret, off=0):
    s = secret.replace(' ', '')
    return otp.totp(base64.b32decode(s + '=' * (-len(s) % 8)), time.time() + off)


# ---- the VIP address by keepalived, one for each node on lo -----------------------------
KA = {}


def vip_role(n):
    try:
        return open('%s/%s/run/vip-role' % (S, n)).read().split()[0]
    except (OSError, IndexError):
        return ''


def vip_master():
    for n in 'ab':
        if vip_role(n) == 'MASTER' and running(n):
            return n
    for n in 'ab':
        if vip_role(n) == 'MASTER':
            return n
    return None


# ---- a prober: RADIUS asked all the time, each node and the VIP address -------------------
class Prober(object):
    def __init__(self, every=0.3):
        self.every = every
        self.expect_down = set()
        self.lost = collections.defaultdict(list)
        self.asked = collections.Counter()
        self.stop_flag = False
        self.t = threading.Thread(target=self.run, daemon=True)
        self.t.start()

    def run(self):
        while not self.stop_flag:
            for target in ('a', 'b', 'vip'):
                if target in self.expect_down:
                    continue
                self.asked[target] += 1
                got, _ = rad(target, 'probe-nobody', '000000', timeout=2)
                if got == 'timeout':
                    self.lost[target].append(time.time())
            time.sleep(self.every)

    def gaps(self, target, since=0):
        """The longest run of unanswered probes, in seconds."""
        ts = [t for t in self.lost[target] if t >= since]
        if not ts:
            return 0.0
        best, run0, last = 0.0, ts[0], ts[0]
        for t in ts[1:]:
            if t - last > self.every * 4 + 2.5:
                best = max(best, last - run0 + 2)
                run0 = t
            last = t
        return max(best, last - run0 + 2)


CHECK_SRC = V + '/deploy/otp-vip-check'          # this version's, not the one installed


def ka_sync(n):
    """keepalived of node n, from the file its root helper wrote: started, read again
    when the file changed, stopped when there is none - its check reading this node's
    vip-state (OTP_RUN), its role written to S/n/vip-role."""
    conf = '%s/%s/keepalived.conf' % (S, n)
    mine = '%s/%s/ka.run.conf' % (S, n)
    chk = '%s/%s/vipcheck.sh' % (S, n)
    pidf = '%s/%s/ka.pid' % (S, n)
    if not os.path.exists(conf):
        ka_stop(n)
        return
    src = open(CHECK_SRC).read().replace('/run/otp/vip-state', '%s/%s/run/vip-state' % (S, n)) \
        .replace('/run/otp/vip-role', '%s/%s/run/vip-role' % (S, n)).replace('[ -d /run/otp ] && ', '') \
        .replace('/var/lib/otp/otp.lock', '%s/%s/state/otp.lock' % (S, n))
    if not os.path.exists(chk) or open(chk).read() != src:
        open(chk, 'w').write(src)
        os.chmod(chk, 0o755)
    text = open(conf).read()
    for p in ('/usr/libexec/keepalived/otp-vip-check', '/usr/local/lib/otp/otp-vip-check'):
        text = text.replace(p, chk)
    text = text.replace('script_user otp', 'script_user root')
    changed = not os.path.exists(mine) or open(mine).read() != text
    if changed:
        open(mine, 'w').write(text)
    pid = ka_pid(n)
    if pid and changed:
        os.kill(pid, 1)                 # SIGHUP: read the file again
    elif not pid:
        subprocess.Popen(['keepalived', '-n', '-l', '-D', '-f', mine, '-p', pidf,
                          '-r', pidf + '.vrrp', '-c', pidf + '.chk'],
                         stdout=open('%s/%s/ka.log' % (S, n), 'a'), stderr=subprocess.STDOUT,
                         start_new_session=True)


def ka_pid(n):
    try:
        p = int(open('%s/%s/ka.pid' % (S, n)).read().strip())
        os.kill(p, 0)
        return p
    except (OSError, ValueError):
        return None


def ka_stop(n):
    p = ka_pid(n)
    if p:
        os.kill(p, 15)
        for _ in range(20):
            if not ka_pid(n):
                break
            time.sleep(0.25)
    try:
        os.unlink('%s/%s/run/vip-role' % (S, n))
    except OSError:
        pass


KA_OFF = set()          # nodes whose keepalived is down on purpose (a machine off)


def ka_loop():
    while True:
        for n in 'ab':
            if n in KA_OFF:
                continue
            try:
                ka_sync(n)
            except Exception as e:                      # noqa: BLE001
                print('keepalived %s: %s' % (n, e), flush=True)
        time.sleep(1)


def ka_on():
    threading.Thread(target=ka_loop, daemon=True).start()
