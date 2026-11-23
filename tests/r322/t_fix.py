"""t_fix.py - 1.0.322: a copy made by a newer otp refused unless --allow-newer; a backup put back on a
node of one shared database keeps its name; the split watch's probe closes its own connection only.
The built otp.py loaded as a module over SQLite.

    python3 t_fix.py VERSION
"""
import gzip, importlib.util, inspect, json, os, shutil, sqlite3, sys, tempfile, threading, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.322'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r322_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx322', 'api_port': 29952}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)
st.db.insert('accounts', {'name': 'boss', 'role': 'fulladmin', 'pw': 'x', 'source': 'local', 'disabled': 0})

# ==== 1 copies: this version's taken, a newer one refused
cp = TOP + '/copy.json.gz'
m.dump_tables(st.db, cp)
said, why = m.db_file_peek(cp, 'sqlite')
ok('peek: a copy of this version', said and said.get('version') == m.__version__ and not said.get('newer'), (said, why))


def rewrite(src, dst, ver):
    with gzip.open(src, 'rt', encoding='utf-8') as f:
        lines = f.read().splitlines()
    head = json.loads(lines[0]); head['otp'] = ver
    with gzip.open(dst, 'wt', encoding='utf-8') as f:
        f.write('\n'.join([json.dumps(head)] + lines[1:]) + '\n')


new = TOP + '/newer.json.gz'; rewrite(cp, new, '9.9.9')
said, why = m.db_file_peek(new, 'sqlite')
ok('peek: a newer one said', said and said.get('newer') == '9.9.9', (said, why))
try:
    m.db_file_restore(st, new, 'test'); ok('restore: newer refused', False)
except ValueError as e:
    ok('restore: newer refused', 'made by otp 9.9.9' in str(e) and '--allow-newer' in str(e), e)
old = TOP + '/older.json.gz'; rewrite(cp, old, '1.0.200')
said, why = m.db_file_peek(old, 'sqlite')
ok('peek: an older one not newer', said and not said.get('newer'), said)

# ==== 2 a SQLite file: the version of its schema rows
sq = TOP + '/n.sqlite'
db2 = m.Db('sqlite', path=sq); db2.make_tables()
db2.insert('accounts', {'name': 'boss', 'role': 'fulladmin', 'pw': 'x', 'source': 'local', 'disabled': 0})
db2.upsert('meta', 'k', {'k': 'schema:a', 'v': '1.0.100'})
db2.upsert('meta', 'k', {'k': 'schema:b', 'v': '9.1.0'})
db2.close()
said, why = m.db_file_peek(sq, 'sqlite')
ok('peek sqlite: the newest schema row', said and said.get('version') == '9.1.0' and said.get('newer') == '9.1.0', (said, why))

# ==== 3 the command line and rb_restore carry allow_newer
src = inspect.getsource(m)
ok('--allow-newer in the parser', "g.add_argument('--allow-newer', action='store_true'" in src)
ok('--restore and --restore-bundle pass it', src.count('allow_newer=args.allow_newer') == 2)
rs = inspect.getsource(m.rb_restore)
ok('rb_restore: the manifest\'s version looked at', "_ver_tuple(m['otp']) > _ver_tuple(__version__) and not allow_newer" in rs)
ok('rb_restore: no rename in any cluster', 'not in_cluster(store)' in rs)

# ==== 4 the split probe: its own connection only
closed = []


class FakeDb:
    def __init__(self, n, slow=0, fail=False):
        self.n, self.slow, self.fail = n, slow, fail

    def value(self, q):
        time.sleep(self.slow)
        if self.fail:
            raise RuntimeError('gone')
        return 1

    def close(self):
        closed.append(self.n)


m.ONCE_PEER['gen'] = 1
m.SPLIT['peer_gen'] = 1
m.SPLIT['peer_db'] = FakeDb('first', slow=4.5, fail=True)
r1 = m._split_peer_probe()
ok('probe: a slow one gives up at 3.5 s', r1 == 'no answer within 3.5 s', r1)
second = FakeDb('second')
m.SPLIT['peer_db'] = second
time.sleep(1.5)            # the first one fails now
ok('probe: the late one closed its own', closed == ['first'], closed)
ok('probe: the next one\'s connection kept', m.SPLIT['peer_db'] is second)

print('ALL %d / %d' % (sum(R), len(R)))
