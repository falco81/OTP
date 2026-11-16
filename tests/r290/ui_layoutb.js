// ui_layoutb.js - 1.0.290 in a real Chromium, on the installed otp (standalone, no agent):
//  - as before: High availability -> Making it two has no steps of layout B;
//  - /api/ha answered in the page as a node whose database is PostgreSQL on its agent's server (db_here):
//    "Each node's database on a server of its own", the commands filled in from what is typed (--ha-peer the
//    other database server, --ha-peer-node the other otp node, install.sh --db-server, --db-agent-join -,
//    --ha-join, --ha-tls-repair), an address that is none marked;
//  - not drawn for a node already one of two, nor for one whose database is not on its agent's server;
//  - Czech; a phone (420 px, nothing wider).
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const BASE = 'https://127.0.0.1/admin/';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/dbashots';
fs.mkdirSync(SHOTS, { recursive: true });
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 400) + ')')); };

(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto(BASE); await pg.waitForTimeout(700);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2000);

  // ---- as before ----
  await pg.goto(BASE + '#settings/ha'); await pg.reload(); await pg.waitForTimeout(3500);
  const real = await pg.evaluate(() => api('ha'));
  ok('the real /api/ha: no agent - no db_here, no database servers', !real.db_here && !real.dbservers, Object.keys(real));
  ok('...Making it two as before: no steps of layout B', await pg.evaluate(() => !!document.getElementById('ha-make-body') && !document.getElementById('ha-dbs-make')));

  // ---- a node whose database is on its agent's server ----
  let over = { engine: 'postgres', db_admin: 'agent:192.0.2.21:9443', db_here: true, dbservers: [], mode: '', address: '192.0.2.11', node: 'otp1' };
  await pg.route(/\?api=ha(&|$)/, async (r) => {
    if (r.request().method() !== 'GET') return r.continue();
    const got = await r.fetch();
    const d = JSON.parse(await got.text());
    return r.fulfill({ contentType: 'application/json', body: JSON.stringify(Object.assign(d, over)) });
  });
  await pg.reload(); await pg.waitForTimeout(3500);
  const s1 = await pg.evaluate(() => {
    const x = document.getElementById('ha-dbs-make');
    return x && { text: x.textContent, first: x.parentNode.id === 'ha-make-body' && x.parentNode.firstChild === x,
      cmds: [...x.querySelectorAll('pre')].map(p => p.textContent) };
  });
  ok('db_here: "Each node’s database on a server of its own" first in Making it two', s1 && s1.first &&
     /Each node’s database on a server of its own/.test(s1.text) && /--ha-peer-node the other otp node/.test(s1.text), s1);
  ok('...the commands with placeholders until typed', s1 && s1.cmds[0] === 'otp --ha-setup --ha-peer DB2 --ha-peer-node OTP2 --node-name otp1' &&
     s1.cmds[1] === './install.sh --db-server postgres --otp-node OTP2 --otp-node 192.0.2.11', s1 && s1.cmds);
  await pg.fill('#ha-dbs-peer', '192.0.2.22');
  await pg.fill('#ha-dbs-node', '192.0.2.12');
  await pg.fill('#ha-dbs-name2', 'otp2');
  await pg.waitForTimeout(300);
  const cmds = await pg.evaluate(() => [...document.querySelectorAll('#ha-dbs-make pre')].map(p => p.textContent));
  ok('typed: otp --ha-setup --ha-peer 192.0.2.22 --ha-peer-node 192.0.2.12 --node-name otp1',
     cmds[0] === 'otp --ha-setup --ha-peer 192.0.2.22 --ha-peer-node 192.0.2.12 --node-name otp1', cmds);
  ok('...the other database server: install.sh --db-server postgres --otp-node 192.0.2.12 --otp-node 192.0.2.11',
     cmds[1] === './install.sh --db-server postgres --otp-node 192.0.2.12 --otp-node 192.0.2.11', cmds[1]);
  ok('...the second node: --db-agent-join - then --ha-join with the bundle\'s name',
     cmds[2] === 'otp --db-agent-join -\notp --ha-join /root/otp-join-otp1.json --node-name otp2', cmds[2]);
  ok('...then the link: otp --ha-tls-repair', cmds[3] === 'otp --ha-tls-repair', cmds[3]);
  await pg.waitForTimeout(5500);
  ok('...kept as typed when the pane is drawn again', await pg.evaluate(() => document.getElementById('ha-dbs-peer') &&
     document.getElementById('ha-dbs-peer').value === '192.0.2.22'));
  await pg.fill('#ha-dbs-node', 'otp2.example');
  await pg.waitForTimeout(200);
  ok('an address that is none: marked', await pg.evaluate(() => document.getElementById('ha-dbs-node').classList.contains('bad')));
  await pg.fill('#ha-dbs-node', '192.0.2.12');
  await pg.locator('#ha-dbs-make').screenshot({ path: SHOTS + '/20-ha-layoutb.png' }).catch(() => {});

  over = Object.assign({}, over, { mode: 'replicated' });
  await pg.reload(); await pg.waitForTimeout(3500);
  ok('one of two already: not drawn', await pg.evaluate(() => !document.getElementById('ha-dbs-make')));
  over = Object.assign({}, over, { mode: '', db_here: false });
  await pg.reload(); await pg.waitForTimeout(3500);
  ok('an agent joined, the database not on its server: not drawn', await pg.evaluate(() => !document.getElementById('ha-dbs-make')));
  over = Object.assign({}, over, { db_here: true });

  // ---- Czech, a phone ----
  await pg.evaluate(() => api('prefs', {lang: 'cs'})); await pg.reload(); await pg.waitForTimeout(4000);
  const cs = await pg.evaluate(() => (document.getElementById('ha-dbs-make') || {}).textContent || '');
  ok('Czech: Databáze každého uzlu na vlastním serveru, Druhý databázový server, Na tomto uzlu jako root',
     /Databáze každého uzlu na vlastním serveru/.test(cs) && /Druhý databázový server/.test(cs) && /Na tomto uzlu jako root/.test(cs) &&
     /otp --ha-setup --ha-peer DB2/.test(cs), cs.slice(300, 1400));
  ok('...nothing left in English', !/On this node, as root|The other database server|Each node’s database/.test(cs), cs.slice(0, 300));
  await pg.locator('#ha-dbs-make').screenshot({ path: SHOTS + '/21-ha-layoutb-cs.png' }).catch(() => {});
  await pg.setViewportSize({ width: 420, height: 900 });
  await pg.waitForTimeout(800);
  const wide = await pg.evaluate(() => ({ box: document.getElementById('ha-dbs-make').getBoundingClientRect().right, sw: document.documentElement.scrollWidth }));
  ok('420 px: it fits (nothing wider than the window)', wide.box <= 420 && wide.sw <= 420, wide);
  await pg.locator('#ha-dbs-make').screenshot({ path: SHOTS + '/22-ha-layoutb-cs-420.png' }).catch(() => {});
  await pg.evaluate(() => api('prefs', {lang: 'en'}));
  ok('no error on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL the test ran through (' + e + ')'); console.log('ALL ' + R.filter(x => x).length + ' / ' + (R.length + 1)); process.exit(1); });
