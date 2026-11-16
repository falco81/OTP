/* ==== The database on a server of its own (1.0.289, docs/external-database.md) ============
   otp-db-agent on the database server looks after it as the root helper looks after one on
   this machine. Here: the card of Settings → The database (where the database is, its server,
   what can be done to it), the wizard that connects one, the database servers' dots beside
   the nodes on the cards whose settings reach them too (DB TLS, the link and replication,
   the server's own settings, the firewall's database port) and their rows on High
   availability. Without an agent none of it draws anything: every card is as it was. */
var DBA = {d: null, at: 0, ask: null, look: false};
function dbaTr(s) { return (typeof i18nText === 'function' && i18nText(s)) || s; }
/* An agent on this node or a database server known to the cluster. */
function dbaOn(d) {
  d = d || DBA.d;
  return !!(d && ((d.servers || []).length || String(d.db_admin || '').indexOf('agent:') === 0));
}
/* /api/db-agent, read once for every card that asks within a few seconds. */
function dbaLoad(fresh) {
  if (!fresh && DBA.d && Date.now() - DBA.at < 8000) return Promise.resolve(DBA.d);
  if (DBA.ask && !fresh) return DBA.ask;
  DBA.ask = api('db-agent').then(function (d) {
    DBA.d = d; DBA.at = Date.now(); DBA.ask = null; return d;
  }, function (e) { DBA.ask = null; throw e; });
  return DBA.ask;
}
/* The name a database server is shown by: its own short host name where that tells it from
   the other, else "db · " and the node it belongs to. */
function dbaShort(h) {
  h = String(h || '').split('.')[0];
  return /^[A-Za-z][A-Za-z0-9-]*$/.test(h) && h !== 'localhost' ? h : '';
}
function dbaLabel(s, all) {
  var h = dbaShort((s.facts || {}).host || s.server);
  var same = (all || []).filter(function (x) { return dbaShort((x.facts || {}).host || x.server) === h; }).length;
  return h && same <= 1 ? h : 'db · ' + (s.node || '?');
}
/* [dot, words, said]: answering and its database running, not heard from lately, its agent
   not answering, its database down - or not looked at yet. */
function dbaState(s) {
  var f = s.facts || {};
  if (s.ok === false) return ['bad', 'its agent does not answer', s.said || ''];
  if (s.stale) return ['warn', 'not heard from lately', ''];
  if (s.ok && f.running === false) return ['bad', 'its database does not run', f.said || ''];
  if (s.ok) return ['ok', 'answers', ''];
  return ['off', 'not looked at yet', ''];
}
function dbaDot(st) { return el('span', 'dot ' + (st === 'bad' ? 'crit' : st)); }
function dbaEngine(e) { return e === 'mariadb' ? 'MariaDB' : 'PostgreSQL'; }
function dbaWhere(s) { return s.db_host || s.host || '?'; }
function dbaDays(ts) { return ts ? Math.round((ts * 1000 - Date.now()) / 86400000) : null; }
function dbaDate(ts) { return ts ? new Date(ts * 1000).toLocaleDateString(numLang()) : '–'; }
/* The pill of a card: a dot and a name for each database server, what each one's agent said
   when it is pointed at, and what of the card reaches it. */
function dbaPill(servers, key) {
  servers = servers || [];
  if (!servers.length) return null;
  var col = {ok: 'var(--ok,#3fb950)', warn: 'var(--warn,#d29922)', bad: 'var(--crit,#f85149)', off: 'var(--tx-mut)'};
  var pill = el('span', 'dbs-pill');
  pill.dataset.dbs = key || '';
  var worst = 'ok';
  var rows = servers.map(function (s) {
    var st = dbaState(s);
    if (st[0] === 'bad' || (st[0] === 'warn' && worst !== 'bad') || (st[0] === 'off' && worst === 'ok')) worst = st[0];
    var one = el('span', 'dbs-one');
    one.appendChild(dbaDot(st[0]));
    one.appendChild(noI18n(el('span', 'dbs-n', dbaLabel(s, servers))));
    pill.appendChild(one);
    return '<tr><td><span class="dot ' + (st[0] === 'bad' ? 'crit' : st[0]) + '"></span></td><td class="sn-n">' + richText(dbaLabel(s, servers))
      + '</td><td class="mono small">' + richText((s.db_host || s.host || '') + (s.port ? ' · ' + dbaTr('agent') + ' :' + s.port : '')) + '</td>'
      + '<td style="color:' + col[st[0]] + '">' + richText(dbaTr(st[1])) + (st[2] ? '<div class="small muted">' + richText(st[2]) + '</div>' : '')
      + (s.at ? '<div class="small muted">' + richText(dbaTr('heard from') + ' ' + dbaTr(ago(s.at))) + '</div>' : '') + '</td></tr>';
  });
  pill.classList.toggle('diff', worst !== 'ok');
  var what = ((DBA.d || {}).applies || {})[key] || '';
  explain(pill, worst === 'ok' ? 'The database servers: what this card does reaches them through their agents, and each answers.'
    : 'The database servers: what this card does reaches them through their agents - not every one answers now.',
    '<table class="sn-pop">' + rows.join('') + '</table>'
    + (what ? '<div class="small muted" style="margin-top:6px">' + richText(dbaTr('Done on them:') + ' ' + dbaTr(what)) + '</div>' : ''));
  return pill;
}
/* Put (or take away) the pill in a card's heading. */
function dbaPillInto(h, servers, key) {
  if (!h) return;
  var old = h.querySelector(':scope > .dbs-pill');
  var pill = dbaOn() || (servers || []).length ? dbaPill(servers, key) : null;
  if (old && pill) h.replaceChild(pill, old);
  else if (old) old.remove();
  else if (pill) h.appendChild(pill);
}
function dbaServers(from) {
  return (from && from.length ? from : ((DBA.d || {}).servers || []));
}

/* ---- Settings → The database: the card of the database server ---------------------------- */
function dbaPane() {
  return dbaLoad(true).then(function (d) {
    dbaCard(d);
    dbaPillInto($('db-tune-card') && $('db-tune-card').querySelector(':scope > h2'), d.servers, 'db_tune');
    dbaPillInto($('db-tls-card') && $('db-tls-card').querySelector(':scope > h2'), d.servers, 'dbtls');
  }).catch(function () { /* the cards stay as they were */ });
}
/* Shown with an agent, or for a database on a server elsewhere (the way to connect its
   agent); never for one on this machine without an agent, nor for a shared pair. */
function dbaCardWanted(d) {
  if (!d) return false;
  if (dbaOn(d)) return true;
  if (dbaLocalOn(d)) return true;                      /* this machine's, opted in (1.0.289) */
  var w = d.where || {};
  return w.kind === 'unmanaged' && d.ha_mode !== 'shared' && !d.ha_mode;
}
function dbaCard(d) {
  var card = $('db-agent-card');
  if (!dbaCardWanted(d)) { if (card) card.remove(); return; }
  if (!card) {
    card = el('div', 'card full dbs-card');
    card.id = 'db-agent-card';
    card.appendChild(el('h2', '', 'Database server'));
    var body = el('div', '');
    body.id = 'db-agent';
    card.appendChild(body);
    var at = $('db-tls-card');
    if (at && at.parentNode) at.parentNode.insertBefore(card, at);
    else if ($('pane-db')) $('pane-db').appendChild(card);
  }
  dbaPillInto(card.querySelector(':scope > h2'), d.servers, 'dbtls');
  liveFill($('db-agent'), function (host) { (dbaLocalOn(d) ? dbaLocalDraw : dbaDraw)(host, d); });
  explainWhatWasDrawn(card);
}
function dbaHero(cls, icon, title, sub, side) {
  var box = el('div', 'dbs-hero ' + cls);
  var ic = el('span', 'dbs-hero-ic');
  ic.innerHTML = iconMarkup(icon, 24);
  box.appendChild(ic);
  var w = el('div', 'dbs-hero-w');
  w.appendChild(title.nodeType ? title : el('b', '', title));
  if (sub) w.appendChild(sub.nodeType ? sub : el('div', 'small', sub));
  box.appendChild(w);
  if (side) box.appendChild(side);
  return box;
}
function dbaDraw(host, d) {
  var w = d.where || {};
  var me = (d.servers || []).filter(function (s) { return s.me; })[0] || null;
  var full = typeof ME === 'object' && ME && ME.role === 'fulladmin';
  if (!dbaOn(d)) {
    /* A server elsewhere, its administrator's: otp only connects to it. */
    var t0 = el('b', '');
    t0.appendChild(noI18n(el('span', '', dbaEngine(w.engine) + ' ')));
    t0.appendChild(noI18n(el('span', 'mono', (w.host || '?') + (w.port ? ':' + w.port : ''))));
    t0.appendChild(el('span', '', ' - a server no agent looks after'));
    host.appendChild(dbaHero('plain', 'db', t0,
      'otp only connects to it: its certificate, its settings and their restart are its administrator’s. With otp-db-agent on that server otp looks after it as it would one on this machine - and the meter in the header shows it.'));
    var row = el('div', 'btnrow');
    if (full) {
      var c = cmdButton('Connect a database server…', 'plug', 'primary');
      c.id = 'dba-connect';
      c.onclick = function () { dbaWizard(); };
      row.appendChild(c);
    }
    host.appendChild(row);
    return;
  }
  var st = me ? dbaState(me) : ['off', 'not looked at yet', ''];
  var f = (me && me.facts) || {};
  var chip = el('span', 'dbs-state ' + st[0]);
  chip.appendChild(dbaDot(st[0]));
  chip.appendChild(el('span', '', st[1]));
  if (me && me.at) { chip.appendChild(noI18n(el('span', 'dbs-ago', ' · '))); chip.appendChild(el('span', 'dbs-ago', ago(me.at))); }
  var title = el('b', '');
  if (w.kind === 'agent') {
    title.appendChild(haWords('This node’s database is on ', (f.fqdn || f.host || d.db_host || d.host || '?'), ''));
  } else if (w.kind === 'here' || w.kind === 'file') {
    title.appendChild(el('span', '', w.kind === 'file' ? 'This node’s database is still the file on this machine' : 'This node’s database is still on this machine'));
  } else {
    title.appendChild(haWords('This node’s database is on ', (w.host || '?'), ' - not the agent’s server'));
  }
  var sub = el('div', 'small');
  sub.appendChild(haWords('Looked after by otp-db-agent at ', (d.host || '?') + ':' + (d.port || '?'), ' · ' + dbaEngine(d.engine) + ' ', f.version ? String(f.version).split(/[ -]/)[0] : '', ''));
  host.appendChild(dbaHero(st[0] === 'bad' ? 'bad' : (w.kind === 'agent' ? (st[0] === 'ok' ? 'good' : 'warn') : 'warn'), 'db', title, sub, chip));
  if (st[0] === 'bad' && st[2]) host.appendChild(el('div', 'note bad dbs-said', st[2]));
  if (w.kind !== 'agent' && full) {
    var nx = el('div', 'note info dbs-next');
    nx.appendChild(el('span', '', w.kind === 'unmanaged'
      ? 'The agent’s server is ready, but this node uses another database server. Move the database onto the agent’s server to have it looked after.'
      : 'The agent’s server is ready: move this node’s database onto it - a copy made first, every row copied and checked, otp started again on it.'));
    var mv = cmdButton('Move it onto the database server…', 'db', 'small primary');
    mv.id = 'dba-move';
    mv.onclick = function () { dbaMove(d); };
    nx.appendChild(mv);
    host.appendChild(nx);
  }
  var grid = el('div', 'dbs-grid');
  (d.servers || []).forEach(function (s) { grid.appendChild(dbaTile(s, d)); });
  if (!(d.servers || []).length) grid.appendChild(el('p', 'note muted', 'Not looked at yet - it is looked at every 30 s.'));
  host.appendChild(grid);
  if (full) {
    var acts = el('div', 'btnrow dbs-acts');
    var look = cmdButton('Look now', 'refresh', '');
    look.id = 'dba-look';
    explain(look, 'Ask the agent now what its server is like, rather than within 30 s.');
    look.onclick = function () { dbaAct(look, 'look'); };
    acts.appendChild(look);
    var rn = cmdButton('Renew the certificates', 'key', '');
    rn.id = 'dba-renew';
    explain(rn, 'A new certificate for the agent (a new key, made on its server) and a new client certificate for this node, now, both from otp’s own authority - rather than when they near their end (the agent’s 60 days before, this node’s 45). Nothing stops.');
    rn.onclick = function () { dbaAct(rn, 'renew'); };
    acts.appendChild(rn);
    var rs = cmdButton('Restart the database…', 'power', '');
    rs.id = 'dba-restart';
    explain(rs, 'The database server restarted by its agent, and waited for. Every connection to it is cut for a few seconds.');
    rs.onclick = function () {
      confirmThen('Restart the database server?', htmlText('The agent restarts ' + dbaEngine(d.engine) + ' on ' + (d.db_host || d.host) + ' and waits for it. Every connection is cut for a few seconds'
        + (d.ha_mode === 'replicated' ? '; replication catches up by itself afterwards.' : ' - this node’s pages and RADIUS wait for it meanwhile.')), 'Restart it', function () { dbaAct(rs, 'restart'); });
    };
    acts.appendChild(rs);
    if (d.engine === 'mariadb') {
      var tl = cmdButton(f.ssl ? 'Give MariaDB a new certificate' : 'Turn TLS on', 'lock', f.ssl ? '' : 'primary');
      tl.id = 'dba-mytls';
      explain(tl, 'MariaDB given a certificate from otp’s own authority by its agent (restarted the first time, reloaded after) - renewed by itself 45 days before it ends. Then Database → TLS moves this node’s connection to verify-full.');
      tl.onclick = function () { dbaAct(tl, 'mariadb_tls'); };
      acts.appendChild(tl);
    }
    /* Not while this node's database is on the agent's server in a cluster (layout B, 1.0.289):
       the replication runs through it - the cluster is taken apart first. */
    if (!d.forget_refused) {
      var fg = cmdButton('Forget the agent…', 'forget', 'danger');
      fg.id = 'dba-forget';
      explain(fg, 'This node goes back to looking after a database on this machine only. The agent is told this node leaves it and takes it off its list (if it does not answer, it keeps this node’s certificate until otp_db_agent.py --forget NODE there); the database and its data are not touched.');
      fg.onclick = function () {
        confirmThen('Forget the database agent?', htmlText('otp no longer renews the database server’s certificate, changes its settings or restarts it, and its row leaves the meter. The database itself is not touched, and this node goes on using it. Connected again with a new join code.'),
          'Forget it', function () { dbaAct(fg, 'forget'); });
      };
      acts.appendChild(fg);
    }
    host.appendChild(acts);
  }
}
function dbaKv(box, k, v, cls) {
  var r = el('div', 'dbs-kv' + (cls ? ' ' + cls : ''));
  r.appendChild(el('span', 'k', k));
  var vv = el('span', 'v');
  if (v && v.nodeType) vv.appendChild(v); else vv.appendChild(noI18n(el('span', '', v === null || v === undefined || v === '' ? '–' : String(v))));
  r.appendChild(vv);
  box.appendChild(r);
  return r;
}
function dbaBar(pct) {
  var b = el('span', 'dbs-bar' + (pct >= 90 ? ' hot' : (pct >= 75 ? ' warm' : '')));
  var f = el('span', '');
  f.style.width = Math.max(0, Math.min(100, pct)) + '%';
  b.appendChild(f);
  return b;
}
function dbaUp(sec) {
  sec = Math.round(sec || 0);
  var dd = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
  return (dd ? dd + ' d ' : '') + (dd || h ? h + ' h ' : '') + m + ' min';
}
/* One database server: its dot, its name, whose it is, and what its agent says of it. */
function dbaTile(s, d) {
  var f = s.facts || {}, a = s.agent || {};
  var st = dbaState(s);
  var t = el('div', 'dbs-tile ' + st[0] + (s.me ? ' me' : ''));
  var top = el('div', 'dbs-tile-top');
  top.appendChild(dbaDot(st[0]));
  top.appendChild(noI18n(el('b', 'dbs-tile-n', dbaLabel(s, d.servers))));
  var tag = el('span', 'tag ' + (s.me ? 'info' : 'dim'));
  if (s.me) tag.appendChild(el('span', '', 'this node’s'));
  else { tag.appendChild(el('span', '', 'node')); tag.appendChild(noI18n(el('span', '', ' ' + s.node))); }
  top.appendChild(tag);
  var eng = el('span', 'dbs-eng');
  eng.appendChild(noI18n(el('span', '', dbaEngine(s.engine || f.engine) + (f.version ? ' ' + String(f.version).split(/[ -]/)[0] : ''))));
  top.appendChild(eng);
  t.appendChild(top);
  var kv = el('div', 'dbs-kvs');
  dbaKv(kv, 'Address', noI18n(el('span', 'mono', (s.db_host || s.host || '?') + ((s.agent || {}).pg_port ? ':' + s.agent.pg_port : ''))));
  dbaKv(kv, 'Agent', noI18n(el('span', 'mono', (s.host || '?') + ':' + (s.port || '?') + (a.version ? ' · ' + a.version : ''))));
  var run = el('span', st[0] === 'ok' ? 'good' : (f.running === false ? 'bad' : 'muted'));
  run.appendChild(el('span', '', f.running === false ? 'not running' : (f.running ? 'running' : '–')));
  if (f.started && f.running) run.appendChild(noI18n(el('span', '', ' · ' + dbaUp(Date.now() / 1000 - f.started))));
  dbaKv(kv, 'The database', run);
  dbaKv(kv, 'TLS', el('span', f.ssl ? 'good' : 'muted', f.ssl === undefined ? '–' : (f.ssl ? 'on' : 'off')));
  dbaKv(kv, 'Connections', f.connections === undefined ? '–' : num(f.connections));
  if (f.disk && f.disk.total) {
    var used = f.disk.total - (f.disk.free || 0), pct = 100 * used / f.disk.total;
    var dk = el('span', 'dbs-diskv');
    dk.appendChild(dbaBar(pct));
    dk.appendChild(noI18n(el('span', 'small', bytes(used) + ' / ' + bytes(f.disk.total))));
    dbaKv(kv, 'Its data’s disk', dk, 'wide');
  }
  if (f.ram) {
    var rm = el('span', 'dbs-diskv');
    rm.appendChild(dbaBar(100 * (f.ram - (f.avail || 0)) / f.ram));
    rm.appendChild(noI18n(el('span', 'small', bytes(f.ram - (f.avail || 0)) + ' / ' + bytes(f.ram))));
    dbaKv(kv, 'RAM', rm, 'wide');
  }
  dbaKv(kv, 'Processors', (f.cpus ? num(f.cpus) : '–') + (f.load ? ' · ' + f.load.map(function (x) { var t = Number(x).toFixed(2); return numDecimal() === ',' ? t.replace('.', ',') : t; }).join(' / ') : ''));
  dbaKv(kv, 'Up for', f.uptime ? dbaUp(f.uptime) : '–');
  var ce = el('span', '');
  var dl = dbaDays(s.agent_cert_end || a.cert_end);
  ce.appendChild(noI18n(el('span', dl !== null && dl < 14 ? 'bad' : '', dbaDate(s.agent_cert_end || a.cert_end))));
  dbaKv(kv, 'Agent’s certificate ends', ce);
  var cc = dbaDays(s.client_cert_end);
  dbaKv(kv, 'Node’s client certificate ends', noI18n(el('span', cc !== null && cc < 14 ? 'bad' : '', dbaDate(s.client_cert_end))));
  var hd = el('span', st[0] === 'ok' ? '' : 'bad');
  hd.appendChild(el('span', '', s.at ? ago(s.at) : 'not yet'));
  dbaKv(kv, 'Last heard', hd);
  t.appendChild(kv);
  if (st[2]) t.appendChild(noI18n(el('div', 'dbs-tile-said small bad', st[2])));
  var gone = (a.clients || []).filter(function (x) { return x && x.stale; });
  if (gone.length) {
    /* Nodes the agent has not heard from for 30 days (1.0.289): not waited for when it puts its
       next certificate in use - one gone for good is taken away on the server. */
    var sg = el('div', 'dbs-tile-said small');
    sg.appendChild(el('span', 'tag dim', 'Not heard from'));
    sg.appendChild(document.createTextNode(' '));
    sg.appendChild(haWords('', gone.map(function (x) { return x.name; }).join(', '), ' - not heard from for 30 days, not waited for. One gone for good is taken away on the database server: ', 'otp_db_agent.py --forget NODE', ''));
    t.appendChild(sg);
  }
  if (a.busy && a.busy.op) {
    var bz = el('div', 'dbs-tile-said small');
    bz.appendChild(haWords('Busy with ', a.busy.op + (a.busy['do'] ? ' ' + a.busy['do'] : ''), ' for ', a.busy.node || '?', ''));
    t.appendChild(bz);
  }
  if (s.version_skew && s.version_skew.agent) {
    /* Its agent another program than the one otp ships (1.0.289: compared by its code, not
       by the release's number): older - upgraded on its server; newer - otp upgraded here. */
    var how = s.version_skew.how || 'older';
    var vs = el('div', 'dbs-tile-said small');
    vs.appendChild(el('span', 'tag warn', how === 'newer' ? 'Newer than otp' : (how === 'other' ? 'Not the one otp ships' : 'Another version than otp')));
    vs.appendChild(document.createTextNode(' '));
    if (how === 'newer') vs.appendChild(haWords('otp-db-agent ', s.version_skew.agent, ' is newer than this otp ', s.version_skew.otp, ' - upgrade otp on this node (or put the agent of this version back on the database server: ', './install.sh --db-agent', ')'));
    else if (how === 'other') vs.appendChild(haWords('The agent’s program is not the one otp ', s.version_skew.otp, ' ships (changed there, or from another build) - put it back: ', './install.sh --db-agent', ''));
    else vs.appendChild(haWords('otp-db-agent ', s.version_skew.agent, ', otp ', s.version_skew.otp, ' - upgrade the agent on the database server: ', './install.sh --db-agent', ''));
    t.appendChild(vs);
  }
  return t;
}
function dbaAct(btn, action) {
  busy(btn, true);
  api('db-agent', {action: action}, 300).then(function (r) {
    if (r.view) { DBA.d = r.view; DBA.at = Date.now(); }
    var said = r.message || ((r.done || []).length ? r.done.join(', ') : '');
    toast(action === 'look' ? 'looked at now' : (action === 'forget' ? 'forgotten: this node looks after a database on this machine only' : (said || 'done')), 'good');
    if (action === 'forget' || action === 'mariadb_tls') { loadDb(); return; }
    dbaCard(DBA.d);
  }).catch(oops).then(function () { busy(btn, false); });
}
function dbaMove(d) {
  var me = (d.servers || []).filter(function (s) { return s.me; })[0] || {};
  /* The database's port on the agent's server, MariaDB's too (1.0.289): not the usual one
     assumed - a server not looked at yet has no row, and 5432 / 3306 was another server. */
  var port = d.db_port || (d.engine === 'mariadb' ? '' : (me.agent || {}).pg_port);
  closeModal();
  dbWizard();
  if (typeof DBW === 'object' && DBW && DBW.step === 0 && $('modal') && !$('modal').hidden) {
    /* the move wizard of otp, filled in with the agent's server (1.0.289) */
    DBW.engine = d.engine || 'postgres';
    DBW.addr = {host: d.db_host || d.host || '', port: port ? Number(port) : (DBW.engine === 'mariadb' ? 3306 : 5432), name: 'otp', user: 'otp', password: '', timeout: 10};
    DBW.step = 1;
    dbwDraw();
  }
}

/* ---- the wizard: connect a database server --------------------------------------------- */
/* ODBA1. and base64url JSON {h, p, s, f, e}: read here only to say what it is - the secret
   is never shown, and the daemon checks it all again. */
function dbaCodeRead(text) {
  var t = String(text || '').replace(/\s+/g, '');
  if (!t) return {empty: true};
  if (t.indexOf('ODBA1.') !== 0) return {bad: 'a join code starts with ODBA1. - the one the database server printed'};
  try {
    var raw = t.slice(6).replace(/-/g, '+').replace(/_/g, '/');
    while (raw.length % 4) raw += '=';
    var o = JSON.parse(atob(raw));
    if (!o || !o.h || !o.s || !/^[0-9a-f]{64}$/.test(String(o.f || ''))) throw new Error('x');
    return {code: t, host: String(o.h), port: Number(o.p) || 9443, fp: String(o.f), engine: o.e === 'mariadb' ? 'mariadb' : 'postgres'};
  } catch (e) {
    return {bad: 'cut short or mistyped: copy all of it, from ODBA1. to the end'};
  }
}
function dbaCmd(text) {
  var box = el('div', 'dbs-cmd');
  box.appendChild(noI18n(el('pre', 'mono', text)));
  var cp = cmdButton('Copy', 'copy', 'small');
  cp.onclick = function () { copyText(text, cp); };
  box.appendChild(cp);
  return box;
}
function dbaWizard() {
  var W = {step: 0, engine: 'postgres', code: '', addr: '', mine: false, dbhost: '', done: null, err: '', running: false};
  dbaLoad().then(function (d) {
    var w = d.where || {};
    W.cur = d;
    W.mine = w.kind === 'unmanaged';
    W.dbhost = W.mine ? (w.host || '') : '';
    W.addrs = (d.addresses || []).slice();
    if (d.ha_mode && typeof HA === 'object' && HA && HA.nodes) {
      HA.nodes.forEach(function (n) { if (n.address && W.addrs.indexOf(n.address) < 0 && !n.me) W.addrs.push(n.address); });
    }
    paint();
  }).catch(oops);
  var STEPS = ['On the database server', 'The join code', 'Connecting'];
  function rail() {
    /* otp's steps of a wizard (as Move to another database draws them) */
    var r = el('div', 'wiz-steps');
    STEPS.forEach(function (t, i) {
      var s = el('div', 'wiz-step' + (i === W.step ? ' now' : (i < W.step ? ' done' : '')));
      s.appendChild(noI18n(el('span', 'wiz-n', String(i + 1))));
      s.appendChild(el('span', '', t));
      if (i < W.step && !W.running && !(W.step === 2 && !!W.done)) {
        s.classList.add('dbs-back');
        s.onclick = function () { W.step = i; paint(); };
      }
      r.appendChild(s);
    });
    return r;
  }
  function paint() {
    var buttons = [];
    if (W.step === 1) buttons.push({words: 'Back', icon: 'prev', left: true, go: function () { W.step = 0; paint(); }});
    if (W.step === 2 && W.err) buttons.push({words: 'Back', icon: 'prev', left: true, go: function () { W.step = 1; W.err = ''; paint(); }});
    buttons.push({words: 'Close', close: true});
    if (W.step === 0) buttons.push({words: 'I have the code', cls: 'primary', icon: 'next', go: function () { W.step = 1; paint(); }});
    if (W.step === 1) buttons.push({words: 'Connect it', cls: 'primary', icon: 'plug', noConfirm: true, go: function () { join(); }});
    if (W.step === 2 && W.done && (W.done.view || {}).where && W.done.view.where.kind !== 'agent') {
      buttons.push({words: 'Move the database onto it…', cls: 'primary', icon: 'db', go: function () { dbaMove(W.done.view); }});
    }
    modal('Connect a database server', function (body) {
      body.appendChild(rail());
      var host = el('div', 'dbs-wiz');
      host.id = 'dbs-wiz-' + W.step;
      body.appendChild(host);
      [one, two, three][W.step](host);
    }, buttons, 'large');
    explainWhatWasDrawn($('modal-body'));
  }
  function one(host) {
    var lead = el('div', 'dbs-lead');
    lead.appendChild(noI18n(el('span', 'dbs-lead-ico'))).innerHTML = iconMarkup('db', 22);
    var lw = el('div', '');
    lw.appendChild(el('b', '', 'otp-db-agent on the database server looks after it for otp'));
    lw.appendChild(el('p', 'note', 'Its certificate from otp’s own authority and its renewal, pg_hba.conf, its settings and restart, the replication, its firewall - the closed set of things the root helper does on this machine, and nothing else. Every request goes over HTTPS with certificates both ways and is signed; the agent does not run as root on the network side.'));
    lead.appendChild(lw);
    host.appendChild(lead);
    host.appendChild(el('h4', 'dbw-h', 'Which database'));
    var tiles = el('div', 'wiz-choices dbs-eng-tiles');
    [['postgres', 'PostgreSQL 16', 'Standalone, or one both nodes of a cluster share'], ['mariadb', 'MariaDB', 'Standalone only']].forEach(function (x) {
      var b = el('button', 'wiz-choice' + (W.engine === x[0] ? ' on' : ''));
      b.type = 'button';
      b.id = 'dbs-eng-' + x[0];
      b.appendChild(noI18n(el('div', 'wiz-choice-k', x[1])));
      b.appendChild(el('div', 'small muted', x[2]));
      b.onclick = function () { W.engine = x[0]; paint(); };
      tiles.appendChild(b);
    });
    host.appendChild(tiles);
    host.appendChild(el('h4', 'dbw-h', 'On the database server, as root'));
    var nodes = (W.addrs || []).slice(0, W.addrs.length > 1 && HA && HA.mode ? 2 : 1);
    var otp = nodes.map(function (a) { return '--otp-node ' + a; }).join(' ') || '--otp-node 192.0.2.11';
    var ol = el('ol', 'dbs-steps');
    var l1 = el('li', '');
    l1.appendChild(el('span', '', 'Copy otp’s installation folder there (the same version), then install the database and the agent:'));
    l1.appendChild(dbaCmd('./install.sh --db-server ' + W.engine + ' ' + otp));
    l1.appendChild(el('div', 'small muted', W.engine === 'postgres'
      ? 'PostgreSQL 16 installed, initialised, listening, wal_level = logical; the database and its account; the nodes let in (pg_hba.conf, firewalld); the agent. It prints a join code at the end.'
      : 'MariaDB installed and secured; the database and its account for the nodes; the agent. It prints a join code at the end.'));
    ol.appendChild(l1);
    var l2 = el('li', '');
    l2.appendChild(el('span', '', 'A database server installed already: the agent alone -'));
    l2.appendChild(dbaCmd('./install.sh --db-agent'));
    ol.appendChild(l2);
    var l3 = el('li', '');
    l3.appendChild(el('span', '', 'The code runs out in an hour; a new one any time:'));
    l3.appendChild(dbaCmd('/usr/local/lib/otp-db-agent/otp_db_agent.py --new-code'));
    ol.appendChild(l3);
    host.appendChild(ol);
    if ((W.addrs || []).length) {
      var said = el('div', 'note info small');
      said.appendChild(haWords('--otp-node is the address the database server sees this node by: ', W.addrs.join(', '), ''));
      host.appendChild(said);
    }
  }
  function two(host) {
    var ta = el('textarea', 'mono dbs-code');
    ta.id = 'dbs-code';
    ta.rows = 3;
    ta.spellcheck = false;
    ta.placeholder = 'ODBA1.eyJoIjo…';
    ta.value = W.code;
    host.appendChild(formField('The join code', ta, 'Printed by install.sh --db-server on the database server (or otp_db_agent.py --new-code). One hour, once.'));
    var said = el('div', 'dbs-code-said');
    said.id = 'dbs-code-said';
    host.appendChild(said);
    var g = el('div', 'formgrid');
    var addr = textBox(W.addr, '', 'mono');
    addr.id = 'dbs-addr';
    var af = formField('The agent’s address (optional)', addr, 'Only when this node reaches the agent by another address than the code says - a NAT, another network. HOST or HOST:PORT.');
    g.appendChild(af);
    var sw = switchBox(W.mine);
    sw.id = 'dbs-mine';
    var swl = el('label', 'dbs-sw');
    swl.appendChild(sw);
    swl.appendChild(el('span', '', 'Use it as this node’s database'));
    var mf = el('div', 'set-item');
    mf.appendChild(swl);
    mf.appendChild(saysBlock('This node’s database is on that server (or is moved there next): otp looks after the server it connects to. The address below is the one the database is reached at - the agent’s when left empty.'));
    g.appendChild(mf);
    var dbh = textBox(W.dbhost, '', 'mono');
    dbh.id = 'dbs-dbhost';
    var df = formField('The database’s address, as this node reaches it', dbh);
    g.appendChild(df);
    host.appendChild(g);
    function check() {
      W.code = ta.value; W.addr = addr.value.trim(); W.mine = !!sw._get(); W.dbhost = dbh.value.trim();
      df.style.visibility = W.mine ? '' : 'hidden';
      clear(said);
      var c = dbaCodeRead(W.code);
      if (c.empty) { said.appendChild(el('span', 'muted small', 'paste the code - it is checked as it is pasted')); return; }
      if (c.bad) { said.className = 'dbs-code-said bad'; said.appendChild(el('span', 'small', c.bad)); return; }
      said.className = 'dbs-code-said good';
      said.appendChild(noI18n(el('span', 'dbs-ok', '✓ ')));
      said.appendChild(haWords('otp-db-agent at ', c.host + ':' + c.port, ' · ' + dbaEngine(c.engine) + ' · its certificate ', c.fp.slice(0, 16) + '…', ''));
      addr.placeholder = c.host + ':' + c.port;
      dbh.placeholder = c.host;
      if (c.engine !== W.engine) W.engine = c.engine;
      /* One agent a node (1.0.289): another one takes the place of the one joined. */
      var cur = W.cur || {};
      var at = (W.addr || (c.host + ':' + c.port));
      if (cur.host && at.replace(/^\[|\]$/g, '') !== String(cur.host) + ':' + String(cur.port) && at !== String(cur.host)) {
        var rp = el('div', 'note ' + ((cur.where || {}).kind === 'agent' ? 'warn' : 'info') + ' small dbs-replace');
        rp.id = 'dbs-replace';
        if ((cur.where || {}).kind === 'agent' && cur.ha_mode) {
          rp.className = 'note bad small dbs-replace';
          rp.appendChild(haWords('This node is one of a cluster and its database is on the server of the agent at ', cur.host + ':' + cur.port, ': another agent is not connected instead. Take the cluster apart first.'));
        } else if ((cur.where || {}).kind === 'agent') {
          rp.appendChild(haWords('This node is connected to the agent at ', cur.host + ':' + cur.port, ' and its database is on that server. One agent a node: this one takes its place, and until the database is moved onto the new server (Move the database onto it…, next) nothing of the old server is looked after - its certificate is not renewed. The old agent is told this node leaves it.'));
        } else {
          rp.appendChild(haWords('This node is connected to the agent at ', cur.host + ':' + cur.port, ' already. One agent a node: this one takes its place.'));
        }
        said.appendChild(rp);
      }
    }
    ta.addEventListener('input', check);
    addr.addEventListener('input', check);
    dbh.addEventListener('input', check);
    sw._input.addEventListener('change', check);
    check();
    setTimeout(function () { try { ta.focus(); } catch (e) { } }, 0);
  }
  function three(host) {
    var steps = haLiveSteps([{key: 'reach', what: 'Reaching the agent, its certificate checked against the code'},
                             {key: 'certs', what: 'Certificates from otp’s own authority, both ways'},
                             {key: 'look', what: 'Looking at the server'}]);
    host.appendChild(steps);
    var res = el('div', 'dbs-result');
    host.appendChild(res);
    if (W.running) {
      steps.set('reach', 'run');
    } else if (W.err) {
      steps.set('reach', 'bad', W.err);
      steps.set('certs', 'skip', '');
      steps.set('look', 'skip', '');
      res.appendChild(el('div', 'note warn', 'Nothing was changed on this node. Put right what it says - a new code if this one ran out or was used - and connect again.'));
    } else if (W.done) {
      var f = W.done.facts || {}, a = W.done.agent || {};
      steps.set('reach', 'ok', (W.done.host || '') + ':' + (W.done.port || '') + (a.version ? ' · otp-db-agent ' + a.version : ''));
      steps.set('certs', 'ok', 'the agent has its certificate; this node its client certificate and signing key');
      steps.set('look', f.running === false ? 'warn' : 'ok', (f.engine === 'mariadb' ? 'MariaDB ' : 'PostgreSQL ') + String(f.version || '').split(/[ -]/)[0] + (f.running === false ? ' - not running' : ' - running'));
      var v = W.done.view || {};
      var me = (v.servers || []).filter(function (s) { return s.me; })[0];
      if (me) { var g = el('div', 'dbs-grid one'); g.appendChild(dbaTile(me, v)); res.appendChild(g); }
      res.appendChild(el('div', 'note good', (v.where || {}).kind === 'agent'
        ? 'Connected: this node’s database is on that server, and otp looks after it from now on.'
        : 'Connected. This node’s database is not on that server yet: move it there next - Move the database onto it…'));
      var rp = W.done.replaced;
      if (rp) {
        var rn = el('div', 'note warn dbs-replaced');
        rn.id = 'dbs-replaced';
        var old = String(rp.db_admin || '').replace(/^agent:/, '');
        if (rp.had_database) rn.appendChild(haWords('It takes the place of the agent at ', old, ' - this node’s database is still on ', rp.db_host, ', and nothing of that server is looked after until the database is moved onto the new one.'));
        else rn.appendChild(haWords('It takes the place of the agent at ', old, ' (one agent a node).'));
        /* Told this node leaves it (1.0.289) - one that did not answer keeps its certificate. */
        rn.appendChild(document.createTextNode(' '));
        if (rp.left) rn.appendChild(el('span', '', 'That agent took this node off its list.'));
        else rn.appendChild(haWords('That agent did not answer: it keeps this node’s certificate until ', 'otp_db_agent.py --forget ' + (v.node || ''), ' there.'));
        res.appendChild(rn);
      }
    }
  }
  function join() {
    var c = dbaCodeRead(W.code);
    if (!c.code) { toast(c.bad || 'paste the join code first', 'bad'); if ($('dbs-code')) $('dbs-code').focus(); return; }
    if (W.addr && !/^\[?[A-Za-z0-9.:-]+\]?(:\d{1,5})?$/.test(W.addr)) { toast('the agent’s address: HOST or HOST:PORT', 'bad'); return; }
    W.step = 2; W.running = true; W.err = ''; W.done = null;
    paint();
    api('db-agent', {action: 'join', code: c.code, address: W.addr, db_host: W.mine ? (W.dbhost || '') : ''}, 180).then(function (r) {
      W.done = r;
      if (r.view) { DBA.d = r.view; DBA.at = Date.now(); }
      toast('the database server is connected', 'good');
      if (typeof PANE !== 'undefined' && PANE === 'db') dbaPane();
    }, function (e) {
      W.err = String((e && e.message) || e);
    }).then(function () { W.running = false; if ($('dbs-wiz-2')) paint(); });
  }
}

/* ---- High availability: the two database servers beside the two nodes -------------------- */
function dbaHa(d) {
  var dbs = (d && d.dbservers) || [];
  if (dbs.length) { DBA.d = Object.assign({}, DBA.d || {}, {servers: dbs}); }
  dbaPillInto($('ha-rep-card') && $('ha-rep-card').querySelector(':scope > h2'), dbs, 'ha_replication');
  var host = $('ha-dbs');
  if (!dbs.length) { if (host) host.remove(); dbaHaMake(d); return; }
  if (!host) {
    host = el('div', 'dbs-ha');
    host.id = 'ha-dbs';
    var nodes = $('ha-nodes');
    if (nodes && nodes.parentNode) nodes.parentNode.insertBefore(host, nodes.nextSibling);
  }
  liveFill(host, function (box) {
    box.appendChild(el('h4', 'dbw-h', 'The database servers'));
    var r = d.replication || {};
    var lt = d.link_tls || {};
    var linkOf = {};
    (lt.nodes || []).forEach(function (n) { linkOf[n.name] = n; });
    var byNode = {};
    dbs.forEach(function (s) { byNode[s.node] = s; });
    var peerNode = ((d.nodes || []).filter(function (n) { return !n.me; })[0] || {}).name;
    box.appendChild(listTable(['Server', 'Of node', 'Address', 'Database', 'Replication', {words: 'Waiting to go over', cls: 'num'}, 'The link’s TLS', 'Its agent'], dbs, function (s) {
      var tr = el('tr');
      var st = dbaState(s), f = s.facts || {};
      var nm = el('td', 'dbs-ha-n');
      nm.appendChild(dbaDot(st[0]));
      nm.appendChild(noI18n(el('b', '', dbaLabel(s, dbs))));
      tr.appendChild(nm);
      tr.appendChild(noI18n(el('td', 'mono small', s.node)));
      tr.appendChild(noI18n(el('td', 'mono small', s.db_host || s.host || '')));
      tr.appendChild(noI18n(el('td', 'small', dbaEngine(s.engine || f.engine) + (f.version ? ' ' + String(f.version).split(/[ -]/)[0] : '') + (f.running === false ? ' ✗' : ''))));
      /* The direction this server sends in: this node's subscription takes from the other one,
         this node's slot keeps for it. */
      var other = s.me ? byNode[peerNode] : (dbs.filter(function (x) { return x.me; })[0]);
      var rep = el('td', 'small');
      var arrow = noI18n(el('span', 'dbs-dir', dbaLabel(s, dbs) + ' → ' + (other ? dbaLabel(other, dbs) : '?')));
      rep.appendChild(arrow);
      var ok = false, words = 'not set up', behind;
      if (s.me) {
        var out = (r.outgoing || [])[0];
        if (out) { ok = out.active && out.wal_status !== 'lost'; words = out.wal_status === 'lost' ? 'lost' : (out.active ? 'taken' : 'waiting'); behind = out.behind; }
      } else {
        var inn = (r.incoming || [])[0];
        if (inn) { ok = inn.enabled && inn.running; words = !inn.enabled ? 'paused' : (inn.running ? 'running' : 'not running'); }
      }
      rep.appendChild(document.createTextNode(' '));
      rep.appendChild(el('span', 'tag ' + (ok ? 'ok' : (words === 'paused' || words === 'waiting' ? 'warn' : 'crit')), words));
      tr.appendChild(rep);
      tr.appendChild(el('td', 'num', behind !== undefined && behind !== null ? bytes(behind) : '–'));
      var ln = linkOf[s.node] || {};
      var lk = el('td', 'small');
      var mode = lt.mode || d.db_tls || '';
      var lok = ln.step === 'done' || ['verify-full', 'verify-ca'].indexOf(mode) >= 0;
      lk.appendChild(el('span', 'tag ' + (ln.step === 'failed' ? 'crit' : (lok ? 'ok' : 'warn')),
        ln.step === 'failed' ? 'failed' : (lok ? (mode || 'verify-full') : (mode ? mode : 'not encrypted'))));
      if (ln.cert_end) lk.appendChild(noI18n(el('span', 'muted', ' ' + dbaDate(ln.cert_end))));
      tr.appendChild(lk);
      var ag = el('td', 'small ' + (st[0] === 'ok' ? 'muted' : 'bad'));
      ag.appendChild(el('span', '', st[1]));
      if (s.at) { ag.appendChild(document.createTextNode(' · ')); ag.appendChild(el('span', '', ago(s.at))); }
      if (st[2]) explain(ag, st[2]);
      tr.appendChild(ag);
      return tr;
    }));
  });
  dbaHaMake(d);
}
/* Making it two with each node's database on a server of its own (layout B) comes with a later
   release: nothing drawn for it yet. */
function dbaHaMake(d) {
  var box = $('ha-dbs-make');
  if (box) box.remove();
}

/* ---- Firewall: the database servers' port, opened by their agents ----------------------- */
function dbaFw() {
  if (!$('fw-nodes')) return;
  /* No agent and no database server known (1.0.289): that answer kept for 10 min - the pane is
     drawn again every 5 s, and asked /api/db-agent each time (1.0.105 asked nothing). Joining
     one is done on the database's pane, which asks afresh. */
  var none = DBA.d && !dbaOn(DBA.d) && Date.now() - DBA.at < 600000;
  (none ? Promise.resolve(DBA.d) : dbaLoad()).then(function (d) {
    var dbs = dbaOn(d) ? d.servers || [] : [];
    var h = $('fw-lede') && $('fw-lede').parentNode && $('fw-lede').parentNode.querySelector('h2');
    dbaPillInto(h, dbs, 'db_firewall');
    var host = $('fw-dbs');
    if (!dbs.length) { if (host) host.remove(); return; }
    if (!host) {
      host = el('div', 'fw-nodes fw-dbs');
      host.id = 'fw-dbs';
      $('fw-nodes').parentNode.insertBefore(host, $('fw-nodes').nextSibling);
    }
    liveFill(host, function (box) {
      dbs.forEach(function (s) {
        var st = dbaState(s);
        var b = el('div', 'fw-node db');
        var top = el('div', 'fw-node-top');
        top.appendChild(noI18n(el('b', '', dbaLabel(s, dbs))));
        top.appendChild(el('span', 'tag dim', 'database server'));
        b.appendChild(top);
        var sl = el('div', 'fw-node-s');
        sl.appendChild(dbaDot(st[0]));
        sl.appendChild(el('span', '', st[0] === 'ok' ? 'its port opened by its agent to the nodes' : st[1]));
        b.appendChild(sl);
        b.appendChild(noI18n(el('div', 'fw-node-a', (s.db_host || s.host || '') + ((s.agent || {}).pg_port ? ' · TCP ' + s.agent.pg_port : ''))));
        explain(b, 'The database server’s own firewall (firewalld) is its administrator’s; otp lets the nodes and the other database server reach the database’s port there through its agent - when the cluster is made, and when an address changes.' + (st[2] ? ' ' + st[2] : ''));
        box.appendChild(b);
      });
    });
  }).catch(function () { });
}

/* ---- what the section needs and otp's pages did not have (1.0.289) ------------------------ */
/* Words and data in turn: the words translated, the data (an address, a name) never. */
function haWords() {
  var span = el('span', '');
  for (var i = 0; i < arguments.length; i++) {
    var t = arguments[i];
    if (t === undefined || t === null || t === '') continue;
    span.appendChild(i % 2 ? noI18n(el('span', 'mono', String(t))) : el('span', '', String(t)));
  }
  return span;
}
/* A list of steps whose state is set as they go: set(key, 'run'|'ok'|'warn'|'bad'|'skip', said). */
function haLiveSteps(list) {
  var box = el('div', 'pt-steps dbs-live');
  var rows = {};
  (list || []).forEach(function (st) {
    var row = el('div', 'si-row');
    var dot = el('span', 'dot off');
    row.appendChild(dot);
    row.appendChild(el('span', '', st.what));
    var said = noI18n(el('span', 'small muted dbs-live-said', ''));
    row.appendChild(said);
    rows[st.key] = {row: row, dot: dot, said: said};
    box.appendChild(row);
  });
  box.set = function (key, state, words) {
    var r = rows[key];
    if (!r) return;
    r.dot.className = 'dot ' + ({run: 'warn', ok: 'ok', warn: 'warn', bad: 'crit', skip: 'off'}[state] || 'off');
    r.row.classList.toggle('run', state === 'run');
    r.said.textContent = words ? ' - ' + words : '';
    r.said.className = 'small dbs-live-said ' + (state === 'bad' ? 'bad' : 'muted');
  };
  return box;
}
function haIp(t) { return /^(\d{1,3}\.){3}\d{1,3}$/.test(t) || /^[0-9A-Fa-f:]+:[0-9A-Fa-f:]*$/.test(t); }
/* This machine's database as a database server (db_local_card) comes with a later release: off. */
function dbaLocalOn(d) { return false; }
function dbaLocalDraw(host, d) { dbaDraw(host, d); }
