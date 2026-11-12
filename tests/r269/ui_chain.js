// ui_chain.js - Certificates and TLS (1.0.269): the node's certificate uploaded without its intermediate (its CA
// Issuers address dead): the line Chain red, "Complete the chain" (primary) and "Upload the missing authority";
// the dialog names the missing authority; the intermediate uploaded - the root missing next (a private CA), named;
// the root uploaded - green "a private root", "Check the chain", no upload button. English and Czech, a phone's
// width. The node's certificate as it was put back after (restore file given by the caller).
const { chromium } = require('playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');
const R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const DIR = process.argv[2], SHOTS = process.argv[3] || '';
const pki = JSON.parse(fs.readFileSync(DIR + '/pki.json', 'utf8'));
(async () => {
  const b = await chromium.launch();
  try {
    for (const [lang, width] of [['en', 1400], ['cs', 1400], ['cs', 390]]) {
      const tag = lang + '@' + width + ': ';
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1500 }, deviceScaleFactor: SHOTS && width === 1400 && lang === 'en' ? 2 : 1 });
      const p = await ctx.newPage();
      const errs = []; p.on('pageerror', e => errs.push(String(e)));
      const api = (k, body) => p.evaluate(async ([k, body]) => {
        const r = await fetch('?api=' + k, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
        return r.json();
      }, [k, body]);
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
      await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
      await api('prefs', {lang});
      const up = await api('web', {action: 'tls_upload', target: 'vm', cert: pki.leaf, key: pki.key});
      ok(tag + 'uploaded alone: the answer says incomplete, complete:false (not an error)', up.complete === false && /incomplete|neúplný/.test(up.message || ''), JSON.stringify(up).slice(0, 300));
      await p.goto('https://127.0.0.1/admin/#settings/web'); await p.reload(); await p.waitForTimeout(3500);
      const card = p.locator('.cert-card').first();
      const chainDd = card.locator('dt', { hasText: lang === 'cs' ? /Řetěz/ : 'Chain' }).locator('xpath=following-sibling::dd[1]');
      const red = await chainDd.locator('.bad').count() + (await chainDd.evaluate(e => e.classList.contains('bad') || !!e.querySelector('.bad')) ? 1 : 0);
      const color = await chainDd.evaluate(e => getComputedStyle(e.querySelector('.bad') || e).color);
      ok(tag + 'Chain: red, incomplete, the missing authority named', red > 0 && /T269UI Issuing CA/.test(await chainDd.innerText()) && color !== 'rgb(255, 255, 255)', [await chainDd.innerText(), color]);
      const comp = card.locator('button', { hasText: lang === 'cs' ? 'Doplnit řetězec' : 'Complete the chain' });
      const upl = card.locator('button', { hasText: lang === 'cs' ? 'Nahrát chybějící autoritu' : 'Upload the missing authority' });
      ok(tag + '"Complete the chain" primary, "Upload the missing authority" beside it', await comp.count() === 1 && /primary/.test(await comp.getAttribute('class')) && await upl.count() === 1);
      if (SHOTS && lang === 'en') await card.screenshot({ path: SHOTS + '/chain-incomplete-' + width + '.png' });
      await upl.click(); await p.waitForTimeout(500);
      const dlg = p.locator('#modal-box');
      ok(tag + 'the dialog: the missing authority named', /T269UI Issuing CA/.test(await dlg.innerText()));
      if (SHOTS && lang === 'en') await dlg.screenshot({ path: SHOTS + '/chain-upload-dialog.png' });
      await dlg.locator('textarea').fill(pki.int);
      await dlg.locator('button', { hasText: lang === 'cs' ? 'Přidat do řetězce' : 'Add it to the chain' }).click();
      await p.waitForTimeout(3000);
      const t2 = await chainDd.innerText();
      ok(tag + 'the intermediate added: next missing the private root, named (red)', /T269UI Root CA/.test(t2), t2);
      await upl.click(); await p.waitForTimeout(500);
      await dlg.locator('textarea').fill(pki.root);
      await dlg.locator('button', { hasText: lang === 'cs' ? 'Přidat do řetězce' : 'Add it to the chain' }).click();
      await p.waitForTimeout(3000);
      const t3 = await chainDd.innerText();
      const green = await chainDd.evaluate(e => !!(e.querySelector('.good') || e.classList.contains('good')));
      ok(tag + 'the root added: green, complete, "a private root"', green && /private root|soukromý kořen/.test(t3), t3);
      const root = await card.locator('dt', { hasText: lang === 'cs' ? /Kořen/ : 'Root' }).locator('xpath=following-sibling::dd[1]').innerText();
      ok(tag + 'Root: the private root named', /T269UI Root CA/.test(root), root);
      ok(tag + 'now "Check the chain" (not primary), no upload button',
         await card.locator('button', { hasText: lang === 'cs' ? 'Zkontrolovat řetězec' : 'Check the chain' }).count() === 1 && await upl.count() === 0);
      if (SHOTS && lang === 'en') await card.screenshot({ path: SHOTS + '/chain-private-root-' + width + '.png' });
      ok(tag + 'no horizontal scroll', !(await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)));
      ok(tag + 'no page errors', errs.length === 0, errs.join(' | '));
      await api('prefs', {lang: 'en'});
      await ctx.close();
    }
  } finally { await b.close(); }
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
