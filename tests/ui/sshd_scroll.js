const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1900, height: 950 } });
  const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.goto('https://127.0.0.1/admin/#settings/sshd'); await pg.waitForTimeout(4000);
  const top = () => pg.evaluate(() => { const o = {w: Math.round(scrollY)}; document.querySelectorAll('*').forEach(n => { if (n.scrollTop > 0) o[(n.id || n.className || n.tagName).toString().slice(0, 20)] = Math.round(n.scrollTop); }); const h = [...document.querySelectorAll('#pane-sshd h2')].find(x => /code from otp/.test(x.textContent)); o.h2y = h ? Math.round(h.getBoundingClientRect().y) : null; return JSON.stringify(o); });
  // scroll the main area with the wheel to the code card
  await pg.mouse.move(1000, 500);
  for (let i = 0; i < 6; i++) { await pg.mouse.wheel(0, 300); await pg.waitForTimeout(150); }
  await pg.waitForTimeout(500);
  const shot = async (n) => pg.screenshot({ path: '/tmp/claude-0/ui/ss' + n + '.png' });
  // every visible switch on screen: click its slider with the mouse
  const sws = await pg.$$('#pane-sshd label.sw');
  console.log('switches', sws.length, 'top', await top());
  let done = 0;
  for (const s of sws.slice(2)) {
    await s.evaluate(e => e.scrollIntoView({ block: 'center' })); await pg.waitForTimeout(400);
    const bb = await s.boundingBox(); if (!bb) continue;
    const t0 = await top(); await pg.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2); await pg.waitForTimeout(900);
    const t1 = await top(); console.log('switch at y', Math.round(bb.y), 'scroll', t0, '->', t1); done++;
    await shot(done); if (done >= 3) break;
  }
  // type into the visible text field
  const ins = await pg.$$('#pane-sshd input[type=text], #pane-sshd input:not([type])');
  for (const i of ins) {
    await i.evaluate(e => e.scrollIntoView({ block: 'center' })); await pg.waitForTimeout(400);
    const bb = await i.boundingBox(); if (!bb) continue;
    const t0 = await top(); await pg.mouse.click(bb.x + 10, bb.y + bb.height / 2); await pg.keyboard.type('ab'); await pg.waitForTimeout(900);
    console.log('typed at y', Math.round(bb.y), 'scroll', t0, '->', await top()); break;
  }
  console.log('errors', errs.slice(0, 3)); await b.close();
})();
