// ui_moves.js - 1.0.291 in a real Chromium, on the installed otp (standalone, no agent):
//  - as before: the move wizard without an agent - no "Make it for me", no agent's lines;
//  - /api/db answered in the page as a node joined to an agent (not moved yet): step Reaching it on
//    the agent's server offers "Make the database and the account for me" (no administrator asked),
//    the request is setup by_agent, what the agent did is listed, the password made shown once;
//    step What happens: "onto the server of this node's database agent";
//  - on the agent's server, moving to SQLite: "the database leaves the server ... let go";
//  - a node of a cluster with each node's database on a server of its own: refused with its words;
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
  await pg.goto(BASE + '#settings/db'); await pg.reload(); await pg.waitForTimeout(3500);

  const real = await pg.evaluate(() => api('db'));
  ok('the real /api/db: no agent key', !('agent' in real), Object.keys(real));

  // the wizard, filled in, on step 2 / 3 - as the page would after typing
  const toStep = async (step, eng) => {
    await pg.evaluate(([step, eng]) => {
      closeModal(); dbWizard();
      DBW.engine = eng;
      DBW.addr = eng === 'sqlite' ? {} : {host: '192.0.2.21', port: 5432, name: 'otp2', user: 'otp2', password: '', timeout: 10};
      DBW.step = step; dbwDraw();
    }, [step, eng]);
    await pg.waitForTimeout(1200);
  };

  // ---- as before: no agent ----
  await pg.route(/\?api=db(&|$)/, async (r) => {
    if (r.request().method() !== 'POST') return r.continue();
    const body = JSON.parse(r.request().postData() || '{}');
    if (body.action === 'try') return r.fulfill({ contentType: 'application/json', body: JSON.stringify(
      { reached: false, writable: false, in_use: false, where: 'otp2@192.0.2.21:5432/otp2', trouble: 'no answer' }) });
    return r.continue();
  });
  await toStep(2, 'postgres');
  const s0 = await pg.evaluate(() => ({ agent: !!document.getElementById('dbw-agent-make'),
    admin: /An administrator on that server/.test(document.getElementById('modal').textContent) }));
  ok('no agent: step Reaching it as before - an administrator asked, no Make it for me', !s0.agent && s0.admin, s0);
  await pg.unroute(/\?api=db(&|$)/);

  // ---- joined to an agent, not moved yet ----
  let get = { agent: { host: '192.0.2.21', port: 9443, engine: 'postgres', db_host: '192.0.2.21', db_port: 5432, here: false, layout_b: false } };
  let made = false, setupBody = null;
  await pg.route(/\?api=db(&|$)/, async (r) => {
    const m = r.request().method();
    if (m === 'GET') {
      const got = await r.fetch();
      const d = JSON.parse(await got.text());
      return r.fulfill({ contentType: 'application/json', body: JSON.stringify(Object.assign(d, get)) });
    }
    const body = JSON.parse(r.request().postData() || '{}');
    if (body.action === 'try') {
      const sq = (body.settings || {}).db_engine === 'sqlite';
      return r.fulfill({ contentType: 'application/json', body: JSON.stringify(sq ?
        { reached: true, writable: true, rows: 0, in_use: false, where: '/var/lib/otp/otp.db', agent_server: false, tables: [] } :
        made ? { reached: true, writable: true, rows: 0, in_use: false, where: 'otp2@192.0.2.21:5432/otp2', agent_server: true, tables: [] } :
               { reached: false, writable: false, in_use: false, where: 'otp2@192.0.2.21:5432/otp2', trouble: 'password authentication failed', agent_server: true }) });
    }
    if (body.action === 'setup') {
      setupBody = body; made = true;
      return r.fulfill({ contentType: 'application/json', body: JSON.stringify({ made: ['the account otp2 was made', 'the database otp2 was made',
        '/etc/postgresql/pg_hba.conf: host otp2 otp2 192.0.2.11/32 scram-sha-256'], password: 'Made-Once-Pw-123', try: {} }) });
    }
    return r.continue();
  });
  await pg.reload(); await pg.waitForTimeout(3500);
  await toStep(2, 'postgres');
  const s1 = await pg.evaluate(() => {
    const x = document.querySelector('.dbw-agent-make');
    return x && { text: x.textContent, admin: /An administrator on that server/.test(document.getElementById('modal').textContent) };
  });
  ok('the agent\'s server: "Make it for me" - made by the agent, no administrator asked', s1 &&
     /The server of this node’s database agent \(192\.0\.2\.21:5432\)/.test(s1.text) && /no administrator’s password typed anywhere/.test(s1.text) &&
     !s1.admin, s1);
  await pg.locator('#modal').screenshot({ path: SHOTS + '/30-move-make-for-me.png' }).catch(() => {});
  await pg.click('#dbw-agent-make'); await pg.waitForTimeout(1500);
  ok('...the request: setup by_agent, no administrator', setupBody && setupBody.by_agent === true && !setupBody.admin_user &&
     setupBody.settings.db_name === 'otp2', setupBody);
  const s2 = await pg.evaluate(() => ({ list: [...document.querySelectorAll('.dbw-agent-made li')].map(x => x.textContent),
    pw: [...document.querySelectorAll('#modal input[readonly]')].map(x => x.value), ready: /ready/.test(document.getElementById('modal').textContent),
    next: !document.querySelector('#modal .wiz-foot button.primary, #modal button.primary:last-child') || true }));
  ok('...what its agent did listed, the password made shown once, ready', s2.list.length === 3 && /otp2 was made/.test(s2.list[0]) &&
     s2.pw.includes('Made-Once-Pw-123') && s2.ready, s2);
  await pg.locator('#modal').screenshot({ path: SHOTS + '/31-move-made-by-agent.png' }).catch(() => {});
  await pg.evaluate(() => dbwGo(3)); await pg.waitForTimeout(600);
  const s3 = await pg.evaluate(() => (document.querySelector('.dbw-agent-onto') || {}).textContent || '');
  ok('step What happens: onto the server of this node\'s database agent, then Database → TLS', /onto the server of this node’s database agent/.test(s3) &&
     /Database → TLS/.test(s3), s3);
  ok('...no "leaves" line', await pg.evaluate(() => !document.querySelector('.dbw-agent-off')));

  // ---- on the agent's server, to SQLite ----
  get = { agent: Object.assign({}, get.agent, { here: true }) };
  await pg.reload(); await pg.waitForTimeout(3500);
  await toStep(2, 'sqlite');
  ok('to SQLite: no Make it for me', await pg.evaluate(() => !document.getElementById('dbw-agent-make')));
  await pg.evaluate(() => dbwGo(3)); await pg.waitForTimeout(600);
  const s4 = await pg.evaluate(() => (document.querySelector('.dbw-agent-off') || {}).textContent || '');
  ok('step What happens: the database leaves the agent\'s server, the agent let go and told', /leaves the server of this node’s database agent/.test(s4) &&
     /let go and told this node leaves it/.test(s4) && /new join code/.test(s4), s4);
  await pg.locator('#modal').screenshot({ path: SHOTS + '/32-move-leaves-agent.png' }).catch(() => {});

  // ---- layout B: refused ----
  get = { cluster: true, ha_mode: 'replicated', agent: Object.assign({}, get.agent, { here: true, layout_b: true }) };
  await pg.reload(); await pg.waitForTimeout(3500);
  await pg.evaluate(() => { closeModal(); dbWizard(); }); await pg.waitForTimeout(600);
  const s5 = await pg.evaluate(() => document.getElementById('modal').textContent);
  ok('layout B: refused with its words and the way out', /each node’s database on a server of its own/.test(s5) &&
     /--ha-standalone --yes on both nodes/.test(s5) && !/Which one/.test(s5), s5.slice(0, 500));
  get = { cluster: true, ha_mode: 'shared', agent: Object.assign({}, get.agent, { layout_b: false }) };
  await pg.reload(); await pg.waitForTimeout(3500);
  await pg.evaluate(() => { closeModal(); dbWizard(); }); await pg.waitForTimeout(600);
  ok('...a shared cluster: the refusal as before', await pg.evaluate(() => /moving it from here would break the cluster/.test(document.getElementById('modal').textContent)));

  // ---- Czech, a phone ----
  get = { agent: { host: '192.0.2.21', port: 9443, engine: 'postgres', db_host: '192.0.2.21', db_port: 5432, here: false, layout_b: false } };
  made = false;
  await pg.evaluate(() => api('prefs', {lang: 'cs'})); await pg.reload(); await pg.waitForTimeout(4000);
  await toStep(2, 'postgres');
  const cs = await pg.evaluate(() => document.getElementById('modal').textContent);
  ok('Czech: Udělat to za mě, Server databázového agenta tohoto uzlu, Vytvořit databázi a účet za mě',
     /Udělat to za mě/.test(cs) && /Server databázového agenta tohoto uzlu/.test(cs) && /Vytvořit databázi a účet za mě/.test(cs) &&
     /heslo správce se nikde nezadává/.test(cs), cs.slice(0, 900));
  ok('...nothing of it left in English', !/Make it for me|the agent makes the database|Encryption is that server/.test(cs), cs.slice(0, 900));
  await pg.click('#dbw-agent-make'); await pg.waitForTimeout(1500);
  await pg.evaluate(() => dbwGo(3)); await pg.waitForTimeout(600);
  const cs3 = await pg.evaluate(() => (document.querySelector('.dbw-agent-onto') || {}).textContent || '');
  ok('...step 3 in Czech', /na server databázového agenta tohoto uzlu/.test(cs3), cs3);
  await pg.evaluate(() => dbwGo(2)); await pg.waitForTimeout(1200);
  await pg.locator('#modal').screenshot({ path: SHOTS + '/33-move-made-by-agent-cs.png' }).catch(() => {});
  await pg.setViewportSize({ width: 420, height: 900 });
  await pg.waitForTimeout(800);
  const wide = await pg.evaluate(() => ({ sw: document.documentElement.scrollWidth, box: document.querySelector('.dbw-agent-made').getBoundingClientRect().right }));
  ok('420 px: it fits (nothing wider than the window)', wide.sw <= 420 && wide.box <= 420, wide);
  await pg.locator('#modal').screenshot({ path: SHOTS + '/34-move-made-by-agent-cs-420.png' }).catch(() => {});
  await pg.evaluate(() => api('prefs', {lang: 'en'}));
  await pg.evaluate(() => closeModal());
  ok('no error on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL the test ran through (' + e + ')'); console.log('ALL ' + R.filter(x => x).length + ' / ' + (R.length + 1)); process.exit(1); });
