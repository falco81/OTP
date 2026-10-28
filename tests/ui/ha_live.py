p='admin.js'; s=open(p).read()
def fn(s,sig):
    i=s.index(sig); j=s.index("\n}\n",i)+3; return i,j
def wrap_in(s, sig, start, endmark, var, live='live', indent='  '):
    i,j=fn(s,sig); b=s[i:j]
    a=b.index(start); e=b.index(endmark, a)
    nb=b[:a]+indent+"liveFill(%s, function (%s) {\n" % (var,var)+b[a+len(start):e]+indent+"}, %s);\n" % live + b[e:]
    return s[:i]+nb+s[j:]
s=s.replace("function drawHaAddr(d) {","function drawHaAddr(d, live) {",1)
s=wrap_in(s,"function drawHaAddr(d, live) {","  clear(host);\n","\n}\n","host")
s=s.replace("function drawHaRep(d) {","function drawHaRep(d, live) {",1)
s=wrap_in(s,"function drawHaRep(d, live) {","  clear(host);\n","  var paused = (r.incoming","host")
s=s.replace("  drawHaAddr(d);\n}","  drawHaAddr(d, live);\n}",1)
s=s.replace("function drawNodeSettings(nodes) {","function drawNodeSettings(nodes, live) {",1)
i,j=fn(s,"function drawNodeSettings(nodes, live) {"); b=s[i:j]
b=b.replace("""    var host = $('ha-own');
    clear(host);
""","""    liveFill($('ha-own'), function (host) {
""",1)
b=b.replace("""within seconds); the RADIUS clients must send to the port the node listens on.'));
  }).catch(oops);""","""within seconds); the RADIUS clients must send to the port the node listens on.'));
    }, !!live);
  }).catch(oops);""",1)
assert "!!live" in b
s=s[:i]+b+s[j:]
i,j=fn(s,"function loadHa() {"); b=s[i:j]
b=b.replace("function loadHa() {\n  loadVip();","function loadHa(live) {\n  loadVip(live);",1)
b=b.replace("drawNodeSettings(d.nodes);","drawNodeSettings(d.nodes, live);",1)
b=b.replace("""    var host = $('ha-nodes');
    clear(host);
    host.appendChild(listTable(""","""    liveFill($('ha-nodes'), function (host) {
    host.appendChild(listTable(""",1)
b=b.replace("""      return tr;
    }));
    var ch = $('ha-checks');
    clear(ch);
    (d.checks || []).forEach(function (c) {
      var p = el('p', 'note ' + (c.ok ? 'good' : (c.warn ? 'warn' : 'bad')));
      p.appendChild(noI18n(el('b', '', c.ok ? '✓ ' : (c.warn ? '! ' : '✗ '))));
      p.appendChild(el('span', '', c.says));
      ch.appendChild(p);
    });""","""      return tr;
    }));
    }, !!live);
    liveFill($('ha-checks'), function (ch) {
    (d.checks || []).forEach(function (c) {
      var p = el('p', 'note ' + (c.ok ? 'good' : (c.warn ? 'warn' : 'bad')));
      p.appendChild(noI18n(el('b', '', c.ok ? '✓ ' : (c.warn ? '! ' : '✗ '))));
      p.appendChild(el('span', '', c.says));
      ch.appendChild(p);
    });
    }, !!live);""",1)
b=b.replace("    drawHaRep(d);\n","    drawHaRep(d, !!live);\n",1)
assert b.count("!!live")==3, b.count("!!live")
s=s[:i]+b+s[j:]
old="""function loadVip() {
  if (!$('web-vip')) return;
  apiLatest('vip', 'web').then(function (d) { WEB.last = d; drawVip(d); explainWhatWasDrawn($('ha-vip-card')); }).catch(oops);"""
assert old in s
s=s.replace(old,"""function loadVip(live) {
  if (!$('web-vip')) return;
  apiLatest('vip', 'web').then(function (d) { WEB.last = d; if (live) liveRun(function () { drawVip(d); }); else drawVip(d); explainWhatWasDrawn($('ha-vip-card')); }).catch(oops);""",1)
old="""HA_LINK_POLL = setTimeout(function () { if (TAB === 'settings' && PANE === 'ha') loadHa(); }, 3000);"""
assert old in s
s=s.replace(old,"""HA_LINK_POLL = setTimeout(function () { if (TAB === 'settings' && PANE === 'ha') loadHa(true); }, 3000);""",1)
old="""  if (host.contains(document.activeElement) && document.activeElement.tagName === 'INPUT') return;
  clear(host);
  var lb = d.lb || {};"""
assert old in s
s=s.replace(old,"""  if (host.contains(document.activeElement) && liveControl(document.activeElement)) return;
  clear(host);
  var lb = d.lb || {};""",1)
open(p,'w').write(s)
