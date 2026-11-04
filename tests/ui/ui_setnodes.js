// ui_setnodes.js - 1.0.246 Settings in a cluster: in effect on every node? The pill at the right of each card's heading
// of Settings (a dot a node, a line, a refresh icon), drawn from /api/settings/nodes - here answered by the test as a
// cluster would: both in step (green, its words), one behind (amber dot, amber edge, "not yet"), one not heard from
// (red), one of an older version (grey); only on cards of the settings (a sect- box); a card with no heading - the
// pill on its top edge; standalone - nothing; the icon asks again (POST, spins). English and Czech, wide and narrow.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const now = () => Date.now() / 1000;
const STATES = {
  step: n => ({cluster: true, at: now(), nodes: [{name: 'otp1', me: true, alive: true, known: true, seen: true, seen_at: now() - 120, age: 1},
                                                   {name: 'otp2', me: false, alive: true, known: true, seen: true, seen_at: now() - 9, age: 3}]}),
  behind: n => ({cluster: true, at: now(), nodes: [{name: 'otp1', me: true, alive: true, known: true, seen: true, seen_at: now() - 120, age: 1},
                                                     {name: 'otp2', me: false, alive: true, known: true, seen: false, seen_at: now() - 300, age: 3}]}),
  gone: n => ({cluster: true, at: now(), nodes: [{name: 'otp1', me: true, alive: true, known: true, seen: true, seen_at: now() - 120, age: 1},
                                                   {name: 'otp2', me: false, alive: false, known: true, seen: true, seen_at: now() - 300, age: 130}]}),
  old: n => ({cluster: true, at: now(), nodes: [{name: 'otp1', me: true, alive: true, known: true, seen: true, seen_at: now() - 120, age: 1},
                                                  {name: 'otp2', me: false, alive: true, known: false, seen: false, age: 3}]}),
  alone: n => ({cluster: false, at: now(), nodes: [{name: 'otp1', me: true, alive: true, known: true, seen: true, seen_at: now() - 5, age: 1}]}),
};
(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'cs']) {
    for (const width of [1300, 390]) {
      const tag = lang + '@' + width + ': ';
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e)));
      let state = 'step', posts = 0;
      await p.route(/api=settings-nodes/, route => {
        if (route.request().method() === 'POST') posts++;
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(STATES[state]()) });
      });
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
      await p.keyboard.press('Enter');
      await p.waitForTimeout(2500);
      await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
      await p.goto('https://127.0.0.1/admin/#settings/hisec');
      await p.reload();
      await p.waitForSelector('.sn-pill', { timeout: 30000 }).catch(() => {});
      const info = await p.evaluate(() => {
        const pane = document.querySelector('.ctl-pane:not([hidden])');
        const cards = [...pane.querySelectorAll('.card')];
        const withSect = cards.filter(c => c.querySelector('[id^="sect-"]'));
        return {pills: pane.querySelectorAll('.sn-pill').length, withSect: withSect.length,
                onlySect: [...pane.querySelectorAll('.sn-pill')].every(x => x.closest('.card').querySelector('[id^="sect-"]')),
                dots: [...pane.querySelectorAll('.sn-pill')][0] ? [...pane.querySelectorAll('.sn-pill')][0].querySelectorAll('.dot').length : 0,
                ok: [...pane.querySelectorAll('.sn-pill .dot')].every(d => d.classList.contains('ok')),
                diff: [...pane.querySelectorAll('.sn-pill')].some(x => x.classList.contains('diff')),
                words: ([...pane.querySelectorAll('.sn-dots')][0] || {})._explainHtml || ''};
      });
      ok(tag + 'a pill on each card of the settings, none elsewhere (' + info.pills + '/' + info.withSect + ')', info.pills === info.withSect && info.pills >= 1 && info.onlySect, info);
      ok(tag + '...a dot a node, both green, no amber edge', info.dots === 2 && info.ok && !info.diff, info);
      // as shown, in the page's language: pointed at
      await p.hover('.ctl-pane:not([hidden]) .sn-dots');
      await p.waitForTimeout(500);
      info.words = await p.evaluate(() => (document.querySelector('.sethelp') || {}).textContent || '');
      await p.hover('.ctl-pane:not([hidden]) .sn-re');
      await p.waitForTimeout(500);
      const re = await p.evaluate(() => (document.querySelector('.sethelp') || {}).textContent || '');
      await p.mouse.move(1, 1);
      ok(tag + '...pointed at: in effect on both, a node a line', (lang === 'en' ? /in effect on both nodes/.test(info.words) && /in effect/.test(info.words)
         : /platí na obou uzlech/.test(info.words) && /platí/.test(info.words)) && /otp1/.test(info.words) && /otp2/.test(info.words), info.words);

      ok(tag + '...the icon: look again on both nodes, by itself every 15 s', lang === 'en' ? /Look again on both nodes/.test(re) && /every 15 s/.test(re)
         : /Zkontrolovat znovu na obou uzlech/.test(re) && /každých 15 s/.test(re), re);
      await p.screenshot({ path: '/tmp/claude-0/osuui/sn-step-' + lang + '-' + width + '.png' });
      for (const [st, cls, rx] of [['behind', 'warn', lang === 'en' ? /not yet/ : /zatím ne/], ['gone', 'bad', lang === 'en' ? /not heard from/ : /neozývá se/],
                                   ['old', 'off', lang === 'en' ? /older version/ : /starší verze/]]) {
        state = st;
        await p.evaluate(() => snLoad());
        await p.waitForTimeout(400);
        const s2 = await p.evaluate(() => { const x = document.querySelector('.ctl-pane:not([hidden]) .sn-pill'); return {diff: x.classList.contains('diff'), dot2: x.querySelectorAll('.dot')[1].className, words: x.querySelector('.sn-dots')._explainHtml}; });
        ok(tag + st + ': the second dot ' + cls + ', the edge amber, the words say so', s2.diff && s2.dot2.includes(cls) && rx.test(s2.words), s2);
        if (st === 'behind') await p.screenshot({ path: '/tmp/claude-0/osuui/sn-behind-' + lang + '-' + width + '.png' });
      }
      state = 'step';
      await p.evaluate(() => snLoad());
      await p.waitForTimeout(300);
      await p.click('.ctl-pane:not([hidden]) .sn-re');
      await p.waitForTimeout(200);
      const spin = await p.evaluate(() => !!document.querySelector('.ctl-pane:not([hidden]) .sn-re.spin'));
      ok(tag + 'the icon clicked: asked again (POST), it spins', posts >= 1 && spin, {posts, spin});
      const corner = await p.evaluate(() => [...document.querySelectorAll('.sn-pill.sn-corner')].every(x => x.parentElement.classList.contains('sn-has-corner')));
      ok(tag + 'a card with no heading: the pill on its top edge', corner);
      state = 'alone';
      await p.evaluate(() => snLoad());
      await p.waitForTimeout(400);
      ok(tag + 'standalone: no pill at all', await p.evaluate(() => document.querySelectorAll('.sn-pill').length === 0));
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      ok(tag + 'no errors', !errs.length, errs.join(' | '));
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
