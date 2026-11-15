// ui_certreq.js - 1.0.282 in a real Chromium: Settings - Accounts - "Values for a certificate request…":
// falco found, the subject, the UPN, the SID's URL each copied to the clipboard by its button, certreq's
// .inf and openssl's config; nobody found said; a phone (420 px) without sideways scroll; Czech. And the
// keytab guide of Windows with the domain's NetBIOS name from AD (CORPNET_NT\svc-otp-web), marked "from AD".
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync } = require('child_process');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/certreqshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const SID = 'S-1-5-21-1111-2222-3333-1105';
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
async function signIn(b, vw, vh, lang) {
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: vw, height: vh }, deviceScaleFactor: 2 });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://127.0.0.1' });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const p = await ctx.newPage();
  p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e)));
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate((l) => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}), lang || 'en');
  await p.goto(URL + '#settings/people'); await p.reload(); await p.waitForTimeout(4000);
  await p.waitForSelector('#cert-req', { timeout: 20000 }).catch(() => {});
  return p;
}
async function findIt(p, who) {
  await p.click('#cert-req');
  await p.waitForSelector('#creq-name', { timeout: 10000 });
  await p.fill('#creq-name', who);
  await p.keyboard.press('Enter');
  await p.waitForSelector('.creq-grid, .creq-out .note.bad', { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(500);
}
(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let p = await signIn(b, 1400, 900);
  await findIt(p, 'falco');
  const t = await p.textContent('#modal').catch(() => '');
  ok('falco: the subject, the UPN, the SID\'s URL', /CN=Falco Tester/.test(t) && /falco@corpnet\.cz/.test(t) && t.includes('tag:microsoft.com,2022-09-14:sid:' + SID), t.slice(0, 300));
  ok('...its role here, the mapping', /read only/.test(t) && /mapping:/.test(t));
  for (const [key, want] of [['subject', 'CN=Falco Tester'], ['upn', 'falco@corpnet.cz'], ['url', 'tag:microsoft.com,2022-09-14:sid:' + SID]]) {
    await p.click('#creq-copy-' + key);
    await p.waitForTimeout(300);
    const clip = await p.evaluate(() => navigator.clipboard.readText()).catch(e => 'ERR ' + e);
    ok(key + ': copied by its button', clip === want, clip);
  }
  await p.click('#creq-copy-certreq');
  await p.waitForTimeout(300);
  let clip = await p.evaluate(() => navigator.clipboard.readText()).catch(e => '');
  ok('certreq\'s .inf copied whole', /\[NewRequest\]/.test(clip) && clip.includes('url=tag:microsoft.com,2022-09-14:sid:' + SID));
  await p.$eval('.creq-grid', e => e.scrollIntoView({ block: 'start' })).catch(() => {});
  await p.screenshot({ path: SHOTS + '/01-falco.png' });
  await p.fill('#creq-name', 'nobody-here');
  await p.click('#creq-find');
  await p.waitForTimeout(1500);
  ok('nobody of the name: said in the window', /nobody called nobody-here/.test(await p.textContent('#modal').catch(() => '')));
  await p.keyboard.press('Escape');
  // the keytab guide from AD
  await p.waitForSelector('.krb-adsaid .tag.ok', { timeout: 20000 }).catch(() => {});
  const kg = await p.textContent('#krb-host').catch(() => '');
  ok('the keytab guide: from AD, CORPNET_NT (not CORPNET)', /from AD/.test(kg) && /CORPNET_NT/.test(kg), kg.slice(0, 200));
  ok('...the account holding the SPN: CORPNET_NT\\svc-otp-web in the commands', /setspn -S HTTP\/\S+ CORPNET_NT\\svc-otp-web/.test(kg) && /-mapuser CORPNET_NT\\svc-otp-web/.test(kg), (kg.match(/setspn[^\n]{0,80}/) || [''])[0]);
  ok('...the realm from AD', /@CORPNET\.LOC/.test(kg));
  await p.$eval('.krb-adsaid', e => e.scrollIntoView({ block: 'center' })).catch(() => {});
  await p.screenshot({ path: SHOTS + '/02-keytab-from-ad.png' });
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
  // a phone
  p = await signIn(b, 420, 860);
  await findIt(p, 'falco');
  const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1 ||
    [...document.querySelectorAll('#modal .creq-grid')].some(e => e.scrollWidth > e.clientWidth + 1));
  ok('420 px: no sideways scroll', !wide);
  await p.screenshot({ path: SHOTS + '/03-phone.png' });
  await p.context().close();
  // Czech
  p = await signIn(b, 1400, 900, 'cs');
  const btn = await p.textContent('#cert-req').catch(() => '');
  ok('in Czech: the button', /Hodnoty pro žádost o certifikát/.test(btn), btn);
  await findIt(p, 'falco');
  const cz = await p.textContent('#modal').catch(() => '');
  ok('...the window', /Subjekt/.test(cz) && /Zkopírovat SAN/.test(cz), cz.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/04-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.context().close();
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
