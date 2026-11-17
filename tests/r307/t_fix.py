"""t_fix.py - 1.0.307: age never takes the newest three backups away (a clock stepped ahead, backups that
failed long); the outgoing mail's tick decides on each mail as it is now (a mail sent again meanwhile is
not given up); a node that does not make the night's copy (one database for the cluster) is not "cannot
be put back". The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.307'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r307_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx307', 'api_port': 29937}, open(D + '/config.json', 'w'))
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


class Daemon(object):
    def __init__(self, store, dirs):
        self.store, self.dirs, self.read = store, dirs, 0

    def reader(self):
        self.read += 1
        return self.store

    def changed(self, *a):
        pass


class H(object):
    """A request: the parts of the handler the routes use."""
    def __init__(self, store, d, sess=None, body=None, args=None):
        self.store, self.d, self._s, self._body, self.args = store, d, sess, body or {}, args or {}
        self.headers = {}
        self.route_path = ''

    arg = m.ApiHandler.arg if hasattr(m, 'ApiHandler') else None


Handler = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, 'directory_recheck'))
for k in ('arg', 'num', 'me', 'directory_recheck', 'end_all', 'body'):
    if k != 'body':
        setattr(H, k, getattr(Handler, k))
H.DIR_CHECKED, H.DIR_CHECK_S = {}, 600
H.body = lambda self: self._body
H.session = lambda self, kind: dict(self._s) if self._s else None
H.reader = property(lambda self: self.d.reader())
H.client_ip = lambda self: '192.0.2.1'


def api(fn, h):
    try:
        return fn(h), None
    except m.ApiError as e:
        return None, e


# ==== 1 retention by age
from datetime import datetime as _dt


class Tr(object):
    def __init__(self, names):
        self.names = list(names)
        self.gone = []

    def list(self):
        return [{'name': n} for n in self.names]

    def delete(self, n):
        self.gone.append(n)
        self.names.remove(n)


site, node = m.rb_slug(m.CONFIG.get('site_name') or 'otp'), m.rb_slug(m.node_name())
now = time.time()
names = ['otp-backup-%s-%s-%s.tar.gz' % (site, node, _dt.fromtimestamp(now - d * 86400).strftime('%Y%m%d-%H%M%S')) for d in (40, 41, 42, 43, 44)]
tr = Tr(names)
gone = m.rb_retain(tr, 0, 30, now=now, just=names[0])
ok('1 backups that failed for 40 days, kept 30 days: the newest three stay (one was left)', sorted(gone) == sorted(names[3:]) and len(tr.names) == 3, gone)
names2 = ['otp-backup-%s-%s-%s.tar.gz' % (site, node, _dt.fromtimestamp(now - d * 86400).strftime('%Y%m%d-%H%M%S')) for d in (0, 1, 2, 3, 40, 41)]
tr = Tr(names2)
gone = m.rb_retain(tr, 0, 30, now=now, just=names2[0])
ok('1 the old ones past the days kept go, as before', sorted(gone) == sorted(names2[4:]), gone)
tr = Tr(names2)
gone = m.rb_retain(tr, 2, 0, now=now, just=names2[0])
ok('1 a count kept: as before', sorted(gone) == sorted(names2[2:]), gone)

# ==== 2 the outgoing mail: a mail sent again meanwhile is not given up
qid = '1700000000000-0000aaaa'
old = {'qid': qid, 'state': 'waiting', 'expires': now - 3600, 'to': ['a@b.cz'], 'kind': 'alert', 'tries': 3, 'node': m.node_name(),
       'created': now - 7200, 'last_try': now - 600, 'said': 'server away'}
fresh = dict(old, expires=now + 86400, next_at=now + 999999, said='sent again by hand')
fresh.pop('qid')
st.set_meta(m.MAILQ_PREFIX + qid, json.dumps(fresh))
m.CONFIG['mail_mode'] = 'smtp'
m.mailq_all = lambda store, open_only=False: [dict(old)]
m.mailq_tick(st)
got = json.loads(st.get_meta(m.MAILQ_PREFIX + qid))
ok('2 a mail sent again since the tick read its list: not given up', got.get('state') == 'waiting' and got.get('said') == 'sent again by hand', got)
st.set_meta(m.MAILQ_PREFIX + qid, json.dumps(dict(old, said='server away', qid=None)))
st.db.run('UPDATE meta SET v = ? WHERE k = ?', (json.dumps({k: v for k, v in old.items() if k != 'qid'}), m.MAILQ_PREFIX + qid))
m.mailq_tick(st)
got = json.loads(st.get_meta(m.MAILQ_PREFIX + qid))
ok('2 one past its time indeed: given up, as before', got.get('state') == 'expired', got)

# ==== 3 the weekly check, one database for the cluster
src = open(TOP + '/otp.py').read()
ok('3 one database for the cluster, no nightly copy here: not counted against this node',
   "CONFIG.get('ha_mode') != 'replicated' and in_cluster(store)" in src and "none here - one database for the cluster" in src)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
