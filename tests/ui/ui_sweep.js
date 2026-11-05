// Live sweep of the admin pages and the portal (round 5, 1.0.249).
// Every tab and every #settings/<pane>, at 1500x1000 and 390x844, in English and Czech,
// with every <details> opened. One check = pane x viewport x language, passed when it had
// no console error / page error, no failed request (status >= 400 or network failure) and
// no horizontal overflow (the page scrolling sideways, or a segmented control cut off).
// Read only: it signs in, changes the hash and opens <details>; it never presses a button.
//   NODE_PATH=$(npm root -g) node tests/ui/ui_sweep.js [base-url] [only,panes]
// Prints FAIL lines with details and, last, "ALL n / m".
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = (process.argv[2] || 'https://127.0.0.1').replace(/\/$/, '');
const ONLY = process.argv[3] ? process.argv[3].split(',') : null;
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const VIEWS = [['wide', 1500, 1000], ['phone', 390, 844]];
const LANGS = ['en', 'cs'];
const TABS0 = ['overview', 'tokens', 'requests', 'test', 'enrolment', 'events'];

// The page has no per-request language switch: the index is rewritten to load the pack,
// as the server does for a user whose language is Czech.
async function forceLang(ctx, lang) {
  if (lang === 'en') return;
  await ctx.route(u => u.pathname === '/admin/' || u.pathname === '/admin/index.php', async route => {
    const resp = await route.fetch(); let body = await resp.text();
    if (body.indexOf('window.OTP_LANG = "en"') >= 0 && body.indexOf('api=lang') < 0) {
      const nonce = (body.match(/<script nonce="([^"]+)"/) || [])[1];
      body = body.replace('<html lang="en" class="app-shell-root', '<html lang="' + lang + '" class="app-shell-root i18n-wait')
        .replace('<script nonce="' + nonce + '">window.OTP_LANGS', '<script nonce="' + nonce + '" src="?api=lang&amp;code=' + lang + '"></script>\n<script nonce="' + nonce + '">window.OTP_LANGS')
        .replace('window.OTP_LANG = "en"', 'window.OTP_LANG = "' + lang + '"');
    }
    await route.fulfill({response: resp, body});
  });
}

function watch(page, state) {
  page.on('console', m => { if (m.type() === 'error') state.errs.push([state.cur, 'console: ' + m.text().slice(0, 200)]); });
  page.on('pageerror', e => state.errs.push([state.cur, 'pageerror: ' + String(e).slice(0, 200)]));
  page.on('response', r => { if (r.status() >= 400 && !(r.status() === 401 && state.cur === 'login'))
    state.errs.push([state.cur, 'http ' + r.status() + ' ' + r.request().method() + ' ' + r.url().replace(BASE, '').slice(0, 120)]); });
  page.on('requestfailed', r => state.errs.push([state.cur, 'request failed ' + r.url().replace(BASE, '').slice(0, 120) + ' ' + ((r.failure() || {}).errorText || '')]));
  page.on('dialog', d => { state.errs.push([state.cur, 'dialog: ' + d.message().slice(0, 100)]); d.dismiss().catch(() => {}); });
}

const OVERFLOW = () => {
  document.querySelectorAll('details').forEach(d => { d.open = true; });
  const vw = document.documentElement.clientWidth; const out = [];
  const sx = document.documentElement.scrollWidth - vw;
  const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  if (sx > 0) {
    // the widest box that is not inside a scroller of its own - text overflowing too
    let worst = null;
    document.querySelectorAll('body *').forEach(e => {
      if (!e.getClientRects().length || e.children.length) return;
      for (let x = e.parentElement; x && x !== document.body; x = x.parentElement) if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(x).overflowX)) return;
      const r = e.getBoundingClientRect(); const right = Math.max(r.right, r.left + e.scrollWidth);
      if (right > vw + 1 && (!worst || right > worst[1])) worst = [e, right];
    });
    out.push('page scrolls sideways by ' + sx + 'px' + (worst ? ' (' + name(worst[0]) + ' to ' + Math.round(worst[1]) + ': ' + (worst[0].textContent || '').trim().slice(0, 50) + ')' : ''));
  }
  // a segmented control whose buttons are cut off by its own overflow:hidden
  document.querySelectorAll('.seg').forEach(s => {
    if (!s.getClientRects().length) return; const r = s.getBoundingClientRect();
    [...s.children].forEach(b => { const q = b.getBoundingClientRect(); if (q.width && q.right > r.right + 2)
      out.push('segmented control cut off: "' + b.textContent.trim().slice(0, 40) + '" ends at ' + Math.round(q.right) + ', the control at ' + Math.round(r.right)); });
  });
  return out;
};

async function admin(browser, lang, vn, w, h) {
  const ctx = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: w, height: h}});
  ctx.setDefaultTimeout(120000);
  await forceLang(ctx, lang);
  const page = await ctx.newPage(); const st = {cur: 'login', errs: []}; watch(page, st);
  const res = [];
  await page.goto(BASE + '/admin/', {waitUntil: 'load'}); await page.waitForTimeout(800);
  await page.fill('input[autocomplete=username]', 'admin');
  await page.fill('input[type=password]', PW);
  await page.click('#in-go'); await page.waitForTimeout(2500);
  await page.goto(BASE + '/admin/#settings/about', {waitUntil: 'load', timeout: 120000}); await page.waitForTimeout(2500);
  const htmlLang = await page.evaluate(() => document.documentElement.lang);
  if (htmlLang !== lang) res.push({id: lang + ' ' + vn + ' sign-in', fails: ['the page is in ' + htmlLang + ', not ' + lang]});
  const panes = await page.$$eval('[data-pane]', els => [...new Set(els.map(e => e.getAttribute('data-pane')))]);
  const tabs = TABS0.concat(panes.map(p => 'settings/' + p)).filter(t => !ONLY || ONLY.includes(t));
  for (const t of tabs) {
    st.cur = t; const e0 = st.errs.length; const t0 = Date.now(); let over;
    try {
      await page.evaluate(t => { location.hash = '#' + t; }, t);
      await page.waitForTimeout(3000);
      over = await page.evaluate(OVERFLOW);
      await page.waitForTimeout(600);
      over = over.concat((await page.evaluate(OVERFLOW)).filter(x => over.indexOf(x) < 0));
    } catch (e) { over = ['could not be looked at: ' + String(e).slice(0, 120)]; }
    const took = Date.now() - t0;
    const fails = st.errs.slice(e0).map(x => x[1]).concat(over);
    if (took > 15000) fails.push('the page did not answer for ' + Math.round(took / 1000) + ' s (layout or script blocking it)');
    res.push({id: lang + ' ' + vn + ' ' + t, fails});
  }
  await ctx.close();
  return res;
}

async function portal(browser, lang, vn, w, h) {
  const ctx = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: w, height: h}});
  await ctx.addCookies([{name: 'otp_lang', value: lang, domain: new URL(BASE).hostname, path: '/', secure: true}]);
  const page = await ctx.newPage(); const st = {cur: 'portal', errs: []}; watch(page, st);
  await page.goto(BASE + '/', {waitUntil: 'load'}); await page.waitForTimeout(2500);
  const over = await page.evaluate(OVERFLOW);
  await ctx.close();
  return [{id: lang + ' ' + vn + ' portal', fails: st.errs.map(x => x[1]).concat(over)}];
}

(async () => {
  const browser = await chromium.launch();
  const jobs = [];
  for (const lang of LANGS) for (const [vn, w, h] of VIEWS) jobs.push(admin(browser, lang, vn, w, h).catch(e => [{id: lang + ' ' + vn + ' (run)', fails: [String(e).slice(0, 200)]}]));
  let all = [].concat(...await Promise.all(jobs));
  if (!ONLY || ONLY.includes('portal')) for (const lang of LANGS) for (const [vn, w, h] of VIEWS) all = all.concat(await portal(browser, lang, vn, w, h));
  await browser.close();
  let ok = 0;
  for (const r of all) {
    if (!r.fails.length) { ok++; continue; }
    const seen = new Set();
    r.fails.forEach(f => { if (!seen.has(f)) { seen.add(f); console.log('FAIL ' + r.id + ': ' + f); } });
  }
  console.log('ALL ' + ok + ' / ' + all.length);
  process.exit(ok === all.length ? 0 : 1);
})();
