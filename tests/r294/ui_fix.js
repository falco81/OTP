// ui_fix.js - 1.0.294 hunt, the pages in a real Chromium on the installed otp (standalone):
//  - 400 px wide: the NTP servers' rows, the remote-backup grid and the token window's sections
//    stay inside their card (they spilled past it);
//  - the Tokens quick view: "never used" is the server's count, the locked ones asked for on
//    their own; the Let-in quick view: People is the day's count; a name opens the Log on the day.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 400, height: 860 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  const asked = [];
  await p.route(/[?&]api=(tokens|activity|dashboard)\b/, async (route) => {
    const u = route.request().url(); asked.push(u);
    const r = await route.fetch();
    let d; try { d = await r.json(); } catch (e) { await route.fulfill({ response: r }); return; }
    const now = Date.now() / 1000;
    if (/api=tokens/.test(u) && /sort=locked_until/.test(u)) d.rows = [{ name: 'locked.never', last_used: null, locked_until: now + 600, state: 'active' }];
    else if (/api=tokens/.test(u)) { d.rows = [{ name: 'used.one', last_used: now - 60, state: 'active' }]; d.counts = Object.assign({}, d.counts, { never_used: 1234 }); }
    else if (/api=activity/.test(u)) { d.rows = [{ name: 'novak', ts: now - 30, result: 'accept' }]; d.total = 500; }
    else if (/api=dashboard/.test(u)) d.people = 321;
    await route.fulfill({ response: r, json: d });
  });
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  await p.keyboard.press('Enter');
  await p.waitForTimeout(3000);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  await p.reload(); await p.waitForTimeout(3000);

  // ---- 400 px: the rows stay inside their card ----
  const fit = await p.evaluate(() => {
    const host = document.querySelector('main') || document.body;
    const card = el('div', 'card'); card.style.maxWidth = '100%'; host.prepend(card);
    NTP.d = NTP.d || {}; NTP.draft = { manage: true, servers: [{ host: 'ntp.example.cz', kind: 'server', iburst: true, prefer: false, nts: false }] };
    let f; try { f = ntpForm(); } catch (e) { return { err: String(e) }; }
    card.appendChild(f);
    const rb = el('div', 'rb-grid'); for (let i = 0; i < 2; i++) rb.appendChild(el('div', 'card', 'a destination card')); card.appendChild(rb);
    const ms = el('div', 'msects'); for (let i = 0; i < 2; i++) ms.appendChild(el('div', '', 'a section')); card.appendChild(ms);
    const out = (n) => { if (!n) return 'none'; const c = card.getBoundingClientRect(); return [...n.querySelectorAll('*')].concat([n]).filter(x => { const r = x.getBoundingClientRect(); return r.width && r.right > c.right + 1; }).length; };
    const res = { ntp: out(card.querySelector('.ntp-srv')), rb: out(rb), ms: out(ms), page: document.documentElement.scrollWidth };
    card.remove();
    return res;
  });
  ok('400 px: an NTP server row inside its card', fit.ntp === 0, fit);
  ok('400 px: the remote-backup grid inside its card', fit.rb === 0, fit);
  ok('400 px: the token window sections inside their card', fit.ms === 0, fit);

  // ---- the Tokens quick view ----
  await p.evaluate(() => peekTokensCard && (window._pk = 1));
  await p.evaluate(() => { const c = document.getElementById('card-tokens'); if (c) c.click(); else peekTokensCard(); });
  await p.waitForTimeout(2000);
  const tk = await p.evaluate(() => { const m = document.querySelector('.modal, dialog[open], .mbox'); return m ? m.innerText : document.body.innerText.slice(0, 3000); });
  ok('tokens: never used is the server\'s count', /1,?234 never used yet/.test(tk), tk.slice(0, 500));
  ok('tokens: the locked one asked for on its own is listed', /locked\.never/.test(tk) && /Locked out now/.test(tk), tk.slice(0, 500));
  ok('tokens: asked sorted by locked_until', asked.some(u => /sort=locked_until&desc=1/.test(u)));
  await p.evaluate(() => closeModal());
  await p.waitForTimeout(500);

  // ---- the Let-in quick view ----
  await p.evaluate(() => peekActivity('Let in - the last 24 hours', 'accept', 'Open the Log'));
  await p.waitForTimeout(2000);
  const ac = await p.evaluate(() => { const m = document.querySelector('.modal, dialog[open], .mbox'); return m ? m.innerText : ''; });
  ok('let in: People is the day\'s count from the server', /people\s*321/i.test(ac), ac.slice(0, 400));
  const stored = await p.evaluate(async () => {
    let got = null; const was = openRequests; window.openRequests = function (f) { got = f; };
    try { openRequests = window.openRequests; } catch (e) {}
    const n = document.querySelector('.fct.tappable, .fct'); if (n) n.click();
    await new Promise(r => setTimeout(r, 300));
    try { openRequests = was; } catch (e) {}
    return got;
  });
  ok('let in: a name opens the Log on the day the view counted', stored && stored.name === 'novak' && stored.since > Date.now() / 1000 - 86400 - 60, stored);
  ok('no errors on the page', errs.length === 0, errs);
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL crashed ' + e); console.log('ALL 0 / 1'); process.exit(1); });
