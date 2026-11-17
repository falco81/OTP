// ui_fix.js - 1.0.298 hunt, the pages in a real Chromium on the installed otp (standalone):
//  - an administrator's second step: the answer of a way given up (another way chosen meanwhile)
//    is not drawn into the way now shown; a way left alone is drawn as before.
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
  let fail = false;
  await p.route(/\?api=mfa(&|$)/, async (r) => {
    await new Promise(x => setTimeout(x, 700));
    if (fail) return r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ error: 'no way' }) });
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ qr: 'data:image/gif;base64,R0lGODlhAQABAAAAACw=', secret: 'ABCDEF', sent_to: 'a@b.c', send: null }) });
  });
  const run = async (first, then, failIt) => {
    fail = !!failIt;
    return p.evaluate(async ([first, then]) => {
      const body = el('div'); document.body.appendChild(body);
      const d = {};
      mfaWay(body, d, first);
      if (first !== 'app') {
        const box = body.querySelector('input'); box.value = 'a@b.c';
        Array.from(body.querySelectorAll('button')).find(x => /send/i.test(x.textContent)).click();
      }
      if (then) mfaWay(body, d, then);
      await new Promise(x => setTimeout(x, 1500));
      const r = { img: !!body.querySelector('img'), inputs: body.querySelectorAll('input').length, text: body.innerText,
        bad: !!body.querySelector('.said.bad') };
      body.remove();
      return r;
    }, [first, then]);
  };
  const a = await run('app', null);
  ok('the app alone: its QR code and a code box, as before', a.img && a.inputs >= 1, a);
  const a2 = await run('app', 'passkey');
  ok('the app, then a passkey chosen: no QR code or code box drawn into it', !a2.img && a2.inputs === 0 && /passkey/i.test(a2.text), a2);
  const a3 = await run('app', 'passkey', true);
  ok('...its failure not drawn into it either', !a3.bad, a3);
  const m1 = await run('mail', null);
  ok('the mail alone: "sent" and a code box, as before', m1.inputs >= 2, m1);
  const m2 = await run('mail', 'passkey');
  ok('the mail sent, then a passkey chosen: no code box drawn into it', m2.inputs === 0, m2);
  ok('no page errors', errs.length === 0, errs);
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  await b.close();
  process.exit(R.every(x => x) ? 0 : 1);
})();
