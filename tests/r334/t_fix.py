"""t_fix.py - 1.0.334: a move from SQLite/MariaDB to PostgreSQL not refused as "an older copy: the
tokens"; a setting saved later than the one it replaces whatever the clock; the other node's
scratchguard rows not tidied here.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.334'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r334_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx334', 'api_port': 29957}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 the fingerprint: a carry into PostgreSQL, whose trigger fills the times
now = time.time()
for i in range(3):
    st.db.insert('tokens', {'name': 'u%d@x' % i, 'secret': 'S', 'created': now - 100 + i})
far_path = TOP + '/far.db'
cp = TOP + '/copy.json.gz'
m.dump_tables(st.db, cp)
fdb = m.Db('sqlite', path=far_path)
fdb.make_tables()
m.load_tables(fdb, cp)
ok('a plain carry: nothing differs', m.db_fingerprint_diff(st.db, fdb) == [], m.db_fingerprint_diff(st.db, fdb))
# as PostgreSQL's trigger does on INSERT: the times filled with the time of the carry
fdb.run('UPDATE tokens SET key_at = ?, state_at = ?, scratch_at = ?', (now + 5, now + 5, now + 5))
ok('times filled by the trigger there, empty here: not "an older copy"', m.db_fingerprint_diff(st.db, fdb) == [],
   m.db_fingerprint_diff(st.db, fdb))
fdb.run("DELETE FROM tokens WHERE name = 'u2@x'")
ok('a token missing there: still found', m.db_fingerprint_diff(st.db, fdb) == ['the tokens'])
fdb.run("INSERT INTO tokens (name, secret, created) VALUES ('u2@x', 'S', ?)", (now - 98,))
fdb.run('UPDATE tokens SET key_at = ?, state_at = ?, scratch_at = ?', (now + 5, now + 5, now + 5))
st.db.run("UPDATE tokens SET key_at = ? WHERE name = 'u1@x'", (now + 50,))
ok('a time here newer than there: still found', m.db_fingerprint_diff(st.db, fdb) == ['the tokens'])
st.db.run("UPDATE tokens SET key_at = NULL")
st.db.insert('tokens', {'name': 'u9@x', 'secret': 'S', 'created': now + 30})
ok('a token enrolled since the carry: still found', m.db_fingerprint_diff(st.db, fdb) == ['the tokens'])
fdb.close()

# ==== 2 a setting later than the one it replaces
st.save_setting('radius_port', 1812)
st.db.run("UPDATE settings SET at = ? WHERE k = 'radius_port'", (now + 3600,))   # the other node's clock ahead
st.save_setting('radius_port', 1813)
at = float(st.db.value("SELECT at FROM settings WHERE k = 'radius_port'"))
ok('saved later than the one it replaces', at > now + 3600 and json.loads(st.db.value("SELECT v FROM settings WHERE k = 'radius_port'")) == 1813, at - now)
st.save_setting('new_one_334', 1)
at2 = float(st.db.value("SELECT at FROM settings WHERE k = 'new_one_334'"))
ok('a new one: now', abs(at2 - time.time()) < 5)

# ==== 3 once_tidy: own rows only
old = json.dumps([now - 3 * 86400])
st.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', ('scratchguard:bob' + m.NODE_KEY_SEP + 'othernode', old))
st.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', ('scratchguard:bob' + m.NODE_KEY_SEP + m.node_name(), old))
m.CONFIG['ha_mode'] = 'replicated'
try:
    m.once_tidy(st)
finally:
    m.CONFIG.pop('ha_mode', None)
left = [r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'scratchguard:%'")]
ok('the other node\'s row kept, this one\'s tidied', left == ['scratchguard:bob' + m.NODE_KEY_SEP + 'othernode'], left)
m.once_tidy(st)
ok('standalone: tidied as before', [r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'scratchguard:%'")] == [])
print('ALL %d / %d' % (sum(R), len(R)))
