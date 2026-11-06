// ui_lb.js - 1.0.259: Settings → High availability → The load balancer - the Layer switch (L7, L4
// with the PROXY protocol, L4 without an address) changing every kind's text, Apache saying it is
// L7 only, the new source field followed by the text and the settings line, no secret field and
// "<the shared secret>" in the RADIUS texts, the trust notes per layer (the administration's list,
// /healthz, the firewall, the way to Firewall and access), Check it with the 404 checks; the setting
// web_proxy_port: proxy_protocol refused without it, then on - the node's own port 8443 answers the
// enrolment page and 404 for /admin/, /metrics, /healthz over the PROXY protocol, and refuses a
// connection without it - and everything put back. Czech. Written for the live single-node install
// (run as root on the server).
//
//     node ui_lb.js              (Playwright; https://127.0.0.1/admin/, admin's password in
//                                 /home/claude/run/adminpw)
const { chromium } = require('playwright');
const fs = require('fs');
const net = require('net');
const tls = require('tls');
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
const BASE = 'https://127.0.0.1/admin/';
const SHOTS = '/tmp/claude-0/uilb';
fs.mkdirSync(SHOTS, { recursive: true });
async function post(p, what, body) {
  return p.evaluate(async ([w, b]) => {
    const r = await fetch('?api=' + w, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
    let d = {}; try { d = await r.json(); } catch (e) {}
    return {st: r.status, d};
  }, [what, body]);
}
async function get(p, what) {
  return p.evaluate(async (w) => { const r = await fetch('?api=' + w); let d = {}; try { d = await r.json(); } catch (e) {} return {st: r.status, d}; }, what);
}
async function signIn(p, name, pw) {
  await p.goto(BASE);
  await p.fill('input[autocomplete=username]', name);
  await p.fill('input[type=password]', pw);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(2500);
}
/* GET a path on the node's own port, the PROXY protocol v1 first (as a balancer at 127.0.0.1 would). */
function viaProxy(port, path, proxy) {
  return new Promise((res) => {
    const raw = net.connect(port, '127.0.0.1', () => {
      if (proxy) raw.write('PROXY TCP4 198.51.100.7 127.0.0.1 40000 ' + port + '\r\n');
      const s = tls.connect({socket: raw, rejectUnauthorized: false, servername: 'otp.test', ALPNProtocols: ['http/1.1']}, () => {
        s.write('GET ' + path + ' HTTP/1.1\r\nHost: otp.test\r\nConnection: close\r\n\r\n');
      });
      let buf = '';
      s.on('data', d => { buf += d; });
      s.on('end', () => res(parseInt((buf.match(/^HTTP\/1\.[01] (\d+)/) || [0, 0])[1], 10)));
      s.on('error', () => res(-1));
    });
    raw.on('error', () => res(-2));
    setTimeout(() => res(-3), 8000);
  });
}
async function lbText(p, kind) {
  return p.evaluate((k) => {
    const d = document.querySelector('#ha-lb details.lb-guide[data-k="' + k + '"]');
    if (!d) return '';
    d.open = true;
    return d.textContent;
  }, kind);
}
async function layer(p, k) {
  await p.click('#ha-lb .lb-layer button[data-v="' + k + '"]');
  await p.waitForTimeout(200);
}
(async () => {
  const b = await chromium.launch({ args: ['--ignore-certificate-errors'] });
  const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  await ctx.addCookies([{name: 'otp_lang', value: 'en', domain: '127.0.0.1', path: '/'}]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  await signIn(p, 'admin', fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim());
  const before = ((await get(p, 'ha')).d.lb || {}).web_proxy || {};
  ok('lb_facts: web_proxy, the lists, portal_sso, fw_managed', before.port !== undefined && ((await get(p, 'ha')).d.lb || {}).access !== undefined, JSON.stringify(before));
  await p.evaluate(() => { localStorage.removeItem('otp.lb'); });
  await p.goto(BASE + '#settings/ha');
  await p.waitForTimeout(1500);
  await p.evaluate(() => showPane('ha'));
  await p.waitForSelector('#ha-lb .lb-layer', { timeout: 15000 }).catch(() => {});
  ok('the Layer switch: three choices', (await p.$$('#ha-lb .lb-layer button')).length === 3);
  ok('no secret field, no password box', !(await p.$('#ha-lb input[type=password]')) && !/RADIUS shared secret/.test(await p.$eval('#ha-lb', e => e.textContent)));
  await layer(p, 'l7');
  let h = await lbText(p, 'haproxy');
  ok('L7 HAProxy: the exact list, set-header X-Forwarded-For %[src], to 8443', /path_reg '\^\/\(\(index/.test(h) && h.includes('http-request set-header X-Forwarded-For %[src]') && h.includes(':8443') && !h.includes('option forwardfor'), h.slice(0, 300));
  const n7 = await lbText(p, 'nginx');
  ok('L7 nginx: X-Forwarded-For $remote_addr, 8m, location / 404', n7.includes('proxy_set_header X-Forwarded-For $remote_addr;') && n7.includes('client_max_body_size 8m') && n7.includes('location / { return 404; }'));
  const asa = await lbText(p, 'asa');
  ok('ASA: <the shared secret>, depletion deadtime', asa.includes('key <the shared secret>') && asa.includes('reactivation-mode depletion deadtime 1'));
  let trust = await p.$eval('#ha-lb .lb-trust', e => e.textContent);
  ok('L7: the trust note (the header, the balancer\'s port) and the way to Firewall and access', /X-Forwarded-For/.test(trust) && /8443/.test(trust) && !!(await p.$('#ha-lb .lb-trust button:has-text("Firewall and access")')), trust.slice(0, 300));
  await layer(p, 'l4');
  h = await lbText(p, 'haproxy');
  ok('L4 HAProxy: mode tcp, send-proxy-v2 to 8443, check port 443', h.includes('mode tcp') && h.includes('send-proxy-v2') && h.includes('check port 443 check-ssl'));
  ok('L4 Apache: says L7 only', /balances HTTP only/.test(await lbText(p, 'apache')));
  ok('L4 NetScaler: the net profile with PROXY v2', (await lbText(p, 'netscaler')).includes('-proxyProtocol ENABLED -proxyProtocolVersion V2'));
  trust = await p.$eval('#ha-lb .lb-trust', e => e.textContent);
  ok('L4: says the balancer cannot see the paths, the admin list is what protects', /cannot see the paths/.test(trust) && /administration pages/.test(trust) && /proxy_protocol/.test(trust), trust.slice(0, 300));
  await layer(p, 'snat');
  h = await lbText(p, 'haproxy');
  ok('L4 without an address: no PROXY, to 443', !h.includes('send-proxy') && /:443\b/.test(h));
  ok('...the warning of the shared pause', /every client is/.test(await p.$eval('#ha-lb .lb-trust', e => e.textContent)));
  await layer(p, 'l7');
  await p.fill('#ha-lb .lb-form label:has-text("comes to the nodes from") input', '203.0.113.9');
  await p.waitForTimeout(300);
  trust = await p.$eval('#ha-lb .lb-trust', e => e.textContent);
  ok('the source field: the settings line follows it', trust.includes("web_proxy_from='203.0.113.9/32'"), trust.slice(0, 400));
  const ck = await lbText(p, 'check');
  ok('Check it: /admin/, //admin/, /metrics, /healthz must be 404', ['/admin/        # 404', '//admin/       # 404', '/metrics       # 404', '/healthz       # 404'].every(w => ck.includes(w)));
  await p.screenshot({ path: SHOTS + '/lb.png', fullPage: true });
  // ---- the setting, for real: the node's own port
  const save = (s) => post(p, 'settings', {settings: s});
  const r1 = await save({web_proxy: 1, web_proxy_from: '127.0.0.1/32', web_proxy_header: 'proxy_protocol', web_proxy_port: 0});
  ok('proxy_protocol without the balancer\'s own port: refused, said why', r1.st === 400 && /own port/.test(r1.d.error || ''), JSON.stringify(r1));
  const r2 = await save({web_proxy: 1, web_proxy_from: '127.0.0.1/32', web_proxy_header: 'proxy_protocol', web_proxy_port: 8443});
  ok('...with port 8443: taken', r2.st === 200, JSON.stringify(r2));
  /* this sandbox has no systemd: otp-web.path and systemctl reload nginx played by hand (on a real
     server the path unit runs the root helper, and it reloads nginx itself) */
  const rootDo = () => { try { require('child_process').execFileSync('python3', ['-I', '/usr/local/lib/otp/otp_web.py'], {stdio: 'ignore', timeout: 60000});
                               require('child_process').execFileSync('nginx', ['-s', 'reload'], {stdio: 'ignore'}); } catch (e) {} };
  let up = 0;
  for (let i = 0; i < 30 && up !== 200 && up !== 403; i++) { await p.waitForTimeout(2000); rootDo(); await p.waitForTimeout(800); up = await viaProxy(8443, '/', true); }
  ok('8443 over the PROXY protocol: the enrolment page answers (200, or 403 by its allow list)', up === 200 || up === 403, up);
  ok('8443: /admin/ 404', (await viaProxy(8443, '/admin/', true)) === 404);
  ok('8443: //admin/ 404', (await viaProxy(8443, '//admin/', true)) === 404);
  ok('8443: /metrics 404', (await viaProxy(8443, '/metrics', true)) === 404);
  ok('8443: /healthz 404', (await viaProxy(8443, '/healthz', true)) === 404);
  ok('8443: /assets/portal.js 200, /assets/admin.js 404', (await viaProxy(8443, '/assets/portal.js', true)) === 200 && (await viaProxy(8443, '/assets/admin.js', true)) === 404);
  ok('8443 without the PROXY protocol: refused', (await viaProxy(8443, '/', false)) < 0);
  ok('443 as before: the administration answers', (await get(p, 'whoami')).st === 200);
  const f = ((await get(p, 'ha')).d.lb || {}).web_proxy || {};
  ok('lb_facts says it', f.on && f.header === 'proxy_protocol' && f.port === 8443, JSON.stringify(f));
  // put back as it was
  const r3 = await save({web_proxy_port: 0, web_proxy_header: before.header === 'proxy_protocol' ? 'X-Forwarded-For' : (before.header || 'X-Forwarded-For'),
                         web_proxy_from: (before.from || []).join(' '), web_proxy: before.on ? 1 : 0});
  ok('put back', r3.st === 200, JSON.stringify(r3));
  let gone = 0;
  for (let i = 0; i < 30 && gone >= 0; i++) { await p.waitForTimeout(2000); rootDo(); await p.waitForTimeout(800); gone = await viaProxy(8443, '/', true); }
  ok('8443 taken away again', gone < 0, gone);
  // Czech
  const cctx = await b.newContext({ ignoreHTTPSErrors: true });
  await cctx.addCookies((await ctx.cookies()).filter(c => c.name !== 'otp_lang').concat([{name: 'otp_lang', value: 'cs', domain: '127.0.0.1', path: '/'}]));
  const cp = await cctx.newPage();
  await cp.goto(BASE);
  await cp.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'cs'})}); });
  await cp.goto(BASE);
  await cp.waitForTimeout(2000);
  await cp.evaluate(() => showPane('ha'));
  await cp.waitForTimeout(2500);
  const cz = await cp.$eval('#ha-lb', e => e.textContent).catch(() => '');
  ok('Czech: the layers and the notes', /TLS končí na balanceru/.test(cz) && /Vrstva/.test(cz), cz.slice(0, 300));
  await cp.screenshot({ path: SHOTS + '/cs.png', fullPage: true });
  await cp.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  await cctx.close();
  ok('no errors on the pages', !errs.length, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  process.exit(R.every(Boolean) ? 0 : 1);
})();
