// Settings -> System updates and SSH keys of root as two nodes show them, the
// API played here (1.0.159): the log switched between nodes, hidden, shown,
// cleared; Look for updates followed until it is done; the gaps between parts.
// Serve: php -S localhost:28080 -t out/otp-VER/web, the daemon running.
const { chromium } = require('playwright');
const SHOT = process.argv[2] || '/tmp/claude-0/ui159';
const now = () => Date.now() / 1000;
let checks = {otp1: 0, otp2: 0}, asked = {};
function check(n) {
  const t = asked[n];
  if (t && Date.now() - t < 5000) return {state: 'running', began: t / 1000, lines: ['$ dnf -q --refresh check-update', 'looking on ' + n]};
  const c = n === 'otp1' ? 32 + checks[n] : 30 + checks[n];
  return {state: 'done', checked: now() - 60, began: now() - 70, count: c, security: 21, pm: 'dnf',
          reboot_after: n === 'otp1', reboot_why: n === 'otp1' ? ['glibc', 'kernel-core'] : [], reboot_now: false,
          packages: ['bind-libs.x86_64 32:9.16 appstream', 'kernel.x86_64 5.14.0 baseos'],
          lines: ['$ dnf -q --refresh check-update'].concat(Array.from({length: 30}, (_, i) => n + ' pkg-' + i + '.x86_64  1.' + i + '  baseos'))};
}
function osup() {
  return {cluster: true, helper: true, power: {}, plan: {},
          nodes: ['otp1', 'otp2'].map(n => ({name: n, me: n === 'otp1', alive: true, reboot: false, row: {}, check: check(n)}))};
}
let kept = {all: {}, otp1: {}, otp2: {}};
function sshkeys() {
  const k = [{fp: 'SHA256:uxmQUTLnHolkc0Uo', bits: 2048, type: 'RSA', comment: 'root@Chris', text: 'ssh-rsa AAAA root@Chris'},
             {fp: 'SHA256:Nps+ejc3fdqiqplJ', bits: 8192, type: 'RSA', comment: 'ansible@falco81.net', text: 'ssh-rsa BBBB ansible'}];
  const keysOf = n => k.concat(Object.keys(kept).filter(s => kept[s].fp && (s === 'all' || s === n)).map(s => ({fp: kept[s].fp, bits: 256, type: 'ED25519', comment: 'otp-root-' + s, text: kept[s].pub})));
  return {keygen: true, cluster: true,
          nodes: ['otp1', 'otp2'].map(n => ({name: n, me: n === 'otp1', alive: true, keys: keysOf(n), file: '/root/.ssh/authorized_keys', at: now() - 1, pending: 0,
                                            sshd: {there: true, permit_root: 'yes', password: 'yes', port: '22'}})),
          kept: ['all', 'otp1', 'otp2'].map(s => ({scope: s, has: !!kept[s].fp, pub: kept[s].pub || '', fp: kept[s].fp || '', how: 'made', by: 'admin', at: now() - 5,
                                                   on: Object.fromEntries((s === 'all' ? ['otp1', 'otp2'] : [s]).map(n => [n, !!kept[s].fp]))}))};
}
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1600, height: 1100}});
  const errs = []; p.on('pageerror', e => errs.push(String(e)));
  const R = []; const ok = (w, c) => { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w); };
  await p.goto('http://localhost:28080/admin/index.php'); await p.waitForTimeout(800);
  await p.fill('input:not([type=password])', 'admin').catch(() => {});
  await p.fill('input[type=password]', 'Test-Admin-Pass-149!'); await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  await p.route(/\?api=(osup|sshkeys)$/, async route => {
    const r = route.request(), what = r.url().split('api=')[1];
    if (r.method() === 'POST') {
      const q = JSON.parse(r.postData() || '{}');
      if (what === 'osup' && q.action === 'check') { (q.nodes || ['otp1', 'otp2']).forEach(n => { asked[n] = Date.now(); checks[n] += 1; }); }
      if (what === 'sshkeys' && q.action === 'rk_make') {
        kept[q.scope] = {fp: 'SHA256:new' + q.scope, pub: 'ssh-ed25519 AAAAC3Nza' + q.scope + ' otp-root-' + q.scope};
        return route.fulfill({json: {message: 'made', private: '-----BEGIN OPENSSH PRIVATE KEY-----\nxx\n-----END OPENSSH PRIVATE KEY-----\n',
                                     pub: kept[q.scope].pub, fp: kept[q.scope].fp, nodes: q.scope === 'all' ? ['otp1', 'otp2'] : [q.scope], file: 'otp-root-' + q.scope}});
      }
      return route.fulfill({json: {message: 'asked'}});
    }
    return route.fulfill({json: what === 'osup' ? osup() : sshkeys()});
  });
  // ---- updates
  await p.goto('http://localhost:28080/admin/index.php#settings/osup'); await p.waitForTimeout(2000);
  await p.screenshot({path: SHOT + '/ha-ou1.png', fullPage: true});
  const log = () => p.locator('#ou-host pre.ou-log').innerText().catch(() => '');
  ok('a restart told before the update', (await p.locator('#ou-host').innerText()).match(/restart after this update: glibc, kernel-core|potřebovat restart: glibc, kernel-core/));
  ok('... on the node it is for', (await p.locator('#ou-host .pw-node').first().innerText()).match(/glibc, kernel-core/));
  ok('the log is of otp1 first', (await log()).includes('otp1 pkg-'));
  await p.locator('#ou-host .seg button', {hasText: 'otp2'}).click(); await p.waitForTimeout(400);
  ok('switched to otp2', (await log()).includes('otp2 pkg-'));
  await p.locator('#ou-host .seg button', {hasText: 'otp1'}).click(); await p.waitForTimeout(400);
  ok('and back to otp1', (await log()).includes('otp1 pkg-'));
  await p.locator('#ou-host button', {hasText: /Hide it|Skrýt/}).click(); await p.waitForTimeout(400);
  ok('hidden', !(await p.locator('#ou-host pre.ou-log').count()));
  await p.locator('#ou-host button', {hasText: /Show it|Zobrazit/}).click(); await p.waitForTimeout(400);
  ok('shown again', (await log()).includes('otp1 pkg-'));
  await p.locator('#ou-host button', {hasText: /Clear the window|Vyčistit/}).click(); await p.waitForTimeout(400);
  ok('cleared', (await log()).trim() === '–');
  const card2 = p.locator('#ou-host .pw-node').nth(1);
  await card2.locator('button', {hasText: /Look for updates|Zjistit aktualizace/}).click();
  ok('looking shown on otp2', await card2.locator('text=/looking|zjišťuje/').waitFor({timeout: 6000}).then(() => true, () => false));
  ok('... and done again: 31 waiting', await card2.locator('text=/31/').first().waitFor({timeout: 12000}).then(() => true, () => false));
  ok('... its log is shown', (await log()).includes('otp2 pkg-'));
  await p.screenshot({path: SHOT + '/ha-ou2.png', fullPage: true});
  // the gaps: no two parts of a card touching
  const gaps = await p.$$eval('#ou-host .card > *, #sk-host .card > *, #sk-host .rb-panel > *', els => {
    const out = [];
    els.forEach(e => { const n = e.nextElementSibling; if (!n || !e.offsetHeight || !n.offsetHeight) return;
      const g = n.getBoundingClientRect().top - e.getBoundingClientRect().bottom;
      if (g < 6) out.push([e.tagName + '.' + e.className, n.tagName + '.' + n.className, Math.round(g)]); });
    return out; });
  ok('no parts touching in updates: ' + JSON.stringify(gaps), !gaps.length);
  const seg = await p.$eval('#ou-host .card .set-item .seg', e => [e.offsetWidth, e.closest('.card').offsetWidth]);
  ok('the choice as wide as its words: ' + seg, seg[0] < seg[1] * 0.8);
  // ---- keys
  await p.goto('http://localhost:28080/admin/index.php#settings/sshkeys'); await p.waitForTimeout(2000);
  ok('every node, otp1, otp2 to choose', await p.locator('#sk-host .seg button').count() === 3);
  await p.locator('#sk-host button', {hasText: /^\s*(Make a key|Vytvořit klíč)\s*$/}).click(); await p.waitForTimeout(500);
  await p.locator('#modal-foot button').last().click(); await p.waitForTimeout(1200);
  ok('the private half shown once', (await p.locator('#modal textarea, .modal-box textarea').first().inputValue().catch(() => '')).includes('PRIVATE KEY'));
  await p.screenshot({path: SHOT + '/ha-sk0.png'});
  await p.locator('#modal-foot button').last().click(); await p.waitForTimeout(1200);
  ok('no Download nor Forget in the key panel', !(await p.locator('#sk-host .rb-panel button', {hasText: /Download it|Forget it|Stáhnout|Zapomenout/}).count()));
  ok('made for every node: the public half shown', (await p.locator('#sk-host .rb-below').innerText()).includes('ssh-ed25519 AAAAC3Nzaall'));
  await p.locator('#sk-host .seg button').nth(2).click(); await p.waitForTimeout(500);
  ok('otp2 alone has none yet', (await p.locator('#sk-host .rb-below').innerText()).match(/None made|Zatím|Žádný/));
  await p.screenshot({path: SHOT + '/ha-sk1.png', fullPage: true});
  const g2 = await p.$$eval('#sk-host .card > *, #sk-host .rb-panel > *', els => {
    const out = []; els.forEach(e => { const n = e.nextElementSibling; if (!n || !e.offsetHeight || !n.offsetHeight) return;
      const g = n.getBoundingClientRect().top - e.getBoundingClientRect().bottom; if (g < 6) out.push([e.className, n.className, Math.round(g)]); }); return out; });
  ok('no parts touching in keys: ' + JSON.stringify(g2), !g2.length);
  console.log('errors', errs); console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
  await b.close();
})();
