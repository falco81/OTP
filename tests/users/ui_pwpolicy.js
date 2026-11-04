// ui_pwpolicy.js - 1.0.245 Settings -> Local users -> Password policy on the installed pages, in Chromium: the card
// with each node's light, off by default (nothing to fill in), switched on - the three columns of rules; saved, put
// in by the node (pwquality's drop-in there), the lights "as set here", the table of what is in effect; given back to
// the system - the drop-in gone, login.defs as it was. English and Czech, wide and narrow; no sideways scroll.
// The root helper is played by /tmp/claude-0/helperloop.sh.
const { chromium } = require('playwright');
const fs = require('fs');
const crypto = require('crypto');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const md5 = f => crypto.createHash('md5').update(fs.readFileSync(f)).digest('hex');
const DEFS = md5('/etc/login.defs');
const DROP = '/etc/security/pwquality.conf.d/50-otp.conf';
async function signIn(b, lang, width) {
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
  const p = await ctx.newPage();
  p._errs = [];
  p.on('pageerror', e => p._errs.push(String(e)));
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
  await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
  await p.goto('https://127.0.0.1/admin/#settings/osusers');
  await p.reload();
  await p.waitForSelector('.pwp-card', { timeout: 40000 }).catch(() => {});
  return [ctx, p];
}
(async () => {
  const b = await chromium.launch();
  fs.mkdirSync('/tmp/claude-0/osuui', { recursive: true });
  // switched on and saved, in English, wide
  {
    const [ctx, p] = await signIn(b, 'en', 1300);
    ok('the card is there, with a light for the node', !!(await p.$('.pwp-card')) && (await p.$$('.pwp-card .pwp-state .hs-light')).length >= 1);
    ok('...off: no rules to fill in', (await p.$$('.pwp-card .pwp-grid')).length === 0);
    await p.click('.pwp-card .osu-chk .sw');
    await p.waitForSelector('.pwp-card .pwp-grid', { timeout: 5000 }).catch(() => {});
    const cols = await p.$$eval('.pwp-card .pwp-col h3', x => x.map(h => h.textContent));
    ok('switched on: three columns of rules', cols.length === 3, cols);
    const nums = await p.$$('.pwp-card .pwp-col input.pwp-num');
    await nums[0].fill('14');
    await nums[0].dispatchEvent('change');
    await p.screenshot({ path: '/tmp/claude-0/osuui/pwp-en-1300.png', fullPage: true });
    await p.click('.pwp-card .btnrow button.primary');
    await p.waitForFunction(() => /as set here/.test((document.querySelector('.pwp-card .pwp-state') || {}).textContent || ''), null, { timeout: 60000 }).catch(() => {});
    ok('saved: the node says "as set here"', /as set here/.test(await p.textContent('.pwp-card .pwp-state')));
    ok('...pwquality\'s drop-in on the machine, minlen 14', fs.existsSync(DROP) && /minlen = 14/.test(fs.readFileSync(DROP, 'utf8')));
    await p.click('.pwp-now summary').catch(() => {});
    const tbl = await p.textContent('.pwp-now').catch(() => '');
    ok('...in effect on the node: 14 characters', /Characters at least\s*14/.test(tbl), tbl.slice(0, 300));
    ok('no errors', !p._errs.length, p._errs.join(' | '));
    await ctx.close();
  }
  for (const lang of ['en', 'cs']) {
    for (const width of [1300, 390]) {
      const tag = lang + '@' + width + ': ';
      const [ctx, p] = await signIn(b, lang, width);
      const h = await p.textContent('.pwp-card h2').catch(() => '');
      ok(tag + 'the card\'s name', lang === 'en' ? /Password policy/.test(h) : /Politika hesel/.test(h), h);
      ok(tag + 'on: the rules shown', (await p.$$('.pwp-card .pwp-col')).length === 3);
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/osuui/pwp-' + lang + '-' + width + '.png', fullPage: true });
      ok(tag + 'no errors', !p._errs.length, p._errs.join(' | '));
      await ctx.close();
    }
  }
  // given back to the system
  {
    const [ctx, p] = await signIn(b, 'en', 1300);
    await p.click('.pwp-card .osu-chk .sw');
    await p.click('.pwp-card .btnrow button.primary');
    await p.waitForFunction(() => /the system's own/.test((document.querySelector('.pwp-card .pwp-state') || {}).textContent || ''), null, { timeout: 60000 }).catch(() => {});
    ok('given back: "the system\'s own"', /the system's own/.test(await p.textContent('.pwp-card .pwp-state')));
    ok('...the drop-in gone, login.defs as it was', !fs.existsSync(DROP) && md5('/etc/login.defs') === DEFS);
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
