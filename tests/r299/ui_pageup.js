// ui_pageup.js - 1.0.299: a whole upgrade started from the pages (standalone), watched in Chromium:
// the package sent, the upgrade started, root's helper (as otp-upgrade.path would) running
// install.sh --upgrade, which restarts the daemon, PHP and nginx. The band all the way: the step
// of N, "restarting" while they are away, never a red bar or toast; at the end the page loads the
// version it was upgraded to, once. The same version again (a retry) - so the version the page
// came with is said to be older once the daemon has gone away.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const cp = require('child_process');
const F = '/var/www/otp/.upgrade.json';
const V = (fs.readFileSync('/var/www/otp/otp-page.php', 'utf8').match(/OTP_VERSION = '([0-9.]+)'/) || [])[1];
const PKG = '/home/claude/build/out/otp-' + V + '.tar.gz';
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 600) + ')')); }
const sleep = ms => new Promise(x => setTimeout(x, ms));
let loop = null;
function cleanup() {
  if (loop && loop.pid) { try { process.kill(-loop.pid); } catch (e) { } }
  try { fs.unlinkSync(F); } catch (e) { }
}
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
  await p.goto('https://127.0.0.1/admin/#settings/upgrade'); await p.waitForTimeout(3000);
  await p.evaluate(() => { try { sessionStorage.removeItem('otp.upg.reload'); } catch (e) { } });
  ok('the package there', fs.existsSync(PKG), PKG);
  // a package sent before (another build of the same version) thrown away first: "ready" is then this one's
  await p.evaluate(async () => { try { await api('upgrade', {action: 'forget'}); } catch (e) { } });
  await p.reload(); await p.waitForTimeout(2500);
  await p.setInputFiles('#up-file', PKG);
  const want = require('crypto').createHash('sha256').update(fs.readFileSync(PKG)).digest('hex');
  let ready = false;
  for (let i = 0; i < 120 && !ready; i++) {
    await sleep(1000);
    ready = await p.evaluate(async (sha) => { try { const d = await api('upgrade'); return !!(d.package && d.package.sha === sha && d.ready); } catch (e) { return false; } }, want);
  }
  const why = await p.evaluate(() => $('up-ready').innerText);
  ok('sent and checked: it may be started', ready, why);
  if (!ready) throw new Error('not ready: ' + why);
  // root's side, as otp-upgrade.path: the request taken once, by the helper
  loop = cp.spawn('setsid', ['bash', '-c', 'for i in $(seq 1 240); do if [ -f /var/lib/otp/upgrade/request.json ]; then ' +
    '/usr/local/lib/otp/python -I /usr/local/lib/otp/otp_upgrade.py >> /tmp/claude-0/r299-root.log 2>&1; exit 0; fi; sleep 1; done'],
    { detached: true, stdio: 'ignore' });
  const start = await p.evaluate(async () => { try { const r = await api('upgrade', {action: 'start'}); return r.plan ? r.plan.id : 'started'; } catch (e) { return 'ERR ' + e.message; } });
  ok('the upgrade started', !/^ERR/.test(start), start);
  const seen = { band: 0, step: '', parts: 0, away: 0, php: 0, offline: '', toast: '', reloaded: false, maint: 0, faked: false };
  for (let i = 0; i < 300 && !seen.reloaded; i++) {
    await sleep(1000);
    let l;
    try {
      l = await p.evaluate(() => {
        const u = document.getElementById('upband'), o = document.getElementById('offline'), t = document.getElementById('toast');
        return { band: u && !u.hidden ? u.innerText : '', offline: o && !o.hidden ? o.innerText : '',
          toast: t && t.classList.contains('show') && /bad/.test(t.className) ? t.innerText : '', pill: ($('state-pill') || {}).innerText || '',
          away: typeof UPG === 'object' ? UPG.away : 0, mark: window.__mark, v: typeof VERSION_LOADED === 'string' ? VERSION_LOADED : '-',
          ctx: window.__ctx || (window.__ctx = Math.random().toString(36).slice(2, 7)), key: sessionStorage.getItem('otp.upg.reload'),
          rl: typeof UPG === 'object' ? UPG.reloading : null, offer: typeof UPG === 'object' ? UPG.offer : null, url: location.pathname, why: typeof UPG === 'object' ? UPG.why : '', mt: !$('modal') || $('modal').hidden ? '' : ($('modal-title') || {}).innerText, dk: Object.keys(DIRTY || {}).join(','), pk: Object.keys(PENDING || {}).join(',') };
      });
    } catch (e) { continue; }                 // the page being loaded again
    if (process.env.DBG) console.log('.. ' + JSON.stringify({ c: l.ctx, a: l.away ? 1 : 0, m: l.mark, v: l.v, k: l.key, rl: l.rl, o: l.offer, u: l.url, w: l.why, mt: l.mt, dk: l.dk, pk: l.pk, b: l.band.split('\n').slice(-1)[0].slice(0, 60) }));
    if (/being upgraded to/i.test(l.band)) seen.band++;
    const m = /step (\d+) of (\d+)/i.exec(l.band);
    if (m) { seen.step = m[0]; seen.parts = +m[2]; }
    if (/API of these pages is restarting/i.test(l.band)) seen.away++;
    if (/nginx and PHP are restarting/i.test(l.band)) seen.php++;
    if (/in maintenance/i.test(l.pill)) seen.maint++;
    if (l.offline) seen.offline = l.offline;
    if (l.toast) seen.toast = l.toast;
    if (l.away && !seen.faked) {
      seen.faked = true;
      await p.evaluate(() => { VERSION_LOADED = '1.0.0'; window.__mark = 1; });
    } else if (seen.faked && l.mark === undefined && l.v === V) {
      seen.reloaded = true;
    }
  }
  ok('the band while it ran', seen.band > 3, seen);
  ok('...the steps of install.sh, step N of M (M counted with root\'s check)', seen.parts >= 7, seen);
  ok('...the daemon away was "restarting" (or nginx and PHP), with the pill "in maintenance"', (seen.away + seen.php) > 0 && seen.maint > 0, seen);
  ok('...never the red "not answering" bar, never a red toast', !seen.offline && !seen.toast, seen);
  ok('at the end the page loaded the new version by itself', seen.reloaded, seen);
  let st = '';
  for (let i = 0; i < 60; i++) { await sleep(2000); st = (await p.evaluate(async () => (await api('upgrade')).plan.state)); if (st !== 'running') break; }
  ok('the plan done (checked, back in service)', st === 'done', st);
  let f = null;
  try { f = JSON.parse(fs.readFileSync(F, 'utf8')); } catch (e) { }
  const plan = await p.evaluate(async () => (await api('upgrade')).plan);
  for (let i = 0; i < 60 && !(f && f.state === 'done'); i++) { await sleep(2000); try { f = JSON.parse(fs.readFileSync(F, 'utf8')); } catch (e) { } }
  ok('the file: done, the plan\'s id, every step counted', f && f.state === 'done' && plan && f.id === plan.id && f.part === f.parts && f.parts === seen.parts, { f, plan: plan && plan.id });
  await sleep(6000);
  const after = await p.evaluate(() => ({ band: $('upband').hidden ? '' : $('upband').innerText, offline: !$('offline').hidden }));
  ok('afterwards: no band, no red bar', !after.band && !after.offline, after);
  ok('no page errors', errs.length === 0, errs);
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
  cleanup();
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL broke: ' + e); cleanup(); process.exit(1); });
