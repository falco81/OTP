# t_round7.py VERSION - joining a cluster (1.0.213): the node being joined let in by the firewall
# before the join, the firewall that really runs opened and said as it is, a cluster of one shared
# database written as one (ha_mode shared), what a failed connection means, a half joined node.
import os, sys, json, time, tempfile, subprocess, importlib.util, io, contextlib
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.213'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r7-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r7a'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
me = otp.node_name()
st.set_meta('fw:conf', json.dumps({'set': True, 'on': True, 'rules': [], 'off': []}))

# ---- the node being joined: let in before the join ---------------------------------------------
peers = lambda: [x for x in otp.fw_auto(st, me) if x['key'] == 'cluster']
ok('alone: no "The other node" in the firewall', not peers())
otp.ha_joining_set(['192.0.2.36'], 't', 'test')
ok('a node being joined: its address among the cluster\'s', '192.0.2.36' in otp.cluster_addresses(st, me))
got = peers()
ok('... "The other node" in the firewall at once, before the cluster is one (%s)' % (got and got[0]['why']),
   got and any(r['source'] == '192.0.2.36' for r in got[0]['rules']) and 'being made' in got[0]['why'])
info = json.load(open(otp.HA_JOINING_FILE))
info['until'] = time.time() - 1
open(otp.HA_JOINING_FILE, 'w').write(json.dumps(info))
ok('... a day later, gone by itself', not otp.ha_joining() and not peers())
otp.ha_joining_done()

# ---- what a connection that failed means --------------------------------------------------------
w = otp.pg_reach_why
ok('"Connection refused" said as nothing listening / a firewall refusing',
   'listens on its own machine' in w('could not connect to server: Connection refused', '192.0.2.35', 5432))
ok('"No route to host" said as a firewall', 'firewall' in w('No route to host'))
ok('"no pg_hba.conf entry" said as pg_hba.conf', 'pg_hba.conf' in w('FATAL: no pg_hba.conf entry for host'))
ok('"password authentication failed" said as an older bundle', 'make it again' in w('password authentication failed'))

# ---- a cluster of one shared database written as one -------------------------------------------
otp.ha_mark_shared('192.0.2.37')
cf = json.load(open(D + '/config.json'))
ok('the first node of a shared cluster: ha_mode shared, the second node as ha_peer (%s)' % cf.get('ha_mode'),
   cf.get('ha_mode') == 'shared' and cf.get('ha_peer') == '192.0.2.37')
ok('... and let in by the firewall for the join', '192.0.2.37' in otp.ha_joining())
otp.ha_joining_done()
json.dump({'db_engine': 'sqlite', 'node_name': 'r7a'}, open(D + '/config.json', 'w'))
otp.load_config(saved=None)
real_try = otp.db_try
otp.db_try = lambda c: {'reached': True, 'rows': 5}
data = {'db': {'db_engine': 'postgres', 'db_host': '192.0.2.35', 'db_port': 5432, 'db_name': 'otp',
               'db_user': 'otp', 'db_password': 'x' * 20},
        'key': otp.sealing_key().hex(), 'cluster': 'c', 'peer': {'name': 'r7b', 'address': '192.0.2.35'}}
try:
    otp.ha_join(data, 'r7c', by='t')
finally:
    otp.db_try = real_try
cf = json.load(open(D + '/config.json'))
ok('the second node of a shared cluster joined: ha_mode shared, the first as ha_peer (%s %s)'
   % (cf.get('ha_mode'), cf.get('ha_peer')), cf.get('ha_mode') == 'shared' and cf.get('ha_peer') == '192.0.2.35')
ok('... the first node let in by its firewall', '192.0.2.35' in otp.ha_joining())
otp.ha_joining_done()

# ---- the command line's firewall: the one that runs, checked, said as it is -------------------------
B = tempfile.mkdtemp(prefix='otp-r7-bin-')
LOG = B + '/calls'
open(B + '/iptables', 'w').write('''#!/bin/bash
echo "iptables $*" >> %s
case "$*" in
  "-n -L OTP-IN") exit 0;;
  -C*) grep -q -- "-I OTP-IN 1" %s && exit 0 || exit 1;;
  *) exit 0;;
esac
''' % (LOG, LOG))
open(B + '/firewall-cmd', 'w').write('#!/bin/bash\necho "firewall-cmd $*" >> %s\n[ "$1" = --state ] && { echo "not running"; exit 252; }\nexit 0\n' % LOG)
os.chmod(B + '/iptables', 0o755); os.chmod(B + '/firewall-cmd', 0o755)
os.environ['PATH'] = B + ':' + os.environ['PATH']
pal = otp.Palette(False) if hasattr(otp, 'Palette') else type('P', (), {
    'ok_line': staticmethod(lambda t: '✔ ' + t), 'bad_line': staticmethod(lambda t: '✘ ' + t),
    'warn_line': staticmethod(lambda t: '! ' + t)})()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    good = otp.firewall_peer('192.0.2.36', pal, 5432)
out = buf.getvalue()
calls = open(LOG).read()
ok('otp\'s own firewall: the other node put into OTP-IN, checked (%s)' % out.strip().replace('\n', ' | '),
   good and '-I OTP-IN 1 -s 192.0.2.36/32' in calls and 'OTP-IN' in out)
ok('... firewalld installed and not running: not said to let anybody in', 'firewalld lets' not in out
   and '--add-rich-rule' not in calls)
otp.ha_joining_done()

# ---- half joined, and the root helper's new step -------------------------------------------------
otp.sealing_key_path().with_name('secrets.key.before-join').write_text('x')
ok('a half joined node said so, with what to run', 'half joined' in otp.half_joined_words(
    'FATAL: password authentication failed for user "otp"'))
ok('... an ordinary failure not', otp.half_joined_words('could not connect: timeout') == '')
spec = importlib.util.spec_from_file_location('otp_web_r7', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
ok('root: PostgreSQL may be let listen on the network for the second node',
   W.pgtls_checked({'id': 'abcdef0123', 'do': 'listen', 'port': 5432, 'db': 'otp', 'user': 'otp'})['do'] == 'listen')
src = open(V + '/otp.py').read()
J = open(V + '/web/assets/admin.js').read()
ok('the pages: the bundle asks for the second node and makes this node ready, step by step',
   "steps = ha_bundle_prepare(h.store" in src and "action: 'bundle_check'" in J)
ok('the pages: the join tried before it is made (Check it)', "if act == 'join_check':" in src and "send('join_check')" in J)
ok('pg_hba.conf has this node\'s own address (1.0.212) - still', "own_address=''" in src)
print('ALL %d / %d' % (sum(R), len(R)))
