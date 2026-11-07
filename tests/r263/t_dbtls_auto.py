"""t_dbtls_auto.py - 1.0.263: the daemon's connection to its own database goes back to TLS by
itself after a rescue, and the database's own renewal stays out while the link is set on (also
while its steps run). The built otp.py as a module over a store of meta rows; dbtls_probe,
dbtls_switch and _dbtls_server_cert replaced by fakes.

    python3 t_dbtls_auto.py 1.0.263
"""
import importlib.util, json, os, sys, tempfile, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.263'
OUT = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


tmp = tempfile.mkdtemp(prefix='t_r263_')
os.environ.setdefault('OTP_CONFIG', tmp + '/otp.conf')
os.environ.setdefault('OTP_STATE_DIR', tmp + '/state')
spec = importlib.util.spec_from_file_location('otpmod', OUT + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.argv = ['otp']
spec.loader.exec_module(m)


class DB:
    def __init__(self, meta):
        self.meta = meta

    def run(self, sql, args=()):
        if sql.startswith('DELETE FROM meta WHERE k = ?'):
            self.meta.pop(args[0], None)
        return 1


class Store:
    def __init__(self):
        self.meta = {}
        self.db = DB(self.meta)
        self.events = []

    def get_meta(self, k):
        return self.meta.get(k)

    def set_meta(self, k, v):
        self.meta[k] = v

    def add_event(self, *a, **kw):
        self.events.append(a)


class Daemon:
    def __init__(self):
        self.store = Store()


PROBE = {'ok': False}
SWITCHED = []
MADE = []
m.dbtls_probe = lambda mode, ca: {'ok': PROBE['ok'], 'said': 'x'}
m.dbtls_switch = lambda d, mode, ca, by: SWITCHED.append((mode, ca, by))
m.dbtls_kind = lambda: 'local'
m.node_name = lambda: 'otp1'
m.dbtls_publish = lambda d, force=False: None
d = Daemon()
k = 'dbtls:rescued:otp1'
ca = str(m.HA_CA_FILE)
m.CONFIG['db_tls'] = ''
d.store.set_meta(k, json.dumps({'at': time.time() - 700, 'was': 'verify-full', 'ca': ca, 'why': 'x'}))
m._dbtls_again(d)
ok('rescued: not moved while the probe fails', not SWITCHED)
PROBE['ok'] = True
m._dbtls_again(d)
ok('... nor again within 10 minutes', not SWITCHED)
r = json.loads(d.store.meta[k]); r['tried'] = time.time() - 700; d.store.set_meta(k, json.dumps(r))
m._dbtls_again(d)
ok('... moved back once the probe goes', SWITCHED == [('verify-full', ca, 'otp (it works with TLS again)')], SWITCHED)
SWITCHED.clear()
m.CONFIG['db_tls'] = 'require'
d.store.set_meta(k, json.dumps({'at': 0, 'was': 'verify-full', 'ca': ca}))
m._dbtls_again(d)
ok('set by hand since: the row dropped, no move', k not in d.store.meta and not SWITCHED)
m.CONFIG['db_tls'] = ''
d.store.set_meta(k, json.dumps({'at': 0, 'was': 'verify-full', 'ca': '/tmp/evil.pem'}))
m._dbtls_again(d)
ok('a row naming another authority file: dropped, no move', k not in d.store.meta and not SWITCHED)

# Gap 2: the link set on - the database's own renewal stays out
m.dbtls_publish = lambda d, force=False: None
m._dbtls_server_cert = lambda store, by: MADE.append(by)
m.hatls_names = lambda: ['otp1', '127.0.0.1']
m.hatls_state = lambda store: {'step': 'names'}          # the link renewing: not done
m.hatls_want = lambda store: {'at': 1}
d2 = Daemon()
d2.store.set_meta('dbtls:server:otp1', json.dumps({'cert_end': time.time() - 86400, 'names': ['otp1']}))
m.CONFIG.update(ha_mode='replicated', ha_tls='verify-full')
m.dbtls_tick(d2)
time.sleep(0.3)
ok('link set on (its steps running): an old dbtls:server row does not renew', not MADE, MADE)
m.CONFIG.update(ha_tls='')
m.dbtls_tick(d2)
time.sleep(0.5)
ok('link off: it renews', MADE == ['otp (renewed)'], MADE)
m.CONFIG.update(ha_tls='verify-full')
m.hatls_want = lambda store: {'at': 1, 'off': True}
ok('link being switched off: not "on"', not m._dbtls_link_on(d2.store))

# The rescue's row read back for the page
src = open(OUT + '/otp.py').read()
ok('the rescue writes its row, the page reads it', "daemon.store.set_meta(_dbtls_rescued_key(), json.dumps(" in src
   and "kept = _meta_json(store, _dbtls_rescued_key())" in src)
ok('a successful switch drops the row', "daemon.store.db.run('DELETE FROM meta WHERE k = ?', (_dbtls_rescued_key(),))" in src)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
