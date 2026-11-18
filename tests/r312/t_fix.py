"""t_fix.py - 1.0.312: the cap of wrong directory passwords counted as the directory counts them - its
counter goes back to 0 only once the time has gone by since the LAST wrong password. The parts loaded as a
module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.312'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r312_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx312', 'api_port': 29942}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
                  OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', TOP + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.sealing_key(make=True)



class H(object):
    def __init__(self, store):
        self.store, self.fails = store, 0

    def failed(self, *a):
        self.fails += 1


M = 60.0
# ==== 1 the run a directory counts
s = m.node_key_streak
ok('1 none: nothing counts', s([], 1800, 1000) == [])
ok('1 the newest 30 min old: nothing counts any more', s([0, 600, 1200], 1800, 1200 + 1800) == [])
ok('1 10 min apart: every one counts (the directory\'s counter never went back to 0)',
   s([0, 600, 1200, 1800], 1800, 1801) == [0, 600, 1200, 1800])
ok('1 a gap of 30 min: only those after it', s([0, 2000, 2600], 1800, 2700) == [2000, 2600])
ok('1 rows as (time, row) too', s([(5, 'b'), (1, 'a')], 1800, 6) == [(1, 'a'), (5, 'b')])

# ==== 2 the cap on these pages: 3 in 30 min
m.CONFIG.update(radius_guard=1, dir_pw_tries=3, dir_pw_window_min=30)
now = time.time()
who = 'novak|corp'
k = m.node_key('adpw', who)


def put(times):
    st.db.run('DELETE FROM meta WHERE k LIKE ?', ('adpw:%',))
    st.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, json.dumps(times)))


put([now - 25 * M, now - 15 * M, now - 5 * M])
h = H(st)
try:
    m.dir_pw_take(h, 'novak', 'corp')
    took = 'let past'
except m.ApiError as e:
    took = e.status, str(e)
ok('2 three wrong 10 min apart, the first 25 min ago: the 4th not let to the directory (it would count 4)',
   isinstance(took, tuple) and took[0] == 429 and 'in 25 min' in took[1], took)
put([now - 45 * M, now - 35 * M, now - 31 * M])
try:
    held = m.dir_pw_take(H(st), 'novak', 'corp')
except m.ApiError as e:
    held = e
ok('2 ...the last one 31 min ago: the directory has gone back to 0 - let past', held == who, held)
put([now - 40 * M, now - 20 * M])
ok('2 two in the run (20 min apart): the third let past', m.dir_pw_take(H(st), 'novak', 'corp') == who)
ok('2 ...and the fourth not', not m.node_key_add(st, 'adpw', who, 1800 * 4, limit=3, streak=1800))
# another node's row counts with this one's
st.db.run('DELETE FROM meta WHERE k LIKE ?', ('adpw:%',))
st.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k + m.NODE_KEY_SEP + 'othernode', json.dumps([now - 25 * M, now - 12 * M])))
st.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, json.dumps([now - 2 * M])))
try:
    m.dir_pw_take(H(st), 'novak', 'corp')
    t2 = 'let past'
except m.ApiError as e:
    t2 = e.status
ok('2 two on the other node, one here, in one run: the 4th refused', t2 == 429, t2)

# ==== 3 Locked out (the list): as the cap counts
put([now - 25 * M, now - 15 * M, now - 5 * M])
rows = [r for r in m.lockouts_shared(st) if r['kind'] == 'dir-passwords']
ok('3 listed locked, free 30 min after the last one', len(rows) == 1 and rows[0]['locked'] and rows[0]['fails'] == 3
   and abs(rows[0]['until'] - (now - 5 * M + 30 * M)) < 2, rows)
put([now - 50 * M, now - 40 * M, now - 31 * M])
ok('3 the last one 31 min ago: not listed', not [r for r in m.lockouts_shared(st) if r['kind'] == 'dir-passwords'])

# ==== 4 the other users of node_key_add: as before
st.db.run("DELETE FROM meta WHERE k LIKE 'codesent:%'")
m.CONFIG.update(code_send_max=2, code_send_window_min=15)
a = [m.code_send_allowed(st, 'eva') for _ in range(3)]
ok('4 codes sent: 2 in 15 min, the 3rd not (each counted on its own, as before)', a == [True, True, False], a)

# ==== 5 the words
ok('5 the help of the time says "since the last wrong password"', 'since the last wrong' in m.SAYS['dir_pw_window_min'], m.SAYS.get('dir_pw_window_min'))
JS = open(ASSETS).read()
ok('5 a domain that never locks: its window and duration greyed', "lk.threshold ? '' : 'dim'" in JS)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
