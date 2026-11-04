// ui_hslights.js - 1.0.246: the lights a node under "High security" and "Guard against writes to the database"
// (1.0.244) gave way to the pill at the right of the card's heading (Settings in a cluster): none drawn any more;
// the switches and their words as they were. English and Czech; no errors.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'cs']) {
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1300, height: 1000 } });
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
    await p.waitForSelector('.set-item[data-key="db_guard"]', { timeout: 30000 });
    await p.waitForTimeout(2500);
    ok(lang + ': the switches there', !!(await p.$('.set-item[data-key="high_security"] .sw')) && !!(await p.$('.set-item[data-key="db_guard"] .sw')));
    ok(lang + ': no lights a node under them any more', (await p.$$('.hs-lights')).length === 0);
    ok(lang + ': no errors', !errs.length, errs.join(' | '));
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
