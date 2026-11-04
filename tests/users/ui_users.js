// ui_users.js - 1.0.240 on the installed pages, in Chromium: Settings -> SSH keys - "Whose keys" lists the normal users,
// a user's keys shown (a key put on for her beforehand), the node's facts for her; Settings -> About - the console at
// login, its "normal users" choice. English and Czech, wide and narrow; no sideways scroll, no errors.
// Before: useradd -m -s /bin/bash otpu_carol, a key in ~otpu_carol/.ssh/authorized_keys; after: userdel -r otpu_carol.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  fs.mkdirSync('/tmp/claude-0/usersui', { recursive: true });
  for (const lang of ['en', 'cs']) {
    for (const width of [1200, 390]) {
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
      await p.goto('https://127.0.0.1/admin/#settings/sshkeys');
      await p.reload();
      await p.waitForSelector('.sk-who select', { timeout: 20000 });
      await p.waitForFunction(() => [...document.querySelectorAll('.sk-who select option')].some(o => o.value === 'otpu_carol'), null, { timeout: 30000 }).catch(() => {});
      const opts = await p.$$eval('.sk-who select option', x => x.map(o => o.value));
      ok(tag + '"Whose keys": root and carol', opts[0] === 'root' && opts.includes('otpu_carol'), opts);
      const nav = await p.textContent('[data-pane="sshkeys"]');
      ok(tag + 'the pane is "SSH keys"', lang === 'en' ? /^\s*SSH keys\s*$/.test(nav) : /SSH klíče/.test(nav), nav);
      await p.selectOption('.sk-who select', 'otpu_carol');
      await p.waitForFunction(() => /carol@laptop/.test(document.querySelector('#sk-host').textContent), null, { timeout: 30000 }).catch(() => {});
      const host = await p.textContent('#sk-host');
      ok(tag + 'her key shown, by its comment', /carol@laptop/.test(host), host.slice(0, 500));
      ok(tag + '...the card is hers, not root\'s ("A key for otpu_carol")', /otpu_carol/.test(await p.textContent('#sk-host .card.full:nth-of-type(2) h2').catch(() => '')) || /(A key for|Klíč pro)\s*otpu_carol/.test(host), host.slice(0, 300));
      ok(tag + '...her file named on the node', /\/home\/otpu_carol\/\.ssh\/authorized_keys/.test(host));
      ok(tag + '...no root-only warning about PermitRootLogin', !/PermitRootLogin no/.test(host));
      let wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'SSH keys: no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/usersui/keys-' + lang + '-' + width + '.png', fullPage: true });
      await p.selectOption('.sk-who select', 'root');
      await p.waitForTimeout(500);
      ok(tag + 'back to root: root\'s card', /(A key for root|Klíč pro root)/.test(await p.textContent('#sk-host')));
      await p.goto('https://127.0.0.1/admin/#settings/about');
      await p.waitForSelector('.con-users .acct-pick', { timeout: 20000 });
      ok(tag + 'the console at login: "normal users" picked, nothing to type', !(await p.$('.con-users input[type=text], .con-users select')));
      await p.click('.con-users .acct-pick summary');
      await p.waitForFunction(() => document.querySelectorAll('.con-users .acct-pick[open] .acct-row').length > 2, null, { timeout: 30000 }).catch(() => {});
      const cu = await p.$$eval('.con-users .acct-pick[open] .acct-row', x => x.map(o => o.textContent.trim()));
      ok(tag + '...nobody, every normal user, then the users (no root)', /Nobody|Nikdo/.test(cu[0]) && /Every normal user|Všichni běžní/.test(cu[1])
         && cu.some(t => t.includes('otpu_carol')) && !cu.some(t => t.endsWith('root')), cu);
      const rows = await p.$$('.con-users .acct-pick[open] .acct-row input');
      await rows[2].click();
      await p.waitForTimeout(200);
      const chip = await p.$$eval('.con-users .acct-pick summary .acct-chip', x => x.map(c => c.textContent));
      ok(tag + '...a user ticked: shown as a chip', chip.length === 1, chip);
      const changed = await p.evaluate(() => document.querySelector('.con-users').closest('.kv-row').classList.contains('changed'));
      ok(tag + '...the row marked changed (the save bar does it)', changed);
      const lefts = await p.$$eval('.con-row .con-users', x => x.map(e => Math.round(e.getBoundingClientRect().left)));
      ok(tag + '...the pickers one under another', lefts.length < 2 || lefts.every(v => v === lefts[0]), lefts);
      wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'About: no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/usersui/about-' + lang + '-' + width + '.png', fullPage: false });
      ok(tag + 'no errors on the pages', !errs.length, errs.join(' | '));
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
