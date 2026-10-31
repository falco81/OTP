const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 950 } });
  const pg = await ctx.newPage(); pg.setDefaultTimeout(8000);
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.evaluate(() => colsReset()); await pg.evaluate(() => colsSwitch(true));
  for (const [h, sel] of [['#settings/acme', '.acme-dns table'], ['#events', '#ev-table table']]) {
    await pg.goto('https://127.0.0.1/admin/' + h); await pg.waitForTimeout(3500);
    const heads = () => pg.evaluate(s => [...document.querySelector(s).tHead.rows[0].cells].filter(c => !c.classList.contains('col-hidden')).map(c => c.dataset.ck).join(','), sel);
    const ths = pg.locator(sel + ' thead th');
    await ths.nth(0).dragTo(ths.nth(2), { targetPosition: { x: 30, y: 8 } }); await pg.waitForTimeout(500);
    // grip: make column 1 wider
    const g = pg.locator(sel + ' thead th .col-grip').nth(1); const gb = await g.boundingBox();
    await pg.mouse.move(gb.x + gb.width / 2, gb.y + gb.height / 2); await pg.mouse.down(); await pg.mouse.move(gb.x + 80, gb.y + 5, { steps: 6 }); await pg.mouse.up(); await pg.waitForTimeout(600);
    // hide the last column by the menu
    const lastTh = ths.nth(4 > 3 ? 3 : 0); const lb = await lastTh.boundingBox();
    await pg.mouse.click(lb.x + 10, lb.y + 8, { button: 'right' }); await pg.waitForTimeout(300);
    await pg.locator('.cols-menu .cols-mi').first().click(); await pg.waitForTimeout(600);
    const w = () => pg.evaluate(s => [...document.querySelector(s).tHead.rows[0].cells].map(c => c.style.width).join(','), sel);
    const a = [await heads(), await w()];
    await pg.waitForTimeout(6000);                    // the card's own refreshes
    const b1 = [await heads(), await w()];
    await pg.reload(); await pg.waitForTimeout(4500);
    const c = [await heads(), await w()];
    console.log(h, '\n set    ', a.join(' / '), '\n 6 s on ', b1.join(' / '), '\n F5     ', c.join(' / '), '\n kept:', JSON.stringify(a) === JSON.stringify(b1) && JSON.stringify(a) === JSON.stringify(c));
  }
  await pg.evaluate(() => colsReset()); await pg.evaluate(() => colsSwitch(false));
  await b.close();
})();
