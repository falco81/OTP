# t_round11.py VERSION - round 2 of the bug hunt (1.0.224), in-process on SQLite: a token whose name
# was stored decomposed (NFD) renamed to the composed form once, its key, recovery codes and log with it;
# a confirm never makes a key made meanwhile the one in use; wrong codes on a waiting key counted from
# two "nodes" at once; a code with a dash taken by confirm too; the clock correction dropped when the
# machine's clock was stepped since it was measured.
import os, sys, json, time, tempfile, threading, unicodedata
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.224'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r11-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r11'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:300]) if more and not cond else ''), flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
tk = otp.Tokens(st)
KEY = 'JBSWY3DPEHPK3PXPJBSWY3DP'
otp.CONFIG['names_any_letters'] = 1

# ---- a name stored decomposed ----------------------------------------------------------------
nfd = unicodedata.normalize('NFD', 'žofie@x.cz')
nfc = unicodedata.normalize('NFC', 'žofie@x.cz')
codes = ['12345678', '87654321']
st.db.insert('tokens', {'name': nfd, 'secret': otp.seal_secret(KEY, otp.token_bind(nfd)), 'digits': 6, 'period': 30,
                        'algorithm': 'SHA1', 'state': 'active', 'last_step': 0, 'failures': 0, 'fail_times': '[]',
                        'window_steps': -1, 'created': time.time(),
                        'scratch': json.dumps([otp.scratch_hash(nfd, c) for c in codes]),
                        'scratch_sealed': otp.seal_codes(codes, otp.token_bind(nfd)), 'scratch_left': 2})
st.db.insert('otp_log', {'ts': time.time(), 'name': nfd, 'ok': 1, 'said': 'x', 'how': 't', 'src': '', 'rid': ''})
g = tk.check(nfc, otp.totp(KEY))
ok('before: a token stored decomposed is found by nobody (%s)' % g[1], not g[0])
otp.names_nfc_kept(st)
ok('once: renamed to the composed form', st.db.value('SELECT COUNT(*) FROM tokens WHERE name = ?', (nfc,)) == 1
   and not st.db.value('SELECT COUNT(*) FROM tokens WHERE name = ?', (nfd,)))
ok('... its log with it', not st.db.value('SELECT COUNT(*) FROM otp_log WHERE name = ?', (nfd,)) and st.db.value('SELECT COUNT(*) FROM otp_log WHERE name = ?', (nfc,)) >= 2)
g = tk.check(nfc, otp.totp(KEY))
ok('... signs in again, the composed name (%s)' % g[1], g[0])
g = tk.check(otp.unicodedata.normalize('NFD', nfc) if hasattr(otp, 'unicodedata') else nfd, codes[0])
ok('... the decomposed name sent, a recovery code (%s)' % g[1], g[0])
ok('... done once (marked)', st.get_meta('names:nfc:done') == '1')

# ---- confirm: never a key made meanwhile -------------------------------------------------------
st2 = otp.Storage(otp.Db('sqlite', path=os.path.join(D, 'otp.db'))); tk2 = otp.Tokens(st2)
out1 = tk.enroll('pc', 'admin', pending=True)
real_token = st.token
HOOK = {'on': True, 'out2': None}


def token_then_other(name):
    r = real_token(name)
    if HOOK['on'] and name == 'pc':
        HOOK['on'] = False
        HOOK['out2'] = tk2.enroll('pc', 'admin2', pending=True)
    return r


st.token = token_then_other
g = tk.confirm('pc', otp.totp(out1['secret']))
st.token = real_token
r = st.token('pc')
ok('a confirm while the other node made a new key: refused (%s), the new key still waits for its own code' % g[1],
   not g[0] and r['state'] == 'pending' and otp.unseal_secret(r['secret'], otp.token_bind('pc')) == HOOK['out2']['secret'])
g = tk.confirm('pc', otp.totp(HOOK['out2']['secret']))
ok('... confirmed with the new key\'s code', g[0], g)

# ---- wrong codes on a waiting key from two "nodes" ---------------------------------------------
otp.CONFIG.update(rate_limit_tries=100, lockout_after=1000)
otp.import_totp(st, 'sg', KEY + '\n')
tk.stage_replacement('sg', 'test')
b = threading.Barrier(2)


def wrong(t):
    b.wait()
    for i in range(10):
        t.confirm('sg', '000000' if i % 2 else '111111')


th = [threading.Thread(target=wrong, args=(tk,)), threading.Thread(target=wrong, args=(tk2,))]
[x.start() for x in th]; [x.join() for x in th]
ok('wrong codes on a waiting key from two nodes at once: all 20 counted (%d)' % tk.staged_shape('sg')['fails'],
   tk.staged_shape('sg')['fails'] == 20)

# ---- a dash in a code ---------------------------------------------------------------------------
otp.CONFIG.update(rate_limit_tries=3, lockout_after=10)
o = tk.enroll('dash', 'admin', pending=True)
c = otp.totp(o['secret'])
g = tk.confirm('dash', c[:3] + '-' + c[3:])
ok('confirm takes "123-456" as the code (%s)' % g[1], g[0])

# ---- the clock stepped since it was measured ---------------------------------------------------
otp.CONFIG.update(clock_mode='watch', clock_codes=1, clock_warn_s=2)
otp.clock_step(st, ref=120.0, skew='none')
ok('the clock 120 s behind: codes corrected', abs(otp.clock_now('codes') - time.time() - 120) < 1)
otp.CLOCK['ref_wall'] -= 120
ok('the machine\'s clock then put right by hand: the correction dropped at once', abs(otp.clock_now('codes') - time.time()) < 1)
otp.CONFIG.update(clock_mode='off', clock_codes=0)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
