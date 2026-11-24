"""t_fix.py - 1.0.333: an SSH token's and an administrator's second step's row written only as it was
read (a token replaced or removed on the other node meanwhile stays so); a sign-in ended for wrong
codes gives no session to a right code waiting behind them.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.333'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r333_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx333', 'api_port': 29956}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 meta_json_update
st.set_meta('x:1', json.dumps({'a': 1}))
ok('changed where it is', st.meta_json_update('x:1', lambda r: dict(r, a=2)) == {'a': 2}
   and json.loads(st.get_meta('x:1')) == {'a': 2})
ok('not there: None, never made', st.meta_json_update('x:none', lambda r: r) is None and st.get_meta('x:none') is None)
ok('declined: False, left', st.meta_json_update('x:1', lambda r: None) is False and json.loads(st.get_meta('x:1')) == {'a': 2})
calls = []


def racing(r):
    calls.append(1)
    if len(calls) == 1:                         # somebody else writes between the read and the write
        st.db.run('UPDATE meta SET v = ? WHERE k = ?', (json.dumps({'a': 10}), 'x:1'))
    return dict(r, a=r['a'] + 1)


ok('a change meanwhile: done again over it', st.meta_json_update('x:1', racing) == {'a': 11} and len(calls) == 2)


# ==== 2 the SSH token
def secret_of(name):
    rec = m.sshotp_get(st, name)
    return m.unseal_secret(rec['secret'], m.sshotp_key(name))


def code_of(sec, ahead=0):
    return m.hotp(sec, m.totp_step(m.clock_now('codes')) + ahead)


m.sshotp_make(st, 'bob', 'admin')
s1 = secret_of('bob')
good, said = m.sshotp_check(st, 'bob', code_of(s1))
ok('a right code lets in', good, said)

# removed on the other node while this one checked a code
real_once = m.once_take


def remove_then(store, *a, **kw):
    store.db.run('DELETE FROM meta WHERE k = ?', (m.sshotp_key('bob'),))
    return real_once(store, *a, **kw)


m.sshotp_make(st, 'bob', 'admin', replace=True)
s2 = secret_of('bob')
m.once_take = remove_then
good, said = m.sshotp_check(st, 'bob', code_of(s2, 1))
m.once_take = real_once
ok('removed meanwhile: refused, and not made again', not good and m.sshotp_get(st, 'bob') is None, (good, said))

# replaced on the other node while this one checked a wrong code
m.sshotp_make(st, 'bob', 'admin')
s3 = secret_of('bob')
st.set_meta(m.sshotp_key('bob') + ':x', '1')
new_secret = {}


def replace_then(store, *a, **kw):
    rec = m.sshotp_get(store, 'bob')
    rec['secret'] = m.seal_secret(m.b32_new(20), m.sshotp_key('bob'))
    rec['step'] = 0
    new_secret['v'] = rec['secret']
    store.db.run('UPDATE meta SET v = ? WHERE k = ?', (json.dumps(rec), m.sshotp_key('bob')))
    return real_once(store, *a, **kw)


m.once_take = replace_then
good, said = m.sshotp_check(st, 'bob', code_of(s3, 2))
m.once_take = real_once
ok('replaced meanwhile: the old code refused', not good, said)
ok('replaced meanwhile: the new key kept', m.sshotp_get(st, 'bob')['secret'] == new_secret['v'])

# wrong codes counted on the row
m.sshotp_make(st, 'carl', 'admin')
m.SSHOTP_FAILS.clear()
m.sshotp_check(st, 'carl', '000000' if code_of(secret_of('carl')) != '000000' else '111111')
ok('a wrong code counted on the row', int(m.sshotp_get(st, 'carl').get('fails') or 0) == 1, m.sshotp_get(st, 'carl'))
m.SSHOTP_FAILS.clear()
m._sshotp_used(st, 'gone-one', True)
ok('_sshotp_used makes no row for one not there', m.sshotp_get(st, 'gone-one') is None)

# ==== 3 the second step: source, and _mfa_done
src = open(V + '/otp.py').read()
chk = src[src.index("        if rec.get('kind') == 'app':\n            # Read, checked and written under one lock"):][:3000]
ok('the app code written only over the same key', "h.store.meta_json_update(mfa_key(name), stepped)" in chk
   and "r.get('secret') != same" in chk)
ok('the passkey counter written only while it is there', 'h.store.meta_json_update(mfa_key(name), counted)' in src)


class H(object):
    def __init__(self):
        self.store = st

    def client_ip(self):
        return '192.0.2.1'


st.db.insert('accounts', {'name': 'boss', 'role': 'fulladmin', 'pw': 'x', 'source': 'local', 'disabled': 0})
tok = st.session_new('admin', 'boss', 'fulladmin', '192.0.2.1', 1, data={'mfa': 1})
sid = st.db.value('SELECT id FROM sessions ORDER BY id DESC LIMIT 1')
srow = {'id': sid, 'name': 'boss', 'role': 'fulladmin', 'expires': time.time() + 3600, 'data': {'mfa': 1}}
n0 = st.db.value('SELECT COUNT(*) FROM sessions')
t2 = m._mfa_done(H(), srow, 'an app')
ok('a right code: a new sign-in, the old one gone', t2 and st.db.value('SELECT COUNT(*) FROM sessions') == n0
   and not st.db.value('SELECT COUNT(*) FROM sessions WHERE id = ?', (sid,)))
try:
    m._mfa_done(H(), srow, 'an app')            # the same sign-in again: it was ended
    e = None
except m.ApiError as x:
    e = x
ok('a sign-in ended: no session given', e is not None and getattr(e, 'status', getattr(e, 'code', 0)) == 401
   and st.db.value('SELECT COUNT(*) FROM sessions') == n0, e)
cs = json.load(open(V + '/web/lang/cs.json'))
ok('its words in Czech', all(any(v['source'] == w and v['text'] for v in cs['strings'].values()) for w in (
    'the SSH token was changed meanwhile - try again', 'this sign-in was ended - sign in again',
    'the second step of this account was changed meanwhile - sign in again')))
print('ALL %d / %d' % (sum(R), len(R)))
