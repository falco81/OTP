// ui_pane.js - 1.0.301: SELinux on a pane of its own (Settings → SELinux, under High security), the card as
// the kit draws it: a light for each node beside the title, "each machine's own", "refused nothing" in green.
// The answer of ?api=selinux given by the test.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
const now = Math.floor(Date.now() / 1000);
const base = { config: 'permissive', policy: 'targeted', relabel_pending: false, cmdline_off: false, tools: {}, module: true, labels: [], booleans: [], ports: [],
  auditd: true, findings: [], local_rules: [], counts: {}, denials: { tool: true, total: 0, groups: [], since: 0 }, problems: [] };
const VIEW = { nodes: [{ name: 'otp1', me: true, state: Object.assign({}, base, { mode: 'Permissive', ready: true }), at: now, error: '', said: [], action: 'check', pending: '' },
                       { name: 'otp2', me: false, state: Object.assign({}, base, { mode: 'Enforcing', config: 'enforcing', ready: false }), at: now, error: '', said: [], action: 'check', pending: '' }],
               reports: {} };
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  for (const [lang, width] of [['en', 1500], ['cs', 1280], ['cs', 390]]) {
    const tag = lang + '@' + width + ': ';
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    await p.route(/\?api=selinux(&|$)/, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(VIEW) }));
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
    await p.goto('https://127.0.0.1/admin/#settings/hisec'); await p.reload(); await p.waitForTimeout(3000);
    const rail = await p.evaluate(() => Array.from(document.querySelectorAll('#ctl-nav [data-pane], [data-pane]')).map(x => x.getAttribute('data-pane')));
    ok(tag + 'the rail: SELinux right under High security', rail.indexOf('selinux') === rail.indexOf('hisec') + 1, rail.slice(0, 40));
    ok(tag + 'High security no longer holds the SELinux cards', await p.locator('#pane-hisec .se-node').count() === 0);
    await p.goto('https://127.0.0.1/admin/#settings/selinux'); await p.reload(); await p.waitForTimeout(3500);
    const pane = p.locator('#pane-selinux');
    ok(tag + 'Settings → SELinux: its title and what it is', await pane.isVisible() && /SELinux/.test(await pane.locator('.ctl-title').innerText()));
    ok(tag + '...a card for each node', await pane.locator('.se-node').count() === 2);
    const dots = await pane.locator('.se-card > h2 .se-chip .dot').evaluateAll(xs => xs.map(x => x.className));
    ok(tag + '...a light for each node beside the title: permissive yellow, enforcing green', JSON.stringify(dots) === JSON.stringify(['dot warn', 'dot ok']), dots);
    ok(tag + '..."each machine\'s own" said', (await pane.locator('.se-card > p.note.small').count()) === 1);
    ok(tag + '...nothing refused: said in green on each node', await pane.locator('.se-none').count() === 2);
    if (lang === 'cs') ok(tag + 'in Czech', /SELinux na tomto uzlu nic neodepřel/.test(await pane.innerText()) && /patří každému stroji zvlášť/.test(await pane.innerText()), (await pane.innerText()).slice(0, 300));
    const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(tag + 'no horizontal scroll', over <= 0, over);
    ok(tag + 'no page errors', errs.length === 0, errs);
    /* the language put back: the tests after this one read the pages in English */
    await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL broke: ' + e); process.exit(1); });
