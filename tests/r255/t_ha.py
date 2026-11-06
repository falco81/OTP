"""t_ha.py - 1.0.255, group "ha": in-process with stubs, no PostgreSQL, no ports.
H1 a column added at run time waits only a moment for its table (PostgreSQL SET LOCAL
   lock_timeout inside its own transaction, MariaDB lock_wait_timeout set and put back);
   the start keeps the long wait; SQLite unchanged.
H2 the main loop never waits on the root helper: pgtls_send busy at once from the ticks,
   the pages wait as before; the old address's drop in a thread of its own.
H3 a rebuild that failed: maintenance written before the rebuilding flag is cleared.
H4 the TLS rescue only after 3 failures in a row, never for a restarting/refused database.
H6 the split watch on time.monotonic(): a clock stepped forward is not "apart"."""
import os, sys, re, json, time, threading, tempfile, contextlib, types
from pathlib import Path
PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]),
                             flush=True)


def src(f):
    return open(os.path.join(PARTS, f)).read()


def block(text, start, end=None):
    """The source from the line starting with `start` up to (not with) the next top-level def/class."""
    i = text.index(start)
    m = re.compile(r'^(def |class |[A-Z_]+ = |# ----)', re.M)
    j = m.search(text, i + len(start))
    return text[i:j.start() if j else len(text)]


LOGS = []


def log(msg, level='info'):
    LOGS.append((level, msg))


def log_sparing(key, msg, level='info', every=600):
    LOGS.append((level, msg))


# ============================== H1 ==========================================================
g = {'__name__': 'db', 'log': log, 'log_sparing': log_sparing, 'DB_FILE': Path('/nonexistent/otp.db'),
     'CONFIG': {}}
exec('import os, re, json, time, threading, contextlib, sqlite3, socket, hashlib\n'
     'from pathlib import Path\n' + src('20_db.py'), g)
Db, _Lane = g['Db'], g['_Lane']


class Conn(object):
    pass


class FakeDb(Db):
    """The real Db, its statements caught where they would reach the driver (_run)."""
    def __init__(self, engine, have=None, fail_alter=False):
        self.engine, self.statement_s, self.timeout = engine, 120, 10
        self._lanes = {'main': _Lane()}
        self._lanes_lock = threading.Lock()
        self._tls = threading.local()
        self.lanes_on = False
        self.host, self.port, self.name, self.user, self.password = '', 0, 'otp', 'otp', ''
        self.tls = self.tls_ca = None
        self.path = Path('/nonexistent')
        self.conn = Conn()
        self.sql = []
        self.have = have
        self.fail_alter = fail_alter
        self.lw = 86400

    def connect(self):
        self.conn = Conn()

    def columns(self, table):
        return list((self.have or {}).get(table, []))

    def _run(self, sql, args, fetch):
        s = str(sql)
        self.sql.append(s)
        if s.startswith('ALTER') and self.fail_alter:
            raise Exception('canceling statement due to lock timeout')
        if '@@SESSION.lock_wait_timeout' in s:
            return [{'v': self.lw}], 1, None
        m = re.match(r'SET SESSION lock_wait_timeout = (\S+)', s)
        if m:
            self.lw = m.group(1)
        return ([{'v': 1}] if fetch else None), 1, None


# Every column, learned by adding them all to a database that has none.
d0 = FakeDb('postgres', have={})
d0._add_missing_columns()
ALL = {}
for s in d0.sql:
    m = re.match(r'ALTER TABLE (\w+) ADD COLUMN (\w+)', s)
    if m:
        ALL.setdefault(m.group(1), ['id']).append(m.group(2))
ok('H1 the columns read off the schema', 'meta' in ALL and len(ALL) >= 5, ALL.keys())
tab = 'meta'
col = ALL[tab][-1]
short = {t: (c if t != tab else c[:-1]) for t, c in ALL.items()}


def alters(d):
    return [s for s in d.sql if s.startswith('ALTER')]


d = FakeDb('postgres', have=short)
d.add_missing_columns()
ok('H1 the start (PostgreSQL): the ALTER as before, no short wait, no transaction of its own',
   len(alters(d)) == 1 and alters(d)[0].startswith('ALTER TABLE %s ADD COLUMN %s ' % (tab, col))
   and not any('lock_timeout' in s or s == 'BEGIN' for s in d.sql), d.sql)

d = FakeDb('postgres', have=short)
d.add_missing_columns(short_wait=True)
i = [k for k, s in enumerate(d.sql) if s.startswith('ALTER')][0]
ok('H1 at run time (PostgreSQL): BEGIN, SET LOCAL lock_timeout 300ms, the ALTER, COMMIT',
   d.sql[i - 1] == "SET LOCAL lock_timeout = '300ms'" and 'BEGIN' in d.sql[i - 3:i - 1] and
   d.sql[i + 1] == 'COMMIT', d.sql)
ok('H1 ... the statement limit taken off and put back around it as before',
   'SET statement_timeout = 0' in d.sql and d.sql[-1] == 'SET statement_timeout = 120000', d.sql)

d = FakeDb('postgres', have=short, fail_alter=True)
d.columns_missing = True
LOGS[:] = []
got = d.add_columns_again()
ok('H1 add_columns_again: the table busy - rolled back, False, tried again later',
   got is False and d.columns_missing and 'ROLLBACK' in d.sql and not d.in_tx and
   "SET LOCAL lock_timeout = '300ms'" in d.sql, d.sql)
d.fail_alter = False
d.sql = []
ok('H1 ... the next try goes through: True', d.add_columns_again() is True and not d.columns_missing
   and "SET LOCAL lock_timeout = '300ms'" in d.sql, d.sql)

d = FakeDb('mariadb', have=short)
d.add_missing_columns(short_wait=True)
a = [k for k, s in enumerate(d.sql) if s.startswith('ALTER')][0]
ok('H1 at run time (MariaDB): lock_wait_timeout 1 before the ALTER, put back to what it was after',
   'SET SESSION lock_wait_timeout = 1' in d.sql[:a] and
   d.sql.index('SET SESSION lock_wait_timeout = 1') < a and
   'SET SESSION lock_wait_timeout = 86400' in d.sql[a:] and d.lw == '86400', d.sql)
d = FakeDb('mariadb', have=short)
d.add_missing_columns()
ok('H1 the start (MariaDB): no lock_wait_timeout touched', not any('lock_wait' in s for s in d.sql), d.sql)

d = FakeDb('sqlite', have=short)
d.add_missing_columns(short_wait=True)
ok('H1 SQLite: as before (one ALTER, nothing set)', len(alters(d)) == 1 and
   not any(s.startswith(('SET', 'BEGIN')) for s in d.sql), d.sql)

# ha_peer_columns: the short wait on the other node, a bool, the start's tries.
gh = {'log': log, 'time': types.SimpleNamespace(sleep=lambda s: None)}
ha_src = src('87_ha.py')
exec(block(ha_src, 'def ha_peer_columns():') + block(ha_src, 'def ha_peer_columns_start('), gh)
calls = []


class Far(object):
    def __init__(self, missing):
        self.missing = missing

    def add_missing_columns(self, short_wait=False):
        calls.append(short_wait)
        self.columns_missing = self.missing.pop(0)

    def close(self):
        pass


miss = [True, True, False]
gh['ha_peer_db'] = lambda: Far(miss)
ok('H1 ha_peer_columns_start: the short wait each time, tried until none is missing',
   gh['ha_peer_columns_start'](tries=5, gap_s=0) is True and calls == [True, True, True], calls)
calls[:] = []
miss[:] = [True] * 9
ok('H1 ... and gives up after its tries (the hourly one goes on)',
   gh['ha_peer_columns_start'](tries=3, gap_s=0) is False and len(calls) == 3)
dsrc = src('80_daemon.py')
ok('H1 the daemon starts ha_peer_columns_start; the main loop keeps add_columns_again',
   "target=ha_peer_columns_start" in dsrc and 'self.store.db.add_columns_again()' in dsrc)

# ============================== H2 ==========================================================
web = Path(tempfile.mkdtemp(prefix='t_ha_web-'))
t_src = src('87t_hatls.py')
gt = {'WEB_DIR': web, 'PGTLS_ASK': 'pgtls.ask', 'log': log, 'log_sparing': log_sparing}
i = t_src.index('PGTLS_LOCK = threading.Lock()')
j = t_src.index('def _hatls_ask(')
exec('import os, json, time, secrets, threading\n' + t_src[i:j], gt)
exec(block(t_src, 'def hatls_tick('), gt)
ask = web / 'pgtls.ask'
ask.write_text('{"id": "before"}')
t0 = time.monotonic()
try:
    gt['pgtls_send']({'id': 'x'}, wait_s=0)
    busy = False
except gt['PgtlsBusy']:
    busy = True
ok('H2 pgtls_send(wait_s=0) with a request not yet read: PgtlsBusy at once, nothing written over',
   busy and time.monotonic() - t0 < 0.3 and json.loads(ask.read_text())['id'] == 'before')
gt['PGTLS_WAIT'].s = 0
try:
    gt['pgtls_send']({'id': 'x'})
    busy = False
except gt['PgtlsBusy']:
    busy = True
del gt['PGTLS_WAIT'].s
ok('H2 ... the same when the thread says so (PGTLS_WAIT.s = 0, as hatls_tick from the loop sets)', busy)
threading.Timer(1.0, lambda: ask.unlink()).start()
t0 = time.monotonic()
gt['pgtls_send']({'id': 'page'})
took = time.monotonic() - t0
ok('H2 the pages and the command line: wait for the one before as ever, then write (%.1f s)' % took,
   0.8 < took < 5 and json.loads(ask.read_text())['id'] == 'page')
ask.unlink()
gt['PGTLS_LOCK'].acquire()
t0 = time.monotonic()
try:
    gt['pgtls_send']({'id': 'x'}, wait_s=0)
    busy = False
except gt['PgtlsBusy']:
    busy = True
gt['PGTLS_LOCK'].release()
ok('H2 another thread sending (lock held): busy at once, not waited for', busy and
   time.monotonic() - t0 < 0.3 and not ask.exists())
gt['pgtls_send']({'id': 'free'}, wait_s=0)
ok('H2 nothing waiting: written at once', json.loads(ask.read_text())['id'] == 'free')
ask.unlink()

seen = []
gt.update(CONFIG={'ha_mode': 'replicated'}, HATLS_LOCK=threading.Lock(), HATLS_CHECK={'next': 1e18},
          hatls_check=lambda st: None)


def fake_tick(store):
    seen.append(getattr(gt['PGTLS_WAIT'], 's', 30))
    raise gt['PgtlsBusy']('busy')


gt['_hatls_tick'] = fake_tick
store = types.SimpleNamespace(db=types.SimpleNamespace(engine='postgres'))
LOGS[:] = []
gt['hatls_tick'](store, ask_wait_s=0)
gt['hatls_tick'](store)
ok('H2 hatls_tick from the loop: its requests do not wait; from the pages: 30 s as before',
   seen == [0, 30], seen)
ok('H2 ... busy is no warning (the step again at the next pass), the thread\'s setting put back',
   not LOGS and getattr(gt['PGTLS_WAIT'], 's', None) is None and not gt['HATLS_LOCK'].locked(), LOGS)
ok('H2 the daemon\'s loop: hatls_tick(ask_wait_s=0), readdress_dropold_tick in background(\'dropold\')',
   'hatls_tick(self.store, ask_wait_s=0)' in dsrc and
   re.search(r"def dropold\(daemon=self\):\s+try:\s+readdress_dropold_tick\(daemon\.store\)", dsrc)
   and "self.background('dropold', dropold)" in dsrc and
   not re.search(r"^\s+readdress_dropold_tick\(self\.store\)", dsrc, re.M))
ok('H2 the server step makes no key while the helper is busy (from the loop)',
   "getattr(PGTLS_WAIT, 's', 30) <= 0 and _pgtls_ask_fresh()" in t_src)

# ============================== H3 ==========================================================
gr = {'threading': threading, 'log': log, 'TABLES': ['meta', 'tokens'], 'HA_REBUILDING': threading.Event(),
      'HA_REBUILDER': [None], 'MAINT_CACHE': {'at': 5.0, 'row': {'on': False}},
      'HA_REBUILD_FAILED_WHY': 'the rebuild failed', 'node_name': lambda: 'n1',
      'time': types.SimpleNamespace(sleep=lambda s: None, monotonic=time.monotonic, time=time.time)}
exec(block(ha_src, 'def _ha_rebuild('), gr)
for n in ('ha_sub_name',):
    gr[n] = lambda slot: 'sub%d' % slot
for n in ('ha_drop_sub', 'ha_drop_slot', 'ha_wait_copied', 'ha_sequences', 'ha_conninfo'):
    gr[n] = lambda *a, **k: None


def boom(*a, **k):
    raise RuntimeError('the copy failed')


gr['ha_subscribe'] = boom
at_write = []
events = []


def maintenance_set(store, on, why='', by='', name=None):
    # The real write guard (20_db): only the rebuilder's own thread writes while the flag is up.
    reb = gr['HA_REBUILDING']
    allowed = not reb.is_set() or gr['HA_REBUILDER'][0] == threading.get_ident()
    at_write.append((on, reb.is_set(), allowed))
    return {'on': bool(on), 'why': why, 'by': by, 'at': time.time()}


gr['maintenance_set'] = maintenance_set
gr['maintenance_row'] = lambda store: {'on': False}


class St(object):
    def add_event(self, kind, words, level='info', who=''):
        events.append((words, gr['HA_REBUILDING'].is_set()))


gr['HA_STORE'] = {'store': St()}


class Local(object):
    def rows(self, sql):
        return []

    def make_tables(self):
        pass

    def run(self, sql, args=()):
        pass

    def value(self, sql):
        return 0


try:
    gr['_ha_rebuild'](Local(), Local(), 1, 2, 'a', 5432, 'b', 5432, 'otp', 'otp', 'pw', lambda s: None)
    raised = False
except RuntimeError:
    raised = True
ok('H3 a rebuild that failed after emptying: maintenance written while the flag was still up, '
   'by the rebuilder (the write guard lets it through)',
   raised and at_write == [(True, True, True)], at_write)
ok('H3 ... the flag cleared after it, the cache already "in maintenance" for RADIUS',
   not gr['HA_REBUILDING'].is_set() and gr['HA_REBUILDER'][0] is None and
   gr['MAINT_CACHE']['row'].get('on') and gr['MAINT_CACHE']['row'].get('why') == 'the rebuild failed')
ok('H3 ... and its event written once the flag is down', any('in maintenance' in w and not up
                                                              for w, up in events), events)
at_write[:] = []
events[:] = []
gr['ha_subscribe'] = lambda *a, **k: None
gr['maintenance_row'] = lambda store: {'on': True, 'why': 'the rebuild failed'}
gr['_ha_rebuild'](Local(), Local(), 1, 2, 'a', 5432, 'b', 5432, 'otp', 'otp', 'pw', lambda s: None)
ok('H3 a rebuild that went through: back in service after the flag, as before',
   at_write == [(False, False, True)] and not gr['HA_REBUILDING'].is_set(), at_write)

# ============================== H4 ==========================================================
dt_src = src('87d_dbtls.py')
gd = {'log': log, 'log_sparing': log_sparing, 'CONFIG': {'db_tls': 'verify-full', 'db_tls_ca': '/x/ca.pem'},
      'dbtls_kind': lambda: 'local', 'hisec_enforced': lambda k, s: False}
i = dt_src.index('DBTLS_WORK = {')
j = dt_src.index('DBTLS_MODES')
exec('import threading, time\nDBTLS_LOCK = threading.Lock()\n' + dt_src[i:j], gd)
gd['time'] = time
exec(block(dt_src, 'def _dbtls_rescue('), gd)
exec(block(ha_src, 'def peer_db_restarting('), gd)
PROBE = {}
moved = []


def dbtls_probe(mode, ca):
    r = PROBE['tls' if mode else 'plain']
    return {'ok': True} if r is True else {'ok': False, 'said': r}


def wfs(d):
    moved.append(d)


gd.update(dbtls_probe=dbtls_probe, write_file_settings=wfs, _dbtls_reconnect=lambda *a: None,
          dbtls_publish=lambda *a, **k: None)


class DDb(object):
    err = 'SSL error: certificate verify failed'

    def value(self, sql):
        if self.err:
            raise Exception(self.err)
        return 1


ddb = DDb()
daemon = types.SimpleNamespace(store=types.SimpleNamespace(db=ddb, add_event=lambda *a, **k: None))


def look(n):
    for _ in range(n):
        gd['DBTLS_WORK']['rescue'] = 0.0      # the 10 s between looks
        gd['_dbtls_rescue'](daemon)


PROBE.update(tls='FATAL: the database system is starting up', plain=True)
ddb.err = 'terminating connection due to administrator command'
look(6)
ok('H4 PostgreSQL restarting (starting up): never rescued, however often', not moved and
   gd['CONFIG']['db_tls'] == 'verify-full')
PROBE.update(tls='could not connect to server: Connection refused', plain=True)
ddb.err = 'connection refused'
look(6)
ok('H4 ... refused: never rescued', not moved)
PROBE.update(tls='SSL error: certificate verify failed', plain=True)
ddb.err = 'SSL SYSCALL error'
look(1)
ok('H4 a real TLS failure: not after 1 look', not moved and gd['DBTLS_WORK']['fails'] == 1)
PROBE['tls'] = True
look(1)
ok('H4 ... TLS going again in between starts the count again', gd['DBTLS_WORK']['fails'] == 0)
PROBE['tls'] = 'SSL error: certificate verify failed'
look(1)
PROBE['tls'] = 'FATAL: the database system is shutting down'
look(1)
ok('H4 ... a restart in between too', not moved and gd['DBTLS_WORK']['fails'] == 0)
PROBE['tls'] = 'SSL error: certificate verify failed'
look(2)
ok('H4 two looks in a row: moved to no TLS (RADIUS first), as before',
   moved == [{'db_tls': '', 'db_tls_ca': ''}] and gd['CONFIG']['db_tls'] == '' and
   gd['DBTLS_WORK'].get('rescued'))
gd['CONFIG'].update(db_tls='verify-full')
moved[:] = []
ddb.err = None
look(1)
ok('H4 the connection working: nothing done, count 0', not moved and gd['DBTLS_WORK']['fails'] == 0)

# ============================== H6 ==========================================================
class Clock(object):
    def __init__(self):
        self.wall, self.mono = 1.7e9, 5000.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def sleep(self, s):
        pass


CLK = Clock()
gs = {'log': log, 'log_sparing': log_sparing, 'time': CLK, 'json': json, 'threading': threading,
      'CONFIG': {'ha_mode': 'replicated', 'ha_peer': '192.0.2.2', 'split_mode': 'priority',
                 'split_after_s': 20},
      'MAINT_CACHE': {'at': 0}, 'ONCE_PEER': {'down_until': 0.0, 'gen': 0}, 'ONCE_PEER_LOCK': threading.Lock(),
      'once_peer_forget': lambda: None, 'human_span': lambda s: '%ds' % s, 'fnum': lambda x, d=0.0: float(x or d),
      'node_name': lambda: 'n1', 'node_ask_kind': lambda k: (lambda f: f)}
exec('import re, os, socket, subprocess, ipaddress, struct, select\n' + src('87y_split.py'), gs)
gs['time'] = CLK
gs.update(split_engaged=lambda: True, split_active=lambda: True, split_mode=lambda: 'priority',
          split_me_preferred=lambda: False, split_preferred_unable=lambda store: '',
          split_arbiter_check=lambda: ([], None), default_gateway=lambda: '', split_frozen=lambda: False,
          split_peer_caught_up=lambda store: True, split_report=lambda store, now: None,
          _split_event=lambda *a: None)
PEER = {'p': True}
gs['_split_peer_probe'] = lambda: PEER['p']
rows = {}


class SSt(object):
    db = types.SimpleNamespace(rows=lambda *a: [], run=lambda *a: 0, value=lambda *a: None)

    def set_meta(self, k, v):
        rows[k] = json.loads(v)


sst = SSt()
SP = gs['SPLIT']
SP['peer_ok_at'] = CLK.mono
gs['split_step'](sst)
ok('H6 together: serving', not SP['apart_since'] and SP['role'] == 'serve')
CLK.wall += 3600                      # NTP steps the clock an hour forward
CLK.mono += 2
PEER['p'] = 'no answer within 3.5 s'  # one look the other node does not answer
gs['split_step'](sst)
ok('H6 the clock stepped an hour forward and one look unanswered: not apart, not aside',
   not SP['apart_since'] and SP['role'] == 'serve', SP)
CLK.mono += 25
CLK.wall += 25
gs['split_step'](sst)
ok('H6 really unanswered for 27 s (monotonic): apart, this node steps aside',
   SP['apart_since'] and SP['role'] == 'aside')
ok('H6 ... apart_since on the wall clock, when it last answered (for the pages)',
   abs(SP['apart_since'] - (CLK.wall - 27)) < 0.01, (SP['apart_since'], CLK.wall))
st_row = rows.get('split:state:n1') or {}
ok('H6 ... its row: at and peer_ok_at on the wall clock',
   abs(st_row.get('at', 0) - CLK.wall) < 0.01 and abs(st_row.get('peer_ok_at', 0) - (CLK.wall - 27)) < 0.01,
   st_row)
CLK.wall -= 7200                      # stepped back two hours while apart
CLK.mono += 2
gs['split_step'](sst)
ok('H6 the clock stepped back while apart: still apart', SP['apart_since'] and SP['role'] == 'aside')
PEER['p'] = True
CLK.mono += 2
CLK.wall += 2
LOGS[:] = []
gs['split_step'](sst)
ok('H6 the other node answers: together, serving; the time apart by the monotonic clock (31 s)',
   not SP['apart_since'] and SP['role'] == 'serve' and any('after 31s' in m for _, m in LOGS), LOGS)
ok('H6 ... the report due on the monotonic clock, together_at on the wall clock',
   abs(SP['report_due'] - (CLK.mono + 30)) < 0.01 and abs(SP['together_at'] - CLK.wall) < 0.01)
# The older tests give `now` alone: both clocks are it.
SP.update(peer_ok_at=1000.0, apart_since=0.0, role='serve', report_due=0.0, written=0.0)
PEER['p'] = 'x'
gs['split_step'](sst, now=1005.0, peer='x', arbiter=None)
a = bool(SP['apart_since'])
gs['split_step'](sst, now=1030.0, peer='x', arbiter=None)
ok('H6 the tests\' own `now`: not apart at 5 s, apart at 30 s, as before',
   not a and SP['apart_since'] == 1000.0 and SP['role'] == 'aside')
gs['split_step'](sst, now=1032.0, peer=True, arbiter=None)
ok('H6 ... together again at once', not SP['apart_since'] and SP['role'] == 'serve')

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
