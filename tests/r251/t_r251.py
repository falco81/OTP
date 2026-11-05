#!/usr/bin/env python3
"""1.0.251: a nested value of another shape read as none; a version's rows not taken in while a
node of a version before was heard from within a day; asks for nodes gone taken away; refused
rows of meta gone since no longer listed; the (i) of every setting of the password policy.

Run as root: python3 t_r251.py VERSION"""
import os, sys, json, time, tempfile, atexit, shutil, re, inspect

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.251'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


TOP = tempfile.mkdtemp(prefix='otp-r251-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
os.environ['OTP_STATE'] = TOP + '/dstate'; os.makedirs(TOP + '/dstate')
open(TOP + '/dstate/guard.json', 'w').write('{}')
sys.path.insert(0, V); sys.argv = ['otp']
import otp
otp.CONFIG.update({'db_engine': 'sqlite', 'node_name': 'nodea'})
store = otp.Storage(otp.open_db()); store.db.make_tables(); otp.sealing_key(make=True)
import pathlib; otp.WEB_DIR = pathlib.Path(TOP + '/web'); otp.WEB_DIR.mkdir()
SRC = open(V + '/otp.py').read()


def raw(k, v):
    store.db.run('DELETE FROM meta WHERE k = ?', (k,))
    store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, v))


# ---- nested values -------------------------------------------------------------------------------------
ok('odict: an object kept', hasattr(otp, 'odict') and otp.odict({'a': 1}) == {'a': 1})
ok('odict: a string, a list, none, a number read as {}',
   all(otp.odict(x) == {} for x in ('text', [1], None, 5, True)))
left = re.findall(r"\([A-Za-z_][A-Za-z0-9_\.]*(?:\[[^\]\[]+\])?\.get\('[A-Za-z0-9_]+'\) or \{\}\)", SRC)
ok('no "(x.get(k) or {})" left in otp', not left, left[:5])
# ---- the version's rows: every node heard from within a day ----------------------------------------------
otp.CONFIG['ha_mode'] = 'shared'
otp.CONFIG['db_guard'] = 1
otp.DBGUARD['refused'].clear()


def beat(name, ver, ago=0):
    store.set_meta('node:' + name, json.dumps({'at': time.time() - ago, 'version': ver, 'address': '127.0.0.9'}))


beat('nodea', otp.__version__)
beat('nodeb', '1.0.247', ago=600)
nb = [n for n in otp.ha_nodes(store) if n['name'] == 'nodeb'][0]
ok('the node of a version before: not alive (10 min)', not nb.get('alive'), nb)
otp.dbguard_adopt_tick(store)
ok('...still counted: the version\'s rows not taken in', '1.0.248' not in otp.DBGUARD['adopted'] and
   '1.0.248' in otp.DBGUARD['behind'], (otp.DBGUARD['adopted'], otp.DBGUARD['behind']))
raw('rbackup:targets', json.dumps([{'id': 't1', 'kind': 'folder', 'path': '/x'}]))
ok('...its unsigned row of the version acted on once back',
   otp.dbguard_ok(store.db, 'm', 'rbackup:targets', store.get_meta('rbackup:targets')))
beat('nodeb', '1.0.247', ago=2 * 86400)
otp.dbguard_adopt_tick(store)
ok('a node not heard from for two days: no longer counted, the version taken in',
   '1.0.248' in otp.DBGUARD['adopted'], otp.DBGUARD['adopted'])
ok('the switch on counts a node of a day too',
   'DBGUARD_PEER_DAY_S' in inspect.getsource(otp.Daemon.dbguard_switch) if hasattr(otp, 'Daemon') else
   'DBGUARD_PEER_DAY_S' in SRC.split('def dbguard_switch', 1)[1][:1500])
store.db.run("DELETE FROM meta WHERE k = 'node:nodeb'")

# ---- asks for nodes gone ---------------------------------------------------------------------------------
beat('nodeb', otp.__version__)
ask = json.dumps([{'id': 'a1', 'do': 'password', 'name': 'novak', 'hash': 'sealed:2:xxx', 'at': time.time()}])
store.set_meta('host:users:want:nodex@@nodea', ask)      # nodex: not of the cluster
store.set_meta('host:users:want:nodeb@@nodea', ask)      # nodeb: of it
store.set_meta('host:sshkeys:want:nodex@@nodea', '[]')
raw('host:users:want:nodex@@nodeb', ask)                 # another node's row: not this node's to take
otp.NODE_ASK_GONE.clear()
n1 = otp.node_asks_of_gone_tidy(store)
ok('a node missing from the list: nothing taken away at once', n1 == 0 and
   store.get_meta('host:users:want:nodex@@nodea'), n1)
otp.NODE_ASK_GONE_S = 0
n2 = otp.node_asks_of_gone_tidy(store)
have = sorted(r['k'] for r in store.db.rows("SELECT k FROM meta WHERE k LIKE 'host:%:want:%'"))
ok('...still missing: its own asks for it taken away, the others left', n2 == 2 and
   have == ['host:users:want:nodeb@@nodea', 'host:users:want:nodex@@nodeb'], (n2, have))
ok('...the going of a signed row signed',
   otp.dbguard_ok(store.db, 'm', 'host:users:want:nodex@@nodea', None, quiet=True))
otp.CONFIG['ha_mode'] = ''
store.set_meta('rbackup:now:nodex@@nodea', json.dumps({'id': 'r1', 'at': time.time()}))
otp.node_asks_of_gone_tidy(store); otp.node_asks_of_gone_tidy(store)
ok('one node alone: an ask of a cluster before (a backup put back) taken away too',
   store.get_meta('rbackup:now:nodex@@nodea') is None)
store.set_meta('host:users:want:nodea@@nodea', ask)
otp.node_asks_of_gone_tidy(store)
ok('...an ask of itself left', store.get_meta('host:users:want:nodea@@nodea') is not None)
store.db.run("DELETE FROM meta WHERE k LIKE 'host:users:want:%'")
otp.CONFIG['ha_mode'] = 'shared'
otp.NODE_ASK_GONE_S = 3600

# a list of the nodes that cannot be read: nothing taken away
real = otp.host_nodes
otp.host_nodes = lambda s: (_ for _ in ()).throw(RuntimeError('db down'))
store.set_meta('host:users:want:nodey@@nodea', ask)
otp.NODE_ASK_GONE_S = 0
ok('the list of nodes not read: nothing taken away', otp.node_asks_of_gone_tidy(store) == 0 and
   store.get_meta('host:users:want:nodey@@nodea'))
otp.host_nodes = lambda s: []
ok('...an empty list (not even this node): nothing', otp.node_asks_of_gone_tidy(store) == 0 and
   store.get_meta('host:users:want:nodey@@nodea'))
otp.host_nodes = real
otp.NODE_ASK_GONE_S = 3600
store.db.run("DELETE FROM meta WHERE k LIKE 'host:users:want:%'")

# ---- refused rows gone since -----------------------------------------------------------------------------
otp.DBGUARD['refused'].clear()
raw('console:want:nodeb', '{"users": ["x"]}')
ok('an unsigned row of meta refused', not otp.dbguard_ok(store.db, 'm', 'console:want:nodeb', '{"users": ["x"]}'))
otp.dbguard_ok(store.db, 's', 'snmp', '"on"')
ok('...listed, with a setting refused', len(otp.DBGUARD['refused']) == 2, otp.DBGUARD['refused'])
otp.dbguard_refused_tidy(store)
ok('...still there: still listed', len(otp.DBGUARD['refused']) == 2)
store.db.run("DELETE FROM meta WHERE k = 'console:want:nodeb'")
otp.dbguard_adopt_tick(store)
kinds = sorted(e['kind'] for e in otp.DBGUARD['refused'].values())
ok('the row gone: no longer listed, the setting still is', kinds == ['s'], otp.DBGUARD['refused'])

# ---- the (i) of the password policy ----------------------------------------------------------------------
js = open(V + '/web/assets/admin.js').read()
m = re.search(r'PWP_HELP\s*=\s*\{(.*?)\n\s*\};', js, re.S)
keys = re.findall(r"^\s*'?([a-z_]+)'?\s*:", m.group(1), re.M) if m else []
ok('a word for every setting of the policy', m and len(keys) >= 16, keys)
for k in ('managed', 'minlen', 'minclass', 'maxrepeat', 'difok', 'dictcheck', 'usercheck', 'remember',
          'deny', 'unlock_time', 'max_days', 'min_days', 'warn_days'):
    ok('...%s explained' % k, k in keys)
ok('the (i) does not toggle what it sits on', 'stopPropagation' in js.split('function pwpInfo', 1)[-1][:1500])
cs = V + '/web/lang/cs.json'
if os.path.exists(cs):
    srcs = {v['source'] for v in json.load(open(cs))['strings'].values()}
    import importlib.util
    spec = importlib.util.spec_from_file_location('cs_261', '/home/claude/i18n/cs_261.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    ok('every word of the (i) in Czech', all(k in srcs for k in mod.S261), [k[:40] for k in mod.S261 if k not in srcs])

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
