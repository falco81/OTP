// ui_split.js - the card "When the nodes lose each other" in Chromium on the installed otp, drawn with a
// cluster of two given to it (the installed one is a node alone): the three choices, the arbiter box,
// the switches, the table of what happens worked out from them, the save bar, Put back; pictures.
const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 300) + ')')); };
const now = Date.now() / 1000;
const VIEW = {active: true, engaged: false, ha_mode: 'replicated',
  conf: {split_mode: 'off', split_prefer: '', split_after_s: 20, split_scratch: 0, split_halve: 0, split_freeze: 0, split_report: 0},
  preferred: 'otp1', me: 'otp1',
  nodes: [{name: 'otp1', me: true, alive: true, fresh: true, arbiter: '',
           state: {at: now, apart: false, role: 'serve', gateway: '192.0.2.1', arbiters: [], arbiter: null}},
          {name: 'otp2', me: false, alive: true, fresh: true, arbiter: '',
           state: {at: now, apart: false, role: 'serve', gateway: '192.0.2.1', arbiters: [], arbiter: null}}],
  report: null};
(async () => {
  const b = await chromium.launch();
  for (const [scheme, width] of [['dark', 1300], ['light', 1300], ['dark', 420]]) {
    const ctx = await b.newContext({ignoreHTTPSErrors: true, viewport: {width: width, height: 3400}, colorScheme: scheme});
    const pg = await ctx.newPage();
    const errs = []; pg.on('pageerror', e => errs.push(String(e)));
    await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(700);
    await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
    await pg.waitForTimeout(2000);
    await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.reload(); await pg.waitForTimeout(3000);
    const tag = scheme + '-' + width;
    if (width === 1300 && scheme === 'dark') {
      /* Through the page's real relay and the daemon (1.0.219: ?api=split was not relayed at all,
         and the card stayed empty): this node alone - one database, nothing to choose. */
      await pg.evaluate(() => loadSplit({mode: 1})); await pg.waitForTimeout(1500);
      const real = await pg.evaluate(() => ({view: SPLITC.view, text: $('ha-split').textContent}));
      ok('the card fetched through the page\'s relay: the daemon answered (' + (real.view ? 'active ' + real.view.active : 'nothing') + ')',
         real.view && real.view.active === false && /one database|jedna databáze|Both nodes open one database|Oba uzly otevírají/i.test(real.text), real);
      await pg.evaluate(() => { SPLITC.view = null; SPLITC.draft = null; });
    }
    await pg.evaluate((v) => { $('ha-split-card').hidden = false; SPLITC.view = v; SPLITC.draft = splitFresh(v); drawSplit(); }, VIEW);
    await pg.waitForTimeout(400);
    if (width === 1300 && scheme === 'dark') {
      const t = await pg.textContent('#ha-split-card');
      ok('drawn: the three choices, the switches, the table', (await pg.$$('.split-choice')).length === 3 &&
         (await pg.$$('.split-opt')).length === 4 && (await pg.$$('.split-scen tbody tr')).length === 5);
      ok('as until now chosen: said to be exactly as before, nodes "not watched"', /1\.0\.218/.test(t) && (await pg.$('.split-said.same')) !== null);
      await (await pg.$('#ha-split-card')).screenshot({path: '/home/claude/shots/split-asbefore.png'});
      await pg.evaluate(() => document.querySelectorAll('.split-choice')[1].click()); await pg.waitForTimeout(300);
      ok('the node that still sees the network: the arbiter box, one field each node, Try it',
         (await pg.$$('.split-arb input')).length === 2 && (await pg.$('#split-try')) !== null);
      ok('... the save bar says a change waits', await pg.evaluate(() => $('save-bar').classList.contains('dirty')));
      const rows = await pg.$$eval('.split-scen tbody tr', trs => trs.map(tr => tr.textContent));
      ok('... the table: a node losing the network steps aside, the other answers', rows.some(r => /steps aside|ustoup/i.test(r)));
      await pg.evaluate(() => document.querySelectorAll('.split-opt input[type=checkbox]')[0].click()); await pg.waitForTimeout(300);
      await (await pg.$('#ha-split-card')).screenshot({path: '/home/claude/shots/split-arbiter.png'});
      await pg.evaluate(() => document.querySelectorAll('.split-choice')[2].click()); await pg.waitForTimeout(300);
      const rows2 = await pg.$$eval('.split-scen tbody tr', trs => trs.map(tr => tr.innerHTML));
      ok('only the preferred node: "nobody answers" when the preferred one fails, in red', rows2.some(r => /split-out crit/.test(r)));
      await (await pg.$('#ha-split-card')).screenshot({path: '/home/claude/shots/split-priority.png'});
      await pg.evaluate(() => $('set-reset').click()); await pg.waitForTimeout(1500);
      await pg.evaluate((v) => { $('ha-split-card').hidden = false; SPLITC.view = v; SPLITC.draft = splitFresh(v); drawSplit(); }, VIEW);
      ok('Put back: as until now again, nothing waits', await pg.evaluate(() => SPLITC.draft.mode === 'off' && !PENDING.split));
      /* apart, one node aside, a report */
      const apart = JSON.parse(JSON.stringify(VIEW));
      apart.engaged = true; apart.conf.split_mode = 'arbiter'; apart.conf.split_report = 1; apart.conf.split_scratch = 1;
      apart.nodes[0].state = {at: now, apart: true, since: now - 95, role: 'serve', why: 'the arbiter is reached - this node answers',
        gateway: '192.0.2.1', arbiter: true, arbiters: [{target: '192.0.2.1', ok: true, how: 'ping', words: ''}]};
      apart.nodes[1].fresh = false; apart.nodes[1].alive = false;
      apart.report = {at: now - 86000, since: now - 90000, taken: {otp1: 12, otp2: 3}, twice: [{name: 'ana@corp', kind: 'step', nodes: ['otp1', 'otp2']}], twice_n: 1};
      await pg.evaluate((v) => { SPLITC.view = v; SPLITC.draft = splitFresh(v); drawSplit(); }, apart);
      ok('apart: the state tag, the broken link, the report', (await pg.$('.split-link.broken')) !== null && (await pg.$('.split-report.bad')) !== null);
      await (await pg.$('#ha-split-card')).screenshot({path: '/home/claude/shots/split-apart.png'});
    } else {
      await (await pg.$('#ha-split-card')).screenshot({path: '/home/claude/shots/split-' + tag + '.png'});
      const over = await pg.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      ok(tag + ': drawn, no sideways scroll', !over && (await pg.$$('.split-choice')).length === 3);
    }
    ok(tag + ': no error in the page', errs.length === 0, errs);
    await ctx.close();
  }
  /* A switch clicked half-way down the page: the page stays where it is (1.0.220). */
  {
    const ctx = await b.newContext({ignoreHTTPSErrors: true, viewport: {width: 1300, height: 900}});
    const pg = await ctx.newPage();
    await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(700);
    await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
    await pg.waitForTimeout(2000);
    const where = () => pg.evaluate(() => {
      var out = [document.scrollingElement.scrollTop];
      document.querySelectorAll('*').forEach(function (e) { if (e.scrollTop > 0) out.push(e.tagName + '.' + e.className + ':' + e.scrollTop); });
      return JSON.stringify(out);
    });
    for (const [pane, card, sel] of [['ha', '#ha-split-card', '.split-opt input[type=checkbox]'],
                                     ['web', '#web-push-card', '#web-push .set-grid input[type=checkbox]']]) {
      await pg.goto('https://127.0.0.1/admin/#settings/' + pane); await pg.reload(); await pg.waitForTimeout(3000);
      if (pane === 'ha') await pg.evaluate((v) => { $('ha-split-card').hidden = false; SPLITC.view = v; SPLITC.draft = splitFresh(v); drawSplit(); }, VIEW);
      /* Clicked with the mouse on the switch as a person does - a click by script on the box
         inside did not send the page up, and the test passed on the version that did. */
      const sws = await pg.$$(sel.replace(' input[type=checkbox]', ' .sw'));
      const sw = sws[sws.length - 1];
      await sw.scrollIntoViewIfNeeded(); await pg.waitForTimeout(400);
      const top = () => pg.evaluate(() => document.querySelector('.ctl-main').scrollTop);
      const before = await top();
      const box = await sw.boundingBox();
      await pg.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await pg.waitForTimeout(600);
      const after = await top();
      ok(pane + ': a switch clicked with the mouse half-way down - the page stays where it was (' + before + ' -> ' + after + ')',
         before > 200 && Math.abs(after - before) < 60, [before, after]);
      await pg.evaluate(() => { if ($('set-reset')) $('set-reset').click(); }); await pg.waitForTimeout(800);
    }
    await ctx.close();
  }
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
})();
