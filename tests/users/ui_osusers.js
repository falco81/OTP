// ui_osusers.js - 1.0.243 Settings -> Local users on the installed pages, in Chromium: root shown and never changed
// (no box to type in, no button that changes it), a user added from the pages (name, full name, password twice,
// sudo), its row with the tags, its popup (the facts per node, the sections), locked from there and shown locked,
// taken away. English and Czech, wide and narrow; no sideways scroll, no errors. The root helper is played by
// /tmp/claude-0/helperloop.sh. Before: no user otpl_ui; after: none.
const { chromium } = require('playwright');
const fs = require('fs');
const { execSync } = require('child_process');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function gone() { try { execSync('userdel -r otpl_ui 2>/dev/null'); } catch (e) { } }
(async () => {
  gone();
  const b = await chromium.launch();
  fs.mkdirSync('/tmp/claude-0/osuui', { recursive: true });
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
      await p.goto('https://127.0.0.1/admin/#settings/osusers');
      await p.reload();
      const nav = await p.textContent('[data-pane="osusers"]');
      ok(tag + 'the pane is in the menu', lang === 'en' ? /Local users/.test(nav) : /Místní uživatelé/.test(nav), nav);
      await p.waitForSelector('.osu-table tbody tr', { timeout: 40000 }).catch(() => {});
      const first = await p.textContent('.osu-table tbody tr:first-child').catch(() => '');
      ok(tag + 'root first, "view only"', /root/.test(first) && (lang === 'en' ? /view only/.test(first) : /jen zobrazit|jen k nahlédnutí/i.test(first)), first);
      ok(tag + '...one button on root, to look', (await p.$$('.osu-root .osu-act button')).length === 1);
      await p.click('.osu-root .osu-act button');
      await p.waitForSelector('#modal:not([hidden])');
      const inputs = await p.$$eval('#modal-body input, #modal-body select, #modal-body textarea', x => x.length);
      const btns = await p.$$eval('#modal-foot button', x => x.map(b => b.textContent.trim()));
      ok(tag + 'root\'s popup: nothing to type, only Close', inputs === 0 && btns.length === 1, [inputs, btns]);
      await p.screenshot({ path: '/tmp/claude-0/osuui/root-' + lang + '-' + width + '.png' });
      await p.click('#modal-foot button');
      if (lang === 'en' && width === 1300) {
        await p.click('.osu-card h2 .right button.primary');
        await p.waitForSelector('#modal:not([hidden])');
        const tb = await p.$$('#modal-body input[type=text], #modal-body input:not([type])');
        await tb[0].fill('otpl_ui');
        await tb[1].fill('UI Test');
        const pw = await p.$$('#modal-body input.masked');
        await pw[0].type('Ui-Pass-243-long');
        await pw[1].type('Ui-Pass-243-long');
        const shown = await pw[0].inputValue();
        ok(tag + 'the password typed shows dots only', !/Ui-Pass/.test(shown), shown);
        const sws = await p.$$('#modal-body .osu-chk .sw');
        ok(tag + 'on/off switches, no boxes to tick', sws.length >= 2 && (await p.$$('#modal-body label.chk input[type=checkbox]')).length === 0);
        await sws[1].click();
        ok(tag + '...a switch turned: sudo on', (await p.$$eval('#modal-body .osu-chk input', x => x.map(i => i.checked)))[1] === true);
        await p.screenshot({ path: '/tmp/claude-0/osuui/add-' + lang + '-' + width + '.png' });
        await p.click('#modal-foot button.primary');
        await p.waitForFunction(() => /otpl_ui/.test(document.querySelector('.osu-table') ? document.querySelector('.osu-table').textContent : ''), null, { timeout: 60000 }).catch(() => {});
        const row = await p.$$eval('.osu-table tbody tr', x => (x.find(r => /otpl_ui/.test(r.textContent)) || {}).textContent || '');
        ok(tag + 'added: its row, its full name, sudo', /otpl_ui/.test(row) && /UI Test/.test(row) && /sudo/.test(row), row);
        let sys = '';
        try { sys = execSync('getent passwd otpl_ui').toString(); } catch (e) { }
        ok(tag + '...a user of the machine', /otpl_ui:x:\d+:\d+:UI Test/.test(sys), sys);
        // SSH keys knows it without a reload of the page (1.0.244)
        await p.click('[data-pane="sshkeys"]');
        await p.waitForFunction(() => [...document.querySelectorAll('.sk-who select option')].some(o => o.value === 'otpl_ui'), null, { timeout: 40000 }).catch(() => {});
        ok(tag + '...in SSH keys\' "Whose keys" without F5', await p.$$eval('.sk-who select option', x => x.some(o => o.value === 'otpl_ui')));
        await p.click('[data-pane="osusers"]');
        await p.waitForSelector('.osu-table tbody tr', { timeout: 20000 }).catch(() => {});
      }
      const has = await p.$$eval('.osu-table tbody tr', x => x.some(r => /otpl_ui/.test(r.textContent)));
      if (has) {
        const rows = await p.$$('.osu-table tbody tr');
        for (const r of rows) {
          if (/otpl_ui/.test(await r.textContent())) { await (await r.$('.osu-act button')).click(); break; }
        }
        await p.waitForSelector('#modal:not([hidden]) .osu-fact');
        const sects = await p.$$eval('#modal-body .osu-sect h3', x => x.map(h => h.textContent));
        ok(tag + 'its popup: the facts, five sections', (await p.$$('#modal-body .osu-fact')).length >= 1 && sects.length === 5, sects);
        const mw = await p.evaluate(() => { const m = document.querySelector('#modal-box'); return m.scrollWidth <= m.clientWidth + 1; });
        ok(tag + '...nothing wider than the popup', mw);
        await p.screenshot({ path: '/tmp/claude-0/osuui/edit-' + lang + '-' + width + '.png' });
        if (lang === 'en' && width === 1300) {
          const lock = await p.$$('#modal-body .osu-sect button');
          for (const bt of lock) { if (/^\s*Lock\s*$/.test(await bt.textContent())) { await bt.click(); break; } }
          await p.waitForFunction(() => [...document.querySelectorAll('.osu-table tbody tr')].some(r => /otpl_ui/.test(r.textContent) && /locked/.test(r.textContent)), null, { timeout: 60000 }).catch(() => {});
          const row = await p.$$eval('.osu-table tbody tr', x => (x.find(r => /otpl_ui/.test(r.textContent)) || {}).textContent || '');
          ok(tag + 'locked from its popup: shown locked', /locked/.test(row), row);
        } else {
          await p.click('#modal-foot button:not(.danger)');
        }
      }
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/osuui/pane-' + lang + '-' + width + '.png', fullPage: true });
      ok(tag + 'no errors on the page', !errs.length, errs.join(' | '));
      await ctx.close();
    }
  }
  // taken away from the pages
  {
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1300, height: 1000 } });
    const p = await ctx.newPage();
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
    await p.goto('https://127.0.0.1/admin/#settings/osusers');
    await p.reload();
    await p.waitForFunction(() => /otpl_ui/.test((document.querySelector('.osu-table') || {}).textContent || ''), null, { timeout: 40000 }).catch(() => {});
    const rows = await p.$$('.osu-table tbody tr');
    for (const r of rows) {
      if (/otpl_ui/.test(await r.textContent())) { await (await r.$('.osu-act button')).click(); break; }
    }
    await p.waitForSelector('#modal:not([hidden]) .osu-fact');
    await p.click('#modal-body .osu-sect:last-child .sw');
    await p.click('#modal-foot button.danger');
    await p.click('.sure-strip button.danger');
    await p.waitForFunction(() => !/otpl_ui/.test((document.querySelector('.osu-table') || {}).textContent || 'otpl_ui'), null, { timeout: 60000 }).catch(() => {});
    let sys = 'x';
    try { sys = execSync('getent passwd otpl_ui').toString(); } catch (e) { sys = ''; }
    ok('taken away from the pages, with its home', !sys && !fs.existsSync('/home/otpl_ui'), sys);
    await ctx.close();
  }
  await b.close();
  gone();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
