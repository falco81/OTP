// The pages of 1.0.170 under php -S (127.0.0.1:8099) with the daemon installed:
// Encryption to the database server (its view put in, a node of a cluster
// each), every node's own settings under the box, ACME's cards beside
// Certificates and TLS. node shot_dbtls.js OUTDIR
const { chromium } = require('playwright');
const fs = require('fs');
const OUT = process.argv[2];
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const NOW = Date.now() / 1000;
const VIEW = {kind: 'local', engine: 'postgres', mode: 'verify-full', ha_mode: 'shared', host: '127.0.0.1',
  link_done: false, own_ca: true, servers: ['otp1'], hisec: false,
  nodes: [{name: 'otp1', me: true, alive: true, kind: 'local', mode: 'verify-full', ssl: true, version: 'TLSv1.3',
           cipher: 'TLS_AES_256_GCM_SHA384', ca_said: "otp's own authority", cert_end: NOW + 700 * 86400, server: true},
          {name: 'otp2', me: false, alive: true, kind: 'remote', mode: 'require', ssl: true, version: 'TLSv1.3',
           cipher: 'TLS_AES_256_GCM_SHA384'}]};
const PROBE = {otp1: {ok: true, kind: 'local', server_tls: true, ssl: true, version: 'TLSv1.3', cipher: 'TLS_AES_256_GCM_SHA384', ms: 14},
  otp2: {ok: false, kind: 'remote', server_tls: true, said: 'certificate verify failed: unable to get local issuer certificate'}};
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport: {width: 1600, height: 1000}});
  await ctx.addInitScript(() => {
    window.__miss = {};
    document.addEventListener('DOMContentLoaded', () => {
      const orig = window.i18nText;
      if (orig) window.i18nText = function (s, depth) { const r = orig(s, depth); if (r === s && /[a-z] [a-z]/i.test(String(s))) window.__miss[s] = 1; return r; };
    });
  });
  const pg = await ctx.newPage();
  const MISS = new Set();
  const grab = async () => { try { (await pg.evaluate('Object.keys(window.__miss||{})')).forEach(x => MISS.add(x)); } catch (e) {} };
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  await pg.route('**/admin/?api=*', async route => {
    const req = route.request(); const url = req.url();
    if (url.includes('api=dbtls')) {
      const body = req.method() === 'POST' ? JSON.parse(req.postData() || 'null') : null;
      if (body && body.action === 'probe') return route.fulfill({json: {id: 'x1', nodes: ['otp1', 'otp2']}});
      if (body && body.action === 'result') return route.fulfill({json: {nodes: PROBE, view: VIEW}});
      return route.fulfill({json: VIEW});
    }
    if (url.endsWith('api=web') && req.method() === 'GET') {
      const r = await route.fetch(); const d = await r.json();
      d.acme = {on: true, care: {}, state: {}}; Object.keys(d.tls || {}).forEach((t, i) => { d.acme.care[t] = i === 0; d.acme.state[t] = i === 0 ? {ok: false, said: 'x'} : {}; });
      return route.fulfill({json: d});
    }
    if (url.endsWith('api=acme') && req.method() === 'POST' && JSON.parse(req.postData() || '{}').action === 'dns_check') {
      return route.fulfill({json: {rows: [
        {target: 'otp1', record: '_acme-challenge.otp1.example.cz', ok: true, said: 'there'},
        {target: 'otp2', record: '_acme-challenge.otp2.example.cz', ok: false, said: 'not there yet'},
        {target: 'vip', record: '_acme-challenge.otp.example.cz', ok: false, said: 'it points elsewhere: _acme-challenge.otp.old.example.'}]}});
    }
    if (url.endsWith('api=acme') && req.method() === 'GET') {
      const t = (target, name, how, care, extra) => Object.assign({target, name, how, care, wanted: true, named: false,
        state: {}, issuer: 'CN=ca.example.cz,O=Example', not_after: NOW + 3600 * 86400}, extra || {});
      return route.fulfill({json: {on: true, node: 'otp1', mine: ['otp1'], directory: 'https://acme-v02.api.letsencrypt.org/directory',
        account: {}, work: {}, challenge: 'dns-01', manual: null,
        dns_guide: {challenge: 'dns-01', dns: 'desec', rows: [
          {target: 'otp1', name: 'otp1.example.cz', type: 'CNAME', record: '_acme-challenge.otp1.example.cz', value: '_acme-challenge.otp1.mine.dedyn.io.', why: 'once, by hand, in your DNS', check: 'cname'},
          {target: 'otp2', name: 'otp2.example.cz', type: 'CNAME', record: '_acme-challenge.otp2.example.cz', value: '_acme-challenge.otp2.mine.dedyn.io.', why: 'once, by hand, in your DNS', check: 'cname'},
          {target: 'vip', name: 'otp.example.cz', type: 'CNAME', record: '_acme-challenge.otp.example.cz', value: '_acme-challenge.otp.mine.dedyn.io.', why: 'once, by hand, in your DNS', check: 'cname'}]},
        targets: [t('otp1', 'otp1.example.cz', 'ACME', true, {issuer: 'CN=R11,O=Let\'s Encrypt', not_after: NOW + 61 * 86400, state: {ok: true, ordered_at: NOW - 29 * 86400}}),
                  t('otp2', 'otp2.example.cz', 'uploaded', false), t('vip', 'otp.example.cz', 'uploaded', false)]}});
    }
    if (url.endsWith('api=settings') && req.method() === 'GET') {
      const r = await route.fetch(); const d = await r.json();
      d.cluster = true; d.nodes = [d.node, 'otp2'];
      d.settings.forEach(s => { if (s.node_key) { s.per_node = s.key === 'acme_node_name' ? {otp2: 'otp2.example.cz'} : {}; s.shared = s.value; } });
      return route.fulfill({json: d});
    }
    return route.continue();
  });
  await pg.goto('http://127.0.0.1:8099/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'uiadmin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter');
  await pg.waitForTimeout(2500);
  await pg.screenshot({path: OUT + '/after-login.png'});
  await pg.goto('http://127.0.0.1:8099/admin/#settings/db'); await pg.waitForTimeout(3000);
  const c = await pg.$('#db-tls-card');
  await c.scrollIntoViewIfNeeded(); await c.screenshot({path: OUT + '/dbtls-card.png'});
  await pg.click('#dbt-on'); await pg.waitForTimeout(800);
  await pg.click('#modal-foot button:nth-child(2)'); await pg.waitForTimeout(2500);
  await pg.screenshot({path: OUT + '/dbtls-wizard.png'});
  await grab();
  await pg.keyboard.press('Escape'); await pg.waitForTimeout(400);
  await pg.click('#dbt-off'); await pg.waitForTimeout(600); await grab();
  await pg.keyboard.press('Escape'); await pg.waitForTimeout(400);
  await pg.goto('http://127.0.0.1:8099/admin/#settings/acme'); await pg.waitForTimeout(3000);
  await pg.screenshot({path: OUT + '/acme.png'});
  const g = await pg.$('#pane-acme .node-grid'); if (g) await g.screenshot({path: OUT + '/acme-cards.png'});
  await pg.click('.acme-dns button:has-text("DNS")'); await pg.waitForTimeout(1200);
  const gd = await pg.$('.acme-dns'); if (gd) { await gd.scrollIntoViewIfNeeded(); await gd.screenshot({path: OUT + '/acme-dns.png'}); }
  await grab();
  for (const sel of ['#pane-acme .node-grid .card:nth-child(2) button:has-text("Its name")', '#pane-acme .node-grid .card:nth-child(3) button:has-text("Its name")', '#pane-acme .node-grid .card:nth-child(2) button.primary']) {
    try { await pg.click(sel); await pg.waitForTimeout(600); await grab(); await pg.keyboard.press('Escape'); await pg.waitForTimeout(400); } catch (e) { console.log('no', sel); }
  }
  const it = await pg.$('.set-item[data-key="acme_node_name"]');
  if (it) { await it.scrollIntoViewIfNeeded(); await it.screenshot({path: OUT + '/acme-node-name.png'}); }
  await pg.goto('http://127.0.0.1:8099/admin/#settings/web'); await pg.waitForTimeout(3000);
  await pg.screenshot({path: OUT + '/web.png'});
  await grab();
  try { await pg.click('.cert-tools button:has-text("Upload"), .cert-tools button:has-text("Nahrát")'); await pg.waitForTimeout(600); await grab(); } catch (e) { console.log('no upload'); }
  await pg.screenshot({path: OUT + '/web-confirm.png'});
  console.log('MISS ' + JSON.stringify([...MISS].sort(), null, 1));
  console.log('errors', JSON.stringify(errs));
  await b.close();
})();
