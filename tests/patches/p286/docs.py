# 1.0.286 docs: a browser that cannot be checked - python3 docs.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/docs/admin-certificate.md'
s = open(F).read()
a = '### Kind to the card'
assert s.count(a) == 1 and 'admin_cert_card_unable' not in s
s = s.replace(a, '''### A browser that cannot be checked (1.0.286)

Found on a real iPad: **Safari on iPadOS signs nothing for a page in the background** - the card is in,
yet the check never arrives. A session therefore keeps whether a check *in the background* has ever found
its card in this browser (the sign-in itself does not count: it was a top-level navigation, which the iPad
does sign).

- **Never yet**: the first check without the card means *this browser cannot be checked*.
  **A browser that cannot be checked** (`admin_cert_card_unable`):
  - `allow` (the default): that sign-in is not watched from then on - never held or ended for its card,
    its sleeping page not held either. An event says so and why, and the page says *This browser cannot
    have the card checked (as an iPad cannot): this sign-in is not watched.*
  - `signout`: on as for a card taken out - such a browser cannot stay signed in while watching is on.
    Choose it where every sign-in must be watched and no iPad is used.
- **Found once**: a later check without the card is a card taken out, as always.
- The trade-off: a card pulled in the first 1.5 s after the page loads, before its first check, makes
  that sign-in look unwatchable (with `allow`); the events say so.

The events say which it was: *no certificate came with the check (the browser does not sign it in the
background)*, *the browser sent no cookie with the check*, or *the check got no answer at all (the browser
did not sign the connection)* - the last is what an iPad gives. The check's picture says it too: 3 px - no
cookie came with it (the page then tells the pages on 443, where its cookie does come); 4 px - this
browser cannot be checked.

''' + a, 1)
open(F, 'w').write(s)
print('docs patched')
