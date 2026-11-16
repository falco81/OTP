// ui_unable.js - 1.0.286 in a real Chromium: a browser that cannot be checked, as an iPad - its page's pictures
// of the certificate's port never arrive (aborted from the start), the card in. allow (the default): no notice,
// still signed in, the person told "This browser cannot have the card checked...", no more checks, the event
// says why; Czech. signout: as a card taken out. The same browser with a check that found the card first: a
// later failure is the card taken out (the notice).
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/unableshots';
const HOST = 'otp.corpnet.loc', URL = 'https://' + HOST + '/admin/';
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
function set(kv, nginx) {
  const args = [];
  for (const k of Object.keys(kv)) args.push('--set', k + '=' + kv[k]);
  execFileSync('otp', args);
  execFileSync('sleep', ['4']);
  if (nginx === undefined) return;
  for (let i = 0; i < 40; i++) {
    execFileSync('python3', ['-I', '/usr/local/lib/otp/otp_web.py']);
    if (/alive/.test(fs.readFileSync('/etc/nginx/conf.d/otp_certlogin.conf', 'utf8')) === nginx) break;
    execFileSync('sleep', ['1.5']);
  }
  execFileSync('sleep', ['4']);
}
const ALIVE = /:8443\/admin\/\?api=cert-alive/;
async function ipad(b, lang) {
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2,
    clientCertificates: [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/falco.pem', keyPath: PKI + '/falco.key' }] });
  await ctx.addCookies([{ name: 'otp_lang', value: lang || 'en', url: 'https://' + HOST }]);
  ctx.looks = 0;
  ctx.on('request', r => { if (ALIVE.test(r.url())) ctx.looks++; });
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  await p.addInitScript(() => { try { if (location.port !== '8443') sessionStorage.setItem('otp.cert.tried', '1'); } catch (e) {} });
  return [ctx, p];
}
async function certIn(p) {
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go');
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
}
async function who(p) { return p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who); }
async function status(p) { return p.evaluate(async () => (await fetch('?api=status')).status); }
async function toastText(p) { return p.evaluate(() => (document.getElementById('toast') || {}).textContent || ''); }

(async () => {
  setup('up');
  set({ admin_cert_card: 'grace', admin_cert_card_s: 5, admin_cert_card_grace_s: 30, admin_cert_card_unable: 'allow' }, true);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  // allow: the pictures never arrive (an iPad)
  let [ctx, p] = await ipad(b);
  await ctx.route(ALIVE, r => r.abort('failed'));
  await certIn(p);
  await p.waitForFunction(() => /cannot have the card checked/.test((document.getElementById('toast') || {}).textContent || ''), null, { timeout: 15000 }).catch(() => {});
  ok('allow: the pictures never arrive - the person told "This browser cannot have the card checked: this sign-in is not watched." (1.0.288; with "as an iPad cannot" before)',
     /This browser cannot have the card checked( \(as an iPad cannot\))?: this sign-in is not watched\./.test(await toastText(p)), await toastText(p));
  await p.screenshot({ path: SHOTS + '/08-unable-en.png' });
  ok('...no notice over the page', !(await p.$('#cw-layer')));
  const w = await who(p);
  ok('...still signed in, the role kept, not watched (whoami: no card)', w && w.name === 'falco' && w.role === 'readonly' && !w.card, JSON.stringify(w));
  ok('...the pages answer (200)', await status(p) === 200);
  const n0 = ctx.looks;
  await p.waitForTimeout(12000);
  ok('...no more checks (the card is not asked again and again)', ctx.looks === n0, (ctx.looks - n0) + ' more');
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await ctx.close();
  // Czech
  [ctx, p] = await ipad(b, 'cs');
  await ctx.route(ALIVE, r => r.abort('failed'));
  await certIn(p);
  await p.waitForFunction(() => /nejde/.test((document.getElementById('toast') || {}).textContent || ''), null, { timeout: 15000 }).catch(() => {});
  ok('in Czech', /V tomto prohlížeči kartu kontrolovat nejde( \(stejně jako na iPadu\))?: toto přihlášení se nehlídá\./.test(await toastText(p)), await toastText(p));
  await p.screenshot({ path: SHOTS + '/08-unable-cs.png' });
  await ctx.close();
  // found first, then the pictures fail: the card taken out
  [ctx, p] = await ipad(b);
  await certIn(p);
  await p.waitForTimeout(4000);
  await ctx.route(ALIVE, r => r.abort('failed'));
  await p.waitForSelector('#cw-layer', { timeout: 20000 }).catch(() => {});
  ok('found once, then the pictures fail: the card taken out - the notice', !!(await p.$('#cw-layer')) && !/cannot have the card checked/.test(await toastText(p)));
  ok('...held (423)', await status(p) === 423);
  await ctx.close();
  // signout: never found - as a card taken out
  set({ admin_cert_card_unable: 'signout' });
  [ctx, p] = await ipad(b);
  await ctx.route(ALIVE, r => r.abort('failed'));
  await certIn(p);
  await p.waitForSelector('#cw-layer', { timeout: 20000 }).catch(() => {});
  ok('A browser that cannot be checked = signout: never found - as the card taken out (the notice)', !!(await p.$('#cw-layer')));
  await ctx.close();
  await b.close();
  set({ admin_cert_card: 'off', admin_cert_card_s: 15, admin_cert_card_grace_s: 30, admin_cert_card_unable: 'allow' }, false);
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { set({ admin_cert_card: 'off', admin_cert_card_unable: 'allow' }, false); setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
