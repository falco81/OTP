// ui_after.js - 1.0.258: Settings → Upgrades → To be done by hand. Written for the live single-node
// install (run as root, on the server itself): the test-only entries of 88n_after.py are switched on
// by root's file /var/lib/otp/after-test.json (off without it), then - the card first in the pane,
// tinted; a band each (bad: red, the × icon; warn: amber, the flag), the why, the lead and the command
// box with Copy (the clipboard holds it); the count beside Upgrades in the menu and on the Settings
// tab; Look again makes the automatic one go by itself; Done takes the manual one; DONE LATELY says
// both (by itself / done, –/admin, the time); the empty state (a green note, the border plain, no
// badge); nothing of it at the top of the pages; the buttons under the words at phone width; a
// read-only account sees no card and gets only the count; Czech. The file is taken away at the end.
//
//     node ui_after.js            (Playwright; https://127.0.0.1/admin/, admin's password in
//                                  /home/claude/run/adminpw)
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const BASE = 'https://127.0.0.1/admin/';
const HOOK = '/var/lib/otp/after-test.json';
/* from nothing: a Done of a run before holds for its entry (1.0.258) - taken out of the database */
try { require('child_process').execFileSync('python3', ['-c', "import sqlite3; c = sqlite3.connect('/var/lib/otp/otp.db'); c.execute(\"DELETE FROM meta WHERE k LIKE 'after:ack:test-%'\"); c.commit()"]); } catch (e) {}
const PW = 'After-258-pass!';
const SHOTS = '/tmp/claude-0/after';
fs.mkdirSync(SHOTS, { recursive: true });
function hook(v) {
  if (v === null) { try { fs.unlinkSync(HOOK); } catch (e) { } return; }
  fs.writeFileSync(HOOK, JSON.stringify(v));
  fs.chmodSync(HOOK, 0o644);
}
async function post(p, what, body) {
  return p.evaluate(async ([w, b]) => {
    const r = await fetch('?api=' + w, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
    let d = {}; try { d = await r.json(); } catch (e) {}
    return {st: r.status, d};
  }, [what, body]);
}
async function get(p, what) {
  return p.evaluate(async (w) => { const r = await fetch('?api=' + w); let d = {}; try { d = await r.json(); } catch (e) {} return {st: r.status, d}; }, what);
}
async function signIn(p, name, pw) {
  await p.goto(BASE);
  await p.fill('input[autocomplete=username]', name);
  await p.fill('input[type=password]', pw);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}
async function newCtx(b, lang = 'en', width = 1280) {
  const c = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: width, height: 900 } });
  await c.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://127.0.0.1' });
  await c.addCookies([{name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/'}]);
  return c;
}
async function openUpgrade(p) {
  await p.evaluate(() => { showTab('settings'); showPane('upgrade'); });
  await p.waitForTimeout(1500);
}
async function band(p, id) { return p.$('#after-bands .after-band[data-id="' + id + '"]'); }
async function lookNow(p) { return post(p, 'after', {action: 'check'}); }
(async () => {
  const b = await chromium.launch();
  const ctx = await newCtx(b);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await signIn(p, 'admin', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  ok('signed in as a full administrator', ((await get(p, 'whoami')).d.who || {}).role === 'fulladmin');
  const before = (await lookNow(p)).d;
  const others = (before.items || []).filter(x => !/^test-/.test(x.id));
  if (others.length) console.log('     (this machine has its own to be done: ' + others.map(x => x.id + '@' + x.node).join(', ') + ')');

  // ---- made needed by root's file --------------------------------------------------------------
  hook({auto: 'needed', manual: 'needed'});
  const d1 = (await lookNow(p)).d;
  ok('the API: both test entries needed after Look again', ['test-auto', 'test-manual'].every(i => (d1.items || []).some(x => x.id === i)), JSON.stringify(d1.items));
  await openUpgrade(p);
  const first = await p.$eval('#pane-upgrade', pane => { const c = pane.querySelector('.card'); return c && c.id; });
  ok('the card "To be done by hand" is the first card of Settings → Upgrades', first === 'after-card', first);
  ok('...its heading and intro', /To be done by hand/.test(await p.$eval('#after-card h2', e => e.textContent)) &&
    /What otp cannot do itself/.test(await p.$eval('#after-card > p.note', e => e.textContent)));
  ok('...tinted red while a bad one is there', await p.$eval('#after-card', e => e.classList.contains('bad') &&
    getComputedStyle(e).borderColor !== getComputedStyle(document.querySelector('#pane-upgrade .card:not(#after-card)')).borderColor));
  const bm = await band(p, 'test-manual'), ba = await band(p, 'test-auto');
  ok('a band each', !!bm && !!ba);
  const look = await p.$eval('#after-bands .after-band[data-id="test-manual"]', e => {
    const cs = getComputedStyle(e), bar = getComputedStyle(e, '::before');
    return {cls: e.className, bar: bar.width, barBg: bar.backgroundColor, radius: cs.borderRadius,
            title: e.querySelector('.after-title b').textContent, why: e.querySelector('.after-why').textContent,
            lead: (e.querySelector('.after-lead') || {}).textContent, cmd: (e.querySelector('.after-cmd code') || {}).textContent,
            copy: !!e.querySelector('.after-cmd .after-copy'), foot: (e.querySelector('.after-foot') || {}).textContent,
            seen: (e.querySelector('.after-seen') || {}).textContent,
            btns: Array.from(e.querySelectorAll('.after-btns button')).map(x => x.textContent.trim()),
            icon: !!e.querySelector('.after-ic svg'), cmdBg: getComputedStyle(e.querySelector('.after-cmd')).backgroundColor};
  });
  ok('the manual band: red, a 4px bar on the left, rounded', /\bbad\b/.test(look.cls) && look.bar === '4px' && /rgb\(248, 81, 73/.test(look.barBg) && parseFloat(look.radius) >= 6, JSON.stringify(look));
  ok('...its icon, title, why, "As root, on the server:" and the command', look.icon && look.title === 'A test: something done by hand' &&
    /Press Done/.test(look.why) && look.lead === 'As root, on the server:' && look.cmd === 'echo done', JSON.stringify(look));
  ok('...the command box dark, Copy inside it', look.copy && /rgb\(10, 13, 18\)/.test(look.cmdBg), look.cmdBg);
  ok('...the footnote and when it was first seen', /press Done/.test(look.foot) && /First seen \d\d-\d\d-\d{4}/.test(look.seen), look.foot + ' | ' + look.seen);
  ok('...Done only (a manual one has no Look again)', look.btns.join('|') === 'Done', look.btns.join('|'));
  const la = await p.$eval('#after-bands .after-band[data-id="test-auto"]', e => ({cls: e.className,
    btns: Array.from(e.querySelectorAll('.after-btns button')).map(x => x.textContent.trim()), cmd: e.querySelector('.after-cmd code').textContent,
    foot: e.querySelector('.after-foot').textContent}));
  ok('the automatic band: amber, Look again and Done, goes by itself', /\bwarn\b/.test(la.cls) && la.btns.join('|') === 'Look again|Done' &&
    la.cmd === 'rm ' + HOOK && /goes by itself/.test(la.foot), JSON.stringify(la));
  await p.screenshot({ path: SHOTS + '/bands.png', fullPage: true });
  // Copy
  await p.click('#after-bands .after-band[data-id="test-auto"] .after-copy');
  await p.waitForTimeout(500);
  const clip = await p.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  ok('Copy: the command on the clipboard, said so', clip === 'rm ' + HOOK && /on the clipboard/.test(await p.$eval('#toast', e => e.textContent)), clip);
  // the badge and the tab's count
  await p.waitForTimeout(11000);          /* the count is read at most every 10 s */
  const badge = await p.evaluate(() => { const b = document.getElementById('after-badge'), t = document.getElementById('tabn-settings');
    const bs = getComputedStyle(b), ic = b.parentNode.querySelector('svg').getBoundingClientRect(), br = b.getBoundingClientRect();
    return {b: b.textContent, bc: b.className, t: t.textContent, tc: t.className, shown: bs.display !== 'none', bg: bs.backgroundColor,
            topRight: br.left > ic.left && br.top <= ic.top + 4}; });
  const n = 2 + others.length;
  ok('the badge on Upgrades in the menu: the count, red, at the icon\'s top right', badge.b === String(n) && /\bbad\b/.test(badge.bc) && badge.shown &&
    /rgb\(248, 81, 73/.test(badge.bg) && badge.topRight, JSON.stringify(badge));
  ok('...and the same count on the Settings tab', badge.t === String(n) && /\bhot\b/.test(badge.tc), JSON.stringify(badge));
  await p.evaluate(() => document.querySelector('#ctl-nav').classList.remove('open', 'pinned'));
  await p.screenshot({ path: SHOTS + '/rail.png', clip: { x: 0, y: 0, width: 400, height: 900 } });
  // nothing at the top of the pages
  await p.evaluate(() => showTab('overview'));
  await p.waitForTimeout(800);
  const top = await p.evaluate(() => ({bands: document.querySelectorAll('.after-band').length,
    visible: Array.from(document.querySelectorAll('.after-band')).filter(x => x.offsetParent).length,
    problems: (document.getElementById('problems') || {}).textContent || '', trials: (document.getElementById('trials') || {}).textContent || ''}));
  ok('nothing of it at the top of the pages (Overview: no band shown, the header as it was)', top.visible === 0 &&
    !/test|by hand/i.test(top.problems + top.trials), JSON.stringify(top));
  // Look again: the automatic one goes by itself
  await openUpgrade(p);
  hook({auto: 'done', manual: 'needed'});
  await p.click('#after-bands .after-band[data-id="test-auto"] button:has-text("Look again")');
  await p.waitForTimeout(2000);
  ok('Look again: the automatic one went by itself', !(await band(p, 'test-auto')) && !!(await band(p, 'test-manual')));
  let rows = await p.$$eval('#after-lately tbody tr', x => x.map(r => Array.from(r.cells).map(c => c.textContent.trim())));
  ok('DONE LATELY: WHAT / HOW by itself / WHO – / WHEN', (await p.$$eval('#after-lately th', x => x.map(t => t.textContent.trim()).join('|'))) === 'What|How|Who|When' &&
    rows[0] && rows[0][0] === 'A test: something that goes by itself' && rows[0][1] === 'by itself' && rows[0][2] === '–' && /\d\d-\d\d-\d{4}/.test(rows[0][3]), JSON.stringify(rows[0]));
  // Done: the manual one
  await p.click('#after-bands .after-band[data-id="test-manual"] button:has-text("Done")');
  await p.waitForTimeout(2000);
  ok('Done: the manual one is gone', !(await band(p, 'test-manual')));
  rows = await p.$$eval('#after-lately tbody tr', x => x.map(r => Array.from(r.cells).map(c => c.textContent.trim())));
  ok('DONE LATELY: done, by admin', rows[0] && rows[0][0] === 'A test: something done by hand' && rows[0][1] === 'done' && rows[0][2] === 'admin', JSON.stringify(rows[0]));
  const ev = (await get(p, 'events&limit=20')).d;
  ok('...written in the events', JSON.stringify(ev).includes('marked as done on'), JSON.stringify(ev).slice(0, 200));
  // the empty state
  await p.waitForTimeout(11000);
  if (!others.length) {
    const empty = await p.evaluate(() => { const c = document.getElementById('after-card'); const nb = c.querySelector('#after-bands p.note.good');
      return {note: nb && nb.textContent, cls: c.className, bands: c.querySelectorAll('.after-band').length,
              lately: !!c.querySelector('#after-lately tbody tr'), badge: document.getElementById('after-badge').textContent,
              badgeShown: getComputedStyle(document.getElementById('after-badge')).display !== 'none',
              tab: document.getElementById('tabn-settings').textContent}; });
    ok('the empty state: the card stays, a green "Nothing is to be done by hand.", its border plain', empty.note === 'Nothing is to be done by hand.' &&
      !/\b(bad|warn|info)\b/.test(empty.cls) && !empty.bands, JSON.stringify(empty));
    ok('...DONE LATELY stays', empty.lately);
    ok('...no badge, no count on the tab', empty.badge === '' && !empty.badgeShown && empty.tab === '', JSON.stringify(empty));
    await p.screenshot({ path: SHOTS + '/empty.png', fullPage: true });
  } else {
    ok('the empty state: not seen here - this machine has its own to be done (' + others.length + ')', true);
  }
  // the band at phone width: the buttons under the words
  hook({auto: 'needed', manual: 'needed'});
  await lookNow(p);
  const pctx = await newCtx(b, 'en', 390);
  await pctx.addCookies(await ctx.cookies());
  const pp = await pctx.newPage();
  await pp.goto(BASE);
  await pp.waitForTimeout(2000);
  await openUpgrade(pp);
  const lay = await pp.$eval('#after-bands .after-band[data-id="test-auto"]', e => {
    const w = e.querySelector('.after-why').getBoundingClientRect(), bt = e.querySelector('.after-btns').getBoundingClientRect();
    return {under: bt.top > w.bottom - 1, fits: e.scrollWidth <= e.clientWidth + 1, page: document.documentElement.scrollWidth <= window.innerWidth + 1};
  });
  ok('phone width: the buttons go under the words, nothing wider than the screen', lay.under && lay.fits && lay.page, JSON.stringify(lay));
  await pp.screenshot({ path: SHOTS + '/phone.png', fullPage: true });
  await pctx.close();
  // a read-only account: no card, only the count from the API
  await post(p, 'users', {action: 'delete', name: 'aftro'});
  ok('a read-only account made', (await post(p, 'users', {action: 'add', name: 'aftro', role: 'readonly', password: PW, must_change: 0})).st === 200);
  const rctx = await newCtx(b);
  const rp = await rctx.newPage();
  await signIn(rp, 'aftro', PW);
  const ro = (await get(rp, 'after')).d;
  ok('read-only: GET after says how many only', ro.count >= 1 && !ro.items && !ro.lately, JSON.stringify(ro));
  ok('read-only: no Upgrades in the menu, no card, no badge', await rp.evaluate(() => {
    const up = document.querySelector('#ctl-nav [data-pane="upgrade"]'), c = document.getElementById('after-card');
    return (!up || up.hidden) && (!c || c.hidden) && !document.getElementById('tabn-settings').textContent; }));
  const rw = await post(rp, 'after', {action: 'done', id: 'test-auto'});
  ok('read-only: Done refused', rw.st === 403, JSON.stringify(rw));
  await rctx.close();
  await post(p, 'users', {action: 'delete', name: 'aftro'});
  // Czech
  hook({auto: 'needed', manual: 'needed'});
  await lookNow(p);
  /* Done holds for the manual one (the same thing again): the Czech is looked at on the automatic one. */
  const cctx = await newCtx(b, 'cs');
  await cctx.addCookies(await ctx.cookies());
  await cctx.addCookies([{name: 'otp_lang', value: 'cs', domain: '127.0.0.1', path: '/'}]);
  const cp = await cctx.newPage();
  await cp.goto(BASE);
  await post(cp, 'prefs', {lang: 'cs'});      /* the account's own language wins over the cookie */
  await cp.goto(BASE);
  await cp.waitForTimeout(2500);
  await openUpgrade(cp);
  const cz = await cp.$eval('#after-card', e => e.textContent).catch(() => '');
  ok('Czech: the card', /Zbývá udělat ručně/.test(cz) && /Co otp samo udělat nemůže/.test(cz) && /Nedávno hotovo/.test(cz), cz.slice(0, 200));
  ok('Czech: the band - title, lead, Copy, buttons, footnote', /Zkouška: něco, co zmizí samo/.test(cz) && /Jako root na serveru:/.test(cz) &&
    /Kopírovat/.test(cz) && /Zkontrolovat znovu/.test(cz) && /Hotovo/.test(cz) && /zmizí sám/.test(cz) && /Poprvé zjištěno/.test(cz), cz.slice(0, 400));
  ok('Czech: the command itself left as it is', (await cp.$eval('#after-bands .after-band[data-id="test-auto"] .after-cmd code', e => e.textContent)) === 'rm ' + HOOK);
  ok('Czech: DONE LATELY', /Co/.test(await cp.$eval('#after-lately thead', e => e.textContent)) && /sám|hotovo/.test(await cp.$eval('#after-lately tbody', e => e.textContent)));
  await cp.screenshot({ path: SHOTS + '/cs.png', fullPage: true });
  await post(cp, 'prefs', {lang: 'en'});
  await cctx.close();
  // taken away again
  hook(null);
  await lookNow(p);
  const last = (await get(p, 'after')).d;
  ok('the file taken away: no test band is left', !(last.items || []).some(x => /^test-/.test(x.id)), JSON.stringify(last.items));
  ok('no errors on the pages', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})().catch(e => { try { fs.unlinkSync(HOOK); } catch (x) { } console.log('FAIL ' + e); process.exit(1); });
