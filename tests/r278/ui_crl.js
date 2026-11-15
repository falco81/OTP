// ui_crl.js - 1.0.278: the CRLs of the sign-in with a certificate in a real Chromium (the crl-revocation-kit):
// the table after a sign-in with a certificate fetched them, a row opened (the clicked row must not move),
// Fetch now (each node's answer in the box drawn at its final shape - the clicked button must not move),
// Clear all asks first, a phone (420 px: no sideways scroll), Czech. Screenshots into SHOTS.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/crlshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(...a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', ...a], { encoding: 'utf8' }); }
async function page(b, person, lang, vw, vh) {
  const opts = { ignoreHTTPSErrors: true, viewport: { width: vw || 1400, height: vh || 900 }, deviceScaleFactor: 2 };
  if (person) opts.clientCertificates = [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/' + person + '.pem', keyPath: PKI + '/' + person + '.key' }];
  const ctx = await b.newContext(opts);
  await ctx.addCookies([{ name: 'otp_lang', value: lang || 'en', url: 'https://' + HOST }]);
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  return p;
}
async function admin(p) {
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  // the pages in English, whatever the account was left in (its own language wins over the cookie)
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(3000);
  await p.waitForSelector('.cert-crl-t', { timeout: 20000 }).catch(() => {});
}
const top = (p, sel) => p.$eval(sel, e => e.getBoundingClientRect().top).catch(() => null);
async function center(p, sel) { await p.$eval(sel, e => e.scrollIntoView({ block: 'center' })); await p.waitForTimeout(400); }

(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  // a sign-in with a certificate fetches its CRLs
  let p = await page(b, 'falco');
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go').catch(() => {});
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(2500);
  await p.context().close();
  for (const [vw, vh, tag] of [[1400, 900, ''], [420, 860, 'phone-']]) {
    p = await page(b, null, 'en', vw, vh);
    await admin(p);
    const rows = await p.$$('tr.cert-crl-row');
    ok(vw + ': the table - a row for each CRL', rows.length >= 1, rows.length);
    const txt = await p.textContent('#cert-host');
    ok(vw + ': the pill and the address', /good|within a day/.test(txt) && /\.crl/.test(txt));
    await p.$eval('#cert-host .cert-crl-head', e => e.scrollIntoView({ block: 'start' })).catch(() => {});
    await p.waitForTimeout(300);
    await p.screenshot({ path: SHOTS + '/' + tag + '01-table.png' });
    // open a row: it does not move
    const sel = 'tr.cert-crl-row';
    await center(p, sel);
    const t0 = await top(p, sel);
    await p.click(sel + ' td.cert-crl-chev');
    await p.waitForTimeout(600);
    const t1 = await top(p, sel);
    ok(vw + ': a row opened - the row clicked stayed where it was (' + Math.round(t1 - t0) + ' px)', Math.abs(t1 - t0) <= 2, t0 + ' -> ' + t1);
    const more = await p.textContent('tr.cert-crl-more').catch(() => '');
    ok(vw + ': ...its details: number, signature, each node', /CRL number/.test(more) && /checked/.test(more) && /Each node/.test(more), more.slice(0, 200));
    await p.screenshot({ path: SHOTS + '/' + tag + '02-row-open.png' });
    if (tag) {
      const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1 ||
        [...document.querySelectorAll('.cert-crl-tw')].some(e => e.scrollWidth > e.clientWidth + 1));
      ok('420: no sideways scroll', !wide);
    }
    // Fetch now: the button does not move, each node answers
    await center(p, '#cert-crl-fetch');
    const f0 = await top(p, '#cert-crl-fetch');
    await p.click('#cert-crl-fetch');
    await p.waitForTimeout(700);
    const f1 = await top(p, '#cert-crl-fetch');
    ok(vw + ': Fetch now pressed, the box of answers above - the button stayed where it was (' + Math.round(f1 - f0) + ' px)', Math.abs(f1 - f0) <= 2, f0 + ' -> ' + f1);
    await p.waitForSelector('.cert-crl-said .tag.ok, .cert-crl-said .tag.crit', { timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(2500);
    const f2 = await top(p, '#cert-crl-fetch');
    ok(vw + ': ...the answers come - still where it was (' + Math.round(f2 - f0) + ' px)', Math.abs(f2 - f0) <= 2, f0 + ' -> ' + f2);
    const said = await p.textContent('.cert-crl-said').catch(() => '');
    ok(vw + ': ...each node said: fetched', /fetched/.test(said), said.slice(0, 200));
    await p.screenshot({ path: SHOTS + '/' + tag + '03-fetch-now.png' });
    if (!tag) {
      await p.click('#cert-crl-clear');
      await p.waitForTimeout(600);
      const m = await p.textContent('#modal').catch(() => '');
      ok('Clear all asks first', /Clear every CRL/.test(m), m.slice(0, 120));
      await p.screenshot({ path: SHOTS + '/04-clear-all-confirm.png' });
      await p.keyboard.press('Escape');
    }
    ok(vw + ': no page errors', p.errs.length === 0, p.errs.join(' | '));
    await p.context().close();
  }
  p = await page(b, null, 'cs', 1400, 900);
  await admin(p);
  // the language of the pages is the account's own: Czech for this look, English again after
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}));
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(4000);
  await p.waitForSelector('.cert-crl-t', { timeout: 20000 }).catch(() => {});
  await p.click('tr.cert-crl-row td.cert-crl-chev').catch(() => {});
  await p.waitForTimeout(600);
  await p.$eval('#cert-host .cert-crl-head', e => e.scrollIntoView({ block: 'start' })).catch(() => {});
  const cz = await p.textContent('#cert-host');
  ok('in Czech: the table\'s words', /Seznamy odvolaných certifikátů/.test(cz) && /Číslo CRL/.test(cz), cz.slice(0, 160));
  await p.screenshot({ path: SHOTS + '/07-table-expanded-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.context().close();
  setup('down');
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
