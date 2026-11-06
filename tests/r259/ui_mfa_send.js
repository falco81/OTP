// ui_mfa_send.js - 1.0.259: the administration's second step by e-mail - the first code sent by
// itself when the check is shown (once a sign-in: F5 sends nothing again, it says "good for m:ss
// more"), "Send another" counting down to the next one allowed, "N more can be sent", at the fifth
// held with the reason and Sign in again; the API's `send` (GET, send, enrol_start, the 429s); Czech.
// Written for the live single-node install (run as root on the server): the mail sink of the tests
// (/tmp/claude-0/chal/sink.eml, as tests/ui/t_mfa2.py reads it). Takes about four minutes (the gaps).
//
//     node ui_mfa_send.js        (Playwright; https://127.0.0.1/admin/, admin's password in
//                                 /home/claude/run/adminpw)
const { chromium } = require('playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const BASE = 'https://127.0.0.1/admin/';
const PW = 'Mfa-Send-259-pass!';
const NAME = 'mfasend';
const SINK = '/tmp/claude-0/chal/sink.eml';
const SHOTS = '/tmp/claude-0/mfasend';
fs.mkdirSync(SHOTS, { recursive: true });
function mails() { try { return (fs.readFileSync(SINK, 'utf8').match(/^Subject:/mg) || []).length; } catch (e) { return 0; } }
function lastCode() { const s = fs.readFileSync(SINK, 'utf8'); const m = s.match(/Subject:.*?(\d{6})/g) || []; return (m[m.length - 1] || '').replace(/.*?(\d{6})$/, '$1'); }
function cli(args) { try { return execFileSync('python3', ['/usr/local/lib/otp/otp.py'].concat(args), {env: Object.assign({}, process.env, {OTP_CONFIG: '/etc/otp/config.json'})}).toString(); } catch (e) { return String(e); } }
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
async function sendBtn(p) {
  return p.$eval('#mfa-box button.cmd:not(.ghost)', e => ({text: e.textContent.trim(), disabled: e.disabled})).catch(() => ({}));
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch({ args: ['--ignore-certificate-errors'] });
  const actx = await b.newContext({ ignoreHTTPSErrors: true });
  await actx.addCookies([{name: 'otp_lang', value: 'en', domain: '127.0.0.1', path: '/'}]);
  const a = await actx.newPage();
  await signIn(a, 'admin', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await post(a, 'users', {action: 'delete', name: NAME});
  ok('the account made', (await post(a, 'users', {action: 'add', name: NAME, role: 'tokenadmin', password: PW, must_change: 0})).st === 200);
  ok('the second step on, by e-mail', (await post(a, 'settings', {settings: {admin_2fa: 1, admin_2fa_mail: 1}})).st === 200);
  await a.waitForTimeout(2500);
  const errs = [];
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  await ctx.addCookies([{name: 'otp_lang', value: 'en', domain: '127.0.0.1', path: '/'}]);
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  // ---- set up: the address proven
  await signIn(p, NAME, PW);
  await p.waitForSelector('.mfa-ways', { timeout: 10000 }).catch(() => {});
  const g0 = (await get(p, 'mfa')).d;
  ok('GET while setting up: send, nothing sent yet', g0.send && g0.send.sent === 0 && g0.send.most === 5, JSON.stringify(g0.send));
  await p.click('.mfa-ways .mfa-way:has-text("E-mail")');
  let m0 = mails();
  await p.fill('.mfa-body input.mono', 'mfasend@example.cz');
  await p.click('.mfa-body button:has-text("Send a code")');
  await p.waitForTimeout(2500);
  ok('set up: one mail', mails() === m0 + 1);
  const eb = await p.$eval('.mfa-body .mfa-row button', e => ({text: e.textContent.trim(), disabled: e.disabled}));
  ok('set up: Send another counting down, held', /^Send another \(0:[0-2]\d\)$/.test(eb.text) && eb.disabled, JSON.stringify(eb));
  ok('set up: "4 more can be sent"', /4 more can be sent for this sign-in/.test(await p.$eval('.mfa-body .mfa-left', e => e.textContent)));
  const again = await post(p, 'mfa', {action: 'enrol_start', kind: 'mail', dest: 'mfasend@example.cz'});
  ok('enrol_start again at once: 429, send in the answer, the wait in the words', again.st === 429 && again.d.send && again.d.send.why === 'gap' && /another in \d+ s/.test(again.d.error), JSON.stringify(again));
  await p.fill('.mfa-body form input', lastCode());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  ok('set up and signed in', ((await get(p, 'whoami')).d.who || {}).role === 'tokenadmin');
  await post(p, 'logout', {});
  // ---- the check: the first code by itself
  m0 = mails();
  await signIn(p, NAME, PW);
  await p.waitForSelector('#mfa-box .mfa-form', { timeout: 10000 }).catch(() => {});
  await p.waitForTimeout(2500);
  ok('the check: the first code went by itself (one mail)', mails() === m0 + 1, mails() - m0);
  ok('...said where it went', /Sent to .+ - write the code from it below\./.test(await p.$eval('#mfa-box .said.good', e => e.textContent).catch(() => '')));
  let sb = await sendBtn(p);
  ok('...Send another counting down, held', /^Send another \(0:[0-2]\d\)$/.test(sb.text) && sb.disabled, JSON.stringify(sb));
  await p.screenshot({ path: SHOTS + '/auto.png' });
  // F5: nothing sent again
  await p.reload();
  await p.waitForTimeout(3000);
  ok('F5: no second code by itself', mails() === m0 + 1, mails() - m0);
  const said = await p.$eval('#mfa-box .said.good', e => e.textContent).catch(() => '');
  ok('F5: "good for m:ss more"', /It is good for [0-4]:\d\d more\./.test(said), said);
  sb = await sendBtn(p);
  ok('F5: still counting down', /^Send another \(0:[0-2]\d\)$/.test(sb.text) && sb.disabled, JSON.stringify(sb));
  const g1 = (await get(p, 'mfa')).d;
  ok('GET: sent 1, left 4, not auto, wait under 30 s, the code good', g1.send && g1.send.sent === 1 && g1.send.left === 4 && !g1.send.auto && g1.send.wait_s <= 30 && g1.send.code_left_s > 0, JSON.stringify(g1.send));
  const sk = await post(p, 'mfa', {action: 'send', auto: true});
  ok('auto again: skipped, nothing sent', sk.st === 200 && sk.d.skipped && mails() === m0 + 1, JSON.stringify(sk));
  const soon = await post(p, 'mfa', {action: 'send'});
  ok('by hand too soon: 429 with send', soon.st === 429 && soon.d.send && soon.d.send.wait_s > 0, JSON.stringify(soon));
  // the countdown to zero, then the others up to the fifth
  for (let n = 2; n <= 5; n++) {
    await p.waitForFunction(() => { const e = document.querySelector('#mfa-box button.cmd:not(.ghost)'); return e && !e.disabled; }, null, { timeout: 40000 }).catch(() => {});
    sb = await sendBtn(p);
    ok('code ' + n + ': at zero "Send another" may be pressed', sb.text === 'Send another' && !sb.disabled, JSON.stringify(sb));
    const before = mails();
    await p.click('#mfa-box button.cmd:not(.ghost)');
    await p.waitForTimeout(2500);
    ok('code ' + n + ': sent', mails() === before + 1);
    if (n < 5) ok('code ' + n + ': "' + (5 - n) + ' more"', new RegExp((5 - n) + ' more can be sent').test(await p.$eval('#mfa-box .mfa-left', e => e.textContent)));
  }
  await p.screenshot({ path: SHOTS + '/limit.png' });
  sb = await sendBtn(p);
  const lim = await p.$eval('#mfa-box .mfa-limit', e => e.textContent).catch(() => '');
  /* 1.0.259: the button itself becomes Sign in again; the note only says why */
  ok('the fifth: the button is Sign in again, the note the reason only', !sb.disabled && /Sign in again/.test(sb.text) &&
     /That was the last code for this sign-in \(5\)/.test(lim) && !(await p.$('#mfa-box .mfa-limit button')), JSON.stringify(sb) + ' ' + lim);
  const six = await post(p, 'mfa', {action: 'send'});
  ok('a sixth by the API: 429, left 0, why most', six.st === 429 && six.d.send && six.d.send.left === 0 && six.d.send.why === 'most', JSON.stringify(six));
  // only the last one is good
  await p.fill('#mfa-box form input', lastCode());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  ok('the last code signs in', ((await get(p, 'whoami')).d.who || {}).role === 'tokenadmin');
  // Sign in again at the limit
  await post(p, 'logout', {});
  await signIn(p, NAME, PW);
  await p.waitForTimeout(2500);
  // Czech
  const cctx = await b.newContext({ ignoreHTTPSErrors: true });
  await cctx.addCookies((await ctx.cookies()).filter(c => c.name !== 'otp_lang').concat([{name: 'otp_lang', value: 'cs', domain: '127.0.0.1', path: '/'}]));
  const cp = await cctx.newPage();
  await cp.goto(BASE);
  await cp.waitForTimeout(3000);
  const cz = await cp.$eval('#mfa-box', e => e.textContent).catch(() => '');
  ok('Czech: the countdown and the count in Czech', /Poslat další/.test(cz) && /lze poslat ještě|Platí ještě/.test(cz), cz.slice(0, 300));
  await cp.screenshot({ path: SHOTS + '/cs.png' });
  await cctx.close();
  // put back
  await ctx.close();
  await post(a, 'users', {action: 'delete', name: NAME});
  const off = await post(a, 'settings', {settings: {admin_2fa: 0, admin_2fa_mail: 0}});
  if (off.st !== 200) cli(['--set', 'admin_2fa=0']);
  ok('no errors on the pages', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
