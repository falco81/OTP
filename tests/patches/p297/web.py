# 1.0.297 web: the portal's code boxes - wide enough for 10 digits, named for a screen reader; the
# reload after a last try only while its card is there; formField names a box inside a wrapper.
#   python3 web.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs, n=1):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == n, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('portal.js', [
("""  box.maxLength = 32;      /* "12345 67890" fits (1.0.227) */
  box.autocomplete = 'one-time-code';
  noI18n(box);""", """  box.maxLength = 32;      /* "12345 67890" fits (1.0.227) */
  box.autocomplete = 'one-time-code';
  /* Named for a screen reader (1.0.297): it read "000000". */
  box.setAttribute('aria-label', (typeof i18nText === 'function' && i18nText('The code')) || 'The code');
  noI18n(box);"""),
("""  box.maxLength = 32;      /* "1234 5678" fits (1.0.227): 8 cut it to 7 digits, counted wrong */
  box.autocomplete = 'one-time-code';
  noI18n(box);""", """  box.maxLength = 32;      /* "1234 5678" fits (1.0.227): 8 cut it to 7 digits, counted wrong */
  box.autocomplete = 'one-time-code';
  box.setAttribute('aria-label', (typeof i18nText === 'function' && i18nText('The code')) || 'The code');
  noI18n(box);"""),
("""        setTimeout(function () { api('me').then(function (d) { ME = d.me; drawPortal(); }).catch(function () { /* the next look draws it */ }); }, 2500);""",
 """        /* Only while this card is still there (1.0.297): "Send it again" pressed meanwhile drew
           a new one, and this wiped the code being typed into it. */
        setTimeout(function () { if (!document.body.contains(wrap)) return; api('me').then(function (d) { ME = d.me; drawPortal(); }).catch(function () { /* the next look draws it */ }); }, 2500);"""),
])
edit('otp.css', [
("""    letter-spacing:8px;text-align:center;width:220px !important;padding:10px 12px !important}""",
 """    letter-spacing:8px;text-align:center;width:min(100%,290px) !important;padding:10px 12px !important}"""),
])
edit('core.js', [
("""  var target = input && input._input ? input._input : input;
  if (target && target.nodeType === 1 && /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName)) {""",
 """  var target = input && input._input ? input._input : input;
  /* A box inside a wrapper (1.0.297): the code box and its send button - the label named nothing. */
  if (target && target.nodeType === 1 && !/^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName) && target.querySelectorAll &&
      target.querySelectorAll('input:not([type=hidden]),select,textarea').length === 1) target = target.querySelector('input:not([type=hidden]),select,textarea');
  if (target && target.nodeType === 1 && /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName)) {"""),
])
print('ok')
