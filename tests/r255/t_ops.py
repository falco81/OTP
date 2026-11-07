"""t_ops.py - 1.0.255 (ops): B1 backups' history and each destination's last word kept per node
and read merged (with the rows of the versions before); B2 'mine' needs the site too, nodes named
alike said and nothing taken away; B3 room for a backup of PostgreSQL / MariaDB; B4 a destination
named is tried even when switched off; B5 ACME not ordered for the short host name before DNS
answered; N1/N2 a network going back is not refused (shared database, a restart under way), a
restart is refused while a new network waits to be kept; N3 search domains and DNS servers checked
as root checks them, this node's settings put back when root refused the request."""
import os, sys, re, json, time, sqlite3, tempfile, threading, types, shutil, socket, ipaddress
import secrets
from pathlib import Path

PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


TMP = Path(tempfile.mkdtemp(prefix='t-ops-'))


class DB(object):
    def __init__(self, engine='sqlite'):
        self.c = sqlite3.connect(':memory:', check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)')
        self.engine = engine
        self.path = str(TMP / 'otp.db')
        self.sz = 0

    def rows(self, q, a=()):
        return [dict(r) for r in self.c.execute(q, a).fetchall()]

    def value(self, q, a=()):
        r = self.c.execute(q, a).fetchone()
        return r[0] if r else None

    def run(self, q, a=()):
        return self.c.execute(q, a).rowcount

    def upsert(self, t, key, row):
        self.c.execute('INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)', (row['k'], row['v']))

    def size(self):
        return self.sz


class Store(object):
    def __init__(self, engine='sqlite'):
        self.db = DB(engine)
        self.events = []

    def get_meta(self, k, d=None):
        v = self.db.value('SELECT v FROM meta WHERE k = ?', (k,))
        return d if v is None else v

    def set_meta(self, k, v):
        self.db.upsert('meta', 'k', {'k': k, 'v': str(v)})

    def drop_meta(self, k):
        return self.db.run('DELETE FROM meta WHERE k = ?', (k,))

    def add_event(self, *a, **k):
        self.events.append(a)

    def settings_saved(self):
        return {}


NODE = ['A']
NODES = []          # ha_nodes() answer
LOGS = []


def fnum(x, d=0.0):
    try:
        return float(x or d)
    except (TypeError, ValueError):
        return d


def json_obj(text, kind=dict):
    try:
        got = json.loads(text) if text else None
    except (ValueError, TypeError):
        return None
    return got if isinstance(got, kind) else None


def _meta_json(store, k, kind=dict):
    return json_obj(store.get_meta(k), kind)


def hatls_version(v):
    out = []
    for x in re.split(r'[.-]', str(v or '')):
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return tuple(out)


def plain_ip(text, how='network'):
    said = str(text or '').strip()
    if not re.match(r'^[0-9A-Fa-f:.]+(/[0-9]{1,3})?\Z', said):
        raise ValueError('not plain')
    got = {'address': ipaddress.ip_address, 'interface': ipaddress.ip_interface,
           'network': lambda t: ipaddress.ip_network(t, strict=False)}[how](said)
    if '%' in str(got):
        raise ValueError('scope')
    return got


CONFIG = {'site_name': 'site1'}
FILE_CONFIG = {}
g = {'__name__': 'ops', 'CONFIG': CONFIG, 'FILE_CONFIG': FILE_CONFIG, 'STATE_DIR': TMP,
     'WEB_DIR': TMP, 'fnum': fnum, 'json_obj': json_obj, '_meta_json': _meta_json,
     'odict': lambda v: v if isinstance(v, dict) else {},
     'hatls_version': hatls_version, 'plain_ip': plain_ip,
     'node_name': lambda: NODE[0], 'ha_nodes': lambda store: list(NODES),
     'host_nodes': lambda store: [NODE[0]] + [n['name'] for n in NODES if n['name'] != NODE[0]],
     'log': lambda *a, **k: LOGS.append(a), 'log_sparing': lambda *a, **k: None,
     'BACKUP_ROOM_MIN': 128 << 20, 'scrub_secret': lambda s: s,
     'route': lambda *a, **k: (lambda f: f)}
HEAD = ('import os, re, json, time, secrets, shutil, socket, ipaddress, threading, tempfile, '
        'subprocess, hashlib, zlib\nfrom pathlib import Path\nfrom datetime import datetime, '
        'timedelta\n')
for f in ('86b_rbackup.py', '86v_verify.py', '87n_net.py', '87x_trial.py', '88a_acme.py'):
    src = open(os.path.join(PARTS, f)).read()
    exec(compile(HEAD + src, f, 'exec'), g)

# ---- B1: the history, a row for each node ------------------------------------------------
st = Store()
NODE[0] = 'A'
g['rb_history_add'](st, {'at': 100.0, 'node': 'A', 'file': 'a1', 'ok': True, 'bytes': 10})
NODE[0] = 'B'
g['rb_history_add'](st, {'at': 200.0, 'node': 'B', 'file': 'b1', 'ok': False})
keys = sorted(r['k'] for r in st.db.rows('SELECT k FROM meta'))
ok('B1 each node writes its own row of runs', keys == ['rbackup:runs:A', 'rbackup:runs:B'], keys)
h = g['rb_history'](st)
ok('B1 read merged, newest first', [r['file'] for r in h] == ['b1', 'a1'], h)
# the row of the versions before: read too, each run once
st.set_meta('rbackup:runs', json.dumps([{'at': 50.0, 'node': 'A', 'file': 'old'},
                                        {'at': 100.0, 'node': 'A', 'file': 'a1', 'ok': True},
                                        'junk']))
h = g['rb_history'](st)
ok('B1 the old shared row read too, each run once',
   [r['file'] for r in h] == ['b1', 'a1', 'old'], [r['file'] for r in h])
# the alerts read the newest of each node first
mine = [r for r in h if r.get('node') == 'A']
ok('B1 the alerts see a node\'s newest first', mine[0]['file'] == 'a1')
# a node of a version before in the cluster: its row said too (only an existing row)
NODES[:] = [{'name': 'B'}, {'name': 'C', 'version': '1.0.254'}]
g['rb_history_add'](st, {'at': 300.0, 'node': 'B', 'file': 'b2', 'ok': True})
old = json.loads(st.get_meta('rbackup:runs'))
ok('B1 mirrored into the old row while an old node is there', old[0]['file'] == 'b2', old[:1])
ok('B1 mirrored run read once', [r['file'] for r in g['rb_history'](st)].count('b2') == 1)
st2 = Store()
g['rb_history_add'](st2, {'at': 300.0, 'node': 'B', 'file': 'b2'})
ok('B1 the old row never made here', st2.get_meta('rbackup:runs') is None)
NODES[:] = [{'name': 'B', 'version': '1.0.255'}, {'name': 'A', 'version': '1.0.255'}]
g['rb_history_add'](st, {'at': 400.0, 'node': 'B', 'file': 'b3'})
ok('B1 not mirrored once every node is new',
   json.loads(st.get_meta('rbackup:runs'))[0]['file'] == 'b2')
NODES[:] = []
# forget one line of the other node's row, and one of the old row
n = g['rb_history_forget'](st, 100.0, 'a1')
ok('B1 forget a line of another node (and of the old row)', n == 2 and 'a1' not in
   [r['file'] for r in g['rb_history'](st)], n)
n = g['rb_history_forget'](st)
ok('B1 forget all', not g['rb_history'](st) and n > 0, g['rb_history'](st))
# keep 60 per node
NODE[0] = 'A'
for i in range(70):
    g['rb_history_add'](st, {'at': 1000.0 + i, 'node': 'A', 'file': 'x%d' % i})
ok('B1 60 kept per node', len(json.loads(st.get_meta('rbackup:runs:A'))) == 60)

# ---- B1: last / tried per node per destination --------------------------------------------
st = Store()
tg = [{'id': 't1', 'kind': 'folder', 'name': 'F', 'enabled': 1,
       'last': {'at': 10.0, 'ok': True, 'file': 'legacy'}},
      {'id': 't2', 'kind': 'folder', 'name': 'G', 'enabled': 0}]
g['rb_put_targets'](st, tg)
before = st.get_meta('rbackup:targets')
NODE[0] = 'A'
ok('B1 last put for a destination', g['rb_status_put'](st, 't1', 'last', {'at': 20.0, 'ok': True}))
NODE[0] = 'B'
g['rb_status_put'](st, 't1', 'last', {'at': 30.0, 'ok': False, 'error': 'x'})
g['rb_status_put'](st, 't2', 'tried', {'at': 5.0, 'ok': True})
ok('B1 no word kept of a destination not there', not g['rb_status_put'](st, 'zz', 'last', {}))
ok('B1 rbackup:targets not rewritten', st.get_meta('rbackup:targets') == before)
ok('B1 rows per node', st.get_meta('rbackup:last:A:t1') and st.get_meta('rbackup:last:B:t1'))
w = {t['id']: t for t in g['rb_with_status'](st)}
ok('B1 last: the newest of any node', w['t1']['last']['at'] == 30.0 and
   w['t1']['last']['node'] == 'B', w['t1'])
ok('B1 last of each node', sorted(w['t1']['last_nodes']) == ['A', 'B'])
ok('B1 tried merged', w['t2']['tried']['at'] == 5.0)
st.drop_meta('rbackup:last:B:t1')
st.drop_meta('rbackup:last:A:t1')
w = {t['id']: t for t in g['rb_with_status'](st)}
ok('B1 the word kept by a version before still read', w['t1']['last']['file'] == 'legacy')
g['rb_status_put'](st, 't1', 'last', {'at': 40.0, 'ok': True})
g['rb_delete'](st, 't1', 'me')
ok('B1 rows of a destination taken away go with it', st.get_meta('rbackup:last:B:t1') is None)
ok('B1 rows of the others stay', st.get_meta('rbackup:tried:B:t2') is not None)

# ---- B2: mine needs the site; nodes named alike ----------------------------------------------
NODE[0] = 'otp1'
CONFIG['site_name'] = 'site1'


class Tr(object):
    def __init__(self, files):
        self.files = list(files)
        self.gone = []

    def open(self):
        pass

    def close(self):
        pass

    def list(self):
        return [{'name': n, 'size': 1} for n in self.files]

    def delete(self, n):
        self.gone.append(n)
        self.files.remove(n)


files = ['otp-backup-site1-otp1-20260101-010101.tar.gz.enc',
         'otp-backup-site2-otp1-20260102-010101.tar.gz.enc',
         'otp-backup-site1-otp2-20260103-010101.tar.gz.enc']
tr = Tr(files)
g['rb_transport'] = lambda t: tr
st = Store()
g['rb_put_targets'](st, [{'id': 't1', 'kind': 'folder', 'name': 'F', 'enabled': 1}])
got = {x['name']: x['mine'] for x in g['rb_remote_list'](st, 't1')}
ok('B2 mine: this node of this site only', got == {files[0]: True, files[1]: False,
                                                   files[2]: False}, got)
tr2 = Tr(files + ['otp-backup-site2-otp1-20250101-010101.tar.gz.enc',
                  'otp-backup-site1-otp1-20250101-010101.tar.gz.enc'])
gone = g['rb_retain'](tr2, 1, 0, now=time.mktime((2026, 2, 1, 0, 0, 0, 0, 0, -1)))
ok('B2 retain takes only this site\'s', gone == ['otp-backup-site1-otp1-20250101-010101.tar.gz.enc'],
   gone)
ok('B2 clashes found', g['rb_slug_clashes'](['otp-1', 'otp_1', 'x', 'OTP.2', 'otp.2']) ==
   [['otp-1', 'otp_1'], ['OTP.2', 'otp.2']], g['rb_slug_clashes'](['otp-1', 'otp_1']))
NODE[0] = 'otp-1'
NODES[:] = [{'name': 'otp-1'}, {'name': 'otp_1'}]
ok('B2 this node\'s clash', g['rb_slug_clash'](st) == ['otp_1'])
NODES[:] = [{'name': 'otp-1'}, {'name': 'otp2'}]
ok('B2 no clash', g['rb_slug_clash'](st) == [])
NODES[:] = []
ok('B2 standalone: no clash', g['rb_slug_clash'](st) == [])
src86b = open(os.path.join(PARTS, '86b_rbackup.py')).read()
ok('B2 nothing taken away on a clash', "if clash:\n                        raise RbError(run['warning'])"
   in src86b)
ok('B2 alert for a clash', 'rb_slug_clashes(names)' in open(os.path.join(PARTS, '88z_alerts.py')).read())

# ---- B3: room for PostgreSQL / MariaDB ------------------------------------------------------
real_shutil = g['shutil']


class FakeShutil(object):
    def __init__(self, free):
        self.free = free

    def disk_usage(self, p):
        return types.SimpleNamespace(free=self.free)

    def __getattr__(self, k):
        return getattr(real_shutil, k)


NODE[0] = 'A'
for eng in ('postgres', 'mariadb'):
    st = Store(eng)
    st.db.sz = 500 << 20
    g['shutil'] = FakeShutil(1000 << 20)
    try:
        g['rb_room'](st)
        said = ''
    except g['RbError'] as e:
        said = str(e)
    ok('B3 %s: no backup yet - as before, not refused by the database\'s own size' % eng, 'no room' not in said, said)
    g['rb_history_add'](st, {'at': 1.0, 'node': 'A', 'bytes': 100 << 20, 'ok': True})
    try:
        g['rb_room'](st)
        said = ''
    except g['RbError'] as e:
        said = str(e)
    ok('B3 %s: the last backup\'s size counted' % eng, said == '', said)
    g['shutil'] = FakeShutil(300 << 20)
    try:
        g['rb_room'](st)
        said = ''
    except g['RbError'] as e:
        said = str(e)
    ok('B3 %s: 2 x the last backup + the minimum needed' % eng, 'no room' in said and '328 MB' in said,
       said)
st = Store('postgres')
g['shutil'] = FakeShutil(200 << 20)
try:
    g['rb_room'](st)
    ok('B3 an empty database, room enough', True)
except g['RbError'] as e:
    ok('B3 an empty database, room enough', False, e)
g['shutil'] = real_shutil

# ---- B4: a destination named is tried even when off ---------------------------------------
st = Store()
g['rb_put_targets'](st, [{'id': 'off1', 'kind': 'folder', 'name': 'Off', 'enabled': 0}])
seen = []


def fake_list(store, tid):
    seen.append(tid)
    raise g['RbError']('the folder is not there')


g['rb_remote_list'] = fake_list
g['kept_dumps'] = lambda engine: []
try:
    res = g['rb_verify'](st, 'me', 'off1')
    ok('B4 named and switched off: tried', seen == ['off1'] and res['target'] == 'off1', res)
except Exception as e:                                  # noqa: BLE001
    ok('B4 named and switched off: tried', False, e)
try:
    g['rb_verify'](st, 'me')
    ok('B4 none named: switched on ones only', False)
except g['RbError'] as e:
    ok('B4 none named: switched on ones only', 'switched on' in str(e), e)
try:
    g['rb_verify'](st, 'me', 'nope')
    ok('B4 no such destination', False)
except g['RbError'] as e:
    ok('B4 no such destination', 'no such' in str(e), e)

# ---- B5: ACME, not for the short host name before DNS answered ------------------------------
started = []


class FakeThread(object):
    def __init__(self, target=None, name='', daemon=None, args=()):
        self.target = target
        started.append(self)

    def start(self):
        pass


fake_threading = types.SimpleNamespace(Thread=FakeThread, Lock=threading.Lock,
                                       local=threading.local)
g['threading'] = fake_threading
g['vip_conf'] = lambda store: {}
g['tls_profile'] = lambda store, t: {'info': {'cn': 'old.example.cz'}}
g['acme_care'] = lambda store, t: True
g['alerts_lead'] = lambda store: True
CONFIG.update(acme=1, acme_for='node')
st = Store()
NODE[0] = 'otp1'
g['FQDN_CACHE'].update(name='', at=0.0, asking=False)
ok('B5 before DNS answered: no name for this node',
   g['acme_name_of'](st, 'otp1', answered=True) == '')
ok('B5 before DNS answered: not among the targets', g['acme_targets'](st, answered=True) == [])
ok('B5 the question asked of DNS meanwhile', len(started) == 1)
ok('B5 without answered: as before (the host name)',
   g['acme_name_of'](st, 'otp1') == socket.gethostname())
g['FQDN_CACHE'].update(name='otp1.example.cz', at=time.monotonic(), asking=False)
ok('B5 once answered: the full name', g['acme_targets'](st, answered=True) ==
   [('otp1', 'otp1.example.cz')], g['acme_targets'](st, answered=True))
g['FQDN_CACHE'].update(name='', at=0.0, asking=False)
CONFIG['acme_node_name'] = 'given.example.cz'
ok('B5 a name given is used at once', g['acme_targets'](st, answered=True) ==
   [('otp1', 'given.example.cz')])
CONFIG.pop('acme_node_name')
# the tick: looked at again within a minute when skipped
g['ACME_WORK'].update(busy=False, at=0.0)
g['ACME_HOST']['at'] = time.time()
g['ACME_ARI']['at'] = time.time()
starts = []
g['acme_start'] = lambda store, due, by: starts.append(due)
g['acme_due'] = lambda store, t, n: 'not ordered yet for %s' % n
started[:] = []
g['acme_tick'](types.SimpleNamespace(store=st))
look = [t for t in started if t.target and t.target.__name__ == 'look'][0]
look.target()
ok('B5 the tick orders nothing before DNS answered', starts == [], starts)
ok('B5 looked at again within a minute',
   time.time() - g['ACME_WORK']['at'] >= g['ACME_EVERY'] - 61, g['ACME_WORK']['at'])
g['FQDN_CACHE'].update(name='otp1.example.cz', at=time.monotonic(), asking=False)
look.target()
ok('B5 ordered once DNS answered', starts == [[('otp1', 'otp1.example.cz')]], starts)
g['threading'] = threading

# ---- N1 / N2 / N3: the network -----------------------------------------------------------
NODE[0] = 'n1'


def now_row(store, node='n1', ip='192.0.2.10/24', host='n1.example.cz'):
    store.set_meta('net:now:' + node, json.dumps({'at': time.time(), 'data': {
        'nm': True, 'con': 'eth0', 'devices': [{'con': 'eth0', 'dev': 'eth0'}],
        'hostname': host, 'conf': {'ipv4_addresses': [ip], 'ipv4_method': 'manual'}}}))


IN_CLUSTER = [True]
g['in_cluster'] = lambda store: IN_CLUSTER[0]
g['osup_plan'] = lambda store: {}
g['upgrade_plan'] = lambda store: {}
want = {'con': 'eth0', 'ipv4': {'addr': '192.0.2.20/24', 'gw': '192.0.2.1', 'dns': ['192.0.2.53'],
                                'search': ['example.cz']},
        'ipv6': {'on': False}, 'hostname': 'n1.example.cz'}
CONFIG['ha_mode'] = 'shared'
st = Store()
now_row(st)
NODES[:] = [{'name': 'n1', 'me': True}, {'name': 'n2', 'address': '192.0.2.11'}]
try:
    g['net_check'](st, 'n1', want)
    ok('N1 shared database: a new address asks for the tick', False)
except ValueError as e:
    ok('N1 shared database: a new address asks for the tick', 'share one database' in str(e), e)
try:
    got = g['net_check'](st, 'n1', want, rollback=True)
    ok('N1 shared database: going back is not refused', got['ip_changed'])
except ValueError as e:
    ok('N1 shared database: going back is not refused', False, e)
# N2: a restart under way
st.set_meta('power:plan', json.dumps({'id': 'p1', 'how': 'reboot', 'targets': ['n2'],
                                      'at': time.time()}))
ok('N2 power busy', g['power_busy'](st))
try:
    g['net_ask'](st, 'n1', want, 'me')
    ok('N2 a new network refused while a restart is under way', False)
except ValueError as e:
    ok('N2 a new network refused while a restart is under way', 'restart' in str(e), e)
try:
    ask = g['net_ask'](st, 'n1', want, 'otp', rollback=True)
    ok('N2 going back asked while a restart is under way', ask['rollback'] and
       st.get_meta('net:want:n1'))
except ValueError as e:
    ok('N2 going back asked while a restart is under way', False, e)
st.drop_meta('power:plan')
# a node on trial: no restart planned
for state in ('trial', 'going back'):
    st.set_meta('net:job:n2', json.dumps({'id': 'j', 'state': state, 'at': time.time(),
                                         'moved': time.time(), 'trial_until': time.time() + 600}))
    try:
        g['power_ask'](st, 'reboot', ['n1'], 'one', 'me')
        ok('N2 a restart refused while %s is %s' % ('n2', state), False)
    except ValueError as e:
        ok('N2 a restart refused while %s is %s' % ('n2', state), 'waits to be kept' in str(e), e)
st.set_meta('net:job:n2', json.dumps({'id': 'j', 'state': 'done', 'at': time.time()}))
IN_CLUSTER[0] = False
try:
    g['power_ask'](st, 'reboot', ['n1'], 'one', 'me')
    ok('N2 a restart asked when no network waits', True)
except ValueError as e:
    ok('N2 a restart asked when no network waits', False, e)
st.set_meta('net:job:n2', json.dumps({'id': 'j', 'state': 'trial', 'at': 1.0, 'moved': 1.0,
                                     'trial_until': 2.0}))
ok('N2 a trial long over does not count', not g['net_job_on_trial'](
    json.loads(st.get_meta('net:job:n2'))))
ok('N2 trial not active for net_ask (its own going back)', not g['net_job_active'](
    {'state': 'trial', 'at': time.time()}))

# N3: as root checks them
CONFIG['ha_mode'] = ''
NODES[:] = []
st = Store()
now_row(st)
for bad, what in ((['example.cz.'], 'search'), (['exa mple'], 'search'), (['-x.cz'], 'search')):
    w = json.loads(json.dumps(want))
    w['ipv4']['search'] = bad
    try:
        g['net_check'](st, 'n1', w)
        ok('N3 search domain %r refused' % bad, False)
    except ValueError as e:
        ok('N3 search domain %r refused' % bad, 'not a search domain' in str(e), e)
    got = g['net_check'](st, 'n1', w, rollback=True)
    ok('N3 going back: %r left out' % bad, got['ipv4']['search'] == [], got['ipv4'])
w = json.loads(json.dumps(want))
w['ipv4']['search'] = ['example.cz', 'Sub.Example.cz']
ok('N3 good search domains taken', g['net_check'](st, 'n1', w)['ipv4']['search'] ==
   ['example.cz', 'Sub.Example.cz'])
w = json.loads(json.dumps(want))
w['ipv6'] = {'on': True, 'mode': 'auto', 'dns': ['fe80::1%eth0']}
try:
    g['net_check'](st, 'n1', w)
    ok('N3 an IPv6 DNS server with a zone id refused', False)
except ValueError as e:
    ok('N3 an IPv6 DNS server with a zone id refused', 'DNS server' in str(e), e)
ok('N3 going back: left out', g['net_check'](st, 'n1', w, rollback=True)['ipv6']['dns'] == [])
w['ipv6'] = {'on': True, 'mode': 'auto', 'dns': ['2001:db8::53'], 'gw': 'fe80::1%eth0'}
try:
    g['net_check'](st, 'n1', w)
    ok('N3 an IPv6 gateway with a zone id refused', False)
except ValueError as e:
    ok('N3 an IPv6 gateway with a zone id refused', 'IPv6 gateway' in str(e), e)
w['ipv6'] = {'on': True, 'mode': 'auto', 'dns': ['2001:db8::53']}
ok('N3 a good IPv6 DNS server taken', g['net_check'](st, 'n1', w)['ipv6']['dns'] == ['2001:db8::53'])
w = json.loads(json.dumps(want))
w['ipv4']['dns'] = [' 192.0.2.53 ', '1.1.1.1']
ok('N3 good DNS servers taken', g['net_check'](st, 'n1', w)['ipv4']['dns'] == ['192.0.2.53', '1.1.1.1'])

# N3: the job stops on root's refusal - this node's settings put back
SAVED = []


class Daemon(object):
    def __init__(self, store):
        self.store = store

    def save_settings(self, ch, by='', node=''):
        SAVED.append(dict(ch))
        CONFIG.update(ch)


def write_file_settings(d):
    FILE_CONFIG.update(d)


g['write_file_settings'] = write_file_settings
g['net_cert_again'] = lambda store, w, by: ''
g['maintenance_set'] = lambda *a, **k: None
g['maintenance_row'] = lambda store: {}
g['boot_time'] = lambda: 1.0


def run_job(root_says):
    st = Store()
    now_row(st)
    CONFIG.update(radius_bind='192.0.2.10', db_host='192.0.2.10', node_name='n1')
    FILE_CONFIG.clear()
    FILE_CONFIG.update(node_name='n1', db_host='192.0.2.10')
    SAVED[:] = []

    def root(data, wait=60):
        raise ValueError(root_says)
    g['net_root'] = root
    chk = g['net_check'](st, 'n1', want)
    g['net_job_run'](Daemon(st), {'id': 'j1', 'want': chk, 'by': 'me'})
    return json.loads(st.get_meta('net:job:n1'))


job = run_job("'example.cz.' is not a domain")
ok('N3 root refused: the job failed', job['state'] == 'failed')
# 1.0.262: radius_bind is saved only once root took the network - nothing to put back then.
ok('N3 root refused: settings put back', CONFIG['radius_bind'] == '192.0.2.10' and
   (not SAVED or SAVED[-1] == {'radius_bind': '192.0.2.10'}), (CONFIG.get('radius_bind'), SAVED))
ok('N3 root refused: config.json put back', FILE_CONFIG.get('db_host') == '192.0.2.10', FILE_CONFIG)
ok('N3 root refused: said that nothing changed',
   'nothing of the network was changed' in job['steps'][-1]['what'], job['steps'][-1])
job = run_job('nmcli connection modify: Error: failed')
ok('N3 root failed half way: not put back (the network may have changed)',
   CONFIG['radius_bind'] == '192.0.2.20' and FILE_CONFIG.get('db_host') == '192.0.2.20',
   (CONFIG.get('radius_bind'), FILE_CONFIG))
ok('N3 refusals before any change known', g['net_root_refused_first'](
    "'fe80::1%eth0' is not the address of a DNS server") and g['net_root_refused_first'](
    'the host name is the whole name: otp1.example.cz') and not g['net_root_refused_first'](
    'hostnamectl set-hostname: failed'))
ok('N3 the same NAME_RE as root', g['NET_DOMAIN_RE'].pattern == re.search(
    r"NAME_RE = re\.compile\(r'([^']*)'\s*\n\s*r'([^']*)'\)", open(
        '/home/claude/build/out/otp-%s/deploy/otp_web.py' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.255')).read()).expand(r'\1\2'))

shutil.rmtree(str(TMP), ignore_errors=True)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
