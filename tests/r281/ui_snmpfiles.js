// ui_snmpfiles.js - 1.0.281: Settings - Monitoring, SNMPv3, in a real Chromium: the Zabbix 7.0 part says
// how to put a node in, and its two buttons hand over the template and OTP-MIB as files; in Czech too.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const SHOTS = process.env.SHOTS || '/tmp/claude-0/snmpfileshots';
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(SHOTS, { recursive: true });
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(URL); await p.waitForTimeout(1000);
  await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  await p.goto(URL + '#settings/monitor'); await p.reload(); await p.waitForTimeout(4000);
  await p.waitForSelector('#snmp-file-zabbix', { timeout: 20000 }).catch(() => {});
  const t = await p.textContent('#snmp-host').catch(() => '');
  ok('the Zabbix 7.0 part: how to put a node in', /Zabbix 7\.0/.test(t) && /otp by SNMP/.test(t) && /Templates/.test(t) && /authPriv/.test(t), t.slice(0, 200));
  await p.$eval('#snmp-file-zabbix', e => e.scrollIntoView({ block: 'center' })).catch(() => {});
  await p.screenshot({ path: SHOTS + '/01-zabbix-part.png' });
  for (const [id, name, want] of [['zabbix', 'otp_by_snmp_zabbix7.yaml', "version: '7.0'"], ['mib', 'OTP-MIB.txt', 'OTP-MIB DEFINITIONS']]) {
    const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 20000 }).catch(() => null), p.click('#snmp-file-' + id)]);
    const path = dl ? await dl.path() : null;
    const text = path ? fs.readFileSync(path, 'utf8') : '';
    ok(id + ': downloaded as ' + name, dl && dl.suggestedFilename() === name && text.includes(want), dl ? dl.suggestedFilename() : 'no download');
  }
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}));
  await p.reload(); await p.waitForTimeout(4000);
  const cz = await p.textContent('#snmp-host').catch(() => '');
  ok('in Czech: the buttons and the words', /Stáhnout šablonu pro Zabbix 7\.0/.test(cz) && /Šablona/.test(cz), cz.slice(0, 200));
  await p.$eval('#snmp-file-zabbix', e => e.scrollIntoView({ block: 'center' })).catch(() => {});
  await p.screenshot({ path: SHOTS + '/02-zabbix-part-cs.png' });
  await p.evaluate(() => fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}));
  ok('no page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
