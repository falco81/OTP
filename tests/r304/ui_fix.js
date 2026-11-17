// ui_fix.js - 1.0.304: the pages during an upgrade - a save that fails is said ("not saved"), a look that
// fails is not; a daemon down after the upgrade ended is not "in maintenance"; the sign-in page never loads
// itself again under somebody typing. The installed pages; this node's file written by the test.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const F = '/var/www/otp/.upgrade.json';
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
const now = () => Math.floor(Date.now() / 1000);
function tell(o) {
  fs.writeFileSync(F + '.t', JSON.stringify(Object.assign({state: 'running', id: 'k1', version: '9.9.9', from: '1.0.1', by: 'admin', node: 'vm',
    part: 3, parts: 8, words: 'The daemon', started: now() - 20, at: now(), said: '', downgrade: false}, o || {})));
  fs.chmodSync(F + '.t', 0o644); fs.renameSync(F + '.t', F);
}
(async () => {
  try { fs.unlinkSync(F); } catch (e) { }
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await (await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 } })).newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  await p.reload(); await p.waitForTimeout(2500);
  // 1 a save and a look while this node is upgraded (the 503 of the pages, as PHP answers it)
  tell();
  await p.waitForTimeout(6000);
  await p.route(/\?api=(settings|tokens)(&|$)/, r => r.fulfill({ status: 503, contentType: 'application/json',
    body: JSON.stringify({ ok: false, upgrading: { state: 'running', version: '9.9.9', part: 4, parts: 8, words: 'Python', at: now(), started: now() - 30 },
      error: 'otp is being upgraded to 9.9.9 - back in a moment' }) }));
  const t1 = await p.evaluate(async () => {
    const shown = () => { const t = document.getElementById('toast'); return t && t.classList.contains('show') ? t.innerText : ''; };
    try { await api('tokens'); } catch (e) { oops(e); }
    const look = shown();
    try { await api('settings', {set: {site_name: 'x'}}); } catch (e) { oops(e); }
    return { look, save: shown() };
  });
  ok('1 a look that fails while it is upgraded: silent (the band says it)', !t1.look, t1);
  ok('1 a save that fails: "Not saved: otp is being upgraded"', /not saved/i.test(t1.save) && /upgraded/i.test(t1.save), t1);
  await p.unrouteAll({ behavior: 'ignoreErrors' });
  // 2 the upgrade ended, then the daemon is down: not "in maintenance"
  tell({ state: 'done', part: 8, words: 'otp 9.9.9 runs' });
  const away = await p.evaluate(() => { UPG.away = 0; upgradeHeard({ state: 'done', version: '9.9.9', at: Date.now() / 1000 }, 'api'); return UPG.away; });
  ok('2 a 503 that says the upgrade is done: not taken as "away for the upgrade"', away === 0, away);
  try { fs.unlinkSync(F); } catch (e) { }
  // 3 the sign-in page: never loaded again under somebody typing
  tell();
  const p2 = await (await b.newContext({ ignoreHTTPSErrors: true })).newPage();
  await p2.goto('https://127.0.0.1/admin/'); await p2.waitForTimeout(1500);
  ok('3 the sign-in page shows the band', await p2.locator('#upband-in').count() === 1);
  await p2.evaluate(() => { window.__mark = 1; });
  await p2.fill('input[autocomplete=username]', 'someone');
  await p2.route(/\?api=upgrade-state/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, upgrading: null, api: true, pages: '9.9.9' }) }));
  await p2.waitForTimeout(5000);
  const st = await p2.evaluate(() => ({ mark: window.__mark, link: !!document.getElementById('upband-in-again'), name: document.querySelector('input[autocomplete=username]').value }));
  ok('3 it ended while a name is typed: not loaded again, "load the page again" offered, the name kept', st.mark === 1 && st.link && st.name === 'someone', st);
  await p2.fill('input[autocomplete=username]', '');
  await p2.evaluate(() => document.activeElement && document.activeElement.blur());
  await p2.waitForTimeout(5000);
  ok('3 nothing typed any more: loaded again by itself', await p2.evaluate(() => window.__mark === undefined).catch(() => true));
  try { fs.unlinkSync(F); } catch (e) { }
  ok('no page errors', errs.length === 0, errs);
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL broke: ' + e); try { fs.unlinkSync(F); } catch (x) { } process.exit(1); });
