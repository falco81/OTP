// ui_hslights.js - 1.0.244 Settings -> High security: under "High security" and "Guard against writes to the
// database" a light for each node, on or off as in effect there; en and cs, wide and narrow; no sideways scroll.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'cs']) {
    for (const width of [1300, 390]) {
      const tag = lang + '@' + width + ': ';
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e)));
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
      await p.keyboard.press('Enter');
      await p.waitForTimeout(2500);
      await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
      await p.goto('https://127.0.0.1/admin/#settings/hisec');
      await p.reload();
      await p.waitForSelector('.set-item[data-key="db_guard"] .hs-lights', { timeout: 30000 }).catch(() => {});
      const api = await p.evaluate(async () => (await (await fetch('?api=hisec')).json()));
      for (const key of ['high_security', 'db_guard']) {
        const chips = await p.$$eval('.set-item[data-key="' + key + '"] .hs-light', x => x.map(c => ({cls: c.className, t: c.textContent})));
        ok(tag + key + ': a light for each node (' + chips.length + ')', chips.length === (api.nodes || []).length && chips.length >= 1, JSON.stringify(chips));
        const me = (api.nodes || []).find(n => n.me) || {};
        const mine = chips.find(c => c.t.indexOf(me.name) >= 0) || {};
        ok(tag + key + ': this node ' + (me[key] ? 'on' : 'off') + ', its light says so', new RegExp('\\b' + (me[key] ? 'on' : 'off') + '\\b').test(mine.cls || ''), JSON.stringify(mine));
      }
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/osuui/hslights-' + lang + '-' + width + '.png', fullPage: false });
      ok(tag + 'no errors on the page', !errs.length, errs.join(' | '));
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
