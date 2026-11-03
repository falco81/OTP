// ui_selinux.js - the SELinux card (1.0.233) on the installed pages: a card a node, the mode, what otp needs,
// the steps offered as the mode allows, the confirmation before one, Czech, a phone's width.
// States are put into the database by ui_selinux_seed.py (a: permissive not ready + enforcing; b: disabled + made ready).
const { chromium } = require('playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');
const R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const seed = s => execFileSync('python3', [__dirname + '/ui_selinux_seed.py', s]);
(async () => {
  const b = await chromium.launch();
  try {
    for (const [lang, width] of [['en', 1500], ['cs', 1500], ['cs', 390]]) {
      const tag = lang + '@' + width + ': ';
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1100 } });
      await ctx.addCookies([{ name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/' }]);
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e)));
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
      await p.keyboard.press('Enter');
      await p.waitForTimeout(2500);
      await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
      seed('a');
      await p.goto('https://127.0.0.1/admin/#settings/hisec');
      await p.reload();
      await p.waitForTimeout(3500);
      const nodes = p.locator('.se-node');
      ok(tag + 'a card a node (2)', await nodes.count() === 2, await nodes.count());
      const vm = nodes.nth(0), o2 = nodes.nth(1);
      const tv = await vm.innerText(), t2 = await o2.innerText();
      ok(tag + 'vm permissive, otp2 enforcing', /permissive/i.test(await vm.locator('.se-mode').innerText()) && /enforcing/i.test(await o2.locator('.se-mode').innerText()));
      ok(tag + 'the wrong label shown with what it should be', tv.includes('var_run_t → httpd_var_run_t') || tv.includes('var_run_t  →  httpd_var_run_t'), tv.slice(0, 400));
      const enf = vm.locator('button', { hasText: lang === 'cs' ? 'Přepnout na enforcing' : 'Switch to enforcing' });
      ok(tag + 'not ready: "Switch to enforcing" there but greyed out', await enf.count() === 1 && await enf.isDisabled());
      ok(tag + 'enforcing node offers only "Back to permissive"', await o2.locator('button').count() === 1 &&
         /permissive/i.test(await o2.locator('button').innerText()));
      if (lang === 'cs') ok(tag + 'in Czech', /Na enforcing zatím není připraveno/.test(tv) && /Od startu stroje nic neodepřeno/.test(t2) && /API token, který čtou stránky/.test(tv), tv.slice(0, 300));
      const scroll = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      ok(tag + 'no horizontal scroll', !scroll);
      await o2.locator('button').click();
      await p.waitForTimeout(600);
      const modal = p.locator('.modal');
      ok(tag + '"Back to permissive" asks first', await modal.count() > 0 && /permissive/i.test(await modal.first().innerText()));
      await p.keyboard.press('Escape');
      await p.waitForTimeout(400);
      await p.locator('.se-card').scrollIntoViewIfNeeded();
      await p.locator('.se-card').screenshot({ path: '/tmp/claude-0/r11ui/se-' + lang + '-' + width + '-a.png' });
      seed('b');
      await p.reload();
      await p.waitForTimeout(3500);
      const n0 = p.locator('.se-node').nth(0), n1 = p.locator('.se-node').nth(1);
      ok(tag + 'disabled: "Make it ready (permissive)" offered', /permissive/i.test(await n0.locator('button').innerText()));
      ok(tag + 'made ready: waiting for a restart, no button', await n1.locator('button').count() === 0 &&
         (lang === 'cs' ? /čeká se na restart/.test(await n1.innerText()) : /waiting for a restart/.test(await n1.innerText())));
      ok(tag + 'no page errors', errs.length === 0, errs.join(' | '));
      await p.locator('.se-card').scrollIntoViewIfNeeded();
      await p.locator('.se-card').screenshot({ path: '/tmp/claude-0/r11ui/se-' + lang + '-' + width + '-b.png' });
      await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
      await ctx.close();
    }
  } finally {
    seed('off');
    await b.close();
  }
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
