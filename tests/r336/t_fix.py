"""t_fix.py - 1.0.336: a node's value from its config.json can be set back to the cluster's; each
node's settings drawn from what was just saved; an empty number named; Czech words of the saves.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.336'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r336_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'otp1', 'api_port': 29958, 'debug': True}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 an empty number named
try:
    m.check_setting('code_ttl_s', '')
    e = None
except m.BadSetting as x:
    e = str(x)
ok('an empty number names its setting', e and e.startswith('code_ttl_s: '), e)
try:
    m.check_setting('code_ttl_s', 'x')
    e = None
except m.BadSetting as x:
    e = str(x)
ok('not a number: named once', e and e.startswith('code_ttl_s: ') and not e.startswith('code_ttl_s: code_ttl_s'), e)
ok('a right one as before', m.check_setting('code_ttl_s', '120') == 120)

# ==== 2 node_file_has
k = sorted(m.NODE_KEYS)[0]
st.set_meta('node:otp2', json.dumps({'at': time.time(), 'own_file': [k]}))
ok('another node: as its heartbeat says', m.node_file_has(st, 'otp2', k) and not m.node_file_has(st, 'otp2', 'zz'))
ok('a node not heard from: no', not m.node_file_has(st, 'otp3', k))
ok('this node: its own file', m.node_file_has(st, 'otp1', 'debug') == ('debug' in (m.FILE_KEYS or ())))
src = open(V + '/otp.py').read()
ok('save_settings keeps the row where the node has it from its file',
   'if v == shared and not node_file_has(self.store, node, k):' in src)

# ==== 3 the pane drawn from what was saved
js = open(V + '/web/assets/admin.js').read()
ok('the save noted', 'NODE_SAVED[s.key] = Date.now() / 1000;' in js)
ok('the heartbeat older than the save not believed', '!(NODE_SAVED[k] && Number(nd.at || 0) < NODE_SAVED[k])' in js)

# ==== 4 Czech
cs = json.load(open(V + '/web/lang/cs.json'))
pats = {v['source']: v['text'] for v in cs['patterns'].values()}
for w in ('{0} setting(s) saved.', 'a test went to {0} a moment ago - wait half a minute',
          'ten tests went to {0} in the last hour - that is enough', 'it could not be sent: {0}'):
    ok('in Czech: ' + w, pats.get(w), w)
print('ALL %d / %d' % (sum(R), len(R)))
