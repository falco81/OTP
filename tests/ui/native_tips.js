const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1500,height:1000}});
  const errs=[]; p.on('pageerror', e=>errs.push(String(e)));
  const scan = async (label) => {
    // hover over a sample of everything so lazily drawn bits appear, then collect native tooltips
    return await p.evaluate((label) => {
      const vis = e => { const r=e.getBoundingClientRect(); return r.width>0 && r.height>0; };
      const out=[];
      document.querySelectorAll('[title]').forEach(e => { if (!e.getAttribute('title')) return; if (e.closest('#modal[hidden]')) return;
        out.push({where:label, kind: e.dataset.explains ? 'title+ours' : 'title', tag:e.tagName, id:e.id, cls:(e.className&&e.className.baseVal!==undefined?e.className.baseVal:e.className||'').toString().slice(0,40), text:(e.textContent||'').trim().slice(0,30), title:e.getAttribute('title').slice(0,60), visible:vis(e)}); });
      document.querySelectorAll('svg title').forEach(t => out.push({where:label, kind:'svg-title', tag:'title', text:(t.textContent||'').slice(0,60), title:'', visible:true}));
      return out;
    }, label);
  };
  const all=[];
  await p.goto('http://localhost:28080/'); await p.waitForTimeout(1500); all.push(...await scan('portal'));
  await p.goto('http://localhost:28080/admin/index.php'); await p.waitForTimeout(1200); all.push(...await scan('admin-login'));
  await p.fill('input[type=text], input[name=name]', 'admin').catch(()=>{});
  await p.fill('input[type=password]', 'Test-Admin-Pass-149!'); await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  const panes = await p.$$eval('[data-pane]', els => [...new Set(els.map(e => e.getAttribute('data-pane')))]);
  const targets = ['#overview','#tokens','#log','#test','#enrol','#events'].concat(panes.map(x=>'#settings/'+x));
  for (const h of targets) { await p.goto('http://localhost:28080/admin/index.php'+h); await p.waitForTimeout(2300); all.push(...await scan(h)); }
  const seen = {};
  for (const x of all) { const k = x.kind+'|'+x.tag+'|'+x.cls+'|'+x.title; if (seen[k]) { seen[k].n++; continue; } seen[k] = Object.assign({n:1}, x); }
  console.log(JSON.stringify(Object.values(seen), null, 0).replace(/\},\{/g,'}\n{'));
  console.log('errors', errs.slice(0,5)); await b.close();
})();
