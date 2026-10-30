# Operations runbook

Step-by-step procedures for running otp, mostly on the command line. Every
procedure here was walked through on a test pair before it was written down.

Commands are run **as root** on the node named in the step. In the examples:

| | |
|---|---|
| first node | `otp1`, `192.0.2.11` |
| second node | `otp2`, `192.0.2.12` |
| VIP address or load balancer | `192.0.2.10`, `otp.example.cz` |
| network | `192.0.2.0/24` |
| VPN concentrators (RADIUS clients) | `198.51.100.1`, `198.51.100.2` |
| operating system | AlmaLinux 9.4 or later (9.x) |
| PostgreSQL | 16, from AlmaLinux AppStream (`postgresql:16` module stream) |

Put your own names and addresses in.

Related documents:
[high-availability.md](high-availability.md) (how the cluster works),
[upgrades.md](upgrades.md), [the-database.md](the-database.md),
[tls-and-vip.md](tls-and-vip.md) (certificates, the VIP address, the
firewall), [load-balancers.md](load-balancers.md) (HAProxy, nginx, Apache,
F5, NetScaler, keepalived/LVS).

---

## Contents

1. [Quick reference](#1-quick-reference)
2. [Fresh installation (one server, SQLite)](#2-fresh-installation-one-server-sqlite)
3. [PostgreSQL 16 on AlmaLinux 9](#3-postgresql-16-on-almalinux-9)
4. [Moving from SQLite to PostgreSQL](#4-moving-from-sqlite-to-postgresql)
5. [Building a cluster of two](#5-building-a-cluster-of-two)
6. [Every-day checks](#6-every-day-checks)
7. [Upgrading otp](#7-upgrading-otp)
8. [Operating-system updates and reboots](#8-operating-system-updates-and-reboots)
9. [A node is down for a while](#9-a-node-is-down-for-a-while)
10. [Split network: both nodes ran alone](#10-split-network-both-nodes-ran-alone)
11. [A node is lost for good](#11-a-node-is-lost-for-good)
12. [A node was away too long ("lost")](#12-a-node-was-away-too-long-lost)
13. [Leaving the cluster: back to one server](#13-leaving-the-cluster-back-to-one-server)
14. [Changing a node's address or name](#14-changing-a-nodes-address-or-name)
15. [Copies of the database, and putting one back](#15-copies-of-the-database-and-putting-one-back)
16. [Back from PostgreSQL to SQLite](#16-back-from-postgresql-to-sqlite)
17. [The key of the tokens](#17-the-key-of-the-tokens)
18. [Lost administrator password](#18-lost-administrator-password)
19. [Certificates and the VIP address](#19-certificates-and-the-web-address)
20. [The picture on the sign-in](#20-the-picture-on-the-sign-in)
21. [Troubleshooting](#21-troubleshooting)

---

## 1. Quick reference

```bash
otp                         # what it is doing (= otp --status)
otp --check                 # every part checked: key, copies, PHP, clients, realms, directories
otp --ha-status             # the nodes, and both directions of replication
otp --ha-compare            # every table counted here and on the other node
otp --web-status            # certificates, TLS settings, where the VIP address is
otp --maintenance status    # in service or not (exit 3 while in maintenance)
otp --maintenance on --why "reason"   /   otp --maintenance off
otp --backup                # a copy of the database now (with the key beside it)
otp --events --limit 50     # what happened
otp --log --rejects         # who was refused, and why
journalctl -u otp -n 100    # the service's own log; also /var/log/otp/otp.log
```

What lives where:

| | |
|---|---|
| program | `/usr/local/lib/otp/` (`otp` command: `/usr/local/bin/otp`) |
| configuration (database address, cluster wiring) | `/etc/otp/config.json` |
| everything else (settings, tokens, accounts, logs) | the database |
| key that seals the tokens | `/var/lib/otp/secrets.key` |
| copies of the database | `/var/lib/otp/backups/` (each with its `.key`) |
| service | `otp.service` (user `otp`) |
| pages | `/var/www/otp/`, nginx `/etc/nginx/conf.d/otp.conf` |

---

## 2. Fresh installation (one server, SQLite)

**Before you start**

- AlmaLinux 9.x, minimal, with network and DNS working, and the clock right:
  `timedatectl` must say `System clock synchronized: yes` (chrony). TOTP codes
  are time based: a clock that is off by more than about 30 s refuses codes.
- A DNS name for the server (`otp1.example.cz`), and later one for the
  cluster's VIP address (`otp.example.cz`).
- A read-only account in Active Directory and LDAPS to the domain
  controllers (with the CA certificate if it is your own CA).
- Firewall openings: see [tls-and-vip.md, "What to open"](tls-and-vip.md#what-to-open-in-the-firewall).

**Steps**

1. Copy the package over and unpack it:

   ```bash
   tar xzf otp-X.Y.Z.tar.gz && cd otp-X.Y.Z
   ```

2. Install. Add `--with-db postgres` if this node will move to PostgreSQL or
   join a cluster later (it only adds the Python driver):

   ```bash
   ./install.sh --server-name otp1.example.cz \
                --radius-from 198.51.100.1/32,198.51.100.2/32 \
                --with-db postgres
   ```

   It installs nginx, PHP-FPM (on a release fixed for php2shell), the
   service, a self-signed certificate, and opens HTTPS and RADIUS in
   firewalld. At the end it prints the first administrator's password.

3. Check it:

   ```bash
   otp --status
   otp --check
   curl -sk https://127.0.0.1/healthz        # "ok otp1"
   ```

4. Sign in at `https://otp1.example.cz/admin/` and change the password.

5. Set it up - on the pages or on the command line:

   ```bash
   otp --add-directory AD --hosts dc1.example.local,dc2.example.local \
       --base DC=example,DC=local --bind-dn otp@example.local --bind-pw - \
       --tls ldaps --ca /root/example-root-ca.pem
   otp --directory-test AD
   otp --add-realm example.cz --suffix example.cz --directory AD --lookup upn \
       --groups 'VPN_USERS' --mode otp
   otp --add-client ASA --address 198.51.100.1 --secret - --realm example.cz
   ```

   `-` asks for the password and the secret, so they never stand on the command
   line where `ps` shows them (or give them in OTP_BIND_PW and OTP_SECRET).

6. Enrol a token for yourself (`otp --enroll you@example.cz`, or on the
   enrolment pages) and test: `otp --radtest you@example.cz 123456`, then
   from the VPN.

7. Your own certificate for the pages: [section 19](#19-certificates-and-the-web-address).

---

## 3. PostgreSQL 16 on AlmaLinux 9

A cluster needs PostgreSQL 16 or later on each node. **The cluster wizard
(`otp --ha-join`) installs and prepares PostgreSQL on the second node by
itself**; these steps are for the first node, or for one server that is
moving to PostgreSQL.

1. Install PostgreSQL 16 from AppStream:

   ```bash
   dnf -y module reset postgresql
   dnf -y module enable postgresql:16
   dnf -y install postgresql-server postgresql-contrib python3-psycopg2
   postgresql-setup --initdb
   systemctl enable --now postgresql
   sudo -u postgres psql -c 'SELECT version()'      # PostgreSQL 16.x
   ```

   On AlmaLinux older than 9.4 there is no `postgresql:16` stream: update the
   system first (`dnf upgrade`), or use the PostgreSQL project's own
   repository (PGDG).

2. Make the database and its account. The database must be UTF-8:

   ```bash
   sudo -u postgres psql <<'SQL'
   CREATE ROLE otp LOGIN PASSWORD 'a-long-random-password';
   CREATE DATABASE otp OWNER otp ENCODING 'UTF8' TEMPLATE template0
          LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8';
   SQL
   ```

3. Let the account sign in with a password from this machine. AlmaLinux's
   `pg_hba.conf` uses `ident` for 127.0.0.1, which refuses it; put a
   password line **above** the existing ones:

   ```bash
   HBA=/var/lib/pgsql/data/pg_hba.conf
   sed -i '0,/^host/s//host    otp    otp    127.0.0.1\/32    scram-sha-256\nhost/' $HBA
   grep -n '^host' $HBA | head -3          # the otp line comes first
   systemctl reload postgresql
   ```

4. Check that the account can sign in:

   ```bash
   PGPASSWORD='a-long-random-password' psql -h 127.0.0.1 -U otp -d otp -c 'SELECT 1'
   ```

5. Optional tuning: *Settings → The database → Tuning* on the pages offers
   values for this machine's memory and disk, and can apply them.

Nothing else is needed for one server. The cluster wizard later switches
`wal_level` to `logical`, makes PostgreSQL listen on the network and lets
the other node in - it asks before restarting PostgreSQL.

---

## 4. Moving from SQLite to PostgreSQL

Either on the pages - *Settings → The database*: *Try it → Set it up → Carry
everything across → Start using it* - or on the command line as below. Both
carry everything: settings, tokens, accounts, logs, events.

1. PostgreSQL ready as in [section 3](#3-postgresql-16-on-almalinux-9), and the
   driver installed (`dnf install python3-psycopg2`, or `./install.sh
   --upgrade --with-db postgres`).

2. A copy of what is in SQLite now, with the service stopped so nothing is
   written meanwhile:

   ```bash
   systemctl stop otp
   otp --backup
   ls -t /var/lib/otp/backups/*.json.gz | head -1     # remember this file
   ```

3. Point otp at PostgreSQL. `--set` with the database keys tries the
   database first and makes the tables; it changes nothing when it cannot
   reach it:

   ```bash
   otp --set db_engine=postgres --set db_host=127.0.0.1 --set db_port=5432 \
       --set db_name=otp --set db_user=otp --set db_password='a-long-random-password'
   ```

4. Put the copy into PostgreSQL:

   ```bash
   otp --restore /var/lib/otp/backups/otp-YYYYMMDD-HHMMSS.json.gz --yes
   ```

5. Start and check:

   ```bash
   systemctl start otp
   otp --status                 # "the database: otp@127.0.0.1:5432/otp (PostgreSQL 16...)"
   otp --tokens | tail -1       # the same number of tokens as before
   otp --radtest you@example.cz 123456
   ```

**Going back** if something is wrong: `systemctl stop otp`, then
`otp --set db_engine=sqlite`, `systemctl start otp`. The SQLite file was not
touched and is used again as it was.

---

## 5. Building a cluster of two

Two nodes, each with its own PostgreSQL, replicating both ways; both answer
RADIUS and the pages. Read [high-availability.md](high-availability.md) once
for how it works.

**Before you start**

- Both nodes run **the same otp version**, and the same AlmaLinux 9.x.
- Clocks synchronised on both (chrony).
- The first node already on PostgreSQL 16 ([sections 3](#3-postgresql-16-on-almalinux-9)
  and [4](#4-moving-from-sqlite-to-postgresql)).
- Between the nodes: TCP 5432 both ways (the wizard opens it in firewalld);
  for the VIP address also VRRP (IP protocol 112). See
  [tls-and-vip.md](tls-and-vip.md#what-to-open-in-the-firewall).
- A copy first: `otp --backup` on the first node.

**On otp1 (the first node)**

```bash
otp --ha-setup --ha-peer 192.0.2.12 --node-name otp1
```

It asks before restarting PostgreSQL (`wal_level = logical`, listening on the
network), lets otp2 in (`pg_hba.conf`, firewalld), publishes every table,
numbers otp1's rows odd, and writes `/root/otp-join-otp1.json` - the bundle
that carries the database account and the key of the tokens, locked with a
passphrase printed **once**. Write the passphrase down.

**On otp2 (the second node)**

```bash
tar xzf otp-X.Y.Z.tar.gz && cd otp-X.Y.Z
./install.sh --server-name otp2.example.cz --with-db postgres \
             --radius-from 198.51.100.1/32,198.51.100.2/32 --yes
scp root@192.0.2.11:/root/otp-join-otp1.json /root/
otp --ha-join /root/otp-join-otp1.json --node-name otp2
```

It installs PostgreSQL 16 if it is missing, prepares it the same way, copies
every row from otp1, sets both directions of replication up, puts the key of
the tokens in place and restarts otp. The accounts of otp2's own fresh
database are gone: sign in with the cluster's accounts.

**Check it, on either node**

```bash
otp --ha-status          # both nodes "ok", "in ... running", "out ... taken"
otp --ha-compare         # "both nodes hold the same rows"
otp --radtest you@example.cz 123456      # on each node
```

On the pages, *Test → On the node* asks either node.

**In front of the nodes** - one of:

- the built-in VIP address for the pages: [section 19](#19-certificates-and-the-web-address);
- your own load balancer: [load-balancers.md](load-balancers.md); then tell
  both nodes its address: `otp --trusted-proxy 192.0.2.5/32` (on each node).

**RADIUS**: give the VPN both nodes as servers of one group (Cisco ASA: two
`aaa-server` hosts with the same key - [load-balancers.md](load-balancers.md#cisco-asa--radius-without-a-balancer)).
The clients' addresses and secrets are entered once and are used by both nodes.

---

## 6. Every-day checks

```bash
otp --ha-status            # both directions running, little or nothing "behind"
otp --ha-compare           # the same rows on both (logs may differ for a second)
otp --web-status           # certificates: how many days left; where the VIP address is
otp --check
```

Things to watch (a monitoring system can ask the same over HTTP):

| What | How | Healthy |
|---|---|---|
| node answers the pages | `GET https://NODE/healthz` | `200 ok NODE` |
| node answers RADIUS | `GET https://NODE/healthz?check=radius` | `200` |
| replication | `GET https://NODE/healthz?check=all` | `200` (`503 degraded: replication ...` when not) |
| certificates | `otp --web-status`, *Settings → Certificates* | more than 21 days left |
| disk | `df -h /var/lib/pgsql /var/lib/otp` | replication keeps up to 16 GB for a node that is away |

---

## 7. Upgrading otp

Keep a copy first: `otp --backup` (on one node of a cluster is enough).

### One server

```bash
tar xzf otp-X.Y.Z.tar.gz && cd otp-X.Y.Z
./install.sh --upgrade
otp --status
```

Or on the pages: *Settings → Upgrades*, send the `.tar.gz`, press *Upgrade*.
The server is out of service for about a minute (with one server nobody can
sign in to the VPN meanwhile).

### A cluster, from the pages (recommended)

*Settings → Upgrades*: send the package, press *Upgrade*. The nodes are done
one at a time, the other node first: each goes into maintenance (RADIUS not
answered, `/healthz` 503, **the VIP address moves to the other node**),
root installs the package, the node comes back, is checked, leaves
maintenance - then the next one. A node does not start until the other one
is alive and in service. Follow it there or with `otp --upgrade-status`.

### A cluster, on the command line

One node at a time, never both at once:

```bash
# on otp2
cd otp-X.Y.Z && ./install.sh --upgrade     # it puts the node in maintenance by itself
otp --ha-status ; otp --check              # both directions running again
# then the same on otp1
```

`install.sh --upgrade` puts the node in maintenance first (and waits 20 s for
the balancer and the VPN, and the VIP address moves away), and back in
service when the new version answers. If it fails half way, it starts the
daemon again and brings the node back into service.

A new version may add columns. Between the first node and the second, the
older node takes nothing from the newer one - it waits in the replication
slot - and catches up as soon as it is upgraded too. Do not leave a cluster
on two versions for long.

### Going back to an older version

Put the older package in with `./install.sh --upgrade` from its folder on the
command line (the pages refuse an older one). If the newer version changed
the database, put back the copy you made before upgrading
([section 15](#15-copies-of-the-database-and-putting-one-back)).

---

## 8. Operating-system updates and reboots

**Minor updates** (`dnf upgrade`, a new kernel, a PostgreSQL 16.x minor
release), one node at a time:

```bash
otp --maintenance on --why "OS updates"     # RADIUS and the VIP address go to the other node
dnf -y upgrade
reboot
# after the reboot:
otp --ha-status                             # both directions running
otp --maintenance off
# then the other node
```

The node that keeps working holds everything the other misses (up to 16 GB)
and hands it over after the reboot.

**A new major release** (AlmaLinux 9 → 10, PostgreSQL 16 → 17): do not upgrade
in place - `pg_upgrade` does not carry the replication slots. Rebuild one node
at a time as in [section 11](#11-a-node-is-lost-for-good) ("reinstalled"),
then the other.

---

## 9. A node is down for a while

A reboot, a network cut, a power failure - hours, or days.

**What happens by itself**

- The other node goes on answering RADIUS and the pages alone. The VPN uses
  the RADIUS server that answers; the VIP address (if on) moves to it within
  a few seconds; a load balancer stops sending to the node that fails `/healthz`.
- Everything written meanwhile on the working node waits for the other in a
  replication slot, up to 16 GB of changes (far more than months of normal use).

**When it is back**

Nothing to do: it catches up by itself. Check:

```bash
otp --ha-status        # "in ... running", "out ... taken", little "behind"
otp --ha-compare       # "both nodes hold the same rows"
```

**Why the node that was away does not overwrite newer data.** Replication
carries *changes*, not the whole database: the node that comes back only
receives what it missed, in order, and it sends only what was written on it
- and while it was down, nothing was. Its old data is never copied over the
working node's.

The exceptions, which need a rebuild of the node that was away
([section 12](#12-a-node-was-away-too-long-lost)):

- it was away so long that the slot was dropped (`otp --ha-status` says
  *lost*);
- **it was restored from a virtual-machine snapshot or a disk backup.** Its
  database is then older than what the other node already confirmed as
  delivered, and the gap is never sent again. **Never revert a node to a
  snapshot while it is in a cluster.** If it happened: right after it starts,
  `otp --maintenance on` and `otp --ha-resync --yes` on it, then
  `otp --maintenance off`;
- both nodes ran and wrote at the same time without seeing each other
  ([section 10](#10-split-network-both-nodes-ran-alone)).

If `otp --ha-compare` still says *DIFFERENT* a minute after the node is back
(and not only in `radius_log`, `otp_log` or `events`, which grow all the
time), rebuild the node that was away.

---

## 10. Split network: both nodes ran alone

The nodes could not reach each other but both kept running and answering:
both wrote, and each wrote things the other never saw. When the network is
back, both streams of changes flow again; a row changed on both sides ends
up as whichever change arrived last on each node - the two may disagree.

1. Decide which node holds the truth - usually the one that answered most
   (the VPN's primary server, or the one holding the VIP address).
2. On **the other** node:

   ```bash
   otp --ha-resync --yes
   ```

   It makes a copy of what it had (in `/var/lib/otp/backups/`), stops otp on
   that node, empties its tables, copies every row from the chosen node, sets
   both directions up afresh and starts otp again.
3. `otp --ha-compare` on either node: the same rows.

Tokens enrolled or changed only on the rebuilt node during the split are in
its safety copy, not in the cluster: enrol them again.

If the VIP address was on both nodes during the split, see
[tls-and-vip.md, "On both nodes at once"](tls-and-vip.md#on-both-nodes-at-once-split-brain).

---

## 11. A node is lost for good

A dead disk, a deleted virtual machine, or a node reinstalled from scratch.
The surviving node goes on alone meanwhile. The same steps work whichever
node was lost - the first or the second. Here otp1 is lost and otp2 survives.

**On otp2 (the survivor): leave the cluster, keeping everything**

```bash
otp --backup
otp --ha-standalone --yes
```

It takes the replication away (and the slot that kept changes for otp1 - so
they stop filling the disk), forgets otp1, and makes `/etc/otp/config.json`
a single server's again. The database, the key, the settings and the tokens
stay. otp restarts once (a few seconds).

**Build the new otp1** - a fresh AlmaLinux 9, the same otp version:

```bash
./install.sh --server-name otp1.example.cz --with-db postgres \
             --radius-from 198.51.100.1/32,198.51.100.2/32 --yes
```

**On otp2: make it the first node of a new pair**

```bash
otp --ha-setup --ha-peer 192.0.2.11 --node-name otp2
```

(The same as [section 5](#5-building-a-cluster-of-two), with the roles
swapped: the survivor is now the first node. Note the new passphrase.)

**On the new otp1: join**

```bash
scp root@192.0.2.12:/root/otp-join-otp2.json /root/
otp --ha-join /root/otp-join-otp2.json --node-name otp1
```

**Check**

```bash
otp --ha-status ; otp --ha-compare
```

While the survivor is alone, the VIP address is released (it is for a
cluster); it comes back by itself once the pair is built again, and the new
node takes part in it. The new node's own certificate and TLS settings are
kept in the database: the new node puts them into its nginx by itself
within seconds of joining. A load balancer needs no change if the address is
the same.

Anything written on otp1 and not yet replicated when it died is lost - in
practice, the last second.

If the new node has a **different name**, the old one stays in the list
until forgotten: `otp --ha-forget otp1` (the standalone step above already
forgot it on the survivor).

---

## 12. A node was away too long ("lost")

`otp --ha-status` says *lost - rebuild the other node*: the node was away so
long that more than 16 GB of changes piled up for it and PostgreSQL dropped
its slot; it can no longer catch up. Rebuild **the node that was away**,
never the one that kept working:

```bash
# on the node that was away
otp --ha-resync --yes
```

Or on its pages: *Settings → High availability → Rebuild this node from the
other…*. Then `otp --ha-compare`.

---

## 13. Leaving the cluster: back to one server

Without losing settings, tokens or accounts. Decide which node stays (here
otp1).

1. Take otp2 out of the VPN's RADIUS group and out of the load balancer.
2. On **otp1**:

   ```bash
   otp --backup
   otp --ha-standalone --yes
   ```

   Replication is taken away on both sides (otp2's subscription too, if otp2
   is reachable), otp2 is forgotten, `/etc/otp/config.json` is a single
   server's again.
3. On **otp2**, either uninstall it (`./install.sh --uninstall`), or make it a
   server of its own: `otp --ha-standalone --yes` - it then goes on with a
   copy of everything as it was at that moment, and the two drift apart.
4. The VIP address belongs to a cluster: on a single server it is released
   by itself (keepalived stops). Point DNS for `otp.example.cz` at otp1's own
   address, and give otp1 the certificate for that name
   ([section 19](#19-certificates-and-the-web-address)). It comes back by
   itself if a cluster is built again.
5. `otp --status` on otp1: one node, its own PostgreSQL. It can stay on
   PostgreSQL, or go back to SQLite ([section 16](#16-back-from-postgresql-to-sqlite)).

The database is left exactly as it was: still numbering rows in steps of
two, still with `wal_level = logical`; both are harmless for one server. A
new cluster can be built from it again at any time ([section 5](#5-building-a-cluster-of-two)).

---

## 14. Changing a node's address or name

**The name** - replication does not use the names, so renaming is safe at any
time, one node at a time:

```bash
otp --set node_name=otp1          # or Settings → High availability → The name of this node
systemctl restart otp
otp --ha-status                   # the new name; the old one is gone from the list
```

On the restart the node carries over everything kept under its old name -
its own settings (*Each node's own settings*), its maintenance, its
certificate and TLS settings, its place in the VIP address - and the old
name leaves the list of nodes. A rename made before 1.0.48 (or by editing
`/etc/otp/config.json` by hand while otp was stopped) is carried over once
with `otp --ha-renamed OLD-NAME` on that node. The machine's own host name
(`hostnamectl`) does not matter to otp once `node_name` is set.

*What to call this installation* (`site_name`, *Settings → About*) is not a
node's name: it is the cluster's, shown at the top of the pages on both
nodes.

**The address** - since 1.0.106 changed in place, on a running cluster: on
the node whose address did **not** change, *Settings → High availability →
The addresses of the two nodes*, or

```bash
otp --ha-readdress --ha-peer NEW-ADDRESS-OF-THE-OTHER-NODE
```

It moves its pg_hba.conf line, its subscription and config.json to the new
address and tells the other node, which puts its own side right by itself.
Both changed, a node that cannot be reached, what is never changed by it,
checking and troubleshooting: [renaming-and-readdressing.md](renaming-and-readdressing.md).

Change the RADIUS server's address on the VPN and the load balancer too.

---

## 15. Copies of the database, and putting one back

The whole subject, every case from a wrong click to a lost cluster, step by
step: [backup-and-recovery.md](backup-and-recovery.md).

- One copy a day at `backup_at` (03:30), the last `backup_keep` (14) kept, in
  `/var/lib/otp/backups/` with the key beside each. In a cluster each node
  makes its own.
- Now: `otp --backup`. On the pages: *Settings → The database → Copies*.
- Copy them off the machine regularly - **with their `.key` files**.

Putting one back replaces everything; a copy of what is replaced is made
first:

```bash
otp --restore /var/lib/otp/backups/otp-YYYYMMDD-HHMMSS.json.gz --yes
```

In a cluster: put it back on **one** node - the rows go over to the other by
replication. A copy sealed with a different key is refused in a cluster (the
other node could not open its tokens). A *dump* (`.pgc`, `.sql.gz`) is
refused while replication runs: switch replication off
([section 13](#13-leaving-the-cluster-back-to-one-server)), restore on one
node, and build the cluster again.

**Copies and dumps - not the same.** Every night at `backup_at` two things are
made. The *copy* (`/var/lib/otp/backups/otp-*.json.gz`, Settings → The database
→ What is in it) is otp's own: portable between SQLite, MariaDB and
PostgreSQL, put back in a cluster too, with the key beside it (or inside, when
downloaded) and, from 1.0.63, the machine's `config.json` in it to read. The
*dump* (`/var/lib/otp/dumps/`, the card "The dumps it keeps") is the engine's
own (`pg_dump`, `mariadb-dump`, the SQLite file): readable by the engine's own
tools without otp, but it goes back only into the same engine, not while
replication runs, and the key is not in it. **Back up with the copies**; the
dumps are a second, independent line.

`otp --backup-info FILE` (or `otp --restore FILE` without `--yes`, or the
question the pages ask before putting one back) says what a copy holds and
where it was made: the node, its database, its place in a cluster and its
`config.json` (the database password left out). That file is only to read -
it is never put back, as it belongs to the machine, not to the data.

A copy holds **everything**: tokens, settings, clients, realms, directories,
accounts, the certificates of the pages and the VIP address with their keys,
the firewall and who may reach which page. Put back on a new machine with its
`.key` file beside it, the new machine is the old one. On the command line a
copy without a full administrator in it can be put back too (an account is
made after it with `otp --add-user NAME --role fulladmin`); the pages refuse
it, so as not to lock you out.

### The configuration alone, as JSON (1.0.62)

Everything except the tokens and the logs - for moving a setup to another
installation, or keeping it under version control:

```bash
otp --export-config /root/otp-config.json                 # without the secrets
otp --export-config /root/otp-config.json --with-secrets  # complete (0600, keep it safe)
otp --import-config /root/otp-config.json --yes           # added to what is here
otp --import-config /root/otp-config.json --yes --replace # exactly the file
```

Secrets kept off the command line, where `ps` would show them (1.0.136):

```bash
OTP_SECRET='…' otp --add-client ASA --address 192.0.2.1 --secret -   # or asked
OTP_VALUE_SMTP_PASSWORD='…' otp --set smtp_password=@env
OTP_RADTEST_PASSWORD='…' otp --radtest novak@example.cz -              # or asked
```

`otp --set` refuses what the pages refuse: `ha_*` (the cluster has its own
steps) and, without `--yes`, `db_*` - a database named that way opens empty at
the next restart; `--yes` only to point at the same data somewhere new.

On the pages (*Settings → Export and import*) *Export with the secrets* gives
a file **locked with a passphrase** made there and shown once (1.0.136) - the
file leaves the machine with every secret in it. Importing it asks for the
passphrase; on the command line `otp --import-config FILE --yes` asks for it
too (or reads `--passphrase-file FILE`, or `OTP_PASSPHRASE`). In it: the settings
(each node's own too), the RADIUS clients, the realms, the directories, the
accounts of the pages, the certificates and keys of the pages and the web
address, the VIP address, who may reach which page, the firewall and the mail
server's authorities. Without `--with-secrets` the client secrets, passwords,
password hashes and private keys stay out: clients new to the other
installation are skipped, new accounts come in switched off, certificates keep
the key that is there. A file of one machine put into a machine of another
name gives that machine its certificate. Your own account is never changed by
an import. With *Exactly the file* (`--replace`) whatever is not in the file
is taken away and settings not in it go back to their defaults.

---

## 16. Back from PostgreSQL to SQLite

For one server (not a cluster):

```bash
systemctl stop otp
otp --backup
otp --set db_engine=sqlite
otp --restore /var/lib/otp/backups/otp-YYYYMMDD-HHMMSS.json.gz --yes   # the copy just made
systemctl start otp
otp --status          # "the database: /var/lib/otp/otp.db (SQLite ...)"
```

---

## 17. The key of the tokens

`/var/lib/otp/secrets.key` seals every token's key, the clients' secrets and
the directories' passwords. Without it a copy of the database is useless.

- It is the same file on both nodes of a cluster (carried by the join bundle).
- Every copy in `/var/lib/otp/backups/` has it beside it.
- Keep one copy of it off the machines, somewhere safe, apart from the
  database copies.

If it is lost on one node of a cluster: `otp --ha-resync --yes` does not
bring it back - make a bundle on the other node (`otp --ha-bundle
/root/b.json`) and `otp --ha-join /root/b.json` on this one.

---

## 18. Lost administrator password

```bash
otp --users
otp --passwd admin              # asks for the new one; ends that account's sign-ins
otp --set-role someone --role fulladmin
```

**"too many wrong passwords from ADDRESS: try again in N min"** - the address
(or the name) is locked out for a while: *Settings → Accounts → Locked out*
lists every address and name with wrong attempts still counted, on every node -
how many of how many, which names were tried from an address, how long the
lockout still runs - and clears one (*Clear*) or all of them (*Clear them all*),
written into Events. The counts live in each node's memory, so
`systemctl restart otp` forgets them as well. How many tries and how long the
wait are: *Settings → Accounts* (`login_tries`, `login_wait_min`) and *The
enrolment pages* (`portal_tries`, `portal_wait_min`). Behind a load balancer
or proxy that hides the people's addresses, everybody shares one - see
load-balancers.md.

---

## 19. Certificates and the VIP address

Everything here is also on the pages: certificates and TLS in *Settings →
Certificates and TLS*, the VIP address in *Settings → High availability →
The VIP address*. Details, and what to open in the firewall: [tls-and-vip.md](tls-and-vip.md).

**A node's own certificate**

```bash
otp --tls-import /root/otp1.pfx --tls-for otp1          # password in OTP_TLS_PASSWORD
otp --tls-import /root/otp1.crt /root/otp1.key /root/chain.pem --tls-for otp1
otp --tls-preset intermediate --tls-dh ffdhe2048 --tls-hsts 31536000 --tls-for otp1
otp --web-status
```

**The VIP address** - in a cluster only:

```bash
otp --vip-set 192.0.2.10/24 --vip-fqdn otp.example.cz --vip-vrid 51
otp --tls-import /root/otp.pfx --tls-for vip             # its own certificate (optional)
otp --vip on
otp --web-status                       # which node holds it
otp --vip-move otp2                    # by hand, to the other node
otp --vip off                          # off: keepalived stops on both
```

It moves by itself when the node holding it goes into maintenance, is
upgraded or rebuilt, stops answering its own `/healthz`, stops listening for
RADIUS, or is gone; and comes back to the node it is meant to be on once
that is well.

---

## 20. The picture on the sign-in

*Settings → The enrolment pages → The picture on the sign-in* has two tabs:
**The enrolment pages** and **The administration**. Each sign-in has its own
picture, picked with a preview (full admin only). A press on one, an upload,
*Back to the default* and *Take my own picture away* only mark the change;
it is made with *Save the changes* at the bottom, as every other setting:

- the drawings that come with otp, in the pages' own colours (they follow
  the light and the dark look): the phone, the check and the way in (the
  enrolment pages' default); RADIUS, the code and Active Directory (the
  administration's default); the authenticator app with its codes; how a
  code is made (the key and the time - TOTP); the six digits with the 30
  seconds running down; the name, the password and the code; the VPN asking
  for the code; the codes in time, a step either side; recovery codes for
  when the phone is gone; a 30-second clock; two keys for one door; the QR
  code and the app; a padlock with six digits;
- *No picture* - only the sign-in;
- *A picture of your own* - a logo: PNG, JPEG, GIF, WebP or SVG, at most
  512 KB, one for each sign-in. An SVG with a script, an event handler or a
  link out is turned away; the picture is served from `/?api=logo`
  (`&slot=admin` for the administration's) with a policy that runs nothing.

*Back to the default* puts that sign-in's own default back at once. A picture
of your own stays kept when another one is picked - to be picked again
without uploading it - until *Take my own picture away*.

It is kept in the database (`meta`: `portal:art`, `portal:logo`,
`admin:art`, `admin:logo`), so both nodes of a cluster show the same
pictures whichever was changed, and they are in every copy of the database
and in the exported configuration (`art`, `logo`, `admin_art`, `admin_logo`).

---

## 21. Troubleshooting

| Symptom | Look at | Usual cause, and the fix |
|---|---|---|
| `in <- ... NOT RUNNING` | `journalctl -u postgresql`, `/var/lib/pgsql/data/log/` | the other node down, TCP 5432 blocked, `pg_hba.conf`; it resumes by itself when fixed |
| `out -> ... NOT TAKEN` | the other node | the other node down or paused (`otp --ha-resume`) |
| `lost - rebuild the other node` | | [section 12](#12-a-node-was-away-too-long-lost) |
| `--ha-compare` DIFFERENT for minutes | `otp --ha-status` | the node that was away: `otp --ha-resync --yes` on it |
| every code refused on one node | `otp --check` ("the key...") | the key differs: re-join the node with a fresh bundle |
| codes refused for everybody | `timedatectl` | the clock is off: chrony |
| VPN times out | `otp --log`, `otp --events` | the client's address or secret; the firewall (UDP 1812) |
| pages 502 | `systemctl status otp php-fpm nginx` | the daemon or PHP-FPM not running |
| VIP address on no node | `otp --web-status` | both nodes unhealthy, or keepalived failed: the reason is shown per node |
| VIP address on both | [tls-and-vip.md](tls-and-vip.md#on-both-nodes-at-once-split-brain) | VRRP blocked between the nodes |
| upgrade from the pages stuck | `otp --upgrade-status`, `/var/lib/otp/upgrade/last.log`, `journalctl -u otp-upgrade` | `otp --upgrade-cancel`; a node that began is finished and brought back |
| disk filling on one node | `otp --ha-status` ("behind") | the other node is away for long: bring it back, or `otp --ha-standalone --yes` if it is gone for good |
