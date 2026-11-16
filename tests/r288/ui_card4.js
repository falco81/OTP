// ui_card4.js - 1.0.288 in a real Chromium: the card watched, the kit's 4th edition. A check held unanswered (a
// window of the card's): the countdown within 4 s, its hint (OK, not Cancel); F5 goes on counting; Czech; the
// server's end said (5 px). The helpers are r285/ui_card.js's.
// (helpers of r285/ui_card.js) 1.0.285 in a real Chromium: the card of a sign-in with a certificate watched (as the kit
// "card-removal-watch"). falco signs in with the certificate (Playwright's clientCertificates for the port,
// as a card's once its PIN is given); the page loads a picture of the port every 5 s - let in by the page's
// policy, with the session's cookie, 1 px wide. The card "taken out" - the port's handshake failing (the
// pictures aborted): grace - the notice with its countdown, nothing behind it reachable, the questions 423;
// back - gone, said; not back in time - the sign-in page saying so; signout - at once; Czech; a phone; two
// tabs sharing one check; the settings and the card's facts. A password's sign-in never watched.
const { chromium, devices } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/cardshots';
const HOST = 'otp.corpnet.loc';
const URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(...a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', ...a], { encoding: 'utf8' }); }
function set(kv) {
  const args = [];
  for (const k of Object.keys(kv)) args.push('--set', k + '=' + kv[k]);
  execFileSync('otp', args, { encoding: 'utf8' });
  execFileSync('sleep', ['4']);
  /* root's helper as otp-web.path would (no systemd here): nginx made for the card, or as before */
  const want = kv.admin_cert_card && kv.admin_cert_card !== 'off';
  if (!('admin_cert_card' in kv)) return;
  for (let i = 0; i < 40; i++) {
    execFileSync('python3', ['-I', '/usr/local/lib/otp/otp_web.py'], { encoding: 'utf8' });
    if (/alive/.test(fs.readFileSync('/etc/nginx/conf.d/otp_certlogin.conf', 'utf8')) === !!want) break;
    execFileSync('sleep', ['1.5']);
  }
}
async function context(b, person, lang, phone) {
  const opts = phone ? { ...devices['Pixel 7'], ignoreHTTPSErrors: true } : { ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 };
  if (person) opts.clientCertificates = [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/' + person + '.pem', keyPath: PKI + '/' + person + '.key' }];
  const ctx = await b.newContext(opts);
  await ctx.addCookies([{ name: 'otp_lang', value: lang || 'en', url: 'https://' + HOST }]);
  ctx.looks = [];
  ctx.on('requestfinished', async r => { if (/api=cert-alive/.test(r.url())) { const s = await r.response(); ctx.looks.push(s ? s.status() : 0); } });
  ctx.on('requestfailed', r => { if (/api=cert-alive/.test(r.url())) ctx.looks.push('x'); });
  return ctx;
}
async function page(ctx) {
  const p = await ctx.newPage();
  p.errs = [];
  p.csp = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  p.on('console', m => { if (/Content Security Policy/i.test(m.text())) p.csp.push(m.text()); });
  return p;
}
async function certIn(p) {
  await p.addInitScript(() => { try { if (location.port !== '8443') sessionStorage.setItem('otp.cert.tried', '1'); } catch (e) {} });
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go');
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(3000);
}
async function status(p) { return p.evaluate(async () => (await fetch('?api=status')).status); }
const ALIVE = /:8443\/admin\/\?api=cert-alive/;
async function cardOut(ctx) { await ctx.route(ALIVE, r => r.abort('failed')); }
async function cardIn(ctx) { await ctx.unroute(ALIVE); }


const HOLD = /:8443\/admin\/\?api=cert-alive/;
(async () => {
  setup('up');
  set({ admin_cert_card: 'grace', admin_cert_card_s: 5, admin_cert_card_grace_s: 60 });
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let ctx = await context(b, 'falco');
  let p = await page(ctx);
  await certIn(p);
  await p.waitForTimeout(7000);
  ok('grace: signed in, checks answered (200)', ctx.looks.length >= 1 && ctx.looks.every(s => s === 200), ctx.looks.join(','));
  /* A window of the card's: the check is held unanswered (Windows' "insert the smart card") */
  let release = [];
  await ctx.route(HOLD, r => { release.push(r); });
  const t0 = Date.now();
  await p.waitForSelector('#cw-layer', { timeout: 20000 }).catch(() => {});
  const took = Date.now() - t0;
  ok('a check waiting on a window of the card\'s: the countdown within a check + 4 s, not after 20 s', !!(await p.$('#cw-layer')) && took < 12000, took + ' ms');
  const hint = await p.textContent('.cw-hint').catch(() => '');
  ok('...the notice says: OK there, not Cancel', /press OK there - not Cancel/.test(hint), hint);
  await p.waitForTimeout(1500);
  ok('...the pages held (423)', await status(p) === 423);
  await p.screenshot({ path: SHOTS + '/10-waiting-en.png' });
  /* F5: the countdown goes on from the server's time */
  await p.waitForTimeout(4000);
  const before = Number(await p.textContent('#cw-n').catch(() => '0'));
  await ctx.unroute(HOLD);
  for (const r of release) { try { await r.abort('failed'); } catch (e) {} }
  release = [];
  await ctx.route(HOLD, r => r.abort('failed'));
  await p.reload();
  await p.waitForSelector('#cw-layer', { timeout: 15000 }).catch(() => {});
  const after = Number(await p.textContent('#cw-n').catch(() => '0'));
  ok('F5 during the countdown: it goes on, not from the full time again', after > 0 && after <= before + 1 && after < 58, before + ' -> ' + after);
  /* the card back */
  await ctx.unroute(HOLD);
  await p.waitForSelector('#cw-layer', { state: 'detached', timeout: 20000 }).catch(() => {});
  ok('the card back: the notice goes', !(await p.$('#cw-layer')));
  ok('...answered again', await status(p) === 200);
  /* Czech: the hint */
  await ctx.close();
  ctx = await context(b, 'falco', 'cs');
  p = await page(ctx);
  await certIn(p);
  await p.waitForTimeout(6000);
  await ctx.route(HOLD, r => r.abort('failed'));
  await p.waitForSelector('#cw-layer', { timeout: 20000 }).catch(() => {});
  const hcs = await p.textContent('.cw-hint').catch(() => '');
  ok('Czech: the hint in Czech', /ne Zrušit/.test(hcs), hcs);
  await p.screenshot({ path: SHOTS + '/11-waiting-cs.png' });
  await ctx.unroute(HOLD);
  await p.waitForTimeout(6000);
  /* ended by the server, said why: signout, the card out - 5 px */
  set({ admin_cert_card: 'signout' });
  await ctx.close();
  ctx = await context(b, 'falco');
  p = await page(ctx);
  await certIn(p);
  await p.waitForTimeout(6000);
  await ctx.route(HOLD, r => r.fulfill({ status: 200, contentType: 'image/gif', body: Buffer.from('R0lGODlhBQABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAFAAEAAAgGAAEIFBgQADs=', 'base64') }));
  await p.waitForSelector('#in-name, #cert-go', { timeout: 20000 }).catch(() => {});
  const said = await p.textContent('#krb-said, #in-said').catch(() => '');
  ok('ended by the server (5 px): the sign-in page says the card was taken out', /taken out/.test(said || ''), said);
  ok('...nothing tried by itself (no certificate sign-in started)', !/api=cert-login/.test(p.url()), p.url());
  ok('no errors on the pages', p.errs.length === 0, p.errs.join(' | '));
  await b.close();
  set({ admin_cert_card: 'off', admin_cert_card_s: 15, admin_cert_card_grace_s: 30 });
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { set({ admin_cert_card: 'off', admin_cert_card_s: 15, admin_cert_card_grace_s: 30 }); setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
