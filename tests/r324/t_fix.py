"""t_fix.py - 1.0.324: a realm switched off answers nobody under "*"; the balancers' networks 256 at most, all
put in; the names looked for on from where the last look stopped. The built otp.py over SQLite.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else "1.0.324"
V = "/home/claude/build/out/otp-%s" % VER
R = []


def ok(n, c, m=""):
    R.append(bool(c))
    print(("ok  " if c else "FAIL") + " " + n + ("" if c else " " + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix="t_r324_")
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + "/state"
os.makedirs(D + "/run")
json.dump({"db_engine": "sqlite", "node_name": "fx324", "api_port": 29954}, open(D + "/config.json", "w"))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + "/config.json", OTP_LOGDIR=D, OTP_RUN=D + "/run", OTP_STATE_DIR=D)
sys.argv = ["otp"]
spec = importlib.util.spec_from_file_location("otp", V + "/otp.py")
m = importlib.util.module_from_spec(spec)
sys.modules["otp"] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 realms
st.realm_save({'name': 'corp', 'suffix': 'corp.cz', 'aliases': ['corp.local'], 'auth_mode': 'otp', 'enabled': 0}, by='t')
st.realm_save({'name': 'all', 'suffix': '*', 'auth_mode': 'otp', 'enabled': 1}, by='t')
ok('realm: switched off - none', st.realm_for('novak@corp.cz') is None, st.realm_for('novak@corp.cz'))
ok('realm: its other suffix - none', st.realm_for('novak@corp.local') is None, st.realm_for('novak@corp.local'))
r = st.realm_for('novak@else.cz')
ok('realm: another suffix - the "*" one', r and r.get('suffix') == '*', r)
cr = [x for x in st.realms() if x.get('suffix') == 'corp.cz'][0]
cr['enabled'] = 1
st.realm_save(cr, by='t')
r = st.realm_for('novak@corp.cz')
ok('realm: switched on - its own', r and r.get('suffix') == 'corp.cz', r)

# ==== 2 the balancers' networks
try:
    m.check_setting('web_proxy_from', ' '.join('10.%d.0.0/16' % i for i in range(257)))
    ok('web_proxy_from: 257 refused', False)
except m.BadSetting:
    ok('web_proxy_from: 257 refused', True)
ok('web_proxy_from: 100 taken', m.check_setting('web_proxy_from', ' '.join('10.%d.0.0/16' % i for i in range(100))))
dep = open(V + '/deploy/otp_web.py').read()
ok('root: no cut at 64, 256 at most', "[:64]" not in dep[dep.index('def realip_checked'):dep.index('def realip_checked') + 2000]
   and "256 at most" in dep)

# ==== 3 fill_names goes on
class Dd:
    pass


for i in range(7):
    st.db.insert('tokens', {'name': 'svc%d' % i, 'secret': 'x', 'display': ''})
d = Dd(); d.store = st; d.dirs = {}
seen = []
real = st.realm_for
st.realm_for = lambda n: seen.append(n) or None
m.Daemon.fill_names(d, limit=3); m.Daemon.fill_names(d, limit=3); m.Daemon.fill_names(d, limit=3)
ok('fill_names: on from where it stopped', seen[:7] == ['svc%d' % i for i in range(7)], seen)
st.realm_for = real

try:
    m.check_setting('web_proxy_from', ' '.join('2001:db8:aaaa:bbbb:cccc:dddd:eeee:%x/128' % i for i in range(256))); _v6 = True
except Exception as e:                                  # noqa: BLE001
    _v6 = e
ok('web_proxy_from: 256 IPv6 networks taken', _v6 is True, _v6)
print('ALL %d / %d' % (sum(R), len(R)))
