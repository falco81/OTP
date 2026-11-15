// ui_card.js - 1.0.285 in a real Chromium: the card of a sign-in with a certificate watched (as the kit
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

(async () => {
  setup('up');
  set({ admin_cert_card: 'grace', admin_cert_card_s: 5, admin_cert_card_grace_s: 30 });
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let ctx = await context(b, 'falco');
  let p = await page(ctx);
  await certIn(p);
  await p.waitForTimeout(7000);
  ok('grace: signed in with the certificate, the port\'s picture loaded (200), let in by the page\'s policy', ctx.looks.length >= 2 &&
     ctx.looks.every(s => s === 200) && p.csp.length === 0, ctx.looks.join(',') + ' ' + p.csp.join(' | '));
  ok('...nothing covers the page', !(await p.$('#cw-layer')));
  await cardOut(ctx);
  const t0 = Date.now();
  await p.waitForSelector('#cw-layer', { timeout: 15000 }).catch(() => {});
  ok('the card taken out: the notice within a check or so', !!(await p.$('#cw-layer')) && Date.now() - t0 < 12000, (Date.now() - t0) + ' ms');
  const n1 = await p.textContent('#cw-n').catch(() => '');
  await p.waitForTimeout(2100);
  const n2 = await p.textContent('#cw-n').catch(() => '');
  const ring = await p.evaluate(() => { const a = document.querySelector('#cw-layer .cw-arc'); return a ? +a.getAttribute('stroke-dashoffset') : -1; });
  ok('..."Put the card back", the seconds in the ring counting down by the second', /Put the card back/.test(await p.textContent('#cw-layer')) &&
     parseInt(n2, 10) <= parseInt(n1, 10) - 2 && parseInt(n1, 10) <= 30 && /Signed out in \d+ s unless the card is back/.test(await p.textContent('#cw-until')), n1 + ' -> ' + n2);
  ok('...the ring empties as they go', ring > 0, ring);
  ok('...Sign out', !!(await p.$('#cw-out')));
  ok('...nothing behind reachable (inert)', await p.evaluate(() => { const h = document.querySelector('header'); return !!(h && h.closest('[inert]')); }));
  ok('...the server answers nothing of the session (423)', await status(p) === 423);
  await p.screenshot({ path: SHOTS + '/01-notice-en.png' });
  const outLooks = ctx.looks.length;
  await p.waitForTimeout(6000);
  ok('...asked again about every 5 s while out, not more', ctx.looks.length - outLooks <= 2, (ctx.looks.length - outLooks) + ' in 6 s');
  await cardIn(ctx);
  await p.waitForSelector('#cw-layer', { state: 'detached', timeout: 12000 }).catch(() => {});
  ok('the card back in time: the notice gone', !(await p.$('#cw-layer')));
  await p.waitForTimeout(300);
  ok('...said', /The card is back/.test(await p.evaluate(() => document.body.innerText)));
  ok('...the pages answer again, nothing inert', await status(p) === 200 && await p.evaluate(() => !document.querySelector('body > [inert]')));
  // two tabs: one check for both
  const p2 = await page(ctx);
  await p2.goto(URL); await p2.waitForTimeout(3000);
  const l0 = ctx.looks.length;
  await p.waitForTimeout(20000);
  const per = ctx.looks.length - l0;
  ok('two tabs of one browser: one check for both (about every 5 s, not twice that)', per >= 3 && per <= 6, per + ' checks in 20 s');
  await p2.close();
  // not back in time
  execFileSync('otp', ['--set', 'admin_cert_card_grace_s=5']);
  await p.waitForTimeout(4000);
  await p.reload(); await p.waitForTimeout(3000);
  await cardOut(ctx);
  await p.waitForSelector('#in-name, #cert-go', { timeout: 25000 }).catch(() => {});
  await p.waitForTimeout(800);
  let said = await p.textContent('#krb-said').catch(() => '');
  ok('not back in time: the sign-in page - "...was not put back in time."', /not put back in time/.test(said), said);
  ok('...signed out on the server too', await p.evaluate(async () => !(await (await fetch('?api=whoami')).json()).who));
  ok('...nothing tried by itself (no certificate chooser)', !/:8443/.test(p.url()));
  await p.screenshot({ path: SHOTS + '/02-signed-out-grace-en.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await ctx.close();

  // signout
  set({ admin_cert_card: 'signout', admin_cert_card_grace_s: 30 });
  ctx = await context(b, 'falco');
  p = await page(ctx);
  await certIn(p);
  ok('signout: signed in', await p.evaluate(async () => !!(await (await fetch('?api=whoami')).json()).who));
  await cardOut(ctx);
  await p.waitForSelector('#in-name, #cert-go', { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(800);
  said = await p.textContent('#krb-said').catch(() => '');
  ok('the card taken out: the sign-in page at once - "...was taken out."', /was taken out/.test(said) && !(await p.$('#cw-layer')), said);
  ok('...signed out on the server', await p.evaluate(async () => !(await (await fetch('?api=whoami')).json()).who));
  await p.screenshot({ path: SHOTS + '/03-signed-out-signout-en.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await ctx.close();

  // Czech, a phone
  set({ admin_cert_card: 'grace' });
  ctx = await context(b, 'falco', 'cs');
  p = await page(ctx);
  await certIn(p);
  await cardOut(ctx);
  await p.waitForSelector('#cw-layer', { timeout: 15000 }).catch(() => {});
  await p.waitForTimeout(700);
  const cz = await p.textContent('#cw-layer').catch(() => '');
  ok('in Czech', /Vraťte kartu zpět/.test(cz) && /sekund/.test(cz) && /Odhlášení za \d+ s, pokud se karta nevrátí/.test(cz) && /Odhlásit/.test(cz), cz.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/04-notice-cs.png' });
  await ctx.close();
  ctx = await context(b, 'falco', 'en', true);
  p = await page(ctx);
  await certIn(p);
  await cardOut(ctx);
  await p.waitForSelector('#cw-layer', { timeout: 15000 }).catch(() => {});
  await p.waitForTimeout(500);
  ok('a phone: the notice fits, no sideways scroll', await p.evaluate(() => {
    const b = document.querySelector('.cw-box').getBoundingClientRect();
    return b.left >= 0 && b.right <= window.innerWidth && document.documentElement.scrollWidth <= window.innerWidth + 1;
  }));
  await p.screenshot({ path: SHOTS + '/05-phone.png' });
  await ctx.close();

  // a password's sign-in: never watched; the settings and the facts
  ctx = await context(b, null);
  p = await page(ctx);
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(6000);
  ok('a password\'s sign-in: the port never asked', ctx.looks.length === 0, ctx.looks.join(','));
  const st = await p.evaluate(() => {
    const sel = document.getElementById('set-admin_cert_card');
    const it = k => document.querySelector('.set-item[data-key="' + k + '"]');
    return { opts: sel ? [...sel.options].map(o => o.value) : [], val: sel ? sel.value : '',
             every: !!it('admin_cert_card_s') && !it('admin_cert_card_s').classList.contains('asleep'),
             grace: !!it('admin_cert_card_grace_s') && !it('admin_cert_card_grace_s').classList.contains('asleep'),
             facts: [...document.querySelectorAll('.kv-grid')].map(e => e.innerText).join('\n') };
  });
  ok('the settings: When the card is taken out - off, signout, grace; Checked every; ...put back within', st.opts.join(',') === 'off,signout,grace' &&
     st.val === 'grace' && st.every && st.grace, JSON.stringify(st).slice(0, 200));
  ok('the card\'s facts: "a notice, then signed out unless it is back within 30 s (checked every 5 s)"',
     /When the card is taken out\s+a notice, then signed out unless it is back within 30 s \(checked every 5 s\)/.test(st.facts), st.facts.slice(0, 300));
  const it = await p.$('.set-item[data-key="admin_cert_card"]');
  if (it) { await it.scrollIntoViewIfNeeded(); await p.waitForTimeout(400); }
  await p.screenshot({ path: SHOTS + '/06-settings-en.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await ctx.close();
  await b.close();
  set({ admin_cert_card: 'off', admin_cert_card_s: 15, admin_cert_card_grace_s: 30 });
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { set({ admin_cert_card: 'off', admin_cert_card_s: 15, admin_cert_card_grace_s: 30 }); setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
