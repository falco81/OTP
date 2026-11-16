## 1.0.292 — 16 November 2026

**This machine's database shown as a database server** (isemon's external-database kit, opt-in). *Settings → The database → Show this machine's database as a database server* (`db_local_card`, **off by default**; offered for PostgreSQL and MariaDB only). Off, nothing changes: nothing is read, written or shown. docs/external-database.md → *This machine's database*.

- On, a node whose PostgreSQL or MariaDB is on its own machine (localhost, 127.0.0.1, ::1 or a socket) and has **no agent** looks at it every 30 s with its own connection and `/proc` (its version, whether it runs and for how long, TLS, the connections, its data's disk, the memory, the processors and the load, the end of the certificate otp gave PostgreSQL) and writes it into its row of the database, `dblocal:node:NODE` - no password in it. The other node of a cluster reads it as it reads every node's rows: nothing new is opened, asked or let in.
- The card *Database server* is drawn above *Encryption to the database server* with a tile per node - this node's first, another node not heard from lately in amber, a certificate ending within 14 days in red. Actions, only what otp already does for a database on this machine: *Look now*, *Renew the certificate* (Encryption to the database server's, or the link's between the databases), *Restart the database…* while PostgreSQL's own settings wait for a restart and install.sh let otp restart it.
- Not there, on purpose: the agent's rows, join codes, *Forget*, pills on other cards, rows in the meter or on High availability, alerts. With an agent the card stays the agent's.
- Switched off, the row is taken away - also when otp starts with the setting already off (the kit's version kept it then). A move to another server leaves it behind, as the other rows about the old server.
- The card's heading on a phone: the state under the title instead of beside it, so the title is no longer squeezed into a column of a word or two (the agent's card too).
- Czech for the setting and the card.

