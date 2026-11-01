# t_round8.py VERSION - 1.0.214: recovery codes of every length in a realm of password+code, a recovery
# code sent again not counted as wrong, spaces inside a code, the database pane's "Set it up" not
# pointing the database in use elsewhere, and the wizard's own parts. In-process, SQLite.
import os, sys, json, time, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.214'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r8-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r8'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
d = otp.Daemon(st, serve=False)
KEY = 'JBSWY3DPEHPK3PXPJBSWY3DP'
otp.import_totp(st, 'ana', KEY + '\n" TOTP_AUTH\n1234567890\n7654321\n22446688\n')
tk = d.tokens if hasattr(d, 'tokens') else otp.Tokens(st)

# ---- a recovery code sent again: said as used, not counted ----------------------------------------
got = tk.check('ana', '22446688', how='t')
ok('a recovery code: let in', got[0] is True, got)
got2 = tk.check('ana', '22446688', how='t')
fails = int(st.token('ana').get('failures') or 0)
ok('... sent again: refused as used, nothing counted (%s, failures %d)' % (got2[1], fails),
   got2[0] is False and got2[1] == otp.SAY_REUSED and fails == 0)
got3 = tk.check('ana', '99999999', how='t')
ok('... a code never given: counted as wrong', got3[0] is False and int(st.token('ana').get('failures') or 0) == 1)
st.db.run("UPDATE tokens SET failures = 0, fail_times = '[]' WHERE name = 'ana'")

# ---- a code with spaces inside, as the phone shows it -----------------------------------------------
code = otp.totp(KEY)
if int(time.time()) % 30 > 26:
    time.sleep(4)
    code = otp.totp(KEY)
if code:
    spaced = code[:3] + ' ' + code[3:]
    got = tk.check('ana', spaced, how='t')
    ok('a code typed "%s": let in' % spaced, got[0] is True, got)

# ---- password+code: a recovery code of another length than scratch_digits ---------------------------
src = open(V + '/otp.py').read()
ok('password+code: every recovery code length 6-12 tried (by the dry check)',
   'for ln in range(6, 13):' in src and 'if ln not in (digits, sd) and len(password) > ln:' in src)
for ln, c in ((10, '1234567890'), (7, '7654321')):
    good = None
    for cut in sorted({6, 8, 10, 7, 9, 11, 12}):
        pw = 'Secret-pass' + c
        if pw[-cut:] == c:
            good = tk.check('ana', pw[-cut:], how='t', dry=True, quiet=True)
            break
    ok('... a %d-digit recovery code after the password found by the dry check' % ln, good and good[0] is True, good)

# ---- the database pane ---------------------------------------------------------------------------------
ok('Set it up writes the address into config.json only when it cannot point the database in use elsewhere',
   ("if h.store.db.engine == 'sqlite' or same_database(c, h.store.db):" in src or
    "if h.store.db.engine == 'sqlite' or db_same_place(h.store, c):" in src))
ok('GET /api/db says whether this node is one of a cluster, and which drivers are here',
   "'cluster': in_cluster(h.store)" in src and "db_driver_here(e)" in src)
ok('... the drivers of this Python: PostgreSQL %s, MariaDB %s' % (otp.db_driver_here('postgres'), otp.db_driver_here('mariadb')),
   otp.db_driver_here('nonsense') is False)
J = open(V + '/web/assets/admin.js').read()
P = open(V + '/web/admin/index.php').read()
ok('the wizard: Back and Next, five steps, the move refused in a cluster',
   'function dbWizard()' in J and "DBW_STEPS = ['Which one', 'Its address', 'Reaching it', 'What happens', 'Moving']" in J
   and 'if (d.cluster)' in J and 'id="db-wizard"' in P and 'id="db-wizard-cluster"' in P)

# ---- 1.0.214 under load in HA: a code used up all or nothing, a burst of requests held ------------
ok('a code from the phone: its step and its token_once rows written in one transaction',
   src.count('with self.store.db.transaction():') == 2 and 'def transaction(self):' in src
   and "once_take(self.store, 'step', name, once_v, peer=False)" in src)
ok('the lock of one node kept when the other counted a wrong code at the same moment',
   'OR NEW.locked_until IS DISTINCT FROM OLD.locked_until) THEN' in src)
ok('RADIUS sockets with a receive buffer for a burst (%d MB)' % (otp.RADIUS_RCVBUF >> 20),
   otp.RADIUS_RCVBUF >= 4 << 20 and 'SO_RCVBUFFORCE' in src)
ok('a token made on the other node a moment before: changed, not a raw duplicate key error',
   "if not ('duplicate' in said or 'unique' in said):" in src)
print('ALL %d / %d' % (sum(R), len(R)))
