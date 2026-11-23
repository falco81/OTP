## 1.0.322 — 23 November 2026

**Bug fix (restore)**: a copy or a backup made by a newer otp went back onto an older one without a word: tables, columns and settings this version does not know were left out or misread, and every guard of a downgrade (passkeys, the floor a node may not go below) went round. It is refused now, saying which version made it - from the pages always, on the command line unless `--allow-newer` is given (`otp --restore FILE --yes --allow-newer`, `otp --restore-bundle ...`).

**Bug fix (two nodes of one database)**: a remote backup put back on one node of a cluster of one shared database (ha_mode empty there) gave it the other node's name - two nodes of one name, both holding the VIP. The node keeps its own name, as in a replicated cluster.

**Bug fix (split brain watch)**: a look at the other node's database that answered after its 3.5 s closed the connection of the next look - a look counted as failed for nothing on a slow link.

