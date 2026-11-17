# 1.0.301 web: the upgrade band - every node on a row of its own, as acme draws it.   python3 band.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


OLD = """  var how = el('div', 'upband-how');
  how.appendChild(noI18n(el('span', '', num(pc) + ' %')));
  var turn = p ? (p.steps || []).filter(function (st) { return st.state !== 'done'; })[0] : null;
  var mine = u && (!p || (turn && u.node === turn.name && (!u.id || u.id === p.id)));
  if (p && (p.steps || []).length > 1) {
    (p.steps || []).forEach(function (st) {
      var one = el('span', 'upband-node');
      one.appendChild(noI18n(el('b', '', st.name)));
      var w = UP_STATE[st.state] || UP_STATE.waiting;
      one.appendChild(el('span', 'tag ' + w[1], w[0]));
      how.appendChild(one);
    });
  }
  if (state === 'running') {
    var words = mine ? u.words : (turn && turn.part_words) || '';
    if (!words && turn) words = (UP_STATE[turn.state] || UP_STATE.waiting)[0];
    if (words) how.appendChild(el('span', '', words));
    if (mine && u.parts) how.appendChild(el('span', '', 'step ' + Math.min(u.part, u.parts) + ' of ' + u.parts));
  }
  host.appendChild(how);"""
NEW = """  /* How far as a whole, then every node on a row of its own (1.0.301, as acme draws it): its name,
     its step, how far, what happened, when - the one whose turn it is in the colour of a link. */
  var turn = p ? ((p.steps || []).filter(function (st) { return /^(draining|installing|checking|failed)$/.test(st.state || ''); })[0]
    || (p.steps || []).filter(function (st) { return st.state !== 'done'; })[0]) : null;
  var how = el('div', 'upband-how');
  how.appendChild(noI18n(el('span', '', num(pc) + ' %')));
  if (p && turn && state === 'running') {
    var tw = el('span', '');
    tw.appendChild(noI18n(el('span', '', turn.name + ': ')));
    tw.appendChild(el('span', '', (UP_STATE[turn.state] || UP_STATE.waiting)[0]));
    how.appendChild(tw);
  }
  if (p) how.appendChild(el('span', '', (p.steps || []).filter(function (st) { return st.state === 'done'; }).length + ' of '
    + (p.steps || []).length + ' node(s) done'));
  host.appendChild(how);
  var fileOf = function (st) { return !!u && (st._file || (u.node === st.name && (!u.id || !p || u.id === p.id))); };
  var filePc = function () { return u.state !== 'running' ? 100 : (u.parts ? Math.round(100 * Math.min(1, Math.max(0, u.part - 1) / u.parts)) : 3); };
  var rows = p ? (p.steps || []) : [{name: u.node || '', state: u.state === 'running' ? 'installing' : u.state, at: u.at, _file: true}];
  var tb = el('div', 'upband-rows');
  rows.forEach(function (st) {
    var r = el('div', 'upband-row' + (turn && state === 'running' && st.name === turn.name ? ' cur' : ''));
    r.appendChild(noI18n(el('span', 'upband-nm', st.name || '–')));
    var w = UP_STATE[st.state] || UP_STATE.waiting;
    var sc = el('span', 'upband-st');
    sc.appendChild(el('span', 'tag ' + w[1], w[0]));
    r.appendChild(sc);
    var mineRow = fileOf(st);
    var npc = st._file ? filePc() : (mineRow && st.state === 'installing' && u.parts
      ? Math.round(20 + 62 * Math.min(1, Math.max(0, u.part - 1) / u.parts)) : upPercent(st, p));
    r.appendChild(noI18n(el('span', 'upband-pc', num(npc) + ' %')));
    var what = el('span', 'upband-what');
    if (mineRow && u.state === 'running' && u.words) {
      what.appendChild(el('span', '', u.words));
      if (u.parts) what.appendChild(el('span', 'muted', 'step ' + Math.min(u.part, u.parts) + ' of ' + u.parts));
    } else if (st.state === 'installing' && st.part_words) {
      what.appendChild(el('span', '', st.part_words));
    } else if (st.said) {
      what.appendChild(el('span', '', st.said));
    }
    r.appendChild(what);
    r.appendChild(el('span', 'upband-when', st.at ? ago(st.at) : '–'));
    tb.appendChild(r);
  });
  host.appendChild(tb);"""

edit('admin.js', [
(OLD, NEW),
("""      ? 'The nodes are upgraded one at a time, each in maintenance while it is - the VPN and these pages go to the other one meanwhile. This page follows it and loads the new version by itself.'""",
 """      ? 'One node at a time: each is taken out of service - the VIP address, the load balancer and the VPN go to the other node - upgraded, checked and put back. This page follows it and loads the new version by itself.'"""),
])
edit('otp.css', [
("""  .upband-node{display:inline-flex;align-items:center;gap:6px}
  .upband-line{margin-top:6px;font-size:13px}""",
 """  .upband-how > span + span::before{content:"·";margin-right:8px;color:var(--tx-dim)}
  .upband-how{gap:4px 8px}
  /* Every node on a row of its own (1.0.301) */
  .upband-rows{margin-top:8px;border-top:1px solid rgba(88,166,255,.22)}
  .upband-row{display:grid;grid-template-columns:minmax(70px,9%) minmax(150px,13%) 64px minmax(0,1fr) auto;gap:4px 14px;
    align-items:center;padding:6px 0;border-bottom:1px solid rgba(88,166,255,.22);font-size:12.5px;min-width:0}
  .upband-nm{font-weight:600;overflow-wrap:anywhere}
  .upband-row.cur .upband-nm{color:var(--info)}
  .upband-pc{color:var(--tx-dim);font-variant-numeric:tabular-nums}
  .upband-what{display:flex;flex-wrap:wrap;gap:2px 10px;min-width:0;overflow-wrap:anywhere}
  .upband-when{color:var(--tx-dim);text-align:right;white-space:nowrap}
  .upband.bad .upband-rows,.upband.bad .upband-row{border-color:rgba(248,81,73,.25)}
  .upband.good .upband-rows,.upband.good .upband-row{border-color:rgba(63,185,80,.25)}
  @media (max-width:700px){
    .upband-row{grid-template-columns:auto auto 1fr auto}
    .upband-what{grid-column:1 / -1;order:5}
  }
  .upband-line{margin-top:8px;font-size:13px;font-weight:600}"""),
])
print('ok')
