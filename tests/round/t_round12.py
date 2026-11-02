# t_round12.py VERSION - round 3 of the bug hunt (1.0.225), in-process on SQLite: a database put back
# keeps the codes used since the copy used up; the names of tokens are put in one form only with the key
# that opens them; a code typed as the mail shows it is read; the limit of codes sent holds; a code not
# sent is not counted; DOMAIN\name refused on a rename.
import os, sys, json, time, tempfile, unicodedata
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.225'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r12-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r12'}, open(D + '/config.json', 'w'))
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

# ---- a database put back ---------------------------------------------------------------------
T = tk.enroll('rest', 'test')
dump = otp.make_backup(st, 'test') if hasattr(otp, 'make_backup') else None
ok('a copy made', dump)
g = tk.check('rest', T['scratch'][0])
ok('a recovery code used after the copy', g[0], g)
try:
    otp.db_file_restore(st, str(dump), by='test', need_admin=False)
    restored = True
except Exception as e:                                  # noqa: BLE001
    restored = False
    print('restore:', e)
ok('the copy put back', restored)
g = tk.check('rest', T['scratch'][0])
ok('... the recovery code used since stays used (%s)' % g[1], not g[0])

# ---- names put in one form only with the key -------------------------------------------------
otp.CONFIG['names_any_letters'] = 1
nfd = unicodedata.normalize('NFD', 'řehoř@x.cz')
nfc = unicodedata.normalize('NFC', nfd)
KEY = 'JBSWY3DPEHPK3PXPJBSWY3DP'
st.db.insert('tokens', {'name': nfd, 'secret': otp.seal_secret(KEY, otp.token_bind(nfd)), 'digits': 6,
                        'period': 30, 'algorithm': 'SHA1', 'state': 'active', 'last_step': 0, 'failures': 0,
                        'fail_times': '[]', 'window_steps': -1, 'created': time.time(),
                        'scratch': json.dumps([otp.scratch_hash(nfd, '24681357')]), 'scratch_sealed': '',
                        'scratch_left': 1})
kp = otp.sealing_key_path()
os.rename(str(kp), str(kp) + '.away'); otp._KEY_CACHE.clear()
otp.names_nfc_kept(st)
ok('without the key: nothing renamed, not marked done', st.db.value('SELECT COUNT(*) FROM tokens WHERE name = ?', (nfd,)) == 1
   and st.get_meta('names:nfc:done') is None)
os.rename(str(kp) + '.away', str(kp)); otp._KEY_CACHE.clear()
otp.names_nfc_kept(st)
ok('with the key: renamed', st.db.value('SELECT COUNT(*) FROM tokens WHERE name = ?', (nfc,)) == 1)
g = tk.check(nfc, otp.totp(KEY))
ok('... its code works (%s)' % g[1], g[0])
g = tk.check(nfc, '24681357')
ok('... a recovery code never sealed, kept by its old hash (%s)' % g[1], g[0])

# ---- a code as the mail shows it -------------------------------------------------------------
ok('"821 275", "188-269", no-break space, the Czech row read as digits',
   otp.code_typed('821 275') == '821275' and otp.code_typed('188-269') == '188269'
   and otp.code_typed('821\xa0275') == '821275' and otp.code_typed('+ěščřž') == '123456')

# ---- codes sent: the limit, a code not sent ----------------------------------------------------
otp.CONFIG.update(code_send_max=3, code_send_window_min=15)
n = sum(1 for _ in range(5) if otp.code_send_allowed(st, 'lim'))
ok('the limit of codes sent holds (%d of 5)' % n, n == 3)
otp.node_key_give_back(st, 'codesent', 'lim')
ok('a code not sent given back: one more may go', otp.code_send_allowed(st, 'lim'))

# ---- DOMAIN\name refused for a rename ----------------------------------------------------------
ok('DOMAIN\\name is not a token\'s name', bool(otp.token_name_problem('corp\\jan')))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
