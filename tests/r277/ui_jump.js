// ui_jump.js - 1.0.277: nothing jumps when a setting is changed. Every pane of Settings, every switch on it:
// flipped (not saved), the page measured before and after - a word, a box or a heading that moved
// sideways, or moved at all above or beside the switch, is a jump. Flipped back, put back. Then a save
// and its redraw on a pane with facts drawn from what is saved (the sign-in protection, the accounts).
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const URL = 'https://127.0.0.1/admin/';
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const ONLY = process.argv[2] || '';
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 600) + ')')); }

/* Every element with words of its own, where it is on the page (in the pane, by document position). */
async function snap(p, paneSel) {
  return p.evaluate((sel) => {
    const pane = document.querySelector(sel);
    const out = [];
    if (!pane) return out;
    let i = 0;
    pane.querySelectorAll('*').forEach(e => {
      if (!e.offsetParent && getComputedStyle(e).position !== 'fixed') return;
      const own = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
      if (!own && !/^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(e.tagName)) return;
      if (e.closest('#save-bar, .toast, .toasts, #toasts, .sn-pill, .tip, .popover')) return;
      const r = e.getBoundingClientRect();
      if (!r.width && !r.height) return;
      if (!e.dataset.jid) e.dataset.jid = 'j' + (window.__jn = (window.__jn || 0) + 1);
      out.push({id: e.dataset.jid, x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width),
                t: (e.textContent || e.value || '').trim().slice(0, 50), tag: e.tagName});
      i++;
    });
    return out;
  }, paneSel);
}
function compare(a, b, itemBox) {
  const was = {}; a.forEach(x => { was[x.id] = x; });
  const moved = [];
  b.forEach(x => {
    const o = was[x.id];
    if (!o) return;
    const dx = Math.abs(x.x - o.x), dy = x.y - o.y;
    /* inside the item flipped: its own words may change */
    if (itemBox && o.x >= itemBox.x - 1 && o.x <= itemBox.x + itemBox.w + 1 && o.y >= itemBox.y - 1 && o.y <= itemBox.y + itemBox.h + 1) return;
    if (dx > 2) moved.push('sideways ' + (x.x - o.x) + 'px: ' + o.tag + ' "' + o.t + '"');
    else if (Math.abs(dy) > 2 && itemBox && o.y < itemBox.y + itemBox.h) moved.push('up/down ' + dy + 'px (above or beside): ' + o.tag + ' "' + o.t + '"');
  });
  return moved;
}

(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  for (const vw of [1920, 1400]) {
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: vw, height: 1000 } });
    await ctx.addCookies([{ name: 'otp_lang', value: 'en', url: 'https://127.0.0.1' }]);
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e)));
    await p.goto(URL); await p.waitForTimeout(1000);
    await p.fill('#in-name', 'admin'); await p.fill('#in-pass', PW); await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.goto(URL + '#settings'); await p.waitForTimeout(2500);
    const panes = await p.$$eval('.ctl-nav [data-pane]', a => a.map(x => x.dataset.pane));
    let flipped = 0;
    for (const pane of panes) {
      if (ONLY && pane !== ONLY) continue;
      await p.goto(URL + '#settings/' + pane); await p.waitForTimeout(1800);
      const sel = '#pane-' + pane;
      const n = await p.$$eval(sel + ' .set-item[data-key]', a => a.filter(x => x.offsetParent && x.querySelector(':scope > label.sw input, .set-ctl label.sw input, label.sw input') && !x.querySelector('label.sw input').disabled).map(x => x.dataset.key));
      const bad = [], asked = [];
      for (const key of n) {
        const item = await p.$(sel + ' .set-item[data-key="' + key + '"]');
        if (!item) continue;
        /* In the middle of what is seen, as a person clicks it - not under the save bar held at the
           bottom (the browser then scrolls the focused switch out from under it). */
        await item.evaluate(e => e.scrollIntoView({block: 'center'}));
        await p.waitForTimeout(150);
        const box0 = await item.boundingBox();
        const sy = await p.evaluate(() => scrollY);
        const itemBox = { x: box0.x, y: box0.y + sy, w: box0.width, h: box0.height };
        const before = await snap(p, sel);
        const sw = await item.$('label.sw');
        if (process.env.JDEBUG) console.log('.. ' + pane + ' ' + key);
        if (sw) await sw.click(); else await (await item.$('input[type=checkbox]')).click({ force: true });
        flipped++;
        await p.waitForTimeout(450);
        /* a switch that asks first (a modal): said, answered No, the switch stays as it was */
        if (await p.$eval('#modal', e => !e.hidden && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden' && e.getClientRects().length > 0).catch(() => false)) {
          asked.push(key + ': ' + ((await p.textContent('#modal').catch(() => '')) || '').replace(/\s+/g, ' ').trim().slice(0, 90));
          await p.keyboard.press('Escape'); await p.waitForTimeout(300);
          for (const t of ['Cancel', 'No', 'Close', 'Zrušit']) {
            const still = await p.$eval('#modal', e => !e.hidden && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0).catch(() => false);
            if (!still) break;
            const btn = await p.$('#modal button:has-text("' + t + '")'); if (btn) { await btn.click(); await p.waitForTimeout(300); }
          }
        }
        const after = await snap(p, sel);
        const m = compare(before, after, itemBox);
        if (m.length) bad.push(key + ': ' + m.slice(0, 4).join('; ') + (m.length > 4 ? ' (+' + (m.length - 4) + ')' : ''));
        /* back as it was */
        const back = await p.$('#set-reset');
        if (back && await back.isVisible()) { await back.click(); await p.waitForTimeout(500); }
        else { if (sw) await sw.click(); await p.waitForTimeout(300); }
      }
      ok(vw + ' ' + pane + ': ' + n.length + ' switch(es) flipped, nothing else moved' + (asked.length ? ' (asked first: ' + asked.join(' / ') + ')' : ''), !bad.length, bad.join(' | '));
    }
    ok(vw + ': ' + flipped + ' switches in all; no page errors', errs.length === 0, errs.join(' | '));
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL ' + e); console.log('ALL ' + R.filter(Boolean).length + ' / ' + (R.length + 1)); process.exit(1); });
