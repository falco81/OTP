"""t_web.py - 1.0.255 (web): the performance meter (hload.js, 90r_load.py) - a day-long page, focus
and scroll kept across the redraw, a clock stepped back on either side, the other node's network
in its own words, previews without tab stops; the second step by mail/SMS after a reload (core.js);
the Czech of the new strings (cs_255_web.py)."""
import os, sys, re, json, time, subprocess, threading, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.255'
OUT = '/home/claude/build/out/otp-%s/web/assets' % VER
PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]))


# ---- node --check ----------------------------------------------------------------------------
for f in ('hload.js', 'core.js', 'admin.js', 'portal.js'):
    p = subprocess.run(['node', '--check', os.path.join(OUT, f)], capture_output=True, text=True)
    ok('node --check ' + f, p.returncode == 0, p.stderr)


def func(src, name):
    """The source of one top-level function, by its braces."""
    i = src.index('function ' + name + '(')
    j = src.index('{', i)
    depth, k = 0, j
    while True:
        c = src[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1


HL = open(os.path.join(OUT, 'hload.js')).read()
CORE = open(os.path.join(OUT, 'core.js')).read()

DOM = r'''
function mk(tag, cls, text) {
  var o = {tag: tag, className: cls || '', textContent: text || '', children: [], dataset: {}, attrs: {}, style: {},
    scrollTop: 0, tabIndex: -1, hidden: true, focused: 0,
    classList: {add: function () {}, remove: function () {}, toggle: function () {}},
    appendChild: function (c) { this.children.push(c); c.parent = this; return c; },
    setAttribute: function (k, v) { this.attrs[k] = v; }, removeAttribute: function (k) { delete this.attrs[k]; },
    getAttribute: function (k) { return this.attrs[k]; },
    click: function () { if (this.onclick) this.onclick(); },
    querySelector: function () { return {focus: function () {}}; },
    focus: function () { this.focused++; document.activeElement = this; },
    contains: function (x) { for (var p = x; p; p = p.parent) if (p === this) return true; return false; }};
  return o;
}
var el = mk;
function clear(x) { x.children = []; x.scrollTop = 0; }
function noI18n(x) { return x; }
function bytes(n) { return n + ' B'; }
var document = {activeElement: null, querySelectorAll: function () { return []; }};
'''


def node(code):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(code)
    try:
        p = subprocess.run(['node', f.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(f.name)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:                                   # noqa: BLE001
        return {'error': p.stdout + p.stderr}


# ---- W5 (client): a node's clock stepped back starts its series again --------------------------
js = 'var HLOAD = {series: {}, off: {}, tops: {}}; var HL_SPAN = 120;\n' + func(HL, 'hlAdd') + r'''
var r = {};
hlAdd('', [{at: 1000}, {at: 1001}, {at: 1002}]);
hlAdd('', [{at: 1001}, {at: 1003}]);
r.dedup = HLOAD.series[''].map(function (x) { return x.at; });
hlAdd('', [{at: 1000.5}]);                 /* a little back (< 5 s): ignored as before */
r.small = HLOAD.series[''].length;
var offWas = HLOAD.off[''];
hlAdd('', [{at: 700}, {at: 701}]);          /* five minutes back: begun again */
r.back = HLOAD.series[''].map(function (x) { return x.at; });
r.offReset = HLOAD.off[''] !== offWas;
hlAdd('', [{at: 702}]);
r.after = HLOAD.series[''].length;
hlAdd('', []);
r.empty = HLOAD.series[''].length;
console.log(JSON.stringify(r));
'''
o = node(js)
ok('W5 hlAdd keeps only newer readings', o.get('dedup') == [1000, 1001, 1002, 1003], o)
ok('W5 hlAdd: a second back changes nothing', o.get('small') == 4, o)
ok('W5 hlAdd: clock stepped back - series begun again', o.get('back') == [700, 701] and o.get('offReset'), o)
ok('W5 hlAdd: then goes on', o.get('after') == 3 and o.get('empty') == 3, o)

# ---- W2, W3: hloadDraw rebases HL_T0 after a day and keeps the focused chip ----------------------
js = DOM + r'''
var HLOAD = {look: 'graphs', others: null, ctx: null}; var HL_RUN_S = 86400, HLOAD_KEEP = 40;
var HL_T0 = Date.now() / 1000 - 86400 + 300;   /* the page open for nearly a day */
var host = mk('div'); host.id = 'hload';
function $(id) { return id === 'hload' ? host : null; }
function hpSample() { return {hist: {cpu: [], mem: [], disk: [], net: []}}; }
var painted = 0;
function hlPaint() { painted++; }
function hloadPanelDraw() {}
function hloadChips(h, d, hist, look, preview, peer) {
  ['cpu', 'mem', 'disk', 'net'].forEach(function (k) { var c = mk('span'); c.dataset.k = k; if (peer) c.dataset.node = peer; h.appendChild(c); });
}
function hloadChipOf(k, node) {
  for (var i = 0; i < host.children.length; i++) { var c = host.children[i]; if (c.dataset.k === k && (c.dataset.node || '') === (node || '')) return c; }
  return null;
}
''' + func(HL, 'hloadDraw') + r'''
var r = {};
hloadDraw({cpu: 1});
r.rebased = Math.abs(HL_T0 - Date.now() / 1000) < 5;
var t0 = HL_T0;
hloadDraw({cpu: 2});
r.kept = HL_T0 === t0;
/* the keyboard on the disk chip: after the redraw on the new disk chip */
var disk = hloadChipOf('disk', ''); disk.focus(); var old = disk;
hloadDraw({cpu: 3});
var now = hloadChipOf('disk', '');
r.focus = document.activeElement === now && now !== old && now.focused === 1;
/* the focus elsewhere: nothing focused by the redraw */
document.activeElement = mk('input');
hloadDraw({cpu: 4});
r.notStolen = hloadChipOf('disk', '').focused === 0;
/* a preview never rebases */
HL_T0 = Date.now() / 1000 - 86400;
var pv = mk('div'); hloadDraw({cpu: 5}, pv, 'pills');
r.previewNo = Date.now() / 1000 - HL_T0 > 80000;
console.log(JSON.stringify(r));
'''
o = node(js)
ok('W2 HL_T0 begun again before the day-long animation ends', o.get('rebased'), o)
ok('W2 HL_T0 not moved otherwise', o.get('kept'), o)
ok('W3 the focused chip keeps the focus across the redraw', o.get('focus'), o)
ok('W3 focus elsewhere not taken', o.get('notStolen'), o)
ok('W2 a preview does not touch HL_T0', o.get('previewNo'), o)
ok('W2 the live svgs are all made anew (run._on on fresh elements)', 'run._on' in func(HL, 'hlPaint')
   and 'clear(host)' in func(HL, 'hloadDraw'))

# ---- W4: the panel keeps its scrollTop ---------------------------------------------------------
js = DOM + r'''
var HLOAD = {open: 'cpu', openNode: '', others: [], ctx: null};
var panel = mk('div'); panel.id = 'hload-panel';
function $(id) { return id === 'hload-panel' ? panel : null; }
var st = 'tiles';
function hpStyle() { return st; }
function hpStyleDraw() {} function hpPeer() {} function hlPaint() {}
''' + func(HL, 'hloadPanelDraw') + r'''
var r = {};
hloadPanelDraw(); panel.scrollTop = 240;
hloadPanelDraw(); r.same = panel.scrollTop;
HLOAD.open = 'disk'; hloadPanelDraw(); r.other = panel.scrollTop;
panel.scrollTop = 90; st = 'table'; hloadPanelDraw(); r.style = panel.scrollTop;
console.log(JSON.stringify(r));
'''
o = node(js)
ok('W4 the same panel keeps where it was scrolled', o.get('same') == 240, o)
ok('W4 another chip opens at the top', o.get('other') == 0 and o.get('style') == 0, o)

# ---- W8: preview chips have no tab stop nor role; the real ones do -----------------------------
js = DOM + r'''
var HLOAD = {ctx: null};
function hpStyle() { return 'tiles'; }
function hloadPanelHooks() {}
''' + ''.join(func(HL, n) + '\n' for n in ('hloadRate', 'hlVal', 'hlWidth', 'hloadRing', 'hloadChips')) + r'''
var r = {};
['pills', 'line'].forEach(function (look) {
  var a = mk('div'), b = mk('div');
  var d = {cpu: 5, mem_used: 1, mem_total: 2, cores: 2};
  hloadChips(a, d, {}, look, true, '', 40);
  hloadChips(b, d, {}, look, false, '', 40);
  var chips = function (h) { return look === 'line' ? h.children[0].children.filter(function (x) { return x.dataset.k; }) : h.children; };
  r[look + 'Prev'] = chips(a).every(function (c) { return c.tabIndex === -1 && !c.attrs.role; }) && chips(a).length === 4;
  r[look + 'Real'] = chips(b).every(function (c) { return c.tabIndex === 0 && c.attrs.role === 'button'; }) && chips(b).length === 4;
});
console.log(JSON.stringify(r));
'''
o = node(js)
ok('W8 preview chips (pills, line): no tabIndex, no role', o.get('pillsPrev') and o.get('linePrev'), o)
ok('W8 header chips keep tabIndex 0 and role button', o.get('pillsReal') and o.get('lineReal'), o)

# ---- W7: the other node's network rate in words of its own -------------------------------------
peer = func(HL, 'hpPeer')
ok("W7 hpPeer no longer uses the bare 'down'/'up'", "kv('down'" not in peer and "kv('up'" not in peer, peer[-400:])
ok('W7 hpPeer: received / sent', "kv('received ↓'" in peer and "kv('sent ↑'" in peer)

# ---- W6: the second step by mail/SMS after a reload ------------------------------------------------
STUB6 = DOM + r'''
var forms = [], sends = 0;
function textBox(v, ph, cls) { var t = mk('input'); t.value = v || ''; t.addEventListener = function () {}; return t; }
function cmdButton(words) { var b = mk('button', '', words); return b; }
function setButtonIcon(b, i, w) { b.textContent = w; }
function api(what, body) { sends++; return API(body); }
var API = function () { return new Promise(function () {}); };
function mfaCodeForm(box, d, action, words) { var f = mk('form'); f.action = action; box.appendChild(f); forms.push(f); return f; }
function mfaOut() { return mk('button'); }
/* 1.0.259: what the newer helpers use of a page */
document.createTextNode = function (t) { var n = mk('span', '', t); return n; };
document.body = {contains: function () { return true; }};
function pkCan() { return false; }
var MFA_WORDS = {app: 'app', mail: 'mail', sms: 'sms'};
var setTimeout = function (f) { f(); };
''' + ''.join(func(CORE, f) for f in ('mmss', 'mfaSendPaint', 'mfaSentSay') if 'function ' + f + '(' in CORE) + func(CORE, 'mfaWay') + func(CORE, 'mfaDraw') + r'''
function find(n, pred) { if (pred(n)) return n; for (var i = 0; i < (n.children || []).length; i++) { var x = find(n.children[i], pred); if (x) return x; } return null; }
'''
js = STUB6 + r'''
var r = {};
/* check stage, mail: the box under Send at once */
var box = mk('div');
mfaDraw(box, {stage: 'check', kind: 'mail', dest: 'n***@x.cz', name: 'novak'});
var kids = box.children.map(function (x) { return x.tag; });
r.checkForm = forms.length === 1 && forms[0].action === 'check' && kids.indexOf('form') > kids.indexOf('button');
r.noSend = sends === 0;
/* a 429 on Send: the box still there, no second one */
API = function () { var e = new Error('a code went a moment ago'); e.status = 429; return Promise.reject(e); };
var send = find(box, function (x) { return x.tag === 'button' && x.textContent === 'Send the code'; });
send.onclick();
setImmediate(function () {
  r.after429 = forms.length === 1;
  /* enrol stage, a code went by SMS before the reload: that way opens with its box */
  forms = []; sends = 0;
  var b2 = mk('div');
  mfaDraw(b2, {stage: 'enrol', methods: ['app', 'mail', 'sms'], started: {kind: 'sms', dest: '+420 *** 456'}, name: 'novak'});
  r.enrolForm = forms.length === 1 && forms[0].action === 'enrol_confirm';
  r.enrolNoApp = sends === 0;          /* the app way (which asks for a new secret) not opened */
  var said = find(b2, function (x) { return /Sent to \+420/.test(x.textContent || ''); });
  r.enrolSaid = !!said;
  /* nothing started: the first way, as before */
  forms = []; sends = 0;
  var b3 = mk('div');
  mfaDraw(b3, {stage: 'enrol', methods: ['mail', 'sms'], started: null, name: 'novak'});
  r.plain = forms.length === 0 && sends === 0;
  /* started by the app: the first way as before */
  forms = []; sends = 0;
  var b4 = mk('div');
  mfaDraw(b4, {stage: 'enrol', methods: ['mail', 'sms'], started: {kind: 'app', dest: ''}, name: 'novak'});
  r.app = forms.length === 0;
  console.log(JSON.stringify(r));
});
'''
o = node(js)
ok('W6 check stage: the code box under Send from the start', o.get('checkForm') and o.get('noSend'), o)
ok('W6 check stage: after a 429 the one box stays', o.get('after429'), o)
ok('W6 enrol stage: d.started reopens that way with its box', o.get('enrolForm') and o.get('enrolNoApp')
   and o.get('enrolSaid'), o)
ok('W6 enrol stage: nothing started - as before', o.get('plain') and o.get('app'), o)

# ---- H5 (server): a since later than now ignored; history and peer de-dup begin again --------------
g = {'__name__': 'load', 'CONFIG': {'perf_meter': True, 'ha_mode': True}, 'route': lambda *a, **k: (lambda f: f),
     'log_sparing': lambda *a, **k: None, 'ApiError': Exception}
src = open(os.path.join(PARTS, '90r_load.py')).read()
src = re.sub(r"^@route\(.*$", '', src, flags=re.M)
exec('import os, re, json, time, threading\n' + src, g)
NOW = [10000.0]
g['time'] = type('T', (), {'time': staticmethod(lambda: NOW[0]), 'monotonic': staticmethod(time.monotonic),
                           'sleep': staticmethod(lambda s: None)})
OUTS = []
g['server_load'] = lambda fresh=False: dict(at=NOW[0], cpu=5.0, mem_used=1, mem_total=2)
for i in range(5):
    g['load_sample'](); NOW[0] += 1
h = g['load_history']
ok('H5 load_history: since in the past', [x['at'] for x in h(10002.0)] == [10003.0, 10004.0])
ok('H5 load_history: since a moment ahead (rounding) still honoured', h(10005.5) == [])
NOW[0] = 9000.0
ok('H5 load_history: since later than now ignored', len(h(10004.0)) == 5)
g['load_sample']()
ok('H5 load_sample: a reading far older than the last begins the history again',
   [x['at'] for x in g['LOAD_HIST']] == [9000.0], g['LOAD_HIST'])
ok('H5 load_history: since later than now - all of it', [x['at'] for x in h(10004.0)] == [9000.0])
NOW[0] = 9001.0
g['load_sample']()
NOW[0] = 9000.5
g['load_sample']()
ok('H5 load_sample: a small step back (< 5 s) keeps the history', len(g['LOAD_HIST']) == 3)

# the other node's rows
ROWS = []


class DB:
    def rows(self, q, a=()):
        return [dict(r) for r in ROWS]

    def run(self, *a):
        pass


class Store:
    db = DB()

    def set_meta(self, k, v):
        pass


g['ha_nodes'] = lambda store: [{'name': 'a', 'me': True}, {'name': 'b'}]
g['node_name'] = lambda: 'a'
g['load_now'] = lambda: {}
g['LOAD_LOOK']['until'] = time.monotonic() + 100
st = Store()


def peer(ats):
    ROWS[:] = [{'k': 'load:b', 'v': json.dumps({'asked': True, 'now': {}, 'hist': [{'at': a, 'cpu': 1} for a in ats]})}]
    g['load_ha_tick'](st)


peer([500.0])                          # the first look: only remembered
peer([500.0, 501.0, 502.0])
peer([501.0, 502.0, 503.0])
ok('H5 peer de-dup as before', [x['at'] for x in g['LOAD_HA']['peers']['b']['hist']] == [500.0, 501.0, 502.0, 503.0],
   g['LOAD_HA']['peers']['b'])
peer([200.0, 201.0])
ok('H5 peer clock stepped back: its history begins again',
   [x['at'] for x in g['LOAD_HA']['peers']['b']['hist']] == [200.0, 201.0], g['LOAD_HA']['peers']['b'])
peer([201.0, 202.0])
ok('H5 peer: then goes on', [x['at'] for x in g['LOAD_HA']['peers']['b']['hist']] == [200.0, 201.0, 202.0])
o = g['load_others'](st, {'b': 201.0})
ok('H5 load_others: since honoured', [x['at'] for x in o[0]['hist']] == [202.0], o)
o = g['load_others'](st, {'b': 503.0})
ok('H5 load_others: a since later than all the peer said - all of it', [x['at'] for x in o[0]['hist']] == [200.0, 201.0, 202.0], o)
o = g['load_others'](st, {'b': 205.0})
ok('H5 load_others: a since a little ahead still honoured', o[0]['hist'] == [], o)

# ---- P4 / W7: the Czech ------------------------------------------------------------------------------
cs = {}
exec(open('/home/claude/i18n/cs_255_web.py').read(), cs)
S, P = cs['S255_WEB'], cs['P255_WEB']
ok('cs: received / sent', 'received ↓' in S and 'sent ↑' in S)
php = open(os.path.join(os.path.dirname(OUT), 'otp-page.php')).read()
ok('cs: the 403 of otp-page.php', 'that request did not come from this page' in S
   and "'that request did not come from this page'" in php)
api = open(os.path.join(PARTS, '90_api.py')).read()
sso = open(os.path.join(PARTS, '90o_sso.py')).read()
what = re.findall(r"what='(refused sign-ins by the load balancer)'", sso)
ok('cs: the SSO throttle text is the one the daemon builds', len(what) == 2 and
   "'too many %s %s: try again in %s'" in api and "'from %s' % ip" in api and "'for this name'" in api)
for eng in P:
    ok('cs pattern slots kept: ' + eng[:50], sorted(re.findall(r'\{\d\}', eng)) == sorted(re.findall(r'\{\d\}', P[eng])))
built = ['too many %s %s: try again in %s' % (what[0], 'from {0}', '{1}'),
         'too many %s %s: try again in %s' % (what[0], 'for this name', '{0}')]
ok('cs: the patterns match the built messages', all(b in P for b in built), built)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
