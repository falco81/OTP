# 1.0.285 docs: the card watched - python3 docs.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/docs/admin-certificate.md'
s = open(F).read()
a = '## On the sign-in page'
assert s.count(a) == 1 and 'admin_cert_card' not in s
s = s.replace(a, '''## When the card is taken out (1.0.285)

On the card *Signing in with a certificate*:

| Key | Values | Default | Shown as |
|---|---|---|---|
| `admin_cert_card` | `off`, `signout`, `grace` | `off` | *When the card is taken out* |
| `admin_cert_card_s` | 5-300 | 15 | *Checked every (seconds)* |
| `admin_cert_card_grace_s` | 5-600 | 30 | *...put back within (seconds)* |

- **`off`** (the default): nothing is checked, the page loads nothing more, and nginx's server on the
  certificate's port is written exactly as before.
- **`signout`**: the first check without the card ends the session; the sign-in page says *Signed out:
  the card you signed in with was taken out.*
- **`grace`**: a notice covers the page (*Put the card back*, the seconds left in a ring that empties, *Sign out*; nothing behind it
  can be used, and the server answers no question of the session meanwhile - HTTP 423). The card back in
  time: the notice goes. Not back in time: *Signed out: the card you signed in with was not put back in
  time.*
- **Another card** than the one signed in with ends the session at once, in either mode.
- Only a sign-in made with a certificate (by 1.0.285 or later) is watched - a password, Windows
  (Kerberos) and RADIUS never are.

### How

A browser has no event for "the smart card was taken out"; the only sure sign is that the card can no
longer sign. Every `admin_cert_card_s` seconds the page loads a picture from the certificate's port
(`/admin/?api=cert-alive`): a new TCP and TLS connection - while watching is on, nginx keeps no TLS
session (`ssl_session_cache off`, `ssl_session_tickets off`) and no connection (`keepalive_timeout 0`)
there - whose handshake only the card's key can sign. PHP hands the certificate that came (none: the card
is out) and the session's cookie to the daemon, which compares its SHA-256 with the one kept with the
sign-in. The answer is a picture 1 pixel wide (the card is there), 2 wide (out, the session waits) or a
403 (the session is over). A picture needs no CORS and gives another site nothing to read; the page's
Content-Security-Policy lets in that one address (`img-src ... https://<name>:<port>`), only for a
watched session. A handshake that fails reaches nothing: the page asks once more, then tells the pages on
443 (`?api=card-gone`), which hold or end only that same session.

The state is kept with the session in the database: either node of a cluster answers a check, and a
restart of the daemon forgets nothing. The server ends a watched session on its own too - the card out
longer than the grace plus *late*, or no check for *late* + grace + max(interval, 30 s), *late* being
three checks or 150 s, the longer (a browser checks a tab in the background about once a minute). Every
end is in the events: `... was signed out: the card they signed in with was taken out` (`...was not put
back in time`, `another certificate than the one signed in with was offered (the card was changed)`,
`their page stopped checking the card they signed in with`).

### Kind to the card

- One check at a time; the tabs of one browser share one check (the others take its answer).
- No PIN at each check, normally: while the card stays in, Windows (the smart-card minidriver) and the
  browser keep the PIN; a YubiKey's PIV slot 9a has PIN policy `once` by default. A key with touch or PIN
  policy `always` would ask at every check - leave watching off for one.
- Windows may show *Insert a smart card* when the browser tries the missing key. Answering it fails the
  check; a check that waited on such a window is followed by a longer pause, so it does not come back
  again and again; after the end, the sign-in page tries nothing by itself, so the browser's certificate
  chooser does not open on its own either.
- A one-off lost connection is asked again before it counts as the card out.

For the whole computer, Windows does it itself - the group policy *Interactive logon: Smart card removal
behavior* = **Lock Workstation** (or **Force Logoff**), with the service **Smart Card Removal Policy**
(`SCPolicySvc`) started. Both together are best. A load balancer in front of the certificate's port must
pass it through as TCP.

''' + a, 1)
open(F, 'w').write(s)
print('docs patched')
