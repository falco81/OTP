"""t_ops_fix.py - 1.0.262 (ops fixes): F1a SELinux wants http_port_t for the balancer's own port;
F1b web_proxy_port kept apart from otp's and its databases' ports, against the batch being saved
(both ways) and, when it changes, a port already listening on 127.0.0.1; F2 otp --acme-order waits
for DNS and orders a full name only (ACME not switched on for a short one); F3 the console's
Upgrades: to be done by hand (show, mark one done, clear done lately behind a confirm); F4 a nightly
copy with no token to try is not "cannot be put back". Pure Python: no daemon, no database; one
port bound on 127.0.0.1 by the test itself (an ephemeral one) for the listening check.

    python3 t_ops_fix.py
"""
import ast, json, os, re, socket, sys, tempfile, threading, time, types
from pathlib import Path

PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]))


def src_of(f):
    return open(os.path.join(PARTS, f), encoding='utf-8').read()


def defs(fname, names, cls=None):
    text = src_of(fname)
    tree = ast.parse(text)
    lines = text.splitlines(True)
    body = tree.body
    if cls:
        body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    out = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            seg = lines[node.lineno - 1:node.end_lineno]
            if cls:
                import textwrap
                seg = [textwrap.dedent(''.join(seg))]
            out.append(''.join(seg))
    assert len(out) == len(names), names
    return '\n\n'.join(out)


# ---- F1a: SELinux ------------------------------------------------------------------------------
CONFIG = {}
SAVED = {}
g = {'CONFIG': CONFIG, 'time': time, 'node_name': lambda: 'otp1', '_meta_json': lambda st, k: SAVED.get(k),
     'odict': lambda v: v if isinstance(v, dict) else {}, 'ssh_gate_wanted': lambda st: False,
     'selinux_facts': lambda st: {}, 'se_helper_knows_http': lambda: True}
_se = src_of('87e_selinux.py')
exec(_se[_se.index('SE_HTTPD_TCP = '):_se.index('\n\n', _se.index('SE_HTTPD_TCP = '))], g)
RF = {'installer': '1.0.262'}
g.update(re=re, root_facts=lambda: RF, _ver_tuple=lambda v: tuple(int(x) for x in str(v).split('.')[:3]))
exec(compile(defs('87e_selinux.py', ['selinux_want', 'selinux_httpd_bindable', 'se_helper_knows_http']),
             '87e', 'exec'), g)


def http_ports():
    return [p for p in g['selinux_want'](None)['ports'] if p['type'] == 'http_port_t']


ok('F1a no balancer port: nothing wanted (as before)', http_ports() == [])
CONFIG.update(web_proxy=1, web_proxy_port=9443)
hp = http_ports()
ok('F1a 9443 with the balancer on: http_port_t tcp', len(hp) == 1 and hp[0]['port'] == 9443 and
   hp[0]['proto'] == 'tcp' and hp[0]['why'], hp)
ok('F1a shaped as the other wants', set(hp[0]) == {'port', 'proto', 'type', 'why'})
for p in (80, 443, 8443):
    CONFIG['web_proxy_port'] = p
    ok('F1a %d is http_port_t already: not wanted' % p, http_ports() == [])
for p in (8080, 8118, 8123, 10005, 81, 9000):
    CONFIG['web_proxy_port'] = p
    ok('F1a %d has a type httpd binds (http_cache_port_t / http_port_t): not asked' % p, http_ports() == [])
for p in (10011, 8444, 4443):
    CONFIG['web_proxy_port'] = p
    ok('F1a %d of no such type: asked' % p, len(http_ports()) == 1)
CONFIG.update(web_proxy=0, web_proxy_port=9443)
ok('F1a balancer off: not wanted', http_ports() == [])
CONFIG.update(web_proxy=1, web_proxy_port='junk')
ok('F1a a bad value: nothing, no crash', http_ports() == [])
CONFIG.update(web_proxy=1, web_proxy_port=9443)
for inst, want in (('1.0.261', 0), ('', 0), ('junk', 0), (None, 0), ('1.0.262', 1), ('1.0.300', 1)):
    RF.clear()
    if inst is not None:
        RF['installer'] = inst
    ok('R3-4 root\'s helper of install.sh %r: http_port_t %s' % (inst, 'asked' if want else 'not asked'),
       len(http_ports()) == want)
g['root_facts'] = lambda: None
ok('R3-4 no root-facts.json: not asked', http_ports() == [])
g['root_facts'] = lambda: 1 / 0
ok('R3-4 root-facts unreadable: not asked, no crash', http_ports() == [])
g['root_facts'] = lambda: RF
RF.clear()
RF['installer'] = '1.0.262'
CONFIG.clear()

# ---- F1b: the ports kept apart ---------------------------------------------------------------
h = {'__name__': 't_head'}
exec(compile(src_of('00_head.py'), '00_head.py', 'exec'), h)
cs, Bad = h['check_setting'], h['BadSetting']
prob = h['web_proxy_port_problem']
C = h['CONFIG']
C.update(api_port=9861, ha_peer_port=5432, db_port=0, radius_auth_port=1812, radius_acct_port=1813,
         ssh_gate_port=18129, web_proxy=1, web_proxy_port=0)
# check_setting: the value alone (round 3) - the clashes are the batch's (web_proxy_port_problem)
for v in (8443, 4443, 9443, 9861, 18129, 1812):
    try:
        ok('R3-6 check_setting %d taken (its clashes asked of the save)' % v, cs('web_proxy_port', v) == v)
    except Bad as e:
        ok('R3-6 check_setting %d taken (its clashes asked of the save)' % v, False, e)
for v in (80, 1023, 5432, 3306, 70000):
    try:
        cs('web_proxy_port', v)
        ok('R3-6 check_setting %d refused' % v, False)
    except Bad as e:
        ok('R3-6 check_setting %d refused' % v, True)
ok('F1b 0 still taken', cs('web_proxy_port', 0) == 0)
ok('R3-6 {api_port: 9862, web_proxy_port: 9861} in one save', prob({'api_port': 9862, 'web_proxy_port': 9861}) == ''
   and cs('web_proxy_port', 9861) == 9861 and cs('api_port', 9862) == 9862)
ok('R3-6 the batch still refuses the API\'s port', 'web_proxy_port' in prob({'web_proxy_port': 9861}))
ok('R3-6 the batch still refuses the SSH gate\'s port', 'web_proxy_port' in prob({'web_proxy_port': 18129}))
ok('R3-6 the batch: the database\'s own (local) port', prob({'web_proxy_port': 15432, 'db_port': 15432}) != '')
# the batch: merged values
ok('F1b batch: nothing about ports - no word', prob({'site_name': 'x'}) == '')
ok('F1b batch: a free one', prob({'web_proxy_port': 9443}) == '')
ok('F1b batch: web_proxy_port = the api_port saved with it', 'web_proxy_port' in
   prob({'web_proxy_port': 9443, 'api_port': 9443}))
ok('F1b batch: api_port moved away in the same save - taken', prob({'web_proxy_port': 9861, 'api_port': 9862}) == '')
C['web_proxy_port'] = 9443
ok('F1b batch: api_port onto the balancer\'s port refused', 'balancer' in prob({'api_port': 9443}))
ok('F1b batch: radius_auth_port onto it refused', 'balancer' in prob({'radius_auth_port': 9443}))
ok('F1b batch: ssh_gate_port onto it refused', prob({'ssh_gate_port': 9443}) != '')
ok('F1b batch: api_port elsewhere taken', prob({'api_port': 9871}) == '')
# 1.0.262 round 2: switched on over a clashing kept port; db_port only for a local database;
# the other nodes' own ports
C['web_proxy'] = 0
C['web_proxy_port'] = 9861
ok('F1b balancer switched on over a kept port that is the API\'s: refused',
   'before switching it on' in prob({'web_proxy': 1}), prob({'web_proxy': 1}))
C['web_proxy_port'] = 9443
ok('F1b balancer switched on over a free kept port: taken', prob({'web_proxy': 1}) == '')
C['web_proxy'] = 1
C.update(db_port=15432, db_host='db.example.cz')
ok('F1b db_port of a database elsewhere: not a clash', prob({'web_proxy_port': 15432}) == '')
for hst in ('', '127.0.0.1', 'localhost', '/run/postgresql'):
    C['db_host'] = hst
    ok('F1b db_port of a local database (%r): a clash' % hst, prob({'web_proxy_port': 15432}) != '')
C.update(db_port=0, db_host='')
o = {'otp2': {'api_port': 9871, 'radius_auth_port': 1812}}
ok('F1b the other node\'s own API port: refused', 'on otp2' in prob({'web_proxy_port': 9871}, others=o),
   prob({'web_proxy_port': 9871}, others=o))
ok('F1b a port free on every node: taken', prob({'web_proxy_port': 9443}, others=o) == '')
ok('F1b save_settings passes the other nodes', 'others=others' in src_of('80_daemon.py'))
ok('F1b batch: the balancer\'s port taken away with it - taken', prob({'api_port': 9443, 'web_proxy_port': 0}) == '')
C['web_proxy'] = 0
ok('F1b batch: balancer off, a port kept from before - api_port not refused (old behaviour)',
   prob({'api_port': 9443}) == '')
C['web_proxy'] = 1
# listening on 127.0.0.1
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(('127.0.0.1', 0))
srv.listen(1)
busy = srv.getsockname()[1]
if busy >= 1024 and busy not in (9861, 18129, 5432, 3306, 1812, 1813):
    ok('F1b probe: a port in use refused', 'listens' in prob({'web_proxy_port': busy}, probe=True))
    ok('F1b no probe: not tried', prob({'web_proxy_port': busy}) == '')
    C['web_proxy_port'] = busy
    ok('F1b probe: the same value as before (nginx\'s own) not tried', prob({'web_proxy_port': busy}, probe=True) == '')
    C['web_proxy_port'] = 9443
srv.close()
t0 = time.time()
r = prob({'web_proxy_port': busy}, probe=True)
ok('F1b probe: a free port taken, quickly', r == '' and time.time() - t0 < 2, r)
ok('F1b probe: the save on another node not probed by default (probe=False)', 'probe=False' in src_of('00_head.py'))

# ---- F2: otp --acme-order ------------------------------------------------------------------------
cli = src_of('95_cli.py')
i = cli.index('    if args.acme_order:\n')
blk = cli[i:cli.index('\n    if args.updates:', i)]
ok('F2 DNS waited for before any name', blk.index('cli_fqdn_wait()') < blk.index('acme_name_of('))
ok('F2 the name asked once DNS answered', 'acme_name_of(store, t, answered=True)' in blk and
   'acme_targets(store, answered=True)' in blk)
ok('F2 ACME switched on only after the name is a full one',
   blk.index('cli_full_name(name)') < blk.index('acme_care_set('), blk)
cache = {'name': '', 'at': 0.0, 'asking': False}
asked = []


def fake_fqdn(answered=False):
    asked.append(1)
    if not cache['asking'] and not cache['at']:
        cache['asking'] = True

        def ask():
            time.sleep(0.3)
            cache.update(name='otp1.example.cz', at=time.monotonic(), asking=False)
        threading.Thread(target=ask, daemon=True).start()
    return cache['name'] or 'otp1'


c = {'time': time, 're': re, 'FQDN_CACHE': cache, 'fqdn_cached': fake_fqdn}
exec(compile(defs('95_cli.py', ['cli_fqdn_wait', 'cli_full_name']), '95_cli', 'exec'), c)
ok('F2 waits for DNS to answer', c['cli_fqdn_wait'](5) and cache['name'] == 'otp1.example.cz')
cache.update(name='', at=0.0, asking=True)      # a DNS that does not answer
t0 = time.time()
ok('F2 gives up after the limit', c['cli_fqdn_wait'](0.4) is False and time.time() - t0 < 2)
for n, want in (('otp1.example.cz', True), ('OTP1.Example.CZ.', True), ('otp1', False), ('', False),
                ('localhost', False), ('a..b', False), ('-x.example.cz', False), ('x.xn--p1ai', True)):
    ok('F2 full name %r: %s' % (n, want), c['cli_full_name'](n) is want)

# ---- F3: the console ---------------------------------------------------------------------------
con = src_of('96_console.py')


class FakeSelf(object):
    def __init__(self, after=None, pick=None, yes=False):
        self.after, self.pick, self.yes = after, pick, yes
        self.acts, self.notes, self.choices, self.confirms = [], [], [], []
        self.items = None

    def sub(self, title, items):
        self.items = items

    def out(self, *a):
        assert a == ('--after',), a
        return self.after

    def act(self, *a, **k):
        self.acts.append(a)
        return 0

    def note(self, title, text, tone=''):
        self.notes.append((title, text, tone))

    def working(self, w):
        pass

    def choose(self, title, options, words='', cur=0):
        self.choices.append(options)
        return self.pick

    def confirm(self, title, words, yes='Yes', no='No', danger=False):
        self.confirms.append((title, words, yes))
        return self.yes


k = {'__version__': '1.0.262', '_ver_tuple': lambda v: tuple(int(x) for x in str(v).split('.')),
     'node_name': lambda: 'otp1', 'os': os, 're': re, 'UPGRADE_HELPER': '/nope'}
exec(compile(defs('96_console.py', ['m_upgrades'], cls='Console' if 'class Console' in con else
                  re.search(r'^class (\w+)\(.*\):\n(?:.*\n)*?    def m_upgrades', con, re.M).group(1)),
             '96_console', 'exec'), k)


def menu(fs):
    k['m_upgrades'](fs)
    return {key: fn for key, words, fn, *rest in fs.items}, {key: words for key, words, *r in fs.items}


fs = FakeSelf()
fns, words = menu(fs)
ok('F3 the old items kept, as they were', [w for x, w in sorted(words.items(), key=lambda kv: int(kv[0]))][:7] ==
   ['How it stands', 'Look for a new version on the web now',
    'Upgrade from the web (every node, with its progress)', 'Follow the upgrade going on',
    'Upgrade this node from a package file', 'Stop an upgrade going on',
    'Go back to an older version (only a safe one)'])
ok('F3 three new items', all(x in words for x in ('8', '9', '10')), words)
fns['8']()
ok('F3 show: otp --after', fs.acts == [('--after',)], fs.acts)
items = [{'id': 'selinux-port', 'node': 'otp2', 'title': 'A port for SELinux'},
         {'id': 'nginx-reload', 'node': 'otp1', 'title': 'nginx again'}]
fs = FakeSelf(after={'items': items, 'cluster': True}, pick='0')
fns, _ = menu(fs)
fns['9']()
ok('F3 mark done: the picker over the items, the nodes said in a cluster',
   len(fs.choices) == 1 and len(fs.choices[0]) == 2 and '[otp2]' in fs.choices[0][0][1], fs.choices)
ok('F3 mark done: --after-done ID --node N', fs.acts == [('--after-done', 'selinux-port', '--node', 'otp2')], fs.acts)
fs = FakeSelf(after={'items': items, 'cluster': False}, pick='1')
fns, _ = menu(fs)
fns['9']()
ok('F3 mark done: standalone, no node in the words; its own node passed',
   '[' not in fs.choices[0][1][1] and fs.acts == [('--after-done', 'nginx-reload', '--node', 'otp1')], fs.acts)
fs = FakeSelf(after={'items': items}, pick=None)
fns, _ = menu(fs)
fns['9']()
ok('F3 mark done: Esc - nothing run', fs.acts == [])
fs = FakeSelf(after={'items': [], 'cluster': False})
fns, _ = menu(fs)
fns['9']()
ok('F3 mark done: nothing to do - said, nothing run', fs.acts == [] and fs.notes and fs.notes[0][2] == 'ok')
fs = FakeSelf(after=None)
fns, _ = menu(fs)
fns['9']()
ok('F3 mark done: unreadable - said as bad, nothing run', fs.acts == [] and fs.notes[0][2] == 'bad')
fs = FakeSelf(yes=False)
fns, _ = menu(fs)
fns['10']()
ok('F3 clear: behind a confirm, No - nothing run', fs.confirms and fs.acts == [])
fs = FakeSelf(yes=True)
fns, _ = menu(fs)
fns['10']()
ok('F3 clear: Yes - otp --after-clear', fs.acts == [('--after-clear',)], fs.acts)
cl = src_of('95_cli.py')
ok('F3 the flags exist in the CLI', all(f in cl for f in ("'--after'", "'--after-done'", "'--after-clear'")))

# ---- F4: a nightly copy with no token to try ---------------------------------------------------
TMP = Path(tempfile.mkdtemp(prefix='t-ops-fix-'))


class RbError(Exception):
    pass


class St(object):
    def __init__(self):
        self.meta, self.events = {}, []
        self.db = types.SimpleNamespace(engine='sqlite')

    def set_meta(self, k, v):
        self.meta[k] = v

    def add_event(self, *a, **kw):
        self.events.append(a)


READ = {}
v = {'time': time, 'os': os, 'json': json, 'shutil': __import__('shutil'), 'tempfile': tempfile,
     'subprocess': __import__('subprocess'), 'tarfile': __import__('tarfile'), 'zlib': __import__('zlib'),
     'STATE_DIR': TMP, 'DUMP_DIR': TMP, 'CONFIG': {'backup_daily': 1}, 'RB_VERIFY_KEEP': 20,
     'RbError': RbError, 'node_name': lambda: 'otp1', '_meta_json': lambda st, k, kind=dict: [],
     'rb_targets': lambda st: [{'id': 't1', 'name': 'NAS', 'enabled': 1}],
     'rb_remote_list': lambda st, tid: (_ for _ in ()).throw(RbError('x')),
     'rb_said': str, 'sealing_key': lambda: b'k' * 32,
     'kept_dumps': lambda eng: [{'name': 'otp-copy-1.json.gz', 'kind': 'copy', 'mine': True}],
     'copy_read_through': lambda path, key: READ['got']}
exec(compile(defs('86v_verify.py', ['rb_verify']), '86v', 'exec'), v)


def nightly(got):
    READ['got'] = got
    res = v['rb_verify'](St(), 'me')
    return next(c for c in res['checks'] if 'nightly' in c['what'])


c0 = nightly({'tried': 0, 'opened': 0, 'counts': {'tokens': 0}})
ok('F4 no token to try: good, and said so', c0['ok'] and 'no tokens to try' in c0['said'], c0)
c1 = nightly({'tried': 5, 'opened': 5, 'counts': {'tokens': 9}})
ok('F4 every one tried opened: good, no extra words', c1['ok'] and 'no tokens' not in c1['said'], c1)
c2 = nightly({'tried': 5, 'opened': 4, 'counts': {'tokens': 9}})
ok('F4 one did not open: not good (as before)', not c2['ok'], c2)

# ==== round 2 ====================================================================================
# ---- R1a: api_port kept apart ------------------------------------------------------------------
ap, up = h['api_port_problem'], h['udp_port_problem']
C.update(api_port=9861, web_proxy=1, web_proxy_port=9443, db_port=0, ha_peer_port=5432, snmp=0,
         snmp_port=161, ssh_gate_port=18129, radius_auth_port=1812, radius_acct_port=1813)
ok('R1a nothing about api_port - no word', ap({'site_name': 'x'}) == '')
ok('R1a a free one taken', ap({'api_port': 9871}) == '')
for v in (5432, 3306, 9443, 1812, 1813):
    ok('R1a api_port %d refused' % v, ap({'api_port': v}).startswith('api_port: %d' % v), ap({'api_port': v}))
C['db_port'] = 15432
ok('R1a the database\'s own port refused', 'database' in ap({'api_port': 15432}))
C['db_port'] = 0
C['ha_peer_port'] = 15433
ok('R1a the other node\'s database port refused', 'other node' in ap({'api_port': 15433}))
C['ha_peer_port'] = 5432
ok('R1a merged: the balancer\'s port moved in the same save - taken', ap({'api_port': 9443, 'web_proxy_port': 9444}) == '')
C['web_proxy'] = 0
ok('R1a balancer off, its port kept from before - not refused (as before)', ap({'api_port': 9443}) == '')
C['web_proxy'] = 1
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(('127.0.0.1', 0))
srv.listen(1)
busy = srv.getsockname()[1]
ok('R1a probe: a port in use refused', 'listens' in ap({'api_port': busy}, probe=True))
ok('R1a no probe (another node, the cluster\'s value): not tried', ap({'api_port': busy}) == '')
C['api_port'] = busy
ok('R1a probe: its own port now (the daemon\'s) not tried', ap({'api_port': busy}, probe=True) == '')
C['api_port'] = 9861
srv.close()
# ---- R1b: the UDP ports --------------------------------------------------------------------------
ok('R1b nothing about them - no word', up({'site_name': 'x'}) == '')
ok('R1b radius on the SSH gate\'s port refused', 'one UDP port' in up({'radius_auth_port': 18129}))
ok('R1b accounting on the SSH gate\'s port refused', 'one UDP port' in up({'radius_acct_port': 18129}))
ok('R1b the SSH gate onto RADIUS refused', 'one UDP port' in up({'ssh_gate_port': 1812}))
ok('R1b SNMP off: radius on 161 taken (as before)', up({'radius_auth_port': 161}) == '')
C['snmp'] = 1
ok('R1b SNMP on: radius on its port refused', 'SNMP' in up({'radius_auth_port': 161}))
ok('R1b SNMP switched on over RADIUS\'s port refused', 'SNMP' in up({'snmp': 1, 'snmp_port': 1813}))
ok('R1b accounting off (0) never a clash', up({'radius_acct_port': 0}) == '')
C['snmp'] = 0
C['radius_auth_port'] = 18129          # a clash kept from before, not touched now
ok('R1b a clash kept from before not refused when other keys saved', up({'snmp_port': 162}) == '')
C['radius_auth_port'] = 1812
dm = src_of('80_daemon.py')
i = dm.index('    def save_settings(')
ok('R1 the save asks both, probing on this node only',
   "why = api_port_problem(checked, probe=(node == node_name() and not cluster_wide)) or" in dm[i:] and
   'udp_port_problem(checked)' in dm[i:])
# ---- R1c: the API's port taken at the start --------------------------------------------------------
ok('R1c the start catches the bind error alone', re.search(r"try:\n\s+self\.api\.start\(\)\n\s+except ApiBindError as e:\n"
                                                          r"(?:\s+#.*\n)*\s+self\.api_bind_failed\(e\)", dm) is not None)
LOGS = []
SPARE = []


class Ev(object):
    def __init__(self, n):
        self.n = n

    def wait(self, t):
        self.n -= 1
        return self.n < 0


class FakeApi(object):
    def __init__(self, fails, exc=OSError):
        self.fails, self.tries, self.httpd, self.exc = fails, 0, None, exc

    def start(self):
        self.tries += 1
        if self.tries <= self.fails:
            raise self.exc(98, 'Address already in use')
        self.httpd = object()


class FakeStore(object):
    def __init__(self):
        self.ev = []

    def add_event(self, *a, **k):
        self.ev.append(a)


dd = {'CONFIG': {'api_port': 5432}, 'log': lambda *a, **k: LOGS.append(a), 'threading': threading,
      'log_sparing': lambda key, words, level='warn', every=30: SPARE.append((key, words))}
exec(compile(defs('80_daemon.py', ['api_bind_failed'], cls='Daemon'), '80d', 'exec'), dd)
fake = types.SimpleNamespace(store=FakeStore(), stop_flag=Ev(5), api=FakeApi(3), _api_again=None)
dd['api_bind_failed'](fake, OSError(98, 'Address already in use'))
fake._api_again.join(2)
ok('R1c said as an error and as an event', LOGS and LOGS[0][-1] == 'error' and '5432' in LOGS[0][0] and
   fake.store.ev and fake.store.ev[0][2] == 'bad', (LOGS, fake.store.ev))
ok('R1c tried again until it listens (3 refused, the 4th listens), then said so', fake.api.tries == 4 and
   'listens' in fake.store.ev[-1][1], (fake.api.tries, fake.store.ev))
ok('R3-5 each failure said sparingly with its reason', len(SPARE) == 3 and 'Address already in use' in SPARE[0][1], SPARE)
fake = types.SimpleNamespace(store=FakeStore(), stop_flag=Ev(2), api=FakeApi(99, RuntimeError), _api_again=None)
dd['api_bind_failed'](fake, OSError(98, 'x'))
fake._api_again.join(2)
ok('R3-5 any trouble of a try caught (the thread goes on), stops when the daemon stops',
   fake.api.tries == 2 and not fake._api_again.is_alive(), fake.api.tries)


class SlowEv(object):
    def __init__(self):
        self.e = threading.Event()

    def wait(self, t):
        return self.e.wait(5)


fake = types.SimpleNamespace(store=FakeStore(), stop_flag=SlowEv(), api=FakeApi(99), _api_again=None)
dd['api_bind_failed'](fake, OSError(98, 'x'))
first = fake._api_again
dd['api_bind_failed'](fake, OSError(98, 'x'))
ok('R3-5 one thread trying, never two', fake._api_again is first)
fake.stop_flag.e.set()
first.join(2)
# ApiServer.start: the bind error its own; after the bind the port let go
api_src = src_of('90_api.py')
st_ = api_src[api_src.index('class ApiBindError(OSError):'):api_src.index('    def stop(self):', api_src.index('class ApiServer('))]
ok('R3-5 ApiServer.start: the bind as ApiBindError, server_close and httpd None on anything after',
   'raise ApiBindError(' in st_ and 'httpd.server_close()' in st_ and 'self.httpd = None\n            raise' in st_)


class FakeHttpd(object):
    closed = []

    def __init__(self, addr, h):
        if addr[1] == 1:
            raise OSError(98, 'Address already in use')

    def server_close(self):
        FakeHttpd.closed.append(1)

    def serve_forever(self):
        pass


def bad_token(make=False):
    raise OSError(13, 'Permission denied')


aa = {'CONFIG': {'api_port': 1}, 'ApiHttpServer': FakeHttpd, 'ApiHandler': None, 'api_token': bad_token,
      'threading': threading, 'log': lambda *a, **k: None, 'write_replacing': lambda *a, **k: None,
      'RUN_DIR': Path('/nonexistent')}
exec(compile(defs('90_api.py', ['ApiBindError', 'ApiServer']), '90api', 'exec'), aa)
srv_ = aa['ApiServer'](None)
try:
    srv_.start()
    ok('R3-5 a port taken: ApiBindError', False)
except aa['ApiBindError'] as e:
    ok('R3-5 a port taken: ApiBindError (an OSError still)', isinstance(e, OSError) and e.errno == 98, e)
aa['CONFIG']['api_port'] = 9861
try:
    srv_.start()
    ok('R3-5 the key not written: not a bind error', False)
except aa['ApiBindError']:
    ok('R3-5 the key not written: not a bind error', False)
except OSError:
    ok('R3-5 the key not written: not a bind error; the port let go, no half server',
       FakeHttpd.closed == [1] and srv_.httpd is None)
up_src = src_of('88_upgrade.py')
ok('R3-5 the upgrade\'s checks: the API not listening', "trouble.append('the API is not listening')" in up_src)

# ---- R2: "exactly the file" and high security ------------------------------------------------------
api = src_of('90_api.py')
i = api.index('def config_import(')
blk = api[i:api.index('\n@route', i)] if '\n@route' in api[i:] else api[i:]
j = blk.index("back = {k: FILE_CONFIG.get(k, DEFAULTS[k]) for k in drops}")
ok('R2 the drops gathered, high security asked, then dropped',
   blk.index('drops.append(k)') < j < blk.index('hisec_guard_settings(store, back)') <
   blk.index('for k in drops:\n                    store.drop_setting(k)'))
ok('R2 nothing dropped before the check', blk.count('store.drop_setting(k)') == 1)
# functional: hisec_guard_settings on what the drops leave
hz = {}
hs = src_of('88h_hisec.py')
ok('R2 hisec_guard_settings checks a setting going back to its default (in checked)',
   'if key in checked or any(' in hs)

# ---- R3: the events, a cursor for each node -----------------------------------------------------------
import sqlite3


class EvDB(object):
    def __init__(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, ts REAL, kind TEXT, level TEXT, '
                       'who TEXT, words TEXT, node TEXT)')

    def rows(self, q, a=()):
        return [dict(r) for r in self.c.execute(q, a).fetchall()]

    def put(self, i, node, words='x'):
        self.c.execute('INSERT INTO events (id, ts, kind, words, node) VALUES (?, ?, ?, ?, ?)',
                       (i, time.time(), 'k', words, node))


al = {'host_nodes': lambda st: ['otp1', 'otp2'], 'node_name': lambda: 'otp1',
      'fnum': lambda x, d=0.0: float(x or d)}
exec(compile(defs('88z_alerts.py', ['alert_event_cursors', 'alert_event_rows', 'alert_node_away']), '88z', 'exec'), al)
db = EvDB()
es = types.SimpleNamespace(db=db)
for i in (1, 3, 5):
    db.put(i, 'otp1')
st = {'event_id': 5}                    # the one cursor of a version before
rows = al['alert_event_rows'](es, st)
ok('R3 begun where the one cursor was', rows == [] and st['event_base'] == 5 and st['event_ids'] == {}
   and st['event_ids_at'] == 5, st)


def turn(st):
    rows = al['alert_event_rows'](es, st)
    for r in rows:                       # as _alerts_evaluate keeps them
        st['event_id'] = max(int(st.get('event_id') or 0), int(r['id']))
        n_ = str(r.get('node') or '')
        st['event_ids'][n_] = max(int(st['event_ids'].get(n_) or 0), int(r['id']))
        st['event_ids_at'] = st['event_id']
    return [r['id'] for r in rows]


db.put(7, 'otp1')
db.put(9, 'otp1')
ok('R3 this node\'s new ones', turn(st) == [7, 9], st)
db.put(6, 'otp2')                        # the other node's, come late by replication
db.put(8, 'otp2')
ok('R3 the other node\'s that came late: said, not lost', turn(st) == [6, 8], st)
ok('R3 nothing twice', turn(st) == [])
ok('R3 the one cursor stays the highest (a node of a version before reads it)', st['event_id'] == 9)
db.put(10, 'otp2')
db.put(11, 'otp1')
st['event_id'] = 11                      # a node of a version before mailed them meanwhile
ok('R3 the cursors begun again where a node of a version before left the one', turn(st) == [] and
   st['event_base'] == 11, st)
db.put(13, None)
db.put(12, 'otp2')
got = turn(st)
ok('R3 rows with no node read too, each node in the order of its ids', sorted(got) == [12, 13], got)
ok('R3 the state still JSON', json.loads(json.dumps(st)) == st)
az = src_of('88z_alerts.py')
ok('R3 the evaluation reads alert_event_rows; the cursors put back where the mail is held',
   'alert_event_rows(store, st)' in az and az.count("st['event_ids'] = last_events") == 2)

# ---- R6: a node away on purpose ---------------------------------------------------------------------
ROWS = {}
al.update(maintenance_row=lambda st, n: ROWS.get('maint:' + n) or {'on': False},
          net_job_active=lambda job: bool(job and job.get('state') == 'running'),
          _meta_json=lambda st, k: ROWS.get(k))
ok('R6 nobody away: not away', al['alert_node_away'](None, 'otp2', {}) == '')
ok('R6 planned away (a restart asked)', al['alert_node_away'](None, 'otp2', {'otp2': 'otp2 is restarting'}) ==
   'otp2 is restarting')
ROWS['maint:otp2'] = {'on': True}
ok('R6 in maintenance', 'maintenance' in al['alert_node_away'](None, 'otp2', {}))
ROWS.clear()
ROWS['net:job:otp2'] = {'state': 'running'}
ok('R6 a new network going in', 'network' in al['alert_node_away'](None, 'otp2', None))
ROWS.clear()
al['maintenance_row'] = lambda st, n: 1 / 0
ok('R6 a failing look: not away (said as before)', al['alert_node_away'](None, 'otp2', {}) == '')
ok('R6 the node\'s alert skipped while away', "if alert_node_away(store, n['name'], away):\n                    continue" in az)
ok('R6 node: held as the others, mails and traps', "ALERTS_HELD = ('repl', 'db:', 'vip:', 'node:')" in az and
   'held = ALERTS_HELD' in az and 'k.startswith(ALERTS_HELD)' in src_of('90s_snmp.py'))

# ---- R4 / R5: the backups' API ------------------------------------------------------------------------
rb = src_of('90b_rbackup_api.py')
i = rb.index('def _rbackup_download(h):')
dl = rb[i:rb.index('\n@route', i) if '\n@route' in rb[i:] else len(rb)]
ok('R4 the keys switch asked before a fetched one too', dl.index("if not CONFIG.get('admin_show_key'):") <
   dl.index('rb_fetch(') and dl.count("CONFIG.get('admin_show_key')") == 1)
i = rb.index('def _rb_restore_job(')
rj = rb[i:rb.index('\n@route', i)]
ok('R5 after a backup put back: the tokens bound, the names in one form',
   rj.index('rb_restore(store') < rj.index("BIND_STRICT['tokens'] = False") <
   rj.index('bind_tokens(store, trusted=True)') < rj.index('names_nfc_kept(store)') < rj.index('return got'))

# ---- R7: a node's own setting refused - said ---------------------------------------------------------
ok('R7 "there is no node" alone left out without a word', "if not str(e).startswith('there is no node'):" in blk and
   "said['settings left out: %s@%s (%s)' % (base, node, str(e)[:160])] += 1" in blk)
ok('R7 the save says that very words for a node not there', "raise BadSetting('there is no node %s' % node)" in dm)

# ==== round 3 ====================================================================================
# ---- P / Q: the cursors begun anew before they are kept; forgotten nodes, the rows with no node --
db = EvDB()
es = types.SimpleNamespace(db=db)
st = {'event_id': 20, 'event_ids': {'otp1': 9, 'otp2': 8}, 'event_ids_at': 9, 'event_base': 0}
al['alert_event_cursors'](st)
ok('P a node of a version before moved the cursor: begun anew where it left it',
   st['event_ids'] == {} and st['event_base'] == 20 and st['event_ids_at'] == 20, st)
az = src_of('88z_alerts.py')
i = az.index('    alert_event_cursors(st)\n    last_events = ')
ok('P the snapshot taken after the cursors are begun anew', i > 0)
st = {'event_id': 9, 'event_ids': {'otp1': 9, 'otp2': 8, 'old3': 3}, 'event_ids_at': 9, 'event_base': 0}
db.put(11, 'otp1')
db.put(12, 'old3')
got = al['alert_event_rows'](es, st)
ok('Q a node no longer of the cluster: its cursor dropped, its rows not read', 'old3' not in st['event_ids'] and
   [r['id'] for r in got] == [11], (st, got))
seen = []
real_rows = db.rows


def counting(q, a=()):
    seen.append(q)
    return real_rows(q, a)


db.rows = counting
al['alert_event_rows'](es, st)
ok('Q no row with no node: that bucket not read (one look only)',
   not any('node IS NULL OR node' in q and 'ORDER BY id LIMIT 200' in q for q in seen) and
   any('LIMIT 1' in q for q in seen), seen)
db.rows = real_rows
db.put(13, '')
got = al['alert_event_rows'](es, st)
ok('Q a row with no node: read', [r['id'] for r in got if not r['node']] == [13], got)
al['host_nodes'] = lambda st_: 1 / 0
st2 = {'event_id': 0, 'event_ids': {'otp9': 0}, 'event_ids_at': 0, 'event_base': 0}
al['alert_event_rows'](es, st2)
ok('Q the nodes not known (a failing look): nothing dropped', 'otp9' in st2['event_ids'])
al['host_nodes'] = lambda st_: ['otp1', 'otp2']
dbs = src_of('20_db.py')
ok('Q the index events(node, id), as the others (every engine, IF NOT EXISTS)',
   "'CREATE INDEX IF NOT EXISTS events_node_id ON events (node, id)'," in dbs)
con_ = sqlite3.connect(':memory:')
con_.execute('CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, level TEXT, who TEXT, words TEXT, node TEXT)')
con_.execute('CREATE INDEX IF NOT EXISTS events_node_id ON events (node, id)')
con_.execute('CREATE INDEX IF NOT EXISTS events_node_id ON events (node, id)')
plan_ = ' '.join(str(r[-1]) for r in con_.execute('EXPLAIN QUERY PLAN SELECT id FROM events WHERE node = ? AND id > ? '
                                                  'ORDER BY id LIMIT 200', ('x', 1)))
ok('Q sqlite: idempotent, and the cursor query uses it', 'events_node_id' in plan_, plan_)

# ---- R3-2: a node alone, install.sh failed, the new version answers: back in service -------------
EV, STEPS, MAINT = [], [], []
OTHERS = []
ug = {'__version__': '1.0.262', 'others_in_service': lambda st_: list(OTHERS), 'node_name': lambda: 'otp1',
      '_my_step': lambda st_, plan, **k: STEPS.append(k), 'log': lambda *a, **k: None,
      'maintenance_set': lambda st_, on, by='': MAINT.append(on)}
exec(compile(defs('88_upgrade.py', ['_upgrade_failed']), '88u', 'exec'), ug)


class USt(object):
    def add_event(self, *a, **k):
        EV.append(a)


plan = {'version': '1.0.262', 'by': 'admin', 'id': 'x'}
ug['_upgrade_failed'](USt(), plan, {'state': 'checking'}, 'install.sh ended with 1', own=False)
ok('R3-2 alone, install.sh only: back in service, the step failed, an event (the alert reads the step)',
   MAINT == [False] and STEPS[-1]['state'] == 'failed' and 'back in service' in STEPS[-1]['said'] and
   EV and EV[-1][2] == 'bad', (MAINT, STEPS, EV))
MAINT[:] = []
ug['_upgrade_failed'](USt(), plan, {'state': 'checking'}, 'RADIUS is not listening', own=True)
ok('R3-2 alone, the daemon\'s own checks failed: kept in maintenance (as before)', MAINT == [] and
   'left in maintenance' in STEPS[-1]['said'])
OTHERS[:] = ['otp2']
ug['_upgrade_failed'](USt(), plan, {'state': 'checking'}, 'install.sh ended with 1', own=False)
ok('R3-2 a cluster with another node answering: kept in maintenance (as before)', MAINT == [] and
   'left in maintenance' in STEPS[-1]['said'])
OTHERS[:] = []
ug['_upgrade_failed'](USt(), plan, {'state': 'checking', 'was_maint': True}, 'install.sh ended with 1', own=False)
ok('R3-2 in maintenance by hand before: left so', MAINT == [])
ug['_upgrade_failed'](USt(), plan, {'state': 'installing'}, 'it has not come back')
ok('R3-2 failed before the new version ran: back in service (as before)', MAINT == [False])
ok('R3-2 the checks pass own=', "_upgrade_failed(store, plan, turn, '; '.join(trouble), tail=got.get('tail'), own=own)"
   in up_src and 'own = bool(trouble)' in up_src)

# ---- R3-3: not below 1.0.259 with the balancer's own port ------------------------------------------
SET = {}
dg = {'__version__': '1.0.262', '_ver_tuple': lambda v: tuple(int(x) for x in str(v).split('.')[:3]),
      'CONFIG': {}, 'node_name': lambda: 'otp1', 'ha_nodes': lambda st_: [],
      'downgrade_db_floor': lambda st_: ('1.0.200', '1.0.200'), 'downgrade_root_floor': lambda: '1.0.200'}
exec(compile(defs('88d_downgrade.py', ['downgrade_why_not']), '88d', 'exec'), dg)
DSt = types.SimpleNamespace(settings_saved=lambda: dict(SET),
                            db=types.SimpleNamespace(rows=lambda q, a=(): []))
ok('R3-3 never set: nothing against it', dg['downgrade_why_not'](DSt, '1.0.258') == [])
SET['web_proxy_port'] = 8443
w = dg['downgrade_why_not'](DSt, '1.0.258')
ok('R3-3 set: below 1.0.259 refused, with what to do', len(w) == 1 and 'web_proxy_port=0' in w[0], w)
ok('R3-3 set: 1.0.259 and up taken', dg['downgrade_why_not'](DSt, '1.0.259') == [] and
   dg['downgrade_why_not'](DSt, '1.0.261') == [])
SET['web_proxy_port'] = 0
ok('R3-3 0 (taken away): nothing against it', dg['downgrade_why_not'](DSt, '1.0.258') == [])
SET.clear()
SET['web_proxy_port@otp2'] = 9443
ok('R3-3 a node\'s own value counts too', len(dg['downgrade_why_not'](DSt, '1.0.250')) == 1)
SET['web_proxy_port@otp2'] = 'junk'
ok('R3-3 a value of another shape: no crash', isinstance(dg['downgrade_why_not'](DSt, '1.0.250'), list))

# ---- R3-1 / R3-4: the patch of otp_web.py, on a copy ---------------------------------------------------
import subprocess
WORK = Path(tempfile.mkdtemp(prefix='t-ops-r3-'))
web_src = '/home/claude/build/out/otp-1.0.262/deploy/otp_web.py'
PATCH_W = '/tmp/claude-0/h262/r3_ops_otpweb_patch.py'
cp = WORK / 'otp_web.py'
cp.write_text(open(web_src).read())
r_ = subprocess.run([sys.executable, '-I', PATCH_W, str(cp)], capture_output=True, text=True)
ok('R3-1 the otp_web.py patch applies', r_.returncode == 0 and ('patched' in r_.stdout or 'already' in r_.stdout), r_.stderr)
r2_ = subprocess.run([sys.executable, '-I', PATCH_W, str(cp)], capture_output=True, text=True)
ok('R3-1 ...and again: nothing twice', r2_.returncode == 0 and 'already' in r2_.stdout)
W = cp.read_text()
ok('R3-1 the patched helper compiles', compile(W, 'otp_web', 'exec') is not None)


def wdefs(names):
    tree = ast.parse(W)
    lines = W.splitlines(True)
    out = [''.join(lines[n.lineno - 1:n.end_lineno]) for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(out) == len(names), names
    return '\n\n'.join(out)


class Refused(Exception):
    pass


SEM = {'mode': 'Enforcing', 'ports': {('http_port_t', 'tcp'): [(80, 81), (443, 443), (8443, 8443)],
                                      ('http_cache_port_t', 'tcp'): [(8080, 8080)]},
       'add': (0, ''), 'asked': []}


def fake_se_run(cmd, timeout=120, light=False, data=None):
    SEM['asked'].append(cmd)
    return types.SimpleNamespace(returncode=SEM['add'][0], stderr=SEM['add'][1], stdout='')


ww = {'Refused': Refused, 'se_mode': lambda: SEM['mode'], 'se_ports': lambda: SEM['ports'],
      '_se_run': fake_se_run, 'time': time, 're': re,
      'SE_PORT_TYPES': ('radius_port_t', 'postgresql_port_t', 'ssh_port_t', 'http_port_t'),
      'SE_BOOLEANS': ('httpd_can_network_connect', 'authlogin_radius')}
exec(compile(wdefs(['se_port_has', 'lbport_selinux', 'lbport_listening', 'se_want_checked']), 'w', 'exec'), ww)
ls = ww['lbport_selinux']
ok('R3-1 a port http_port_t has: nothing asked', ls(8443) == '' and SEM['asked'] == [])
ok('R3-1 a port http_cache_port_t has: nothing asked', ls(8080) == '' and SEM['asked'] == [])
ok('R3-1 a port of no type: semanage port -a -t http_port_t', 'nginx listen' in ls(9443) and
   SEM['asked'][-1][:7] == ['semanage', 'port', '-a', '-t', 'http_port_t', '-p', 'tcp'])
SEM['add'] = (1, 'ValueError: Port tcp/9443 already defined')
try:
    ls(9443)
    ok('R3-1 enforcing, another service\'s port: refused', False)
except Refused as e:
    ok('R3-1 enforcing, another service\'s port: refused, clearly', 'another service' in str(e) and
       'web_proxy_port' in str(e), e)
SEM['mode'] = 'Permissive'
ok('R3-1 permissive: said, not refused', 'permissive' in ls(9443))
SEM['add'] = (0, '')
for m in ('Disabled', 'absent'):
    SEM['mode'] = m
    n0 = len(SEM['asked'])
    ok('R3-1 SELinux %s: nothing done' % m, ls(9443) == '' and len(SEM['asked']) == n0)
SEM['mode'] = 'Enforcing'
ww['se_ports'] = lambda: None
try:
    ls(9443)
    ok('R3-1 enforcing without semanage: refused', False)
except Refused as e:
    ok('R3-1 enforcing without semanage: refused, says what to install', 'policycoreutils' in str(e))
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(('127.0.0.1', 0))
srv.listen(1)
lport = srv.getsockname()[1]
ok('R3-1 a port listened on: seen', ww['lbport_listening'](lport, 0))
srv.close()
t0 = time.time()
ok('R3-1 a port nobody listens on: not seen, within the wait', not ww['lbport_listening'](lport, 0.5) and
   time.time() - t0 < 3)
ngx = W[W.index('def nginx_part(r, last):'):W.index('\ndef vip_part(')]
ok('R3-1 labelled before the file is written',
   ngx.index('w = lbport_selinux(int(lp[\'port\']))') < ngx.index('write_root(NGINX_LB, text, 0o644)'))
ok('R3-1 the reload checked: refused (files put back) when it fails',
   "if rl.returncode != 0:" in ngx and 'nginx could not be reloaded' in ngx)
ok('R3-1 the port looked at after the reload: put back, read again, refused',
   ngx.index('if lb_look and not lbport_listening(lb_look):') < ngx.index("does not listen on the balancer") and
   'put_back(snap)\n                subprocess.run([\'systemctl\', \'reload\', \'nginx\']' in ngx)
ok('R3-1 a file of 1.0.259-261 not listened on: labelled now', 'elif not NO_SERVICES and not lbport_listening(' in ngx)
# R3-4: a port type it does not know - left out, said
wc = ww['se_want_checked']
left = []
b_, p_ = wc({'booleans': [{'name': 'httpd_can_network_connect'}],
             'ports': [{'port': 9443, 'proto': 'tcp', 'type': 'futuristic_port_t', 'why': 'x'},
                       {'port': 15432, 'proto': 'tcp', 'type': 'postgresql_port_t', 'why': 'y'}]}, left)
ok('R3-4 helper: a type it does not know left out and said, the rest kept',
   len(b_) == 1 and [x['type'] for x in p_] == ['postgresql_port_t'] and len(left) == 1 and
   'futuristic_port_t' in left[0], (b_, p_, left))
for bad in ({'port': 1, 'proto': 'tcp', 'type': 'x; rm -rf /'}, {'port': 1, 'proto': 'icmp', 'type': 'a_port_t'}, 'junk'):
    try:
        wc({'ports': [bad]}, [])
        ok('R3-4 helper: what is not a port type at all still refused (%r)' % (bad,), False)
    except Refused:
        ok('R3-4 helper: what is not a port type at all still refused (%r)' % (bad,), True)
try:
    wc({'ports': [{'port': 1, 'proto': 'tcp', 'type': 'futuristic_port_t'}]})
    ok('R3-4 helper: without a list (an old caller) refused as before', False)
except Refused:
    ok('R3-4 helper: without a list (an old caller) refused as before', True)
ok('R3-4 helper: se_do says what was left out, se_check shows it',
   'said = list(left)' in W and "'left_out': left}" in W)

# ---- R3-1: the patch of install.sh, on a copy -----------------------------------------------------------
PATCH_I = '/tmp/claude-0/h262/r3_ops_install_patch.py'
ic = WORK / 'install.sh'
ic.write_text(open('/home/claude/build/out/otp-1.0.262/install.sh').read())
r_ = subprocess.run([sys.executable, '-I', PATCH_I, str(ic)], capture_output=True, text=True)
ok('R3-1 the install.sh patch applies, bash -n', r_.returncode == 0 and
   subprocess.run(['bash', '-n', str(ic)]).returncode == 0, r_.stderr)
ok('R3-1 install.sh: again, nothing twice', 'already' in subprocess.run([sys.executable, '-I', PATCH_I, str(ic)],
                                                                         capture_output=True, text=True).stdout)
I = ic.read_text()
ok('R3-1 install.sh: labelled before the restart, a failed restart said (not the end of the upgrade)',
   I.index('        lbport_selinux_label\n        run systemctl restart nginx || warn ') > 0)
fn = I[I.index('lbport_selinux_label() {'):I.index('\n}\n', I.index('lbport_selinux_label() {')) + 3]
BIN = WORK / 'bin'
BIN.mkdir()
(BIN / 'getenforce').write_text('#!/bin/sh\necho "${FAKE_MODE:-Enforcing}"\n')
(BIN / 'semanage').write_text('#!/bin/sh\nif [ "$2" = "-l" ]; then printf "http_cache_port_t   tcp  8080, 10001-10010\\n'
                              'http_port_t   tcp  80, 81, 443, 8443\\n"; exit 0; fi\necho "$@" >> "$SEM_LOG"; exit ${SEM_RC:-0}\n')
for f_ in BIN.iterdir():
    f_.chmod(0o755)
conf = WORK / 'otp_lbport.conf'


def run_fn(port_line, mode='Enforcing', rc=0, with_file=True):
    log_ = WORK / 'sem.log'
    if log_.exists():
        log_.unlink()
    if with_file:
        conf.write_text('server {\n    %s\n    listen [::]:9443 ssl;\n' % port_line)
    elif conf.exists():
        conf.unlink()
    script = ('set -Eeuo pipefail\nDRY_RUN=""\nrun() { "$@"; }\ngood() { echo "GOOD $*"; }\nwarn() { echo "WARN $*"; }\n' +
              fn.replace('/etc/nginx/conf.d/otp_lbport.conf', str(conf)) + '\nlbport_selinux_label\necho END\n')
    env = dict(os.environ, PATH='%s:/usr/bin:/bin' % BIN, FAKE_MODE=mode, SEM_RC=str(rc), SEM_LOG=str(log_))
    got = subprocess.run(['bash', '-c', script], capture_output=True, text=True, env=env)
    return got.stdout, (log_.read_text() if log_.exists() else '')


o_, l_ = run_fn('listen 9443 ssl proxy_protocol;')
ok('R3-1 install.sh: a port of no type labelled http_port_t', 'port -a -t http_port_t -p tcp 9443' in l_ and
   'GOOD' in o_ and 'END' in o_, (o_, l_))
o_, l_ = run_fn('listen 8443 ssl;')
ok('R3-1 install.sh: one http_port_t has: left alone', l_ == '' and 'END' in o_, (o_, l_))
o_, l_ = run_fn('listen 10005 ssl;')
ok('R3-1 install.sh: one of a range of http_cache_port_t: left alone', l_ == '' and 'END' in o_, (o_, l_))
o_, l_ = run_fn('listen 9443 ssl;', mode='Disabled')
ok('R3-1 install.sh: SELinux disabled: nothing', l_ == '' and 'END' in o_)
o_, l_ = run_fn('listen 9443 ssl;', with_file=False)
ok('R3-1 install.sh: no balancer port: nothing', l_ == '' and 'END' in o_)
o_, l_ = run_fn('listen 9443 ssl;', rc=1)
ok('R3-1 install.sh: semanage refusing: a warning, the install goes on', 'WARN' in o_ and 'END' in o_, o_)

print('%d/%d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
