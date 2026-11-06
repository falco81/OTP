// ui_perf_ha.js - 1.0.253: the meter with two nodes, drawn: the answers of ?api=load given another
// node ("nodeb", its readings a second apart as its row brings them, its clock 40 s ahead). A group
// for each node with its name, both graphs moved by the same animation, the other node's panel,
// the other node late when it says nothing; what fits at 1900 / 1500 / 1200 wide.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1900, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  let late = false, sent = 0, DET = null;
  await p.route(/[?&]api=load\b/, async (route) => {
    const r = await route.fetch();
    let d;
    try { d = await r.json(); } catch (e) { await route.fulfill({ response: r }); return; }   /* the pages' limit: as it came */
    const now = Date.now() / 1000 + 40, hist = [];
    const since = (/since=([^&]*)/.exec(route.request().url()) || [])[1] || '';
    const from = (decodeURIComponent(since).split(',').filter(x => /^nodeb:/.test(x))[0] || '').split(':')[1];
    for (let t = Math.floor(now) - 8; t <= now - 3; t++) if (!from || t > +from) hist.push({at: t, cpu: 30 + 20 * Math.sin(t / 5), mem: 40, disk_rd: 1e6 * (1 + Math.sin(t / 3)), disk_wr: 0, net_rx: 2e5, net_tx: 1e5});
    if (!sent) for (let t = Math.floor(now) - 100; t < now - 8; t++) hist.unshift({at: t, cpu: 30, mem: 40, disk_rd: 1e6, disk_wr: 0, net_rx: 2e5, net_tx: 1e5});
    hist.sort((a, c) => a.at - c.at);
    sent++;
    d.others = [{node: 'nodeb', late, now: late ? null : {at: now, cpu: 33, cores: 8, mem_total: 32e9, mem_used: 12e9, load: [1, 1, 1], disk_rd: 1e6, disk_wr: 0, net_rx: 2e5, net_tx: 1e5},
                 hist: late ? [] : hist}];
    /* the other node's own details when its panel asks (1.0.258): this node's, under its name */
    if (d.detail) DET = d.detail;
    if (/detail_node=/.test(route.request().url()) && !late) {
      if (!DET) {
        try {
          const r2 = await route.fetch({ url: route.request().url().replace(/detail_node=[^&]*/, 'detail=1') });
          DET = (await r2.json()).detail || null;
        } catch (e) {}          /* the pages' own limit of asks a second: the next one then */
      }
      if (DET) d.others[0].detail = DET;
    }
    await route.fulfill({ response: r, json: d });
  });
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate(async () => {
    await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({settings: {perf_meter: true}})});
    await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en', hload: 'graphs', hpanel: 'tiles'})});
  });
  sent = 0; await p.reload(); await p.waitForTimeout(12000);
  const groups = await p.$$eval('#hload .hl-node', a => a.map(g => g.querySelector('.hl-name').textContent));
  ok('a group for each node, with its name', groups.length === 2 && groups[1] === 'nodeb', JSON.stringify(groups));
  const g = await p.evaluate(() => {
    const svgs = [...document.querySelectorAll('#hload .hl-peer svg.hl-live')];
    const d = svgs.map(s => (s.querySelector('.hl-line').getAttribute('d') || '').split(/[ML]/).filter(Boolean).length);
    const box = svgs[0] && svgs[0].getBoundingClientRect();
    // where the newest drawn point of nodeb is now, on the screen: near the right edge, not beyond the clock's 40 s
    const line = svgs[0] && svgs[0].querySelector('.hl-line'), bb = line && line.getBoundingClientRect();
    return {d, right: bb && box ? Math.round(box.right - bb.right) : null, w: box && Math.round(box.width)};
  });
  ok('the other node\'s graphs drawn from its readings', g.d.length >= 2 && g.d.every(n => n >= 20), JSON.stringify(g));
  ok('...by its own clock: its line up to the right edge, the newest waiting just beyond it (40 s ahead or not)', g.right !== null && g.right >= -8 && g.right < 8, JSON.stringify(g));
  await p.screenshot({ path: '/tmp/claude-0/perfui/ha-header.png', clip: { x: 0, y: 0, width: 1900, height: 70 } });
  await p.hover('#hload .hl-peer [data-k="cpu"]'); await p.waitForTimeout(1500);
  const pan = await p.evaluate(() => { const x = document.getElementById('hload-panel'); return x && !x.hidden ? x.textContent : ''; });
  ok('the other node\'s panel: its numbers, its name', /nodeb/.test(pan) && /33 %/.test(pan), pan.slice(0, 200));
  await p.waitForTimeout(3500);
  const pan2 = await p.evaluate(() => { const x = document.getElementById('hload-panel'); return x && !x.hidden ? x.textContent : ''; });
  ok('...then its own details, as this node\'s (1.0.258)', !/its own pages/.test(pan2) && /nodeb/.test(pan2) && /CPU 0/.test(pan2), pan2.slice(0, 200));
  await p.screenshot({ path: '/tmp/claude-0/perfui/ha-panel.png', clip: { x: 0, y: 0, width: 1900, height: 450 } });
  await p.mouse.move(900, 700); await p.waitForTimeout(600);
  const fits = async (w) => {
    await p.setViewportSize({ width: w, height: 900 }); await p.waitForTimeout(500);
    return p.evaluate(() => {
      const h = document.querySelector('header h1').getBoundingClientRect(), bt = document.querySelector('header .btnrow').getBoundingClientRect();
      return {row: Math.abs(h.top - bt.top) < 20, shown: [...document.querySelectorAll('#hload [data-k]')].filter(x => x.offsetParent).map(x => (x.dataset.node || 'here') + ':' + x.dataset.k).join()};
    });
  };
  for (const w of [1900, 1500, 1200]) {
    const f = await fits(w);
    ok(w + ' wide: the header in one row (' + f.shown + ')', f.row && f.shown.length, JSON.stringify(f));
  }
  await p.setViewportSize({ width: 1900, height: 900 });
  late = true; await p.waitForTimeout(4500);
  ok('the other node not heard: its group said late', !!(await p.$('#hload .hl-peer.hl-late')));
  ok('no errors', !errs.length, errs.join(' | '));
  await p.evaluate(async () => { await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({settings: {perf_meter: false}})}); });
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
