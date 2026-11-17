// ui_fix.js - 1.0.295 hunt, the pages in a real Chromium on the installed otp (standalone):
//  - Settings -> The database on a node with no agent of its own while the other node's server is
//    looked after by one: the card of a server no agent looks after, the other's tile beside it -
//    no Move, Restart, Renew or Forget of an agent it does not have; with its own agent as before;
//  - the HA pane's database servers without replication: "no replication", not a red "not set up";
//    replicated: as before.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(3000);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  await p.reload(); await p.waitForTimeout(3000);
  const now = Date.now() / 1000;
  const srv = (node, me) => ({ kind: 'db', name: 'db:' + node, node, me, alive: true, ok: true, at: now - 10, host: '192.0.2.30', port: 9443,
    db_host: 'db1.corp', engine: 'postgres', facts: { version: '16.4', running: true, ssl: true, connections: 5 }, agent: { version: '1.0' } });

  const card = await p.evaluate((a) => {
    const out = {};
    for (const [k, d] of Object.entries(a)) {
      const host = el('div'); document.body.appendChild(host);
      try { dbaDraw(host, d); } catch (e) { out[k] = { err: String(e) }; continue; }
      out[k] = { text: host.innerText, move: !!host.querySelector('#dba-move'), restart: !!host.querySelector('#dba-restart'),
        forget: !!host.querySelector('#dba-forget'), renew: !!host.querySelector('#dba-renew'), tiles: host.querySelectorAll('.dbs-tile').length,
        connect: !!host.querySelector('#dba-connect') };
      host.remove();
    }
    return out;
  }, {
    other: { db_admin: 'local', servers: [srv('nodea', false)], where: { kind: 'unmanaged', engine: 'postgres', host: 'db1.corp', port: 5432 } },
    own: { db_admin: 'agent:192.0.2.30:9443', host: '192.0.2.30', port: 9443, engine: 'postgres', servers: [srv('me1', true)], where: { kind: 'agent', engine: 'postgres', host: 'db1.corp' } },
  });
  const o = card.other || {};
  ok('no agent of its own: no Move, Restart, Renew or Forget', o.text && !o.move && !o.restart && !o.renew && !o.forget, o);
  ok('...the card of a server no agent looks after, with Connect', /a server no agent looks after/.test(o.text || '') && o.connect, o);
  ok('...the other node\'s server as a tile beside it', o.tiles === 1, o);
  const w = card.own || {};
  ok('its own agent: as before - the agent\'s card, Restart and Forget', w.restart && w.forget && w.tiles === 1 && !/no agent looks after/.test(w.text || ''), w);

  const ha = await p.evaluate((a) => {
    const out = {};
    for (const [k, d] of Object.entries(a)) {
      const nodes = el('div'); nodes.id = 'ha-nodes'; document.body.appendChild(nodes);
      try { dbaHa(d); } catch (e) { out[k] = { err: String(e) }; nodes.remove(); continue; }
      const host = document.getElementById('ha-dbs');
      out[k] = host ? { text: host.innerText, crit: host.querySelectorAll('.tag.crit').length, arrow: !!host.querySelector('.dbs-dir') } : { none: true };
      if (host) host.remove(); nodes.remove();
    }
    return out;
  }, {
    alone: { mode: '', nodes: [{ name: 'me1', me: true }], dbservers: [srv('me1', true)], replication: {} },
    shared: { mode: 'shared', nodes: [{ name: 'me1', me: true }, { name: 'nodeb' }], dbservers: [srv('me1', true), srv('nodeb', false)], replication: {} },
    repl: { mode: 'replicated', nodes: [{ name: 'me1', me: true }, { name: 'nodeb' }], dbservers: [srv('me1', true), srv('nodeb', false)],
      replication: { outgoing: [{ active: true, wal_status: 'reserved', behind: 0 }], incoming: [{ enabled: true, running: true }] } },
  });
  ok('standalone with an agent: "no replication", no red "not set up"', /no replication/.test((ha.alone || {}).text || '') && ha.alone.crit === 0 && !ha.alone.arrow, ha.alone);
  ok('two nodes on one server: no red "not set up"', (ha.shared || {}).crit === 0 && /no replication/.test(ha.shared.text || ''), ha.shared);
  ok('replicated: as before - the direction and its state', (ha.repl || {}).arrow && /running/.test(ha.repl.text) && /taken/.test(ha.repl.text) && ha.repl.crit === 0, ha.repl);
  ok('no errors on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL crashed ' + e); console.log('ALL 0 / 1'); process.exit(1); });
