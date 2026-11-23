"""t_fix.py - 1.0.321: the command line asks before it takes a local user away or makes a new balancer
key; --api says a file is the pages' and reads the query as they do; a directory's certificate check
put back; the console's port follows the way; the pages' decimal mark, one ask at a time, dates in the
page's language. The built otp.py loaded as a module over SQLite; the page's scripts read by node.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, json, os, shutil, subprocess, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.321'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r321_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx321', 'api_port': 29951}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 cli_sure: --yes goes, no terminal refused
class A:
    yes = False


sys.stdin = open(os.devnull)
try:
    m.cli_sure(A(), 'take x away'); ok('cli_sure: no terminal, no --yes - refused', False)
except SystemExit as e:
    ok('cli_sure: no terminal, no --yes - refused', 'nothing was changed' in str(e), e)
a = A(); a.yes = True
m.cli_sure(a, 'take x away'); ok('cli_sure: --yes goes', True)
src = inspect.getsource(m)
ok('--local-user drop asks through cli_sure', "cli_sure(args, 'take %s away on %s%s'" in src and
   "input('take %s away on %s%s? type yes: '" not in src)
ok('--sso-key asks through cli_sure', "cli_sure(args, 'a new key: the one the balancer sends now is no longer taken')" in src)

# ==== 2 --api: a file is the pages'
class Dm:
    store = st


for meth, path in [(k[0], k[1]) for k in m.ROUTES if k[1] in ('/api/db/download',)]:
    try:
        m.cli_api(Dm(), 'command line', meth, path, None, {})
        ok('--api %s %s refused in words' % (meth, path), False)
    except SystemExit as e:
        ok('--api %s %s refused in words' % (meth, path), 'from the pages only' in str(e) or 'otp:' in str(e), e)
    except Exception as e:                              # noqa: BLE001
        ok('--api %s %s refused in words' % (meth, path), False, repr(e))
h = m.CliApiHandler(Dm(), 'x')
for f in ('send_file', 'send_bytes', '_send_open_file', 'body_to_file'):
    try:
        getattr(h, f)('a', 'b'); ok('handler %s refuses' % f, False)
    except m.ApiError as e:
        ok('handler %s refuses' % f, e.status == 400)
ok('--api reads the query with parse_qs', 'qs = {k: v[-1] for k, v in urllib.parse.parse_qs(query).items()}' in src)

# ==== 3 a directory's certificate check back on
p = m.build_parser() if hasattr(m, 'build_parser') else None
ok('--dir-cert-check in the parser', "'--dir-cert-check', choices=('on', 'off')" in src)
ok('--dir-cert-check read', "int(args.dir_cert_check == 'on') if args.dir_cert_check" in src)
ok('--local-user help names aging', 'drop-home or aging' in src)

# ==== 4 the console's form
cs = inspect.getsource(m.Console.directory_edit) if hasattr(m, 'Console') else src
ok('console: the old way\'s port dropped with a new way', "port == {'ldaps': '636'}.get(was_tls, '389')" in cs)
ok('console: the certificate check asked', "'--dir-cert-check', got.get('verify') or 'on'" in cs)

# ==== 5 the pages
W = V + '/web/assets/'
core, hload, adm = (open(W + f).read() for f in ('core.js', 'hload.js', 'admin.js'))
js = r"""
var I18N = {on: true, code: process.argv[2]};
%s
console.log(JSON.stringify([numFixed(1.25, 1), numFixed(12.3456, 3), numFixed(2, 0)]));
""" % core[core.index('function numLang()'):core.index('/** A number read back off the page')]
open(TOP + '/n.js', 'w').write(js)
cz = subprocess.run(['node', TOP + '/n.js', 'cs-CZ'], capture_output=True, text=True)
en = subprocess.run(['node', TOP + '/n.js', 'en-US'], capture_output=True, text=True)
ok('numFixed: Czech comma', json.loads(cz.stdout or 'null') in (['1,3', '12,346', '2'], ['1,2', '12,346', '2']), cz.stdout + cz.stderr)
ok('numFixed: English point', json.loads(en.stdout or 'null') in (['1.3', '12.346', '2'], ['1.2', '12.346', '2']), en.stdout + en.stderr)
ok('hload: rates and GHz with numFixed', "numFixed(n / 1024" in hload and "numFixed(m / 1000, 1) + ' GHz'" in hload and
   '(c.mhz / 1000).toFixed(1)' not in hload)
ok('time pane with numFixed', "numFixed(t.freq, 3)" in adm and "numFixed(a / 1000, 2) + ' s'" in adm)
ok('rbackup try with numFixed', "'It works (' + numFixed(x.secs || 0, 1) + ' s)'" in adm)
ok('proxy try: one ask, its own end', 'PX.poll = mine = setInterval(look, 1000);' in adm and 'if (PX.poll === mine)' in adm)
ok('isemon try: one ask', "        if (asking || over) return;\n        asking = true;\n        api('isemon'" in adm)
ok('net / power: one look at a time', 'if (NET.asking) return;' in adm and 'if (PW.asking) return;' in adm)
ok('dates in the page\'s language', 'toLocaleDateString(numLang()) : \'–\'; }' in adm and
   "'Looked at ' + new Date(n.at * 1000).toLocaleString(numLang())" in adm and
   'new Date().toLocaleDateString(numLang())' in core)
for f in ('core.js', 'hload.js', 'admin.js'):
    r = subprocess.run(['node', '--check', W + f], capture_output=True, text=True)
    ok('node --check ' + f, r.returncode == 0, r.stderr)

print('ALL %d / %d' % (sum(R), len(R)))
