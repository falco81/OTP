"""t_fix.py - 1.0.315: the alerts, the outgoing mail and the sign-ins of the pages on the command line
and in the console; an option alone, where nobody types, no longer starts the daemon. The parts loaded
as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import ast, contextlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = sys.argv[1] if len(sys.argv) > 1 else '1.0.315'
BUILD = '/home/claude/build'
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r315_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in re.findall(r'parts/\S+\.py', cat):
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read() + '\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx315', 'api_port': 29945}, open(D + '/config.json', 'w'))
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
import pwd
_svc = pwd.getpwnam('otp')
os.chmod(TOP, 0o755)
for _d, _ds, _fs in os.walk(TOP):
    for _x in [_d] + [os.path.join(_d, f) for f in _fs]:
        os.chown(_x, _svc.pw_uid, _svc.pw_gid)


def cli(*argv):
    # A process of its own: the command line becomes the otp account before it acts.
    p = subprocess.run([sys.executable, '-I', TOP + '/otp.py'] + list(argv) + ['--no-color'],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, env=os.environ)
    return p.returncode, p.stdout, p.stderr


def cj(*argv):
    rc, o, e = cli(*(list(argv) + ['--json']))
    try:
        return rc, json.loads(o)
    except ValueError:
        return rc, (o, e)


# ==== 1 the outgoing mail
now = time.time()
recs = [('1795000000000-aaaaaaaa', 'failed', 'one@example.com'), ('1795000000001-bbbbbbbb', 'sent', 'two@example.com'),
        ('1795000000002-cccccccc', 'waiting', 'three@example.com')]
for qid, state, to in recs:
    st.set_meta(m.MAILQ_PREFIX + qid, json.dumps({'qid': qid, 'created': now - 60, 'node': 'fx315', 'kind': 'test',
                                                  'to': [to], 'subject': 'hello ' + state, 'state': state,
                                                  'tries': 1, 'history': [{'at': now - 50, 'said': 'x'}]}))
rc, got = cj('--mailq')
ok('1 --mailq: all three', rc == 0 and isinstance(got, dict) and got.get('total') == 3, got)
rc, got = cj('--mailq', 'failed')
ok('1 --mailq failed: the one', rc == 0 and [r['qid'] for r in got['rows']] == ['1795000000000-aaaaaaaa'], got)
rc, got = cj('--mailq', 'open')
ok('1 --mailq open: waiting and failed', rc == 0 and got.get('total') == 2, got)
rc, o, e = cli('--mailq')
ok('1 as a table, with the counts', rc == 0 and 'hello sent' in o and 'failed 1' in o and 'sent 1' in o, o + e)
rc, got = cj('--mailq-one', '1795000000002-cccccccc')
ok('1 --mailq-one: its history', rc == 0 and got.get('state') == 'waiting' and got.get('history'), got)
rc, o, e = cli('--mailq', 'retry-all')
ok('1 retry-all while sending is off: said so', rc != 0 and 'switched off' in e, (rc, o, e))
rc, o, e = cli('--mailq', 'drop-sent')
ok('1 drop-sent without --yes (no terminal): refused, nothing changed', rc != 0 and '--yes' in e and
   m.mailq_read(st, '1795000000001-bbbbbbbb')[0], (rc, o, e))
rc, o, e = cli('--mailq', 'drop-sent', '--yes')
ok('1 drop-sent --yes: the sent one gone', rc == 0 and not m.mailq_read(st, '1795000000001-bbbbbbbb')[0]
   and m.mailq_read(st, '1795000000000-aaaaaaaa')[0], (rc, o, e))
rc, o, e = cli('--mailq-drop', '1795000000000-aaaaaaaa', '--yes')
ok('1 --mailq-drop ID: that one gone', rc == 0 and not m.mailq_read(st, '1795000000000-aaaaaaaa')[0], (rc, o, e))
rc, o, e = cli('--mailq-drop', 'nonsense', '--yes')
ok('1 a wrong id: refused', rc != 0 and 'ids' in e, (rc, o, e))

# ==== 2 the sign-ins
sid = st.session_new('admin', 'eva', 'fulladmin', '10.1.2.3', 8)
rc, got = cj('--sessions')
ok('2 --sessions: listed', rc == 0 and any(r.get('name') == 'eva' and r.get('ip') == '10.1.2.3' for r in got), got)
rc, o, e = cli('--sessions')
ok('2 as a table', rc == 0 and 'eva' in o and '10.1.2.3' in o, o + e)
ident = [r['id'] for r in got if r.get('name') == 'eva'][0]
rc, o, e = cli('--session-end', str(ident))
ok('2 --session-end without --yes: refused', rc != 0 and st.sessions(), (rc, o, e))
rc, o, e = cli('--session-end', str(ident), '--yes')
ok('2 --session-end --yes: ended, written down', rc == 0 and not [r for r in st.sessions() if r['id'] == ident]
   and any('ended the sign-in of eva' in str(r) for r in st.db.rows('SELECT * FROM events')), (rc, o, e))
rc, o, e = cli('--session-end', str(ident), '--yes')
ok('2 again: ended already', rc != 0 and 'ended already' in e, (rc, o, e))

# ==== 3 the alerts
rc, got = cj('--alerts')
ok('3 --alerts --json: the view', isinstance(got, dict) and 'problems' in got and 'mail' in got, got)
bad = any(p.get('level') == 'bad' for p in got.get('problems') or [])
ok('3 exit 1 only when something is bad', rc == (1 if bad else 0), (rc, bad))
rc, o, e = cli('--alerts')
ok('3 said', ('nothing is wrong now' in o or 'LEVEL' in o.upper()) and 'switched off' in o, o + e)
rc, o, e = cli('--alerts', 'test')
ok('3 test with no address: said so', rc != 0 and 'no address' in e, (rc, o, e))

# ==== 4 an option alone, where nobody types: never the daemon
otp = TOP + '/otp.py'
env = dict(os.environ)
env.pop('INVOCATION_ID', None)
for opt in (['--pending'], ['--yes'], ['--limit', '5'], ['--role', 'readonly']):
    p = subprocess.run([sys.executable, '-I', otp] + opt, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30, env=env)
    ok('4 otp %s from a script: refused at once, no daemon' % ' '.join(opt),
       p.returncode == 2 and 'alone asks nothing' in p.stderr and not os.path.exists(D + '/otp.lock'),
       (p.returncode, p.stderr[-300:], p.stdout[-200:]))
src = open(BUILD + '/parts/95_cli.py').read()
ok('4 bare otp from a script: still the daemon (as it always was)',
   "alone asks nothing" in src and src.index("alone asks nothing") < src.index("            return run_daemon()\n        args.status = True"))

# ==== 5 the console: every call is one the command line takes
p = m.build_parser()
tree = ast.parse(open(BUILD + '/parts/96_console.py').read())
calls, badc = 0, []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
            'act', 'out', 'show', 'show_live', 'cmd') and node.args and isinstance(node.args[0], ast.Constant) \
            and str(node.args[0].value).startswith('--'):
        names = [a.value for a in node.args if isinstance(a, ast.Constant) and str(a.value).startswith('--')]
        known = {o for a in p._actions for o in a.option_strings}
        calls += 1
        badc += [(node.lineno, n) for n in names if n not in known]
ok('5 the console\'s %d calls: every option known' % calls, calls > 100 and not badc, badc)
con = open(BUILD + '/parts/96_console.py').read()
ok('5 the console has the alerts, the outgoing mail and the sign-ins',
   all(x in con for x in ("'Alerts: what is wrong now'", "'Outgoing mail', mailq", "self.act('--session-end', which, '--yes')")))
# ==== 6 an alert's words cut where a word ends
c = m._al_cut
ok('6 short: as it is', c('a b c', 600) == 'a b c')
long_ = ('word ' * 200).strip()
got = c(long_, 600)
ok('6 long: no longer than asked, ends on a whole word, said cut', len(got) <= 600 and got.endswith('word…'), got[-20:])
fw = [e for e in m.AFTER if e.get('id') == 'firewall-by-hand']
w = (fw[0].get('why') or '') if fw else ''
ok('6 the firewall one (%d characters, over the old 300) said whole' % len(w), 300 < len(w) <= 600 and c(w, 600) == w, len(w))
src = open(BUILD + '/parts/88z_alerts.py').read()
ok('6 the after items through it, 600', "_al_cut(str(words.get('why') or it.get('why') or ''), 600)" in src)

# ==== 7 the firewall and who may reach the pages, from the command line
rc, got = cj('--firewall')
ok('7 --firewall --json: as the pages have it', rc == 0 and isinstance(got, dict) and 'conf' in got and 'access' in got, got)
rc, o, e = cli('--firewall')
ok('7 said: the rules and who may reach each page', rc == 0 and "otp's firewall rules" in o and 'the administration pages:' in o, o + e)
rc, o, e = cli('--web-access', 'admin=10.0.0.0/8')
ok('7 --web-access without --yes: refused, nothing changed', rc != 0 and not st.get_meta('web:access'), (rc, o, e))
rc, o, e = cli('--web-access', 'admin=10.0.0.0/8,192.168.1.0/24', '--yes')
acc = json.loads(st.get_meta('web:access') or '{}')
ok('7 --web-access admin=NETS --yes: kept, the others everybody', rc == 0 and acc.get('admin', {}).get('from') ==
   ['10.0.0.0/8', '192.168.1.0/24'] and not acc['admin']['any'] and acc.get('portal', {}).get('any'), (rc, o, e, acc))
ok('7 ...written down', any('set who may reach the pages' in str(r) for r in st.db.rows('SELECT * FROM events')))
rc, o, e = cli('--web-access', 'portal=192.168.5.0/24', '--yes')
acc = json.loads(st.get_meta('web:access') or '{}')
ok('7 another kind: the first as it was', rc == 0 and acc['admin']['from'] == ['10.0.0.0/8', '192.168.1.0/24']
   and acc['portal']['from'] == ['192.168.5.0/24'], acc)
rc, o, e = cli('--web-access', 'admin=any', '--yes')
acc = json.loads(st.get_meta('web:access') or '{}')
ok('7 admin=any: everybody again', rc == 0 and acc['admin']['any'], acc)
rc, o, e = cli('--web-access', 'admin=not-a-net', '--yes')
ok('7 a wrong network: refused', rc != 0 and 'not an address' in e, (rc, e))
rc, o, e = cli('--web-access', 'nonsense=any', '--yes')
ok('7 a wrong kind: refused', rc != 0 and 'KIND' in e, (rc, e))
rc, o, e = cli('--firewall', 'on')
ok('7 --firewall on', rc == 0 and json.loads(st.get_meta('fw:conf'))['on'], (rc, o, e))
rc, o, e = cli('--firewall', 'off')
ok('7 --firewall off without --yes: refused', rc != 0 and json.loads(st.get_meta('fw:conf'))['on'], (rc, o, e))
rc, o, e = cli('--firewall', 'off', '--yes')
ok('7 --firewall off --yes: taken away', rc == 0 and not json.loads(st.get_meta('fw:conf'))['on'], (rc, o, e))
ok('7 the console: the way back in', all(x in con for x in ("self.act('--web-access', 'admin=any', '--yes')",
                                                            "self.act('--firewall', 'off', '--yes')")))

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
