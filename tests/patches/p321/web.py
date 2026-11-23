"""1.0.321 (web, OUTDIR): the page's decimal mark in the load meter, the time pane and the remote
backups' tries; the proxy's and isemon's tries ask one at a time and end once; the network's and
the power's looks one at a time; dates in the page's language."""
import re, sys, pathlib
OUT = pathlib.Path(sys.argv[1])
A = OUT / 'web/assets'


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(A / 'core.js', [
("""  return NUM_FMT.dec;
}
/** A number read back off the page, written either way. */
""",
 """  return NUM_FMT.dec;
}
/** n.toFixed(k) with the page's decimal mark (1.0.321). */
function numFixed(n, k) {
  var t = Number(n).toFixed(k);
  return numDecimal() === ',' ? t.replace('.', ',') : t;
}
/** A number read back off the page, written either way. */
"""),
("""  return n + ' · ' + new Date().toLocaleDateString();
""",
 """  return n + ' · ' + new Date().toLocaleDateString(numLang());
"""),
])

edit(A / 'hload.js', [
("""  if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' kB/s';
  return (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + ' MB/s';
""",
 """  if (n < 1024 * 1024) return numFixed(n / 1024, n < 10240 ? 1 : 0) + ' kB/s';
  return numFixed(n / 1048576, n < 10485760 ? 1 : 0) + ' MB/s';
"""),
("""(d.load ? ' · load ' + d.load.join(' / ') : '')""",
 """(d.load ? ' · load ' + d.load.map(function (v) { return numFixed(v, 2); }).join(' / ') : '')"""),
("""function hpGHz(m) { return m ? (m >= 1000 ? (m / 1000).toFixed(1) + ' GHz' : m + ' MHz') : ''; }""",
 """function hpGHz(m) { return m ? (m >= 1000 ? numFixed(m / 1000, 1) + ' GHz' : m + ' MHz') : ''; }"""),
("""c.mhz ? (c.mhz >= 1000 ? (c.mhz / 1000).toFixed(1) + ' GHz' : c.mhz + ' MHz') : ''""",
 """c.mhz ? hpGHz(c.mhz) : ''"""),
])

s = (A / 'admin.js').read_text()

# The proxy's try: one ask at a time, the end once, and only its own run's (1.0.321).
a0 = s.index("      var began = Date.now();\n      var look = function () {\n        api('proxy', {action: 'result', id: x.id})")
a1 = s.index("      setTimeout(look, 300);\n", a0) + len("      setTimeout(look, 300);\n")
blk = s[a0:a1]
assert blk.count('clearInterval(PX.poll); PX.poll = null; busy(go, false);') == 2, 'proxy ends'
blk = blk.replace('clearInterval(PX.poll); PX.poll = null; busy(go, false);', 'pxEnd();')
blk = blk.replace("      var look = function () {\n        api('proxy', {action: 'result', id: x.id}).then(function (r) {\n",
                  "      var asking = false, over = false, mine = null;\n"
                  "      var pxEnd = function () {\n"
                  "        over = true; clearInterval(mine);\n"
                  "        if (PX.poll === mine) { PX.poll = null; busy(go, false); }\n"
                  "      };\n"
                  "      var look = function () {\n"
                  "        if (asking || over) return;\n"
                  "        asking = true;\n"
                  "        api('proxy', {action: 'result', id: x.id}).then(function (r) {\n"
                  "          asking = false;\n"
                  "          if (over) return;\n", 1)
blk = blk.replace("        }).catch(function () {\n          /* Every answer failing: the minute ends it too (1.0.208). */\n",
                  "        }).catch(function () {\n          asking = false;\n          if (over) return;\n"
                  "          /* Every answer failing: the minute ends it too (1.0.208). */\n", 1)
assert blk.count('asking = false;') == 2, 'proxy catch'
blk = blk.replace("      PX.poll = setInterval(look, 1000);\n", "      PX.poll = mine = setInterval(look, 1000);\n", 1)
assert 'PX.poll = mine' in blk
s = s[:a0] + blk + s[a1:]

# isemon's try the same.
old_i = """      var timer = setInterval(function () {
        api('isemon', {action: 'tls_result', id: x.id}).then(function (r) {
"""
new_i = """      var asking = false, over = false;
      var timer = setInterval(function () {
        if (asking || over) return;
        asking = true;
        api('isemon', {action: 'tls_result', id: x.id}).then(function (r) {
          asking = false;
          if (over) return;
"""
assert s.count(old_i) == 1
s = s.replace(old_i, new_i)
old_e = """          if (!left.length || Date.now() - began > 60000) { clearInterval(timer); busy(b, false); }
        }).catch(function () {
          if (Date.now() - began > 60000) { clearInterval(timer); busy(b, false); }   /* (1.0.208) */
        });"""
new_e = """          if (!left.length || Date.now() - began > 60000) { over = true; clearInterval(timer); busy(b, false); }
        }).catch(function () {
          asking = false;
          if (over) return;
          if (Date.now() - began > 60000) { over = true; clearInterval(timer); busy(b, false); }   /* (1.0.208) */
        });"""
assert s.count(old_e) == 1
s = s.replace(old_e, new_e)

pairs = [
# The network's and the power's looks: one at a time, 8 s each - a node restarting held ten.
("""  if (TAB !== 'settings' || PANE !== 'network') { clearInterval(NET.poll); NET.poll = null; return; }
  api('net').then(function (d) {
    NET.d = d; NET.fails = 0; NET.failSince = 0;
""",
 """  if (TAB !== 'settings' || PANE !== 'network') { clearInterval(NET.poll); NET.poll = null; return; }
  if (NET.asking) return;   /* one at a time (1.0.321) */
  NET.asking = true;
  api('net', undefined, 8).then(function (d) {
    NET.asking = false;
    NET.d = d; NET.fails = 0; NET.failSince = 0;
"""),
("""  }).catch(function () {
    /* The page's own node restarting: it does not answer for a while. */
    NET.fails += 1;
""",
 """  }).catch(function () {
    NET.asking = false;
    /* The page's own node restarting: it does not answer for a while. */
    NET.fails += 1;
"""),
("""  if (TAB !== 'settings' || PANE !== 'power') { clearInterval(PW.poll); PW.poll = null; return; }
  api('power').then(function (d) {
    var wasAway = !!PW.failSince;
""",
 """  if (TAB !== 'settings' || PANE !== 'power') { clearInterval(PW.poll); PW.poll = null; return; }
  if (PW.asking) return;    /* one at a time (1.0.321) */
  PW.asking = true;
  api('power', undefined, 8).then(function (d) {
    PW.asking = false;
    var wasAway = !!PW.failSince;
"""),
("""  }).catch(function () { if (!PW.failSince) PW.failSince = Date.now(); drawPowerAway(); });
""",
 """  }).catch(function () { PW.asking = false; if (!PW.failSince) PW.failSince = Date.now(); drawPowerAway(); });
"""),
# The decimal mark.
("""  var n = a >= 100 ? a.toFixed(0) + ' s' : a >= 1 ? a.toFixed(1) + ' s' : (a * 1000).toFixed(0) + ' ms';
""",
 """  var n = a >= 100 ? a.toFixed(0) + ' s' : a >= 1 ? numFixed(a, 1) + ' s' : (a * 1000).toFixed(0) + ' ms';
"""),
("""  return (ms >= 0 ? '+' : '−') + (a >= 1000 ? (a / 1000).toFixed(2) + ' s' : (a >= 10 ? a.toFixed(1) : a.toFixed(3)) + ' ms');
""",
 """  return (ms >= 0 ? '+' : '−') + (a >= 1000 ? numFixed(a / 1000, 2) + ' s' : numFixed(a, a >= 10 ? 1 : 3) + ' ms');
"""),
("""t.freq !== undefined ? t.freq.toFixed(3) + ' ppm' : ''""",
 """t.freq !== undefined ? numFixed(t.freq, 3) + ' ppm' : ''"""),
("""x.ok ? 'It works (' + x.secs + ' s)' : 'It does not work'""",
 """x.ok ? 'It works (' + numFixed(x.secs || 0, 1) + ' s)' : 'It does not work'"""),
("""s.title = x.ok ? (x.secs + ' s' + """,
 """s.title = x.ok ? (numFixed(x.secs || 0, 1) + ' s' + """),
# Dates in the page's language.
("""tr.appendChild(el('td', 'small', x.at ? new Date(x.at * 1000).toLocaleString() : ''));
      var st = el('td', '');""",
 """tr.appendChild(el('td', 'small', x.at ? new Date(x.at * 1000).toLocaleString(numLang()) : ''));
      var st = el('td', '');"""),
("""function alDay(t) { return t ? new Date(t * 1000).toLocaleDateString() : '–'; }""",
 """function alDay(t) { return t ? new Date(t * 1000).toLocaleDateString(numLang()) : '–'; }"""),
("""'- put in ' + (x.at ? new Date(x.at * 1000).toLocaleString() : '?')""",
 """'- put in ' + (x.at ? new Date(x.at * 1000).toLocaleString(numLang()) : '?')"""),
("""'Looked at ' + new Date(n.at * 1000).toLocaleString()""",
 """'Looked at ' + new Date(n.at * 1000).toLocaleString(numLang())"""),
("""kt.at ? new Date(kt.at * 1000).toLocaleString() : ''""",
 """kt.at ? new Date(kt.at * 1000).toLocaleString(numLang()) : ''"""),
]
for a, b in pairs:
    n = s.count(a)
    assert n == 1, (n, a[:90])
    s = s.replace(a, b)
(A / 'admin.js').write_text(s)
