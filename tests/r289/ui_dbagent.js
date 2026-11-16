// ui_dbagent.js - 1.0.289 in a real Chromium, on the installed otp (its database the file here, no agent):
//  - no agent: Settings -> The database exactly as before - no card, no pill, nothing said;
//  - /api/db-agent answered in the page (a node whose database is on a server with its agent): the card,
//    its tile, its actions, the pills on Database -> TLS and the server's own settings; the agent down: red,
//    what it said; layout B's forget refused: no Forget; Czech; a phone (420 px, nothing wider);
//  - the wizard: the commands for the database server, the code read as it is pasted (cut short said;
//    a good one: the agent and its certificate - never the secret), Connect it answered: connected;
//  - the move wizard's first step offers Connect a database server.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const BASE = 'https://127.0.0.1/admin/';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/dbashots';
fs.mkdirSync(SHOTS, { recursive: true });
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 400) + ')')); };
const now = Date.now() / 1000;
const SECRET = 'S3cr3tOfTheCodeNeverShown';

function view(over) {
  const me = Object.assign({
    kind: 'db', name: 'db:vm', node: 'vm', me: true, alive: true, ok: true, at: now - 12, host: '192.0.2.21', port: 9443,
    db_host: '192.0.2.21', engine: 'postgres', agent_cert_end: now + 300 * 86400, client_cert_end: now + 700 * 86400,
    facts: { host: 'db1', fqdn: 'db1.example.lan', running: true, version: '16.4 (Debian 16.4-1)', ssl: true, connections: 7,
      disk: { total: 100e9, free: 61e9 }, ram: 8e9, avail: 5e9, cpus: 4, load: [0.43, 0.36, 0.30], uptime: 86400 * 12,
      started: now - 86400 * 3 },
    agent: { version: '1.0.289', cert_end: now + 300 * 86400, clients: [{ name: 'vm' }], stale_days: 30 }
  }, (over || {}).me || {});
  return Object.assign({
    db_admin: 'agent:192.0.2.21:9443', node: 'vm', servers: [me], host: '192.0.2.21', port: 9443, db_host: '192.0.2.21',
    engine: 'postgres', db_port: 5432, joined_at: now - 3600, joined_by: 'admin', peer_node: '', forget_refused: '',
    agent_cert_end: me.agent_cert_end, client_cert_end: me.client_cert_end, state: { ok: true },
    applies: { dbtls: 'the database\'s certificate from otp\'s authority, ssl on, its renewal', db_tune: 'the database server\'s own settings and their restart', db_firewall: 'the database\'s port opened to the otp nodes and the other server' },
    where: { engine: 'postgres', host: '192.0.2.21', port: 5432, name: 'otp', local: false, agent: true, kind: 'agent' },
    ha_mode: '', addresses: ['192.0.2.11']
  }, over || {});
}
function code(o) {
  return 'ODBA1.' + Buffer.from(JSON.stringify(Object.assign({ h: '192.0.2.21', p: 9443, s: SECRET, i: 'ab12cd34', f: 'a'.repeat(64), e: 'postgres', k: 'b'.repeat(64) }, o || {}))).toString('base64url');
}

(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto(BASE); await pg.waitForTimeout(700);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2000);

  // ---- no agent: as before ----
  await pg.goto(BASE + '#settings/db'); await pg.reload(); await pg.waitForTimeout(3500);
  const real = await pg.evaluate(() => api('db-agent'));
  ok('the real /api/db-agent: no agent, db_admin local, the file here', real.db_admin === 'local' && (real.servers || []).length === 0 && (real.where || {}).kind === 'file', real.where);
  ok('...no card, no pill on Database -> TLS or the server\'s own settings', await pg.evaluate(() => !document.getElementById('db-agent-card') && !document.querySelector('.dbs-pill')));
  await pg.evaluate(() => dbWizard()); await pg.waitForTimeout(800);
  ok('the move wizard\'s first step offers Connect a database server…', await pg.evaluate(() => !!document.getElementById('dbw-agent')));
  await pg.evaluate(() => closeModal()); await pg.waitForTimeout(300);

  // ---- an agent, answered in the page ----
  let V = view();
  let posted = [];
  await pg.route(/\?api=db-agent/, async (r) => {
    if (r.request().method() === 'POST') {
      const body = JSON.parse(r.request().postData() || '{}');
      posted.push(body);
      if (body.action === 'join') {
        if (body.code.indexOf('ODBA1.') !== 0) return r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ error: 'bad' }) });
        const J = view();
        return r.fulfill({ contentType: 'application/json', body: JSON.stringify({ host: '192.0.2.21', port: 9443, facts: J.servers[0].facts, agent: J.servers[0].agent, view: J }) });
      }
      return r.fulfill({ contentType: 'application/json', body: JSON.stringify({ view: V, message: 'done' }) });
    }
    return r.fulfill({ contentType: 'application/json', body: JSON.stringify(V) });
  });
  await pg.reload(); await pg.waitForTimeout(3500);
  const c1 = await pg.evaluate(() => {
    const c = document.getElementById('db-agent-card');
    return c && { h: c.querySelector('h2').textContent, tile: !!c.querySelector('.dbs-tile.me'), text: c.textContent,
      btns: ['dba-look', 'dba-renew', 'dba-restart', 'dba-forget'].filter(i => document.getElementById(i)),
      tunePill: !!document.querySelector('#db-tune-card > h2 > .dbs-pill'), tlsPill: !!document.querySelector('#db-tls-card > h2 > .dbs-pill') };
  });
  ok('with an agent: the card Database server, this node\'s tile', c1 && c1.tile && /Database server/.test(c1.h), c1);
  ok('...on db1.example.lan, looked after by otp-db-agent at 192.0.2.21:9443, PostgreSQL 16.4, running, TLS on', c1 && /db1\.example\.lan/.test(c1.text) && /192\.0\.2\.21:9443/.test(c1.text) && /16\.4/.test(c1.text) && /running/.test(c1.text), c1 && c1.text.slice(0, 300));
  ok('...Look now, Renew the certificates, Restart the database, Forget the agent', c1 && c1.btns.length === 4, c1 && c1.btns);
  ok('...the pill on the server\'s own settings', c1 && c1.tunePill, c1);
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/01-card-en.png' }).catch(() => {});
  await pg.click('#dba-look'); await pg.waitForTimeout(800);
  ok('Look now asks POST {action: look}', posted.some(x => x.action === 'look'), posted);

  // ---- the agent down ----
  V = view({ me: { ok: false, alive: false, said: 'the database agent at 192.0.2.21:9443 does not answer: [Errno 111] Connection refused', down_since: now - 300 } });
  await pg.reload(); await pg.waitForTimeout(3500);
  const c2 = await pg.evaluate(() => { const c = document.getElementById('db-agent-card'); return c && { text: c.textContent, bad: !!c.querySelector('.dbs-tile.bad'), hero: !!c.querySelector('.dbs-hero.bad') }; });
  ok('the agent down: red, "its agent does not answer", what it said', c2 && c2.bad && c2.hero && /its agent does not answer/.test(c2.text) && /Connection refused/.test(c2.text), c2);
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/02-card-down.png' }).catch(() => {});

  // ---- layout B's forget refused, notes ----
  V = view({ forget_refused: 'this node is one of a cluster...', me: { agent: { version: '1.0.290', cert_end: now + 300 * 86400, clients: [{ name: 'vm' }, { name: 'old', stale: true }], stale_days: 30, busy: { op: 'pg_restart', node: 'other', since: now - 20 } }, version_skew: { agent: '1.0.290', otp: '1.0.289', how: 'newer' } } });
  await pg.reload(); await pg.waitForTimeout(3500);
  const c3 = await pg.evaluate(() => { const c = document.getElementById('db-agent-card'); return c && { forget: !!document.getElementById('dba-forget'), text: c.textContent }; });
  ok('forget refused: no Forget the agent', c3 && !c3.forget, c3);
  ok('...the notes: Not heard from (old), Busy with pg_restart, Newer than otp', c3 && /Not heard from/.test(c3.text) && /pg_restart/.test(c3.text) && /Newer than otp/.test(c3.text), c3 && c3.text.slice(-600));

  // ---- Czech ----
  V = view();
  await pg.evaluate(() => api('prefs', {lang: 'cs'})); await pg.reload(); await pg.waitForTimeout(4000);
  const cz = await pg.evaluate(() => { const c = document.getElementById('db-agent-card'); return c && { h: c.querySelector('h2').textContent, text: c.textContent }; });
  ok('Czech: Databázový server, Podívat se teď / Obnovit certifikáty', cz && /Databázový server/.test(cz.h) && /Obnovit certifikáty/.test(cz.text), cz && cz.text.slice(0, 400));
  ok('...the load with the page\'s decimal mark (0,43)', cz && /0,43/.test(cz.text), cz && cz.text.slice(0, 600));
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/03-card-cs.png' }).catch(() => {});

  // ---- a phone ----
  await pg.setViewportSize({ width: 420, height: 900 });
  await pg.waitForTimeout(800);
  const wide = await pg.evaluate(() => ({ sw: document.documentElement.scrollWidth, card: Math.round(document.getElementById('db-agent-card').getBoundingClientRect().right) }));
  ok('420 px: the card fits (nothing wider than the window)', wide.card <= 420 && wide.sw <= 420, wide);
  await pg.locator('#db-agent-card').screenshot({ path: SHOTS + '/04-card-cs-420.png' }).catch(() => {});
  await pg.setViewportSize({ width: 1400, height: 1000 });
  await pg.evaluate(() => api('prefs', {lang: 'en'})); await pg.reload(); await pg.waitForTimeout(3500);

  // ---- the wizard ----
  V = view({ db_admin: 'local', servers: [], where: { engine: 'postgres', host: '192.0.2.30', port: 5432, kind: 'unmanaged', local: false, agent: false }, host: undefined, port: undefined });
  await pg.reload(); await pg.waitForTimeout(3500);
  const un = await pg.evaluate(() => { const c = document.getElementById('db-agent-card'); return c && { text: c.textContent, connect: !!document.getElementById('dba-connect') }; });
  ok('a server elsewhere, no agent: the card says so, Connect a database server…', un && un.connect && /no agent looks after/.test(un.text), un);
  await pg.click('#dba-connect'); await pg.waitForTimeout(1200);
  const w1 = await pg.evaluate(() => document.getElementById('modal-body').textContent);
  ok('the wizard, step 1: ./install.sh --db-server postgres --otp-node 192.0.2.11, the agent alone, a new code', /install\.sh --db-server postgres --otp-node 192\.0\.2\.11/.test(w1) && /--db-agent/.test(w1) && /otp_db_agent\.py --new-code/.test(w1), w1.slice(0, 500));
  await pg.locator('#modal-box').screenshot({ path: SHOTS + '/05-wizard-1.png' }).catch(() => {});
  await pg.click('#modal-foot button:has-text("I have the code")'); await pg.waitForTimeout(600);
  await pg.fill('#dbs-code', 'ODBA1.eyJoIjoi'); await pg.waitForTimeout(300);
  ok('step 2: a code cut short is said as it is pasted', await pg.evaluate(() => /cut short/.test(document.getElementById('dbs-code-said').textContent) && document.getElementById('dbs-code-said').classList.contains('bad')));
  await pg.fill('#dbs-code', code()); await pg.waitForTimeout(300);
  const said = await pg.evaluate(() => document.getElementById('dbs-code-said').textContent);
  ok('...a good one: the agent at 192.0.2.21:9443 and its certificate - never the secret', /192\.0\.2\.21:9443/.test(said) && /aaaaaaaa/.test(said) && !(await pg.evaluate(s => document.body.textContent.indexOf(s) >= 0, SECRET)), said);
  await pg.locator('#modal-box').screenshot({ path: SHOTS + '/06-wizard-2.png' }).catch(() => {});
  await pg.click('#modal-foot button:has-text("Connect it")'); await pg.waitForTimeout(1800);
  const j = posted.filter(x => x.action === 'join').pop() || {};
  ok('Connect it: POST {action: join, code}', j.code === code(), j);
  V = view();
  const w3 = await pg.evaluate(() => document.getElementById('modal-body').textContent);
  ok('step 3: connected, the server\'s tile', /Connected/.test(w3) && /db1/.test(w3), w3.slice(0, 500));
  await pg.locator('#modal-box').screenshot({ path: SHOTS + '/07-wizard-3.png' }).catch(() => {});
  ok('no error on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL the test ran through (' + e + ')'); console.log('ALL ' + R.filter(x => x).length + ' / ' + (R.length + 1)); process.exit(1); });
