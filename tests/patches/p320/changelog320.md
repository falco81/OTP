## 1.0.320 — 23 November 2026

**Security**: root's SSH keys are only shown on the pages since 1.0.280 - but making, putting on or making again *root's* key was refused only when the request named root: one naming any other user still put a key into */root/.ssh/authorized_keys* of every node. Refused whoever is named.

**Security (high security)**: isemon's targets, or isemon switched on, saved by themselves were never looked at - plain syslog, or a certificate not checked, went through while high security was on. They are looked at.

**Bug fix (high security)**: root over SSH with a key and the code from otp (no password to fall back on) was taken by high security's check, which then refused every later save of the SSH server - even of its notice. It is taken there too.

**Bug fix (network)**: a change of this node's address that failed after config.json was given the new address of the database (a database on this node, or a node on its own) said *nothing of the network was changed* - and config.json still named an address that never came: the next start could not reach the database. It is put back as it was.

**Bug fix (network)**: a node's name changed from a short one to a full one (*otp1* to *otp2.example.cz*) gave a self-signed certificate naming only *otp2* - never the full name the browsers ask for. The full name is in it.

**Bug fix (two nodes)**: a system update or an upgrade of otp could start while a node had a new network on trial: the other node was drained meanwhile, the trial ran out and went back with a restart - both nodes down at once. It waits until the network is kept or put back.

**Bug fix (SELinux)**: an SSH server listening on more than one port (*22 2222*) had none of them labelled for SELinux.

**Bug fix (report)**: a scheduled report that could not be made (too big for the time the reader is given, no address set) was made again every minute, and one that could not be put into a mail (no sender address set) was kept as sent - that period's report never went, even once the sender was set. Both are tried again in 30 minutes.

**Bug fix (two nodes of one database)**: the Alerts, syslog/SIEM and isemon panes showed only the node they were opened on - the alert mails named both.

