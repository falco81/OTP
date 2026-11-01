// t_dbwizard.js - the database pane's wizard driven in Chromium, every way: SQLite -> PostgreSQL
// (set up by it) -> MariaDB (set up by it) -> SQLite (emptied first) -> PostgreSQL (not empty: emptied
// first), each checked: the daemon back on the new one, every count the same. Then a node of a cluster:
// the wizard shut. Needs the installed otp, nginx+PHP, a supervisor that restarts the daemon, the
// administrators wizpg (PostgreSQL 127.0.0.1:5432) and wizroot (MariaDB 127.0.0.1:3306).
const { chromium } = require('playwright');
const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const R = [];
const ok = (what, cond, more) => { R.push(!!cond); console.log((cond ? 'ok   ' : 'FAIL ') + what + (!cond && more ? ' (' + String(more).slice(0, 300) + ')' : '')); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const BASE = 'https://127.0.0.1/admin/';
const shots = '/home/claude/shots/';

async function login(pg) {
  for (let i = 0; i < 30; i++) {
    try {
      await pg.goto(BASE); await pg.waitForTimeout(700);
      if (await pg.$('#in-name')) {
        await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
        await pg.waitForTimeout(2000);
      }
      const st = await pg.evaluate(() => api('db').then(d => d.engine).catch(() => ''));
      if (st) return;
    } catch (e) { }
    await sleep(3000);
  }
  throw new Error('could not sign in');
}
const state = pg => pg.evaluate(() => api('db'));
const foot = pg => pg.$$('#modal-foot button');
async function next(pg) {
  for (let i = 0; i < 120; i++) {
    const b = await foot(pg);
    const last = b[b.length - 1];
    if (last && !(await last.isDisabled())) { await last.click(); await pg.waitForTimeout(500); return; }
    await sleep(500);
  }
  throw new Error('Next stayed shut');
}
async function typeInto(pg, el, text) {
  await el.click({clickCount: 3});
  await pg.keyboard.press('Control+A'); await pg.keyboard.press('Backspace');
  if (text !== '') await pg.keyboard.type(String(text));
}

async function move(pg, idx, addr, admin, tag) {
  const before = await state(pg);
  await pg.goto(BASE + '#settings/db'); await pg.waitForTimeout(2500);
  await pg.evaluate(() => document.querySelector('#db-wizard').click()); await pg.waitForTimeout(800);
  const choices = await pg.$$('.wiz-choice');
  await choices[idx].click(); await pg.waitForTimeout(300);
  await pg.screenshot({path: shots + 'wiz-' + tag + '-1.png'});
  await next(pg);
  if (addr) {
    const inputs = await pg.$$('.wiz-page .formgrid input');
    const vals = [addr.host, addr.port, addr.name, addr.user, addr.password || '', 10];
    for (let i = 0; i < vals.length; i++) await typeInto(pg, inputs[i], vals[i]);
    await pg.screenshot({path: shots + 'wiz-' + tag + '-2.png'});
    await next(pg);
  }
  // Reaching it: set it up when it is not there, empty it when it is not empty.
  for (let i = 0; i < 60; i++) {
    await pg.waitForTimeout(700);
    if (await pg.$('.wiz-setup')) {
      const ins = await pg.$$('.wiz-setup input');
      await typeInto(pg, ins[0], admin.user); await typeInto(pg, ins[1], admin.password);
      await pg.screenshot({path: shots + 'wiz-' + tag + '-3a.png'});
      await (await pg.$('.wiz-setup button')).click();
      await pg.waitForTimeout(3000);
      continue;
    }
    const cb = await pg.$('.wiz-said input[type=checkbox]');
    if (cb && !(await cb.isChecked())) { await cb.check(); await pg.waitForTimeout(300); }
    const b = await foot(pg);
    if (b.length && !(await b[b.length - 1].isDisabled())) break;
  }
  await pg.screenshot({path: shots + 'wiz-' + tag + '-3.png'});
  await next(pg);
  await pg.screenshot({path: shots + 'wiz-' + tag + '-4.png'});
  await next(pg);         // Move it
  let done = false, lines = '';
  for (let i = 0; i < 240; i++) {
    await sleep(1000);
    try {
      lines = await pg.evaluate(() => Array.from(document.querySelectorAll('.wiz-page .si-row')).map(r => (r.querySelector('.dot').className.split(' ')[1]) + ': ' + r.textContent).join(' | '));
      if (/bad:/.test(lines)) break;
      const b = await foot(pg);
      if (b.length === 2 && (await pg.evaluate(() => /Done|Hotovo/.test(document.querySelector('#modal-foot').textContent)))) { done = true; break; }
    } catch (e) { }
  }
  await pg.screenshot({path: shots + 'wiz-' + tag + '-5.png'});
  ok(tag + ': the wizard went through to the end', done, lines);
  await login(pg);
  const after = await state(pg);
  const want = ['sqlite', 'postgres', 'mariadb'][idx];
  ok(tag + ': the daemon runs on ' + want + ' now (' + after.engine + ' · ' + after.where + ')', after.engine === want);
  const same = ['tokens', 'accounts', 'clients', 'realms', 'directories'].every(k => (after.counts || {})[k] === (before.counts || {})[k]);
  ok(tag + ': tokens, accounts, clients, realms, directories all carried (' + JSON.stringify(after.counts) + ')', same, JSON.stringify(before.counts));
}

(async () => {
  const b = await chromium.launch();
  const pg = await (await b.newContext({ignoreHTTPSErrors: true, viewport: {width: 1500, height: 1000}})).newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await login(pg);
  const PGA = {user: 'wizpg', password: 'Wiz-Admin-2x'}, MYA = {user: 'wizroot', password: 'Wiz-Admin-1x'};
  const PGT = {host: '127.0.0.1', port: 5432, name: 'otpwiz_pg', user: 'otpwiz'};
  const MYT = {host: '127.0.0.1', port: 3306, name: 'otpwiz_my', user: 'otpwiz'};
  const IDX = {sqlite: 0, postgres: 1, mariadb: 2}, ADDR = {sqlite: null, postgres: PGT, mariadb: MYT};
  const ADM = {sqlite: null, postgres: PGA, mariadb: MYA};
  // Every way: from wherever it is, through each of the six moves, back to SQLite.
  const ways = (process.env.WAYS || 'postgres,mariadb,sqlite,mariadb,postgres,sqlite,postgres,sqlite').split(',');
  let now = (await state(pg)).engine;
  for (const to of ways) {
    if (to === now) continue;
    await move(pg, IDX[to], ADDR[to], ADM[to], now + '-to-' + to);
    now = (await state(pg)).engine;
  }
  ok('no error in the page', !errs.length, errs.join(' | '));
  // A node of a cluster: another node heard from - the wizard shut, the server refuses.
  require('child_process').execSync('/usr/local/lib/otp/python /home/claude/ws/tests/ui/fake_node.py add');
  await pg.goto(BASE + '#settings/db'); await pg.reload(); await pg.waitForTimeout(3000);
  const shut = await pg.evaluate(() => [document.querySelector('#db-wizard').disabled, !document.querySelector('#db-wizard-cluster').hidden]);
  await pg.screenshot({path: shots + 'wiz-cluster.png'});
  ok('a node of a cluster: the wizard shut, and why said', shut[0] && shut[1], JSON.stringify(shut));
  const refused = await pg.evaluate(() => api('db', {action: 'move', settings: {db_engine: 'postgres', db_host: '127.0.0.1', db_port: 5432, db_name: 'x', db_user: 'x'}}).then(() => 'taken', e => String(e.message || e)));
  ok('... and the server refuses the move all the same (' + refused + ')', /cluster/.test(refused));
  require('child_process').execSync('/usr/local/lib/otp/python /home/claude/ws/tests/ui/fake_node.py drop');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  await b.close();
})().catch(e => { console.log('FAIL ' + e.message); console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
