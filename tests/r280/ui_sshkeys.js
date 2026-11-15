// ui_sshkeys.js - 1.0.280: Settings - SSH keys in a real Chromium. Root's keys only shown (no Make a key,
// no Add a key, no taking away - the export stays, a note says where it is done); a normal user's keys
// made and added as before (Make a key, Add a key, a key made and taken away). The server refuses root's
// from the pages too (t_r280.py). Needs root's helper (tests/dg/webloop.sh) and a user t280user.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/sshkeyshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/sshkeys'); await p.waitForTimeout(4000);
  await p.waitForSelector('#sk-host .sk-who select', { timeout: 30000 }).catch(() => {});
  const host = () => p.textContent('#sk-host').catch(() => '');
  let t = await host();
  ok('root: the keys are listed', /Keys that may sign in as root/.test(t), t.slice(0, 200));
  ok('root: no Make a key', !(await p.$('#sk-host button:has-text("Make a key")')));
  ok('root: no Add a key', !(await p.$('#sk-host button:has-text("Add a key")')));
  ok('root: no key taken away from here', (await p.$$('#sk-host button[title="Take this key away"], #sk-host button[aria-label="Take this key away"]')).length === 0);
  ok('root: a note says it is done by root on the node itself', /only shown here/.test(t) && /on the node itself/.test(t), t.slice(0, 300));
  await p.screenshot({ path: SHOTS + '/01-root-only-shown.png' });
  for (let i = 0; i < 30; i++) {
    const has = await p.$eval('#sk-host .sk-who select', s => [...s.options].some(o => o.value === 't280user')).catch(() => false);
    if (has) break;
    await p.waitForTimeout(1000);
  }
  await p.selectOption('#sk-host .sk-who select', 't280user').catch(() => {});
  await p.waitForTimeout(3000);
  t = await host();
  ok('t280user: A key for t280user', /A key for/.test(t) && /t280user/.test(t), t.slice(0, 200));
  const mk = await p.$('#sk-host button:has-text("Make a key")');
  ok('t280user: Make a key there', !!mk && !(await mk.isDisabled()));
  ok('t280user: Add a key there', !!(await p.$('#sk-host button:has-text("Add a key")')));
  await p.screenshot({ path: SHOTS + '/02-user-card.png' });
  if (mk && !(await mk.isDisabled())) {
    await mk.click(); await p.waitForTimeout(800);
    await p.click('#modal button:has-text("Make one")').catch(() => {});
    await p.waitForSelector('#modal textarea', { timeout: 20000 }).catch(() => {});
    const priv = await p.$eval('#modal textarea', e => e.value).catch(() => '');
    ok('t280user: a key made - its private half shown once', /PRIVATE KEY/.test(priv));
    await p.screenshot({ path: SHOTS + '/03-user-key-made.png' });
    await p.click('#modal button:has-text("I have kept it")').catch(() => {});
    let rows = 0;
    for (let i = 0; i < 20 && rows < 1; i++) {
      await p.waitForTimeout(1500);
      rows = (await p.$$('#sk-host td.sk-act')).length;
    }
    ok('t280user: the key is in the list', rows >= 1, rows);
    // (a key of a run before may be there too: one row fewer is what counts)
    const btns = await p.$$('#sk-host td.sk-act:first-of-type button, #sk-host tr:nth-child(1) td.sk-act button');
    const per = (await p.$$('#sk-host td.sk-act button')).length / Math.max(rows, 1);
    ok('t280user: each key can be exported and taken away', per === 2, per);
    if (per === 2) {
      await p.waitForTimeout(6000);           // the list drawn again by the poll: the button found afresh
      rows = (await p.$$('#sk-host td.sk-act')).length;
      await p.locator('#sk-host td.sk-act button').nth(1).click(); await p.waitForTimeout(800);
      const mt = await p.textContent('#modal').catch(() => '');
      await p.screenshot({ path: SHOTS + '/04-take-away.png' });
      ok('t280user: taking it away asks first', /Take the key away/.test(mt), mt.slice(0, 200));
      // anything that destroys is asked twice: "Really?", then the same button again
      await p.locator('#modal-foot > button.danger').click().catch(() => {});
      await p.waitForTimeout(500);
      await p.locator('#modal-foot .sure-strip button.danger').click().catch(() => {});
      let left = rows;
      for (let i = 0; i < 20 && left >= rows; i++) { await p.waitForTimeout(1500); left = (await p.$$('#sk-host td.sk-act')).length; }
      ok('t280user: ...taken away (one row fewer)', left === rows - 1, rows + ' -> ' + left);
    }
  }
  ok('no page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
