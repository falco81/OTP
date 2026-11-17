// ui_meter.js - 1.0.293: the database servers in the header's meter, in a real Chromium on the
// installed otp (standalone, SQLite, no agent - its /api/load has no dbservers):
//  - as before: no dbservers, the meter's chips as they were (no groups);
//  - ?api=load answered in the page with a row of this node's database server (as with an agent):
//    a group after this node's, named with a cylinder, its graphs moving; its panel: the database
//    (version, running, connections, size, its disk, TLS) and the machine;
//  - its agent down: the group dimmed, the name red, the panel says so;
//  - two servers of the same short name: db·NODE; Czech; 1200 px wide.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/dbashots';
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1900, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  let mode = 'none', asked = [];
  await p.route(/[?&]api=load\b/, async (route) => {
    asked.push(route.request().url());
    const r = await route.fetch();
    let d;
    try { d = await r.json(); } catch (e) { await route.fulfill({ response: r }); return; }
    if (mode !== 'none') {
      const now = Date.now() / 1000;
      const row = { kind: 'db', name: 'db:' + d.node, node: d.node, host: '192.0.2.21', server: 'db1', engine: 'postgres', age: 0, at: now,
        cpu: 20 + 15 * Math.sin(now / 3), cores: 4, mem_total: 16e9, mem_used: 6e9, load: [0.43, 0.36, 0.2],
        disk_rd: 2e6, disk_wr: 5e5, net_rx: 3e5, net_tx: 2e5, over_s: 2,
        db: { engine: 'postgres', running: true, version: '16.4 (Debian)', started: now - 3 * 86400, connections: 12, repl_behind: 0,
              size: 52e6, disk: { total: 50e9, free: 30e9 }, ssl: true } };
      if (mode === 'down') d.dbservers = [{ kind: 'db', name: 'db:' + d.node, node: d.node, host: '192.0.2.21', server: '', age: 0, at: now,
        down: true, said: 'the database agent at 192.0.2.21:9443 does not answer: timed out' }];
      else if (mode === 'two') d.dbservers = [row, Object.assign({}, row, { name: 'db:nodeb', node: 'nodeb', age: 4, host: '192.0.2.22', server: 'db1.corp' })];
      else d.dbservers = [row];
    }
    await route.fulfill({ response: r, json: d });
  });
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate(async () => {
    await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({settings: {perf_meter: true}})});
    await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en', hload: 'graphs', hpanel: 'tiles'})});
  });
  await p.reload(); await p.waitForTimeout(6000);

  // ---- as before ----
  const real = await p.evaluate(() => api('load'));
  ok('the real /api/load (no agent): no dbservers', real && real.now && !('dbservers' in real), Object.keys(real || {}));
  const s0 = await p.evaluate(() => ({ groups: document.querySelectorAll('#hload .hl-node').length, chips: document.querySelectorAll('#hload > [data-k]').length,
    cls: document.getElementById('hload').className }));
  ok('no dbservers: the meter as before - its chips, no groups', s0.groups === 0 && s0.chips === 4 && !/hl-cluster/.test(s0.cls), s0);

  // ---- this node's database server ----
  mode = 'one';
  await p.waitForTimeout(24000);   /* drawn 14 s after it was read, as every row of a cluster */
  const s1 = await p.evaluate(() => {
    const g = [...document.querySelectorAll('#hload .hl-node')];
    const db = document.querySelector('#hload .hl-node.hl-db');
    const path = db ? (db.querySelector('svg.hl-live .hl-line') || {}).getAttribute('d') : '';
    const sv = db && db.querySelector('svg.hl-live'); const run = sv && sv.querySelector('.hl-run');
    const vis = (() => { if (!sv) return 0; const r = sv.getBoundingClientRect(); const pts = (path || '').match(/[\d.]+,[\d.]+/g) || []; const m = new DOMMatrix(getComputedStyle(run).transform); return pts.filter(q => { const x = +q.split(',')[0] + m.m41; return x >= 0 && x <= +sv.getAttribute('data-w'); }).length; })();
    return { names: g.map(x => x.querySelector('.hl-name').textContent), here: g[0] && g[0].classList.contains('hl-here'),
      icon: !!(db && db.querySelector('.hl-name .hl-dbic svg')), title: db ? (n => n.title || n.getAttribute('aria-label') || (n._explainHtml || ''))(db.querySelector('.hl-name')) : '',
      chips: db ? [...db.querySelectorAll('[data-k]')].map(x => x.dataset.node + '/' + x.dataset.k) : [], path: path || '', vis: vis,
      color: db ? getComputedStyle(db.querySelector('.hl-name')).color : '', late: !!document.querySelector('#hload .hl-db.hl-late') };
  });
  ok('a row for the database server after this node\'s, named with a cylinder', s1.names.length === 2 && s1.here && s1.names[1] === 'db1' && s1.icon, s1);
  ok('...its title: whose and where', /The database server of .+: 192\.0\.2\.21/.test(s1.title), s1.title);
  ok('...its four parts, under its own key', s1.chips.length === 4 && s1.chips.every(x => /^db:.+\/(cpu|mem|disk|net)$/.test(x)), s1.chips);
  ok('...its graphs drawn from the readings as they come (inside the graph)', /^M[\d.]+,[\d.]+L/.test(s1.path) && s1.vis >= 2, [s1.vis, s1.path.slice(0, 80)]);
  ok('...in violet, not late', /rgb\(163, 113, 247\)|rgb\(1[3-9]\d, \d+, 2[0-5]\d\)/.test(s1.color) && !s1.late, s1.color);
  const sinceDb = asked.slice(-3).some(u => /since=[^&]*db%3A/.test(u) || /since=[^&]*db:/.test(u));
  ok('...the page does not ask readings of it by since (they come whole)', !sinceDb, asked.slice(-1));
  await p.hover('#hload .hl-db [data-k="cpu"]'); await p.waitForTimeout(2500);
  const pan = await p.evaluate(() => { const x = document.getElementById('hload-panel'); return x && !x.hidden ? x.textContent : ''; });
  ok('its panel: whose, the graph, the database - version, running, connections, size, its disk, TLS',
     /db1/.test(pan) && /the database server of/.test(pan) && /The database/.test(pan) && /PostgreSQL 16\.4/.test(pan) && /running · 3 d/.test(pan) &&
     /Connections\s*12/.test(pan) && /The size of otp’s database/.test(pan) && /Its data’s disk/.test(pan) && /TLS\s*on/.test(pan), pan.slice(0, 600));
  ok('...and the machine: CPU with cores and load, RAM, Disk, Net', /The machine/.test(pan) && /4 ×/.test(pan) && /0\.43 \/ 0\.36 \/ 0\.20/.test(pan) &&
     /RAM/.test(pan) && /Disk/.test(pan) && /Net/.test(pan), pan.slice(0, 600));
  const askedDetail = asked.slice(-2).some(u => /detail_node=db/.test(u));
  ok('...nothing asked of another node for it (no detail_node)', !askedDetail, asked.slice(-2));
  await p.locator('#hload').screenshot({ path: SHOTS + '/50-meter-db.png' }).catch(() => {});
  await p.locator('#hload-panel').screenshot({ path: SHOTS + '/51-meter-db-panel.png' }).catch(() => {});
  await p.mouse.move(5, 600); await p.waitForTimeout(800);

  // ---- its agent down ----
  mode = 'down';
  await p.waitForTimeout(5000);
  const s2 = await p.evaluate(() => { const db = document.querySelector('#hload .hl-node.hl-db'); return db ? { late: db.classList.contains('hl-late'),
    color: getComputedStyle(db.querySelector('.hl-name')).color, name: db.querySelector('.hl-name').textContent, title: (n => n.title || n.getAttribute('aria-label') || (n._explainHtml || ''))(db.querySelector('.hl-name')) } : null; });
  ok('its agent down: the row dimmed, its name red, db·NODE (no server name)', s2 && s2.late && /rgb\(2[0-5]\d, \d{1,2}, \d{1,2}\)|rgb\(2[0-5]\d, [0-9]{2,3}, [0-9]{2,3}\)/.test(s2.color) &&
     /^db·/.test(s2.name) && /its agent does not answer/.test(s2.title), s2);
  await p.hover('#hload .hl-db [data-k="mem"]'); await p.waitForTimeout(2500);
  const pan2 = await p.evaluate(() => { const x = document.getElementById('hload-panel'); return x && !x.hidden ? x.textContent : ''; });
  ok('...its panel: the agent does not answer, why', /Its agent does not answer - nothing read from it now\./.test(pan2) && /timed out/.test(pan2), pan2.slice(0, 300));
  await p.mouse.move(5, 600); await p.waitForTimeout(800);

  // ---- two of the same short name ----
  mode = 'two';
  await p.waitForTimeout(5000);
  const names = await p.$$eval('#hload .hl-node .hl-name', a => a.map(x => x.textContent));
  ok('two servers of the same short name: db·NODE each', names.length === 3 && /^db·/.test(names[1]) && names[2] === 'db·nodeb', names);

  // ---- 1200 px: it fits ----
  mode = 'one';
  await p.setViewportSize({ width: 1200, height: 900 }); await p.waitForTimeout(5000);
  const fit = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, r: document.getElementById('hload').getBoundingClientRect().right }));
  ok('1200 px: nothing wider than the window', fit.sw <= 1200 && fit.r <= 1200, fit);
  await p.setViewportSize({ width: 1900, height: 900 });

  // ---- Czech ----
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}); });
  await p.reload(); await p.waitForTimeout(9000);
  await p.hover('#hload .hl-db [data-k="cpu"]'); await p.waitForTimeout(2500);
  const pcs = await p.evaluate(() => { const x = document.getElementById('hload-panel'); return x && !x.hidden ? x.textContent : ''; });
  const tcs = await p.evaluate(() => (n => n ? (n.title || n.getAttribute('aria-label') || (n._explainHtml || '')) : '')(document.querySelector('#hload .hl-db .hl-name')));
  ok('Czech: the panel', /databázový server uzlu/.test(pcs) && /Databáze/.test(pcs) && /Stroj/.test(pcs) && /Spojení/.test(pcs) && /Velikost databáze otp/.test(pcs) &&
     /běží/.test(pcs) && /0,43 \/ 0,36 \/ 0,20/.test(pcs), pcs.slice(0, 500));
  ok('...nothing of it in English', !/the database server of|The machine|Connections|The size of/.test(pcs), pcs.slice(0, 500));
  ok('...the row\'s title', /Databázový server uzlu .+: 192\.0\.2\.21/.test(tcs), tcs);
  await p.locator('#hload-panel').screenshot({ path: SHOTS + '/52-meter-db-panel-cs.png' }).catch(() => {});
  await p.evaluate(async () => {
    await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})});
    await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({settings: {perf_meter: false}})});
  });
  ok('no error on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL the test ran through (' + e + ')'); console.log('ALL ' + R.filter(x => x).length + ' / ' + (R.length + 1)); process.exit(1); });
