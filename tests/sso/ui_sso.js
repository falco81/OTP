// ui_sso.js - signed in by a load balancer (1.0.239), in Chromium on the installed pages: the enrolment page signed in
// by the headers (no password), refused with a wrong key or none, Sign out held until asked again; the card on the
// administration pages - the last sign-in, the guides - in English and Czech, wide and narrow.
// Before: python3 ../cz/mockldap_cz.py PKG 23977 &, python3 ui_sso_setup.py up VER; after: python3 ui_sso_setup.py down VER.
const { chromium } = require('playwright');
const fs = require('fs');
const KEY = fs.readFileSync('/tmp/claude-0/ui_sso_key', 'utf8').trim();
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  fs.mkdirSync('/tmp/claude-0/ssoui', { recursive: true });
  for (const lang of ['en', 'cs']) {
    for (const width of [1200, 390]) {
      const tag = lang + '@' + width + ': ';
      const mk = async (headers) => {
        const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 900 }, extraHTTPHeaders: headers || {} });
        await ctx.addCookies([{ name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/' }]);
        const p = await ctx.newPage();
        p._errs = [];
        p.on('pageerror', e => p._errs.push(String(e)));
        p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) p._errs.push(m.text()); });
        return [ctx, p];
      };
      /* signed in by the headers */
      let [ctx, p] = await mk({ 'X-Otp-User': 'jcermak', 'X-Otp-Sso-Key': KEY });
      await p.goto('https://127.0.0.1/');
      await p.waitForSelector('#portal, #signin-form', { timeout: 20000 });
      ok(tag + 'the balancer\'s headers: signed in, no password asked', await p.$('#portal') && !(await p.$('#signin-form')), await p.content().then(t => t.slice(0, 300)));
      const me = await p.textContent('#mebtn').catch(() => '');
      ok(tag + '...as the person it named', /Čermák/.test(me), me);
      await p.waitForTimeout(800);
      await p.screenshot({ path: '/tmp/claude-0/ssoui/portal-' + lang + '-' + width + '.png', fullPage: true });
      await p.reload();
      await p.waitForSelector('#portal', { timeout: 10000 });
      ok(tag + 'reloaded: still signed in (the same session)', true);
      await p.click('#signout');
      await p.waitForSelector('#signin-form', { timeout: 10000 });
      ok(tag + 'Sign out (no sign-out of the balancer set): the sign-in page, not straight back in', !(await p.$('#portal')));
      const again = await p.$('#sso-again');
      ok(tag + '...with the way back to the company sign-in', again && /\?sso=1/.test(await again.innerHTML()), again && await again.innerHTML());
      const t1 = await p.textContent('#sso-again');
      ok(tag + '...in the page\'s language', lang === 'en' ? /You signed out/.test(t1) : /Odhlásili jste se/.test(t1), t1);
      await p.click('#sso-again a');
      await p.waitForSelector('#portal', { timeout: 10000 });
      ok(tag + '...followed: signed in by the balancer again', true);
      ok(tag + 'no errors on the page', !p._errs.length, p._errs.join(' | '));
      await ctx.close();
      /* a wrong key, no key */
      for (const [what, h] of [['a wrong key', { 'X-Otp-User': 'jcermak', 'X-Otp-Sso-Key': KEY.slice(0, -3) + 'zzz' }], ['no key', { 'X-Otp-User': 'jcermak' }]]) {
        [ctx, p] = await mk(h);
        await p.goto('https://127.0.0.1/');
        await p.waitForSelector('#signin-form', { timeout: 10000 });
        const said = await p.textContent('#sso-said').catch(() => '');
        ok(tag + what + ': the sign-in page with the password, the refusal said', !(await p.$('#portal')) && said.length > 10, said);
        await ctx.close();
      }
      /* the card on the administration pages */
      [ctx, p] = await mk();
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', PW);
      await p.keyboard.press('Enter');
      await p.waitForTimeout(2500);
      await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
      await p.goto('https://127.0.0.1/admin/#settings/portal');
      await p.reload();
      await p.waitForSelector('#sso-host .lb-facts', { timeout: 20000 });
      await p.waitForTimeout(800);
      const card = await p.textContent('#sso-card');
      ok(tag + 'the card: on, a key set', lang === 'en' ? /On/.test(card) && /A key is set/.test(card) : /Klíč je nastaven/.test(card), card.slice(0, 400));
      ok(tag + '...the last sign-in by the balancer: jcermak, signed in', /jcermak/.test(card) && (lang === 'en' ? /signed in/.test(card) : /přihlášen/.test(card)), card.slice(0, 600));
      ok(tag + '...the settings of it laid out in its own card', await p.$('#sect-portalsso #set-portal_sso_from'));
      const guides = await p.$$eval('#sso-host details.lb-guide summary b', x => x.map(e => e.textContent));
      ok(tag + '...the guides: NetScaler, F5, nginx, check', guides.length === 4 && /NetScaler/.test(guides[0]) && /F5/.test(guides[1]), guides);
      await p.click('#sso-host details.lb-guide summary');
      const code = await p.textContent('#sso-host details.lb-guide pre');
      ok(tag + '...NetScaler opened: the header and the commands filled in', /insert_http_header X-Otp-User AAA\.USER\.NAME/.test(code) && /delete_http_header X-Otp-User/.test(code), code.slice(0, 300));
      ok(tag + '...the key not in it (made elsewhere, never shown again)', !code.includes(KEY));
      if (lang === 'cs') {
        const h2 = await p.textContent('#sso-card h2');
        ok(tag + 'in Czech', /Přihlášení přes load balancer/.test(h2), h2);
      }
      const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
      ok(tag + 'no sideways scroll', wide);
      await p.screenshot({ path: '/tmp/claude-0/ssoui/card-' + lang + '-' + width + '.png', fullPage: false, clip: undefined });
      const el = await p.$('#sso-card');
      await el.screenshot({ path: '/tmp/claude-0/ssoui/cardonly-' + lang + '-' + width + '.png' });
      ok(tag + 'no errors on the administration page', !p._errs.length, p._errs.join(' | '));
      await ctx.close();
    }
  }
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
