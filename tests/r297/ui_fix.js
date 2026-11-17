// ui_fix.js - 1.0.297 hunt, the pages in a real Chromium on the installed otp (standalone):
//  - formField names the one box inside a wrapper (the code box with its send button);
//  - the code box is wide enough for "12345 67890" and no wider than a phone;
//  - the portal's code boxes are named for a screen reader; the reload after a last try only while
//    its card is there.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
(async () => {
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

  const f = await p.evaluate(() => {
    const wrap = el('div'); const box = el('input'); box.type = 'text'; const btn = el('button', '', 'Send');
    const hid = el('input'); hid.type = 'hidden';
    wrap.appendChild(hid); wrap.appendChild(box); wrap.appendChild(btn);
    const it = formField('The code', wrap); document.body.appendChild(it);
    const lab = it.querySelector('label');
    const two = el('div'); two.appendChild(el('input')); two.appendChild(el('input'));
    const it2 = formField('Two', two); document.body.appendChild(it2);
    const plain = el('input'); const it3 = formField('Plain', plain); document.body.appendChild(it3);
    const r = { one: !!lab.htmlFor && lab.htmlFor === box.id, two: !it2.querySelector('label').htmlFor,
      plain: !!plain.id && it3.querySelector('label').htmlFor === plain.id };
    it.remove(); it2.remove(); it3.remove();
    return r;
  });
  ok('formField: the one box inside a wrapper is named by the label', f.one, f);
  ok('...two boxes inside: none picked', f.two, f);
  ok('...a box itself: as before', f.plain, f);

  const w = await p.evaluate(() => {
    const host = el('div'); host.style.width = '600px'; const box = el('input', 'codein'); host.appendChild(box); document.body.appendChild(host);
    const wide = box.getBoundingClientRect().width;
    host.style.width = '200px';
    const narrow = box.getBoundingClientRect().width;
    host.remove();
    return { wide, narrow };
  });
  ok('the code box: 290 px where there is room (was 220)', Math.round(w.wide) === 290, w);
  ok('...no wider than its place on a phone', w.narrow <= 200, w);

  const pj = await p.evaluate(async () => (await fetch('/assets/portal.js')).text());
  ok('the portal\'s code boxes named for a screen reader', (pj.match(/box\.setAttribute\('aria-label', \(typeof i18nText === 'function' && i18nText\('The code'\)\) \|\| 'The code'\)/g) || []).length === 2);
  ok('...the reload after a last try only while its card is there', pj.includes("if (!document.body.contains(wrap)) return; api('me')"));
  ok('no page errors', errs.length === 0, errs);
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
  process.exit(R.every(x => x) ? 0 : 1);
})();
