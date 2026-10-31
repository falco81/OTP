const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 900 } });
  const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.goto('https://127.0.0.1/admin/#settings/acme'); await pg.waitForTimeout(4000);
  await pg.evaluate(() => { const t = AC.d.targets[0]; AC.d.targets.push(Object.assign({}, t, {target: 'vip', name: 'otp.falco81.net', wanted: true})); t.wanted = true; t.name = t.name || 'otp1.falco81.net'; drawAcme(); });
  await pg.waitForTimeout(500);
  await (await pg.$('#ac-host')).screenshot({ path: '/tmp/claude-0/ui/orderall.png', clip: undefined });
  await pg.locator('.ac-all button').click(); await pg.waitForTimeout(600); await pg.locator('.ac-pick .sw').nth(1).click(); await pg.waitForTimeout(300);
  await pg.screenshot({ path: '/tmp/claude-0/ui/orderall2.png' });
  console.log('errors', errs.length);
  await b.close();
})();
