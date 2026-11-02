# t_round13.py VERSION - round 5 of the bug hunt (1.0.227), in-process on SQLite: a code typed with any dash,
# composed or not, "++++++" in password_otp; no key made for a recovery code where tokens are sealed with
# another; a node of a shared database kept as one after a day; the SMS gateway through the proxy kept on
# from before 1.0.202; a node aside for split or clock is not drained; the clock aside node is no longer
# held aside while apart.
import os, sys, json, time, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.227'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r13-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r13'}, open(D + '/config.json', 'w'))
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

# ---- what is typed ------------------------------------------------------------------------------
for typed, want in (('123–456', '123456'), ('123‑456', '123456'), ('１２３－４５６', '123456'),
                    ('ěščřžý', '234567'), ('123\t456', '123456'), ('123−456', '123456'),
                    ('++++++', '111111'), ('1234 5678', '12345678')):
    ok('typed %r read as %s' % (typed, want), otp.code_typed(typed) == want, otp.code_typed(typed))
T = tk.enroll('dash', 'test')
for i, f in enumerate((lambda c: c[:3] + '–' + c[3:], lambda c: c[:3] + '－' + c[3:])):
    while int(time.time()) % 30 > 26:
        time.sleep(1)
    c = otp.totp(T['secret'])
    g = tk.check('dash', f(c))
    ok('a right code with a dash of another kind (%d) let in' % i, g[0], g)
    time.sleep(31 - int(time.time()) % 30)
g = tk.check('dash', T['scratch'][0][:4] + '‐' + T['scratch'][0][4:])
ok('a recovery code with a hyphen let in', g[0], g)

# ---- the key ----------------------------------------------------------------------------------------
otp.seal_fp_check(st)
ok('the mark of the key is written', st.get_meta('seal:fp'))
kp = otp.sealing_key_path()
keep = open(kp, 'rb').read()
os.unlink(kp)
try:
    otp.scratch_hash('x', '12345678')
    ok('no key made for a recovery code where tokens are sealed', False, 'made')
except OSError:
    ok('no key made for a recovery code where tokens are sealed', not os.path.exists(kp))
open(kp, 'wb').write(keep)
os.chmod(kp, 0o600)

# ---- a node of a shared database ------------------------------------------------------------------
otp.CONFIG['ha_mode'] = ''
now = time.time()
st.set_meta('node:moved', json.dumps({'at': now - 25 * 3600}))
ok('a name never alive beside this one is not a cluster after a day', not otp.in_cluster(st))
st.set_meta('node:peer', json.dumps({'at': now - 5}))
ok('a node alive beside this one: a cluster', otp.in_cluster(st))
st.set_meta('node:peer', json.dumps({'at': now - 25 * 3600}))
otp.CLUSTER_WITH.clear()
ok('...still one after it is dead a day', otp.in_cluster(st))
otp.ha_forget(st, 'peer')
st.db.run('DELETE FROM meta WHERE k = ?', ('node:moved',))
ok('...and not once forgotten', not otp.in_cluster(st))

# ---- the SMS gateway through the proxy -----------------------------------------------------------
st.save_setting('proxy', 1)
st.set_meta('schema:r13', '1.0.200')
otp.Storage(db)
ok('from 1.0.200: the SMS gateway kept through the proxy', st.settings_saved().get('proxy_sms') == 1)
st.drop_setting('proxy_sms')
st.set_meta('schema:r13', '1.0.210')
otp.Storage(db)
ok('from 1.0.210: left as it is', 'proxy_sms' not in st.settings_saved())
st.drop_setting('proxy')

# ---- a node aside for split or clock answers nothing, at once ------------------------------------
otp.VIP_HEALTH['here'] = True
otp.VIP_HEALTH.pop('drain_since', None)
ok('maintenance by hand drains while the VIP is here', otp.RadiusServer.draining())
src = open(os.path.join(V, 'otp.py')).read()
ok('split or clock aside is never drained', "m.get('split') or m.get('clock') or not self.draining()" in src)

# ---- clock aside no longer held while apart -------------------------------------------------------
ok('the clock aside node is not kept aside for as long as the nodes are apart',
   "p = dict(p, fresh=True)" not in src)
ok('the wait for the other node\'s database is short', otp.ONCE_PEER_RETRY_S <= 3)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
