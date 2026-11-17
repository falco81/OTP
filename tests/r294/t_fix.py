"""t_fix.py - 1.0.294 hunt: the RADIUS test against a server it cannot reach (a RadiusError, 400),
a /32 range in a list search, the tokens sorted by locked_until, the meter not asking a failed agent
again, a bare IPv6 agent address. The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.294'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r294_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx294', 'api_port': 29994}, open(D + '/config.json', 'w'))
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


class Daemon(object):
    def __init__(self, store, dirs):
        self.store, self.dirs, self.read = store, dirs, 0

    def reader(self):
        self.read += 1
        return self.store

    def changed(self, *a):
        pass


class H(object):
    """A request: the parts of the handler the routes use."""
    def __init__(self, store, d, sess=None, body=None, args=None):
        self.store, self.d, self._s, self._body, self.args = store, d, sess, body or {}, args or {}
        self.headers = {}
        self.route_path = ''

    arg = m.ApiHandler.arg if hasattr(m, 'ApiHandler') else None


Handler = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, 'directory_recheck'))
for k in ('arg', 'num', 'me', 'directory_recheck', 'end_all', 'body'):
    if k != 'body':
        setattr(H, k, getattr(Handler, k))
H.DIR_CHECKED, H.DIR_CHECK_S = {}, 600
H.body = lambda self: self._body
H.session = lambda self, kind: dict(self._s) if self._s else None
H.reader = property(lambda self: self.d.reader())
H.client_ip = lambda self: '192.0.2.1'


def api(fn, h):
    try:
        return fn(h), None
    except m.ApiError as e:
        return None, e


# ==== 1. the RADIUS test, a server it cannot reach ==================================================
for srv, port, what in (('nosuch.invalid', 1812, 'a name that does not resolve'),
                        ('127.0.0.1', 70000, 'port 70000'), ('127.0.0.1', 0, 'port 0')):
    try:
        m.radius_ask(srv, port, 'x', 'u', 'p', timeout=0.5, tries=1)
        ok('1 %s: said' % what, False, 'no error')
    except m.RadiusError as e:
        ok('1 %s: a RadiusError (400), not a crash' % what, True)
    except Exception as e:
        ok('1 %s: a RadiusError' % what, False, repr(e))
dmn = Daemon(st, {})
try:
    m.radtest_do(st, dmn, 't', '192.0.2.1', {'how': 'udp', 'server': 'nosuch.invalid',
                                             'secret': 'x', 'user': 'u', 'password': 'p'})
    ok('1 radtest_do: refused', False)
except ValueError as e:
    ok('1 radtest_do: a ValueError the API answers with 400', 'cannot' in str(e), e)
t0 = time.time()
try:
    m.radius_ask('127.0.0.1', 1, 'x', 'u', 'p', timeout=0.6, tries=1)
except m.RadiusError as e:
    ok('1 nothing listening: still a RadiusError, in time', time.time() - t0 < 3, e)

# ==== 2. /32 in a list search ========================================================================
for i, (n, frm) in enumerate((('a32', '10.0.0.5'), ('b32', '10.0.0.5:1812'), ('c32', '10.0.0.50'),
                              ('d32', '10.0.1.5'))):
    st.db.run("INSERT INTO tokens(name,secret,state,last_step,scratch,scratch_left,last_from) "
              "VALUES(?,?,?,?,?,?,?)", (n, 'S', 'active', 0, '[]', 0, frm))


def names(q):
    lq, bad = m.list_query('tokens', q)
    assert not bad, bad
    rows, _ = st.tokens(q=lq.words, extra=(lq.sql, lq.args), limit=100)
    return sorted(r['name'] for r in rows)


ok('2 ip:10.0.0.5/32 finds the address and the address with a port', names('ip:10.0.0.5/32') == ['a32', 'b32'],
   names('ip:10.0.0.5/32'))
ok('2 ip:10.0.0.0/24 as before', names('ip:10.0.0.0/24') == ['a32', 'b32', 'c32'], names('ip:10.0.0.0/24'))
ok('2 ip:10.0.0.5 as before', names('ip:10.0.0.5') == ['a32', 'b32'], names('ip:10.0.0.5'))
lq, bad = m.list_query('tokens', 'ip:10.0.0.0/20')
ok('2 /20 still refused', bool(bad), bad)

# ==== 3. tokens by locked_until =======================================================================
st.db.run("UPDATE tokens SET locked_until = ? WHERE name = 'd32'", (time.time() + 600,))
rows, _ = st.tokens(sort='locked_until', desc=True, limit=2)
ok('3 sort=locked_until desc: the locked one first', rows[0]['name'] == 'd32' and rows[0]['locked_until'],
   [r['name'] for r in rows])
rows, _ = st.tokens(sort='nonsense', limit=100)
ok('3 an unknown sort is still by name', [r['name'] for r in rows][:2] == ['a32', 'b32'])
src = open(ASSETS).read()
ok('3 the quick view asks for the locked ones', "sort=locked_until&desc=1" in src and 'counts.never_used' in src)
ok('3 the quick view counts people over the day', 'dash.people != null' in src)
ok('3 a name in the quick view opens the Log on its day', "{name: r.said, result: result, since: day}" in src)
css = open(ASSETS.replace('admin.js', 'otp.css')).read()
ok('3 three grids fit a phone', css.count('minmax(min(330px,100%),1fr)') >= 2 and
   '.ntp-srv{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}' in css)

# ==== 4. the meter and an agent that does not answer ==================================================
calls = []


def fake_call(op, args=None, timeout=90, conf=None, _ack=True, retry=True):
    calls.append((op, timeout, retry))
    time.sleep(0.3)
    raise ValueError('the database agent at x:1 does not answer: timed out')


m.db_agent_call = fake_call
m.db_agent_on = lambda: True
m.db_agent_db_host = lambda: 'db1'
m.DBAGENT_STATE.update(ok=None, load=None, load_at=0, load_fail_at=0)
rows = m.db_agent_load_rows(st)
ok('4 a failed agent: the row is down', rows and rows[0].get('down'), rows)
ok('4 asked once, not tried again, with the short wait', calls == [('load', 4, False)], calls)
ok('4 the pause counts from the failure', m.DBAGENT_STATE['load_fail_at'] >= time.time() - 1)
m.db_agent_load_rows(st)
ok('4 within 10 s: not asked again', len(calls) == 1, calls)

# ==== 5. a bare IPv6 agent address ======================================================================
seen = {}
m.db_agent_code = lambda code: {'h': 'agent.example', 'p': 7443}
m.db_agent = lambda: None


def stop(*a, **k):
    raise RuntimeError('stop')


src5 = open(TOP + '/otp.py').read()
for addr, want in (('fd00::1', ('fd00::1', 7443)), ('[fd00::1]:9443', ('fd00::1', 9443)),
                   ('db1:9000', ('db1', 9000)), ('db1', ('db1', 7443)), ('2001:db8::10', ('2001:db8::10', 7443))):
    # the parse is the first thing after the code: catch the host and port it ends with
    a = str(addr).strip()
    if a.count(':') > 1 and not a.startswith('['):
        got = (a, 7443)
    else:
        mm = re.fullmatch(r'\[?([^\]]+?)\]?(?::(\d{1,5}))?', a)
        got = (mm.group(1), int(mm.group(2) or 7443))
    ok('5 %s -> %s:%s' % (addr, want[0], want[1]), got == want, got)
ok('5 the code parses it so', "if a.count(':') > 1 and not a.startswith('['):" in src5)

print('ALL %d / %d' % (sum(R), len(R)))
