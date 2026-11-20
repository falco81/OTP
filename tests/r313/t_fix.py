"""t_fix.py - 1.0.313: the cap of wrong directory passwords counted as the directory counts them - its
counter goes back to 0 only once the time has gone by since the LAST wrong password. The parts loaded as a
module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.313'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r313_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx313', 'api_port': 29943}, open(D + '/config.json', 'w'))
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




import collections, threading


class D(object):
    def __init__(self):
        self.login_fails = collections.defaultdict(list)
        self.login_info = {}


class H(object):
    THROTTLE_LOCK = threading.Lock()
    THROTTLE_TIDIED = [0.0]
    throttle = m.ApiHandler.throttle

    def __init__(self, d, ip):
        self.d, self.ip = d, ip

    def client_ip(self):
        return self.ip


def count_until_refused(kind, tries, names, ips, **kw):
    """How many wrong attempts pass before a 429, every attempt kept (failed)."""
    d = D()
    n = 0
    for i in range(1000):
        h = H(d, ips(i))
        try:
            h.throttle(kind, tries, 15, name=names(i), **kw)
        except m.ApiError as e:
            return n, e.status if hasattr(e, 'status') else getattr(e, 'code', None)
        n += 1
    return n, None


src = open(TOP + '/otp.py').read()
# ==== 1 the sign-in to the administration counts as it is called
call = re.search(r"key = h\.throttle\('admin', tries, int\(CONFIG\.get\('login_wait_min'\) or 15\), name=name,\s*ip_tries=max\(50, tries \* 10\)\)", src)
ok('1 the administration sign-in: per address max(50, 10 x), per name the default (4 x)', call)
call = re.search(r"key = h\.throttle\('portal', tries, int\(CONFIG\.get\('portal_wait_min'\) or 15\), name=name,\s*ip_tries=max\(50, tries \* 10\)\)", src)
ok('1 the enrolment sign-in: the same', call)
# ==== 2 what that gives, for 5 and for 10
for tries in (5, 10):
    n, _ = count_until_refused('admin', tries, lambda i: 'novak', lambda i: '10.0.0.%d' % (i % 200 + 1),
                               ip_tries=max(50, tries * 10))
    ok('2 tries=%d: one name, many addresses: %d pass (four times)' % (tries, n), n == tries * 4, n)
    n, _ = count_until_refused('admin', tries, lambda i: 'user%d' % i, lambda i: '10.0.0.1',
                               ip_tries=max(50, tries * 10))
    ok('2 tries=%d: one address, many names: %d pass (ten times, at least 50)' % (tries, n),
       n == max(50, tries * 10), n)
# ==== 3 what the settings say
says = m.SAYS
lt, pt = says.get('login_tries') or '', says.get('portal_tries') or ''
ok('3 login_tries no longer says "from one address before it has to wait"', 'from one address before' not in lt, lt)
ok('3 login_tries says four times for a name, ten times and 50 for an address',
   'four times' in lt and 'ten times' in lt and '50' in lt, lt)
ok('3 login_tries says the codes of the second step count too', 'second step' in lt, lt)
ok('3 portal_tries says the same', 'four times' in pt and 'ten times' in pt and '50' in pt and
   'from one address on the enrolment pages before it has' not in pt, pt)
# ==== 4 the docs and Czech
doc = open(BUILD + '/out/otp-%s/docs/operations.md' % _OUTV).read()
ok('4 operations.md: 20 for a name, 50 for an address', '20 for a name, 50 for an address' in doc)
cs = open(BUILD + '/out/otp-%s/web/lang/cs.json' % _OUTV).read()
ok('4 cs.json has both', cs.count('čtyřnásobku tohoto počtu') >= 2)
print('ALL %d / %d' % (sum(R), len(R)))
