// ui_find.js - 1.0.300: the SELinux card's findings on the installed pages (the answer of ?api=selinux
// given by the test): each kind with what root would do, the fixable ones ticked and counted, a confirm
// listing exactly that, only ids sent; otp's local rules taken away one by one; an enforcing node with
// nothing refused as before; Czech; a phone's width.
const { chromium } = require('playwright');
for (const k of ['HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'https_proxy', 'http_proxy', 'all_proxy']) delete process.env[k];
const fs = require('fs');
const R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || more === undefined ? '' : ' (' + String(typeof more === 'string' ? more : JSON.stringify(more)).slice(0, 400) + ')')); }
const now = Math.floor(Date.now() / 1000);
const F = (id, kind, extra) => Object.assign({ id, kind, whose: kind === 'other' ? 'other' : 'otp', count: 1, first: now - 7200, last: now - 7200,
  permissive: true, program: 'nginx', exe: '/usr/sbin/nginx', source: 'httpd_t', target: 'default_t', class: 'file', perms: ['read'],
  path: '', port: '', name: '', fix: null, why: '' }, extra);
const FIND = [
  F('aaaaaaaaaaa1', 'fixed', { program: 'otp-tick', source: 'unconfined_service_t', target: 'chronyc_t', class: 'process2', perms: ['nnp_transition'], why: 'put right (allow ...)', count: 2 }),
  F('aaaaaaaaaaa2', 'label', { path: '/var/www/otp/assets/core.js', count: 2, fix: { restorecon: '/var/www/otp/assets', cmd: 'restorecon -R -v /var/www/otp/assets' },
    why: '/var/www/otp/assets/core.js is labelled default_t - the policy says httpd_sys_content_t' }),
  F('aaaaaaaaaaa3', 'port', { program: 'sshd', source: 'sshd_t', target: 'unreserved_port_t', class: 'tcp_socket', perms: ['name_bind'], port: '2222/tcp',
    fix: { port: 2222, proto: 'tcp', type: 'ssh_port_t', cmd: 'semanage port -a -t ssh_port_t -p tcp 2222' }, why: 'port 2222/tcp has no type' }),
  F('aaaaaaaaaaa4', 'rule', { program: 'otp-tick', source: 'unconfined_service_t', target: 'hostname_t', class: 'process2', perms: ['nnp_transition'],
    fix: { rule: '(allow unconfined_service_t hostname_t (process2 (nnp_transition)))', cmd: '(allow unconfined_service_t hostname_t (process2 (nnp_transition)))' },
    why: 'nothing of the policy allows it: a rule of otp\'s own local module allows exactly this' }),
  F('aaaaaaaaaaa5', 'boolean', { program: 'php-fpm', target: 'unreserved_port_t', class: 'tcp_socket', perms: ['name_connect'], port: '9861/tcp',
    fix: { boolean: 'httpd_can_network_connect', cmd: 'setsebool -P httpd_can_network_connect 1' }, why: 'the boolean httpd_can_network_connect allows it' }),
  F('aaaaaaaaaaa6', 'nobutton', { program: 'php-fpm', target: 'shadow_t', path: '/etc/shadow', why: 'shadow_t is security-sensitive (file) - never allowed from here' }),
  F('aaaaaaaaaaa7', 'other', { program: 'smbd', source: 'smbd_t', target: 'home_root_t', class: 'dir', perms: ['write'], path: '/home/share',
    why: 'not otp\'s: smbd (smbd_t) is another program of this machine - look at it with whoever looks after it' }),
];
const RULES = [{ id: 'aaaaaaaaaaa1', rule: '(allow unconfined_service_t chronyc_t (process2 (nnp_transition)))', why: 'otp-tick: nothing of the policy allows it', at: now - 600, by: 'admin', program: 'otp-tick' }];
const base = { config: 'permissive', policy: 'targeted', relabel_pending: false, cmdline_off: false, tools: {}, module: true, labels: [], booleans: [], ports: [], auditd: true };
const perm = Object.assign({}, base, { mode: 'Permissive', ready: false, findings: FIND, local_rules: RULES, local_module: true,
  counts: { fixed: 1, boolean: 1, label: 1, port: 1, rule: 1, nobutton: 1, other: 1 },
  denials: { tool: true, total: 6, settled: 0, since: 0, groups: [] }, problems: ['SELinux refused 6 thing(s) since the machine started'] });
const enf = Object.assign({}, base, { mode: 'Enforcing', config: 'enforcing', ready: false, findings: [], local_rules: [], counts: {},
  denials: { tool: true, total: 0, groups: [] }, problems: [] });
const VIEW = { nodes: [{ name: 'vm', me: true, state: perm, at: now, error: '', said: [], action: 'check', pending: '' },
                       { name: 'otp2', me: false, state: enf, at: now, error: '', said: [], action: 'check', pending: '' }], reports: {} };
(async () => {
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  for (const [lang, width] of [['en', 1500], ['cs', 1280], ['cs', 390]]) {
    const tag = lang + '@' + width + ': ';
    const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1000 } });
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    const posts = [];
    await p.route(/\?api=selinux(&|$)/, async (r) => {
      if (r.request().method() === 'POST') { posts.push(JSON.parse(r.request().postData() || '{}')); return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'asked' }) }); }
      r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(VIEW) });
    });
    await p.goto('https://127.0.0.1/admin/');
    await p.fill('input[autocomplete=username]', 'admin');
    await p.fill('input[type=password]', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
    await p.keyboard.press('Enter');
    await p.waitForTimeout(2500);
    await p.evaluate(async (l) => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: l})}); }, lang);
    await p.goto('https://127.0.0.1/admin/#settings/selinux'); await p.reload(); await p.waitForTimeout(3500);
    const vm = p.locator('.se-node').first(), o2 = p.locator('.se-node').nth(1);
    const kinds = await vm.locator('.se-kind').evaluateAll(xs => xs.map(x => x.className.replace(/.*se-k-/, '')));
    ok(tag + 'each kind in its group, in order', JSON.stringify(kinds) === JSON.stringify(['fixed', 'boolean', 'label', 'port', 'rule', 'nobutton', 'other']), kinds);
    ok(tag + 'a checkbox for each one that may be put right, ticked', await vm.locator('.se-f input[type=checkbox]:checked').count() === 4);
    ok(tag + 'none for "put right", "not for a button", "not otp\'s"', await vm.locator('.se-k-nobutton input, .se-k-other input, .se-k-fixed input').count() === 0);
    const btn = vm.locator('.se-fixbar button');
    ok(tag + 'the button counts them (4)', /\(4\)/.test(await btn.innerText()), await btn.innerText());
    await vm.locator('.se-k-label .se-f input[type=checkbox]').uncheck();
    ok(tag + '...one unticked: (3)', /\(3\)/.test(await btn.innerText()), await btn.innerText());
    await vm.locator('.se-k-label .se-kind-h input[type=checkbox]').check();
    ok(tag + '...select all of a group: (4) again', /\(4\)/.test(await btn.innerText()));
    const txt = await vm.innerText();
    ok(tag + 'what root would do, shown', txt.includes('restorecon -R -v /var/www/otp/assets') && txt.includes('semanage port -a -t ssh_port_t -p tcp 2222') && txt.includes('setsebool -P httpd_can_network_connect 1'));
    ok(tag + 'why not, said', txt.includes('shadow_t is security-sensitive'));
    await btn.click(); await p.waitForTimeout(600);
    const modal = await p.locator('#modal').innerText();
    ok(tag + 'the confirm lists exactly what root will do', modal.includes('restorecon -R -v /var/www/otp/assets') && modal.includes('(allow unconfined_service_t hostname_t (process2 (nnp_transition)))')
       && !modal.includes('shadow'), modal.slice(0, 400));
    await p.locator('#modal-foot button').last().click(); await p.waitForTimeout(800);
    const fix = posts.find(x => x.action === 'fix') || {};
    ok(tag + 'only the ids are sent', fix.node === 'vm' && JSON.stringify((fix.ids || []).slice().sort()) === JSON.stringify(['aaaaaaaaaaa2', 'aaaaaaaaaaa3', 'aaaaaaaaaaa4', 'aaaaaaaaaaa5'])
       && Object.keys(fix).sort().join() === 'action,ids,node', fix);
    await p.waitForTimeout(1200);
    const vm2 = p.locator('.se-node').first();
    ok(tag + 'otp\'s local rules listed, each with Take it away', await vm2.locator('.se-rule button').count() === 1 && (await vm2.locator('.se-rules').innerText()).includes('chronyc_t'));
    await vm2.locator('.se-rule button').click(); await p.waitForTimeout(500);
    ok(tag + '...asked first, the last one said', /otp_local|otp/i.test(await p.locator('#modal').innerText()));
    await p.locator('#modal-foot button').last().click(); await p.waitForTimeout(300);
    await p.locator('#modal-foot .sure-strip button.danger').click(); await p.waitForTimeout(600);
    const drop = posts.find(x => x.action === 'rule_drop') || {};
    ok(tag + '...only its id sent', drop.rule === 'aaaaaaaaaaa1' && drop.node === 'vm', drop);
    await p.waitForTimeout(1200);
    const enfBtn = vm2.locator('.se-btns button', { hasText: /enforcing/i });
    ok(tag + 'enforcing locked while anything is left', await enfBtn.count() === 1 && await enfBtn.isDisabled());
    ok(tag + '...the verdict says how many of each', /4 /.test(await vm2.locator('.se-verdict').innerText()) && /1 /.test(await vm2.locator('.se-verdict').innerText()));
    ok(tag + 'the enforcing node with nothing refused: only "Back to permissive", as before; "refused nothing" said', await o2.locator('button').count() === 1 && await o2.locator('.se-none').count() === 1);
    if (lang === 'cs') ok(tag + 'in Czech', /Co SELinux odpírá/.test(await vm2.innerText()) && /Nasadit vybrané/.test(await vm2.innerText()) && /Lokální pravidla otp/.test(await vm2.innerText()), (await vm2.innerText()).slice(0, 300));
    const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(tag + 'no horizontal scroll', over <= 0, over);
    const out = await vm2.evaluate(n => { const r = n.getBoundingClientRect(); return Math.max(0, ...Array.from(n.querySelectorAll('.se-find *')).map(x => x.getBoundingClientRect().right - r.right)); });
    ok(tag + 'the findings stay inside the node\'s box', out <= 1, out);
    ok(tag + 'no page errors', errs.length === 0, errs);
    /* the language put back: the tests after this one read the pages in English */
    await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
    await ctx.close();
  }
  await b.close();
  console.log('ALL ' + R.filter(x => x).length + ' / ' + R.length);
  process.exit(R.every(x => x) ? 0 : 1);
})().catch(e => { console.log('FAIL broke: ' + e); process.exit(1); });
