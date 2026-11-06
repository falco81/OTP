// ui_pk_me.js - 1.0.257: Your account - the passkeys of the account signed in. Set up as the
// second step, then: listed (name, for, added, last used); named with the pencil (Enter saves,
// Escape leaves); another device's passkey added; either one signs in; one taken away; the last one
// cannot be; hidden while the second step is off and for an account whose second step is the app.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const BASE = 'https://otp.test/admin/';
const PW = 'Pk-Me-257-pass!';
const SHOTS = '/tmp/claude-0/pkme';
fs.mkdirSync(SHOTS, { recursive: true });
async function post(p, what, body) {
  return p.evaluate(async ([w, b]) => {
    const r = await fetch('?api=' + w, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
    let d = {}; try { d = await r.json(); } catch (e) {}
    return {st: r.status, d};
  }, [what, body]);
}
async function get(p, what) {
  return p.evaluate(async (w) => { const r = await fetch('?api=' + w); let d = {}; try { d = await r.json(); } catch (e) {} return {st: r.status, d}; }, what);
}
async function signIn(p, name, pw) {
  await p.goto(BASE);
  await p.fill('input[autocomplete=username]', name);
  await p.fill('input[type=password]', pw);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}
async function device(ctx, p) {
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('WebAuthn.enable');
  const a = await cdp.send('WebAuthn.addVirtualAuthenticator', {options: {protocol: 'ctap2', transport: 'internal',
    hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true}});
  return {cdp, id: a.authenticatorId};
}
async function newCtx(b, lang = 'en') {
  const c = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  await c.addCookies([{name: 'otp_lang', value: lang, domain: 'otp.test', path: '/'}]);
  return c;
}
async function openMe(p) {
  await p.evaluate(() => showMe());
  await p.waitForTimeout(1500);
}
(async () => {
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY || process.env.https_proxy || 'direct://', bypass: 'otp.test,localhost,127.0.0.1' },
    args: ['--host-resolver-rules=MAP otp.test 127.0.0.1', '--ignore-certificate-errors'] });
  const actx = await newCtx(b);
  const a = await actx.newPage();
  await signIn(a, 'admin', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await post(a, 'users', {action: 'delete', name: 'pkme'});
  ok('the account made', (await post(a, 'users', {action: 'add', name: 'pkme', role: 'tokenadmin', password: PW, must_change: 0})).st === 200);
  ok('the second step on, by a passkey', (await post(a, 'settings', {settings: {admin_2fa: 1, admin_2fa_passkey: 1}})).st === 200);
  await a.waitForTimeout(2500);
  const errs = [];
  let ctx = await newCtx(b);
  let p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  let d1 = await device(ctx, p);
  await signIn(p, 'pkme', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  await p.click('.mfa-ways .mfa-way:has-text("passkey")');
  await p.click('text=Set up the passkey of this device');
  await p.waitForTimeout(4000);
  ok('set up and signed in', ((await get(p, 'whoami')).d.who || {}).role === 'tokenadmin');

  await openMe(p);
  const rows = await p.$$eval('.me-pk-t tbody tr', x => x.map(r => Array.from(r.cells).map(c => c.textContent.trim())));
  ok('Your account: the passkey listed - name, for, added, last used', rows.length === 1 && /otp\.test/.test(rows[0][1]) && rows[0][2] && rows[0][3] !== '', JSON.stringify(rows));
  ok('...the last one cannot be taken away', await p.$eval('.me-pk-t tbody tr .iconbtn:last-child', e => e.disabled));
  await p.screenshot({ path: SHOTS + '/one.png' });
  // named with the pencil
  await p.click('.me-pk-t tbody tr .iconbtn:first-child');
  await p.waitForTimeout(200);
  const sel = await p.evaluate(() => { const i = document.querySelector('.me-pk-name input'); return i && document.activeElement === i && i.selectionStart === 0 && i.selectionEnd === i.value.length; });
  ok('the pencil: the name in a box, focused, all of it selected', sel);
  await p.screenshot({ path: SHOTS + '/edit.png' });
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  ok('...Escape leaves it as it was, the window stays open', !(await p.$('.me-pk-name input')) && !!(await p.$('.me-pk-t')));
  await p.click('.me-pk-t tbody tr .iconbtn:first-child');
  await p.fill('.me-pk-name input', 'My iPad');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(1500);
  ok('...Enter saves the name', (await p.$eval('.me-pk-t tbody tr td', e => e.textContent.trim())) === 'My iPad');
  const l1 = (await get(p, 'passkeys')).d;
  ok('...kept by the server', (l1.keys || [])[0] && l1.keys[0].name === 'My iPad', JSON.stringify(l1));

  // another device's passkey added
  await d1.cdp.send('WebAuthn.removeVirtualAuthenticator', {authenticatorId: d1.id});
  const d2 = await device(ctx, p);
  await p.click('text=Add a passkey of this device');
  await p.waitForTimeout(4000);
  const rows2 = await p.$$eval('.me-pk-t tbody tr', x => x.length);
  ok('another device\'s passkey added: two listed', rows2 === 2, rows2);
  ok('...either may now be taken away', (await p.$$eval('.me-pk-t tbody tr .iconbtn:last-child', x => x.every(e => !e.disabled))));
  await p.screenshot({ path: SHOTS + '/two.png' });
  // signed in with the new one
  await post(p, 'logout', {});
  await signIn(p, 'pkme', PW);
  await p.waitForSelector('text=Use the passkey', { timeout: 10000 }).catch(() => {});
  await p.click('text=Use the passkey');
  await p.waitForTimeout(4000);
  ok('the new device signs in', ((await get(p, 'whoami')).d.who || {}).role === 'tokenadmin');
  // the first one taken away
  await openMe(p);
  await p.click('.me-pk-t tbody tr:has-text("My iPad") .iconbtn:last-child');
  await p.waitForTimeout(500);
  await p.click('.modal button:has-text("Take it away")');
  await p.waitForTimeout(1500);
  const l2 = (await get(p, 'passkeys')).d;
  ok('one taken away: one left, the other device\'s', (l2.keys || []).length === 1 && l2.keys[0].name !== 'My iPad', JSON.stringify(l2.keys));
  const last = await post(p, 'passkeys', {action: 'delete', id: l2.keys[0].id});
  ok('the last one refused by the server too, said why', last.st === 409 && /reset/.test(last.d.error || ''), JSON.stringify(last));
  await d2.cdp.send('WebAuthn.removeVirtualAuthenticator', {authenticatorId: d2.id});
  // Czech
  const cctx = await newCtx(b, 'cs');
  const cp = await cctx.newPage();
  await cp.goto(BASE);
  await cctx.addCookies(await ctx.cookies());
  await cctx.addCookies([{name: 'otp_lang', value: 'cs', domain: 'otp.test', path: '/'}]);
  await cp.goto(BASE);
  await cp.waitForTimeout(2000);
  await openMe(cp);
  const cz = await cp.$eval('.me-pk', e => e.textContent).catch(() => '');
  ok('Czech: the passkeys in Czech', /Naposledy použito/.test(cz) && /Přidat passkey/.test(cz), cz.slice(0, 200));
  await cp.screenshot({ path: SHOTS + '/cs.png' });
  await cctx.close();
  // the second step off: not shown
  await post(a, 'settings', {settings: {admin_2fa: 0, admin_2fa_passkey: 0}});
  await a.waitForTimeout(2500);
  await p.reload();
  await p.waitForTimeout(2000);
  await openMe(p);
  ok('the second step off: no passkeys in Your account', !(await p.$('.me-pk-t')) && (await p.$eval('.me-pk', e => e.hidden).catch(() => true)));
  // the admin (no passkey): not shown
  await openMe(a);
  ok('an account whose second step is not a passkey: not shown', !(await a.$('.me-pk-t')));
  await ctx.close();
  await post(a, 'users', {action: 'delete', name: 'pkme'});
  ok('no errors on the pages', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
