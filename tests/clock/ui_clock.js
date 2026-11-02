// ui_clock.js - the card "The clocks of the nodes" (1.0.222) in Chromium on the installed otp: fetched
// through the page's real relay (a node alone), then drawn with a cluster of two given to it: the
// three choices, the reference box and Try it, the switches 2x2, the table worked out from the
// choices (its columns stay put), the save bar, guard refused without a try, Put back; a real mouse
// click on a switch half-way down keeps the page where it is; the Czech page; pictures.
const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 300) + ')')); };
const now = Date.now() / 1000;
const VIEW = {engaged: false, ha_mode: 'replicated', cluster: true, me: 'otp1', common: ['tik.cesnet.cz', 'tak.cesnet.cz'],
  conf: {clock_mode: 'off', clock_warn_s: 2, clock_aside_s: 20, clock_codes: 0, clock_beat: 0, clock_locks: 0, health_dir: 0},
  nodes: [{name: 'otp1', me: true, alive: true, fresh: true, ref: '', state: {at: now, role: 'serve'}},
          {name: 'otp2', me: false, alive: true, fresh: true, ref: '', state: {at: now, role: 'serve'}}]};
const SICK = JSON.parse(JSON.stringify(VIEW));
SICK.engaged = true; SICK.conf.clock_mode = 'guard'; SICK.conf.health_dir = 1;
SICK.nodes[0].state = {at: now, role: 'serve', ref: 0.004, skew: 312.2, skew_of: 'otp2', dir_ok: true, dirs: []};
SICK.nodes[1].state = {at: now, role: 'aside', ref: 312.4, skew: -312.2, skew_of: 'otp1', dir_ok: true, dirs: [],
  why: 'this node\'s clock is -312.4 s off the time servers - the other node answers'};
const login = async (pg) => {
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(700);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2000);
};
const english = (pg) => pg.evaluate(() => api('prefs', {lang: 'en'}));
const draw = (pg, v) => pg.evaluate((v) => { $('clock-card').hidden = false; CLOCKC.view = v; CLOCKC.draft = clockFresh(v); drawClock(); }, v);
(async () => {
  const b = await chromium.launch();
  for (const [scheme, width] of [['dark', 1300], ['light', 1300], ['dark', 420]]) {
    const ctx = await b.newContext({ignoreHTTPSErrors: true, viewport: {width: width, height: 3400}, colorScheme: scheme});
    const pg = await ctx.newPage();
    const errs = []; pg.on('pageerror', e => errs.push(String(e)));
    await login(pg); await english(pg);
    await pg.goto('https://127.0.0.1/admin/#settings/time'); await pg.reload(); await pg.waitForTimeout(3500);
    const tag = scheme + '-' + width;
    if (width === 1300 && scheme === 'dark') {
      const real = await pg.evaluate(() => ({view: CLOCKC.view, hidden: $('clock-card').hidden, text: $('clock-guard').textContent}));
      ok('the card fetched through the page\'s relay on the Time pane (mode ' + (real.view ? real.view.conf.clock_mode : 'nothing') + ')',
         real.view && !real.hidden && real.view.conf.clock_mode === 'off' && real.view.nodes.length >= 1, real);
      ok('... a node alone: as until now, "not watched", and the note of one node', /not watched|nesleduje/i.test(real.text));
      await draw(pg, VIEW); await pg.waitForTimeout(300);
      ok('drawn: two tiles, the three choices, four switches, the table of five', (await pg.$$('#clock-guard .split-node')).length === 2 &&
         (await pg.$$('#clock-guard .split-choice')).length === 3 && (await pg.$$('#clock-guard .split-opt')).length === 4 &&
         (await pg.$$('#clock-guard .split-scen tbody tr')).length === 5);
      ok('as until now: said to be exactly as before', /1\.0\.222/.test(await pg.textContent('#clock-guard')) && (await pg.$('#clock-guard .split-said.same')) !== null);
      const two = await pg.$$eval('#clock-guard .split-opts', g => getComputedStyle(g[0]).gridTemplateColumns.split(' ').length);
      ok('the switches two by two (' + two + ' columns)', two === 2);
      await (await pg.$('#clock-card')).screenshot({path: '/home/claude/shots/clock-asbefore.png'});
      await pg.evaluate(() => document.querySelectorAll('#clock-guard .split-choice')[2].click()); await pg.waitForTimeout(300);
      ok('guard: the reference box, one field each node with the cluster\'s servers as its placeholder, Try it',
         (await pg.$$('#clock-guard .split-arb input')).length === 2 && (await pg.$('#clock-try')) !== null &&
         /tik\.cesnet\.cz/.test(await pg.$eval('#clock-guard .split-arb input', i => i.placeholder)));
      ok('... the save bar says a change waits', await pg.evaluate(() => $('save-bar').classList.contains('dirty')));
      const rows = await pg.$$eval('#clock-guard .split-scen tbody tr', trs => trs.map(tr => tr.textContent));
      ok('... the table: a node with its clock 5 min off steps aside, the other answers', /steps aside|ustoup/i.test(rows[0]));
      const saved = await pg.evaluate(() => clockSave().then(r => [r, CLOCKC.view.conf.clock_mode]));
      ok('... saved without trying first: refused on the page', saved[0] === false && saved[1] === 'off', saved);
      const cols = () => pg.$$eval('#clock-guard .split-scen thead th', ths => ths.map(t => Math.round(t.getBoundingClientRect().left)).join(','));
      const c0 = await cols();
      let same = true;
      for (let i = 0; i < 4; i++) {
        await pg.evaluate((i) => document.querySelectorAll('#clock-guard .split-opt input[type=checkbox]')[i].click(), i); await pg.waitForTimeout(200);
        if (await cols() !== c0) same = false;
      }
      const rows2 = await pg.$$eval('#clock-guard .split-scen tbody tr', trs => trs.map(tr => tr.textContent));
      ok('codes corrected: the node with its clock off answers, codes corrected', /codes corrected|kódy opraveny/i.test(rows2[0]));
      ok('... the directory switch: the node without it steps aside', /steps aside|ustoup/i.test(rows2[4]));
      for (let i = 0; i < 4; i++) {
        await pg.evaluate((i) => document.querySelectorAll('#clock-guard .split-opt input[type=checkbox]')[i].click(), i); await pg.waitForTimeout(150);
      }
      await pg.evaluate(() => document.querySelectorAll('#clock-guard .split-choice')[1].click()); await pg.waitForTimeout(200);
      if (await cols() !== c0) same = false;
      ok('the table: its columns stay put whatever is switched (' + c0 + ')', same);
      await pg.evaluate(() => document.querySelectorAll('#clock-guard .split-choice')[0].click()); await pg.waitForTimeout(200);
      await pg.evaluate(() => $('set-reset').click()); await pg.waitForTimeout(1500);
      ok('Put back: as until now again, nothing waits', await pg.evaluate(() => CLOCKC.draft.mode === 'off' && !PENDING.clock));
      await draw(pg, SICK); await pg.waitForTimeout(300);
      const t = await pg.textContent('#clock-guard');
      ok('a node 312 s behind and aside: the tile says it, its link "apart", the state "not well"',
         (await pg.$('#clock-guard .split-node.aside')) !== null && /behind by/.test(t) && /312/.test(t) &&
         (await pg.$('#clock-guard .split-link.broken')) !== null && /not well/.test(await pg.textContent('#clock-state')));
      await (await pg.$('#clock-card')).screenshot({path: '/home/claude/shots/clock-guard.png'});
      /* The Czech page: nothing of the card left in English. */
      await pg.evaluate(() => api('prefs', {lang: 'cs'})); await pg.reload(); await pg.waitForTimeout(3500);
      await draw(pg, SICK); await pg.waitForTimeout(1500);
      const cz = await pg.textContent('#clock-card');
      const left = ['The clocks of the nodes', 'Step aside when not well', 'Measure and warn', 'behind by', 'What happens',
                    'Codes by the corrected time', 'stepped aside', 'Try it from every node'].filter(w => cz.indexOf(w) >= 0);
      ok('in Czech: the reason it stepped aside, from the daemon, translated too', /obsluhuje druhý uzel/.test(cz) && !/the other node answers/.test(cz));
      ok('in Czech: the card translated (left in English: ' + JSON.stringify(left) + ')', left.length === 0 && /Hodiny uzlů/.test(cz));
      await (await pg.$('#clock-card')).screenshot({path: '/home/claude/shots/clock-cs.png'});
      await english(pg); await pg.waitForTimeout(800);
    } else {
      await draw(pg, SICK); await pg.waitForTimeout(400);
      await (await pg.$('#clock-card')).screenshot({path: '/home/claude/shots/clock-' + tag + '.png'});
      const over = await pg.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      ok(tag + ': drawn, no sideways scroll', !over && (await pg.$$('#clock-guard .split-choice')).length === 3);
    }
    ok(tag + ': no error in the page', errs.length === 0, errs);
    await ctx.close();
  }
  {
    const ctx = await b.newContext({ignoreHTTPSErrors: true, viewport: {width: 1300, height: 900}});
    const pg = await ctx.newPage();
    await login(pg);
    await pg.goto('https://127.0.0.1/admin/#settings/time'); await pg.reload(); await pg.waitForTimeout(3500);
    await draw(pg, VIEW);
    const sws = await pg.$$('#clock-guard .split-opt .sw');
    const sw = sws[sws.length - 1];
    await sw.scrollIntoViewIfNeeded(); await pg.waitForTimeout(400);
    const top = () => pg.evaluate(() => document.querySelector('.ctl-main').scrollTop);
    const before = await top();
    const box = await sw.boundingBox();
    await pg.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await pg.waitForTimeout(600);
    const after = await top();
    ok('a switch clicked with the mouse half-way down - the page stays where it was (' + before + ' -> ' + after + ')',
       before > 200 && Math.abs(after - before) < 60, [before, after]);
    ok('... and the switch is on, the change waits', await pg.evaluate(() => CLOCKC.draft.health_dir === true && !!PENDING.clock));
    await pg.evaluate(() => { if ($('set-reset')) $('set-reset').click(); }); await pg.waitForTimeout(800);
    await ctx.close();
  }
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
})();
