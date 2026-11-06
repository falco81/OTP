"""t_cli.py - 1.0.255: the command line, the console, the installer and the root helper.
C1 the console's deletes pass --yes; C2 the installer's nginx patch of the admin block twice, on
copies with 4g and with 32m (nginx_upload_guard's); C3 --acme-order takes the lease and the DNS
scope; C4 --rbackup-now's guard, verify-after and --rbackup-all; C6 the UDP probe; C7 no secret
printed by install.sh; N4 an authorized_keys longer than read not rewritten; N5 chrony lines
split on any whitespace."""
import os, sys, re, ast, json, time, socket, errno, secrets, shutil, stat, subprocess, tempfile, types
PARTS = '/home/claude/build/parts'
OUT = '/home/claude/build/out/otp-%s' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.255')
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


def funcs(path, names, g):
    src = open(path).read()
    tree = ast.parse(src)
    lines = src.split('\n')
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            exec('\n'.join(lines[start:node.end_lineno]), g)
    for n in names:
        if n not in g:
            raise SystemExit('FAIL no %s in %s' % (n, path))


cli = open(os.path.join(PARTS, '95_cli.py')).read()
con = open(os.path.join(PARTS, '96_console.py')).read()
inst = open(os.path.join(OUT, 'install.sh')).read()
web_path = os.path.join(OUT, 'deploy', 'otp_web.py')
web = open(web_path).read()

# ---- C1 ---------------------------------------------------------------------------------
for flag in ('--del-user', '--del-client', '--del-realm', '--del-directory', '--ssh-token-del'):
    calls = re.findall(r"self\.act\('%s'[^\n]*" % re.escape(flag), con)
    ok('C1 console %s passes --yes' % flag, calls and all("'--yes'" in c for c in calls), calls)
for py in ('95_cli.py', '96_console.py'):
    r = subprocess.run([sys.executable, '-m', 'py_compile', os.path.join(PARTS, py)],
                       capture_output=True, text=True)
    ok('py_compile %s' % py, r.returncode == 0, r.stderr)

# ---- C2 ---------------------------------------------------------------------------------
r = subprocess.run(['bash', '-n', os.path.join(OUT, 'install.sh')], capture_output=True, text=True)
ok('C2/C7 bash -n install.sh', r.returncode == 0, r.stderr)
m = re.search(r'python3 - "\$NGINX_CONF" <<\'PY\'\n(.*?)\nPY\n', inst, re.S)
patch = m.group(1) if m else ''
ok('C2 the nginx patch found', 'location = /admin/' in patch and 'client_max_body_size' in patch)
work = tempfile.mkdtemp(prefix='t_cli-')
try:
    shipped = open(os.path.join(OUT, 'deploy', 'nginx-otp.conf')).read()
    pfile = os.path.join(work, 'patch.py')
    open(pfile, 'w').write(patch)

    def admin_block(text):
        b = re.search(r'(?ms)^([ \t]*)location = /admin/ \{\n(.*?)^\1\}\n', text)
        return b.group(2) if b else ''

    # An old conf, from before 1.0.10: no size in the admin block - put in once.
    old = re.sub(r'(?m)^\s*(client_max_body_size 4g|client_body_timeout +\S+|'
                 r'fastcgi_request_buffering +\S+);\n', '', shipped)
    for name, text in (('4g', shipped), ('32m', shipped.replace('client_max_body_size 4g;',
                                                                 'client_max_body_size 32m;')),
                       ('none', old)):
        f = os.path.join(work, 'otp-%s.conf' % name)
        open(f, 'w').write(text)
        for run in (1, 2):
            r = subprocess.run([sys.executable, '-I', pfile, f], capture_output=True, text=True)
            got = open(f).read()
            n = admin_block(got).count('client_max_body_size')
            ok('C2 %s, run %d: the patch ran' % (name, run), r.returncode == 0, r.stderr)
            ok('C2 %s, run %d: one client_max_body_size in the admin block' % (name, run), n == 1, n)
            ok('C2 %s, run %d: one client_body_timeout in the admin block' % (name, run),
               admin_block(got).count('client_body_timeout') == 1)
        if name == '32m':
            ok('C2 32m stays 32m', 'client_max_body_size 32m;' in admin_block(got)
               and '4g' not in admin_block(got))
        if name == 'none':
            ok('C2 an old conf gets 4g', 'client_max_body_size 4g;' in admin_block(got))
finally:
    shutil.rmtree(work, ignore_errors=True)

# ---- C3 ---------------------------------------------------------------------------------
class Store:
    def __init__(self):
        self.meta = {}

    def get_meta(self, k):
        return self.meta.get(k)

    def set_meta(self, k, v):
        self.meta[k] = v

    def drop_meta(self, k):
        self.meta.pop(k, None)


class Scope:
    on = False

    def __enter__(self):
        Scope.was = Scope.on; Scope.on = True

    def __exit__(self, *a):
        Scope.on = Scope.was


seen = {}


def fake_order(store, t, name, by, say):
    seen['scope'] = Scope.on
    seen['lease'] = json.loads(store.get_meta('acme:busy:%s' % t) or '{}')
    if name == 'boom':
        raise ValueError('boom')
    return 'made'


def json_obj(text, kind=dict):
    try:
        v = json.loads(text) if text else None
    except ValueError:
        return None
    return v if isinstance(v, kind) else None


g = {'json': json, 'time': time, 'secrets': secrets, 'json_obj': json_obj,
     'fnum': lambda x, d=0.0: float(x or d), 'node_name': lambda: 'n1',
     'acme_dns_scope': Scope, 'acme_order': fake_order}
funcs(os.path.join(PARTS, '95_cli.py'), ['cli_acme_order_one'], g)
st = Store()
got = g['cli_acme_order_one'](st, 'node:n1', 'otp.example', 'cli', print)
ok('C3 ordered inside acme_dns_scope', got == 'made' and seen.get('scope') is True, seen)
ok('C3 the lease held while ordering', seen['lease'].get('node') == 'n1' and seen['lease'].get('until', 0) > time.time())
ok('C3 the lease dropped after', 'acme:busy:node:n1' not in st.meta)
ok('C3 scope left after', Scope.on is False)
st.meta['acme:busy:node:n1'] = json.dumps({'node': 'n2', 'until': time.time() + 600})
try:
    g['cli_acme_order_one'](st, 'node:n1', 'otp.example', 'cli', print)
    ok('C3 refused while n2 holds it', False)
except ValueError as e:
    ok('C3 refused while n2 holds it', 'n2' in str(e))
ok('C3 the other node\'s lease kept', json.loads(st.meta['acme:busy:node:n1'])['node'] == 'n2')
st.meta['acme:busy:node:n1'] = json.dumps({'node': 'n1', 'until': time.time() + 600})
try:
    g['cli_acme_order_one'](st, 'node:n1', 'otp.example', 'cli', print)
    ok('C3 refused while this node\'s daemon holds it', False)
except ValueError:
    ok('C3 refused while this node\'s daemon holds it', True)
st.meta['acme:busy:node:n1'] = json.dumps({'node': 'n2', 'until': time.time() - 5})
g['cli_acme_order_one'](st, 'node:n1', 'otp.example', 'cli', print)
ok('C3 a lapsed lease taken over', 'acme:busy:node:n1' not in st.meta)
st.meta['acme:busy:node:n1'] = 'not json'
try:
    g['cli_acme_order_one'](st, 'node:n1', 'boom', 'cli', print)
except ValueError:
    pass
ok('C3 a failed order drops its lease', 'acme:busy:node:n1' not in st.meta)
ok('C3 --acme-order uses it', "cli_acme_order_one(store, t, name, who," in cli)

# ---- C4 ---------------------------------------------------------------------------------
from pathlib import Path
sd = Path(tempfile.mkdtemp(prefix='t_cli-state-'))
try:
    g = {'STATE_DIR': sd, 'time': time}
    funcs(os.path.join(PARTS, '95_cli.py'), ['cli_rbackup_busy'], g)
    ok('C4 nothing made: not busy', g['cli_rbackup_busy']() == '')
    (sd / 'otp-putback-x').mkdir()
    ok('C4 another kind of work: not busy', g['cli_rbackup_busy']() == '')
    (sd / 'otp-rbackup-abc').mkdir()
    ok('C4 a backup being made: busy', g['cli_rbackup_busy']() == 'otp-rbackup-abc')
    old_t = time.time() - 7 * 3600
    os.utime(str(sd / 'otp-rbackup-abc'), (old_t, old_t))
    ok('C4 one left hours ago: not busy', g['cli_rbackup_busy']() == '')
    (sd / 'otp-verify-q').mkdir()
    ok('C4 a try being made: busy', g['cli_rbackup_busy']() == 'otp-verify-q')
finally:
    shutil.rmtree(str(sd), ignore_errors=True)
blk = cli[cli.index('    if args.rbackup_now:'):cli.index('    if args.restore_bundle:')]
ok('C4 verify after, as the pages', "CONFIG.get('rbackup_verify') == 'after'" in blk and 'rb_verify(store' in blk)
ok('C4 the guard asked, --yes over it', 'cli_rbackup_busy()' in blk and 'args.yes' in blk)
ok('C4 --rbackup-all asks the others', 'rb_now_ask_others(store' in blk and 'args.rbackup_all' in blk)
ok('C4 --help says this node only', "this node only, unless" in cli and "'--rbackup-all'" in cli)

# ---- C6 ---------------------------------------------------------------------------------
# No port is bound here: a socket module of the test's own says what the machine would.
class FakeSock:
    made = []
    answers = {}

    def __init__(self, fam, kind):
        self.fam, self.opts = fam, {}
        FakeSock.made.append(self)

    def setsockopt(self, lvl, opt, v):
        self.opts[opt] = v

    def bind(self, addr):
        e = FakeSock.answers.get(addr[0])
        if e:
            raise OSError(e, os.strerror(e))

    def close(self):
        pass


fs = types.SimpleNamespace(AF_INET=socket.AF_INET, AF_INET6=socket.AF_INET6, SOCK_DGRAM=socket.SOCK_DGRAM,
                           IPPROTO_IPV6=socket.IPPROTO_IPV6, IPV6_V6ONLY=socket.IPV6_V6ONLY, socket=FakeSock)
g = {'socket': fs, 'errno': errno}
funcs(os.path.join(PARTS, '95_cli.py'), ['cli_udp_taken'], g)
taken = g['cli_udp_taken']
FakeSock.answers = {'0.0.0.0': errno.EADDRINUSE, '10.0.0.9': errno.EADDRNOTAVAIL, '::': errno.EADDRINUSE,
                    '1.2.3.4': errno.EACCES}
ok('C6 IPv4 port in use: taken', taken('', 1812) is True and FakeSock.made[-1].fam == socket.AF_INET)
ok('C6 IPv4 port free: not taken', taken('127.0.0.1', 1812) is False)
ok('C6 an address not here: unknown, not taken', taken('10.0.0.9', 1812) is None)
ok('C6 refused for another reason: unknown', taken('1.2.3.4', 1812) is None)
ok('C6 IPv6 bind probed as IPv6, both families', taken('::', 1812) is True
   and FakeSock.made[-1].fam == socket.AF_INET6 and FakeSock.made[-1].opts.get(socket.IPV6_V6ONLY) == 0)
ok('C6 IPv6 port free: not taken', taken('fd00::1', 1812) is False and FakeSock.made[-1].fam == socket.AF_INET6)
ok('C6 --status uses it', "cli_udp_taken(CONFIG.get('radius_bind'), port)" in cli
   and 'socket.socket(socket.AF_INET, socket.SOCK_DGRAM)' not in cli[cli.index('    if args.status or args.check:'):][:3000])

# ---- C7 ---------------------------------------------------------------------------------
step = inst[inst.index('step "A RADIUS client for testing from this machine"'):inst.index('step "The service"')]
said = [l for l in step.split('\n') if re.match(r'\s*(good|note|warn|echo|printf)\b', l)]
ok('C7 the test secret not printed', said and not any('TEST_SECRET' in l or 'OTP_SECRET' in l for l in said), said)
ok('C7 radtest suggested without a secret', any('otp --radtest NAME -' in l for l in said), said)

# ---- N4, N5 -----------------------------------------------------------------------------
class Refused(Exception):
    pass


d = tempfile.mkdtemp(prefix='t_cli-ssh-')
try:
    ak = os.path.join(d, '.ssh', 'authorized_keys')
    g = {'os': os, 'stat': stat, 'tempfile': tempfile, 'shutil': shutil, 'subprocess': subprocess,
         'Refused': Refused, 'ROOT_AUTH': ak, 'NO_SERVICES': True}
    src = web
    lines = src.split('\n')
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'AUTH_READ_MAX' for t in node.targets):
            exec('\n'.join(lines[node.lineno - 1:node.end_lineno]), g)
    funcs(web_path, ['auth_lines', 'auth_write', 'auth_too_long', 'ntp_conf_text'], g)
    g['AUTH_READ_MAX'] = 4096                      # a small limit, for the test
    g['auth_write'](['ssh-ed25519 AAAA one'])
    ok('N4 a new file written', open(ak).read() == 'ssh-ed25519 AAAA one\n')
    g['auth_write'](g['auth_lines']() + ['ssh-ed25519 AAAA two'])
    ok('N4 a short file written again', 'two' in open(ak).read())
    big = 'ssh-ed25519 AAAA one\n' + '#' * 5000 + '\nssh-ed25519 AAAA last\n'
    open(ak, 'w').write(big)
    read = g['auth_lines']()
    ok('N4 only a part read', 'ssh-ed25519 AAAA last' not in read)
    try:
        g['auth_write'](read + ['ssh-ed25519 AAAA new'])
        ok('N4 a longer file not rewritten', False)
    except Refused as e:
        ok('N4 a longer file not rewritten', 'longer' in str(e))
    ok('N4 its end kept', open(ak).read() == big)
    ok('N4 the user\'s writer asks it too', web.count('auth_too_long(path, st.st_size)') == 1
       and web.count('auth_too_long(ROOT_AUTH, st.st_size)') == 1)
    g.update(NTP_BEGIN='# ---- otp begin', NTP_END='# ---- otp end',
             NTP_KEYS=('server', 'pool', 'peer', 'makestep', 'allow', 'minsources', 'maxdistance',
                       'sourcedir'))
    conf = 'server\tntp1.example iburst\npool  2.pool.example\n\ndriftfile /var/lib/chrony/drift\n'
    n = {'manage': True, 'servers': [{'host': 'a.example', 'pool': False, 'iburst': True,
                                      'prefer': False, 'nts': False}],
         'peers': [], 'allow': [], 'makestep': [1.0, 3], 'minsources': 1}
    try:
        out = g['ntp_conf_text'](conf, n)
        ok('N5 a tab-separated server line put aside', '#otp# server\tntp1.example iburst' in out, out)
        ok('N5 two spaces too', '#otp# pool  2.pool.example' in out, out)
        ok('N5 an empty line kept', '\n\n' in out or out.count('\n') >= 4)
        back = g['ntp_conf_text'](out, dict(n, manage=False))
        ok('N5 put back as it was', back == conf, repr(back))
    except KeyError as e:
        print('note: ntp_conf_text needs %s - checked by text only' % e)
        ok('N5 split on any whitespace', "(l.split() or [''])[0] in NTP_KEYS" in web)
    ok('N5 ntp_read too', "(l.split() or [''])[0] in ('server', 'pool', 'peer')" in web)
finally:
    shutil.rmtree(d, ignore_errors=True)
r = subprocess.run([sys.executable, '-m', 'py_compile', web_path], capture_output=True, text=True)
ok('py_compile otp_web.py', r.returncode == 0, r.stderr)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
