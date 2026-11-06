"""t_mfa_send.py - 1.0.259, the administration's second step by mail or SMS: where the codes of a sign-in
stand (`send`: sent, most, left, gap_s, wait_s, can, why, code_left_s, code_ttl_s, auto) in GET
/api/auth/mfa, in the answers of send and enrol_start and in both 429s (ApiError's extra, merged into the
JSON); the first code sent by itself once a sign-in (auto: true - skipped when one went already, even
past the gap); the gap and the most; a send that fails gives its place back; the 429 words from wait_s;
the page's countdown, "N more", the limit with Sign in again and "good for m:ss more" (core.js run in
node with a stub DOM); the Czech. Pure Python + node: parts exec'd with stubs - no daemon, no ports,
no database, no mail.

    cd /tmp && python3 t_mfa_send.py 1.0.259
"""
import ast, json, math, os, re, secrets, subprocess, sys, tempfile, threading, time
from pathlib import Path

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.259'
BUILD = '/home/claude/build'
PARTS = BUILD + '/parts'
OUT = '%s/out/otp-%s' % (BUILD, VER)
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:500]))


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


CLOCK = [1_000_000.0]
SENT = []
FAIL = [None]


class FakeTime:
    @staticmethod
    def time():
        return CLOCK[0]


class MailError(Exception):
    pass


class SmsError(Exception):
    pass


def odict(v):
    return v if isinstance(v, dict) else {}


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def code_send(store, kind, dest, code, **kw):
    if FAIL[0]:
        raise MailError(FAIL[0])
    SENT.append((kind, dest, code))
    return 'queued'


class Store:
    def __init__(self):
        self.sessions, self.events = {}, []
        self.lose_next = False

    def session_merge(self, ident, changes, expect=None):
        s = self.sessions.get(ident)
        if s is None:
            return None
        d = s['data']
        if expect is not None:
            if self.lose_next:
                self.lose_next = False
                return False
            if any(d.get(k) != v for k, v in expect.items()):
                return False
        for k, v in changes.items():
            if v is None:
                d.pop(k, None)
            else:
                d[k] = v
        return dict(d)

    def account(self, name, checked=False):
        return {'name': name, 'display': 'Boss'}

    def add_event(self, *a, **k):
        self.events.append(a)


g = {'time': FakeTime, 'math': math, 'secrets': secrets, 'json': json, 'threading': threading, 're': re,
     'CONFIG': {'code_ttl_s': 300, 'admin_2fa': 1, 'code_digits': 6}, 'fnum': fnum, 'odict': odict,
     'code_new': lambda: '%06d' % secrets.randbelow(10 ** 6), 'code_hash': lambda salt, code: salt + ':' + code,
     'code_send': code_send, 'dest_masked': lambda kind, dest: 'b***@example.cz' if kind == 'mail' else '+420 *** 456',
     'log': lambda *a, **k: None, 'MailError': MailError, 'SmsError': SmsError, 'mfa_lang': lambda h: 'en',
     'MFA_SEND_GAP_S': 30, 'MFA_SEND_MOST': 5, 'MFA_WRONG_MOST': 5, 'MFA_LOCK': threading.Lock(),
     'MFA_BLOCKED_WORDS': 'blocked %s', 'MFA_KIND_WORDS': {'mail': 'a code by e-mail', 'sms': 'a code by SMS', 'app': 'an app'},
     'code_channels': lambda: ['mail', 'sms'], 'mfa_methods': lambda h=None: ['app', 'mail', 'sms'],
     'dest_checked': lambda kind, d: str(d).strip()}
consts = dict(re.findall(r'^(MFA_SEND_GAP_S|MFA_SEND_MOST) = (\d+)', src_of('90m_mfa.py'), re.M))
ok('the limits are as they were: 30 s apart, 5 a sign-in', consts == {'MFA_SEND_GAP_S': '30', 'MFA_SEND_MOST': '5'}, consts)
exec(defs('90_api.py', ['ApiError']), g)
ApiError = g['ApiError']
REC = {'kind': 'mail', 'dest': 'boss@example.cz'}
STAGE = ['check']
g.update(mfa_get=lambda st, name: dict(REC), mfa_pending=lambda s, st=None: STAGE[0], mfa_stage=lambda st, n: STAGE[0])
exec(defs('90m_mfa.py', ['mfa_send_state', 'mfa_wait_words', '_mfa_send', '_mfa', '_mfa_do']), g)
st_of, send = g['mfa_send_state'], g['_mfa_send']

# ---- the state alone ---------------------------------------------------------------------------
st = st_of({}, 'mfa_code', 1000.0)
ok('nothing sent: 0 of 5, may send now, auto', st == {'sent': 0, 'most': 5, 'left': 5, 'gap_s': 30, 'wait_s': 0, 'can': True,
                                                      'why': '', 'code_left_s': 0, 'code_ttl_s': 300, 'auto': True}, st)
st = st_of({'mfa_sent_at': 1000.0, 'mfa_sent': 1, 'mfa_code': {'exp': 1300.0}}, 'mfa_code', 1010.2)
ok('10 s after the first: 20 s to wait, 4 left, good for 289 s, not auto', (st['wait_s'], st['left'], st['can'], st['why'], st['code_left_s'], st['auto']) == (20, 4, False, 'gap', 289, False), st)
st = st_of({'mfa_sent_at': 1000.0, 'mfa_sent': 1}, 'mfa_code', 1030.0)
ok('30 s after: may send again', st['wait_s'] == 0 and st['can'] and st['why'] == '')
st = st_of({'mfa_sent_at': 1000.0, 'mfa_sent': 5}, 'mfa_code', 1001.0)
ok('the fifth went: none left, why "most", no countdown', (st['left'], st['can'], st['why'], st['wait_s']) == (0, False, 'most', 0), st)
st = st_of({'mfa_sent_at': 1100.0, 'mfa_sent': 1}, 'mfa_code', 1000.0)
ok('the other node\'s clock ahead: the wait is never longer than the gap', st['wait_s'] == 30, st)
st = st_of({'mfa_sent_at': 1000.0, 'mfa_sent': 2, 'mfa_new': {'exp': 1100.0}}, 'mfa_new', 1050.0)
ok('enrolment: the code being proven is mfa_new', st['code_left_s'] == 50)
ok('the words of the wait from wait_s', g['mfa_wait_words'](17) == 'a code went a moment ago - another in 17 s' and g['mfa_wait_words'](0).endswith('in 1 s'))


# ---- through the routes --------------------------------------------------------------------------
class H:
    def __init__(self, store, sid, body=None):
        self.store, self.sid, self._body = store, sid, body or {}

    def body(self):
        return self._body

    def throttle(self, *a, **k):
        return 'k'

    def failed(self, k):
        pass


SID = 'sess1'


def new_sign_in():
    store = Store()
    store.sessions[SID] = {'id': SID, 'name': 'boss', 'role': 'fulladmin', 'data': {'mfa': 'check'}}
    return store


def session_of(store):
    s = store.sessions[SID]
    return {'id': SID, 'name': s['name'], 'role': s['role'], 'data': json.loads(json.dumps(s['data']))}


def call(store, body=None, get=False):
    g['_mfa_session'] = lambda h: (session_of(store), {'name': 'boss', 'display': 'Boss'})
    h = H(store, SID, body)
    try:
        return 200, (g['_mfa'](h) if get else g['_mfa_do'](h))
    except ApiError as e:
        return e.status, dict({'error': str(e)}, **(e.extra or {}))


store = new_sign_in()
CLOCK[0] = 1_000_000.0
st, d = call(store, get=True)
ok('GET: send with the state, auto on, nothing sent', st == 200 and d['send']['auto'] and d['send']['sent'] == 0 and d['send']['can'], d.get('send'))
st, d = call(store, {'action': 'send', 'auto': True})
ok('the first code by itself: sent, the state with it (1 of 5, 30 s to wait, good for 300 s)',
   st == 200 and len(SENT) == 1 and d['sent_to'] == 'b***@example.cz' and not d.get('skipped')
   and (d['send']['sent'], d['send']['left'], d['send']['wait_s'], d['send']['code_left_s'], d['send']['auto']) == (1, 4, 30, 300, False), d)
CLOCK[0] += 5
st, d = call(store, {'action': 'send', 'auto': True})
ok('F5 five seconds later: auto skipped, nothing sent, the state (25 s, good for 295 s)',
   st == 200 and d.get('skipped') and len(SENT) == 1 and d['send']['wait_s'] == 25 and d['send']['code_left_s'] == 295, d)
CLOCK[0] += 100
st, d = call(store, {'action': 'send', 'auto': True})
ok('F5 past the gap: still no second code by itself - once a sign-in', st == 200 and d.get('skipped') and len(SENT) == 1, d)
st, d = call(store, get=True)
ok('GET after: auto off, 1 sent, may send another, the code still good', not d['send']['auto'] and d['send']['sent'] == 1 and d['send']['can'] and d['send']['code_left_s'] == 195, d['send'])
st, d = call(store, {'action': 'send'})
ok('Send another (by hand) past the gap: sent, 2 of 5', st == 200 and len(SENT) == 2 and d['send']['sent'] == 2 and d['send']['left'] == 3)
CLOCK[0] += 3
st, d = call(store, {'action': 'send'})
ok('too soon: 429 with the words from wait_s and send in the answer', st == 429 and d['error'] == 'a code went a moment ago - another in 27 s'
   and d['send']['wait_s'] == 27 and d['send']['why'] == 'gap' and len(SENT) == 2, d)
for i in range(3):
    CLOCK[0] += 31
    call(store, {'action': 'send'})
ok('five sent in all', len(SENT) == 5 and store.sessions[SID]['data']['mfa_sent'] == 5)
CLOCK[0] += 31
st, d = call(store, {'action': 'send'})
ok('the sixth: 429 "sign in again", send says none left (why most)', st == 429 and 'sign in again for more' in d['error']
   and d['send']['left'] == 0 and d['send']['why'] == 'most' and len(SENT) == 5, d)
st, d = call(store, get=True)
ok('GET at the limit: can false, left 0', d['send']['can'] is False and d['send']['left'] == 0)
# a send that fails gives the place back
store = new_sign_in()
SENT.clear()
FAIL[0] = 'the mail server said no'
st, d = call(store, {'action': 'send', 'auto': True})
ok('a send that fails: 502, nothing counted', st == 502 and 'mfa_sent' not in store.sessions[SID]['data'] or store.sessions[SID]['data'].get('mfa_sent') in (None, 0), (st, store.sessions[SID]['data']))
FAIL[0] = None
st, d = call(store, get=True)
ok('...and the next look still sends by itself', d['send']['auto'] and d['send']['sent'] == 0)
# another request took the place a moment ago (two tabs, the other node)
store = new_sign_in()
store.lose_next = True
st, d = call(store, {'action': 'send', 'auto': True})
ok('the place taken by another request at once: 429 with send, no code', st == 429 and d['send']['wait_s'] == 30 and not SENT, d)
# app accounts are not offered any of it
REC.update(kind='app')
store = new_sign_in()
st, d = call(store, get=True)
ok('GET for an app: no send state', d['send'] is None)
st, d = call(store, {'action': 'send', 'auto': True})
ok('send for an app: refused as before', st == 400)
REC.update(kind='sms', dest='+420603123456')
st, d = call(store, get=True)
ok('GET for SMS: the state', d['send'] and d['send']['sent'] == 0)
# enrolment
STAGE[0] = 'enrol'
store = new_sign_in()
store.sessions[SID]['data'] = {'mfa': 'enrol'}
SENT.clear()
st, d = call(store, {'action': 'enrol_start', 'kind': 'mail', 'dest': 'boss@example.cz'})
ok('enrol_start: sent_to and send (1 of 5)', st == 200 and d['sent_to'] and d['send']['sent'] == 1 and d['send']['code_left_s'] == 300, d)
st, d = call(store, {'action': 'enrol_start', 'kind': 'mail', 'dest': 'boss@example.cz'})
ok('enrol_start again at once: 429 with send', st == 429 and d['send']['why'] == 'gap', d)
st, d = call(store, get=True)
ok('GET while enrolling: send for the way being proven', d['send']['sent'] == 1 and d['send']['code_left_s'] == 300)
STAGE[0] = 'check'

# ---- the JSON: ApiError's extra merged, never over ok/error ----------------------------------
api = src_of('90_api.py')
e = ApiError(429, 'x', extra={'send': {'left': 1}})
ok('ApiError carries extra (a dict, or nothing)', e.extra == {'send': {'left': 1}} and ApiError(400, 'y').extra is None and ApiError(400, 'y', extra='z').extra is None)
ok('the handler merges it without overwriting ok, error, detail', "for k, v in (e.extra or {}).items():\n                said.setdefault(k, v)" in api)

# ---- the page (core.js in node, a stub DOM) ------------------------------------------------------
core = open(OUT + '/web/assets/core.js', encoding='utf-8').read()
a = core.index('function mmss(n)')
b = core.index('function mfaCodeForm(box, d, action, words, after)')
runner = Path(tempfile.mkdtemp(prefix='t_mfa_send_')) / 'ui.js'
runner.write_text(r'''
function Node(tag) { this.tag = tag; this.children = []; this.className = ''; this._text = ''; this.disabled = false; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Object.defineProperty(Node.prototype, 'textContent', {get: function () { return this._text + this.children.map(function (c) { return c.textContent; }).join(''); },
  set: function (v) { this._text = String(v); this.children = []; }});
var document = {body: {contains: function () { return true; }}, createTextNode: function (t) { var n = new Node('#'); n._text = t; return n; }};
function el(tag, cls, text) { var n = new Node(tag); n.className = cls || ''; if (text !== undefined) n._text = String(text); return n; }
function clear(n) { n.children = []; n._text = ''; }
function setButtonIcon(b, icon, label) { b.label = label; return b; }
function cmdButton(label, icon, cls) { var b = el('button', cls); b.label = label; return b; }
function api() { return {then: function () {}}; }
var now = 1000000, timers = [];
Date.now = function () { return now; };
function setInterval(f) { timers.push(f); return timers.length; }
function clearInterval(i) { if (i) timers[i - 1] = null; }
function tick(s) { for (var k = 0; k < s; k++) { now += 1000; timers.forEach(function (f) { if (f) f(); }); } }
''' + core[a:b] + r'''
var out = {};
var btn = el('button'), note = el('div');
mfaSendPaint(btn, note, {sent: 1, most: 5, left: 4, wait_s: 25, code_left_s: 280}, 'mail');
out.first = [btn.label, btn.disabled, note.textContent];
tick(10); out.later = [btn.label, btn.disabled];
tick(15); out.done = [btn.label, btn.disabled, note.textContent];
var b2 = el('button'), n2 = el('div');
mfaSendPaint(b2, n2, {sent: 1, most: 5, left: 1, wait_s: 0}, 'mail');
out.one = n2.textContent;
var b3 = el('button'), n3 = el('div');
mfaSendPaint(b3, n3, {sent: 5, most: 5, left: 0, wait_s: 0, why: 'most'}, 'mail');
out.most = [b3.label, b3.disabled, n3.textContent, n3.children.length, n3.children[1] && n3.children[1].label];
var b4 = el('button'), n4 = el('div');
mfaSendPaint(b4, n4, {sent: 0, most: 5, left: 5, wait_s: 0, auto: true, can: true}, 'mail');
out.none = [b4.label === undefined, b4.disabled, n4.textContent];
var s = el('div');
mfaSentSay(s, 'b***@example.cz', {sent: 2, code_left_s: 125});
out.said = s.children.map(function (c) { return c.textContent; });
mfaSentSay(s, 'b***@example.cz', null);
out.said0 = s.textContent;
out.mmss = [mmss(0), mmss(9), mmss(65), mmss(300)];
console.log(JSON.stringify(out));
''')
got = subprocess.run(['node', str(runner)], capture_output=True, text=True)
ok('core.js: the countdown runs in node', got.returncode == 0, got.stderr[-400:])
U = json.loads(got.stdout or '{}')
ok('Send another (0:25), held, "4 more can be sent"', U.get('first') == ['Send another (0:25)', True, '4 more can be sent for this sign-in.'], U.get('first'))
ok('...ten seconds later (0:15)', U.get('later') == ['Send another (0:15)', True], U.get('later'))
ok('...at 0: Send another, may be pressed', U.get('done') == ['Send another', False, '4 more can be sent for this sign-in.'], U.get('done'))
ok('"1 more can be sent"', U.get('one') == '1 more can be sent for this sign-in.')
# 1.0.259: the button itself becomes Sign in again (may be pressed); the note says why, with no button in it
ok('at the limit: the button is Sign in again, the note why', U.get('most', [None])[0] == 'Sign in again' and U['most'][1] is False
   and 'That was the last code for this sign-in (5) - sign in again for more.' in U['most'][2] and U['most'][3] == 0, U.get('most'))
ok('nothing sent yet: the button left as it is, no note', U.get('none') == [True, False, ''], U.get('none'))
ok('after F5: sent to, good for 2:05 more, only the last one is good - each its own words',
   U.get('said') == ['Sent to b***@example.cz - write the code from it below.', ' ', 'It is good for 2:05 more.', ' ', 'Only the last one sent is good.'], U.get('said'))
ok('after a send: the one sentence', U.get('said0') == 'Sent to b***@example.cz - write the code from it below.')
ok('m:ss', U.get('mmss') == ['0:00', '0:09', '1:05', '5:00'])
dr = core[core.index('function mfaDraw(box, d)'):core.index('function mfaWay(body, d, kind)')]
ok('mfaDraw: the first code by itself once (auto and can), never when one went (st0.sent)',
   "} else if (st0 && st0.auto && st0.can) {" in dr and 'go(true);' in dr and dr.index('if (st0 && st0.sent)') < dr.index('st0.auto && st0.can'))
ok('mfaDraw: auto sends {action: send, auto: true}; a 429 of auto is quiet', "{action: 'send', auto: true}" in dr and 'if (auto && e.status === 429)' in dr)
ok('no more fixed 30 s re-enable where the daemon says when', core.count('setTimeout(function () { send.disabled = false; }, 30000);') == 2
   and core.count('if (!r.send) setTimeout(function () { send.disabled = false; }, 30000);') == 2)
ok('api(): the rest of the answer kept on the error (err.data)', 'err.data = data;' in core)
# ---- the Czech --------------------------------------------------------------------------------
sys.path.insert(0, '/home/claude/i18n')
from cs_267 import S267, P267
pack = json.load(open(OUT + '/web/lang/cs.json'))
had = {v['source'] for v in pack['strings'].values() if v.get('text')}
hadp = [v['source'] for v in pack['patterns'].values() if v.get('text')]


def covered(t):
    if t in S267 or t in had:
        return True
    return any(re.match('^' + re.sub(r'\\\{\d\\\}', '(.+?)', re.escape(k)) + '$', t) for k in list(P267) + hadp)


words = [U['first'][0], U['first'][2], U['one'], U['most'][2].strip(), 'Sign in again', U['said'][2], U['said'][4], U['said0'],
         'a code went a moment ago - another in 27 s', 'that is 5 codes for this sign-in: sign in again for more']
words = [w for w in words if w]
words += [x for x in ('That was the last code for this sign-in (5) - sign in again for more.',)]
missing = [w for w in words if not covered(w)]
ok('Czech: the new words of the second step', not missing, missing)
ok('Czech: formal (vy)', not re.search(r'\b(stiskni|udělej|podívej|přihlas se|ty)\b', json.dumps([S267, P267], ensure_ascii=False)))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
