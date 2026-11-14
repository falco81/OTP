// ui_cert.js - 1.0.275: signing in to the administration with a client certificate in a real Chromium,
// which presents the certificate itself (Playwright's clientCertificates for the certificate's port -
// as a browser presents one from a smart card or a YubiKey once its PIN is given). The pages opened as
// https://otp.corpnet.loc/admin/ (a line of /etc/hosts). Off: no button. On: the button goes to the
// port and comes back signed in; refused: back on the sign-in page with why; the second step after it;
// the card in Settings → Accounts and "Try my certificate"; certificate only: no field for a password
// anywhere. Screenshots (for the documentation) into SHOTS.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/certshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
if (!/\botp\.corpnet\.loc\b/.test(fs.readFileSync('/etc/hosts', 'utf8'))) fs.appendFileSync('/etc/hosts', '127.0.0.1 otp.corpnet.loc\n');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(...a) { return execFileSync('python3', [__dirname + '/ui_cert_setup.py', ...a], { encoding: 'utf8' }); }
async function page(b, person, lang, scale) {
  const opts = { ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: scale || 1 };
  if (person) opts.clientCertificates = [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/' + person + '.pem', keyPath: PKI + '/' + person + '.key' }];
  const ctx = await b.newContext(opts);
  if (lang) await ctx.addCookies([{ name: 'otp_lang', value: lang, url: 'https://' + HOST }]);
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  return p;
}
async function signedIn(p) {
  return p.evaluate(async () => { const r = await fetch('?api=whoami'); return r.status === 200 ? (await r.json()).who : null; });
}
async function certIn(p) {
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go');
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(3000);
}

(async () => {
  setup('down');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let p = await page(b, 'falco', 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1200);
  ok('off: no "Sign in with a certificate"', !(await p.$('#cert-go')));
  await p.context().close();

  setup('up');
  p = await page(b, 'falco', 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1200);
  ok('on: "Sign in with a certificate" under the form', !!(await p.$('#cert-go')));
  await p.screenshot({ path: SHOTS + '/1-sign-in-page.png' });
  await certIn(p);
  let who = await signedIn(p);
  ok('pressed: the port asked for the certificate, back on 443 signed in as falco (read only)', who && who.name === 'falco' && who.role === 'readonly' && !/:8443/.test(p.url()), JSON.stringify(who) + ' ' + p.url());
  await p.screenshot({ path: SHOTS + '/2-signed-in.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();

  for (const [person, words, shot] of [['outsider', /none of the groups/, '3-refused.png'], ['falco-rev', /revoked/, ''], ['falco-old', /expired/, '']]) {
    p = await page(b, person, 'en', 2);
    await certIn(p);
    const said = await p.textContent('#krb-said');
    ok(person + ': back on the sign-in page, not signed in, said why (' + said.trim() + ')', !(await signedIn(p)) && words.test(said));
    if (shot) await p.screenshot({ path: SHOTS + '/' + shot });
    await p.context().close();
  }
  p = await page(b, null, 'en', 1);
  await certIn(p);
  const none = await p.textContent('#krb-said');
  ok('no certificate in the browser: said so', /no certificate was sent/.test(none), none);
  await p.context().close();

  setup('mfa');
  p = await page(b, 'nested', 'en', 2);
  await certIn(p);
  const mfa = /second step/i.test(await p.textContent('body'));
  const w2 = await signedIn(p);
  ok('the second step on: asked after the certificate, no role before it', mfa && !(w2 && w2.role), JSON.stringify(w2));
  await p.screenshot({ path: SHOTS + '/4-second-step-after-certificate.png' });
  await p.context().close();
  setup('nomfa');

  // the card, as the local administrator, with nested's certificate in the browser for "Try"
  p = await page(b, 'nested', 'en', 2);
  await p.goto(URL);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(3000);
  await p.waitForSelector('#cert-host table', { timeout: 15000 }).catch(() => {});
  const text = await p.textContent('#cert-card');
  ok('Settings → Accounts: the card - the two authorities, the port, the CRL fetched, the node listening',
     /Corpnet Issuing CA/.test(text) && /Corpnet Root CA/.test(text) && /8443/.test(text) && /issuing\.crl/.test(text) && /listening/.test(text), text.slice(0, 300));
  const [tab] = await Promise.all([p.context().waitForEvent('page'), p.click('#cert-try')]);
  await tab.waitForLoadState(); await tab.waitForTimeout(1500);
  const tried = await tab.textContent('#said').catch(() => '');
  ok('"Try my certificate": nested would sign in as full admin, nothing opened', /would sign in nested@corpnet\.cz as fulladmin/.test(tried), tried);
  await tab.setViewportSize({ width: 900, height: 520 });
  await tab.screenshot({ path: SHOTS + '/7-try-my-certificate.png' });
  await tab.close();
  await p.setViewportSize({ width: 1400, height: 2700 });
  await p.evaluate(() => document.querySelectorAll('body *').forEach(e => {
    const pos = getComputedStyle(e).position;
    if (pos === 'sticky' || pos === 'fixed') e.style.setProperty('position', 'static', 'important');
  }));
  await p.waitForTimeout(500);
  const card = await p.$('#cert-card');
  if (card) { await card.scrollIntoViewIfNeeded(); await card.screenshot({ path: SHOTS + '/5-settings-card.png' }); }
  const sw = await p.$('#sect-people');
  if (sw) await sw.screenshot({ path: SHOTS + '/6-settings-switches.png' });
  ok('no page errors (settings)', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();

  // certificate only - switched on from a certificate's sign-in
  p = await page(b, 'nested', 'en', 2);
  await certIn(p);
  const saved = await p.evaluate(async () => (await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({settings: {admin_password_off: 1}})})).status);
  ok('nested (full admin, signed in with a certificate) switches the password off', saved === 200, saved);
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(2500);
  await p.click('#me-btn'); await p.waitForTimeout(1500);
  ok('certificate only: Your account has no "A new password"', !(await p.$('#me-pw-old')));
  await p.screenshot({ path: SHOTS + '/9-your-account-certificate-only.png' });
  await p.keyboard.press('Escape'); await p.waitForTimeout(500);
  const pwIn = await p.$$eval('input[type=password], input.masked', a => a.filter(x => x.offsetParent).length);
  ok('certificate only: no field for a password on the page', pwIn === 0, pwIn);
  await p.context().close();
  p = await page(b, 'falco', 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1200);
  ok('certificate only: the sign-in page has no name and password, only the certificate',
     await p.$eval('#signin-form', f => f.hidden) && /with a certificate only/.test(await p.textContent('body')) && !(await p.$('#krb-go')));
  await p.screenshot({ path: SHOTS + '/8-sign-in-certificate-only.png' });
  await certIn(p);
  who = await signedIn(p);
  ok('... and the certificate signs in', who && who.name === 'falco', JSON.stringify(who));
  await p.context().close();
  execFileSync('otp', ['--set', 'admin_password_off=0']);
  await new Promise(r => setTimeout(r, 4000));

  // in Czech
  p = await page(b, 'falco', 'cs', 2);
  await p.goto(URL); await p.waitForTimeout(1200);
  const cz = await p.textContent('#cert-go');
  ok('in Czech: "' + cz.trim() + '"', /certifik/i.test(cz) && !/Sign in/.test(cz));
  await p.screenshot({ path: SHOTS + '/10-sign-in-page-cs.png' });
  await p.context().close();
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); });
