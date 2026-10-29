const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1500,height:1000}});
  const errs=[]; p.on('pageerror', e=>errs.push(String(e)));
  await p.goto('http://localhost:28080/admin/index.php'); await p.waitForTimeout(800);
  await p.fill('input[type=text], input[name=name]', 'admin').catch(()=>{});
  await p.fill('input[type=password]', 'Test-Admin-Pass-149!'); await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  const panes = await p.$$eval('[data-pane]', els => els.map(e => e.getAttribute('data-pane')));
  const tabs = ['overview','tokens','log','test','enrol','events'];
  const targets = tabs.map(t=>'#'+t).concat([...new Set(panes)].map(x=>'#settings/'+x));
  const out = [];
  for (const h of targets) {
    await p.goto('http://localhost:28080/admin/index.php'+h); await p.waitForTimeout(2200);
    const bad = await p.evaluate(() => {
      const vis = e => { const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden'; };
      // outermost visible cards
      const cards=[...document.querySelectorAll('.card')].filter(c=>vis(c) && !c.parentElement.closest('.card') && !c.closest('.modal'));
      const res=[];
      for (let i=0;i<cards.length;i++) for (let j=0;j<cards.length;j++) {
        if (i===j) continue;
        const a=cards[i].getBoundingClientRect(), c=cards[j].getBoundingClientRect();
        const overlapX = Math.min(a.right,c.right)-Math.max(a.left,c.left);
        if (overlapX<40) continue;
        const gap=c.top-a.bottom;
        if (gap>-2 && gap<8) res.push({a:(cards[i].querySelector('h2,h3')||{}).textContent||cards[i].id, b:(cards[j].querySelector('h2,h3')||{}).textContent||cards[j].id, gap:Math.round(gap)});
        // horizontal neighbours too
        const overlapY = Math.min(a.bottom,c.bottom)-Math.max(a.top,c.top);
        const hg=c.left-a.right;
        if (overlapY>20 && hg>-2 && hg<8) res.push({a:(cards[i].querySelector('h2,h3')||{}).textContent, b:(cards[j].querySelector('h2,h3')||{}).textContent, hgap:Math.round(hg)});
      }
      return res;
    });
    if (bad.length) out.push([h, bad]);
  }
  console.log(JSON.stringify(out, null, 1)); console.log('errors', errs.slice(0,5)); await b.close();
})();
