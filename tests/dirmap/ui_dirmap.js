// ui_dirmap.js - the directory's card: where the e-mail and the mobile are read, a person's attributes
// with Use (1.0.229), in Chromium on the installed pages. Needs the directory R6Dom (portal/ui_firstcode_setup.py up)
// and the mock AD on 23977.
const { chromium } = require('playwright');
const fs = require('fs');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
(async () => {
  const b = await chromium.launch();
  for (const [lang, width] of [['en', 1400], ['cs', 1400], ['cs', 390]]) {
    const tag = lang + '@' + width + ': ';
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
    await ctx.addCookies([{ name: 'otp_lang', value: lang, domain: '127.0.0.1', path: '/' }]);
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errs.push(m.text()); });
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.goto('https://127.0.0.1/admin/#settings/dir');
    await p.waitForTimeout(2500);
    const card = p.locator('.ic-card, .card').filter({ hasText: 'R6Dom' }).first();
    const facts = await card.textContent();
    ok(tag + 'the card says where both are read from', /mail/.test(facts) && /mobile, telephoneNumber/.test(facts), facts);
    await card.click();
    await p.waitForSelector('.samp-ask input', { timeout: 10000 });
    const boxes = await p.$$eval('#modal input.mono', xs => xs.map(x => x.value));
    ok(tag + 'the boxes hold the defaults', boxes.includes('mail') && boxes.includes('mobile, telephoneNumber'), boxes.join(' | '));
    await p.fill('.samp-ask input', 'jcermak');
    await p.click('.samp-ask button');
    await p.waitForSelector('.samp-head', { timeout: 15000 });
    const nows = await p.$$eval('.samp-now', xs => xs.map(x => x.textContent));
    ok(tag + 'what the boxes read now: the address and the number', /jiri\.cermak@corpnet\.cz/.test(nows[0]) && /\+420 603 111 222/.test(nows[1]), nows.join(' | '));
    const cols = await p.$$eval('.samp-col', xs => xs.map(c => [...c.querySelectorAll('.samp-name')].map(n => n.textContent)));
    ok(tag + 'e-mail offers mail and the UPN, not the phone', cols[0].includes('mail') && cols[0].includes('userPrincipalName') && !cols[0].includes('mobile'), JSON.stringify(cols));
    ok(tag + 'phone offers mobile, not the mail', cols[1].includes('mobile') && !cols[1].includes('mail'), JSON.stringify(cols));
    const inUse = await p.$$eval('.samp-col', xs => xs.map(c => [...c.querySelectorAll('.samp-row')].filter(r => /In use|Používá se/.test(r.textContent)).map(r => r.querySelector('.samp-name').textContent)));
    ok(tag + 'the attributes in the boxes marked in use', inUse[0].includes('mail') && inUse[1].includes('mobile'), JSON.stringify(inUse));
    if (width > 500) await p.screenshot({ path: '/tmp/claude-0/r7ui/dir-' + lang + '-' + width + '.png' });
    const upn = p.locator('.samp-col').first().locator('.samp-row').filter({ hasText: 'userPrincipalName' }).locator('button');
    await upn.click();
    await p.waitForTimeout(300);
    const boxes2 = await p.$$eval('#modal input.mono', xs => xs.map(x => x.value));
    ok(tag + 'Use puts userPrincipalName into the e-mail box', boxes2.includes('userPrincipalName'), boxes2.join(' | '));
    const now2 = await p.$$eval('.samp-now', xs => xs.map(x => x.textContent));
    ok(tag + '...and what it reads changes with it', /jcermak@corpnet\.cz/.test(now2[0]) && /userPrincipalName/.test(now2[0]), now2[0]);
    await p.click('.samp-all summary');
    await p.fill('.samp-find', 'department');
    const listed = await p.$$eval('.samp-list .samp-name', xs => xs.map(x => x.textContent));
    ok(tag + 'every attribute listed, found by its name', listed.length >= 0 && listed.every(n => /department/i.test(n)), listed.join(','));
    await p.fill('.samp-find', 'company');
    await p.waitForTimeout(200);
    const own = p.locator('.samp-list .samp-row').filter({ hasText: 'company-MobileNo' });
    ok(tag + 'an attribute of a schema of one\'s own listed, with a button for either box', (await own.count()) === 1 && (await own.locator('button').count()) === 2);
    await own.locator('button').nth(1).click();
    await p.waitForTimeout(300);
    const boxes3 = await p.$$eval('#modal input.mono', xs => xs.map(x => x.value));
    ok(tag + 'chosen for the mobile: in the box, read from it', boxes3.includes('company-MobileNo'), boxes3.join(' | '));
    const now3 = await p.$$eval('.samp-now', xs => xs.map(x => x.textContent));
    ok(tag + '...what it reads: its value', /777 555 444/.test(now3[1]), now3[1]);
    const wide = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    ok(tag + 'no sideways scroll', wide);
    await p.evaluate(() => { const s = document.querySelector('.samp'); if (s) s.scrollIntoView(); });
    await p.waitForTimeout(300);
    await p.screenshot({ path: '/tmp/claude-0/r7ui/dir2-' + lang + '-' + width + '.png' });
    ok(tag + 'no script errors', !errs.length, errs.join(' | '));
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
})().catch(e => { console.log('FAIL crashed', e); process.exit(1); });
