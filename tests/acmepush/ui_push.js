// ui_push.js [on|look|flow] - the card Certificates from acme (as ai's 1.0.60) in Chromium, on the
// installed otp.
//   on    switched on (with the save bar) and paired: a code made - prints {"code": ...}
//   look  the card as it is, and a picture of it
//   flow  the two switches and Forget it wait for the save bar, Put back forgets them; a pairing
//         code, Take it back and a pasted key are done in their own window, as in ai
const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const BASE = 'https://127.0.0.1/admin/';
const step = process.argv[2] || 'on';
const R = [];
const ok = (w, c, more) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + JSON.stringify(more).slice(0, 300) + ')')); };
(async () => {
  const b = await chromium.launch();
  const pg = await (await b.newContext({ignoreHTTPSErrors: true, viewport: {width: 1300, height: 1000}})).newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto(BASE); await pg.waitForTimeout(700);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2000);
  await pg.goto(BASE + '#settings/web'); await pg.reload(); await pg.waitForTimeout(3000);
  const srv = () => pg.evaluate(() => api('acme-push'));
  const box = (i) => pg.evaluate((i) => document.querySelectorAll('#web-push .set-grid input[type=checkbox]')[i].click(), i);
  const save = async () => { await pg.evaluate(() => $('set-save').click()); await pg.waitForTimeout(2500); };
  const putBack = async () => { await pg.evaluate(() => $('set-reset').click()); await pg.waitForTimeout(1500); };
  const dirty = () => pg.evaluate(() => $('save-bar').classList.contains('dirty') && $('save-bar').style.display !== 'none');
  const btn = (words) => pg.evaluate((w) => { const x = Array.from(document.querySelectorAll('#web-push .btnrow button')).find(b => b.textContent.indexOf(w) >= 0) || document.querySelectorAll('#web-push .btnrow button')[w === 'pair' ? 0 : w === 'back' ? 1 : 2]; x.click(); }, words);
  const pairCode = async () => { await btn('pair'); await pg.waitForTimeout(1500); const c = await pg.$('.push-code'); return c ? (await c.textContent()).trim() : ''; };
  if (step === 'on') {
    if (!(await srv()).on) { await box(0); await save(); }
    const code = await pairCode();
    await pg.screenshot({path: '/home/claude/shots/push-code.png'});
    console.log(JSON.stringify({errors: errs, code: code}));
  } else if (step === 'look') {
    console.log(JSON.stringify({errors: errs, card: (await pg.textContent('#web-push-card')).replace(/\s+/g, ' ').trim()}));
    await (await pg.$('#web-push-card')).screenshot({path: '/home/claude/shots/push-card-after.png'});
  } else {
    let v = await srv();
    if (v.on) { await box(0); await save(); v = await srv(); }
    ok('off to start with: the card says off, one switch', !v.on && (await pg.textContent('#web-push-state')).trim().length > 0 &&
       (await pg.$$('#web-push .set-grid input[type=checkbox]')).length === 1);
    await (await pg.$('#web-push-card')).screenshot({path: '/home/claude/shots/push-card-off.png'});
    await box(0); await pg.waitForTimeout(400);
    ok('switched on on the card: the save bar says a change waits, the server still off', await dirty() && !(await srv()).on);
    await putBack();
    ok('Put back: off on the card, nothing waits', !(await dirty()) &&
       !(await pg.evaluate(() => document.querySelector('#web-push .set-grid input[type=checkbox]').checked)));
    await box(0); await save();
    v = await srv();
    ok('Save: on', v.on && !(await dirty()));
    const tiles = await pg.$$eval('#web-push .fact', xs => xs.map(x => x.textContent.replace(/\s+/g, ' ').trim()));
    ok('the tiles: the address for acme, the id, the sealing key (' + tiles.length + ')', tiles.length === 3 &&
       tiles[0].indexOf('/admin/') >= 0 && tiles[1].indexOf(v.app_id) >= 0 && /[A-Za-z0-9+\/]{43}=/.test(tiles[2]), tiles);
    const code = await pairCode();
    ok('Pair with an acme: the code at once in its window (****-****-****-****)', /^[A-Z0-9]{4}(-[A-Z0-9]{4}){3}$/.test(code) && !!(await srv()).pairing);
    await pg.screenshot({path: '/home/claude/shots/push-code.png'});
    await pg.keyboard.press('Escape'); await pg.waitForTimeout(600);
    await (await pg.$('#web-push-card')).screenshot({path: '/home/claude/shots/push-card-on.png'});
    await btn('back'); await pg.waitForTimeout(1500);
    ok('Take it back: no code waits', !(await srv()).pairing);
    const before = (await srv()).other_names;
    await box(1); await pg.waitForTimeout(400);
    ok('Take certificates of other names: waits for the save bar', await dirty() && (await srv()).other_names === before);
    await save();
    ok('Save: changed', (await srv()).other_names === !before);
    await box(1); await save();
    if ((await srv()).keys.length) {
      const n = (await srv()).keys.length;
      await pg.evaluate(() => document.querySelector('#web-push td.rowtools button').click()); await pg.waitForTimeout(500);
      ok('Forget it: struck through, waits for the save bar, still paired', await dirty() && (await pg.$('#web-push tr.push-gone')) && (await srv()).keys.length === n);
      await putBack();
      ok('Put back: kept', !(await dirty()) && !(await pg.$('#web-push tr.push-gone')) && (await srv()).keys.length === n);
    }
    ok('no error in the page', errs.length === 0, errs);
    console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  }
  await b.close();
})();
