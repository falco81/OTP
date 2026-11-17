"""t_upgrade.py - 1.0.299: the upgrade at a glance in every status (upgrade_brief: running, ended
lately, not cancelled, not old); otp_upgrade.py's file for the pages (written whole, 0644, never
through a link, nothing where the folder is not root's alone). In-process, SQLite - no ports.

    python3 t_upgrade.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.299'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r299_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx299', 'api_port': 29999}, open(D + '/config.json', 'w'))
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


# ==== 1 upgrade_brief
now = time.time()
ok('1 no plan: nothing', m.upgrade_brief(st) is None)


def plan(state_b, at_b, cancelled=False, ident='p1'):
    p = {'id': ident, 'version': '9.9.9', 'sha': 'x', 'order': ['na', 'nb'], 'by': 'admin', 'at': min(now - 100, at_b - 200),
         'from': 'nb', 'downgrade': False, 'was': '1.0.1'}
    if cancelled:
        p['cancelled'] = {'by': 'admin', 'at': now}
    st.set_meta('upgrade:plan', json.dumps(p))
    st.set_meta('upgrade:node:na', json.dumps({'id': ident, 'state': 'done', 'at': at_b - 50, 'said': 'x' * 900}))
    st.set_meta('upgrade:node:nb', json.dumps({'id': ident, 'state': state_b, 'at': at_b, 'part': 3, 'part_words': 'The pages'}))
    m.UPG_BRIEF['at'] = -10


plan('installing', now)
b = m.upgrade_brief(st)
ok('1 running: the version, where from, who, the steps', b and b['state'] == 'running' and b['version'] == '9.9.9' and b['from'] == '1.0.1'
   and b['by'] == 'admin' and [s['name'] for s in b['steps']] == ['na', 'nb'] and b['steps'][1]['part_words'] == 'The pages', b)
ok('1 ...a long "said" cut', b and len(b['steps'][0]['said']) == 300, b and len(b['steps'][0].get('said', '')))
st.set_meta('upgrade:plan', json.dumps({'id': 'p1', 'version': '9.9.8'}))
ok('1 ...read again only after 2 s', m.upgrade_brief(st)['version'] == '9.9.9')
plan('done', now - 60)
b = m.upgrade_brief(st)
ok('1 done a minute ago: still said (ended)', b and b['state'] == 'done' and b['ended'] > 0, b)
plan('failed', now - 30)
ok('1 failed lately: said', (m.upgrade_brief(st) or {}).get('state') == 'failed')
plan('done', now - 3600)
ok('1 done an hour ago: nothing', m.upgrade_brief(st) is None)
plan('failed', now - 30)
st.set_meta('upgrade:seen', 'p1')
ok('1 failed lately but hidden (Hide this): nothing', m.upgrade_brief(st) is None)
st.set_meta('upgrade:seen', '')
plan('waiting', now, cancelled=True)
ok('1 cancelled: nothing', m.upgrade_brief(st) is None)
d = Daemon(st, None)
d.status = lambda: {'node': 'fx299'}


class HS(H):
    def me(self, *a):
        return dict(self._s)


plan('installing', now)
r, e = api(m._status, HS(st, d, {'name': 'admin', 'role': 'fulladmin'}))
ok('1 every status carries it', e is None and (r or {}).get('upgrading', {}).get('version') == '9.9.9', e or r)
st.set_meta('upgrade:plan', 'not json')
m.UPG_BRIEF['at'] = -10
r, e = api(m._status, HS(st, d, {'name': 'admin', 'role': 'fulladmin'}))
ok('1 a plan that does not read: the status as ever', e is None and r.get('upgrading') is None, e)

# ==== 2 otp_upgrade.py: the pages' file
spec2 = importlib.util.spec_from_file_location('otp_upgrade', BUILD + '/out/otp-%s/deploy/otp_upgrade.py' % _OUTV)
up = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(up)
W = TOP + '/www'
os.makedirs(W)
os.chmod(W, 0o755)
up.PAGES_FILE = W + '/.upgrade.json'
up.pages_tell('running', 'k1', '9.9.9', by='admin', part=1, words='root checks the package\x07', frm='1.0.1', started=now)
got = up.pages_said()
ok('2 written: the state, the words without control characters', got.get('state') == 'running' and got.get('words') == 'root checks the package'
   and got.get('id') == 'k1' and got.get('from') == '1.0.1' and got.get('started') == int(now), got)
ok('2 ...0644, read by the pages', (os.stat(up.PAGES_FILE).st_mode & 0o777) == 0o644)
ok('2 ...no temporary file left', sorted(os.listdir(W)) == ['.upgrade.json'], os.listdir(W))
os.unlink(up.PAGES_FILE)
target = TOP + '/elsewhere'
open(target, 'w').write('keep')
os.symlink(target, up.PAGES_FILE)
up.pages_tell('failed', 'k1', '9.9.9', said='no')
ok('2 a link in its place: replaced, never followed', open(target).read() == 'keep' and not os.path.islink(up.PAGES_FILE)
   and up.pages_said().get('state') == 'failed')
os.chmod(W, 0o777)
up.pages_tell('done', 'k1', '9.9.9')
ok('2 a folder others may write to: nothing written', up.pages_said().get('state') == 'failed')
os.chmod(W, 0o755)
up.PAGES_FILE = TOP + '/none/.upgrade.json'
up.pages_tell('running', 'k1', '9.9.9')
ok('2 no folder (no pages here): nothing, no error', not os.path.exists(up.PAGES_FILE))

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
