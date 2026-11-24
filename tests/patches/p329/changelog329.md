## 1.0.329 — 24 November 2026

**Security (database agent)**: a node joined to a database agent could name any database or account on that server. On MariaDB it was given every right on another application's database, or an account there (a backup's, a monitoring one's) had its password reset; on PostgreSQL a role of the server's was given the node's password and let in from the network. Several clusters may share one database server, so one node taken over reached everything else on it. Now:
- each database and account is the cluster's whose node made it - known by the authority that signed its node's certificate, as the server's certificate already is; another cluster's node is refused it, by name. The other node of the same cluster, a node joined again, a cluster whose authority was renewed, are the same cluster. One whose nodes are gone (taken away, or not heard from for 30 days) may be taken over;
- one there before - made by an agent before 1.0.329, or by hand - is taken over by the first cluster that asks for it, only when it is otp's kind: on PostgreSQL an account that owns no other database (and a database owned by that account); on MariaDB an account with rights on that database alone, and a database no other account has rights on. otp's own are always that; an application's are not. Checked before anything is changed.

Nothing changes for a database server used by one cluster.

**Fixed**: `otp --del-user` on a full administrator (1.0.328) switched the account off before it asked - answered no, or run without `--yes` from a script, the account stayed off although "nothing was changed" was said. It is asked first now.

**Fixed (Czech)**: the status line of a mail or SMS token said "zbývá 3 záložních kódů" - the plural is right now; "that was done already - load the page again" on the enrolment page is in Czech.

**Fixed (database agent, MariaDB)**: TLS for MariaDB through the agent (1.0.327) was refused with "Read-only file system" - its new folder was not one the agent's service may write. The service may now, `db-server.sh` makes the folder, and an agent installed before says what to do.

**Fixed**: one failed write of an OS update's progress (a full disk for a moment) stopped every later one - the update was said running for an hour, then failed, and the other nodes were not updated. The VIP's sysctl file is put back with the rest when nginx refuses a change. An upgrade keeps the number and size of otp's log files set on the pages (it put 30 of 200 MB back).

