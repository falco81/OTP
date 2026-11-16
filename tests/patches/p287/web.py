# 1.0.287 pages: the bug hunt's fixes in the browser code - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [
    # R1/5.1: the card watched, but this page's name is one the policy cannot carry (an underscore): PHP leaves
    # the card's address out of the page, the poll learnt it from whoami again - and loaded the page again every
    # minute, for good. Loaded again once per tab; then said, once.
    (
"""  var unsaved = (typeof DIRTY === 'object' && DIRTY && Object.keys(DIRTY).length) ||
                (typeof PENDING === 'object' && PENDING && Object.keys(PENDING).length);
  if (!unsaved) location.reload();
  else if (!CW.said) { CW.said = true; toast('The card you signed in with is watched from now on - save and reload the page.', 'warn'); }
}""",
"""  var unsaved = (typeof DIRTY === 'object' && DIRTY && Object.keys(DIRTY).length) ||
                (typeof PENDING === 'object' && PENDING && Object.keys(PENDING).length);
  var again = false;
  try { again = !!sessionStorage.getItem('otp.card.reloaded'); } catch (e) { again = true; }
  if (!unsaved && !again) {
    try { sessionStorage.setItem('otp.card.reloaded', '1'); } catch (e) { }
    location.reload();
  } else if (!CW.said) {
    CW.said = true;
    toast(again ? 'The card you signed in with cannot be checked from this address of the pages - open them by the server\\'s name.'
                : 'The card you signed in with is watched from now on - save and reload the page.', 'warn');
  }
}"""),
    (
"""if (typeof ME !== 'undefined' && ME && ME.card) certWatchStart(ME.card);""",
"""if (typeof ME !== 'undefined' && ME && ME.card) {
  try { sessionStorage.removeItem('otp.card.reloaded'); } catch (e) { }
  certWatchStart(ME.card);
}"""),
    # R1/5.3: KeyUsage of an EC key - digitalSignature alone is one bit: 7 unused (DER drops the trailing zeros).
    (
"""derOctets(derBits(ec ? [0x80] : [0xa0], 5))""",
"""derOctets(derBits(ec ? [0x80] : [0xa0], ec ? 7 : 5))"""),
])
# R1/4.2: the certificate's port took any method and a multipart body to PHP (which parses it before the
# page runs) - the guards of every other server of otp's were not carried over. Only GET there, small.
edit('deploy/otp_web.py', [(
"""    # A certificate nginx itself refuses""",
"""    # Only GET and HEAD, no body to speak of, never a multipart one (1.0.287) - as otp's other servers.
    out += ['    client_max_body_size 16k;',
            '    if ($request_method !~ ^(GET|HEAD)$) { return 405; }',
            '    if ($http_content_type ~* "multipart") { return 403; }']
    # A certificate nginx itself refuses""")])
# R1/1.5: the check's key (made from the session) in the picture's address, handed on by PHP - a page of
# another host of the same site cannot make one.
edit('web/assets/admin.js', [(
"""  img.src = 'https://' + location.hostname + ':' + c.port + '/admin/?api=cert-alive&r=' + Date.now().toString(36);""",
"""  img.src = 'https://' + location.hostname + ':' + c.port + '/admin/?api=cert-alive&k=' + encodeURIComponent(c.key || '') +
    '&r=' + Date.now().toString(36);""")])
edit('web/admin/index.php', [(
"""            [$status, $body] = otp_call('/api/auth/card', 'POST', ['cert' => $pem], 10.0);""",
"""            $k = preg_replace('/[^0-9a-f]/', '', substr((string) ($_GET['k'] ?? ''), 0, 64));
            [$status, $body] = otp_call('/api/auth/card', 'POST', ['cert' => $pem, 'k' => $k], 10.0);""")])
print('1.0.287 web patched')
