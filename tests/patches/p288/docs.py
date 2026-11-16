# 1.0.288 docs: the card watched - the kit's 4th edition - python3 docs.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/docs/admin-certificate.md'
s = open(F).read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


rep('Found on a real iPad: **Safari on iPadOS signs nothing for a page in the background**',
    'First thought to be an iPad\'s way (isemon\'s kit, 3rd edition; its 4th found the cause was a policy header '
    'of isemon\'s own nginx, which otp does not send): **a browser that signs nothing for a page in the background**')
rep('have the card checked (as an iPad cannot): this sign-in is not watched.*',
    'have the card checked: this sign-in is not watched.*')
rep('Choose it where every sign-in must be watched and no iPad is used.',
    'Choose it where every sign-in must be watched.')
rep('did not sign the connection)* - the last is what an iPad gives.', 'did not sign the connection)*.')
rep('### Kind to the card', '''### The kit's 4th edition (1.0.288)

Found by isemon on Windows 10 + Chrome with a smart card and an iPad with a YubiKey:

- **Windows' "Insert a smart card" window, the browser's certificate chooser.** A check waiting on one for
  over 4 s counts as the card out: the countdown shows at once, behind that window, and the pages are told
  (`card-gone {why: waiting}`). The server takes it as *out* only for a browser whose checks have already
  found the card - never as *cannot be checked*. Put back and answered with OK, the check comes back and
  the notice goes.
- **Cancel in that window**: Chrome and Edge then offer no certificate to that address until the browser
  is closed and opened again - no page can change that. The notice says so: *press OK there - not Cancel*.
- **F5 during the countdown** went on from the full grace; it now counts from when the server saw the card
  out (whoami's `card.out_for`).
- **The mode changed** (`admin_cert_card`, from the pages, the command line or the other node): each
  watched sign-in's count starts afresh - none ends at once for time counted under the mode before.
- **Root still putting the port into nginx** (a request for root waiting, at most 5 minutes): a check that
  got nothing says nothing about the browser yet - no *cannot be checked*.
- **Ended by the server** - the check's picture is 5 px wide (the card out too long) or 6 px (another
  card): the page says why on the sign-in page and tries nothing by itself (a 403 left it without a word).
- **A page reached by an IPv6 address or a name with an underscore** - which a policy (CSP) cannot name:
  pictures over https are let in (`img-src 'self' data: https:`). Before, the card of such a page went
  unchecked and its sign-in was held once the page stopped checking.

otp's nginx sends no policy header of its own beside the page's (the kit's main fix of the 4th edition
is isemon's own): nothing to change there.

### Kind to the card''')
open(F, 'w').write(s)
print('1.0.288 docs patched')
