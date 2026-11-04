// ui_dbtile.js - 1.0.245: the card "The database" on the overview, clicked - at the top of what opens, why the card
// has its colour, in the colour of the card (green / yellow / red), English and Czech; then the facts as before.
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
      await p.goto('https://127.0.0.1/admin/#overview');
      await p.reload();
      await p.waitForFunction(() => /\b(ok|warn|crit)\b/.test(document.getElementById('card-db').className), null, { timeout: 30000 });
      const level = await p.evaluate(() => ['ok', 'warn', 'crit'].find(c => document.getElementById('card-db').classList.contains(c)));
      await p.click('#card-db');
      await p.waitForSelector('#modal:not([hidden]) .peek-why', { timeout: 20000 }).catch(() => {});
      const why = await p.$eval('#modal-body .peek-why', e => ({t: e.textContent, c: e.className})).catch(() => ({t: '', c: ''}));
      const want = {ok: ['good', /^(Green|Zelená):/], warn: ['warn', /^(Yellow|Žlutá):/], crit: ['bad', /^(Red|Červená):/]}[level];
      ok(tag + 'the card is ' + level + ': its popup says why, first, in its colour', new RegExp('\\b' + want[0] + '\\b').test(why.c) && want[1].test(why.t), JSON.stringify(why));
      ok(tag + '...in its language', lang === 'en' ? /^(Green|Yellow|Red)/.test(why.t) : /^(Zelená|Žlutá|Červená)/.test(why.t), why.t);
      const first = await p.evaluate(() => document.querySelector('#modal-body').firstElementChild.classList.contains('peek-why'));
      ok(tag + '...at the top, the facts under it', first && !!(await p.$('#modal-body .dbheld')));
      await p.screenshot({ path: '/tmp/claude-0/osuui/dbtile-' + lang + '-' + width + '.png' });
      ok(tag + 'no errors', !errs.length, errs.join(' | '));
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
