## 1.0.337 — 24 November 2026

**Fixed (upgrade)**: an upgrade of the cluster started from a node in maintenance - set by hand, or left there by an earlier upgrade whose checks failed - waited for good: the other node, whose turn it was, waited for this one to be in service again, and this one for its turn. No other upgrade was taken until it was stopped. A node in maintenance is now upgraded first.

**Fixed**: a realm renamed and given another directory in one save was refused as "the realm ... already keeps its tokens under the name alone" - compared with itself as it was.

**Fixed (import)**: clients.conf's `require_message_authenticator = true` (or `on`, `Yes`) was taken as no - the client lost the rule that it must sign (BlastRADIUS); FreeRADIUS 2's `netmask` is taken as the network. A totpcgi import run again stopped part way when its realm was written in capital letters. A `.totp` file beginning with a BOM (saved by Notepad) was "not a base32 key" inside a ZIP.

