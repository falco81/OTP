# 1.0.292: the card "Database server" for this machine's database (db_local_card) - the tiles of
# the `local` rows of GET /api/db-agent.   python3 web.py OUT
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


JS = r"""/* ---- This machine's database as a database server (1.0.292, opt-in: db_local_card) ------
   Drawn from the `local` rows of GET /api/db-agent - only with the setting on and no agent. */
function dbaLocalOn(d) {
  d = d || DBA.d;
  return !!(d && !dbaOn(d) && (d.local || []).length);
}
function dbaLocalState(s) {
  var f = s.facts || {};
  if (s.stale) return ['warn', 'not heard from lately', ''];
  if (f.running === false) return ['bad', 'its database does not run', f.said || ''];
  return ['ok', 'answers', ''];
}
function dbaLocalAddr(s) {
  var h = String(s.host || 'localhost');
  if (h.charAt(0) === '/') return h;
  return (h.indexOf(':') >= 0 ? '[' + h + ']' : h) + ':' + (s.port || '?');
}
function dbaLocalDraw(host, d) {
  var rows = d.local || [];
  var me = rows.filter(function (s) { return s.me; })[0] || null;
  var one = me || rows[0];
  var full = typeof ME === 'object' && ME && ME.role === 'fulladmin';
  var st = dbaLocalState(one);
  var f = one.facts || {};
  var chip = el('span', 'dbs-state ' + st[0]);
  chip.appendChild(dbaDot(st[0]));
  chip.appendChild(el('span', '', st[1]));
  if (one.at) { chip.appendChild(noI18n(el('span', 'dbs-ago', ' · '))); chip.appendChild(el('span', 'dbs-ago', ago(one.at))); }
  var title = el('b', '');
  if (me) title.appendChild(el('span', '', rows.length > 1 ? 'Each node’s database is on its own machine' : 'This node’s database is on this machine'));
  else title.appendChild(haWords('This node’s database is on ', dbaLabel(one, rows), ''));
  var sub = el('div', 'small');
  sub.appendChild(noI18n(el('span', '', dbaEngine(one.engine || f.engine) + (f.version ? ' ' + String(f.version).split(/[ -]/)[0] : '') + ' · ')));
  sub.appendChild(noI18n(el('span', 'mono', dbaLocalAddr(one))));
  sub.appendChild(noI18n(el('span', '', ' · ')));
  sub.appendChild(el('span', '', 'looked at by each node itself - no agent'));
  host.appendChild(dbaHero(st[0] === 'bad' ? 'bad' : (st[0] === 'ok' ? 'good' : 'warn'), 'db', title, sub, chip));
  if (st[0] === 'bad' && st[2]) host.appendChild(noI18n(el('div', 'note bad dbs-said', st[2])));
  var grid = el('div', 'dbs-grid');
  rows.forEach(function (s) { grid.appendChild(dbaLocalTile(s, rows)); });
  host.appendChild(grid);
  if (!full) return;
  var acts = el('div', 'btnrow dbs-acts');
  var look = cmdButton('Look now', 'refresh', '');
  look.id = 'dba-look';
  explain(look, 'Look at this node’s database server now, rather than within 30 s.');
  look.onclick = function () { dbaAct(look, 'look'); };
  acts.appendChild(look);
  /* What otp already does for a database on this machine, and only that: the certificate it
     gave PostgreSQL - the link's between the databases (High availability) or Encryption to the
     database server's - and its restart for settings waiting. */
  if (rows.some(function (s) { return s.cert_by === 'link'; })) {
    var rl = cmdButton('Renew the certificate', 'key', '');
    rl.id = 'dba-renew';
    explain(rl, 'The certificates of the link between the databases, made again on both nodes as High availability does - PostgreSQL reloaded, not restarted; replication goes on.');
    rl.onclick = function () {
      confirmThen('Encrypt and check the link between the databases?',
        'Both nodes go through the steps by themselves; replication goes on meanwhile. A step that does not work stops there and leaves what is in use as it was.',
        'Start', function () {
          busy(rl, true);
          api('ha', {action: 'tls_link'}).then(function (x) { toast(x.message, 'good'); dbaPane(); })
            .catch(oops).then(function () { busy(rl, false); });
        }, false);
    };
    acts.appendChild(rl);
  } else if (rows.some(function (s) { return s.cert_by === 'dbtls'; }) && typeof dbtSteps === 'function') {
    var rn = cmdButton('Renew the certificate', 'key', '');
    rn.id = 'dba-renew';
    explain(rn, 'A new certificate from otp’s own authority for the PostgreSQL of each node, now, not 45 days before the end - as Encryption to the database server does. The connections go on.');
    rn.onclick = function () { dbtSteps([{label: 'a new certificate', body: {action: 'apply', phase: 'server', renew: true}}], function () { dbaPane(); }); };
    acts.appendChild(rn);
  }
  if (me && me.restart && me.restart.may && typeof tuneRestartAsk === 'function') {
    var rs = cmdButton('Restart the database…', 'power', '');
    rs.id = 'dba-restart';
    explain(rs, 'PostgreSQL on this machine started again for the settings waiting for its next start, and waited for (asked first).');
    rs.onclick = function () { tuneRestartAsk(); };
    acts.appendChild(rs);
  }
  host.appendChild(acts);
}
function dbaLocalTile(s, rows) {
  var f = s.facts || {};
  var st = dbaLocalState(s);
  var t = el('div', 'dbs-tile ' + st[0] + (s.me ? ' me' : ''));
  var top = el('div', 'dbs-tile-top');
  top.appendChild(dbaDot(st[0]));
  top.appendChild(noI18n(el('b', 'dbs-tile-n', dbaLabel(s, rows))));
  var tag = el('span', 'tag ' + (s.me ? 'info' : 'dim'));
  if (s.me) tag.appendChild(el('span', '', 'this node’s'));
  else { tag.appendChild(el('span', '', 'node')); tag.appendChild(noI18n(el('span', '', ' ' + s.node))); }
  top.appendChild(tag);
  var eng = el('span', 'dbs-eng');
  eng.appendChild(noI18n(el('span', '', dbaEngine(s.engine || f.engine) + (f.version ? ' ' + String(f.version).split(/[ -]/)[0] : ''))));
  top.appendChild(eng);
  t.appendChild(top);
  var kv = el('div', 'dbs-kvs');
  dbaKv(kv, 'Address', noI18n(el('span', 'mono', dbaLocalAddr(s))));
  var run = el('span', f.running === false ? 'bad' : (f.running ? 'good' : 'muted'));
  run.appendChild(el('span', '', f.running === false ? 'not running' : (f.running ? 'running' : '–')));
  if (f.started && f.running) run.appendChild(noI18n(el('span', '', ' · ' + dbaUp(Date.now() / 1000 - f.started))));
  dbaKv(kv, 'The database', run);
  dbaKv(kv, 'TLS', el('span', f.ssl ? 'good' : 'muted', f.ssl === undefined ? '–' : (f.ssl ? 'on' : 'off')));
  if (s.cert_end) {
    var dl = dbaDays(s.cert_end);
    dbaKv(kv, 'Its certificate ends', noI18n(el('span', dl !== null && dl < 14 ? 'bad' : '', dbaDate(s.cert_end))));
  }
  dbaKv(kv, 'Connections', f.connections === undefined ? '–' : num(f.connections));
  if (f.disk && f.disk.total) {
    var used = f.disk.total - (f.disk.free || 0);
    var dk = el('span', 'dbs-diskv');
    dk.appendChild(dbaBar(100 * used / f.disk.total));
    dk.appendChild(noI18n(el('span', 'small', bytes(used) + ' / ' + bytes(f.disk.total))));
    dbaKv(kv, 'Its data’s disk', dk, 'wide');
  }
  if (f.ram) {
    var rm = el('span', 'dbs-diskv');
    rm.appendChild(dbaBar(100 * (f.ram - (f.avail || 0)) / f.ram));
    rm.appendChild(noI18n(el('span', 'small', bytes(f.ram - (f.avail || 0)) + ' / ' + bytes(f.ram))));
    dbaKv(kv, 'RAM', rm, 'wide');
  }
  dbaKv(kv, 'Processors', (f.cpus ? num(f.cpus) : '–') + (f.load ? ' · ' + f.load.map(function (x) { var v = Number(x).toFixed(2); return numDecimal() === ',' ? v.replace('.', ',') : v; }).join(' / ') : ''));
  dbaKv(kv, 'Up for', f.uptime ? dbaUp(f.uptime) : '–');
  var hd = el('span', st[0] === 'ok' ? '' : 'bad');
  hd.appendChild(el('span', '', s.at ? ago(s.at) : 'not yet'));
  dbaKv(kv, 'Last heard', hd);
  t.appendChild(kv);
  if (st[0] !== 'ok') t.appendChild(el('div', 'dbs-tile-said small ' + st[0], st[1]));
  if (st[2]) t.appendChild(noI18n(el('div', 'dbs-tile-said small bad', st[2])));
  return t;
}
"""

edit('web/assets/admin.js', [
("""function dbaLocalOn(d) { return false; }
function dbaLocalDraw(host, d) { dbaDraw(host, d); }
""", JS),
])
print('ok')

# The hero of the card on a phone (1.0.292): the state below the title, not beside it - the
# title had a column of a word or two (the agent's card too).
edit('web/assets/otp.css', [
("""  .dbs-state{order:3}
""", """  .dbs-state{order:3}
  .dbs-hero-w{flex:1 1 calc(100% - 64px)}
"""),
])
print('ok css')
