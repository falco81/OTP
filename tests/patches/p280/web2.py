# 1.0.280 (2): the cards of Settings - Accounts drawn again after a save - python3 web2.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [(
"""      loadSettings(Object.keys(left).length ? false : undefined);
      if (paneLive('upgrade')) loadUpgrade();      /* the card to go back shown or not (1.0.144) */""",
"""      loadSettings(Object.keys(left).length ? false : undefined);
      if (paneLive('upgrade')) loadUpgrade();      /* the card to go back shown or not (1.0.144) */
      peopleCardsAgain(Object.keys(want));"""), (
"""function drawKrb() {""",
"""/* The cards of Windows, the certificate and the sign-in page drawn again after a save that
   touches them (1.0.280): only the settings were read again, the cards kept what they had until F5.
   Asked again a few times in the first minute too - root's helper puts nginx's part in a little later
   (the certificate's port listening, the keytab written on every node). */
var PEOPLE_AGAIN = [];
function peopleCardsAgain(keys) {
  if (!(keys || []).some(function (k) { return /^(admin_(kerberos|cert|password_off|2fa|directory|group_)|acme_node_name)/.test(String(k).split('@')[0]); })) return;
  PEOPLE_AGAIN.forEach(function (t) { clearTimeout(t); });
  PEOPLE_AGAIN = [0, 4000, 15000, 40000, 70000].map(function (ms) {
    return setTimeout(function () {
      if (!paneLive('people')) return;
      loadKrb();
      loadCert();
    }, ms);
  });
}
function drawKrb() {""")])
print('web2 patched')
# Drawn again keeping the place (1.0.280): drawn again after a save now, a card cleared and drawn whole
# moved what was under it.
edit('web/assets/admin.js', [(
"""  var d = KRB.d, host = $('krb-host');
  if (!host || !d) return;
  clear(host);
  var full = ME && ME.role === 'fulladmin';
  var kt = d.keytab || {};""",
"""  var real = $('krb-host');
  if (!real || !KRB.d) return;
  redrawKeepingPlace(real, drawKrbInto);
  drawSignin();
}
function drawKrbInto(host) {
  var d = KRB.d;
  var full = ME && ME.role === 'fulladmin';
  var kt = d.keytab || {};"""), (
"""  host.appendChild(el('p', 'note small muted', 'The way back from "only Windows", as root: otp --set admin_password_off=0 (or Kerberos switched off). More: docs/admin-kerberos.md in the package.'));
  drawSignin();
}""",
"""  host.appendChild(el('p', 'note small muted', 'The way back from "only Windows", as root: otp --set admin_password_off=0 (or Kerberos switched off). More: docs/admin-kerberos.md in the package.'));
}"""), (
"""function drawSignin() {
  var host = $('signin-host'), k = KRB.d, c = CERTL.d;
  if (!host || !k || !c) return;
  clear(host);
  var pwOff""",
"""function drawSignin() {
  var real = $('signin-host');
  if (!real || !KRB.d || !CERTL.d) return;
  redrawKeepingPlace(real, drawSigninInto);
}
function drawSigninInto(host) {
  var k = KRB.d, c = CERTL.d;
  var pwOff""")])
print('web2 (2) patched')
# The settings drawn again after a save keep the place (1.0.280): every box of every pane was
# cleared and made again with nothing holding the place - a save moved what was in view
# (66 px on Settings - Accounts).
edit('web/assets/admin.js', [(
"""function drawSettings() {
  /* The height held for the pane before let go (1.0.280): a short pane after a long one kept a gap. */
  paneLetGo();""",
"""function settingsPlace() {
  var pane = typeof PANE !== 'undefined' && PANE && $('pane-' + PANE);
  if (!pane || pane.hidden) return null;
  var act = document.activeElement, pick = act && pane.contains(act) ? act.closest('.set-item[data-key]') : null;
  if (!pick) {
    var all = pane.querySelectorAll('.set-item[data-key], [id$="-host"]');
    for (var i = 0; i < all.length && !pick; i++) {
      var r = all[i].getBoundingClientRect();
      if (r.height && r.bottom > 0 && r.top < window.innerHeight) pick = all[i];
    }
  }
  if (!pick) return null;
  return {sel: pick.dataset.key ? '.set-item[data-key="' + pick.dataset.key + '"]' : '#' + pick.id,
          top: pick.getBoundingClientRect().top, sc: scrollerOf(pick), pane: pane};
}
function settingsHold(place) {
  if (!place) return;
  var fix = function () {
    var n = place.pane.querySelector(place.sel);
    if (!n) return;
    var d = n.getBoundingClientRect().top - place.top;
    if (Math.abs(d) >= 1) place.sc.scrollTop += d;
  };
  fix();
  setTimeout(fix, 0);
  requestAnimationFrame(fix);
  setTimeout(fix, 150);
}
function drawSettings() {
  /* What is in view stays where it is (1.0.280): every box is made again below. */
  var place = settingsPlace();
  /* The height held for the pane before let go (1.0.280): a short pane after a long one kept a gap. */
  paneLetGo();"""), (
"""  if (typeof PANE !== 'undefined' && PANE === 'backup' && typeof rbPassTools === 'function') rbPassTools();
}""",
"""  if (typeof PANE !== 'undefined' && PANE === 'backup' && typeof rbPassTools === 'function') rbPassTools();
  settingsHold(place);
}""")])
print('web2 (3) patched')
