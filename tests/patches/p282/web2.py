# 1.0.282 pages (2): the keytab guide's values from AD - python3 web2.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [(
"""function loadKrb() {
  var host = $('krb-host');
  if (!host) return;
  api('kerberos').then(function (d) { KRB.d = d; drawKrb(); }).catch(function (e) {""",
"""/* The guide's values from the directory itself (1.0.282): the domain's NetBIOS name and DNS name, and
   the account holding each SPN - asked once in ten minutes, the card drawn again with them. */
function krbAskAd(force) {
  if (!(ME && ME.role === 'fulladmin') || !KRB.d || !KRB.d.directory) return;
  if (!force && KRB.ad && Date.now() - KRB.adAt < 600000) return;
  if (KRB.adAsking) return;
  KRB.adAsking = true;
  api('kerberos', {action: 'ad'}).then(function (x) {
    KRB.adAsking = false; KRB.ad = x; KRB.adAt = Date.now(); drawKrb();
  }).catch(function (e) {
    KRB.adAsking = false; KRB.ad = {ok: false, said: String(e && e.message || e)}; KRB.adAt = Date.now(); drawKrb();
  });
}
function loadKrb() {
  var host = $('krb-host');
  if (!host) return;
  api('kerberos').then(function (d) { KRB.d = d; drawKrb(); krbAskAd(false); }).catch(function (e) {"""), (
"""  var realm = d.realm || 'CORP.EXAMPLE';
  var v = {dom: realm.split('.')[0], acct: 'svc-otp-http', realm: realm};
  host.appendChild(el('h3', 'peek-h', 'Making the keytab in AD'));""",
"""  var realm = d.realm || 'CORP.EXAMPLE';
  /* From AD where it said them (1.0.282): its NetBIOS name is not always the first part of the DNS one
     (MERIT_NT for merit.cz), and an SPN already on an account names that account. */
  var ad = KRB.ad && KRB.ad.ok ? KRB.ad : null;
  var held = {};
  if (ad) Object.keys(ad.spn || {}).forEach(function (s) { (ad.spn[s] || []).forEach(function (a) { held[a] = (held[a] || []).concat([s]); }); });
  var holders = Object.keys(held);
  var v = {dom: (ad && ad.netbios) || realm.split('.')[0], acct: holders.length === 1 ? holders[0] : 'svc-otp-http',
           realm: (ad && ad.realm) || realm};
  host.appendChild(el('h3', 'peek-h', 'Making the keytab in AD'));
  var from = el('div', 'krb-adsaid');
  if (ad) {
    from.appendChild(certTag('ok', 'from AD'));
    from.appendChild(el('span', 'small', 'the domain ' + (ad.netbios || '?') + ' (NetBIOS), ' + (ad.dns || '?') + ' (DNS) - as ' + ad.directory + ' says them'));
  } else if (KRB.ad) {
    from.appendChild(certTag('warn', 'guessed'));
    from.appendChild(el('span', 'small', 'the directory did not say the domain\\'s names (' + (KRB.ad.said || '?') + ') - the NetBIOS name below is the first part of the realm: check it (set /a USERDOMAIN on a computer of the domain)'));
  } else {
    from.appendChild(certTag('dim', 'asking AD…'));
  }
  var again = iconButton('refresh', 'Ask AD again');
  again.dataset.key = 'krb-ad-again';
  again.onclick = function () { krbAskAd(true); };
  from.appendChild(again);
  host.appendChild(from);
  if (ad && ad.realm && d.realm && ad.realm.toUpperCase() !== String(d.realm).toUpperCase())
    host.appendChild(el('p', 'note warn', 'The realm used here is ' + d.realm + ', and AD says its domain is ' + ad.realm + ' - set the realm (admin_kerberos_realm) to it.'));
  if (holders.length > 1)
    host.appendChild(el('p', 'note bad', 'The SPNs are on more than one account (' + holders.join(', ') + ') - one key serves them all only when one account holds them: setspn -D them from the others.'));
  else if (holders.length === 1)
    host.appendChild(el('p', 'note', 'AD has the SPN' + (held[holders[0]].length > 1 ? 's' : '') + ' ' + held[holders[0]].join(', ') + ' on ' + v.dom + '\\\\' + holders[0] + ' already - that account is the one below.'));""")])
s = open(O + 'web/assets/otp.css').read()
if '.krb-adsaid' not in s:
    s += '''
/* Where the keytab guide's values come from (1.0.282). */
.krb-adsaid{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:-2px 0 10px}
.krb-adsaid .tag{flex:none}
'''
    open(O + 'web/assets/otp.css', 'w').write(s)
print('1.0.282 web (2) patched')
