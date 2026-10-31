const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1920, height: 1000 } });
  const pg = await ctx.newPage();
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.goto('https://127.0.0.1/admin/#settings/osup'); await pg.waitForTimeout(3500);
  const r = await pg.evaluate(() => {
    const pane = document.getElementById('pane-osup');
    const grid = document.createElement('div'); grid.className = 'pw-grid'; grid.id = 'test-grid';
    for (const me of [true, false]) {
      const c = document.createElement('div'); c.className = 'card pw-node';
      const hd = document.createElement('div'); hd.className = 'pw-head';
      hd.innerHTML = '<span class="dot ok"></span><b>otp' + (me ? 1 : 2) + '</b>' + (me ? '<span class="tag info">this page</span>' : '') +
        '<span class="tag warn">16 waiting</span><span class="tag info">restart after the update</span>';
      c.appendChild(hd); const p = document.createElement('p'); p.textContent = 'UPDATES WAITING 16'; c.appendChild(p);
      grid.appendChild(c);
    }
    pane.insertBefore(grid, pane.firstChild);
    const out = [];
    grid.querySelectorAll('.card').forEach(c => { const cr = c.getBoundingClientRect(); c.querySelectorAll('.tag').forEach(t => { const tr = t.getBoundingClientRect(); out.push([t.textContent, Math.round(tr.right) <= Math.round(cr.right) - 1, t.scrollWidth <= t.clientWidth]); }); });
    grid.scrollIntoView(); return out;
  });
  console.log(JSON.stringify(r));
  await pg.locator('#test-grid').screenshot({ path: '/tmp/claude-0/ui/pwhead.png' });
  await b.close();
})();
