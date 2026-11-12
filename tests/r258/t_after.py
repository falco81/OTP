"""t_after.py - 1.0.258, "after the update": what an update cannot do itself, kept until it is done.
The registry (an entry added, a bad one refused), every check with stub facts, each node's own row
(HA: one writer a row), Done for a manual one and for an automatic one (kept for its sig, taken back
when it changes, an automatic one coming back after it went), what went by itself, the alert
problems (English and Czech), the routes, the tick, the CLI, root-facts.json as install.sh writes it,
the wiring (build.sh, index.php, admin.js, the console, the CLI) and the Czech. Pure Python: parts
exec'd with stubs - no daemon, no ports, no database.

    cd /tmp && python3 t_after.py 1.0.258
"""
import ast, contextlib, datetime, hashlib, io, json, os, re, secrets, shutil, subprocess, sys, tempfile
import threading, time
from pathlib import Path

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.258'
BUILD = '/home/claude/build'
PARTS = BUILD + '/parts'
OUT = '%s/out/otp-%s' % (BUILD, VER)
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]))


def src_of(fname):
    return open(os.path.join(PARTS, fname), encoding='utf-8').read()


def defs(fname, names):
    text = src_of(fname)
    tree = ast.parse(text)
    lines = text.splitlines(True)
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            out.append(''.join(lines[node.lineno - 1:node.end_lineno]))
    missing = set(names) - set(re.findall(r'^(?:def|class) (\w+)', ''.join(out), re.M))
    assert not missing, missing
    return '\n\n'.join(out)


TMP = Path(tempfile.mkdtemp(prefix='t_after_'))
LIB = TMP / 'lib'
LIB.mkdir()
(LIB / 'otp_upgrade.py').write_text('# stub\n')
STATE = TMP / 'state'
STATE.mkdir()
os.environ['OTP_ROOT_FACTS'] = str(LIB / 'root-facts.json')
os.environ['OTP_AFTER_TEST'] = str(STATE / 'after-test.json')


# ---- a database of meta rows, and who wrote each ----------------------------------------------
class DB:
    def __init__(self, st):
        self.st = st

    def rows(self, sql, args=()):
        m = re.search(r"FROM meta WHERE k LIKE '([^%']*)%'", sql)
        if not m or 'mailq' in sql:
            return []
        return [{'k': k, 'v': v} for k, v in sorted(self.st.meta.items()) if k.startswith(m.group(1))]


class Store:
    def __init__(self):
        self.meta, self.writers, self.events = {}, {}, []
        self.db = DB(self)

    def get_meta(self, k, default=None):
        return self.meta.get(k, default)

    def set_meta(self, k, v):
        self.meta[k] = v
        self.writers.setdefault(k, set()).add(NODE[0])

    def drop_meta(self, k):
        self.meta.pop(k, None)

    def add_event(self, kind, words, level='info', who=''):
        self.events.append((kind, words, level, who))


NODE = ['otp1']
CLUSTER = [False]
PHP = [{'version': '', 'fixed': None}]
SE_ASKED = []
g = {'__name__': 'ta', '__version__': VER, 'datetime': datetime.datetime, 'os': os, 're': re, 'json': json, 'time': time,
     'threading': threading, 'hashlib': hashlib, 'secrets': secrets, 'Path': Path,
     'UPGRADE_HELPER': LIB / 'otp_upgrade.py', 'STATE_DIR': STATE, 'CONFIG': {},
     'node_name': lambda: NODE[0], 'in_cluster': lambda store=None: CLUSTER[0],
     'ha_nodes': lambda store: [{'name': n, 'me': n == NODE[0], 'alive': True}
                                for n in (('otp1', 'otp2') if CLUSTER[0] else (NODE[0],))],
     'log_sparing': lambda key, words, level='warn', every=30: print('    (log) ' + words),
     'php_state': lambda: dict(PHP[0]),
     'selinux_ask': lambda store, node, action, by: SE_ASKED.append((node, action, by)),
     'cli_who': lambda: 'command line'}
exec(defs('00_head.py', ['json_obj', 'odict', 'fnum', 'stamp']), g)
exec(defs('88_upgrade.py', ['_meta_json']), g)
exec(defs('88o_online.py', ['_ver_tuple']), g)
exec(src_of('88n_after.py'), g)
AFTER = g['AFTER']
F = lambda **k: dict({'node': NODE[0], 'version': VER, 'cluster': CLUSTER[0], 'installed': True,
                      'root': {'installer': VER, 'at': 1}, 'selinux': {}, 'cil': 'aa', 'cil_in': 'aa',
                      'upgrade_helper': True, 'upgrade_path': True, 'php': {}, 'test': {}}, **k)
E = {e['id']: e for e in AFTER}


def ck(i, f):
    got = E[i]['check'](None, f)
    return got if isinstance(got, tuple) else (got, {})


# ---- the registry ------------------------------------------------------------------------------
ids = [e['id'] for e in AFTER]
ok('registry: the entries of 1.0.258 are there', set(ids) >= {
    'root-parts', 'upgrade-helper', 'nginx-additions', 'nginx-upload-guard', 'selinux-module',
    'selinux-refused', 'php2shell', 'firewall-by-hand', 'test-auto', 'test-manual'}, ids)
ok('registry: ids unique, every entry whole', len(ids) == len(set(ids)) and all(
    e['level'] in ('bad', 'warn', 'info') and e['ack'] in ('auto', 'manual') and e['title'] and e['why']
    and callable(e['check']) and e['since'] and e.get('foot') for e in AFTER))
ok('registry: every step is a command as root or a pane', all(
    (st.get('where') == 'root' and st.get('cmd')) or (st.get('where') == 'pages' and st.get('pane'))
    for e in AFTER for st in e['steps']))
ok('registry: never advises switching SELinux off', not any(
    re.search(r'setenforce 0|SELINUX=disabled|selinux=0|permissive$', ' '.join(st.get('cmd', '') for st in e['steps']))
    for e in AFTER) and all('Do not switch SELinux off' in E[i]['why'] for i in ('selinux-module', 'selinux-refused')))
try:
    g['after_entry'](id='root-parts', since='1.0.259', level='bad', ack='auto', title='x', why='y',
                     check=lambda s, f: 'na')
    dup = False
except ValueError:
    dup = True
try:
    g['after_entry'](id='x', since='1.0.259', level='loud', ack='auto', title='x', why='y', check=lambda s, f: 'na')
    badlvl = False
except ValueError:
    badlvl = True
ok('registry: a second entry of one id, or a level not known, refused', dup and badlvl)

# ---- each check, with stub facts --------------------------------------------------------------
ok('root-parts: not put in by install.sh (a folder) - not asked', ck('root-parts', F(installed=False))[0] == 'na')
st, det = ck('root-parts', F(root=None))
ok('root-parts: no root-facts.json (install.sh before 1.0.258) - needed',
   st == 'needed' and det['args']['had'] == 'an install.sh older than 1.0.258', det)
st, det = ck('root-parts', F(root={'installer': '1.0.257'}))
ok('root-parts: install.sh 1.0.257 under otp %s - needed, sig its version' % VER, st == 'needed' and det['sig'] == '1.0.257')
ok('root-parts: install.sh of this version or newer - done', ck('root-parts', F())[0] == 'done' and
   ck('root-parts', F(root={'installer': '1.0.300'}))[0] == 'done')
ok('root-parts: a file that is not JSON - needed', ck('root-parts', F(root={}))[0] == 'needed')
ok('upgrade-helper: otp-upgrade.path missing - needed; there - done',
   ck('upgrade-helper', F(upgrade_path=False))[0] == 'needed' and ck('upgrade-helper', F())[0] == 'done')
st, det = ck('nginx-additions', F(root={'installer': VER, 'nginx': {'additions': 'failed', 'at': 77}}))
ok('nginx-additions: nginx refused them - needed, sig when', st == 'needed' and det['sig'] == '77')
ok('nginx-additions: taken - done', ck('nginx-additions', F(root={'nginx': {'additions': 'ok'}}))[0] == 'done')
ok('nginx-upload-guard: refused - needed', ck('nginx-upload-guard', F(root={'nginx': {'guard': 'failed'}}))[0] == 'needed')
ok('selinux-module: SELinux disabled or absent - not asked',
   ck('selinux-module', F(selinux={'mode': 'Disabled', 'module': False}))[0] == 'na' and ck('selinux-module', F())[0] == 'na')
st, det = ck('selinux-module', F(selinux={'mode': 'Enforcing', 'module': False}))
ok('selinux-module: enforcing, not in the policy - needed, bad', st == 'needed' and det['level'] == 'bad')
st, det = ck('selinux-module', F(selinux={'mode': 'Permissive', 'module': True}, cil='new', cil_in='old'))
ok('selinux-module: permissive, older in the policy - needed, warn', st == 'needed' and det['level'] == 'warn')
ok('selinux-module: the one beside the program in the policy - done',
   ck('selinux-module', F(selinux={'mode': 'Enforcing', 'module': True}))[0] == 'done')
st, det = ck('selinux-refused', F(selinux={'mode': 'Enforcing', 'denials': {'total': 3}}))
ok('selinux-refused: enforcing, 3 refused - needed, grows', st == 'needed' and det['sig'] == '3' and det['grows'])
ok('selinux-refused: nothing refused, or permissive - not needed',
   ck('selinux-refused', F(selinux={'mode': 'Enforcing', 'denials': {'total': 0}}))[0] == 'done' and
   ck('selinux-refused', F(selinux={'mode': 'Permissive', 'denials': {'total': 9}}))[0] == 'na')
ok('php2shell: not fixed - needed; fixed or no PHP - not',
   ck('php2shell', F(php={'version': '8.3.10', 'fixed': False}))[0] == 'needed' and
   ck('php2shell', F(php={'version': '8.3.30', 'fixed': True}))[0] == 'done' and ck('php2shell', F())[0] == 'na')
ok('firewall-by-hand: firewalld was not there - needed (manual)',
   ck('firewall-by-hand', F(root={'firewall': {'state': 'none', 'at': 5}}))[0] == 'needed' and E['firewall-by-hand']['ack'] == 'manual'
   and ck('firewall-by-hand', F(root={'firewall': {'state': 'firewalld'}}))[0] == 'na')
ok('test hooks: off without the file', ck('test-auto', F())[0] == 'na' and ck('test-manual', F())[0] == 'na')
ok('test hooks: on with it', ck('test-auto', F(test={'auto': 'needed'}))[0] == 'needed' and
   ck('test-auto', F(test={'auto': 'done'}))[0] == 'done' and ck('test-manual', F(test={'manual': 'needed'}))[0] == 'needed')

# ---- the words filled in ----------------------------------------------------------------------
it = g['after_item'](E['root-parts'], F(root=None), ck('root-parts', F(root=None))[1])
ok('words: title and why filled in, in English and Czech', it['title'] == 'otp %s is running, but the parts root installs are from before it' % VER
   and 'an install.sh older than 1.0.258' in it['why'] and 'install.sh starší než 1.0.258' in it['cs']['why']
   and it['cs']['title'].startswith('Běží otp %s' % VER), it)
ok('words: the command and where - standalone', it['steps'][0]['cmd'] == './install.sh --upgrade' and
   it['steps'][0]['lead'] == 'As root, in the folder the otp-%s package was unpacked in:' % VER, it['steps'])
CLUSTER[0] = True
it2 = g['after_item'](E['selinux-refused'], F(), {'sig': '3', 'args': {'n': 3}})
ok('words: in a cluster the node is in the lead',
   it2['steps'][0]['lead'] == 'As root, on otp1 - what is refused, and what otp needs:' and
   g['after_item'](E['firewall-by-hand'], F(), {})['steps'][0]['lead'] == 'As root, on otp1, with firewalld:', it2['steps'])
CLUSTER[0] = False
ok('words: nothing left as a {placeholder}', not any(re.search(r'\{[a-z_]+\}', json.dumps(
    g['after_item'](e, F(root={'installer': '1.0.1', 'nginx': {}, 'firewall': {}}, php={'version': '8.1.1'}),
                    {'args': {'had': 'x', 'had_cs': 'x', 'mode': 'enforcing', 'mode_cs': 'enforcing', 'how': 'h',
                              'how_cs': 'h', 'n': 2, 'php': '8.1.1', 'installer': '1.0.1'}})))
    for e in AFTER))

# ---- a node's own row; HA: each node writes only its own ----------------------------------------
st = Store()
facts = {'otp1': F(node='otp1', root={'installer': '1.0.257'}), 'otp2': F(node='otp2')}
CLUSTER[0] = True
NODE[0] = 'otp1'
row1 = g['after_evaluate'](st, facts['otp1'])
NODE[0] = 'otp2'
row2 = g['after_evaluate'](st, facts['otp2'])
ok('HA: each node wrote its own row only', st.writers.get('after:otp1') == {'otp1'} and
   st.writers.get('after:otp2') == {'otp2'}, st.writers)
ok('HA: otp1 needs the root parts, otp2 nothing', list(row1['items']) == ['root-parts'] and not row2['items'])
v = g['after_view'](st)
ok('view: one band, otp1\'s, seen from otp2\'s pages', v['count'] == 1 and v['items'][0]['node'] == 'otp1'
   and v['level'] == 'bad' and v['cluster'] and v['items'][0]['steps'], v)
ok('view: not a full administrator - only how many', g['after_view'](st, full=False) == {
    'count': 1, 'level': 'bad', 'nodes': ['otp1']})
ok('summary: the count for the menu and the tab', g['after_summary'](st, fresh=True)['n'] == 1)
since1 = row1['items']['root-parts']['since']
time.sleep(0.01)
NODE[0] = 'otp1'
row1b = g['after_evaluate'](st, facts['otp1'])
ok('first seen kept from one look to the next', row1b['items']['root-parts']['since'] == since1)
# it goes by itself
row1c = g['after_evaluate'](st, F(node='otp1'))
ok('gone by itself: off the row, logged "by itself"', not row1c['items'] and row1c['log'][0]['how'] == 'by itself'
   and row1c['log'][0]['id'] == 'root-parts')
v = g['after_view'](st)
ok('view: nothing to be done, DONE LATELY says by itself', v['count'] == 0 and v['lately'][0]['how'] == 'by itself'
   and v['lately'][0]['who'] == '')

# ---- Done: a manual one ---------------------------------------------------------------------------
fw = F(node='otp1', root={'installer': VER, 'firewall': {'state': 'none', 'at': 5}})
g['after_evaluate'](st, fw)
ok('manual: needed until Done', g['after_view'](st)['count'] == 1)
NODE[0] = 'otp2'                                # pressed on otp2's pages
g['after_done'](st, 'firewall-by-hand', 'otp1', 'alice')
ok('manual Done: the ack row of otp1 kept, written by the pages', 'after:ack:firewall-by-hand:otp1' in st.meta)
v = g['after_view'](st)
ok('manual Done: gone from every page at once', v['count'] == 0, v['items'])
ok('manual Done: DONE LATELY - done, by alice', v['lately'][0]['how'] == 'done' and v['lately'][0]['who'] == 'alice')
ok('manual Done: logged as an event', st.events[-1][0] == 'settings' and 'alice marked as done on otp1' in st.events[-1][1]
   and st.events[-1][2] == 'info')
NODE[0] = 'otp1'
r = g['after_evaluate'](st, fw)
ok('manual Done: the node keeps it as done (acked)', r['items']['firewall-by-hand']['state'] == 'acked')
r = g['after_evaluate'](st, F(node='otp1', root={'installer': VER, 'firewall': {'state': 'none', 'at': 9}}))
ok('manual: another install with no firewall - taken back, needed again',
   r['items']['firewall-by-hand']['state'] == 'needed' and r['log'][0]['how'] == 'taken back'
   and g['after_view'](st)['count'] == 1)
g['after_done'](st, 'firewall-by-hand', 'otp1', 'command line', 'cli')
ok('CLI Done: WHO is the command line', g['after_view'](st)['lately'][0]['who'] == 'the command line')
try:
    g['after_done'](st, 'nothing-here', 'otp1', 'alice')
    refused = False
except ValueError as e:
    refused = 'nothing called nothing-here' in str(e)
ok('Done: one the node does not have - refused', refused)

# ---- Done: an automatic one, by hand (logged); it comes back -----------------------------------------
se3 = F(node='otp1', selinux={'mode': 'Enforcing', 'denials': {'total': 3}})
g['after_evaluate'](st, se3)
ok('auto: SELinux refusing - needed, bad', any(x['id'] == 'selinux-refused' for x in g['after_needed'](st)))
g['after_done'](st, 'selinux-refused', 'otp1', 'bob')
ok('auto Done by hand: logged as such (warn)', 'although its check still finds it needed' in st.events[-1][1]
   and st.events[-1][2] == 'warn')
ok('auto Done by hand: gone', not any(x['id'] == 'selinux-refused' for x in g['after_needed'](st)))
g['after_evaluate'](st, F(node='otp1', selinux={'mode': 'Enforcing', 'denials': {'total': 2}}))
ok('auto, grows: fewer refused - still done', not any(x['id'] == 'selinux-refused' for x in g['after_needed'](st)))
r = g['after_evaluate'](st, F(node='otp1', selinux={'mode': 'Enforcing', 'denials': {'total': 5}}))
ok('auto, grows: more refused - taken back', any(x['id'] == 'selinux-refused' for x in g['after_needed'](st))
   and r['log'][0]['how'] == 'taken back')
g['after_done'](st, 'selinux-refused', 'otp1', 'bob')
g['after_evaluate'](st, F(node='otp1'))
time.sleep(1.2)
g['after_evaluate'](st, se3)
ok('auto: gone, then back - a Done before it does not hold', any(x['id'] == 'selinux-refused' for x in g['after_needed'](st)))

# ---- the alerts ------------------------------------------------------------------------------------
g['after_evaluate'](st, F(node='otp1', selinux={'mode': 'Enforcing', 'denials': {'total': 3}},
                         root={'installer': VER, 'firewall': {'state': 'none', 'at': 11}}))
ga = dict(g)
ga.update(CONFIG={'alerts_upgrade': 1}, DEFAULTS={}, human_bytes=str, ha_repl_state=lambda s: {},
          upgrade_plan=lambda s: {}, hisec_findings=lambda s: {}, selinux_problems=lambda s, n: [],
          acme_care=lambda s, t: True, _al_when=str)
exec(defs('88z_alerts.py', ['_al', 'alert_problems_more']), ga)
probs = {}


def add(key, level, node, title, said, pane):
    probs[key] = {'level': level, 'node': node, 'title': title, 'said': said, 'pane': pane}


ga['alert_problems_more'](st, 'en', add, ['otp1', 'otp2'], {}, {}, True, '', time.time())
p = probs.get('after:selinux-refused:otp1')
ok('alerts: each needed thing is a problem, key after:ID:NODE, pane upgrade',
   p and p['level'] == 'bad' and p['node'] == 'otp1' and p['pane'] == 'upgrade' and
   p['title'] == 'SELinux refuses otp something on this node', probs)
ok('alerts: a note (info) goes as a warning', probs.get('after:firewall-by-hand:otp1', {}).get('level') == 'warn', probs)

probs.clear()
ga['alert_problems_more'](st, 'cs', add, ['otp1', 'otp2'], {}, {}, True, '', time.time())
ok('alerts: in Czech', probs.get('after:selinux-refused:otp1', {}).get('title') == 'SELinux na tomto uzlu něco otp odmítá'
   and 'Nevypínejte' in probs['after:selinux-refused:otp1']['said'], probs)
probs.clear()
ga['CONFIG']['alerts_upgrade'] = 0
ga['alert_problems_more'](st, 'en', add, ['otp1'], {}, {}, True, '', time.time())
ok('alerts: off with the upgrade alerts', not any(k.startswith('after:') for k in probs))
txt = src_of('88z_alerts.py')
ok('alerts: in try/except, logged sparingly', re.search(r"try:\n\s+for it in after_needed\(store, names\):[\s\S]{0,600}except Exception as e:[\s\S]{0,80}log_sparing\('alerts-after'", txt))

# ---- the routes ---------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, msg)
        self.code = code


class H:
    def __init__(self, store, body=None, role='fulladmin'):
        self.store, self._b, self.role = store, body or {}, role

    def me(self, role='readonly'):
        rank = {'readonly': 1, 'tokenadmin': 2, 'fulladmin': 3}
        if rank[self.role] < rank[role]:
            raise ApiError(403, 'only a full administrator may do that')
        return {'name': 'alice', 'role': self.role, 'id': 's'}

    def body(self):
        return self._b


gr = dict(g)
gr['ApiError'] = ApiError
exec(defs('90a_alerts_api.py', ['_after', '_after_do']), gr)
d = gr['_after'](H(st, role='readonly'))
ok('GET /api/after: a read-only account sees how many only', set(d) == {'count', 'level', 'nodes'}, d)
d = gr['_after'](H(st))
ok('GET /api/after: a full administrator - the bands and DONE LATELY', 'items' in d and 'lately' in d and d['me'] == 'otp1')
try:
    gr['_after_do'](H(st, {'action': 'done', 'id': 'selinux-refused', 'node': 'otp1'}, role='tokenadmin'))
    noperm = False
except ApiError as e:
    noperm = e.code == 403
ok('POST /api/after: only a full administrator', noperm)
NODE[0] = 'otp1'
SE_ASKED[:] = []
real_facts = g['after_facts']
g['after_facts'] = lambda store: se3
d = gr['_after_do'](H(st, {'action': 'check', 'node': 'otp1'}))
ok('POST check, this node: looked now, SELinux asked again too', d['message'] == 'looked again' and
   SE_ASKED and SE_ASKED[0][:2] == ('otp1', 'check'), (d.get('message'), SE_ASKED))
d = gr['_after_do'](H(st, {'action': 'check', 'node': 'otp2'}))
look = json.loads(st.meta.get('after:look:otp2') or '{}')
ok('POST check, the other node: asked through its look row', 'otp2 looks again within a minute' == d['message']
   and look.get('id') and look.get('by') == 'alice')
d = gr['_after_do'](H(st, {'action': 'done', 'id': 'selinux-refused', 'node': 'otp1'}))
ok('POST done: marked, the view without it', d['message'] == 'marked as done' and
   not any(x['id'] == 'selinux-refused' for x in d['items']))
g['after_facts'] = real_facts
for body, words in (({'action': 'done', 'id': '../x', 'node': 'otp1'}, 'which one'),
                    ({'action': 'done', 'id': 'x', 'node': 'nowhere'}, 'no node'),
                    ({'action': 'check', 'node': 'nowhere'}, 'no node'), ({'action': 'shout'}, 'no such')):
    try:
        gr['_after_do'](H(st, body))
        said = ''
    except ApiError as e:
        said = '%d %s' % (e.code, e)
    ok('POST %s: refused (%s)' % (json.dumps(body), said), said.startswith('400') and words in said)

# ---- the tick: at the start, every 10 min, and when asked --------------------------------------------
class Dm:
    store = st


calls = []
real_eval = g['after_evaluate']
g['after_evaluate'] = lambda store, facts=None: calls.append(1)
g['AFTER_WORK'].update(at=0.0, busy=False, looked=0.0, look_id='')
g['after_tick'](Dm())
time.sleep(0.2)
g['after_tick'](Dm())
time.sleep(0.2)
ok('tick: once at the start, not again at once', len(calls) == 1, calls)
NODE[0] = 'otp2'
g['AFTER_WORK']['looked'] = 0.0
g['after_tick'](Dm())
time.sleep(0.2)
ok('tick: "Look again" from the other node\'s pages - looked again', len(calls) == 2, calls)
g['AFTER_WORK']['looked'] = 0.0
g['after_tick'](Dm())
time.sleep(0.2)
ok('tick: the same ask not twice', len(calls) == 2, calls)


def boom(store, facts=None):
    raise RuntimeError('the database is away')


g['after_evaluate'] = boom
g['AFTER_WORK'].update(at=0.0, busy=False)
g['after_tick'](Dm())
time.sleep(0.2)
ok('tick: a fault is logged, never raised; not busy after', not g['AFTER_WORK']['busy'])
g['after_evaluate'] = real_eval
NODE[0] = 'otp1'
# a check that breaks keeps what it said
E['php2shell']['check'], was_ck = (lambda s, f: 1 / 0), E['php2shell']['check']
g['after_evaluate'](st, F(node='otp1', php={'version': '8.1', 'fixed': False}))
E['php2shell']['check'] = was_ck
ok('evaluate: one check that breaks does not stop the others', True)

# ---- the CLI ------------------------------------------------------------------------------------------
class Pal:
    def __getattr__(self, k):
        return lambda t: str(t)


class A:
    after, after_done, after_brief, json, node = True, None, False, False, None


st2 = Store()
CLUSTER[0] = False
NODE[0] = 'otp1'
(LIB / 'root-facts.json').write_text(json.dumps({'installer': '1.0.257', 'at': 1}))
g['after_facts_real'] = g['after_facts']
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = g['cli_after'](A(), Pal(), st2)
out = buf.getvalue()
ok('otp --after: looks now (root-facts.json read), says what and how', rc == 0 and
   'to be done by hand: 1' in out and 'otp %s is running' % VER in out and './install.sh --upgrade' in out
   and 'otp --after-done root-parts' in out, out)
A.json = True
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g['cli_after'](A(), Pal(), st2)
ok('otp --after --json: the view as JSON', json.loads(buf.getvalue())['items'][0]['id'] == 'root-parts')
A.json, A.after, A.after_done = False, False, 'root-parts'
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g['cli_after'](A(), Pal(), st2)
ok('otp --after-done ID: marked, written as the command line', 'marked as done' in buf.getvalue() and
   json.loads(st2.meta['after:ack:root-parts:otp1'])['via'] == 'cli')
A.after, A.after_done = True, None
(LIB / 'root-facts.json').write_text(json.dumps({'installer': VER, 'at': 2}))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    g['cli_after'](A(), Pal(), st2)
ok('otp --after: nothing - said so', 'nothing is to be done by hand' in buf.getvalue(), buf.getvalue())
(LIB / 'root-facts.json').unlink()
os.symlink('/etc/hostname', str(LIB / 'root-facts.json'))
ok('root-facts.json: a link is not read', g['root_facts']() == {})
os.unlink(str(LIB / 'root-facts.json'))
ok('root-facts.json: not there - None', g['root_facts']() is None)

cli = src_of('95_cli.py')
ok('CLI: --after, --after-done, --node with it', "add_argument('--after'," in cli and "add_argument('--after-done'" in cli
   and '--after-done: another' in cli and 'return cli_after(args, pal, store)' in cli)
ok('CLI: --status/--check say how many, the check fails on a bad one only',
   "s['after'] = after_summary(store, fresh=True)" in cli and "'to be done by hand: %d - otp --after says what and how'" in cli
   and "if args.check and aft.get('level') == 'bad':" in cli)
con = src_of('96_console.py')
ok('console: the first screen says them', "aft = odict(st.get('after'))" in con and "'! to be done by hand%s: %s'" in con)
dm = src_of('80_daemon.py')
ok('daemon: the tick in try/except, logged sparingly', re.search(
    r"try:\n\s+after_tick\(self\)[^\n]*\n\s+except Exception as e:[^\n]*\n\s+log_sparing\('after-tick'", dm))
api = src_of('90_api.py')
ok('/api/status: the count, never in the way', "out['after'] = {'n': a['n'], 'level': a['level']}" in api
   and "out['after'] = {'n': 0, 'level': ''}" in api)

# ---- root-facts.json as install.sh writes it ---------------------------------------------------------
sh = open(OUT + '/install.sh').read()
m = re.search(r"python3 - \"\$LIB_DIR/root-facts.json\" <<'PY'[^\n]*\n(.*?)\nPY\n", sh, re.S)
ok('install.sh: root_facts_write is there', bool(m))
pyw = TMP / 'w.py'
pyw.write_text(m.group(1) if m else '')
rf = TMP / 'rf.json'


def facts_run(**env):
    e = dict(os.environ)
    e.update({k: str(v) for k, v in env.items()})
    subprocess.run([sys.executable, '-I', str(pyw), str(rf)], env=e, check=True)
    return json.loads(rf.read_text())


f1 = facts_run(FACT_VERSION=VER, FACT_KIND='', FACT_NGINX_ADD='ok', FACT_NGINX_GUARD='ok',
               FACT_SELINUX_MODULE='in', FACT_FIREWALL='none')
ok('root-facts.json: written - versions, words, times', f1['installer'] == VER and f1['kind'] == 'install' and
   f1['nginx']['additions'] == 'ok' and f1['nginx']['guard'] == 'ok' and f1['selinux_module'] == 'in' and
   f1['firewall']['state'] == 'none', f1)
ok('root-facts.json: world-readable, not writable by others', (os.stat(rf).st_mode & 0o777) == 0o644)
f2 = facts_run(FACT_VERSION='1.0.259', FACT_KIND='upgrade', FACT_NGINX_ADD='failed', FACT_NGINX_GUARD='',
               FACT_SELINUX_MODULE='', FACT_FIREWALL='')
ok('root-facts.json: an upgrade keeps what it did not look at', f2['installer'] == '1.0.259' and
   f2['kind'] == 'upgrade' and f2['nginx']['additions'] == 'failed' and f2['nginx']['guard'] == 'ok' and
   f2['selinux_module'] == 'in' and f2['firewall']['state'] == 'none', f2)
f3 = facts_run(FACT_VERSION='1.0.259; rm -rf /', FACT_KIND='', FACT_NGINX_ADD='x y', FACT_NGINX_GUARD='',
               FACT_SELINUX_MODULE='', FACT_FIREWALL='')
ok('root-facts.json: only digits and plain words go in', f3['installer'] == '1.0.259' and f3['nginx']['additions'] == 'failed')
ok('root-facts.json: no secret in it', not re.search(r'(?i)secret|password|token|key', json.dumps(f1)))
ok('install.sh: written before the daemon starts (upgrade and install), said at the end',
   re.search(r'root_facts_write\n\s+restart_daemon\n\s+UPGRADE_STAGE=done', sh) and
   re.search(r'step "The service"\nroot_facts_write\nrestart_daemon', sh) and sh.count('\nafter_says\n') + sh.count('    after_says\n') >= 2
   and 'as_otp --after --after-brief || true' in sh)
ok('install.sh: what nginx, SELinux and the firewall made of it, noted',
   'FACT_NGINX_ADD=failed' in sh and 'FACT_NGINX_GUARD=failed' in sh and 'FACT_SELINUX_MODULE=failed' in sh
   and 'FACT_FIREWALL=none' in sh)
r = subprocess.run(['bash', '-n', OUT + '/install.sh'], capture_output=True, text=True)
ok('install.sh: bash -n', r.returncode == 0, r.stderr)

# ---- the wiring --------------------------------------------------------------------------------------
bsh = open(BUILD + '/build.sh').read()
ok('build.sh: 88n_after.py right after 88z_alerts.py', 'parts/88z_alerts.py parts/88n_after.py parts/89_rename.py' in bsh)
files = re.search(r'cat (parts/\S+(?: parts/\S+)*) >', bsh).group(1).split()
whole = TMP / 'otp_all.py'
with open(whole, 'w') as w:
    for f in files:
        w.write(open(os.path.join(BUILD, f)).read())
r = subprocess.run([sys.executable, '-m', 'py_compile', str(whole)], capture_output=True, text=True)
ok('the parts together compile', r.returncode == 0, r.stderr)
php = open(OUT + '/web/admin/index.php').read()
reads = php[php.index('$reads = ['):php.index('$writes = [')]
writes = php[php.index('$writes = ['):php.index('if ($post) {', php.index('$writes = ['))]
ok('index.php: route "after" in the read and the write maps', "'after' => '/api/after'" in reads and "'after' => '/api/after'" in writes)
ok('index.php: the card first in the Upgrades pane, before the nodes', re.search(
    r'id="pane-upgrade"[\s\S]*?ctl-lede[\s\S]*?</div>\s*<!--[\s\S]*?-->\s*<div class="card full fulladmin-only after-card" id="after-card">[\s\S]*?<h2>The nodes</h2>', php))
ok('index.php: the badge on Upgrades in the menu, the count on the Settings tab',
   'data-pane="upgrade" data-icon="up"' in php and 'id="after-badge"' in php and 'id="tabn-settings"' in php)
if shutil.which('php'):
    r = subprocess.run(['php', '-l', OUT + '/web/admin/index.php'], capture_output=True, text=True)
    ok('index.php: php -l', r.returncode == 0, r.stdout + r.stderr)
js = open(OUT + '/web/assets/admin.js').read()
if shutil.which('node'):
    r = subprocess.run(['node', '--check', OUT + '/web/assets/admin.js'], capture_output=True, text=True)
    ok('admin.js: node --check', r.returncode == 0, r.stderr)
ok('admin.js: the badge from every status, the pane loads the card', 'afterBadge(s.after);' in js and
   "if (name === 'upgrade') { loadAfter(); loadUpgrade(); }" in js)
ok('admin.js: bands with Copy, Look again (auto), Done, Open it; DONE LATELY; the empty state', all(
    w in js for w in ("cmdButton('Copy', 'copy'", "cmdButton('Look again', 'refresh'", "cmdButton('Done', 'check'",
                      "cmdButton('Open it', 'next'", "'Done lately'", "'Nothing is to be done by hand.'",
                      "['What', 'How', 'Who', 'When']", 'stampCell(x.at)')))
top = js[:js.index('function paintHeader(s) {')]
ok('admin.js: nothing new drawn at the top of the pages', 'after-band' not in top and
   js.count("$('problems')") == 1 and 'afterBand' not in js[js.index('function paintHeader(s) {'):js.index('function drawTrials(s) {')])
css = open(OUT + '/web/assets/otp.css').read()
ok('otp.css: the band, the command box, the rail badge, phone width', all(w in css for w in (
    '.after-band::before{', '.after-cmd{', '.ctl-nav .rail-n{', '@media (max-width:760px){\n  .after-band', 'var(--crit)', 'var(--warn)')))
doc = open(OUT + '/docs/upgrades.md').read()
ok('docs: a section in upgrades.md', '## To be done by hand (1.0.258)' in doc and 'otp --after' in doc)

# ---- Czech ------------------------------------------------------------------------------------------------
sys.path.insert(0, '/home/claude/i18n')
import cs_266, cs_270
# The entries of later versions in the dictionaries of theirs (1.0.268).
S, P = dict(cs_266.S266, **cs_270.S270), dict(cs_266.P266, **cs_270.P270)
ok('Czech: every text given', all(v.strip() for v in list(S.values()) + list(P.values())))
ok('Czech: the {0} of each pattern kept', all(set(re.findall(r'\{\d', k)) == set(re.findall(r'\{\d', v)) for k, v in P.items()), [k for k, v in P.items() if set(re.findall(r'\{\d', k)) != set(re.findall(r'\{\d', v))])


def covered(text):
    if text in S:
        return True
    for k in P:
        rx = '^' + re.sub(r'\\\{\d\\\}', '(.+?)', re.escape(k)) + '$'
        if re.match(rx, text):
            return True
    return False


def ui_words():
    out = set()
    a = js[js.index('To be done by hand, after an update (1.0.258)'):js.index('Certificates and the VIP address (1.0.47)')]
    out.update(re.findall(r"cmdButton\('([^']+)'", a))
    out.update(re.findall(r"\bel\('[a-z0-9]+', '[^']*', '([^']+)'\)", a))
    out.update(['Nothing is to be done by hand.', 'Done lately', 'Nothing yet.', 'Just seen', 'Mark it as done?',
                'Mark it as done', 'the command is on the clipboard', 'This node looks again now.', 'taken back',
                'the command line', 'To be done by hand'])
    note = re.search(r'id="after-card">\s*<h2>To be done by hand</h2>\s*<p class="note">(.*?)</p>', php, re.S)
    out.add(' '.join(note.group(1).split()))
    return out


pack = json.load(open(OUT + '/web/lang/cs.json'))
had = {v['source'] for v in pack['strings'].values() if v.get('text')}
missing = [w for w in ui_words() if not covered(w) and w not in had]
ok('Czech: the card\'s words (new ones in cs_266, the rest in cs.json already)', not missing, missing)
NODE[0] = 'otp1'
said = []
for cl in (False, True):
    CLUSTER[0] = cl
    for e in AFTER:
        for args in ({'had': 'an install.sh older than 1.0.258', 'mode': 'enforcing', 'how': 'is not in its policy',
                      'n': 3, 'php': '8.3.1', 'installer': '1.0.257'},
                     {'had': 'install.sh 1.0.257', 'mode': 'permissive', 'how': 'in its policy is older than the one of this version'}):
            x = g['after_item'](e, F(), {'args': args})
            said += [x['title'], x['why'], x['foot']] + [s.get('lead') or '' for s in x['steps']] + \
                [s.get('words') or '' for s in x['steps']]
missing = sorted({w for w in said if w and not covered(w)})
ok('Czech: every title, why, lead and footnote of the entries', not missing, missing[:6])
ok('Czech: the slots of several words too', all(covered(w) for w in (
    'an install.sh older than 1.0.258', 'is not in its policy', 'in its policy is older than the one of this version')))
ok('Czech: the alerts\' switch', covered('An upgrade of otp that failed, or left to be done by hand') and covered(
    'An upgrade of otp (Settings → Upgrades) that failed on a node, or one left stuck - and what an update left to be done by hand (To be done by hand, there).'))
for m in ('looked again', 'marked as done', 'otp2 looks again within a minute', 'which one?',
          'otp1 has nothing called x to be done'):
    ok('Czech: the answer "%s"' % m, covered(m))
ok('Czech: formal (vy), not ty', not re.search(r'\b(stiskni|udělej|podívej|vlož|ty)\b', json.dumps(S, ensure_ascii=False) + json.dumps(P, ensure_ascii=False)))

shutil.rmtree(TMP, ignore_errors=True)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
