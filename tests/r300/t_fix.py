"""t_fix.py - 1.0.300: SELinux asked of a node - "put right" with ids only, a rule taken away by its id,
each a step said in Events, never two at once; the root helper asked with them; how many the card puts
right said with the problems. The parts loaded as a module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.300'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r300_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx300', 'api_port': 29930}, open(D + '/config.json', 'w'))
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


# ==== 1 selinux_ask
me = m.node_name()
I = ['0123456789ab', 'abcdef012345']


def ask(*a, **kw):
    try:
        m.selinux_ask(st, *a, **kw)
        return ''
    except ValueError as e:
        return str(e)


for bad, why in ((None, 'none'), ('abc', 'a string'), ([], 'empty'), (['xyz'], 'not hex'), (['0123456789ab;'], 'more'),
                 (['0123456789AB'], 'capitals'), (['0123456789ab'] * 301, 'too many')):
    ok('1 fix refused: %s' % why, 'ids' in ask(me, 'fix', 'admin', ids=bad))
ok('1 rule_drop refused without an id', 'its id' in ask(me, 'rule_drop', 'admin', rule='x; rm -rf'))
ok('1 fix asked: no error', ask(me, 'fix', 'admin', ids=I + [I[0]]) == '')
w = json.loads(st.get_meta('host:selinux:want:' + me))
ok('1 ...the row: fix, the ids once each, who', w['do'] == 'fix' and w['ids'] == sorted(set(I)) and w['by'] == 'admin' and 'rule' not in w, w)
ev = st.db.rows("SELECT * FROM events ORDER BY id DESC LIMIT 1")
ok('1 ...said in Events', ev and 'put right 2 thing(s)' in (ev[0].get('message') or ev[0].get('text') or str(dict(ev[0]))), ev and dict(ev[0]))
ok('1 another step while it is not done: refused', 'not done the step' in ask(me, 'rule_drop', 'admin', rule=I[0]))
ok('1 ...a look is not written over it', ask(me, 'check', 'admin') == '' and json.loads(st.get_meta('host:selinux:want:' + me))['do'] == 'fix')
st.set_meta('host:selinux:now:' + me, json.dumps({'done': w['id'], 'data': {}}))
ok('1 done: a rule taken away may be asked', ask(me, 'rule_drop', 'admin', rule=I[0]) == '')
w = json.loads(st.get_meta('host:selinux:want:' + me))
ok('1 ...the row: rule_drop, its id', w['do'] == 'rule_drop' and w['rule'] == I[0] and 'ids' not in w, w)
ok('1 an unknown node refused', 'no node' in ask('nosuch', 'fix', 'admin', ids=I))

# ==== 2 selinux_tick asks the helper with them
SENT = []
m.root_ask = lambda a, b, data, wait=60: (SENT.append(data), {'mode': 'Permissive', 'said': ['rule %s taken away' % I[0]]})[1]
m.SE_WORK.update(busy=False, tried='')
d = Daemon(st, None)
m.selinux_tick(d)
for _ in range(50):
    if SENT and not m.SE_WORK['busy']:
        break
    time.sleep(0.1)
ok('2 the helper asked: rule_drop, its id, who', SENT and SENT[-1].get('do') == 'rule_drop' and SENT[-1].get('rule') == I[0]
   and SENT[-1].get('by') == 'admin' and 'ids' not in SENT[-1], SENT[-1:])
now = json.loads(st.get_meta('host:selinux:now:' + me))
ok('2 ...done, what it said kept', now.get('done') == w['id'] and now.get('action') == 'rule_drop' and now.get('said'), now)
st.set_meta('host:selinux:want:' + me, json.dumps({'id': 'f1', 'do': 'fix', 'ids': I, 'by': 'admin', 'at': time.time()}))
m.SE_WORK.update(busy=False, tried='')
m.selinux_tick(d)
for _ in range(50):
    if len(SENT) > 1 and not m.SE_WORK['busy']:
        break
    time.sleep(0.1)
ok('2 fix: the ids sent, nothing else of what to do', SENT[-1].get('do') == 'fix' and SENT[-1].get('ids') == I and 'rule' not in SENT[-1], SENT[-1:])

# ==== 3 the problems say how many the card puts right
st.set_meta('host:selinux:now:' + me, json.dumps({'data': {'mode': 'Permissive', 'problems': ['SELinux refused 5 thing(s) since the machine started'],
                                                          'counts': {'boolean': 1, 'rule': 2, 'nobutton': 1, 'other': 3}}}))
p = m.selinux_problems(st)
ok('3 "3 of what SELinux refused can be put right on the card"', any(x.startswith('3 of what SELinux refused can be put right') for x in p), p)
st.set_meta('host:selinux:now:' + me, json.dumps({'data': {'mode': 'Permissive', 'problems': []}}))
ok('3 nothing refused: as before (ready for enforcing)', m.selinux_problems(st) == ['SELinux is permissive: nothing is refused - otp is ready for enforcing'])

# ==== 4 the API
s_admin = {'name': 'admin', 'role': 'fulladmin'}


class HS(H):
    def me(self, *a):
        return dict(self._s)


st.set_meta('host:selinux:now:' + me, json.dumps({'done': 'f1', 'data': {}}))
r, e = api(m._selinux_do, HS(st, d, s_admin, body={'node': me, 'action': 'fix', 'ids': [I[1]]}))
ok('4 POST fix: asked', e is None and 'puts right what was selected' in r['message'], e)
st.set_meta('host:selinux:now:' + me, json.dumps({'done': json.loads(st.get_meta('host:selinux:want:' + me))['id'], 'data': {}}))
r, e = api(m._selinux_do, HS(st, d, s_admin, body={'node': me, 'action': 'fix', 'ids': ['../../etc']}))
ok('4 POST fix with something else than ids: 400', e is not None and e.status == 400, r)
r, e = api(m._selinux_do, HS(st, d, s_admin, body={'node': me, 'action': 'rule_drop', 'rule': I[1]}))
ok('4 POST rule_drop: asked', e is None and 'takes the rule away' in r['message'], e)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
