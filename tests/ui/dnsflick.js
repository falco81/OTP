const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 950 } });
  const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  const pos = () => pg.evaluate(() => [...document.querySelectorAll('.acme-dns th, .acme-dns td .dns-val button')].map(x => Math.round(x.getBoundingClientRect().x)).join(','));
  await pg.goto('https://127.0.0.1/admin/#settings/acme'); await pg.waitForTimeout(4000);
  const a = await pos();
  await pg.reload(); await pg.waitForTimeout(4000);
  const b2 = await pos();
  const s = []; const chk = pg.locator('.acme-dns button', { hasText: /Check DNS|Zkontrolovat DNS/ });
  await chk.click(); for (let i = 0; i < 30; i++) { s.push(await pos()); await pg.waitForTimeout(200); }
  console.log('load  ', a); console.log('F5    ', b2); console.log('check ', [...new Set(s)].join(' || '));
  await (await pg.$('.acme-dns')).screenshot({ path: '/tmp/claude-0/ui/acme_dns.png' });
  await pg.setViewportSize({ width: 420, height: 900 }); await pg.waitForTimeout(500);
  const ov = await pg.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  console.log('page wider than phone:', ov, 'errors', errs.length);
  await b.close();
})();
