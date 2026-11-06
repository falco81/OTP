"""t_review.py - 1.0.255, the review of its own fixes: an account whose second step an older version
reset (its signature left behind) is not held; a sign-in with no signed marks taken while a node of
1.0.254 is alive; a request to the root helper left unread for long is written over, not waited on
for ever; no backup yet - not refused by the database's own size; the TLS rescue judged by the
probe's own words, after two looks."""
import sys, os, time, json, tempfile, pathlib
V = '/home/claude/build/out/otp-%s' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.255')
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402

R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


# ---- 1: a row not there is never held ---------------------------------------------------------
otp.dbguard_on = lambda: True
otp._dbguard_sigs = lambda db, kind, ident: ['a signature left behind']


class Db:
    engine = 'sqlite'

    def __init__(self, v):
        self.v = v

    def value(self, sql, args=()):
        return self.v


ok('a row not there, its old signature left: not held', otp.dbguard_meta_gone(Db(None), 'adm2fa:novak') is False)
real_ok = otp.dbguard_ok
otp.dbguard_ok = lambda db, kind, ident, value, quiet=False, early=True: False
ok('a row there, not signed by otp: held', otp.dbguard_meta_gone(Db('{"kind": "app"}'), 'adm2fa:novak') is True)
otp.dbguard_ok = real_ok

# ---- 2: no signed marks while a node of 1.0.254 is alive --------------------------------------
otp.CONFIG['admin_2fa'] = 1
otp._dbguard_sigs = lambda db, kind, ident: []
otp.DBGUARD['behind'] = {'1.0.255'}
ok('no marks signed, a node of 1.0.254 alive: taken', otp.dbguard_session_marks_ok(Db(None), {'token_hash': 'h'}) is True)
otp.DBGUARD['behind'] = set()
ok('...with none: asked to sign in again, as before', otp.dbguard_session_marks_ok(Db(None), {'token_hash': 'h'}) is False)
ok('1.0.255 among the versions a node behind is told by', '1.0.255' in otp.DBGUARD_SINCE)

# ---- 3: a request to the root helper left unread ----------------------------------------------
d = pathlib.Path(tempfile.mkdtemp(prefix='rv-'))
otp.WEB_DIR = d
ok('no request there: not busy', otp._pgtls_ask_fresh() is False)
(d / otp.PGTLS_ASK).write_text('{}')
ok('a request just written: busy', otp._pgtls_ask_fresh() is True)
old = time.time() - 600
os.utime(str(d / otp.PGTLS_ASK), (old, old))
ok('one left for 10 min: written over as before, not passed over for ever', otp._pgtls_ask_fresh() is False)

# ---- 4 / 5: the source -------------------------------------------------------------------------
src = open(V + '/otp.py').read()
ok('the room check: no backup yet - no size from the database', 'size = int(store.db.size() or 0)' not in src)
ok('the TLS rescue: by the probe\'s own words, after two looks',
   'if peer_db_restarting(why):' in src and 'DBTLS_RESCUE_AFTER = 2' in src)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
