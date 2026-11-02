// ui_firstcode.js - the one-time code before the first token, in Chromium on the installed pages (1.0.228).
// Before: python3 ../cz/mockldap_cz.py PKG 23977 &, mkdir -p /var/spool/sms/outgoing (owner otp), python3 ui_firstcode_setup.py up;
// after: python3 ui_firstcode_setup.py down - everything as it was.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const SP = '/var/spool/sms/outgoing';
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
function lastSms() {
  const fs_ = fs.readdirSync(SP).filter(f => f.startsWith('otp-')).map(f => path.join(SP, f));
  if (!fs_.length) return null;
  fs_.sort((a, b) => fs.statSync(a).mtimeMs - fs.statSync(b).mtimeMs);
  const t = fs.readFileSync(fs_[fs_.length - 1], 'utf8');
  fs_.forEach(f => fs.unlinkSync(f));
  const m = t.split('\n\n').slice(1).join('\n\n').match(/\b(\d{6})\b/);
  return m ? m[1] : null;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'cs']) {
    for (const width of [1200, 390]) {
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 860 } });
      await ctx.addCookies([{ name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/' }]);
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e)));
      p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errs.push(m.text()); });
      await p.goto('https://127.0.0.1/');
      try { fs.readdirSync(SP).filter(f => f.startsWith('otp-')).forEach(f => fs.unlinkSync(path.join(SP, f))); } catch (e) {}
      await p.fill('#in-name', 'jcermak');
      await p.fill('#in-pass', 'Heslo-Žluťoučký-1');
      await p.click('#in-go');
      await p.waitForSelector('#gate-box', { timeout: 20000 });
      const t = await p.textContent('#gate-box');
      const tag = lang + '@' + width + ': ';
      ok(tag + 'the code asked for, where it went said (masked)', /\+420\*+222/.test(t) && !/603/.test(t), t);
      ok(tag + 'in the page\'s language', lang === 'en' ? /You have no token yet/.test(t) : /Ještě nemáte token/.test(t), t);
      ok(tag + 'the sign-in form hidden', await p.isHidden('#signin-form'));
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/r6ui/gate-' + lang + '-' + width + '.png', fullPage: true });
      await sleep(600);
      const code = lastSms();
      ok(tag + 'the SMS came', code, code);
      await p.fill('#gate-box input', '000000' === code ? '111111' : '000000');
      await p.click('#gate-box button[type=submit]');
      await p.waitForFunction(() => document.querySelector('#gate-box .gate-said').textContent.length > 2, null, { timeout: 10000 });
      const bad = await p.textContent('#gate-box .gate-said');
      ok(tag + 'a wrong code: said so, still asked', /not the code|není kód|nebyl|to není/i.test(bad), bad);
      await p.reload();
      await p.waitForSelector('#gate-box', { timeout: 10000 });
      ok(tag + 'reloaded: still the code asked for, not the pages', !(await p.$('#portal')));
      const lay = await p.evaluate(() => {
        const q = s => document.querySelector(s);
        const bs = [...document.querySelectorAll('.gate-actions .btn')].map(b => ({r: b.getBoundingClientRect(), fit: b.scrollWidth <= b.clientWidth + 1}));
        const card = q('#gate-box').getBoundingClientRect(), inp = q('.gate-code').getBoundingClientRect(), d = q('.gate-dest');
        return {two: bs.length === 2, row: bs.length === 2 && Math.abs(bs[0].r.top - bs[1].r.top) < 2,
                same: bs.length === 2 && Math.abs(bs[0].r.width - bs[1].r.width) < 2, fit: bs.every(b => b.fit),
                centred: Math.abs((inp.left + inp.right) / 2 - (card.left + card.right) / 2) < 3,
                destLine: d.getBoundingClientRect().height < 30 && d.scrollWidth <= d.clientWidth + 1};
      });
      ok(tag + 'the two buttons side by side, the same width, their words whole', lay.two && lay.row && lay.same && lay.fit, JSON.stringify(lay));
      ok(tag + 'the code box in the middle, the address on one line', lay.centred && lay.destLine, JSON.stringify(lay));
      if (width < 500) {
        // pasted from the message, as it came: words around it, a space inside
        await p.evaluate(c => {
          const dt = new DataTransfer(); dt.setData('text', 'Váš kód: ' + c.slice(0, 3) + ' ' + c.slice(3) + ' (platí 5 min)');
          document.querySelector('.gate-code').dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
        }, code);
      } else {
        await p.fill('#gate-box input', code.slice(0, 3) + ' ' + code.slice(3));
        await p.click('#gate-box button[type=submit]');
      }
      await p.waitForSelector('#portal .card', { timeout: 15000 });
      const pt = await p.textContent('#portal');
      ok(tag + (width < 500 ? 'the code pasted ("482 913" with words around): sent at once, ' : 'the code typed "482 913": ') + 'the enrolment pages open', /token|Token/.test(pt), pt.slice(0, 120));
      await p.screenshot({ path: '/tmp/claude-0/r6ui/after-' + lang + '-' + width + '.png', fullPage: true });
      ok(tag + 'no script errors', !errs.length, errs.join(' | '));
      await p.click('#signout');
      await sleep(800);
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL crashed', e); process.exit(1); });
