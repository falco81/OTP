## 1.0.317 — 23 November 2026

**Bug fix**: an administrator's second step by e-mail or SMS during a mail or SMS outage: each try that could not send counted against the account's and the address's limit of codes all the same, so five tries had the administrator refused ("too many codes sent lately") for the whole window after the outage ended. A code that does not go no longer counts, as on the enrolment pages.

**Bug fix**: a mail address with letters such as *á* or *ř* before the @ (*jiří@…*), to a server without SMTPUTF8 (most): the code or the token's mail was tried again and again for a day and never went. It now fails at once, said as that: write the address in plain letters.

**Bug fix**: with the database guard on, adding, changing or taking out a certificate authority of the directory the administrators sign in against left that directory's signature wrong - nobody of it could sign in any more, and those signed in were signed out. The change is signed now; a directory taken out has its removal signed too.

**Bug fix**: a copy put back into PostgreSQL while RADIUS or the pages were in use: what waited on the restore wrote with the old numbering before it was set - a duplicate key, and the RADIUS line, the event or the sign-in lost. The numbering is now set before anybody else writes.

**Bug fix (RADIUS)**: an Access-Request with an EAP-Message and no Message-Authenticator is now discarded, as RFC 3579 says, not refused (EAP is not taken here either way).

**Bug fix (pages)**:
- A check asked of every node (a test, the CRL, the database's certificates): a slow answer had the next second's ask overtake it - the end said twice (two notices, the pane loaded twice) and *did not answer* said again of a node that had answered. One ask at a time now, the end said once.
- The load balancer guide counted an IPv6 network only as one address: a balancer inside *2001:db8::/64* was said not to be let in, and a needless /128 was added to the command it gives.
- A colour pasted into a rich mail text went into the mail unescaped.
- *Show all* after a time window of the RADIUS requests opened on the page you were on, not the newest, and the list stopped refreshing.
- The remote backups' sizes now use the page's decimal mark (*1,5 MB* in Czech).

