# 1.0.293: the database servers in the header's meter - a row each after the nodes (only with
# an agent: /api/load has `dbservers`), its panel: the database and the machine.
#   python3 web.py OUT
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/hload.js', [
# the same lag for every row: the nodes' and the database servers'
("""    var many = !!(HLOAD.others && HLOAD.others.length);
""", """    var many = !!((HLOAD.others && HLOAD.others.length) || (HLOAD.dbs && HLOAD.dbs.length));
"""),
# the groups: the nodes, then the database servers
("""  var others = preview ? [] : (HLOAD.others || []);
  host.className = 'hload look-' + look + (preview ? ' hl-preview' : '') + (others.length ? ' hl-cluster' : '');
  clear(host);
  var was = HLOAD.ctx;
  HLOAD.ctx = preview ? null : '';
  if (!others.length) { hloadChips(host, d, hist, look, preview, '', HLOAD_KEEP); }
  else {
    [{node: HLOAD.node || '', d: d, hist: hist, keep: HLOAD_KEEP}].concat(others.map(function (o) {
      /* its last numbers kept while it is late (1.0.257), dimmed; none ever heard: a dash */
      return {node: o.node, d: o.now ? o.now : {late: true}, hist: hist, keep: HLOAD_KEEP, late: o.late || !o.now, error: o.error};
    })).forEach(function (g, i) {
      HLOAD.ctx = i ? g.node : '';
      var box = el('span', 'hl-node' + (i ? ' hl-peer' : ' hl-here') + (g.late ? ' hl-late' : ''));
      var name = noI18n(el('span', 'hl-name', g.node));
      name.title = i ? (g.late ? 'The other node ' + g.node + ' does not answer' + (g.error ? ': ' + g.error : '') : 'The other node: ' + g.node)
                     : 'This node, the one this page is on: ' + g.node;
      box.appendChild(name);
""", """  var others = preview ? [] : (HLOAD.others || []);
  /* the database servers of their own (1.0.293): a row each after the nodes - only with an
     agent (/api/load dbservers); this node's own row is named beside them */
  var dbs = preview ? [] : (HLOAD.dbs || []);
  host.className = 'hload look-' + look + (preview ? ' hl-preview' : '') + (others.length || dbs.length ? ' hl-cluster' : '');
  clear(host);
  var was = HLOAD.ctx;
  HLOAD.ctx = preview ? null : '';
  if (!others.length && !dbs.length) { hloadChips(host, d, hist, look, preview, '', HLOAD_KEEP); }
  else {
    [{node: HLOAD.node || '', d: d, hist: hist, keep: HLOAD_KEEP}].concat(others.map(function (o) {
      /* its last numbers kept while it is late (1.0.257), dimmed; none ever heard: a dash */
      return {node: o.node, d: o.now ? o.now : {late: true}, hist: hist, keep: HLOAD_KEEP, late: o.late || !o.now, error: o.error};
    })).concat(dbs.map(function (r) {
      var late = !!r.down || (Number(r.age) || 0) > 20;
      return {node: hlDbKey(r), d: r.down ? {late: true} : r, hist: hist, keep: HLOAD_KEEP, late: late, db: r};
    })).forEach(function (g, i) {
      HLOAD.ctx = i ? g.node : '';
      var box = el('span', 'hl-node' + (i ? ' hl-peer' : ' hl-here') + (g.late ? ' hl-late' : '') + (g.db ? ' hl-db' : ''));
      var name = noI18n(el('span', 'hl-name', g.db ? hlDbLabel(g.db, dbs) : g.node));
      if (g.db) {
        name.insertBefore(el('span', 'hl-dbic'), name.firstChild).innerHTML = '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/></svg>';
        name.title = g.db.down ? 'The database server of ' + g.db.node + ' - its agent does not answer'
                               : 'The database server of ' + g.db.node + (g.db.host ? ': ' + g.db.host : '');
      } else
      name.title = i ? (g.late ? 'The other node ' + g.node + ' does not answer' + (g.error ? ': ' + g.error : '') : 'The other node: ' + g.node)
                     : 'This node, the one this page is on: ' + g.node;
      box.appendChild(name);
"""),
# the panel of a database server
("""  var o = node ? (HLOAD.others || []).filter(function (x) { return x.node === node; })[0] || {} : null;
  var keep = [HLOAD.last, HLOAD.detail, HLOAD.ctx];
""", """  if (node.indexOf('db:') === 0) {
    var dr = (HLOAD.dbs || []).filter(function (x) { return hlDbKey(x) === node; })[0];
    if (dr) {
      var kc = HLOAD.ctx;
      HLOAD.ctx = node;
      p.className = 'hl-panel hp-tiles';
      try { hpDb(p, k, dr); } finally { HLOAD.ctx = kc; }
      p._key = key;
      p.scrollTop = top;
      hlPaint();
      return;
    }
    HLOAD.openNode = node = '';
  }
  var o = node ? (HLOAD.others || []).filter(function (x) { return x.node === node; })[0] || {} : null;
  var keep = [HLOAD.last, HLOAD.detail, HLOAD.ctx];
"""),
("""/* A - the tiles */
function hpTiles(p, k) {""", """/* The database servers of their own (1.0.293). Their key in the series and the panel:
   'db:NODE'; their name: the server's own short name, or db·NODE where that is not one. */
function hlDbKey(r) { return 'db:' + (r.node || ''); }
function hlDbLabel(r, all) {
  var h = String(r.server || '').split('.')[0];
  var ok = /^[A-Za-z][A-Za-z0-9-]*$/.test(h) && h !== 'localhost'
    && (all || []).filter(function (x) { return String(x.server || '').split('.')[0] === h; }).length <= 1;
  return ok ? h : 'db·' + (r.node || '?');
}
function hlLoads(l) {
  return (l || []).map(function (x) { var v = Number(x).toFixed(2); return typeof numDecimal === 'function' && numDecimal() === ',' ? v.replace('.', ',') : v; }).join(' / ');
}
/* Its panel: the graph of what was pointed at, then its database - the version, how long it
   runs, the connections, what waits to go over to the other server, the size - and the machine
   in numbers. */
function hpDb(p, k, r) {
  var db = r.db || {};
  var head = el('div', 'hp-head');
  var t = el('div', 'hp-dbt');
  t.appendChild(noI18n(el('b', 'hp-dbn', hlDbLabel(r, HLOAD.dbs))));
  var who = el('span', 'muted small');
  who.appendChild(el('span', '', 'the database server of'));
  who.appendChild(noI18n(el('span', '', ' ' + (r.node || '') + (r.host ? ' · ' + r.host : ''))));
  t.appendChild(who);
  head.appendChild(t);
  head.appendChild(el('span', 'hp-scale muted small', HP_TITLE[k]));
  p.appendChild(head);
  if (r.down) {
    p.appendChild(el('p', 'small hp-dbdown', 'Its agent does not answer - nothing read from it now.'));
    if (r.said) p.appendChild(noI18n(el('p', 'muted small', r.said)));
    return;
  }
  var big = el('div', 'hp-graph hl-' + k);
  big.innerHTML = hlLiveSvg(k, 400, 54, false, true);
  p.appendChild(big);
  p.appendChild(el('div', 'hp-span muted small', 'the last two minutes'));
  var row = function (host, kk, v, cls) {
    var r2 = el('div', 'hp-row hp-kv' + (cls ? ' ' + cls : ''));
    r2.appendChild(el('span', 'muted', kk));
    r2.appendChild(v && v.nodeType ? v : noI18n(el('b', '', v === null || v === undefined || v === '' ? '–' : String(v))));
    host.appendChild(r2);
  };
  var s1 = hpSec(p, 'The database');
  var eng = (db.engine || r.engine) === 'mariadb' ? 'MariaDB' : 'PostgreSQL';
  row(s1, 'Version', eng + (db.version ? ' ' + String(db.version).split(/[ -]/)[0] : ''));
  var run = el('b', db.running ? '' : 'hp-bad');
  run.appendChild(el('span', '', db.running ? 'running' : 'not running'));
  if (db.running && db.started) run.appendChild(noI18n(el('span', '', ' · ' + hlUp(Date.now() / 1000 - db.started))));
  row(s1, 'State', run);
  row(s1, 'Connections', db.connections === undefined || db.connections === null ? '–' : String(db.connections));
  if (db.repl_behind !== undefined && db.repl_behind !== null) row(s1, 'Waiting to go over (replication)', bytes(db.repl_behind));
  if (db.size !== undefined && db.size !== null) row(s1, 'The size of otp’s database', bytes(db.size));
  if (db.disk && db.disk.total) row(s1, 'Its data’s disk', bytes(db.disk.total - (db.disk.free || 0)) + ' / ' + bytes(db.disk.total));
  var tls = el('b', '');
  tls.appendChild(el('span', '', db.ssl ? 'on' : 'off'));
  row(s1, 'TLS', tls);
  var s2 = hpSec(p, 'The machine');
  row(s2, 'CPU', (r.cpu === undefined || r.cpu === null ? '…' : Math.round(r.cpu) + ' %') + (r.cores ? ' · ' + r.cores + ' ×' : '') + (r.load ? ' · ' + hlLoads(r.load) : ''));
  row(s2, 'RAM', r.mem_total ? bytes(r.mem_used) + ' / ' + bytes(r.mem_total) : '–');
  row(s2, 'Disk', '↓' + hloadRate(r.disk_rd) + ' ↑' + hloadRate(r.disk_wr));
  row(s2, 'Net', '↓' + hloadRate(r.net_rx) + ' ↑' + hloadRate(r.net_tx));
}
/* A - the tiles */
function hpTiles(p, k) {"""),
("""  HLOAD.others = null; HLOAD.last = null; HLOAD.had = false; HLOAD.series = {}; HLOAD.off = {}; HLOAD.tops = {};
  var h = $('hload');""", """  HLOAD.others = null; HLOAD.dbs = null; HLOAD.last = null; HLOAD.had = false; HLOAD.series = {}; HLOAD.off = {}; HLOAD.tops = {};
  var h = $('hload');"""),
# since: the nodes' only (the database servers' readings come whole each time)
("""  var since = Object.keys(HLOAD.series).filter(function (n) { return hlLast(n); })""",
 """  var since = Object.keys(HLOAD.series).filter(function (n) { return hlLast(n) && n.indexOf('db:') !== 0; })"""),
("""  else if (HLOAD.open && HLOAD.openNode) q += '&detail_node=' + encodeURIComponent(HLOAD.openNode);""",
 """  else if (HLOAD.open && HLOAD.openNode && HLOAD.openNode.indexOf('db:') !== 0) q += '&detail_node=' + encodeURIComponent(HLOAD.openNode);"""),
("""    HLOAD.others = d.others || null;
""", """    HLOAD.others = d.others || null;
    /* the database servers (1.0.293): their readings into the series as they come; known
       before this node's row is drawn, so it is named beside them at once */
    HLOAD.dbs = Array.isArray(d.dbservers) && d.dbservers.length ? d.dbservers : null;
    (HLOAD.dbs || []).forEach(function (r) {
      if (r.down || typeof r.at !== 'number' || r.cpu === undefined || r.cpu === null) return;
      hlAdd(hlDbKey(r), [{at: r.at, cpu: r.cpu, mem: r.mem_total ? 100 * r.mem_used / r.mem_total : 0,
                          disk_rd: r.disk_rd, disk_wr: r.disk_wr, net_rx: r.net_rx, net_tx: r.net_tx}]);
    });
"""),
])

edit('web/assets/hload.css', [
("""@media (max-width:1100px){.hload .hl-peer{display:none}}
""", """@media (max-width:1100px){.hload .hl-peer{display:none}}
/* the database servers of their own (1.0.293): named with a small cylinder, in violet */
.hload .hl-db .hl-name{display:inline-flex;align-items:center;gap:3px;color:var(--violet,#a371f7)}
.hload .hl-dbic{display:inline-flex;opacity:.9}
.hload .hl-db.hl-late .hl-name{color:var(--crit,#f85149)}
.hl-panel .hp-dbt{display:flex;flex-direction:column;gap:1px;min-width:0}
.hl-panel .hp-dbn{color:var(--violet,#a371f7)}
.hl-panel .hp-bad{color:var(--crit,#f85149)}
.hl-panel .hp-dbdown{color:var(--crit,#f85149);margin:8px 0 2px}
"""),
])
print('ok')
