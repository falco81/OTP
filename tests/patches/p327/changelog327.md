## 1.0.327 — 24 November 2026

**Bug fix (HA)**: in a replicated pair each node tidied the other's counts of codes sent and of wrong directory passwords too - a row deleted here while the other node added to it there lost its newest count: one code, or one directory password, more than the limit. Each node tidies only its own now; one written before 1.0.146 is the lead's.

**Bug fix (HA)**: a copy put back on the node of a replicated pair that is not the lead left the names of its tokens as the copy had them (letters written decomposed by a client before 1.0.222) until the lead started again - nobody found those tokens meanwhile. The lead is asked, and puts them in one form on its next look.

**Bug fix (trusted authorities)**: when the system's tool (update-ca-trust, update-ca-certificates) failed or ran out of time, a certificate taken away on the pages stayed trusted by the system - and every later look said it was done. It is run again until it runs through.

**Bug fix (message texts)**: `{account}` inside a link's address (`<a href="https://help.example/u/{account}">`) took the HTML that keeps a name from turning into a link - its quote closed the address, and the link of every mail with codes and every token's mail was broken. Inside a link's address each `{word}` is the plain value, as an address takes it.

**Bug fix (database agent, MariaDB)**: TLS for MariaDB could not be switched on: its files went to a folder only root could open, MariaDB started without TLS, and each try put it back with one restart of the database more - and did not start it again with what it had. The files go to `/etc/otp-db-agent-mariadb` (root:mysql, 0750); a set-up made to work by hand with the old folder keeps it; MariaDB is started again when it is put back.

**Bug fix (database agent)**: an otp node on IPv6 was taken by the wizard but got no answer - the agent and MariaDB listened on IPv4 alone. A new database server listens on both where the machine has IPv6 (and on IPv4 alone where it does not, as before); one set up before is left as it is.
