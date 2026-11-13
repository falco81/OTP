// ui_krb.js - 1.0.274: signing in to the administration pages with Windows (Kerberos) in a real
// Chromium that does SPNEGO itself (its own GSS-API, the ticket of falco@CORPNET.LOC from the test
// realm, tests/krb/kdc.sh), the pages opened as https://otp.corpnet.loc/admin/ (mapped to this
// machine by a line of /etc/hosts - a browser asks for HTTP/<the name it resolved>). Off: no button. On: the button signs in; on by itself: the page signs in when it opens,
// and never again in that tab after signing out; the second step on: asked after Kerberos. The
// card in Settings → Accounts: the keytab, the names, each node, "Try my browser's ticket".
// Screenshots (for the documentation) into SHOTS.
//   node ui_krb.js            (the setup: python3 ui_krb_setup.py up|down)
const { chromium } = require('playwright');
// The pages are this machine's: no proxy of the environment (it would tunnel them away).
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const KDC = process.env.KDC_DIR || '/tmp/claude-0/kdc2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/krbshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
if (!/\botp\.corpnet\.loc\b/.test(fs.readFileSync('/etc/hosts', 'utf8'))) fs.appendFileSync('/etc/hosts', '127.0.0.1 otp.corpnet.loc\n');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(...a) { return execFileSync('python3', [__dirname + '/ui_krb_setup.py', ...a], { encoding: 'utf8' }); }

async function browser(person) {
  return chromium.launch({
    args: ['--auth-server-allowlist=' + HOST, 
           '--disable-auth-negotiate-cname-lookup', '--no-proxy-server'],
    env: Object.assign({}, process.env, { KRB5_CONFIG: KDC + '/krb5.conf', KRB5CCNAME: 'FILE:' + KDC + '/' + person + '.cc' }),
  });
}
async function page(b, lang, scale) {
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: scale || 1 });
  if (lang) await ctx.addCookies([{ name: 'otp_lang', value: lang, url: 'https://' + HOST }]);
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  return p;
}
async function signedIn(p) {
  return p.evaluate(async () => { const r = await fetch('?api=whoami'); return r.status === 200 ? (await r.json()).who : null; });
}
async function adminLogin(p) {
  await p.goto(URL);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}

(async () => {
  try { execFileSync('otp', ['--set', 'admin_kerberos=0', '--set', 'admin_password_off=0', '--set', 'admin_2fa=0']); } catch (e) {}
  await new Promise(r => setTimeout(r, 4000));
  setup('up', 'off');
  let b = await browser('falco');
  let p = await page(b, 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1500);
  ok('off: no "Sign in with Windows"', !(await p.$('#krb-go')));

  setup('on', 'button');
  await p.goto(URL); await p.waitForTimeout(1500);
  ok('on: "Sign in with Windows" under the form', !!(await p.$('#krb-go')));
  await p.screenshot({ path: SHOTS + '/1-sign-in-page.png' });
  ok('on, not by itself: not signed in until it is pressed', !(await signedIn(p)));
  await p.click('#krb-go');
  await p.waitForURL(/admin\//, { timeout: 15000 }).catch(() => {});
  await p.waitForTimeout(3500);
  let who = await signedIn(p);
  ok('pressed: signed in as falco (read only), no password typed', who && who.name === 'falco' && who.role === 'readonly', JSON.stringify(who));
  await p.screenshot({ path: SHOTS + '/2-signed-in.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  // signed out: not signed in again by itself in that tab
  setup('on', 'auto');
  await p.click('#signout'); await p.waitForTimeout(2500);
  ok('signed out: the sign-in page stays (not signed in again by itself)', !(await signedIn(p)) && !!(await p.$('#in-name')));
  await p.context().close();

  // by itself when the page opens
  p = await page(b, 'en', 1);
  await p.goto(URL); await p.waitForTimeout(5000);
  who = await signedIn(p);
  ok('by itself: a new tab opens signed in as falco', who && who.name === 'falco', JSON.stringify(who));
  await p.context().close();
  await b.close();

  // somebody the directory gives no role: the form, and why
  b = await browser('outsider');
  p = await page(b, 'en', 2);
  setup('on', 'button');
  await p.goto(URL); await p.waitForTimeout(1500);
  await p.click('#krb-go'); await p.waitForTimeout(3000);
  const said = await p.textContent('#krb-said');
  ok('outsider: not signed in, said why (' + said + ')', !(await signedIn(p)) && /none of the groups/.test(said));
  await p.screenshot({ path: SHOTS + '/3-refused.png' });
  await p.context().close();
  await b.close();

  // only Windows: no password on the sign-in page (switched on from a Windows sign-in of a full admin)
  b = await browser('nested');
  p = await page(b, 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1500);
  await p.click('#krb-go'); await p.waitForTimeout(3500);
  const offSaved = await p.evaluate(async () => (await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({settings: {admin_password_off: 1}})})).status);
  ok('nested (full admin, signed in with Windows) switches the password off', offSaved === 200, offSaved);
  await p.context().close();
  p = await page(b, 'en', 2);
  // as after signing out in this tab: the page does not sign in by itself, the picture shows it as it is
  await p.context().addInitScript(() => { try { sessionStorage.setItem('otp.krb.out', '1'); } catch (e) {} });
  await p.goto(URL); await p.waitForTimeout(1500);
  ok('only Windows: no name and password on the sign-in page', await p.$eval('#signin-form', f => f.hidden)
     && /with Windows only/.test(await p.textContent('body')));
  await p.screenshot({ path: SHOTS + '/8-sign-in-windows-only.png' });
  await p.click('#krb-go'); await p.waitForTimeout(3500);
  who = await signedIn(p);
  ok('... and Windows signs in', who && who.name === 'nested', JSON.stringify(who));
  // ...and no field for a password anywhere inside either
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(3000);
  await p.click('#me-btn'); await p.waitForTimeout(1500);
  ok('only Windows: Your account has no "A new password"', !(await p.$('#me-pw-old')) && !(await p.$('#me-pw-new')));
  await p.screenshot({ path: SHOTS + '/9-your-account-windows-only.png' });
  await p.keyboard.press('Escape'); await p.waitForTimeout(600);
  await p.click('#us-add'); await p.waitForTimeout(800);
  const made = await p.textContent('#modal-body');
  ok('only Windows: "Make an account" offers no password', !(await p.$('#modal-body input[type=password], #modal-body input.masked'))
     && /Windows only/.test(made), made);
  await p.keyboard.press('Escape'); await p.waitForTimeout(600);
  const pwInputs = await p.$$eval('input[type=password], input.masked', a => a.filter(x => x.offsetParent).length);
  ok('only Windows: no field for a password shown on the page', pwInputs === 0, pwInputs);
  const st = await p.evaluate(async () => (await fetch('?api=password', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({old: 'x', 'new': 'yyyyyyyyyy'})})).status);
  ok('only Windows: a change of a password refused by the server too', st === 400 || st === 403, st);
  await p.context().close();
  await b.close();
  execFileSync('otp', ['--set', 'admin_password_off=0']);
  await new Promise(r => setTimeout(r, 4000));

  // the second step after Kerberos
  setup('mfa');
  b = await browser('nested');
  p = await page(b, 'en', 2);
  await p.goto(URL); await p.waitForTimeout(1500);
  await p.click('#krb-go'); await p.waitForTimeout(3500);
  const mfa = /Set up the second step|second step/i.test(await p.textContent('body'));
  const w2 = await signedIn(p);
  ok('the second step on: asked after Kerberos, no role before it', mfa && !(w2 && w2.role), JSON.stringify(w2));
  await p.screenshot({ path: SHOTS + '/4-second-step-after-kerberos.png' });
  await p.context().close();
  await b.close();
  setup('nomfa');

  // the card, as the local administrator, in a browser that has falco's ticket
  b = await browser('falco');
  p = await page(b, 'en', 2);
  await adminLogin(p);
  await p.goto(URL + '#settings/people'); await p.waitForTimeout(3000);
  await p.waitForSelector('#krb-host table', { timeout: 15000 }).catch(() => {});
  const card = await p.$('#krb-card');
  ok('Settings → Accounts: the card of Kerberos', !!card);
  const text = card ? await card.textContent() : '';
  ok('... the keytab\'s principals, never a key', /HTTP\/otp\.corpnet\.loc@CORPNET\.LOC/.test(text) && /aes256-cts-hmac-sha1-96/.test(text));
  ok('... the realm from the directory, NTLM never taken', /CORPNET\.LOC/.test(text) && /never taken/.test(text));
  ok('... each node: the keytab written, the library there', /written/.test(text) && /there/.test(text));
  ok('... the commands for AD (setspn, ktpass)', /setspn -S HTTP\//.test(text) && /ktpass -princ HTTP\//.test(text));
  await p.click('#krb-try'); await p.waitForTimeout(3000);
  const tried = await p.textContent('#krb-host .krb-try-out');
  ok('"Try my browser\'s ticket": falco would sign in, read only', /would sign in/.test(tried) && /falco@CORPNET\.LOC/.test(tried), tried);
  // The whole card in one picture: a tall window, the header not held over it.
  await p.setViewportSize({ width: 1400, height: 2600 });
  await p.evaluate(() => document.querySelectorAll('body *').forEach(e => {
    const pos = getComputedStyle(e).position;
    if (pos === 'sticky' || pos === 'fixed') e.style.setProperty('position', 'static', 'important');
  }));
  await p.waitForTimeout(600);
  const sect = await p.$('#krb-card');
  if (sect) { await sect.scrollIntoViewIfNeeded(); await sect.screenshot({ path: SHOTS + '/5-settings-card.png' }); }
  const sw = await p.$('#sect-people');
  if (sw) await sw.screenshot({ path: SHOTS + '/6-settings-switches.png' });
  ok('no page errors (settings)', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();

  // in Czech
  setup('on', 'button');
  p = await page(b, 'cs', 2);
  await p.goto(URL); await p.waitForTimeout(1500);
  const cz = await p.textContent('#krb-go');
  ok('in Czech: "' + cz.trim() + '"', /Windows/.test(cz) && !/Sign in/.test(cz));
  await p.screenshot({ path: SHOTS + '/7-sign-in-page-cs.png' });
  await p.context().close();
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); });
