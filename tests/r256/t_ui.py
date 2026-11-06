#!/usr/bin/env python3
"""1.0.256 ui group (U1-U8): the admin pages as the API's roles, confirmations of one's own
account, the Test tab's node, the DB pane on a cluster, the settings-nodes poll after a failure,
and Czech. No daemon, no ports: node --check, node probes of the changed functions with stubs,
and i18n.js's own matcher run over cs.json and cs_256_ui.  Run: python3 t_ui.py 1.0.256"""
import json
import os
import re
import subprocess
import sys
import tempfile

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.256'
WEB = '/home/claude/build/out/otp-%s/web' % VER
AS = WEB + '/assets'
I18N_DIR = '/home/claude/i18n'
OK = [0, 0]


def check(cond, what):
    OK[1] += 1
    if cond:
        OK[0] += 1
        print('ok   ' + what)
    else:
        print('FAIL ' + what)


def src(name):
    with open(os.path.join(AS, name), encoding='utf-8') as f:
        return f.read()


def func(text, name):
    """The source of `function name(...) {...}`: braces counted outside strings, regexes and
    comments (good enough for these functions)."""
    m = re.search(r'\nfunction %s\(' % re.escape(name), text)
    assert m, name
    i = text.index('{', m.end())
    depth, j, n = 0, i, len(text)
    while j < n:
        c = text[j]
        if c in '\'"`':
            q = c
            j += 1
            while j < n and text[j] != q:
                j += 2 if text[j] == '\\' else 1
        elif text.startswith('//', j):
            j = text.index('\n', j)
        elif text.startswith('/*', j):
            j = text.index('*/', j) + 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[m.start() + 1:j + 1]
        j += 1
    raise AssertionError('unbalanced ' + name)


def node(js):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(js)
        p = f.name
    try:
        r = subprocess.run(['node', p], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(p)
    if r.returncode:
        print(r.stderr)
    return r.stdout.strip()


ADM = src('admin.js')

# ---- syntax -----------------------------------------------------------------------------
for f in ('admin.js', 'core.js', 'cols.js'):
    r = subprocess.run(['node', '--check', os.path.join(AS, f)], capture_output=True, text=True)
    check(r.returncode == 0, 'node --check %s' % f)

# ---- U1: token actions as the API --------------------------------------------------------
js = func(ADM, 'tokenMayReplace') + """
var out = [];
[[true, true], [false, true], [false, false]].forEach(function (r) {
  ADMIN = r[0]; TOKADMIN = r[1];
  out.push(['active', 'pending', 'disabled', undefined].map(tokenMayReplace));
});
console.log(JSON.stringify(out));
"""
got = json.loads(node('var ADMIN, TOKADMIN;\n' + js) or 'null')
check(got == [[True, True, True, True], [False, True, False, False], [False, False, False, False]],
      'U1 tokenMayReplace: full admin any, token admin a pending one, reader none')
tt = func(ADM, 'tokenTools')
check('tokenMayReplace(r && r.state)' in tt and 'tokenTools(r.name, r)' in ADM,
      'U1 row trash only where the API takes it away')
tp = func(ADM, 'tokenPeek')
check("var mayReplace = tokenMayReplace(t.state);" in tp, 'U1 token window knows mayReplace')
check(re.search(r"if \(mayReplace\) ph\.add\('Where they go'", tp) is not None,
      'U1 where codes go: editable only where the API allows')
check(re.search(r"if \(mayReplace\) ph\.add\('Test it, or another way'.*\[tst, toApp\]\);\s*"
                r"else ph\.add\('Test it'.*\[tst\]\);", tp) is not None,
      'U1 "The app instead" only where replacing is allowed; the test stays')
check("if (mayReplace && !sent) {" in tp and "if (TOKADMIN && !sent) {\n      var re" not in tp,
      'U1 New QR code only where replacing is allowed')
check(re.search(r"if \(ADMIN\) \{\s*nt\.add\('Move to'", tp) is not None, 'U1 Move only for a full admin')
check(re.search(r"if \(mayReplace\) \{[^\n]*\n\s*var del = cmdButton\('Take the token away'", tp)
      is not None, 'U1 Take the token away only where the API allows')

# ---- U2: whois buttons only for a token administrator ------------------------------------
check(re.search(r"if \(TOKADMIN\) \{\s*var who = iconButton\('person'", tt) is not None,
      'U2 row directory button for TOKADMIN only')
check("[whoBtn]" not in tp.split('} else {\n      grid.appendChild(rcCard);')[1].split('body.appendChild(grid)')[0],
      'U2 reader branch of the token window has no directory button')
check(re.search(r"r0\.appendChild\(m\);\s*r0\.appendChild\(whoBtn\);", tp) is not None,
      'U2 no-token window: directory button inside the TOKADMIN block')
check("u.source === 'directory' && TOKADMIN) info.onclick" in ADM, 'U2 accounts list whois for TOKADMIN only')

# ---- U3: own role / disable confirmed ------------------------------------------------------
js = func(ADM, 'userIsMe') + '\n' + func(ADM, 'roleWordsOf') + """
var ME = {name: 'Admin'};
console.log(JSON.stringify([userIsMe('admin'), userIsMe('ADMIN'), userIsMe('novak'), userIsMe(''),
  roleWordsOf([{role: 'readonly', words: 'read only'}], 'readonly'), roleWordsOf([], 'x')]));
ME = null; console.log(JSON.stringify(userIsMe('admin')));
"""
lines = node(js).splitlines()
check(lines and json.loads(lines[0]) == [True, True, False, False, 'read only', 'x'] and
      json.loads(lines[1]) is False, 'U3 userIsMe / roleWordsOf')
m = re.search(r"role\.onchange = function \(\) \{(.*?)\n        \};", ADM, re.S)
check(m and 'userIsMe(u.name)' in m.group(1) and 'role.value = u.role;' in m.group(1) and
      "confirmThen('Change your own role'" in m.group(1), 'U3 own role change asks first, list reset')
# The role handler run with stubs: own change asks, another's goes straight.
if m:
    body = m.group(1)
    js = func(ADM, 'userIsMe') + '\n' + func(ADM, 'roleWordsOf') + """
var ME = {name: 'admin'}, sent = [], asked = [];
function userDo(b) { sent.push(b.name + ':' + b.role); }
function htmlText(t) { return String(t); }
function confirmThen(t, w, b, go) { asked.push(t); go(); }
function make(u) { var d = {roles: [{role: 'readonly', words: 'read only'}]};
  var role = {value: u.role}; role.onchange = function () {""" + body + """
  }; return role; }
var r1 = make({name: 'novak', role: 'fulladmin'}); r1.value = 'readonly'; r1.onchange();
var r2 = make({name: 'admin', role: 'fulladmin'}); r2.value = 'readonly'; r2.onchange();
console.log(JSON.stringify([sent, asked, r2.value]));
"""
    got = json.loads(node(js) or 'null')
    check(got == [['novak:readonly', 'admin:readonly'], ['Change your own role'], 'fulladmin'],
          'U3 probe: another account at once, own one through the confirmation')
m = re.search(r"off\.onclick = function \(\) \{(.*?)\n        \};", ADM, re.S)
check(m and "confirmThen('Switch your own account off'" in m.group(1) and
      "confirmThen('Switch the account ' + u.name + ' off'" in m.group(1) and
      "userDo({action: 'enable'" in m.group(1), 'U3 disabling asks (own one more strongly); enabling does not')

# ---- U4: the Test tab names this node too ------------------------------------------------
js = func(ADM, 'loadTest') + """
var made = [];
var nsel = {value: '', appendChild: function (o) { made.push(o); }};
var item = {hidden: false};
function $(id) { return id === 'rt-node' ? nsel : (id === 'rt-node-item' ? item : {value: ''}); }
function clear() { made = []; }
function el(t, c, w) { return {text: w}; }
function api() { return {then: function () { return {catch: function () {}}; }}; }
function oops() {}
var STATUS = {nodes: [{name: 'otp1', me: true, alive: true}, {name: 'otp2', me: false, alive: true}]};
loadTest();
console.log(JSON.stringify(made.map(function (o) { return o.value; })));
"""
check(json.loads(node(js) or 'null') == ['otp1', 'otp2'], "U4 this node's option carries its name, not ''")

# ---- U5: engine buttons stay shut on a cluster ------------------------------------------
js = func(ADM, 'engineButtons') + """
var B = {}; ['db-engine-setup', 'db-engine-move', 'db-engine-empty', 'db-engine-use'].forEach(function (k) { B[k] = {disabled: true}; });
function $(id) { return B[id]; }
var CH = 'postgresql';
function engineChosen() { return CH; }
function state() { return Object.keys(B).map(function (k) { return B[k].disabled; }); }
var DBSTATE = {engine: 'sqlite', cluster: true}; engineButtons(); var a = state();
DBSTATE = {engine: 'sqlite', cluster: false}; engineButtons(); var b = state();
DBSTATE = {engine: 'postgresql', cluster: true}; CH = 'sqlite'; engineButtons(); var c = state();
console.log(JSON.stringify([a, b, c]));
"""
got = json.loads(node(js) or 'null')
check(got == [[True] * 4, [False] * 4, [True] * 4], 'U5 cluster: all four shut; standalone as before')

# ---- U6: the settings-nodes poll survives a failure ---------------------------------------
js = func(ADM, 'snLoad') + '\n' + func(ADM, 'snPace') + """
var SN = {d: null, poll: null, fast: 0, busy: false}, TAB = 'settings', delays = [], FAIL = true;
function snPills() {}
function setTimeout(f, ms) { delays.push(ms); return 1; }
function clearTimeout() {}
function api() { return FAIL ? Promise.reject(new Error('x')) : Promise.resolve({cluster: true, nodes: [], at: 0}); }
(async function () {
  for (var i = 0; i < 5; i++) await snLoad();
  FAIL = false; await snLoad();
  var ok = delays.slice();
  delays = []; SN.d = {cluster: false, nodes: []}; FAIL = true; await snLoad();
  var alone = delays.slice();
  delays = []; SN.d = null; TAB = 'radius'; await snLoad();
  console.log(JSON.stringify([ok, alone, delays, SN.fails]));
})();
"""
got = json.loads(node(js) or 'null')
check(got and got[0] == [15000, 30000, 60000, 120000, 120000, 15000],
      'U6 failures back off 15/30/60/120 s, a success goes back to the usual pace')
check(got and got[1] == [] and got[2] == [], 'U6 no poll on one known to stand alone, nor off the Settings tab')

# ---- U8: full administrators' cards --------------------------------------------------------
ls = func(ADM, 'loadSplit')
check("card.hidden = !cluster || !ADMIN;" in ls and "if (!cluster || !ADMIN) return;" in ls,
      'U8 the split card for a full admin only, and no refused request')
check("$('art-forget').hidden = !own || !ADMIN;" in ADM, 'U8 art-forget stays hidden for a non-admin')

# ---- U7: Czech, through i18n.js's own matcher ---------------------------------------------
sys.path.insert(0, I18N_DIR)
import cs_256_ui as M  # noqa: E402

TAG = re.compile(r'</?(b|i|code|kbd|em|strong)>')
extra = {'strings': {}, 'patterns': {}, 'rich': {}}
for k, v in M.S256_UI.items():
    extra['rich' if TAG.search(k) else 'strings'][k] = v
for k, v in M.P256_UI.items():          # as make_cs.py: tagged patterns are rich ones
    extra['rich' if TAG.search(k) else 'patterns'][k] = v
for d in (M.S256_UI, M.P256_UI):
    for k, v in d.items():
        check(re.findall(r'\{\d+\}', k) and sorted(set(re.findall(r'\{\d+\}', k))) ==
              sorted(set(re.findall(r'\{\d+\}', re.sub(r'\{(\d+):[^}]*\}', '', v)))) or
              not re.findall(r'\{\d+\}', k), 'U7 slots kept: ' + k[:60])
        check(TAG.findall(k) == TAG.findall(v), 'U7 tags kept: ' + k[:60])
probe = r"""
var fs = require('fs'), vm = require('vm');
var ctx = {window: {}, document: {documentElement: {classList: {remove: function () {}}, setAttribute: function () {}}, readyState: 'complete'},
  setTimeout: function () {}, Map: Map, Set: Set, WeakMap: WeakMap, MutationObserver: function () {}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(%(i18n)s, 'utf8'), ctx);
var cs = JSON.parse(fs.readFileSync(%(cs)s, 'utf8')), extra = %(extra)s;
var pack = {code: 'cs', strings: {}, patterns: [], rich: {}}, seenP = {};
['strings', 'patterns', 'rich'].forEach(function (sec) {
  Object.keys(cs[sec]).forEach(function (id) {
    var k = cs[sec][id].source, v = cs[sec][id].text;
    if (sec === 'patterns') { pack.patterns.push([k, v]); seenP[k] = 1; } else pack[sec][k] = v;
  });
});
/* make_cs.py adds these with setdefault: what is there already stays. */
Object.keys(extra.strings).forEach(function (k) { if (!(k in pack.strings)) pack.strings[k] = extra.strings[k]; });
Object.keys(extra.rich).forEach(function (k) { if (!(k in pack.rich)) pack.rich[k] = extra.rich[k]; });
Object.keys(extra.patterns).forEach(function (k) { if (!seenP[k]) pack.patterns.push([k, extra.patterns[k]]); });
ctx.PACK = pack;
vm.runInContext('i18nInit(PACK);', ctx);
vm.runInContext('function richOf(key) { key = i18nFold(key); var to = I18N.rich.get(key); if (to !== undefined) return to;'
  + ' for (var i = 0; i < I18N.richPats.length; i++) { var p = I18N.richPats[i]; if (p.lit && key.indexOf(p.lit) < 0) continue;'
  + ' var m = p.re.exec(key); if (m && !(p.weak && i18nWordy(m))) return i18nPlural(p.text, p.slots, m).replace(/\\{(\\d+)\\}/g,'
  + ' function (all, n) { var at = p.slots.indexOf(Number(n)); return at < 0 ? all : i18nSlot(m[at + 1], 0); }); } return null; }', ctx);
var tests = %(tests)s;
console.log(JSON.stringify(tests.map(function (t) { ctx.K = t[1]; return vm.runInContext(t[0] === 'rich' ? 'richOf(K)' : 'i18nText(K)', ctx); })));
"""
CASES = [
    ('rich', '<b>CN=Acme Root</b> is no longer trusted for the SMS gateway. The others stay.',
     'Certifikátu <b>CN=Acme Root</b> se u SMS brány přestane věřit. Ostatní zůstanou.'),
    ('rich', '<b>CN=Acme Root</b> is no longer trusted for the mail server. The others stay.',
     'Certifikátu <b>CN=Acme Root</b> se u poštovního serveru přestane věřit. Ostatní zůstanou.'),
    ('rich', '<b>CN=Acme Root</b> is no longer trusted for corp.cz. The others stay.',
     'Certifikátu <b>CN=Acme Root</b> se u adresáře corp.cz přestane věřit. Ostatní zůstanou.'),
    ('text', 'Time servers set 3 min ago', 'Časové servery nastaveny před 3 min'),
    ('text', 'Time servers NOT set 3 min ago', 'Časové servery NENASTAVENY před 3 min'),
    ('text', 'Time servers set 3 min ago: done', 'Časové servery nastaveny před 3 min: done'),
    ('text', '5 token(s) in otp.zip, locked', '5 tokenů v otp.zip, zamčeno'),
    ('text', '2 token(s) in otp.zip, not locked - left out, their keys cannot be opened here: a, b',
     '2 tokeny v otp.zip, nezamčeno – vynechány, jejich klíče tu nelze otevřít: a, b'),
    ('rich', 'novak no longer signs in with <code>SHA256:abc</code> (me@pc) on n1, n2.',
     'novak se už nepřihlásí klíčem <code>SHA256:abc</code> (me@pc) na n1, n2.'),
    ('rich', 'novak no longer signs in with <code>SHA256:abc</code> on n1.',
     'novak se už nepřihlásí klíčem <code>SHA256:abc</code> na n1.'),
    ('rich', 'Root no longer signs in with <code>SHA</code> on n1.',
     'Root se už nepřihlásí klíčem <code>SHA</code> na n1.'),
    ('rich', 'Put <b>VPN users</b> in this role, or take it out of it. It is a change like any other '
             'on this page — nothing happens until you save.',
     'Přidat <b>VPN users</b> do této role, nebo ji z ní vyjmout. Je to změna jako každá jiná na '
     'této stránce — nic se nestane, dokud neuložíte.'),
    ('text', 'tried until 03-11-2026 14:05', 'zkouší se do 03-11-2026 14:05'),
    ('text', 'Test it', 'Vyzkoušet'),
    ('text', 'Switch the account novak off', 'Vypnout účet novak'),
    ('text', 'Switch me off', 'Vypnout mě'),
    ('rich', 'You are signed in as <b>admin</b>. Switched off, you are signed out at once and cannot '
             'sign in again - only another full administrator can switch it back on.',
     'Jste přihlášeni jako <b>admin</b>. Po vypnutí budete hned odhlášeni a znovu se nepřihlásíte – '
     'zapnout ho zpět může jen jiný plný správce.'),
]
js = probe % {'i18n': json.dumps(AS + '/i18n.js'), 'cs': json.dumps(WEB + '/lang/cs.json'),
              'extra': json.dumps(extra, ensure_ascii=False),
              'tests': json.dumps([[c[0], c[1]] for c in CASES], ensure_ascii=False)}
got = json.loads(node(js) or '[]')
for c, g in zip(CASES, got + [None] * (len(CASES) - len(got))):
    check(g == c[2], 'U7 %s -> %s' % (c[1][:60], g))
# The new English of these pages has its Czech.
for s in ('Test it', 'A message the way a code goes, with a code that opens nothing.',
          'In the directory - asked by a token administrator or a full administrator',
          'Change your own role', 'Change my role', 'Switch your own account off', 'Switch me off',
          'It cannot sign in until it is switched on again; its sign-ins now are ended.'):
    check(s in ADM and s in M.S256_UI, 'U7 new string has Czech: ' + s[:50])

print('ALL %d / %d' % (OK[0], OK[1]))
sys.exit(0 if OK[0] == OK[1] else 1)
