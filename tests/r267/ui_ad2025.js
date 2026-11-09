// ui_ad2025.js - Settings → Directories (1.0.267): a directory over plain LDAP says Windows Server 2025
// refuses it; one with a server given by address (the certificate checked) says to give the name; one by
// name says nothing. English and Czech, a phone's width, no horizontal scroll. Its directories taken away after.
const { chromium } = require('playwright');
const fs = require('fs');
const R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const DIRS = [
  {name: 'zz267-plain', hosts: 'dc1.example.local', port: 389, tls: 'none', base: 'DC=example,DC=local', verify: 1, enabled: 1},
  {name: 'zz267-ip', hosts: '10.0.0.10, dc2.example.local', port: 636, tls: 'ldaps', base: 'DC=example,DC=local', verify: 1, enabled: 1},
  {name: 'zz267-good', hosts: 'dc1.example.local, dc2.example.local', port: 636, tls: 'ldaps', base: 'DC=example,DC=local', verify: 1, enabled: 1},
];
(async () => {
  const b = await chromium.launch();
  let p;
  const api = (k, body) => p.evaluate(async ([k, body]) => {
    const r = await fetch('?api=' + k, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
    return r.json();
  }, [k, body]);
  try {
    for (const [lang, width] of [['en', 1400], ['cs', 1400], ['cs', 390]]) {
      const tag = lang + '@' + width + ': ';
      const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1400 } });
      p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e)));
      await p.goto('https://127.0.0.1/admin/');
      await p.fill('input[autocomplete=username]', 'admin');
      await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
      await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
      await api('prefs', {lang});
      for (const d of DIRS) await api('directories', {action: 'save', directory: d});
      await p.goto('https://127.0.0.1/admin/#settings/dir'); await p.reload(); await p.waitForTimeout(3500);
      const card = n => p.locator('#ad-table .itemcard', { has: p.locator('.ic-title b', { hasText: n }) });
      const tPlain = await card('zz267-plain').innerText(), tIp = await card('zz267-ip').innerText(), tGood = await card('zz267-good').innerText();
      if (lang === 'en') {
        ok(tag + 'plain LDAP: Windows Server 2025 refuses it', /Windows Server 2025 refuse a sign-in/.test(tPlain), tPlain);
        ok(tag + 'by address: give the name (FQDN), the address shown', /Give the name \(FQDN\)/.test(tIp) && tIp.includes('10.0.0.10'), tIp);
      } else {
        ok(tag + 'plain LDAP in Czech', /Windows Serverem 2025 přihlášení přes něj odmítnou/.test(tPlain), tPlain);
        ok(tag + 'by address in Czech', /Zadejte místo toho jméno \(FQDN\)/.test(tIp) && tIp.includes('10.0.0.10'), tIp);
      }
      ok(tag + 'the address chip only for the address, not the name', (await card('zz267-ip').locator('.dir-ip .chip').allInnerTexts()).join(',') === '10.0.0.10');
      ok(tag + 'by name: nothing said', !/2025|FQDN/.test(tGood), tGood);
      const scroll = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      ok(tag + 'no horizontal scroll', !scroll);
      ok(tag + 'no page errors', errs.length === 0, errs.join(' | '));
      if (width === 390 || lang === 'en') await card('zz267-ip').screenshot({ path: '/tmp/claude-0/ui267-' + lang + '-' + width + '.png' });
      const all = (await api('directories')).directories || [];
      for (const d of all.filter(x => /^zz267-/.test(x.name))) await api('directories', {action: 'delete', id: d.id});
      await api('prefs', {lang: 'en'});
      await ctx.close();
    }
  } finally { await b.close(); }
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
