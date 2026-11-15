// ui_ocsp.js - 1.0.279: OCSP on the certificate's card in a real Chromium (the ocsp-ldap-kit): the order of
// the checks as steps, the table "Online status (OCSP)" after a sign-in with alice's certificate of the kit's
// PKI asked her responder and the root's, a row opened (the row clicked stays), Ask again (the button stays,
// each node answers), Clear all asks first, a phone (420 px), Czech. Screenshots into SHOTS.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const D = '/tmp/claude-0/pki-ocsp';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/ocspshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(a) { return execFileSync('python3', [__dirname + '/ui_ocsp_setup.py', a], { encoding: 'utf8' }); }
async function page(b, person, vw, vh) {
  const opts = { ignoreHTTPSErrors: true, viewport: { width: vw || 1400, height: vh || 900 }, deviceScaleFactor: 2 };
  if (person) opts.clientCertificates = [{ origin: 'https://' + HOST + ':8443', certPath: D + '/' + person + '.pem', keyPath: D + '/' + person + '.key' }];
  const ctx = await b.newContext(opts);
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://' + HOST }]);
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  return p;
}
async function admin(p, lang) {
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate((l) => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}), lang || 'en');
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(3500);
  await p.waitForSelector('.ocsp-t', { timeout: 20000 }).catch(() => {});
}
const top = (p, sel) => p.$eval(sel, e => e.getBoundingClientRect().top).catch(() => null);
async function center(p, sel) { await p.$eval(sel, e => e.scrollIntoView({ block: 'center' })); await p.waitForTimeout(400); }

(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  // alice's certificate checked: her responder and the root's asked (not in the directory - refused after)
  let p = await page(b, 'alice');
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go').catch(() => {});
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(2000);
  await p.context().close();
  for (const [vw, vh, tag] of [[1400, 900, ''], [420, 860, 'phone-']]) {
    p = await page(b, null, vw, vh);
    await admin(p);
    const flow = await p.textContent('.rev-flow').catch(() => '');
    ok(vw + ': the order as steps: OCSP, no answer, CRL, no sign-in', /OCSP/.test(flow) && /no answer/.test(flow) && /CRL/.test(flow) && /no sign-in/.test(flow), flow);
    const rows = await p.$$('table.ocsp-t tr.cert-crl-row');
    ok(vw + ': the OCSP table - alice and the issuing authority asked', rows.length >= 2, rows.length);
    const txt = await p.textContent('table.ocsp-t').catch(() => '');
    ok(vw + ': ...good, by name', /alice/.test(txt) && /Corp Issuing CA/.test(txt) && /good/i.test(txt), txt.slice(0, 200));
    await p.$eval('table.ocsp-t', e => e.closest('.krb-tw').previousElementSibling.scrollIntoView({ block: 'start' })).catch(() => {});
    await p.screenshot({ path: SHOTS + '/' + tag + '04-ocsp-table.png' });
    const sel = 'table.ocsp-t tr.cert-crl-row';
    await center(p, sel);
    const t0 = await top(p, sel);
    await p.click(sel + ' td.cert-crl-chev');
    await p.waitForTimeout(700);
    const t1 = await top(p, sel);
    ok(vw + ': a row opened - the row clicked stayed (' + Math.round(t1 - t0) + ' px)', Math.abs(t1 - t0) <= 2, t0 + ' -> ' + t1);
    const more = await p.textContent('table.ocsp-t tr.cert-crl-more').catch(() => '');
    ok(vw + ': ...its details: signed by, serial, responder, each node', /Signed by/.test(more) && /Serial/.test(more) && /Responder/.test(more) && /Each node/.test(more), more.slice(0, 200));
    await p.screenshot({ path: SHOTS + '/' + tag + '05-ocsp-rows-opened.png' });
    if (tag) {
      const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1 ||
        [...document.querySelectorAll('.cert-crl-tw')].some(e => e.scrollWidth > e.clientWidth + 1));
      ok('420: no sideways scroll', !wide);
    }
    await center(p, '#cert-ocsp-fetch');
    const f0 = await top(p, '#cert-ocsp-fetch');
    await p.click('#cert-ocsp-fetch');
    await p.waitForTimeout(700);
    const f1 = await top(p, '#cert-ocsp-fetch');
    ok(vw + ': Ask again pressed - the button stayed (' + Math.round(f1 - f0) + ' px)', Math.abs(f1 - f0) <= 2, f0 + ' -> ' + f1);
    await p.waitForSelector('.cert-crl-said .tag.ok, .cert-crl-said .tag.crit', { timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(2500);
    const said = await p.textContent('.cert-crl-said').catch(() => '');
    ok(vw + ': ...each node answered', /Ask every responder again/.test(said) && /answered/.test(said), said.slice(0, 200));
    await p.screenshot({ path: SHOTS + '/' + tag + '06-ask-again.png' });
    if (!tag) {
      await p.click('#cert-ocsp-clear');
      await p.waitForTimeout(600);
      const m = await p.textContent('#modal').catch(() => '');
      ok('Clear all asks first', /Clear every OCSP answer/.test(m), m.slice(0, 120));
      await p.screenshot({ path: SHOTS + '/07-clear-all-confirm.png' });
      await p.keyboard.press('Escape');
    }
    ok(vw + ': no page errors', p.errs.length === 0, p.errs.join(' | '));
    await p.context().close();
  }
  p = await page(b, null, 1400, 900);
  await admin(p, 'cs');
  const cz = await p.textContent('#cert-host');
  ok('in Czech: the steps and the table\'s words', /žádné přihlášení/.test(cz) && /Stav online \(OCSP\)/.test(cz), cz.slice(0, 160));
  await p.$eval('.rev-flow', e => e.scrollIntoView({ block: 'center' })).catch(() => {});
  await p.screenshot({ path: SHOTS + '/11-order-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.context().close();
  setup('down');
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
