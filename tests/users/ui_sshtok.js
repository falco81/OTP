// ui_sshtok.js - 1.0.241: Add an SSH token offers the account names from the nodes (root, the users who may sign in).
// Before: useradd -m -s /bin/bash otpu_carol, the root helper running; after: userdel -r otpu_carol.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'cs']) {
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1200, height: 900 } });
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
    await p.goto('https://127.0.0.1/admin/#settings/sshd'); await p.reload();
    await p.waitForSelector('.sd-tokens .btn.primary', { timeout: 30000 });
    await p.click('.sd-tokens .btn.primary');
    await p.waitForSelector('#sd-who-list', { state: 'attached', timeout: 10000 });
    await p.waitForFunction(() => [...document.querySelectorAll('#sd-who-list option')].some(o => o.value === 'otpu_carol'), null, { timeout: 30000 }).catch(() => {});
    const opts = await p.$$eval('#sd-who-list option', x => x.map(o => o.value));
    ok(lang + ': the account offers root and the users of the nodes', opts[0] === 'root' && opts.includes('otpu_carol'), opts);
    const list = await p.$eval('#modal input.mono', i => i.getAttribute('list'));
    ok(lang + ': ...tied to the account box', list === 'sd-who-list', list);
    ok(lang + ': no errors', !errs.length, errs.join(' | '));
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
