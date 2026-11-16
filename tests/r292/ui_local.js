// ui_local.js - 1.0.292 in a real Chromium, on the installed otp (standalone, SQLite, no agent):
//  - the setting db_local_card in Settings -> The database, asleep for SQLite; the pane as before
//    (no tile of this machine's database);
//  - GET /api/db-agent answered in the page with `local` rows (a pair: this node's PostgreSQL and the
//    other node's, not heard from lately, its certificate ending): the card Database server drawn
//    with a tile each - hero, state, facts, Look now (POST look), Renew the certificate, Restart;
//  - one node alone: "This node's database is on this machine", only Look now;
//  - Czech; a phone (420 px).
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const BASE = 'https://127.0.0.1/admin/';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/dbashots';
fs.mkdirSync(SHOTS, { recursive: true });
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 500) + ')')); };

(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto(BASE); await pg.waitForTimeout(700);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2000);
  await pg.evaluate(() => api('prefs', {lang: 'en'}));
  await pg.goto(BASE + '#settings/db'); await pg.reload(); await pg.waitForTimeout(3500);

  // ---- as before ----
  const real = await pg.evaluate(() => api('db-agent'));
  ok('the real GET /api/db-agent: no `local` (off)', !('local' in real), Object.keys(real));
  const set0 = await pg.evaluate(() => {
    const it = document.querySelector('.set-item[data-key="db_local_card"]');
    return { there: !!it, asleep: !!(it && it.classList.contains('asleep')),
             words: it ? it.textContent : '', tiles: document.querySelectorAll('.dbs-tile').length };
  });
  ok('the setting in The database: its words, asleep for SQLite', set0.there && set0.asleep &&
     /Show this machine’s database as a database server/.test(set0.words), set0);
  ok('...no tile of this machine\'s database (as before)', set0.tiles === 0, set0);

  // ---- a pair, each node its own PostgreSQL ----
  const now = Date.now() / 1000;
  const n1 = { kind: 'db', name: 'db:n1', node: 'n1', me: true, ok: true, stale: false, at: now - 2, host: '127.0.0.1', port: 5432,
    engine: 'postgres', cert_end: now + 60 * 86400, cert_by: 'dbtls', restart: { may: true, unit: 'postgresql@16-main', waiting: ['shared_buffers'] },
    facts: { host: 'otp1', engine: 'postgres', running: true, version: '16.4 (Debian 16.4-1)', ssl: true, started: now - 3 * 86400, connections: 7,
      cpus: 4, ram: 8 * 2 ** 30, avail: 5 * 2 ** 30, load: [0.43, 0.36, 0.2], uptime: 9 * 86400, disk: { total: 50 * 2 ** 30, free: 30 * 2 ** 30 } } };
  const n2 = { kind: 'db', name: 'db:n2', node: 'n2', me: false, ok: true, stale: true, at: now - 900, host: 'localhost', port: 5432,
    engine: 'postgres', cert_end: now + 6 * 86400, cert_by: 'dbtls',
    facts: { host: 'otp2', engine: 'postgres', running: true, version: '16.4', ssl: true, started: now - 86400, connections: 3, cpus: 2,
      ram: 4 * 2 ** 30, avail: 1 * 2 ** 30, load: [1.5, 1.2, 1.0], uptime: 2 * 86400, disk: { total: 20 * 2 ** 30, free: 2 * 2 ** 30 } } };
  let local = [n1, n2]; let looked = 0;
  await pg.route(/\?api=db-agent(&|$)/, async (r) => {
    const got = await r.fetch();
    const d = JSON.parse(await got.text());
    if (r.request().method() === 'POST') {
      const body = JSON.parse(r.request().postData() || '{}');
      if (body.action === 'look') looked++;
      d.view = Object.assign(d.view || {}, { local: local });
      return r.fulfill({ contentType: 'application/json', body: JSON.stringify(Object.assign(d, { row: local[0] })) });
    }
    return r.fulfill({ contentType: 'application/json', body: JSON.stringify(Object.assign(d, { local: local })) });
  });
  await pg.evaluate(() => dbaPane()); await pg.waitForTimeout(1500);
  const c1 = await pg.evaluate(() => {
    const card = document.getElementById('db-agent-card');
    const tiles = [...document.querySelectorAll('#db-agent .dbs-tile')];
    const tls = document.getElementById('db-tls-card');
    return { card: !!card, text: card ? card.textContent : '', tiles: tiles.map(t => t.className),
      above: !!(card && tls && (card.compareDocumentPosition(tls) & Node.DOCUMENT_POSITION_FOLLOWING)),
      t2: tiles[1] ? tiles[1].textContent : '', t2bad: tiles[1] ? [...tiles[1].querySelectorAll('.bad')].map(x => x.textContent) : [],
      look: !!document.getElementById('dba-look'), renew: !!document.getElementById('dba-renew'), restart: !!document.getElementById('dba-restart'),
      forget: /Forget the agent/.test(card ? card.textContent : ''), join: /Connect a database server/.test(card ? card.textContent : '') };
  });
  ok('on, a pair: the card Database server above Encryption to the database server', c1.card && c1.above, c1);
  ok('...the hero: each node\'s database on its own machine, no agent', /Each node’s database is on its own machine/.test(c1.text) &&
     /looked at by each node itself - no agent/.test(c1.text) && /PostgreSQL 16\.4/.test(c1.text) && /127\.0\.0\.1:5432/.test(c1.text), c1.text.slice(0, 400));
  ok('...a tile each: this node\'s first (ok, me), the other not heard from lately (warn)', c1.tiles.length === 2 &&
     /\bok\b/.test(c1.tiles[0]) && /\bme\b/.test(c1.tiles[0]) && /\bwarn\b/.test(c1.tiles[1]), c1.tiles);
  ok('...the other\'s tile: its node, not heard from lately, its certificate ending in red', /node n2/.test(c1.t2) &&
     /not heard from lately/.test(c1.t2) && c1.t2bad.length >= 2, [c1.t2, c1.t2bad]);
  ok('...the facts: address, the database running, TLS, connections, disk, RAM, processors with the load',
     ['Address', 'The database', 'running', 'TLS', 'Its certificate ends', 'Connections', 'Its data’s disk', 'RAM', 'Processors', '0.43 / 0.36 / 0.20', 'Up for', 'Last heard']
       .every(w => c1.text.indexOf(w) >= 0), c1.text.slice(0, 900));
  ok('...actions: Look now, Renew the certificate, Restart the database (a restart waits)', c1.look && c1.renew && c1.restart, c1);
  ok('...none of the agent\'s: no Forget, no Connect a database server', !c1.forget && !c1.join, c1);
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/40-local-pair.png' }).catch(() => {});
  await pg.click('#dba-look'); await pg.waitForTimeout(1500);
  ok('Look now: asked (POST look), the card drawn again', looked === 1 && await pg.evaluate(() => document.querySelectorAll('#db-agent .dbs-tile').length === 2), looked);
  await pg.click('#dba-restart'); await pg.waitForTimeout(700);
  ok('Restart the database…: asked first (its unit)', await pg.evaluate(() => /Restart postgresql/.test(document.getElementById('modal').textContent)));
  await pg.evaluate(() => closeModal()); await pg.waitForTimeout(300);

  // ---- one node alone ----
  local = [Object.assign({}, n1, { cert_end: null, cert_by: '', restart: undefined })];
  await pg.evaluate(() => dbaPane()); await pg.waitForTimeout(1200);
  const c2 = await pg.evaluate(() => ({ text: document.getElementById('db-agent-card').textContent, tiles: document.querySelectorAll('#db-agent .dbs-tile').length,
    renew: !!document.getElementById('dba-renew'), restart: !!document.getElementById('dba-restart'), look: !!document.getElementById('dba-look') }));
  ok('one node: "This node’s database is on this machine", one tile, no certificate row', /This node’s database is on this machine/.test(c2.text) &&
     c2.tiles === 1 && !/Its certificate ends/.test(c2.text), c2);
  ok('...only Look now', c2.look && !c2.renew && !c2.restart, c2);
  local = [Object.assign({}, n1, { facts: { running: false, said: 'connection refused', engine: 'postgres' } })];
  await pg.evaluate(() => dbaPane()); await pg.waitForTimeout(1200);
  const c3 = await pg.evaluate(() => document.getElementById('db-agent-card').textContent);
  ok('its database not running: said, and why', /its database does not run/.test(c3) && /connection refused/.test(c3), c3.slice(0, 400));

  // ---- off: as before ----
  local = [];
  await pg.evaluate(() => dbaPane()); await pg.waitForTimeout(1200);
  ok('no rows: no card (as before)', await pg.evaluate(() => !document.getElementById('db-agent-card')));

  // ---- Czech, a phone ----
  local = [n1, n2];
  await pg.evaluate(() => api('prefs', {lang: 'cs'})); await pg.reload(); await pg.waitForTimeout(4000);
  const cs = await pg.evaluate(() => (document.getElementById('db-agent-card') || {}).textContent || '');
  ok('Czech: the card', /Databáze každého uzlu je na jeho vlastním stroji/.test(cs) && /sleduje ji každý uzel sám – bez agenta/.test(cs) &&
     /poslední dobou se neozval/.test(cs) && /0,43 \/ 0,36 \/ 0,20/.test(cs), cs.slice(0, 600));
  ok('...nothing of it left in English', !/Each node’s database|looked at by each node|not heard from lately|Look now|Last heard/.test(cs), cs.slice(0, 600));
  const setcs = await pg.evaluate(() => (document.querySelector('.set-item[data-key="db_local_card"]') || {}).textContent || '');
  ok('...the setting in Czech', /Zobrazit databázi tohoto stroje jako databázový server/.test(setcs), setcs.slice(0, 300));
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/41-local-pair-cs.png' }).catch(() => {});
  await pg.setViewportSize({ width: 420, height: 900 });
  await pg.waitForTimeout(800);
  const wide = await pg.evaluate(() => ({ sw: document.documentElement.scrollWidth,
    box: Math.max(...[...document.querySelectorAll('#db-agent-card, #db-agent .dbs-tile')].map(x => x.getBoundingClientRect().right)),
    one: (() => { const t = document.querySelectorAll('#db-agent .dbs-tile'); return t.length === 2 && t[1].getBoundingClientRect().top >= t[0].getBoundingClientRect().bottom - 1; })() }));
  ok('420 px: it fits, the tiles one under the other', wide.sw <= 420 && wide.box <= 420 && wide.one, wide);
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/42-local-pair-cs-420.png' }).catch(() => {});
  await pg.evaluate(() => api('prefs', {lang: 'en'}));
  ok('no error on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL the test ran through (' + e + ')'); console.log('ALL ' + R.filter(x => x).length + ' / ' + (R.length + 1)); process.exit(1); });
