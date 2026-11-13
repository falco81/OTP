// ui_r273.js - 1.0.273 on the installed pages: Your account asks for the new password twice
// (different: refused on the page, nothing sent; the same: changed, then put back), and the
// SSH server saved with "Who may sign in" leaving root out (then put back as it was).
const { chromium } = require('playwright');
const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
let R = [];
function ok(w, c, more) { R.push(!!c); console.log((c ? 'ok   ' : 'FAIL ') + w + (c || !more ? '' : ' (' + String(more).slice(0, 300) + ')')); }
async function login(p, pw) {
  await p.goto('https://127.0.0.1/admin/');
  await p.fill('input[autocomplete=username]', 'admin');
  await p.fill('input[type=password]', pw);
  await p.keyboard.press('Enter');
  await p.waitForTimeout(3000);
}
async function typeIn(p, sel, text) { await p.click(sel); await p.keyboard.type(text); }
async function change(p, from, to, again) {
  await p.click('#me-btn'); await p.waitForSelector('#me-pw-go');
  await typeIn(p, '#me-pw-old', from);
  await typeIn(p, '#me-pw-new', to);
  await typeIn(p, '#me-pw-new2', again);
  await p.click('#me-pw-go');
  await p.waitForTimeout(1500);
  return p.$$eval('.toast', a => a.map(x => x.textContent).join(' | '));
}
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1900, height: 1000 } })).newPage();
  const errs = [], sent = [];
  p.on('pageerror', e => errs.push(String(e)));
  p.on('request', r => { if (/api=password/.test(r.url())) sent.push(r.url()); });
  await login(p, PW);
  await p.evaluate(async () => { await fetch('?api=prefs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lang: 'en'})}); });
  await p.reload(); await p.waitForTimeout(2500);
  await p.click('#me-btn'); await p.waitForSelector('#me-pw-go');
  const labels = await p.$$eval('.me-sec .formgrid label, .me-sec .formgrid .flabel, .me-sec .formgrid', a => a.map(x => x.textContent).join(' '));
  ok('three boxes: now, new, again', await p.$$eval('#me-pw-old, #me-pw-new, #me-pw-new2', a => a.length) === 3 && /The new one again/.test(labels), labels.slice(0, 200));
  await p.click('.modal .close, #modal-close').catch(() => {});
  await p.keyboard.press('Escape'); await p.waitForTimeout(500);

  const NEW = PW + '-273';
  let t = await change(p, PW, NEW, NEW + 'x');
  ok('the two new ones differ: refused on the page', /not the same/.test(t), t);
  ok('the two new ones differ: nothing sent', sent.length === 0, sent.join());
  await p.keyboard.press('Escape'); await p.waitForTimeout(800);
  await p.reload(); await p.waitForTimeout(2500);
  t = await change(p, PW, NEW, NEW);
  ok('the same twice: changed', /password is changed/.test(t), t);
  await p.waitForTimeout(800);
  const st = await p.evaluate(async (a) => (await fetch('?api=password', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({old: a[0], 'new': a[1]})})).status, [NEW, PW]);
  ok('put back as it was', st === 200, st);

  // SSH: who may sign in without root
  const was = await p.evaluate(async () => (await (await fetch('?api=sshd')).json()));
  const conf = Object.assign({}, was.want || was.conf || {}, {manage: true, permit_root: 'prohibit-password', allow_users: ['falco']});
  const r = await p.evaluate(async (c) => { const x = await fetch('?api=sshd', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'save', conf: c})}); return [x.status, await x.text()]; }, conf);
  ok('SSH: AllowUsers falco, root by key: saved', r[0] === 200, r[1]);
  const back = Object.assign({}, was.want || was.conf || {}, {manage: false});
  const r2 = await p.evaluate(async (c) => (await fetch('?api=sshd', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'save', conf: c})})).status, back);
  ok('SSH: put back (otp keeps out of sshd)', r2 === 200, r2);
  await p.goto('https://127.0.0.1/admin/#settings/sshd'); await p.waitForTimeout(2500);
  ok('SSH help: root left out signs in at the console', /Root left out of the list signs in only at the console/.test(await p.textContent('body')));
  ok('no page errors', errs.length === 0, errs.join(' | '));
  await b.close();
  console.log('ALL ' + R.filter(Boolean).length + ' / ' + R.length);
})();
