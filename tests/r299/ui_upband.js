// ui_upband.js - 1.0.299: the upgrade band, in a real Chromium on the installed otp (standalone).
// This node's file written by hand (as root writes it), the daemon stopped and started again by its
// exact PID, nginx/PHP away simulated in the browser; a cluster's plan (HA, the VIP address moving)
// put into the status the page gets. Everything put back at the end.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const { execSync } = require('child_process');
const F = '/var/www/otp/.upgrade.json';
const V = (fs.readFileSync('/var/www/otp/otp-page.php', 'utf8').match(/OTP_VERSION = '([0-9.]+)'/) || [])[1];
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 500) + ')')); }
const now = () => Math.floor(Date.now() / 1000);
function tell(o) {
  fs.writeFileSync(F + '.t', JSON.stringify(Object.assign({state: 'running', id: 'k1', version: '9.9.9', from: V, by: 'admin on the pages',
    node: 'vm', part: 3, parts: 8, words: 'The daemon', started: now() - 20, at: now(), said: '', downgrade: false}, o || {})));
  fs.chmodSync(F + '.t', 0o644); fs.renameSync(F + '.t', F);
}
const daemonPid = () => { try { return execSync("pgrep -f '^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'").toString().trim().split('\n')[0]; } catch (e) { return ''; } };
function stopDaemon() { const p = daemonPid(); if (p) execSync('kill ' + p); for (let i = 0; i < 60 && daemonPid(); i++) execSync('sleep 0.5'); console.log('.. stopped ' + p); }
function startDaemon() { require('child_process').spawnSync('setsid', ['bash', '/home/claude/ws/tests/dg/startd.sh'], { stdio: 'ignore', timeout: 90000 }); }
async function apiUp() { for (let i = 0; i < 60; i++) { try { execSync('curl -sk -m 3 -o /dev/null -w "%{http_code}" https://127.0.0.1/healthz | grep -q 200', { stdio: ['ignore', 'pipe', 'pipe'], timeout: 10000 }); return true; } catch (e) { await new Promise(x => setTimeout(x, 1000)); } } return false; }
const health = () => { try { return execSync('curl -sk -m 5 -w "|%{http_code}" https://127.0.0.1/healthz').toString(); } catch (e) { return String(e.stdout || ''); } };
(async () => {
  try { fs.unlinkSync(F); } catch (e) { }
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(3000);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  // an upgrade ended before (another test's) hidden, as "Hide this" on Settings → Upgrades does
  await p.evaluate(async () => { try { const d = await api('upgrade'); if (d.plan && d.plan.state !== 'running') await api('upgrade', {action: 'hide'}); } catch (e) { } });
  await p.reload(); await p.waitForTimeout(2500);
  const look = () => p.evaluate(() => {
    const u = document.getElementById('upband'), o = document.getElementById('offline'), t = document.getElementById('toast');
    return { band: u && !u.hidden ? u.innerText : '', bad: !!(u && u.classList.contains('bad')), offline: o && !o.hidden ? o.innerText : '',
      pill: (document.getElementById('state-pill') || {}).innerText || '', toast: t && t.classList.contains('show') && /bad/.test(t.className) ? t.innerText : '' };
  });
  let l = await look();
  ok('no file: no band', !l.band, l);

  tell();
  await p.waitForTimeout(6500);
  l = await look();
  ok('running (the daemon answers): the band, from the status', /being upgraded to 9\.9\.9/i.test(l.band) && /the daemon/i.test(l.band) && /step 3 of 8/i.test(l.band), l);
  ok('...from, asked by, so far', /from /i.test(l.band) && /asked by admin on the pages/i.test(l.band) && /so far/i.test(l.band), l);
  ok('...what it means, one node', /restart once/i.test(l.band) && /loads the new version by itself/i.test(l.band), l);

  tell({part: 6, words: 'The service restarts'});
  stopDaemon();
  await p.waitForTimeout(7000);
  l = await look();
  ok('the daemon away: "the API ... restarting", step 6 of 8 from the 503', /API of these pages is restarting/i.test(l.band) && /step 6 of 8/i.test(l.band), l);
  ok('...no red "not answering" bar, no red toast', !l.offline && !l.toast, l);
  ok('...the pill "in maintenance"', /in maintenance/i.test(l.pill), l);
  const h1 = health();
  ok('/healthz: 503 "maintenance vm: being upgraded to 9.9.9"', /maintenance vm: being upgraded to 9\.9\.9\n?\|503/.test(h1), h1);
  const st = await p.evaluate(async () => (await fetch('?api=upgrade-state')).json());
  ok('?api=upgrade-state without the daemon: the file, api false, the pages\' version', st.upgrading && st.upgrading.version === '9.9.9' && st.api === false && st.pages, st);
  const anon = execSync('curl -sk -m 5 "https://127.0.0.1/admin/?api=upgrade-state"').toString();
  ok('...asked without a session: no "by", no "said", no id', /9\.9\.9/.test(anon) && !/admin on the pages/.test(anon) && !/"id"/.test(anon), anon);
  const rel = await p.evaluate(async () => { const r = await fetch('?api=tokens'); return { s: r.status, d: await r.json() }; });
  ok('any API call while away: 503 with "upgrading", not "not answering"', rel.s === 503 && rel.d.upgrading && /being upgraded to 9\.9\.9/.test(rel.d.error), rel);

  // nginx and PHP away: nothing answers the page at all
  await p.route(/\?api=/, r => r.abort());
  await p.waitForTimeout(5000);
  l = await look();
  ok('nginx and PHP away: "nginx and PHP are restarting", no red', /nginx and PHP are restarting/i.test(l.band) && !l.offline && !l.toast, l);
  await p.unroute(/\?api=/);
  tell({part: 7, words: 'Done'});
  await p.waitForTimeout(4000);
  l = await look();
  ok('PHP back, the daemon not yet: step 7 of 8 from the file again', /step 7 of 8/i.test(l.band) && /API of these pages is restarting/i.test(l.band), l);

  // a signed-out page meanwhile
  const p2 = await (await b.newContext({ ignoreHTTPSErrors: true })).newPage();
  await p2.goto('https://127.0.0.1/admin/');
  const si = await p2.evaluate(() => { const x = document.getElementById('upband-in'); window.__mark = 1;
    return { band: x ? x.innerText : '', down: Array.from(document.querySelectorAll('.offline')).map(o => o.innerText).join('|') }; });
  ok('the sign-in page while the daemon is away: the band from the file', /being upgraded to|se aktualizuje na/i.test(si.band) && /7 \/ 8/.test(si.band), si);
  ok('...not "the daemon is not answering"', !/not answering/i.test(si.down), si);

  startDaemon();
  ok('the daemon back', await apiUp());
  await p.waitForTimeout(6000);
  l = await look();
  ok('back: the band again without "restarting", the pill as the status says', /being upgraded to 9\.9\.9/i.test(l.band) && !/restarting/i.test(l.band) && !/in maintenance/i.test(l.pill), l);
  await p2.waitForTimeout(3000);
  const si2 = await p2.evaluate(() => window.__mark === undefined);
  ok('the sign-in page loaded itself again once the daemon answered', si2);
  await p2.context().close();

  // done, to the version that answers: loaded again, once
  await p.evaluate(() => { VERSION_LOADED = '1.0.0'; window.__mark = 1; try { sessionStorage.removeItem('otp.upg.reload'); } catch (e) { } });
  tell({version: V, part: 8, words: 'To be done by hand'});
  await p.waitForTimeout(3500);
  tell({state: 'done', version: V, part: 8, words: 'otp ' + V + ' runs'});
  await p.waitForTimeout(6000);
  const re = await p.evaluate(() => ({ gone: window.__mark === undefined, key: sessionStorage.getItem('otp.upg.reload'), v: VERSION_LOADED }));
  ok('done, its version answers: the page loaded itself again', re.gone && re.key === V && re.v === V, re);
  await p.waitForTimeout(1500);
  await p.evaluate(() => { VERSION_LOADED = '1.0.0'; window.__mark = 1; });
  tell({state: 'running', version: V, part: 8});
  await p.waitForTimeout(6000);
  const once = await p.evaluate(() => ({ still: window.__mark === 1, band: document.getElementById('upband').innerText }));
  ok('...once: not again, "Load it again" offered instead', once.still && /load it again/i.test(once.band), once);
  await p.reload(); await p.waitForTimeout(2500);

  // failed
  tell({state: 'failed', id: 'k2', version: '9.9.9', part: 6, words: 'The service restarts', said: 'install.sh --upgrade stopped (exit 1) - otp ' + V + ' runs again'});
  await p.waitForTimeout(6500);
  l = await look();
  ok('failed: a red band, the reason, a way to Upgrades', l.bad && /upgrade to otp 9\.9\.9 failed/i.test(l.band) && /runs again/i.test(l.band) && /open upgrades/i.test(l.band), l);
  await p.click('#upband .upband-x');
  await p.waitForTimeout(6000);
  l = await look();
  ok('...hidden with ×, and stays hidden', !l.band, l);
  try { fs.unlinkSync(F); } catch (e) { }

  // a plan ended a moment ago (its "done" said 10 min), then an upgrade by hand: the file's, not the plan's
  tell({id: 'cli-1', version: '9.9.7', part: 2, words: 'The daemon'});
  await p.unrouteAll({ behavior: 'ignoreErrors' }); await p.route(/\?api=status(&|$)/, async (r) => {
    const res = await r.fetch(); const d = await res.json();
    d.upgrading = { id: 'old1', version: '1.0.200', from: '1.0.199', by: 'admin', at: now() - 400, state: 'done', downgrade: false, drain_s: 20,
      ended: now() - 300, steps: [{ name: 'vm', state: 'done', at: now() - 300 }] };
    try { await r.fulfill({ response: res, body: JSON.stringify(d) }); } catch (e) { }
  });
  await p.waitForTimeout(6000);
  l = await look();
  ok('a plan ended lately, an upgrade by hand now: the band says the one that runs', /being upgraded to 9\.9\.7/i.test(l.band) && /step 2 of 8/i.test(l.band) && !/1\.0\.200/.test(l.band), l);
  await p.unrouteAll({ behavior: 'ignoreErrors' });
  try { fs.unlinkSync(F); } catch (e) { }

  // a cluster's plan in the status (HA): two nodes, the VIP address moving between them
  const plan = (ver, nodeVer) => async (r) => {
    const res = await r.fetch(); const d = await res.json();
    d.upgrading = { id: 'p1', version: ver, from: '1.0.1', by: 'admin', at: now() - 60, state: 'running', downgrade: false, drain_s: 20, ended: 0,
      steps: [{ name: 'nodea', state: 'done', at: now() - 30 }, { name: 'nodeb', state: 'installing', part: 3, part_words: 'The pages', at: now(), asked: now() - 20 }] };
    if (nodeVer) d.version = nodeVer;
    try { await r.fulfill({ response: res, body: JSON.stringify(d) }); } catch (e) { }
  };
  await p.unrouteAll({ behavior: 'ignoreErrors' }); await p.route(/\?api=status(&|$)/, plan('9.9.8'));
  await p.waitForTimeout(6000);
  l = await look();
  ok('HA: both nodes in the band, one at a time', /nodea/.test(l.band) && /nodeb/.test(l.band) && /one at a time/i.test(l.band) && /the pages/i.test(l.band), l);
  await p.evaluate(() => { window.__mark = 1; try { sessionStorage.removeItem('otp.upg.reload'); } catch (e) { } });
  await p.waitForTimeout(5000);
  ok('...the node answering is still the old version: not loaded again', await p.evaluate(() => window.__mark === 1));
  await p.unrouteAll({ behavior: 'ignoreErrors' });
  await p.unrouteAll({ behavior: 'ignoreErrors' }); await p.route(/\?api=status(&|$)/, plan(V, V));
  await p.evaluate(() => { VERSION_LOADED = '1.0.1'; window.__mark = 1; });
  await p.waitForTimeout(6000);
  ok('...the VIP address moved to the node upgraded already: its pages loaded, once', await p.evaluate((v) => window.__mark === undefined && sessionStorage.getItem('otp.upg.reload') === v, V));
  await p.unrouteAll({ behavior: 'ignoreErrors' });
  await p.evaluate(() => { try { sessionStorage.removeItem('otp.upg.reload'); localStorage.removeItem('otp.upg.hide'); } catch (e) { } });
  await p.waitForTimeout(6000);
  l = await look();
  ok('no plan, no file: no band', !l.band, l);
  ok('no page errors', errs.length === 0, errs);
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
  try { fs.unlinkSync(F); } catch (e) { }
  if (!daemonPid()) startDaemon();
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL broke: ' + e); try { fs.unlinkSync(F); } catch (x) { } if (!daemonPid()) startDaemon(); process.exit(1); });
