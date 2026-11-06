// ui_passkey.js - 1.0.254: a passkey (Face ID, Touch ID, Windows Hello) as the administration's second
// step, in Chromium with its virtual authenticator, on the pages opened by a name (otp.test). Off by
// default: not offered. On: offered beside the app at the first sign-in; set up with the face; the next
// sign-in: the password, then the passkey; another device's passkey refused; by an address: not offered,
// said why; reset by a full administrator: set up again; the password is always asked first.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const BASE = 'https://otp.test/admin/';
const PW = 'Pk-User-254-pass!';
const SHOTS = '/tmp/claude-0/pkui';
fs.mkdirSync(SHOTS, { recursive: true });
async function post(p, what, body) {
  return p.evaluate(async ([w, b]) => {
    const r = await fetch('?api=' + w, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
    let d = {}; try { d = await r.json(); } catch (e) {}
    return {st: r.status, d};
  }, [what, body]);
}
async function signIn(p, name, pw) {
  await p.goto(BASE);
  await p.fill('input[autocomplete=username]', name);
  await p.fill('input[type=password]', pw);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}
async function device(ctx, p, verified = true) {
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('WebAuthn.enable');
  const a = await cdp.send('WebAuthn.addVirtualAuthenticator', {options: {protocol: 'ctap2', transport: 'internal',
    hasResidentKey: true, hasUserVerification: true, isUserVerified: verified, automaticPresenceSimulation: true}});
  return {cdp, id: a.authenticatorId};
}
(async () => {
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY || process.env.https_proxy || 'direct://', bypass: 'otp.test,localhost,127.0.0.1' },
    args: ['--host-resolver-rules=MAP otp.test 127.0.0.1', '--ignore-certificate-errors'] });
  // the administrator: switches it on, makes the account
  const actx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1300, height: 900 } });
  const a = await actx.newPage();
  await signIn(a, 'admin', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await post(a, 'users', {action: 'delete', name: 'pkuser'});
  ok('the account made', (await post(a, 'users', {action: 'add', name: 'pkuser', role: 'fulladmin', password: PW, must_change: 0})).st === 200);
  ok('the second step on, the passkey off (the default)', (await post(a, 'settings', {settings: {admin_2fa: 1, admin_2fa_passkey: 0}})).st === 200);
  await a.waitForTimeout(2500);

  const errs = [];
  let ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1180, height: 820 } });
  let p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  let dev = await device(ctx, p);
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  let ways = await p.$$eval('.mfa-ways .mfa-way', x => x.map(e => e.textContent));
  ok('off: no passkey among the ways', ways.length >= 1 && !ways.some(w => /passkey/i.test(w)), JSON.stringify(ways));
  await ctx.close();

  ok('the passkey switched on', (await post(a, 'settings', {settings: {admin_2fa_passkey: 1}})).st === 200);
  await a.waitForTimeout(2500);
  ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1180, height: 820 } });
  p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  dev = await device(ctx, p);
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  ways = await p.$$eval('.mfa-ways .mfa-way', x => x.map(e => e.textContent));
  ok('on: the password first, then the ways - the passkey among them', ways.some(w => /passkey/i.test(w)) && ways.some(w => /App/.test(w)), JSON.stringify(ways));
  await p.click('.mfa-ways .mfa-way:has-text("passkey")');
  await p.waitForTimeout(400);
  await p.screenshot({ path: SHOTS + '/enrol.png' });
  await p.click('text=Set up the passkey of this device');
  await p.waitForTimeout(4000);
  const inNow = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who);
  ok('set up with the face: signed in', inNow && inNow.name === 'pkuser' && inNow.role === 'fulladmin', JSON.stringify(inNow));
  const creds = (await dev.cdp.send('WebAuthn.getCredentials', {authenticatorId: dev.id})).credentials;
  ok('...the device keeps the passkey', creds.length === 1 && creds[0].rpId === 'otp.test', JSON.stringify(creds.map(c => c.rpId)));
  const acc = await a.evaluate(async () => (await (await fetch('?api=users')).json()));
  const row = (acc.users || []).find(u => u.name === 'pkuser');
  ok('Accounts: the second step a passkey, of which device for which name', row && row.mfa && row.mfa.kind === 'passkey' && /otp\.test/.test(row.mfa.dest), JSON.stringify(row && row.mfa));

  // the next time: the password, then the passkey
  await post(p, 'logout', {});
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('text=Use the passkey', { timeout: 10000 }).catch(() => {});
  ok('the next sign-in: after the password, the passkey asked', !!(await p.$('text=Use the passkey')));
  const half = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who);
  ok('...the password alone opens nothing', half && half.role === '', JSON.stringify(half));
  await p.screenshot({ path: SHOTS + '/check.png' });
  await p.click('text=Use the passkey');
  await p.waitForTimeout(4000);
  const in2 = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who);
  ok('...the face given: in', in2 && in2.role === 'fulladmin', JSON.stringify(in2));

  // another device (no passkey of this account): refused
  await post(p, 'logout', {});
  await dev.cdp.send('WebAuthn.removeVirtualAuthenticator', {authenticatorId: dev.id});
  const other = await device(ctx, p);
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('text=Use the passkey', { timeout: 10000 }).catch(() => {});
  await p.click('text=Use the passkey');
  await p.waitForTimeout(4000);
  const in3 = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who);
  const said = await p.$eval('#mfa-box', e => e.textContent).catch(() => '');
  ok('a device without its passkey: not in', in3 && in3.role === '', JSON.stringify(in3) + ' ' + said.slice(0, 200));
  await other.cdp.send('WebAuthn.removeVirtualAuthenticator', {authenticatorId: other.id});
  await ctx.close();

  // by an address: no passkey - said why
  ctx = await b.newContext({ ignoreHTTPSErrors: true });
  p = await ctx.newPage();
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'pkuser');
  await p.fill('input[type=password]', PW);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(3000);
  const why = await p.$eval('#mfa-box', e => e.textContent).catch(() => '');
  ok('by an address: the passkey cannot be used, said why', /opened by a name/.test(why), why.slice(0, 200));
  await ctx.close();

  // reset by a full administrator: set up again at the next sign-in
  ok('Accounts: the second step reset', (await post(a, 'users', {action: 'mfa_reset', name: 'pkuser'})).st === 200);
  ctx = await b.newContext({ ignoreHTTPSErrors: true });
  p = await ctx.newPage();
  dev = await device(ctx, p);
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  ok('...the next sign-in chooses and sets it up again', (await p.$$eval('.mfa-ways .mfa-way', x => x.length)) >= 2);
  await ctx.close();

  // a device that does not check who it is (no face, finger, PIN): refused at the setting up
  ctx = await b.newContext({ ignoreHTTPSErrors: true });
  p = await ctx.newPage();
  await device(ctx, p, false);
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  await p.click('.mfa-ways .mfa-way:has-text("passkey")');
  await p.click('text=Set up the passkey of this device');
  await p.waitForTimeout(4000);
  const in4 = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who);
  ok('a device that checks nobody: not taken', in4 && in4.role === '', JSON.stringify(in4));
  await ctx.close();

  const ev = await a.evaluate(async () => JSON.stringify(await (await fetch('?api=events&limit=200')).json()));
  ok('the events: the passkey set up, given, refused', /set up the second step of signing in: a passkey/.test(ev) && /gave the second step \(a passkey/.test(ev), ev.slice(0, 100));
  // Czech
  ctx = await b.newContext({ ignoreHTTPSErrors: true });
  p = await ctx.newPage();
  await p.goto(BASE);
  await p.evaluate(() => { document.cookie = 'otp_lang=cs; path=/'; });
  await signIn(p, 'pkuser', PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  await p.click('.mfa-ways .mfa-way:has-text("passkey")').catch(() => {});
  await p.waitForTimeout(500);
  const cz = await p.$eval('#mfa-box', e => e.textContent).catch(() => '');
  ok('Czech: the passkey way in Czech', /zařízení/.test(cz) && !/The face, a finger/.test(cz), cz.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/enrol-cs.png' });
  await ctx.close();

  // put back
  await post(a, 'settings', {settings: {admin_2fa: 0, admin_2fa_passkey: 0}});
  await post(a, 'users', {action: 'delete', name: 'pkuser'});
  ok('no errors on the pages', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
