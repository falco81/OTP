// ui_certpick.js - 1.0.284 in a real Chromium: Values for a certificate request - the account picked as a
// token's "For" box picks a person: "fal" typed, the people of the directory offered (falco@corpnet.cz, its
// name shown), one clicked - looked up at once; arrows and Enter take one of the list; Enter on a name typed
// whole looks it up.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/certpickshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 950 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(4000);
  await p.waitForSelector('#cert-req', { timeout: 20000 });
  await p.click('#cert-req');
  await p.waitForSelector('#creq-name');
  await p.click('#creq-name');
  await p.keyboard.type('fal', { delay: 80 });
  await p.waitForSelector('.suggest .sg-item, .sg-box .sg-item, [class*="suggest"] li', { timeout: 10000 }).catch(() => {});
  await p.waitForTimeout(1500);
  const list = await p.evaluate(() => {
    const box = [...document.querySelectorAll('.t-suggest')].find(e => !e.hidden && /In the directory/.test(e.textContent));
    return box ? box.textContent : '';
  });
  ok('"fal" typed: the people of the directory offered - falco@corpnet.cz with its name', /In the directory/.test(list) && /falco@corpnet\.cz/.test(list) && /Falco Tester/.test(list), list.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/01-offered.png' });
  await p.click('text=falco@corpnet.cz >> nth=0');
  await p.waitForSelector('.creq-grid', { timeout: 15000 }).catch(() => {});
  ok('one clicked: put in and looked up at once', await p.inputValue('#creq-name') === 'falco@corpnet.cz' && /CN=Falco Tester/.test(await p.textContent('.creq-out').catch(() => '')));
  await p.screenshot({ path: SHOTS + '/02-looked-up.png' });
  await p.fill('#creq-name', '');
  await p.keyboard.type('edv', { delay: 80 });
  await p.waitForTimeout(2000);
  await p.keyboard.press('ArrowDown');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  ok('arrows and Enter: one of the list taken and looked up', await p.inputValue('#creq-name') === 'edvorak@corpnet.loc' && /Eva Dvo/.test(await p.textContent('.creq-out').catch(() => '')),
     await p.inputValue('#creq-name'));
  await p.fill('#creq-name', 'jnovak');
  await p.waitForTimeout(800);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  ok('a name typed whole, Enter (the list open, nothing chosen in it): looked up', /jnovak@corpnet\.loc/.test(await p.textContent('.creq-out').catch(() => '')));
  ok('no page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
