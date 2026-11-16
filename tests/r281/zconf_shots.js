// zconf_shots.js - how the test Zabbix 7.0 is set up for otp's SNMPv3 agent: the hosts list (SNMP available), the
// host's SNMP interface (its form), latest data; and otp's own SNMP card. Into OUT.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const OUT = process.argv[2] || '/tmp/claude-0/zconf2';
const HOSTID = process.argv[3] || '10684';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await (await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 })).newPage();
  await p.goto('http://127.0.0.1:8088/index.php');
  await p.fill('#name', 'Admin'); await p.fill('#password', 'zabbix'); await p.click('#enter');
  await p.waitForTimeout(2000);
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=host.list&filter_name=otp1&filter_set=1');
  await p.waitForTimeout(2500);
  await p.screenshot({ path: OUT + '/1-hosts.png' });
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=host.edit&hostid=' + HOSTID);
  await p.waitForTimeout(3000);
  /* the SNMP interface's details opened (the arrow before "SNMP") */
  await p.mouse.click(425, 347);
  await p.waitForTimeout(1200);
  await p.screenshot({ path: OUT + '/2-host-snmp-interface.png', fullPage: true });
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=latest.view&hostids%5B%5D=' + HOSTID + '&filter_set=1');
  await p.waitForTimeout(3000);
  await p.screenshot({ path: OUT + '/3-latest-data.png' });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
  const q = await ctx.newPage();
  await q.goto('https://127.0.0.1/admin/'); await q.waitForTimeout(1000);
  await q.fill('#in-name', 'admin'); await q.fill('#in-pass', PW); await q.keyboard.press('Enter');
  await q.waitForTimeout(2500);
  await q.goto('https://127.0.0.1/admin/#settings/monitor'); await q.reload(); await q.waitForTimeout(5000);
  await q.evaluate(() => { const e = document.querySelector('.set-item[data-key="snmp"]'); if (e) e.scrollIntoView({block: 'start'}); window.scrollBy(0, -120); });
  await q.waitForTimeout(600);
  await q.screenshot({ path: OUT + '/4-otp-snmp-settings.png' });
  await q.evaluate(() => { const e = document.getElementById('snmp-host'); if (e) e.scrollIntoView({block: 'start'}); window.scrollBy(0, -80); });
  await q.waitForTimeout(600);
  await q.screenshot({ path: OUT + '/5-otp-snmp-state.png' });
  await b.close();
  console.log('done');
})().catch(e => { console.log('FAIL ' + e); process.exit(1); });
