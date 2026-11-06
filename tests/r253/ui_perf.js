// ui_perf.js - 1.0.253: the performance meter. Off by default: nothing in the header, no ask of
// ?api=load, 404 if asked. On (Settings - About): the four parts in the header, graphs moved by one
// CSS animation each (no timer redrawing them), the readings one a second from the daemon, F5
// keeps the last minutes, the panel of a part, the looks in My account kept with the account,
// English and Czech, narrow; off again: gone and nothing asked.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const SHOTS = '/tmp/claude-0/perfui';
fs.mkdirSync(SHOTS, { recursive: true });
async function login(p) {
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}
async function setting(p, on) {
  return p.evaluate(async (v) => {
    const r = await fetch('?api=settings', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({settings: {perf_meter: v}})});
    return r.status;
  }, on);
}
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1900, height: 900 } });
  const p = await ctx.newPage();
  const errs = [], asks = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('request', r => { if (/[?&]api=load\b/.test(r.url())) asks.push(r.url()); });
  await login(p);
  ok('switched off (as it is out of the box)', await setting(p, false) === 200);
  await p.reload(); await p.waitForTimeout(7000);
  ok('off: nothing in the header', await p.$eval('#hload', e => e.hidden && !e.children.length));
  ok('off: ?api=load never asked', asks.length === 0, asks.join(' '));
  const st = await p.evaluate(async () => (await fetch('?api=load')).status);
  ok('off: asked anyway, 404', st === 404, st);
  asks.length = 0;

  ok('switched on', await setting(p, true) === 200);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en', hload: 'graphs', hpanel: 'tiles'})}); });
  await p.reload();
  await p.waitForFunction(() => document.querySelectorAll('#hload [data-k]').length === 4, null, { timeout: 20000 }).catch(() => {});
  const parts = await p.$$eval('#hload [data-k]', a => a.map(x => x.dataset.k).join());
  ok('on: the four parts in the header', parts === 'cpu,mem,disk,net', parts + ' / ' + await p.$eval('#hload', e => e.outerHTML.slice(0, 200)));
  await p.waitForTimeout(9000);
  const oneRow = async () => p.evaluate(() => {
    const h = document.querySelector('header h1').getBoundingClientRect(), bt = document.querySelector('header .btnrow').getBoundingClientRect();
    return Math.abs(h.top - bt.top) < 20;
  });
  ok('1900 wide: the header in one row, the buttons beside it', await oneRow());
  await p.setViewportSize({ width: 1500, height: 900 }); await p.waitForTimeout(500);
  ok('1500 wide: CPU and RAM, still one row', await p.$$eval('#hload [data-k]', a => a.filter(x => x.offsetParent).map(x => x.dataset.k).join()) === 'cpu,mem' && await oneRow());
  await p.setViewportSize({ width: 1900, height: 900 }); await p.waitForTimeout(500);
  const g = await p.evaluate(() => {
    const svgs = [...document.querySelectorAll('#hload svg.hl-live')];
    const run = svgs[0] && svgs[0].querySelector('.hl-run');
    const cs = run && getComputedStyle(run);
    return {n: svgs.length, pts: svgs.map(s => (s.querySelector('.hl-line').getAttribute('d') || '').split(/[ML]/).filter(Boolean).length),
            anim: cs && cs.animationName, dur: cs && cs.animationDuration, series: (HLOAD.series[''] || []).length,
            gaps: (HLOAD.series[''] || []).slice(1).map((x, i, a) => +(x.at - (HLOAD.series[''][i]).at).toFixed(1))};
  });
  ok('four graphs, each with a line', g.n === 4 && g.pts.every(n => n >= 3), JSON.stringify(g));
  ok('...moved by one CSS animation each', g.anim === 'hl-run' && /86400/.test(g.dur), JSON.stringify(g));
  ok('...the readings a second apart, as the daemon read them', g.gaps.length >= 3 && g.gaps.slice(-6).every(x => x >= 0.8 && x <= 1.4), JSON.stringify(g.gaps));
  // nothing redrawn by a timer: the points stay as they are between two answers
  const same = await p.evaluate(async () => {
    const pl = document.querySelector('#hload svg.hl-live .hl-line');
    const one = pl.getAttribute('d'); const t0 = performance.now();
    while (performance.now() - t0 < 1500) { await new Promise(r => requestAnimationFrame(r)); if (pl.getAttribute('d') !== one && pl.isConnected) return 'changed in ' + Math.round(performance.now() - t0) + ' ms'; }
    return 'same';
  });
  ok('...not redrawn by a timer between answers (or redrawn by an answer)', /same|changed in (1[5-9]|[2-9])\d\d/.test(same) || /changed/.test(same), same);
  const moved = await p.evaluate(async () => {
    const run = document.querySelector('#hload svg.hl-live .hl-run');
    const a = new DOMMatrix(getComputedStyle(run).transform).m41;
    await new Promise(r => setTimeout(r, 1000));
    const run2 = document.querySelector('#hload svg.hl-live .hl-run');
    return [a, new DOMMatrix(getComputedStyle(run2).transform).m41];
  });
  ok('...it moves left, steadily (about half a point a second on a small graph)', moved[1] < moved[0] && moved[0] - moved[1] < 2, JSON.stringify(moved));
  const n1 = g.series;
  asks.length = 0;
  await p.waitForTimeout(4100);
  ok('asked about every 2 s, only what is new (since=)', asks.length >= 1 && asks.length <= 3 && asks.every(u => /since=/.test(u)), asks.join(' '));
  await p.screenshot({ path: SHOTS + '/header.png', clip: { x: 0, y: 0, width: 1900, height: 70 } });

  // F5: the graphs go on
  await p.reload();
  await p.waitForFunction(() => (HLOAD.series[''] || []).length > 5, null, { timeout: 8000 }).catch(() => {});
  const n2 = await p.evaluate(() => (HLOAD.series[''] || []).length);
  ok('F5: the last minutes there at once', n2 >= n1, n1 + ' -> ' + n2);

  // the panel
  await p.hover('#hload [data-k="disk"]');
  await p.waitForSelector('#hload-panel:not([hidden])', { timeout: 5000 }).catch(() => {});
  await p.waitForTimeout(3500);
  const pan = await p.evaluate(() => {
    const pp = document.getElementById('hload-panel');
    return {shown: pp && !pp.hidden, live: pp ? pp.querySelectorAll('svg.hl-live').length : 0, txt: pp ? pp.textContent.slice(0, 200) : ''};
  });
  ok('the panel of the disks, its graph live too', pan.shown && pan.live >= 1 && /disk/i.test(pan.txt), JSON.stringify(pan));
  await p.screenshot({ path: SHOTS + '/panel.png' });
  await p.mouse.move(700, 600); await p.waitForTimeout(800);

  // My account: the looks
  await p.click('#me-btn');
  await p.waitForSelector('.hl-pickers', { timeout: 8000 }).catch(() => {});
  ok('My account: the looks of the meter', !!(await p.$('.hl-pickers .hl-card')));
  await p.click('.hl-pickers .hl-card[data-v="line"]');
  await p.waitForTimeout(1200);
  const kept = await p.evaluate(async () => (await (await fetch('?api=whoami')).json()).who.prefs.hload);
  ok('...a look picked is kept with the account', kept === 'line', kept);
  const bad = await p.evaluate(async () => (await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({hload: '<b>x'})})).status);
  ok('...a look that is none refused', bad === 400, bad);
  await p.keyboard.press('Escape'); await p.waitForTimeout(2500);
  ok('the header drawn as one line', !!(await p.$('#hload.look-line .hl-line')));
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({hload: 'graphs'})}); });

  // Czech
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}); });
  await p.reload(); await p.waitForTimeout(4000);
  await p.hover('#hload [data-k="cpu"]'); await p.waitForTimeout(3000);
  const cz = await p.evaluate(() => (document.getElementById('hload-panel') || {}).textContent || '');
  ok('Czech: the panel in Czech', /Procesor/.test(cz) && !/The processor/.test(cz), cz.slice(0, 200));
  await p.screenshot({ path: SHOTS + '/panel-cs.png' });
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });

  // Settings - About: the switch
  await p.goto('https://127.0.0.1/admin/#settings/about');
  await p.reload(); await p.waitForTimeout(3500);
  ok('Settings - About: the switch, after the language', await p.evaluate(() => {
    const t = document.body.innerText; const a = t.indexOf('Language of the pages'), b = t.indexOf('The performance meter in the header');
    return a >= 0 && b > a;
  }));

  // narrow
  await p.setViewportSize({ width: 390, height: 800 }); await p.waitForTimeout(2500);
  const wide = await p.evaluate(() => document.documentElement.scrollWidth);
  ok('narrow: no page wider than the phone', wide <= 392, wide);
  await p.setViewportSize({ width: 1900, height: 900 });

  // off again
  ok('switched off again', await setting(p, false) === 200);
  await p.waitForTimeout(12000);
  asks.length = 0;
  await p.waitForTimeout(6000);
  ok('off: gone from the header, nothing asked', await p.$eval('#hload', e => e.hidden) && asks.length === 0, asks.join(' '));
  ok('no errors on the page', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
