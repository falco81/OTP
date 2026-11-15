// zshots.js - the dashboard of "otp by SNMP" in Zabbix 7.0, each page, in a real Chromium
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const OUT = process.argv[2] || '/tmp/claude-0/zshots';
const HOSTID = process.argv[3] || '10684';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await (await b.newContext({ viewport: { width: 1680, height: 1050 }, deviceScaleFactor: 2 })).newPage();
  await p.goto('http://127.0.0.1:8088/index.php');
  await p.fill('#name', 'Admin'); await p.fill('#password', 'zabbix'); await p.click('#enter');
  await p.waitForTimeout(2000);
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=host.dashboard.view&hostid=' + HOSTID + '&from=now-30m&to=now');
  await p.waitForTimeout(9000);
  // the time filter folded, the slideshow stopped
  if (await p.isVisible('text=Last 2 days').catch(() => false)) await p.click('text=Last 30 minutes >> nth=0').catch(() => {});
  await p.click('button:has-text("Stop slideshow")').catch(() => {});
  await p.waitForTimeout(1500);
  const tabs = await p.$$('.dashboard-navigation-tabs li, .sortable-item');
  const names = await p.$$eval('.dashboard-navigation-tabs li', l => l.map(x => x.textContent.trim())).catch(() => []);
  console.log('pages: ' + JSON.stringify(names));
  for (let i = 0; i < Math.max(names.length, 1); i++) {
    if (names.length) {
      await p.click('.dashboard-navigation-tabs li >> nth=' + i);
      await p.waitForTimeout(8000);
    }
    await p.screenshot({ path: OUT + '/' + String(i + 1).padStart(2, '0') + '-' + (names[i] || 'page').replace(/[^A-Za-z0-9]+/g, '-') + '.png', fullPage: true });
  }
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=problem.view&hostids%5B%5D=' + HOSTID);
  await p.waitForTimeout(4000);
  await p.screenshot({ path: OUT + '/06-problems.png' });
  await p.goto('http://127.0.0.1:8088/zabbix.php?action=latest.view&hostids%5B%5D=' + HOSTID + '&filter_set=1');
  await p.waitForTimeout(4000);
  await p.screenshot({ path: OUT + '/07-latest-data.png' });
  await b.close();
})().catch(e => { console.log('FAIL ' + e); process.exit(1); });
