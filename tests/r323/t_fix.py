"""t_fix.py - 1.0.323: a lockout clear asked meanwhile kept; a backup of tokens with odd values
searched; the second step's wait from the count that refused. The built otp.py over SQLite.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, json, os, shutil, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.323'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r323_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx323', 'api_port': 29953}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 lockouts: an ask added while the earlier ones are cleared stays
key = 'lockouts:ask:fx323'
st.set_meta(key, json.dumps([{'all': True, 'by': 'a'}]))
cleared = []


class Dm:
    store = st


def clear(d, which):
    cleared.append(which)
    # the other node asks again meanwhile
    if len(cleared) == 1:
        st.set_meta(key, json.dumps([{'all': True, 'by': 'a'}, {'key': ['ip', '192.0.2.1'], 'by': 'b'}]))
    return 1


m.lockouts_clear = clear
m.lockouts_said = lambda *a, **k: None
m.lockouts_publish = lambda *a, **k: None
m.lockouts_tick(Dm())
ok('lockouts: the ask added meanwhile kept', st.get_meta(key) is not None and 'b' in st.get_meta(key), st.get_meta(key))
m.lockouts_tick(Dm())
ok('lockouts: read and cleared at the next look', st.get_meta(key) is None and len(cleared) == 2, (st.get_meta(key), cleared))

# ==== 2 memory_search: a list or an object as text
rows = [{'name': 'a', 'note': ['x', 'y']}, {'name': 'b', 'note': {'k': 1}}, {'name': 'c', 'note': 'plain'}]
try:
    got = m.memory_search('tokens', 'CREATE TABLE t (i INTEGER, name TEXT, note TEXT)', ['name', 'note'], rows, 'a')
    ok('memory_search: odd values searched', isinstance(got, list), got)
except Exception as e:                                  # noqa: BLE001
    ok('memory_search: odd values searched', False, repr(e))
ok('memory_search: values', m._mem_value(['x']) == '["x"]' and m._mem_value(3) == 3 and m._mem_value(None) is None)

# ==== 3 the second step's wait
src = inspect.getsource(m._mfa_send)
ok('mfa: the refusing count\'s wait', 'code_send_wait_min(h.store, dkey if a_ok else akey)' in src)

print('ALL %d / %d' % (sum(R), len(R)))
