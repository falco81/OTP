// ui_csr.js - 1.0.283 in a real Chromium: Values for a certificate request -> Make a CSR…: falco's values
// in the second window, chosen and added to (ECDSA P-256 and RSA 2048, O and C, the e-mail left out,
// Secure Email added, a template, a passphrase); the CSR and the key downloaded and checked by openssl - the
// request's signature, subject, SAN (the UPN, the SID's URL), the key usages, the template, the key locked by
// the passphrase and the CSR's own; the CSR signed by the test PKI's issuing authority and the certificate
// read by otp: falco's UPN and SID (strong mapping). Wrong input said in the window; a phone; Czech.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execFileSync, spawnSync } = require('child_process');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/csrshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const SID = 'S-1-5-21-1111-2222-3333-1105';
const PKI = process.env.PKI_DIR || '/tmp/claude-0/pki2';
/* the version installed (the full run gives none): its otp.py reads the certificate */
const V = process.argv[2] || (execFileSync('otp', ['--version'], { encoding: 'utf8' }).match(/\d+\.\d+\.\d+/) || ['1.0.283'])[0];
const WORK = fs.mkdtempSync('/tmp/claude-0/csr-');
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function sh(cmd, args, input) {
  /* what it said on both outputs (openssl says "verify OK" on its errors' one); ERR when it failed */
  const r = spawnSync(cmd, args, { encoding: 'utf8', input: input });
  return (r.status === 0 ? '' : 'ERR ') + (r.stdout || '') + (r.stderr || '');
}
function setup(a) { return execFileSync('python3', [__dirname + '/../cert/ui_cert_setup.py', a], { encoding: 'utf8' }); }
async function signIn(b, vw, vh, lang) {
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: vw, height: vh }, deviceScaleFactor: 2, acceptDownloads: true });
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
async function openCsr(p, who) {
  await p.click('#cert-req');
  await p.waitForSelector('#creq-name', { timeout: 10000 });
  await p.fill('#creq-name', who);
  await p.keyboard.press('Enter');
  await p.waitForSelector('#creq-csr', { timeout: 20000 });
  await p.click('#creq-csr');
  await p.waitForSelector('#csr-key', { timeout: 10000 });
}
async function grab(p, id) {
  const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 20000 }).catch(() => null), p.click(id)]);
  if (!dl) return null;
  const to = WORK + '/' + dl.suggestedFilename();
  await dl.saveAs(to);
  return to;
}
(async () => {
  setup('up');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let p = await signIn(b, 1400, 950);
  await openCsr(p, 'falco');
  ok('the second window: falco\'s CN, UPN and SID\'s URL filled in', await p.inputValue('#csr-cn') === 'Falco Tester' &&
     await p.inputValue('#csr-upn') === 'falco@corpnet.cz' && await p.inputValue('#csr-url') === 'tag:microsoft.com,2022-09-14:sid:' + SID);
  ok('...the UPN and the URL ticked; Client Authentication and Smart Card Logon ticked, Secure Email not',
     await p.isChecked('#csr-use-upn') && await p.isChecked('#csr-use-url') && await p.isChecked('#csr-eku-0') &&
     await p.isChecked('#csr-eku-1') && !(await p.isChecked('#csr-eku-2')));
  await p.screenshot({ path: SHOTS + '/01-options.png' });
  // wrong input said
  await p.fill('#csr-c', '1Z');
  await p.click('#modal-foot button:has-text("Make the CSR")');
  await p.waitForTimeout(400);
  ok('a country not of two letters: said, nothing made', /two letters/.test(await p.textContent('.csr-out')));
  await p.fill('#csr-c', 'CZ');
  await p.fill('#csr-pass', 'short');
  await p.fill('#csr-pass2', 'short');
  await p.click('#modal-foot button:has-text("Make the CSR")');
  await p.waitForTimeout(400);
  ok('a passphrase too short: said', /8 characters/.test(await p.textContent('.csr-out')));
  // ECDSA P-256, O, C, no e-mail, Secure Email, a template, a passphrase
  await p.selectOption('#csr-key', 'p256');
  await p.fill('#csr-o', 'Corp a.s.');
  if (await p.isChecked('#csr-use-email')) await p.uncheck('#csr-use-email');
  await p.check('#csr-eku-2');
  await p.fill('#csr-template', 'SmartcardLogonOtp');
  await p.fill('#csr-pass', 'csr-passphrase-283');
  await p.fill('#csr-pass2', 'csr-passphrase-283');
  await p.click('#modal-foot button:has-text("Make the CSR")');
  await p.waitForSelector('#csr-dl-csr', { timeout: 30000 }).catch(() => {});
  await p.screenshot({ path: SHOTS + '/02-made.png' });
  const csr = await grab(p, '#csr-dl-csr'), key = await grab(p, '#csr-dl-key');
  ok('the CSR and the key downloaded (falco-....csr/.key)', csr && key && /falco-\d{8}\.csr$/.test(csr) && /\.key$/.test(key), [csr, key]);
  const txt = sh('openssl', ['req', '-in', csr, '-noout', '-text', '-verify']);
  ok('openssl: the request\'s signature good', /verify OK/i.test(txt) || /self-signature verify OK/.test(sh('openssl', ['req', '-in', csr, '-noout', '-verify'])), txt.slice(-200));
  ok('...the subject O=Corp a.s., C=CZ, CN=Falco Tester', /C\s*=\s*CZ, O\s*=\s*Corp a\.s\., CN\s*=\s*Falco Tester/.test(txt), (txt.match(/Subject:.*/) || [''])[0]);
  ok('...ECDSA P-256', /P-256/.test(txt));
  ok('...the SAN: the UPN and the SID\'s URL, no e-mail', /othername: UPN::falco@corpnet\.cz/.test(txt) && txt.includes('URI:tag:microsoft.com,2022-09-14:sid:' + SID) && !/email:/.test(txt));
  ok('...Client Authentication, Smart Card Logon, E-mail Protection', /TLS Web Client Authentication/.test(txt) && /Smartcard Log/i.test(txt) && /E-mail Protection/.test(txt));
  ok('...the template in it', /S.m.a.r.t.c.a.r.d.L.o.g.o.n.O.t.p/.test(txt));
  ok('the key: locked by the passphrase', /ENCRYPTED PRIVATE KEY/.test(fs.readFileSync(key, 'utf8')) && /^ERR/.test(sh('openssl', ['pkey', '-in', key, '-passin', 'pass:wrong-one', '-noout'])));
  const kpub = sh('openssl', ['pkey', '-in', key, '-passin', 'pass:csr-passphrase-283', '-pubout']), rpub = sh('openssl', ['req', '-in', csr, '-pubkey', '-noout']);
  // (both say only the key: the same text when it is the same key)
  ok('...opened by it, and the CSR\'s own', kpub.includes('PUBLIC KEY') && kpub === rpub);
  // the CSR signed by the test PKI's issuing authority, the certificate read by otp
  const crt = WORK + '/falco.crt';
  const signed = sh('openssl', ['x509', '-req', '-in', csr, '-CA', PKI + '/issuing.pem', '-CAkey', PKI + '/issuing.key', '-CAcreateserial',
                                '-days', '30', '-copy_extensions', 'copy', '-out', crt]);
  ok('the CSR signed by the test PKI\'s issuing authority', fs.existsSync(crt), signed);
  const read = sh('python3', ['-c', 'import sys;g={"__name__":"t","__file__":sys.argv[1]};exec(compile(open(sys.argv[1]).read(),"otp","exec"),g);f=g["cert_facts"](open(sys.argv[2]).read());print(f["upn"],f["sid"],f["eku"])',
                              '/home/claude/build/out/otp-' + V + '/otp.py', crt]);
  ok('...otp reads it: falco\'s UPN and SID (strong mapping), Client Authentication and Smart Card Logon', read.includes("['falco@corpnet.cz']") && read.includes(SID) &&
     read.includes('1.3.6.1.5.5.7.3.2') && read.includes('1.3.6.1.4.1.311.20.2.2'), read);
  // RSA 2048, no passphrase
  await p.selectOption('#csr-key', 'rsa2048');
  await p.uncheck('#csr-protect');
  await p.click('#modal-foot button:has-text("Make the CSR")');
  await p.waitForTimeout(6000);
  const csr2 = await grab(p, '#csr-dl-csr'), key2 = await grab(p, '#csr-dl-key');
  const t2 = csr2 ? sh('openssl', ['req', '-in', csr2, '-noout', '-text']) : '';
  ok('RSA 2048 without a passphrase: a good request, the key open', /Public-Key: \(2048 bit\)/.test(t2) && /^-----BEGIN PRIVATE KEY/.test(fs.readFileSync(key2, 'utf8')) &&
     /self-signature verify OK/.test(sh('openssl', ['req', '-in', csr2, '-noout', '-verify'])), t2.slice(0, 200));
  await p.click('#csr-copy');
  await p.waitForTimeout(300);
  const clip = await p.evaluate(() => navigator.clipboard.readText()).catch(() => '');
  ok('Copy the CSR: on the clipboard', clip === fs.readFileSync(csr2, 'utf8'));
  ok('no page errors', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
  // a phone, Czech
  p = await signIn(b, 420, 860);
  await openCsr(p, 'falco');
  const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1 ||
    [...document.querySelectorAll('#modal .csr-san, #modal .csr-grid')].some(e => e.scrollWidth > e.clientWidth + 1));
  ok('420 px: no sideways scroll', !wide);
  await p.screenshot({ path: SHOTS + '/03-phone.png' });
  await p.context().close();
  p = await signIn(b, 1400, 950, 'cs');
  await openCsr(p, 'falco');
  const cz = await p.textContent('#modal').catch(() => '');
  ok('in Czech', /Vytvořit žádost o certifikát/.test(cz) && /Soukromý klíč/.test(cz) && /K čemu certifikát slouží/.test(cz), cz.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/04-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.context().close();
  await b.close();
  setup('down');
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); try { setup('down'); } catch (x) {} console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
