// ui_dirpw.js - each directory's cap of wrong passwords and the domain's policy (1.0.232), in Chromium on the
// installed pages. Needs the directory R6Dom (portal/ui_firstcode_setup.py up) and the mock AD on 23977.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  for (const [lang, width] of [['en', 1500], ['cs', 1500], ['cs', 390]]) {
    const tag = lang + '@' + width + ': ';
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1100 } });
    await ctx.addCookies([{ name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/' }]);
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errs.push(m.text()); });
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
    await p.reload(); await p.waitForTimeout(1500);
    const api = async (body) => p.evaluate(async (bd) => { const r = await fetch('?api=directories', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(bd)}); return r.json(); }, body);
    await api({action: 'pw_caps_save', caps: {R6Dom: {tries: null, window_min: null}}});
    await p.goto('https://127.0.0.1/admin/#settings/guard');
    await p.waitForSelector('.dp-dir', { timeout: 15000 });
    ok(tag + 'the directory listed, as the setting above', /R6Dom/.test(await p.textContent('#dp-list')));
    await p.locator('.dp-dir').filter({ hasText: 'R6Dom' }).locator('.dp-head button').click();
    await p.waitForSelector('.dp-rec', { timeout: 15000 });
    const t = await p.textContent('.dp-dir');
    ok(tag + 'the lockout read: 5 wrong passwords, 30 min', /\b5\b/.test(t) && /30 min/.test(t), t.slice(0, 300));
    if (lang === 'cs') ok(tag + 'in Czech', /Zamykání účtů/.test(t) && /Politika hesel/.test(t) && /Doporučeno/.test(t), t.slice(0, 300));
    ok(tag + 'the password policy and the fine-grained one shown', /Admins PSO/.test(t) && /24/.test(t));
    await p.evaluate(() => document.querySelector('.dp-dir').scrollIntoView());
    await p.waitForTimeout(300);
    await p.screenshot({ path: '/tmp/claude-0/r10ui/dp-' + lang + '-' + width + '.png', fullPage: false });
    await p.click('.dp-rec button');
    await p.waitForTimeout(400);
    const dirty = await p.evaluate(() => document.getElementById('save-bar').classList.contains('dirty'));
    ok(tag + 'Use it: filled in, the save bar says a change waits', dirty);
    let saved = await api({action: 'pw_caps'});
    let d = saved.directories.find(x => x.name === 'R6Dom');
    ok(tag + '...nothing saved yet', d.tries === null || d.tries === undefined, JSON.stringify(d));
    const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    ok(tag + 'no sideways scroll', wide);
    await p.click('#set-save');
    await p.waitForTimeout(1500);
    saved = await api({action: 'pw_caps'});
    d = saved.directories.find(x => x.name === 'R6Dom');
    ok(tag + 'Save the changes: its own cap 2 in 30 min kept', d.tries === 2 && d.window_min === 30, JSON.stringify(d));
    await api({action: 'pw_caps_save', caps: {R6Dom: {tries: null, window_min: null}}});
    ok(tag + 'no script errors', !errs.length, errs.join(' | '));
    await ctx.close();
  }
  {
    const ctx = await b.newContext({ ignoreHTTPSErrors: true });
    const p = await ctx.newPage();
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2000);
    await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL crashed', e); process.exit(1); });
