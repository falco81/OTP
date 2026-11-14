// ui_variants.js - 1.0.277: the sign-in page with a password, Windows and a certificate, in a real Chromium
// that has a Kerberos ticket (or none) and a client certificate (or none). What is tried by itself, in which
// order, never twice; the three cards of Settings → Accounts. Screenshots into SHOTS.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const KDC = process.env.KDC_DIR || '/tmp/claude-0/kdc2';
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/varshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
if (!/\botp\.corpnet\.loc\b/.test(fs.readFileSync('/etc/hosts', 'utf8'))) fs.appendFileSync('/etc/hosts', '127.0.0.1 otp.corpnet.loc\n');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(...a) { return execFileSync('python3', [__dirname + '/ui_variants_setup.py', ...a], { encoding: 'utf8' }); }
const browsers = {};
async function browser(ticket) {           /* ticket: a person of the test realm, or 'none' (outside the domain) */
  if (browsers[ticket]) return browsers[ticket];
  const cc = ticket === 'none' ? KDC + '/nobody-at-all.cc' : KDC + '/' + ticket + '.cc';
  browsers[ticket] = await chromium.launch({
    args: ['--auth-server-allowlist=' + HOST, '--disable-auth-negotiate-cname-lookup', '--no-proxy-server'],
    env: Object.assign({}, process.env, { KRB5_CONFIG: KDC + '/krb5.conf', KRB5CCNAME: 'FILE:' + cc }) });
  return browsers[ticket];
}
async function page(ticket, cert, scale) {
  const b = await browser(ticket);
  const opts = { ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: scale || 1 };
  if (cert) opts.clientCertificates = [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/' + cert + '.pem', keyPath: PKI + '/' + cert + '.key' }];
  const ctx = await b.newContext(opts);
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://' + HOST }]);
  const p = await ctx.newPage();
  p.errs = []; p.on('pageerror', e => p.errs.push(String(e)));
  p.toPort = 0; p.on('request', r => { if (/:8443\//.test(r.url())) p.toPort++; });
  p.krbAsks = 0; p.on('request', r => { if (/api=kerberos-login/.test(r.url())) p.krbAsks++; });
  return p;
}
async function who(p) {
  return p.evaluate(async () => { const r = await fetch('?api=whoami'); return r.status === 200 ? (await r.json()).who : null; });
}
async function open(p) { await p.goto(URL); await p.waitForTimeout(5000); }
const name = w => (w && w.name) || '-';

(async () => {
  setup('down');
  setup('up');
  setup('set', 'admin_kerberos=1', 'admin_kerberos_auto=0', 'admin_cert=1', 'admin_cert_auto=0', 'admin_password_off=0');
  // 1. both buttons, nothing by itself
  let p = await page('falco', 'nested', 2);
  await open(p);
  ok('buttons: the form, "Sign in with Windows" and "Sign in with a certificate", nothing tried by itself',
     !!(await p.$('#krb-go')) && !!(await p.$('#cert-go')) && !(await p.$eval('#signin-form', f => f.hidden)) && !(await who(p)) && p.toPort === 0, p.toPort);
  await p.screenshot({ path: SHOTS + '/04-password-windows-certificate.png' });
  await p.context().close();

  // 2. the certificate by itself, Windows a button
  setup('set', 'admin_cert_auto=1');
  p = await page('none', 'falco', 2);
  await open(p);
  let w = await who(p);
  ok('the certificate by itself: the page went to the port at once and came back signed in (falco)', name(w) === 'falco' && p.toPort > 0, JSON.stringify(w));
  await p.context().close();
  p = await page('none', null, 2);
  await open(p);
  const said = await p.textContent('#krb-said');
  ok('...no certificate in the browser: back on the page, said why, the form there', !(await who(p)) && /no certificate was sent/.test(said)
     && !(await p.$eval('#signin-form', f => f.hidden)), said);
  const n0 = p.toPort;
  await open(p);
  ok('...and not tried by itself again in that tab', p.toPort === n0 && !(await who(p)), p.toPort + ' vs ' + n0);
  await p.context().close();

  // 2b. Windows by itself: a browser with no ticket remembered for 30 days
  setup('set', 'admin_cert_auto=0', 'admin_kerberos_auto=1');
  p = await page('none', null, 2);
  await open(p);
  const mark = await p.evaluate(() => localStorage.getItem('otp.krb.none'));
  ok('Windows by itself, no ticket: quiet, the form there, the browser marked', !(await who(p)) && p.krbAsks === 1 && !!mark
     && !(await p.$eval('#signin-form', f => f.hidden)) && !(await p.textContent('#krb-said')).trim(), p.krbAsks + ' ' + mark);
  let p2 = await p.context().newPage();
  p2.krbAsks = 0; p2.on('request', r => { if (/api=kerberos-login/.test(r.url())) p2.krbAsks++; });
  await p2.goto(URL); await p2.waitForTimeout(4000);
  ok('...a new tab of that browser: Windows not tried by itself (30 days)', p2.krbAsks === 0 && !!(await p2.$('#krb-go')), p2.krbAsks);
  await p2.click('#krb-go'); await p2.waitForTimeout(2500);
  ok('...its button still asks (and says there is no ticket)', p2.krbAsks === 1 && /no Kerberos ticket/.test(await p2.textContent('#krb-said')));
  await p.context().close();
  p = await page('falco', null, 2);
  await p.context().addInitScript(() => {
    if (!sessionStorage.getItem('seeded')) { localStorage.setItem('otp.krb.none', String(Date.now())); sessionStorage.setItem('seeded', '1'); }
  });
  await open(p);
  ok('...a browser marked within 30 days: not tried by itself even with a ticket', p.krbAsks === 0 && !(await who(p)), p.krbAsks);
  await p.click('#krb-go'); await p.waitForTimeout(4000);
  w = await who(p);
  ok('...the button signs in with Windows, and the mark is gone', name(w) === 'falco' && !(await p.evaluate(() => localStorage.getItem('otp.krb.none'))), JSON.stringify(w));
  await p.context().close();
  p = await page('falco', null, 2);
  await open(p);
  ok('a computer in the domain: signed in silently as before, never marked', name(await who(p)) === 'falco'
     && !(await p.evaluate(() => localStorage.getItem('otp.krb.none'))));
  await p.context().close();

  // 3. both by itself: Windows first
  setup('set', 'admin_kerberos_auto=1', 'admin_cert_auto=1');
  p = await page('falco', 'nested', 2);
  await open(p);
  w = await who(p);
  ok('both by itself, a ticket: Windows first, silently (falco - not the certificate\'s nested), the port not asked', name(w) === 'falco' && p.toPort === 0, JSON.stringify(w) + ' port ' + p.toPort);
  // Sign out: nothing again
  await p.click('#signout').catch(() => {}); await p.waitForTimeout(3000);
  const n1 = p.toPort;
  await open(p);
  ok('...after Sign out nothing is tried by itself in that tab', !(await who(p)) && p.toPort === n1, JSON.stringify(await who(p)));
  await p.context().close();
  p = await page('none', 'nested', 2);
  await open(p);
  w = await who(p);
  ok('both by itself, no ticket (outside the domain): then the certificate (nested)', name(w) === 'nested' && p.toPort > 0, JSON.stringify(w));
  await p.context().close();
  p = await page('outsider', 'nested', 2);
  await open(p);
  const said2 = await p.textContent('#krb-said');
  ok('both by itself, a ticket Windows refuses: said why, the certificate not tried', !(await who(p)) && p.toPort === 0 && said2.trim().length > 0, said2 + ' port ' + p.toPort);
  await p.screenshot({ path: SHOTS + '/08-refused-windows.png' });
  await p.context().close();

  // 4. no password at all, a certificate alone: tried by itself whatever its own switch
  setup('set', 'admin_kerberos=0', 'admin_kerberos_auto=0', 'admin_cert_auto=0', 'admin_password_off=1');
  p = await page('none', 'falco', 2);
  // the page as a tab that tried the certificate already sees it (otherwise it is gone to the port at once)
  await p.addInitScript(() => { try { if (location.port !== '8443' && !sessionStorage.getItem('t.look')) { sessionStorage.setItem('t.look', '1'); sessionStorage.setItem('otp.cert.tried', '1'); } } catch (e) {} });
  await p.goto(URL); await p.waitForTimeout(1200);
  const formHidden = await p.$eval('#signin-form', f => f.hidden).catch(() => null);
  await p.context().close();
  p = await page('none', 'falco', 2);
  await p.goto(URL); await p.waitForTimeout(5000);
  w = await who(p);
  ok('no password at all, the certificate alone: no form, the certificate tried by itself, signed in', formHidden === true && name(w) === 'falco', JSON.stringify(w));
  await p.context().close();
  setup('set', 'admin_password_off=0', 'admin_kerberos=1', 'admin_cert_auto=1', 'admin_kerberos_auto=1');

  // 5. the three cards
  p = await page('none', null, 2);
  await p.goto(URL); await p.waitForTimeout(800);
  await p.evaluate(() => { try { sessionStorage.setItem('otp.krb.out', '1'); } catch (e) {} });
  await p.goto(URL); await p.waitForTimeout(1500);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(3500);
  const k = await p.$$eval('#sect-kerberos .set-item[data-key]', a => a.map(x => x.dataset.key));
  const c = await p.$$eval('#sect-certlogin .set-item[data-key]', a => a.map(x => x.dataset.key));
  const s = await p.$$eval('#sect-signin .set-item[data-key]', a => a.map(x => x.dataset.key));
  ok('Windows\' card has its switches', k.join() === 'admin_kerberos,admin_kerberos_auto,admin_kerberos_realm', k.join());
  ok('the certificate\'s card has its switches, by itself among them', c.join() === 'admin_cert,admin_cert_auto,admin_cert_port,admin_cert_map,admin_cert_crl', c.join());
  ok('the sign-in page\'s card: No password at all', s.join() === 'admin_password_off', s.join());
  const facts = await p.textContent('#signin-host');
  ok('the sign-in page\'s card says the order: Windows silently, the certificate without a ticket', /Windows silently; the certificate when this computer has no Windows ticket/.test(facts), facts.slice(0, 300));
  ok('the cards\' chips (Windows: a keytab is in; the certificate: authorities, nginx)', /A keytab is in/.test(await p.textContent('#krb-host')) && /Authorities put in/.test(await p.textContent('#cert-host')));
  await p.setViewportSize({ width: 1400, height: 3200 });
  for (const [id, f] of [['#krb-card', '14-settings-windows-card.png'], ['#cert-card', '15-settings-certificate-card.png'], ['#signin-card', '13-settings-the-sign-in-page.png']]) {
    const e = await p.$(id); if (e) await e.screenshot({ path: SHOTS + '/' + f });
  }
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
  for (const b of Object.values(browsers)) await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
