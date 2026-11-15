# 1.0.283 pages: a CSR made in the browser from the values of the account - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'
HERE = __file__.rsplit('/', 1)[0]


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


CSR_JS = open(HERE + '/csr.js').read()
edit('web/assets/admin.js', [(
"""  all.appendChild(cpSan);
  out.appendChild(all);""",
"""  all.appendChild(cpSan);
  /* A request made here, in this browser (1.0.283): the values above, chosen and added to first. */
  var mk = cmdButton('Make a CSR…', 'key', 'primary small');
  mk.id = 'creq-csr';
  mk.title = 'A key pair made in this browser - it never leaves it - and its certificate request (CSR) with the values above; what goes in is chosen first.';
  mk.disabled = !(window.crypto && window.crypto.subtle);
  mk.onclick = function () { modalOver(function () { csrWin(x); }); };
  all.appendChild(mk);
  out.appendChild(all);"""), (
"""function certRequestShow(out, x) {""",
CSR_JS + r"""/* What goes into the request, chosen and added to before it is made (1.0.283). */
function csrWin(x) {
  var f = {};
  var chk = function (on, words, id) {
    var lab = el('label', 'chk');
    var c = el('input'); c.type = 'checkbox'; c.checked = !!on; if (id) c.id = id;
    lab.appendChild(c); lab.appendChild(el('span', '', ' ' + words));
    return {lab: lab, box: c};
  };
  modal('Make a certificate request (CSR)', function (body) {
    body.appendChild(el('p', 'note', 'The key pair is made in this browser and never leaves it: the request and the private key are handed to you as files, and nothing of them is sent to the server. For a smart card or a YubiKey (PIV) the key is made on the card instead - certreq\'s request.inf of the window before, or ykman.'));
    var g = el('div', 'formgrid csr-grid');
    f.key = selectBox([['rsa2048', 'RSA 2048 (what AD CS templates ask by default)'], ['rsa3072', 'RSA 3072'], ['rsa4096', 'RSA 4096'],
                       ['p256', 'ECDSA P-256'], ['p384', 'ECDSA P-384']], 'rsa2048');
    f.key.id = 'csr-key';
    var kf = formField('The key', f.key);
    kf.classList.add('csr-keyf');
    body.appendChild(el('h3', 'peek-h', 'The key pair'));
    body.appendChild(kf);
    [['cn', 'CN (Common Name)', x.cn], ['o', 'O (organization)', ''], ['ou', 'OU (its unit)', ''], ['l', 'L (city)', ''],
     ['st', 'ST (region)', ''], ['c', 'C (country, two letters)', '']].forEach(function (s) {
      f[s[0]] = textBox(s[2] || '', s[0] === 'c' ? 'CZ' : '', 'mono');
      f[s[0]].id = 'csr-' + s[0];
      if (s[0] === 'c') f.c.maxLength = 2;
      g.appendChild(formField(s[1], f[s[0]]));
    });
    body.appendChild(el('h3', 'peek-h', 'Subject'));
    body.appendChild(g);
    body.appendChild(el('h3', 'peek-h', 'Subject Alternative Name'));
    var sg = el('div', 'csr-sans');
    [['upn', 'UPN (Other Name - Principal Name)', x.upn, !!x.upn], ['url', 'URL - the SID (strong mapping, KB5014754)', x.url, !!x.url],
     ['email', 'e-mail (RFC 822 Name)', x.mail, !!x.mail]].forEach(function (s) {
      var c = chk(s[3], s[1], 'csr-use-' + s[0]);
      var t = textBox(s[2] || '', '', 'mono');
      t.id = 'csr-' + s[0];
      var row = el('div', 'csr-san');
      row.appendChild(c.lab); row.appendChild(t);
      sg.appendChild(row);
      f['use_' + s[0]] = c.box; f[s[0]] = t;
    });
    body.appendChild(sg);
    body.appendChild(el('h3', 'peek-h', 'What the certificate is for'));
    var eg = el('div', 'csr-eku');
    f.eku = [];
    [['1.3.6.1.5.5.7.3.2', 'Client Authentication', true], ['1.3.6.1.4.1.311.20.2.2', 'Smart Card Logon', true],
     ['1.3.6.1.5.5.7.3.4', 'Secure Email', false]].forEach(function (e, i) {
      var c = chk(e[2], e[1] + ' (' + e[0] + ')', 'csr-eku-' + i);
      c.box.value = e[0];
      f.eku.push(c.box);
      eg.appendChild(c.lab);
    });
    body.appendChild(eg);
    f.template = textBox('', 'SmartcardLogon', 'mono');
    f.template.id = 'csr-template';
    body.appendChild(formField('The template of AD CS (optional - written into the request; certreq -attrib names it too)', f.template));
    body.appendChild(el('h3', 'peek-h', 'The private key'));
    var pc = chk(true, 'Protected by a passphrase (PKCS#8, AES-256 - openssl and Windows read it)', 'csr-protect');
    f.protect = pc.box;
    pc.lab.classList.add('csr-protect');
    body.appendChild(pc.lab);
    var pg = el('div', 'formgrid csr-pass');
    f.pass = maskBox('', '', 'mono'); f.pass.id = 'csr-pass';
    f.pass2 = maskBox('', '', 'mono'); f.pass2.id = 'csr-pass2';
    var p1 = formField('Passphrase', f.pass), p2 = formField('Again', f.pass2);
    pg.appendChild(p1); pg.appendChild(p2);
    body.appendChild(pg);
    f.protect.onchange = function () { pg.hidden = !f.protect.checked; };
    f.out = el('div', 'csr-out');
    body.appendChild(f.out);
  }, [{words: 'Close', close: true}, {words: 'Make the CSR', cls: 'primary', icon: 'key', go: function (b) {
    var said = function (w) { clear(f.out); f.out.appendChild(el('p', 'note bad', w)); f.out.scrollIntoView({block: 'nearest'}); };
    var subject = ['cn', 'o', 'ou', 'l', 'st', 'c'].map(function (k) { return [k, f[k].value.trim()]; });
    if (!f.cn.value.trim()) return said('The CN is needed.');
    if (f.c.value.trim() && !/^[A-Za-z]{2}$/.test(f.c.value.trim())) return said('C is the two letters of a country (CZ).');
    var use = function (k) { return f['use_' + k].checked ? f[k].value.trim() : ''; };
    if (f.use_upn.checked && !/^[^@\s]+@[^@\s]+$/.test(f.upn.value.trim())) return said('The UPN is name@domain.');
    if (f.use_url.checked && !/^tag:microsoft\.com,2022-09-14:sid:S-1-[0-9-]+$/i.test(f.url.value.trim())) return said('The URL of the SID is tag:microsoft.com,2022-09-14:sid:S-1-5-21-...');
    if (f.use_email.checked && !/^[^@\s]+@[^@\s]+$/.test(f.email.value.trim())) return said('The e-mail is not an address.');
    if (/[^\x20-\x7e]/.test(use('url') + use('email'))) return said('The URL and the e-mail are of plain letters only.');
    var eku = f.eku.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    if (!eku.length) return said('At least one: what the certificate is for.');
    var pass = '';
    if (f.protect.checked) {
      if (f.pass.value.length < 8) return said('The passphrase: 8 characters at least.');
      if (f.pass.value !== f.pass2.value) return said('The passphrase typed twice differs.');
      pass = f.pass.value;
    }
    busy(b, true);
    clear(f.out);
    f.out.appendChild(el('p', 'muted small', 'Making the key pair and the request in this browser…'));
    csrMake({key: f.key.value, subject: subject, upn: use('upn'), url: use('url'), email: use('email'), eku: eku,
             template: f.template.value.trim(), pass: pass}).then(function (r) {
      busy(b, false);
      csrShowMade(f.out, r, x, !!pass);
    }).catch(function (e) { busy(b, false); said('It could not be made: ' + (e && e.message || e)); });
  }}], 'medium');
}
function csrShowMade(out, r, x, locked) {
  clear(out);
  var base = String(x.name || 'request').replace(/[^A-Za-z0-9._-]+/g, '_') + '-' + new Date().toISOString().slice(0, 10).replace(/-/g, '');
  var save = function (text, file) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], {type: 'application/octet-stream'}));
    a.download = file;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  var ok = el('p', 'note');
  ok.appendChild(certTag('ok', 'made'));
  ok.appendChild(el('span', '', 'The request below goes to AD CS (certreq -submit, or the web enrolment); the key stays with you -'));
  ok.appendChild(el('span', '', locked ? 'locked by the passphrase.' : 'not locked: keep it where nobody else reads it.'));
  out.appendChild(ok);
  out.appendChild(noI18n(el('pre', 'wrap mono small creq-pre', r.csr)));
  var row = el('div', 'btnrow');
  var d1 = cmdButton('Download the CSR', 'download', 'primary small'); d1.id = 'csr-dl-csr';
  d1.onclick = function () { save(r.csr, base + '.csr'); };
  var d2 = cmdButton('Download the key', 'download', 'small'); d2.id = 'csr-dl-key';
  d2.onclick = function () { save(r.key, base + '.key'); };
  var c1 = cmdButton('Copy the CSR', 'copy', 'small'); c1.id = 'csr-copy';
  c1.onclick = function () { copyText(r.csr, c1, 'the CSR copied'); };
  row.appendChild(d1); row.appendChild(d2); row.appendChild(c1);
  out.appendChild(row);
  out.appendChild(el('p', 'note warn small', 'The private key is not kept anywhere - download it now: made again, the request has a new key.'));
  out.scrollIntoView({block: 'nearest'});
}
function certRequestShow(out, x) {""")])
s = open(O + 'web/assets/otp.css').read()
if '.csr-san' not in s:
    s += '''
/* A CSR made in the browser (1.0.283). */
.csr-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.csr-sans{display:flex;flex-direction:column;gap:8px}
.csr-san{display:grid;grid-template-columns:minmax(220px,auto) 1fr;gap:10px;align-items:center}
.csr-san input[type=text]{min-width:0}
.csr-eku{display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:16px}
.csr-keyf{max-width:520px}
.csr-protect{display:block;margin-bottom:10px}
.csr-pass{grid-template-columns:repeat(2,minmax(0,1fr))}
.csr-out{margin-top:12px}
.csr-out > .note:first-child{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
@media (max-width:640px){
  .csr-grid{grid-template-columns:1fr}
  .csr-san{grid-template-columns:1fr}
}
'''
    open(O + 'web/assets/otp.css', 'w').write(s)
print('1.0.283 web patched')
