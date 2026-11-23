"""t_fix.py - 1.0.319: the SSH gate without a Message-Authenticator only with the secret; Windows'
Kerberos OID; an SSH token removed under its lock; local users' asks under a lock; agents' alerts on
every node; no TLS rescue to an agent's server; the TLS wish put back; the SNMP salt under a lock.
The built otp.py loaded as a module over SQLite, no daemon.

    python3 t_fix.py VERSION
"""
import hashlib, hmac, importlib.util, inspect, json, os, shutil, struct, sys, tempfile, threading, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.319'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r319_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx319', 'api_port': 29949}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 the SSH gate
sec = m.ssh_gate_secret(st, make=True).encode()
m.sshotp_make(st, 'jan', 'admin')


def req(user, pw=None, secret=sec, ma=False, rawpw=None):
    auth = os.urandom(16)
    attrs = bytes([1, len(user) + 2]) + user.encode()
    if rawpw is not None:
        attrs += bytes([2, len(rawpw) + 2]) + rawpw
    elif pw is not None:
        p = pw.encode() + b'\x00' * (16 - len(pw) % 16 if len(pw) % 16 or not pw else 0)
        out, last = b'', auth
        for i in range(0, len(p), 16):
            pad = hashlib.md5(secret + last).digest()
            blk = bytes(a ^ b for a, b in zip(p[i:i + 16], pad))
            out += blk; last = blk
        attrs += bytes([2, len(out) + 2]) + out
    if ma:
        attrs += bytes([80, 18]) + b'\x00' * 16
    data = bytearray(struct.pack('!BBH', 1, 7, 20 + len(attrs)) + auth + attrs)
    if ma:
        mac = hmac.new(secret, bytes(data), hashlib.md5).digest()
        data[-16:] = mac
    return bytes(data)


class Dm:
    store = st


g = object.__new__(m.SshGate); g.d = Dm()
A = ('127.0.0.1', 40000)
fails0 = (m.sshotp_get(st, 'jan') or {}).get('fails')
ok('gate: a forged password without MA ignored', g.answer(req('jan', rawpw=os.urandom(16)), A) is None)
ok('gate: no password without MA ignored', g.answer(req('jan'), A) is None)
ok('gate: a wrong-secret empty password ignored', g.answer(req('jan', '', secret=b'nope'), A) is None)
ok('gate: nothing counted against the name', (m.sshotp_get(st, 'jan') or {}).get('fails') == fails0 and
   not m.SSHOTP_FAILS.get('jan'), (m.sshotp_get(st, 'jan'), dict(m.SSHOTP_FAILS)))
r = g.answer(req('jan', ''), A)
ok('gate: pam_radius without MA, empty password: asked for the code', r is not None and r[0] == 11, r and r[0])
r = g.answer(req('jan', '123456'), A)
ok('gate: pam_radius without MA, a code: answered (refused)', r is not None and r[0] == 3, r and r[0])
r = g.answer(req('jan', '123456', ma=True), A)
ok('gate: with a right MA: answered', r is not None and r[0] == 3, r and r[0])
bad = bytearray(req('jan', '123456', ma=True)); bad[-1] ^= 1
ok('gate: a wrong MA ignored', g.answer(bytes(bad), A) is None)

# ==== 2 Kerberos: both OIDs
src = inspect.getsource(m)
ok('kerberos: Windows OID taken', m.KRB5_MECH_MS == bytes.fromhex('2a864882f712010202') and
   'got not in (KRB5_MECH, KRB5_MECH_MS)' in src)

# ==== 3 an SSH token removed while a sign-in writes: under the lock
held = threading.Event(); went = []


def remover():
    m.sshotp_remove(st, 'jan', 'admin'); went.append(1)


with m.SSHOTP_LOCK:
    t = threading.Thread(target=remover); t.start(); t.join(0.5)
    ok('sshotp: remove waits for the lock', not went)
t.join(5)
ok('sshotp: removed after', went and not m.sshotp_get(st, 'jan'))
m._sshotp_used(st, 'jan', False)
ok('sshotp: a sign-in after the removal does not bring it back', not m.sshotp_get(st, 'jan'))

# ==== 4 local users: asks under their lock
ok('osusers: a lock of their own', isinstance(m.OSU_ASK_LOCK, type(threading.Lock())))
s1, s2 = inspect.getsource(m.osu_ask), inspect.getsource(m.osu_forget_hashes)
ok('osusers: both writers hold it', 'with OSU_ASK_LOCK' in s1 and 'with OSU_ASK_LOCK' in s2)

# ==== 5 agents' alerts on a node without an agent of its own
m.CONFIG['ha_mode'] = 'replicated'
m.db_agent_on = lambda *a, **k: False
m.db_agent_servers = lambda store: [{'node': 'n2', 'host': 'db2', 'port': 5432, 'ok': False,
                                     'down_since': 1.0, 'said': 'down', 'facts': {}, 'agent': {}}]
try:
    al = m._db_agent_alerts(st)
    ok('dbagent: the other node\'s server said', any('n2' in json.dumps(a) for a in al), al)
except Exception as e:                                  # noqa: BLE001
    ok('dbagent: the other node\'s server said', False, repr(e))
m.CONFIG['ha_mode'] = ''

# ==== 6 no TLS rescue to an agent's server
class Db2:
    def value(self, q):
        raise RuntimeError('SSL error: certificate verify failed')


class Dm2:
    store = type('S', (), {'db': Db2()})()


m.CONFIG.update(db_engine='postgres', db_host='10.0.0.9', db_tls='verify-full')
m.db_agent_here = lambda *a, **k: True
probes = []
m.dbtls_probe = lambda mode, ca: probes.append(mode) or {'ok': True}
m.write_file_settings = lambda d: probes.append(('write', d))
m.DBTLS_WORK['rescue'] = 0
m._dbtls_rescue(Dm2())
ok('dbtls: no rescue for an agent\'s server', not probes and m.CONFIG.get('db_tls') == 'verify-full', probes)
m.CONFIG.update(db_engine='sqlite', db_host='', db_tls='')

# ==== 7 the wish of none put back when the switch fails
srcw = inspect.getsource(m)
ok('dbtls: wish checked against high security first and put back',
   '_dbtls_hisec(mode, store)\n            was_want = _dbtls_want(store, derive=False)' in srcw and
   'store.set_meta(DBTLS_WANT_KEY, json.dumps(was_want))' in srcw)

# ==== 8 SNMP salt: never twice from two threads
a = m.SnmpAgent.__new__(m.SnmpAgent); a.salt = 0
ok('snmp: a lock of the class', isinstance(m.SnmpAgent.salt_lock, type(threading.Lock())))
c = {'auth': 'sha', 'priv': 'aes', 'user': 'u', 'auth_key': 'x' * 12, 'priv_key': 'y' * 12}
seen = []
a.engine = b'\x80\x00\x1f\x88\x04test'; a.boots = 1; a.now_time = lambda: 5
a.keys = (b'k' * 20, b'p' * 16)
orig = m.snmp_cfb
m.snmp_cfb = lambda key, iv, data, dec: seen.append(iv) or data


def many():
    for _ in range(300):
        try:
            a.wrap(1, b'\x30\x00', c, 3)
        except Exception as e:                          # noqa: BLE001
            seen.append(('err', repr(e)))
            return


ts = [threading.Thread(target=many) for _ in range(4)]
[t.start() for t in ts]; [t.join() for t in ts]
errs = [x for x in seen if isinstance(x, tuple)]
ok('snmp: 1200 IVs, all different', not errs and len(set(seen)) == 1200, errs[:2] or len(set(seen)))
m.snmp_cfb = orig

print('ALL %d / %d' % (sum(R), len(R)))
