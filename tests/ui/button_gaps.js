// Buttons side by side with no room between them, on every page and pane (1.0.159).
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1500, height: 1000}});
  await p.goto('http://localhost:28080/admin/index.php'); await p.waitForTimeout(800);
  await p.fill('input:not([type=password])', 'admin').catch(() => {});
  await p.fill('input[type=password]', 'Test-Admin-Pass-149!'); await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  const panes = await p.$$eval('[data-pane]', els => [...new Set(els.map(e => e.getAttribute('data-pane')))]);
  const targets = ['#overview', '#tokens', '#log', '#test', '#enrol', '#events'].concat(panes.map(x => '#settings/' + x));
  const out = [];
  for (const t of targets) {
    await p.goto('http://localhost:28080/admin/index.php' + t); await p.waitForTimeout(1800);
    const got = await p.$$eval('button, a.btn', els => {
      const r = [];
      els.forEach(e => {
        if (!e.offsetWidth || !e.offsetHeight) return;
        let n = e.nextElementSibling;
        while (n && (!n.offsetWidth || n.tagName === 'INPUT')) n = n.nextElementSibling;
        if (!n || !(n.tagName === 'BUTTON' || n.matches('a.btn'))) return;
        const a = e.getBoundingClientRect(), c = n.getBoundingClientRect();
        if (Math.abs(a.top - c.top) > 4) return;
        const gap = c.left - a.right;
        if (gap < 6 && !e.closest('.seg, .tabs, .ctl-rail, nav, .segmented, .pager, .btngroup')) r.push([(e.innerText || e.title || '').trim().slice(0, 30), (n.innerText || n.title || '').trim().slice(0, 30), Math.round(gap)]);
      });
      return r;
    });
    if (got.length) out.push([t, got]);
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
