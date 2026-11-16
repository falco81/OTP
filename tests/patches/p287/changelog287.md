## 1.0.287 — 16 November 2026

Three rounds of looking for bugs and security problems through the whole application; each round's own fixes looked at again by the next. Every finding checked in the code and traced to a real path before it was fixed.

Upgrades and the database
- **An upgrade whose daemon does not start puts the version before back**: its program, deploy/, root's helpers, its unit and the pages are kept until the new one has run for ten seconds without systemd starting it again; a new version that falls over at its start was left in place before, and the node stayed without RADIUS until it was repaired by hand.
- **A replicated node's nightly backup can be put back there**: it is a portable copy now (a dump makes tables anew, which replication does not carry - it was refused, and no copy was made by itself).
- **One copy put back at a time**: from the page, a kept one, `otp --restore` or a remote one - on this node and on the other (the same rows inserted on both stopped replication both ways); a job (an erase, a move) does not start meanwhile.
- A kept copy is no longer downloaded "with its key" when no .key lies beside it (the key in use went with it - put back elsewhere, every token was refused).
- Files written by otp (config.json, keys) are on the disk before their name: after a power cut config.json could be empty, and the daemon did not start.
- config.json changed while the daemon started (`otp --set`, `--ha-readdress`) is read at the next reload.

Sign-in and security
- An account whose row in the database is not as otp wrote it (the database guard) is no longer signed again with what somebody else put in - by a password reset or a sign-in from the directory; such a directory account is refused at sign-in. `otp --passwd NAME` (root) signs it again.
- The roles of directory administrators are not asked again of a directory whose row is not as otp wrote it - they are signed out, as a sign-in is refused.
- A directory or a revocation server (CRL, OCSP) that cannot be reached no longer counts as a wrong password - after it was back, the name or the office's whole address was locked out.
- The certificate's port takes only GET and HEAD, no multipart body, 16 kB at most - as otp's other servers.
- The card watched: the page's check carries a key made from the session - a page of another host of the same site cannot end or unwatch it (only a card found counts without it, so a page loaded before the upgrade keeps going); "cannot be checked" no longer written over a check that found the card at the same moment; the pages are loaded again only once when their address cannot be let into their policy (they did every minute).
- The certificate request (CSR) of an EC key: its key usage in strict DER.

The network, RADIUS, the cluster
- An address with an IPv6 scope id (fe80::1%ens192) in the balancers', SSO, SNMP, metrics, trusted or time servers' addresses is refused when set - root refused it inside its request, and with it every certificate, VIP and firewall change; one kept from before is left out. A network with its mask (10.0.0.0/255.0.0.0) is taken.
- RADIUS on `::`: an IPv4 client (::ffff:a.b.c.d) has its own line in the queue again, not the one of the addresses of nobody's.
- A reply through a proxy is measured with the request's Proxy-State before the code is used (near 4 KB the code was used up and the answer refused).
- A network change on trial that cut the node off from a shared database comes back the promised minutes after the machine started, not an hour later.
- Arbiter mode: one ping not answered no longer takes the only node left out of service - three checks in a row (about 6 s).
- "The other node" is the live one with the newest heartbeat - a node reinstalled under another name and never forgotten was taken for it (the clock guard, the measured clock difference, a split).
- A split: the preferred node's word read by the measured difference of the clocks.

Alerts, backups sent away, the rest
- An alert mail that failed with anything but a mail error (the key that seals the outgoing mail missing - the very alert about it) no longer stops the alerts; "right again" mails are no longer lost.
- A cluster with one database: the nightly copy of the cluster counts - the node that did not make it was told "no nightly copy" every day.
- A backup destination that lists a backup as 0 bytes no longer switches off the cap - never more than the room there is.
- High security's rules for backup destinations apply each time one is used, switched on or not ("Back up now" with its id, verify, put back, Try it).
- A configuration file's VIP without an address is switched off and its number read; realms and clients are matched in any case (the import stopped half way).
- `otp --set-role` and `--passwd` refuse accounts of the directory as the pages do; `otp --api` refuses a `bind_pw` written out on the command line.
- The sign-in by the load balancer ends whoever else was signed in in that browser first - before a refusal (429, 503) that showed their portal to the next person.
- The console's switch handles a full disk; the columns' switch writes only its own key of the session; log lines spared by the monotonic clock.

Pages loaded before this upgrade with the card watched: load them again.

