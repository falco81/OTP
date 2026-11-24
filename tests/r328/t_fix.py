"""t_fix.py - 1.0.328: a copy of the database read in one transaction; the last full administrator
not taken away by two at once; port 80's names for the ACME CA kept as otp's own set; the database
agent does not begin what the node stopped waiting for.

    python3 t_fix.py VERSION
"""
import gzip, importlib.util, json, os, re, shutil, sqlite3, sys, tempfile, threading, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.328'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r328_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx328', 'api_port': 29958}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 the copy: one moment
for i in range(3):
    st.db.run('INSERT INTO tokens (name) VALUES (?)', ('t%d' % i,))
dbfile = st.db.conn.execute('PRAGMA database_list').fetchall()[0][2]
other = sqlite3.connect(dbfile, isolation_level=None, timeout=5)
first = m.TABLES[0]
real_rows = st.db.rows
done = {'n': 0}


def rows_then_write(sql, args=()):
    got = real_rows(sql, args)
    if done['n'] == 0 and first in sql:
        done['n'] = 1
        # another connection writes while the copy is being read: a token more
        other.execute("INSERT INTO tokens (name) VALUES ('late')")
    return got


st.db.rows = rows_then_write
out = TOP + '/copy.json.gz'
m.dump_tables(st.db, out, child=True)
st.db.rows = real_rows
names = [json.loads(l).get('name') for l in gzip.open(out, 'rt') if '"name"' in l]
ok('copy (child): the write made while it read is not in it', 'late' not in names and 't2' in names, names[:10])
ok('copy: the write is in the database all the same', st.db.value("SELECT COUNT(*) FROM tokens WHERE name = 'late'") == 1)
ok('copy: the transaction ended', not getattr(st.db, 'in_tx', False))
st.db.run("INSERT INTO tokens (name) VALUES ('after')")
ok('copy: writes go on afterwards', st.db.value("SELECT COUNT(*) FROM tokens WHERE name = 'after'") == 1)
# not a child: as before, no transaction
calls = []
st.db.run, real_run = (lambda sql, args=(), **k: calls.append(sql) or real_run(sql, args, **k)), st.db.run
m.dump_tables(st.db, TOP + '/c2.json.gz', tables=['tokens'])
st.db.run = real_run
ok('copy (not a child): no transaction, as before', not any('BEGIN' in c for c in calls), calls)
src = open(V + '/otp.py').read()
ok('copy: PostgreSQL REPEATABLE READ READ ONLY, MariaDB a consistent snapshot',
   "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY" in src and 'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY' in src)
# a copy that fails half way: rolled back
st.db.rows = lambda sql, args=(): (_ for _ in ()).throw(RuntimeError('broke'))
try:
    m.dump_tables(st.db, TOP + '/c3.json.gz', child=True); e = None
except RuntimeError as x:
    e = x
st.db.rows = real_rows
ok('copy: broken half way - said, the transaction ended', e is not None and not getattr(st.db, 'in_tx', False))
st.db.run("INSERT INTO tokens (name) VALUES ('after2')")
ok('copy: ...and writes go on', st.db.value("SELECT COUNT(*) FROM tokens WHERE name = 'after2'") == 1)

# ==== 2 the last full administrator, two at once
st.add_account('anna', 'fulladmin', 'Anna-Pass-328-long!', must_change=0)
st.add_account('bert', 'fulladmin', 'Bert-Pass-328-long!', must_change=0)


def other_takes_anna():
    # the other tab / node: anna switched off between the check and the count
    st.db.run("UPDATE accounts SET disabled = 1 WHERE LOWER(name) = 'anna'")


try:
    st.fulladmin_change(lambda: (st.set_account('bert', disabled=1), other_takes_anna()),
                        lambda: st.set_account('bert', disabled=0)); e = None
except ValueError as x:
    e = x
ok('two at once: refused', e is not None and 'last full administrator' in str(e), e)
ok('two at once: bert put back', not st.account('bert')['disabled'])
st.db.run("UPDATE accounts SET disabled = 0 WHERE LOWER(name) = 'anna'")
st.fulladmin_change(lambda: st.set_account('bert', role='readonly'), lambda: st.set_account('bert', role='fulladmin'))
ok('one left all the same: done', st.account('bert')['role'] == 'readonly')
st.set_account('bert', role='fulladmin')
# threads: each takes the other away at once, many times - never nobody
lost = []
for i in range(30):
    st.set_account('anna', disabled=0); st.set_account('bert', disabled=0)
    bar = threading.Barrier(2)

    def take(who):
        bar.wait()
        try:
            st.fulladmin_change(lambda: st.set_account(who, disabled=1), lambda: st.set_account(who, disabled=0))
        except ValueError:
            pass
    ts = [threading.Thread(target=take, args=(n,)) for n in ('anna', 'bert')]
    [t.start() for t in ts]; [t.join() for t in ts]
    if not st.fulladmins_left():
        lost.append(i)
ok('two threads, 30 times: somebody always left', not lost, lost)
ok('the pages: counted again after the change', 'h.store.fulladmin_change(' in src)
ok('the command line: counted again after the change', 'store.fulladmin_change(' in src.split('def cli_main', 1)[1])

# ==== 3 ACME's names on port 80
os.makedirs(TOP + '/hs', exist_ok=True)
os.environ['OTP_STATE'] = TOP + '/hs'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
tpl = open(V + '/deploy/nginx-otp.conf').read().replace('otp.example.local', 'host1.corp')


def sn(t):
    a, b = W.http_block(t)
    blk = t[a:b]
    return re.search(r'server_name\s+([^;]*);', blk).group(1)


ok('acme off, never on: the file as it is', W.acme_into(tpl, []) == tpl)
a = W.acme_into(tpl, ['vip.corp', 'host1.corp'])
ok('acme on: its names added', sn(a) == 'host1.corp vip.corp', sn(a))
b = W.acme_into(a, ['vip2.corp', 'host1.corp'])
ok('the VIP renamed: the old name gone', sn(b) == 'host1.corp vip2.corp', sn(b))
ok('...again the same: nothing changed', W.acme_into(b, ['vip2.corp', 'host1.corp']) == b)
c = W.acme_into(b, [])
ok('acme off: its names taken away', sn(c) == 'host1.corp' and 'otp-acme-names' not in c, sn(c))
ok('...off again: nothing changed', W.acme_into(c, []) == c)
old = tpl.replace('server_name host1.corp;', 'server_name host1.corp oldvip.corp vip.corp;', 1)
d = W.acme_into(old, ['vip.corp'])
ok('a file from before: names of old orders gone, install.sh\'s kept', sn(d) == 'host1.corp vip.corp', sn(d))
ok('...the HTTPS server untouched', d.count('server_name host1.corp;') == 1)
hand = tpl.replace('server_name host1.corp;', 'server_name host1.corp alias.corp;', 1)
ok('names put by hand, ACME never on: left', W.acme_into(hand, []) == hand)
src_web = open(V + '/otp.py').read()
ok('the daemon says none when ACME is off', "out['acme'] = acme_http_names(store) if CONFIG.get('acme') else []" in src_web)

# ==== 4 the agent: not begun once the node stopped waiting
sys.argv = ['otp-db-agent']
spec = importlib.util.spec_from_file_location('otp_db_agent', V + '/deploy/otp_db_agent.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
r = A.Root.__new__(A.Root)
r.stopping, r.work, r.busy = False, threading.Lock(), None
ran = []


class Ops:
    Refused = A.otp_pg_ops.Refused if hasattr(A, 'otp_pg_ops') else ValueError

    @staticmethod
    def run_op(op, args, c):
        ran.append(op)
        return {'said': 'done'}


r.ops, r.c = Ops, {}
try:
    r.long_op('pg_allow', {}, 'n1', until=time.monotonic() - 1); e = None
except Exception as x:                                  # noqa: BLE001
    e = x
ok('agent: the node stopped waiting - not begun', e is not None and 'not done' in str(e) and not ran, (e, ran))
r.long_op('pg_allow', {}, 'n1', until=time.monotonic() + 60)
ok('agent: within the wait - done', ran == ['pg_allow'])
r.long_op('pg_allow', {}, 'n1')
ok('agent: a node of an earlier version (no wait said) - done as before', ran == ['pg_allow', 'pg_allow'])
r.work.acquire()
res = {}


def behind():
    try:
        r.long_op('pgtls', {}, 'n2', until=time.monotonic() + 0.3); res['x'] = 'done'
    except Exception as x:                              # noqa: BLE001
        res['x'] = str(x)


t = threading.Thread(target=behind); t.start(); time.sleep(0.8); r.work.release(); t.join()
ok('agent: waiting behind another past its time - refused', 'not done' in res['x'] and ran.count('pgtls') == 0, res)
ok('the node says how long it waits', "'wait_s': max(5, int(timeout) - 5)" in src)
cs = json.load(open(V + '/web/lang/cs.json'))
ok('its words in Czech', any(v['source'].startswith('{0} waited for another operation') and v['text']
                             for v in cs['patterns'].values()))
print('ALL %d / %d' % (sum(R), len(R)))
