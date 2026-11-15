// ui_redraw.js - 1.0.280: Settings - Accounts in a real Chromium. A setting of the cards saved with Save
// shows on the cards at once - no F5: "Ask an OCSP responder" changes the Revocation steps on the
// certificate's card, "By itself on the sign-in page" changes the card and The sign-in page. The page is
// not loaded again meanwhile, and the card stays where it was (no jump).
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/redrawshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(4000);
  await p.waitForSelector('#cert-host .rev-flow', { timeout: 30000 }).catch(() => {});
  await p.evaluate(() => { window.__notReloaded = 1; });
  const flow = () => p.textContent('#cert-host .rev-flow').catch(() => '');
  const save = async () => { await p.click('#set-save'); await p.waitForTimeout(3500); };
  let f0 = await flow();
  ok('the steps as they are: the CRL alone', /CRL/.test(f0) && !/OCSP/.test(f0), f0);
  await p.$eval('#cert-host .rev-flow', e => e.scrollIntoView({ block: 'center' }));
  await p.waitForTimeout(300);
  await p.selectOption('#set-admin_cert_ocsp', 'first');
  await p.waitForTimeout(500);            // the box of its own responder wakes above: measured after it
  const t0 = await p.$eval('#cert-host .rev-flow', e => e.getBoundingClientRect().top);
  await save();
  let f1 = await flow();
  ok('OCSP "first" saved: the steps on the card at once - OCSP, no answer, CRL', /OCSP/.test(f1) && /no answer/.test(f1), f1);
  const t1 = await p.$eval('#cert-host .rev-flow', e => e.getBoundingClientRect().top).catch(() => null);
  ok('...the card stayed where it was (' + Math.round(t1 - t0) + ' px)', t1 !== null && Math.abs(t1 - t0) <= 2, t0 + ' -> ' + t1);
  await p.screenshot({ path: SHOTS + '/01-ocsp-first-at-once.png' });
  await p.selectOption('#set-admin_cert_ocsp', 'off');
  await save();
  f1 = await flow();
  ok('...off again: the CRL alone at once', /CRL/.test(f1) && !/OCSP/.test(f1), f1);
  // By itself on the sign-in page: the card's facts and The sign-in page
  const signin = () => p.textContent('#signin-host').catch(() => '');
  const certFacts = () => p.textContent('#cert-host .kv-grid').catch(() => '');
  const auto0 = await p.$eval('#set-admin_cert_auto input', e => e.checked).catch(() => null);
  ok('the switch "by itself" is there', auto0 !== null);
  const s0 = await signin();
  await p.click('#set-admin_cert_auto');
  await save();
  const s1 = await signin(), c1 = await certFacts();
  ok('"by itself" saved: The sign-in page says it at once', s1 !== s0 && (auto0 ? /a button/.test(s1) : /tried by itself/.test(s1)), s0.slice(0, 120) + ' => ' + s1.slice(0, 120));
  ok('...and the certificate\'s card', auto0 ? /a button under the form/.test(c1) : /yes - at once/.test(c1), c1.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/02-signin-at-once.png' });
  await p.click('#set-admin_cert_auto');
  await save();
  ok('...back as it was, at once', (await signin()) === s0);
  // Windows: its card's facts
  const krbFacts = () => p.textContent('#krb-host .kv-grid').catch(() => '');
  const k0 = await krbFacts();
  if (await p.$('#set-admin_kerberos_auto')) {
    await p.click('#set-admin_kerberos_auto');
    await save();
    const k1 = await krbFacts();
    ok('Windows "by itself" saved: its card says it at once', k1 !== k0 && /By itself on the sign-in page/.test(k1), k0.slice(0, 80) + ' => ' + k1.slice(0, 80));
    await p.click('#set-admin_kerberos_auto');
    await save();
    ok('...back as it was, at once', (await krbFacts()) === k0);
  } else ok('the switch of Windows "by itself" is there', false);
  ok('all without loading the page again', await p.evaluate(() => window.__notReloaded === 1));
  ok('no page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
