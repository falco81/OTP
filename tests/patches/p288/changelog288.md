## 1.0.288 — 16 November 2026

The card watched while signed in with it (Settings → Accounts → Signing in with a certificate → When the card is taken out): what isemon's kit, 4th edition, found on Windows 10 + Chrome with a smart card and on an iPad with a YubiKey. Off (the default) nothing changes.

- **Windows' "Insert a smart card" window and the browser's certificate chooser**: a check waiting on one for over 4 s counts as the card out - the countdown shows at once, behind that window, rather than only after Cancel. The server takes it as out only for a browser whose checks have already found the card, never as "cannot be checked". Put back and answered with OK, the notice goes.
- The notice says: press **OK** in that window, not Cancel - after Cancel Chrome and Edge offer no card to the server until they are closed and opened again.
- **F5 during the countdown** no longer starts it again from the full time: it counts from when the server saw the card out.
- **The mode changed** (off, signout, grace - from the pages, the command line or the other node): each watched sign-in's count starts afresh; none ends at once for time counted under the mode before.
- While root is still putting the certificate's port into nginx (just switched on), a check that got nothing no longer makes the browser "one that cannot be checked" for good.
- **Ended by the server** (the card out too long, another card): the page says why on the sign-in page and tries nothing by itself; it was reloaded without a word.
- **Pages reached by an IPv6 address or a name with an underscore**: the check's picture is let in (the page's policy could not name such an address) - the card went unchecked there, and the sign-in was held once the page stopped checking.
- The words no longer say an iPad cannot be checked: isemon found its cause was a policy header of its own nginx (otp's nginx sends none). *A browser that cannot be checked* stays, as a safety net.
