const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1100 } });
  const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.goto('https://127.0.0.1/admin/#settings/proxy'); await pg.waitForTimeout(4000);
  await (await pg.$('#pane-proxy')).screenshot({ path: '/tmp/claude-0/ui/proxy.png' });
  console.log('errors', errs.length);
  await b.close();
})();
