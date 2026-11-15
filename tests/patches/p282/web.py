# 1.0.282 pages: "Values for a certificate request" on the certificate's card - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [(
"""  row.appendChild(tryb);
  host.appendChild(row);
  certCrls(host, d);""",
"""  row.appendChild(tryb);
  /* The values of a certificate request for an account of the directory (1.0.282). */
  var reqb = cmdButton('Values for a certificate request…', 'key', '');
  reqb.id = 'cert-req';
  reqb.title = 'An account of the directory looked up: the subject, the UPN and the SID of the SAN its certificate needs - each to copy, and certreq\\'s and openssl\\'s words for them.';
  reqb.disabled = !full || !d.directory;
  reqb.onclick = function () { certRequestWin(''); };
  row.appendChild(reqb);
  host.appendChild(row);
  certCrls(host, d);"""), (
"""function certTag(cls, words) { return el('span', 'tag ' + cls, words); }""",
"""function certTag(cls, words) { return el('span', 'tag ' + cls, words); }
/* What a certificate request of an account needs (1.0.282): the account looked up in the directory set
   for administrators, its values each with a copy button - the subject, the UPN of the SAN, the SID as
   the URL of the SAN for the strong mapping (KB5014754) - and certreq's .inf and openssl's config. */
function certRequestWin(name) {
  var box, inp, go, out;
  var find = function () {
    var who = inp.value.trim();
    if (!who) { inp.focus(); return; }
    busy(go, true);
    clear(out);
    out.appendChild(el('p', 'muted small', 'Asking the directory…'));
    api('certlogin', {action: 'request', name: who}).then(function (x) {
      busy(go, false);
      certRequestShow(out, x);
    }).catch(function (e) {
      busy(go, false);
      clear(out);
      out.appendChild(el('p', 'note bad', String(e && e.message || e)));
    });
  };
  modal('Values for a certificate request', function (body) {
    body.appendChild(el('p', 'note', 'An account of the directory set for administrators: its subject, the UPN and the SID the certificate must name to sign in here - as AD CS writes them since KB5014754 (strong mapping). Nothing is changed or kept.'));
    var row = el('div', 'creq-find');
    inp = textBox(name || '', 'jnovak, CORP\\\\jnovak or jnovak@corp.example', 'mono');
    inp.id = 'creq-name';
    inp.onkeydown = function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); find(); } };
    go = cmdButton('Find', 'search', 'primary');
    go.id = 'creq-find';
    go.onclick = find;
    row.appendChild(inp);
    row.appendChild(go);
    body.appendChild(row);
    out = el('div', 'creq-out');
    body.appendChild(out);
    setTimeout(function () { inp.focus(); }, 60);
  }, [{words: 'Close', close: true}], 'large');
  if (name) find();
}
function certRequestShow(out, x) {
  clear(out);
  var head = el('div', 'creq-head');
  var who = el('div', 'creq-who');
  who.appendChild(noI18n(el('b', '', x.display || x.cn || x.name)));
  who.appendChild(noI18n(el('span', 'mono small muted', x.name + ' · ' + x.directory)));
  head.appendChild(who);
  var tags = el('div', 'creq-tags');
  tags.appendChild(certTag(x.role ? 'ok' : 'warn', x.role ? (x.role === 'fulladmin' ? 'full administrator' : x.role === 'readonly' ? 'read only' : x.role) : 'no role here'));
  if (x.disabled) tags.appendChild(certTag('crit', 'switched off'));
  if (x.locked) tags.appendChild(certTag('warn', 'locked out'));
  tags.appendChild(certTag(x.sid ? 'info' : 'warn', 'mapping: ' + x.map));
  head.appendChild(tags);
  out.appendChild(head);
  (x.notes || []).forEach(function (n) { out.appendChild(el('p', 'note ' + (n[0] === 'bad' ? 'bad' : 'warn'), n[1])); });
  var grid = el('div', 'creq-grid');
  var line = function (key, label, value, says) {
    var k = el('div', 'creq-k');
    k.appendChild(el('span', '', label));
    if (says) k.appendChild(el('span', 'creq-says', says));
    grid.appendChild(k);
    var v = el('div', 'creq-v');
    var t = noI18n(el('span', 'mono', value || '–'));
    v.appendChild(t);
    grid.appendChild(v);
    var c = el('div', 'creq-c');
    if (value) {
      var b = iconButton('copy', 'Copy it');
      b.dataset.key = 'creq-copy-' + key;
      b.id = 'creq-copy-' + key;
      b.onclick = function () { copyText(value, b, label + ' copied'); };
      c.appendChild(b);
    }
    grid.appendChild(c);
  };
  line('subject', 'Certificate subject', x.subject, 'the certificate\\'s name');
  line('cn', 'CN', x.cn, 'Common Name');
  line('upn', 'SAN: UPN', x.upn, 'Other Name - Principal Name (1.3.6.1.4.1.311.20.2.3)');
  line('url', 'SAN: URL', x.url, 'the SID - strong mapping (KB5014754)');
  line('email', 'SAN: e-mail', x.mail, 'RFC 822 Name - not needed to sign in');
  line('sid', 'SID', x.sid, 'objectSid of the account');
  line('dn', 'Account', x.dn, 'its place in the directory');
  out.appendChild(grid);
  var all = el('div', 'btnrow');
  var cpSan = cmdButton('Copy the SAN', 'copy', 'small');
  cpSan.id = 'creq-copy-san';
  cpSan.onclick = function () { copyText((x.san || []).join('\\n'), cpSan, 'the SAN copied'); };
  all.appendChild(cpSan);
  out.appendChild(all);
  var block = function (key, title, says, text, file) {
    var h = el('h3', 'peek-h', title);
    out.appendChild(h);
    out.appendChild(el('p', 'muted small', says));
    var pre = noI18n(el('pre', 'wrap mono small creq-pre', text));
    out.appendChild(pre);
    var r = el('div', 'btnrow');
    var cp = cmdButton('Copy', 'copy', 'small');
    cp.id = 'creq-copy-' + key;
    cp.onclick = function () { copyText(text, cp, title + ' copied'); };
    r.appendChild(cp);
    var dl = cmdButton('Download ' + file, 'download', 'small');
    dl.onclick = function () {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([text], {type: 'application/octet-stream'}));
      a.download = file;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    };
    r.appendChild(dl);
    out.appendChild(r);
  };
  block('certreq', 'Windows: certreq', 'certreq -new request.inf request.req, then certreq -submit -attrib "CertificateTemplate:SmartcardLogon" request.req - on the computer with the card (or the YubiKey); a template whose subject is "Supply in the request".', x.certreq, 'request.inf');
  block('openssl', 'openssl', 'openssl req -new -key the.key -config request.cnf -out request.csr - for a key made outside Windows (a YubiKey with ykman, a CSR of slot 9a).', x.openssl, 'request.cnf');
}""")])
s = open(O + 'web/assets/otp.css').read()
if '.creq-grid' not in s:
    s += r'''
/* Values for a certificate request (1.0.282). */
.creq-find{display:flex;gap:10px;align-items:center;margin:4px 0 14px}
.creq-find input{flex:1 1 auto;min-width:0}
.creq-head{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;margin:6px 0 10px}
.creq-who{display:flex;flex-direction:column;gap:2px}
.creq-who b{font-size:15px}
.creq-tags{display:flex;flex-wrap:wrap;gap:6px}
.creq-grid{display:grid;grid-template-columns:minmax(150px,auto) 1fr auto;gap:0;border:1px solid var(--line);
  border-radius:10px;overflow:hidden;margin:4px 0 10px}
.creq-grid > div{padding:9px 12px;border-bottom:1px solid var(--line);display:flex;align-items:center;min-width:0}
.creq-grid > div:nth-last-child(-n+3){border-bottom:0}
.creq-k{flex-direction:column;align-items:flex-start !important;gap:2px;background:var(--panel2)}
.creq-k > span:first-child{font-weight:600;font-size:13px}
.creq-says{font-size:11px;color:var(--tx-dim)}
.creq-v .mono{overflow-wrap:anywhere;word-break:break-all;font-size:13px}
.creq-c{justify-content:flex-end}
.creq-pre{max-height:260px;overflow:auto}
@media (max-width:640px){
  .creq-grid{grid-template-columns:1fr auto}
  .creq-k{grid-column:1 / -1;border-bottom:0 !important;padding-bottom:2px !important}
}
'''
    open(O + 'web/assets/otp.css', 'w').write(s)
print('1.0.282 web patched')
