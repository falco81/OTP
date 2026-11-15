// kit_shots.js - 1.0.285: the kit's Czech pictures: the settings with the card's facts, and the sign-in page
// after the card was taken out (signout). Into SHOTS.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
const SHOTS = process.env.SHOTS || '/tmp/claude-0/cardshots';
const HOST = 'otp.corpnet.loc', URL = 'https://' + HOST + '/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
function set(mode) {
  execFileSync('otp', ['--set', 'admin_cert_card=' + mode, '--set', 'admin_cert_card_s=5', '--set', 'admin_cert_card_grace_s=30']);
  execFileSync('sleep', ['4']);
  for (let i = 0; i < 40; i++) {
    execFileSync('python3', ['-I', '/usr/local/lib/otp/otp_web.py']);
    if (/alive/.test(fs.readFileSync('/etc/nginx/conf.d/otp_certlogin.conf', 'utf8')) === (mode !== 'off')) break;
    execFileSync('sleep', ['1.5']);
  }
  execFileSync('sleep', ['4']);
}
(async () => {
  setup('up');
  set('grace');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'otp_lang', value: 'cs', url: 'https://' + HOST }]);
  let p = await ctx.newPage();
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}));
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(6000);
  const it = await p.$('.set-item[data-key="admin_cert_card"]');
  if (it) { await it.scrollIntoViewIfNeeded(); await p.evaluate(() => window.scrollBy(0, 120)); await p.waitForTimeout(500); }
  await p.screenshot({ path: SHOTS + '/07-settings-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await ctx.close();
  set('signout');
  ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2,
    clientCertificates: [{ origin: 'https://' + HOST + ':8443', certPath: PKI + '/falco.pem', keyPath: PKI + '/falco.key' }] });
  await ctx.addCookies([{ name: 'otp_lang', value: 'cs', url: 'https://' + HOST }]);
  p = await ctx.newPage();
  await p.addInitScript(() => { try { if (location.port !== '8443') sessionStorage.setItem('otp.cert.tried', '1'); } catch (e) {} });
  await p.goto(URL); await p.waitForTimeout(1200);
  await p.click('#cert-go');
  await p.waitForURL(/otp\.corpnet\.loc\/admin\//, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(3000);
  await ctx.route(/:8443\/admin\/\?api=cert-alive/, r => r.abort('failed'));
  await p.waitForSelector('#cert-go', { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(1500);
  console.log('said: ' + await p.textContent('#krb-said').catch(() => ''));
  await p.screenshot({ path: SHOTS + '/08-signed-out-cs.png' });
  await ctx.close();
  await b.close();
  set('off');
  setup('down');
  console.log('done');
})().catch(e => { console.log('FAIL ' + e); try { set('off'); setup('down'); } catch (x) {} process.exit(1); });
