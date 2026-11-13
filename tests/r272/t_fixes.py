# t_fixes.py VERSION - the fixes of 1.0.272 (bug hunt round 3), on otp.py loaded as a module (a private state
# folder - the live installation is never touched):
#  - unlimited() within unlimited(): the limit put back only by the outer one;
#  - the RADIUS log's short columns at 190 (MariaDB's VARCHAR), the reason at 1000;
#  - a node renamed carries its database's certificate rows;
#  - nginx's certificate found drifted is asked again (past the retry gate);
#  - the cluster's authority made by one node only, for isemon too (hatls_ca_ensure);
#  - the root helper takes a request of up to 4 MB and 20000 firewall rules;
#  - the pages: idle sign-out shared across tabs, pollers wait for the last answer, popups checked.
import atexit, importlib.util, json, os, re, shutil, sys, tempfile, threading, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.272'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t272-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx272', 'api_port': 29973}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
SRC = open(V + '/otp.py').read()
WEB = open(V + '/deploy/otp_web.py').read()
JS = open(V + '/web/assets/admin.js').read()


# -- unlimited() nested
class Stub(object):
    engine = 'postgres'
    statement_s = 120

    def __init__(self):
        self.lane = m._Lane()
        self.said = []

    @property
    def lock(self):
        return self.lane.lock

    def _lane(self):
        return self.lane

    def value(self, *a):
        return 1

    def run(self, sql, *a):
        self.said.append(str(sql))


st = Stub()
with m.Db.unlimited(st):
    with m.Db.unlimited(st):
        pass
    st.said.append('INDEX')
with_limit = [x for x in st.said if x.startswith('SET statement_timeout = 120000')]
ok('unlimited() within unlimited(): no limit put back before the outer one ends',
   st.said.index('INDEX') < st.said.index(with_limit[0]) if with_limit else False, st.said)
ok('...put back once, at the end', len(with_limit) == 1 and st.said[-1].startswith('SET statement_timeout = 120000'), st.said)
ok('...the depth back to 0', st.lane.unl == 0)

# -- the RADIUS log's columns
store = m.Storage(m.open_db())
rid = store.radius_add({'ts': time.time(), 'username': 'u' * 240, 'client': 'c' * 300, 'reason': 'r' * 1500,
                        'result': 'reject', 'attrs': 'a' * 3000})
row = store.db.row('SELECT username, client, reason, attrs FROM radius_log ORDER BY id DESC LIMIT 1')
ok('the RADIUS log: a 240-letter name kept at 190 (MariaDB\'s column)', len(row['username']) == 190, len(row['username']))
ok('...the client at 190, the reason at 1000, the attributes whole',
   len(row['client']) == 190 and len(row['reason']) == 1000 and len(row['attrs']) == 3000)

# -- a node renamed: its database certificate
store.set_meta('dbtls:server:oldn', json.dumps({'end': time.time() + 9e6, 'names': ['oldn']}))
store.set_meta('dbtls:rescued:oldn', '1')
said = m.node_carry(store, 'oldn', 'newn', 'test')
ok('a node renamed: its database\'s certificate row carried',
   store.get_meta('dbtls:server:newn') and store.get_meta('dbtls:server:oldn') is None, said)
ok('...its rescued mark too', store.get_meta('dbtls:rescued:newn') == '1' and store.get_meta('dbtls:rescued:oldn') is None)

# -- the authority made by one node only
CA = {'cas': []}
MADE = []
m.hatls_ca = lambda s: CA
m.hatls_ca_make = lambda s, by: (MADE.append(by), CA.update(cas=[{'end': time.time() + 9e7}]))
m.CONFIG['ha_mode'] = 'replicated'
m.ha_lead = lambda s: False
try:
    m.hatls_ca_ensure(store, 'x', wait=0)
    ok('the authority, not the lead: waits for the other node', False)
except ValueError as e:
    ok('the authority, not the lead: waits for the other node, never makes one', MADE == [] and 'come over' in str(e))
m.ha_lead = lambda s: True
m.hatls_ca_ensure(store, 'x', wait=0)
ok('...the lead makes it', MADE == ['x'])
m.CONFIG.pop('ha_mode', None)
isem = SRC[SRC.index('def isemon_client_cert('):SRC.index('\ndef ', SRC.index('def isemon_client_cert(') + 10)]
ok('isemon\'s client certificate: hatls_ca_ensure, no bare hatls_ca_make', 'hatls_ca_ensure(' in isem and 'hatls_ca_make(' not in isem)

# -- drift
wt = SRC[SRC.index('def web_tick('):SRC.index('\ndef ', SRC.index('def web_tick(') + 10)]
ok('nginx\'s certificate drifted: asked again past the retry gate', 'drifted = True' in wt and 'if not drifted and' in wt)

# -- the root helper
ok('the root helper takes a request of up to 4 MB', "read_req('request.taken', 4 << 20)" in WEB)
ok('...and 20000 firewall rules', 'len(rules) > 20000' in WEB)

# -- the pages
ok('idle sign-out: the last activity shared across tabs', "otp.active" in JS)
ok('the pollers of Web, VIP and Firewall wait for their last answer',
   all("apiLatestOut('%s')" % k in JS for k in ('web', 'vip', 'fw')))
ok('a slow answer not written into another popup (Try a sign-in, the HA bundle)', JS.count('modalStill(tk') >= 2)
print('ALL %d / %d' % (sum(R), len(R)))
