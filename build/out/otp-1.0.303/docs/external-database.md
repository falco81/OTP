# The database on a server of its own (otp-db-agent)

Since 1.0.289 otp can look after a PostgreSQL or MariaDB that runs on **a server of its own**
the way it looks after one on its own machine. A small agent, **otp-db-agent**, runs on that
server and does the closed set of things otp's root helper does on a node. Those are the
database's certificate from otp's own authority and its renewal, `pg_hba.conf`, the server's
own settings and their restart, and opening the database's port in its firewall.

Without an agent nothing changes. A node with no file `/var/lib/otp/db-agent/agent.json` takes
every path it always took: nothing new runs, is asked, said or drawn. A database elsewhere with
no agent stays its administrator's, and otp only connects to it.

**Layout A**: one otp node, or two that share one database, and its database server.
**Layout B** (1.0.290): high availability with each node's database on a server of its own,
the two servers replicating (see *High availability* below). Moving onto the agent's server and off it
(1.0.291, *Moving* below). This machine's database shown as a database server (1.0.292,
*This machine's database* below). The database servers' rows in the header's meter (1.0.293,
*Monitoring* below).

```
   otp1 (192.0.2.11)                                    db1 (192.0.2.21)
  ┌───────────────────────┐   HTTPS 9443, mutual TLS,   ┌──────────────────────────────┐
  │ otp daemon            │   every request signed      │ otp-db-agent                 │
  │  └ db-agent client ───┼────────────────────────────►│  network side (otp-db-agent  │
  │    agent.json, pins,  │   (the agent's certificate  │   account, holds no key)     │
  │    client.crt/key,    │    pinned, the node's       │   └ socketpair ─► root side  │
  │    sign.key           │    certificate by its hash) │       closed set, audit log  │
  │                       │   PostgreSQL 5432 /         │                              │
  │ the database client ──┼────────────────────────────►│ PostgreSQL 16 / MariaDB      │
  └───────────────────────┘   MariaDB 3306, TLS         │  cert from otp's authority   │
                              verify-full               └──────────────────────────────┘
```

## Installing the database server

Copy otp's installation folder, of the same version, to the database server. Then, as root:

```
./install.sh --db-server postgres --otp-node 192.0.2.11     # or: --db-server mariadb
```

- **postgres** installs and initialises PostgreSQL 16 and starts it. On EL 9/10 it comes from
  AppStream's `postgresql:16` module, or else from PGDG; on Debian and Ubuntu from the
  distribution's own packages, or else from PGDG. It listens on the network, and
  `wal_level = logical` is set. The database `otp` and its account `otp` are made, and each
  `--otp-node` is let in through `pg_hba.conf` (scram-sha-256) and firewalld.
- **mariadb** installs the distribution's MariaDB and secures it: no anonymous accounts, no
  test database, root only on this machine. The database and the account are made for the
  nodes given.
- Both install **otp-db-agent** (`/usr/local/lib/otp-db-agent`, its unit `otp-db-agent.service`,
  TCP 9443) and print **a join code** at the end.
- `--db-agent` installs the agent alone, for a server installed already. Run again, it upgrades
  the agent: its configuration, its keys and the nodes joined are kept, and **no join code is
  printed**. Only a new install, or `--new-code`, prints one.
- `--db-password-file FILE` gives the account's password (the first line of FILE). Without it a
  password is made and shown once. `--db-password PASS` works too, but every account on the
  machine sees a command line.
- `--db-name`, `--db-user` and `--db-agent-port` change the defaults.
- `--dry-run` says what it would do, passwords masked.
- `--db-agent --uninstall` takes the agent away. The database and its data stay.

Without `--otp-node`, firewalld drops every node until it is let in. install.sh prints the exact
`firewall-cmd` lines. A node that joins asks the agent to open the database's port, and the
agent's own, to it.

A new code, any time (each code runs out in an hour and is used once):

```
python3 -I /usr/local/lib/otp-db-agent/otp_db_agent.py --new-code
```

## Joining the agent

On the otp node, as root:

```
otp --db-agent-join -
```

Paste the code on standard input, or put it in `OTP_DB_AGENT_CODE`. A code given on the
command line is refused: every account on the machine would see it in `ps`, and the shell keeps
it. In the pages: *Settings → The database → Connect a database server…* (or the link in the
first step of *Move to another database*) is a wizard. It shows the commands for the database
server, then reads the code as it is pasted (the code's secret is never shown) and connects.

The join:

1. Reaches the agent at the address in the code (or `--db-agent HOST[:PORT]`). The agent's
   certificate is checked against the fingerprint in the code, before anything is sent.
2. Fetches the agent's own enrolment key and checks it against the code's `k`.
3. Seals the code's secret, a new signing key of this node, and the fingerprint of a new client
   certificate from otp's own authority to that key (RSA-OAEP, SHA-256). The agent's network
   side passes them on and never sees them.
4. Writes `agent.json`, `client.crt/key`, `client-ca.pem` and `sign.key` into
   `/var/lib/otp/db-agent` (0600, the daemon's). None of them is in config.json or the database,
   so nothing of it travels with a backup or to the other node.

`--db-agent-db-host HOST` gives the database's address as this node reaches it, when it is not
the agent's.

The agent is **asked only while this node's database is the one on its server**: the same
engine, the same host (the agent's or `db_host`) and the same port. A node that joined but
still uses a database on its own machine is looked after as before, and the card says to move
the database (*Move it onto the database server…*, which opens the move wizard filled in).

One agent per node: joining another one replaces it. The old agent is told that this node is
leaving it (`agent.json.replaced` is kept).

## What goes through the agent

| On this machine (the root helper)                 | With the database on the agent's server     |
|---------------------------------------------------|---------------------------------------------|
| Database → TLS: the server's certificate, ssl on  | `pgtls` (server, hba, server_off …)         |
| The server's own settings: the machine's size     | the agent's `status` (RAM, CPUs)            |
| …and their restart                                | `pg_restart` (the agent waits for it)       |
| PostgreSQL running? installed?                    | `status` - and "install it there" said      |
| a node at a new address (the network job)         | `pg_allow` / `my_allow`, `fw_allow` - first |
| MariaDB's certificate                             | `my_tls` (`otp --db-agent-mariadb-tls`)     |

Database → TLS treats the agent's server as it treats a PostgreSQL on this machine: otp's
authority, `verify-full`, and the certificate renewed 45 days before it ends. MariaDB's
certificate comes from *Turn TLS on* on the card, or `otp --db-agent-mariadb-tls`. The first
time MariaDB restarts; after that a `FLUSH SSL` takes a renewed certificate. MariaDB asked for
TLS never goes on in the clear: a connection asking for `require` / `verify-*` to a MariaDB that
does not offer TLS is refused (PyMySQL went on unencrypted before).

## The card

*Settings → The database → Database server* shows:

- where the database is, and the agent's state;
- a tile for the server, with the engine and version, whether it runs, TLS, connections, the
  data's disk, RAM, processors and load, uptime, both certificates' ends, and when it was last
  heard from;
- notes: nodes the agent has not heard from for 30 days, *Busy with* an operation for a node,
  and an agent whose program is not the one this otp ships;
- **Look now**, **Renew the certificates**, **Restart the database…**, *Turn TLS on* (MariaDB)
  and **Forget the agent…**.

A database server elsewhere with no agent gets the same card with *Connect a database
server…*. The cards whose work reaches the server too carry a pill naming it:
*Encryption to the database server*, *The server's own settings*, and Firewall. Database → TLS
also has a row for it.

## The command line

```
otp --db-agent-join -           join (the code on standard input)
otp --db-agent-status [--json]  the agent, its server, versions, certificates, nodes
otp --db-agent-renew            the agent's certificate and this node's, renewed now
otp --db-agent-restart          the database server started again by its agent
otp --db-agent-mariadb-tls      MariaDB given a certificate from otp's authority
otp --db-agent-forget --yes     back to db_admin local; the agent told this node leaves it
otp --db-agent-leave --yes      the same, before this node is taken away for good
```

Each opens the database that config.json names (never the defaults' file). `otp --status` has a
line for the database server.

## Security

- **Two processes.** Root binds the port and starts the side that faces the network as a new
  program (never a `fork()` of root's memory). It runs as the account `otp-db-agent`, never
  root and never nobody. It terminates TLS and rate-limits, and hands each request, as it
  came, to root over a socket pair. Root works out the client's fingerprint from its
  certificate, checks everything, runs the operation, signs the answer and writes the audit
  log, refusals included.
- **Both ends pinned.** The node pins the agent's self-made certificate by its SHA-256, from the
  code on. The agent lets a node in by its own client certificate's SHA-256, each node its own.
- **Every request signed** (HMAC-SHA256, a key per node, the time within ±120 s, a nonce never
  seen - also across a restart, kept in `nonces.json`), **and every answer**.
- **A closed set.** status, load, pgtls, pg_prepare, pg_allow, my_allow, pg_publication,
  pg_restart, pg_reload, pglog, dbmake, my_tls, my_restart and fw_allow, plus the agent's own
  agent_renew, trust, clients and leave. Every argument is checked against the one shape it may
  have. There is no shell and no file named by a request, and SQL runs only as postgres, with
  statements on standard input. Anything else is refused: *… is not something this agent does*.
- **One database server, one cluster's TLS.** The node that put the server's certificate in owns
  it, by the authority that signed its client certificate (never by what it lists). A node of
  another authority is refused, and a node takes only itself off the list.
- **Join codes.** A code is used once and runs out in an hour. Wrong codes are counted per
  address, and per code only with its id right, so a stranger burns no code. A token is given
  per begin.
- **Secrets never on a command line**: the join code on standard input, passwords on psql's or
  mariadb's standard input, with `log_statement = none` / `sql_log_off`, and masked by
  `--dry-run`.
- The unit is hardened: `ProtectSystem=strict` with the folders it writes, `PrivateDevices`,
  `RestrictAddressFamilies`, a `CapabilityBoundingSet`, and `KillMode=mixed` so a stop waits up
  to 300 s for the operation under way.

## Certificates

- **The agent's own.** It is made on its server. 60 days before it ends the agent makes the next
  one and announces it in the signed answer of `status`. Each node pins it beside the one in
  use, and the agent switches once every node heard from in the last 30 days took it in, or 7
  days before the end at the latest.
- **The node's client certificate** comes from otp's authority and is renewed by the node 45
  days before it ends. The agent is told about it first, with the authorities that issued it.
- **The database's** comes from otp's authority through Database → TLS, or *Turn TLS on* for
  MariaDB, and is renewed 45 days before it ends.

## Monitoring

| Alert | When |
|---|---|
| `dbagent:NODE` | the node's agent has not answered for 90 s |
| `dbserver:NODE` | the agent answers, but its database does not run |
| `dbagent:cert:NODE` | the agent's certificate ends within 14 days and the agent did not renew it by itself |
| `dbagent:client:NODE` | the node's client certificate ends within 14 days |
| `dbagent:version:NODE` | the agent's program is not the one this otp ships (*older*: `./install.sh --db-agent` there; *newer*: upgrade otp) |

All of them are said in Czech too. Prometheus gets `otp_db_agent_up` and `otp_db_server_up`.

**The meter in the header** (Settings → About → the performance meter, 1.0.293): with an agent,
a row for each database server after the nodes, in the look chosen, named with a small cylinder -
the server's own short name (`db1`), or `db·NODE` where that is not one. Its numbers are the
agent's (`load`), read through it every 2 s while a page looks; the other node's server from
the row its node writes. Pointed at, its panel: the graph of what was pointed at, **The
database** (the version, running for how long, the connections, *Waiting to go over
(replication)*, the size of otp's database, its data's disk, TLS) and **The machine** in numbers.
An agent that does not answer: the row dimmed and its name red, its panel says so, and the meter
does not wait for it - it is asked again 10 s later. Without an agent the meter is as before.

The agent's version is its program. The node compares the SHA-256 of `otp_db_agent.py`,
`otp_pg_ops.py` and `otp_web.py` with the files it ships, so a release that did not change the
agent says nothing.

## High availability (layout B)

PostgreSQL 16 or later only. otp1 uses db1, otp2 uses db2, and db1 and db2 replicate both ways
(logical replication, as two nodes with a PostgreSQL each). The VIP address, keepalived, the
leader, the split handling and the clocks stay the **otp nodes'** own. The link between the
two database servers is encrypted with certificates from otp's authority, put in by their agents.

```
                    VRRP VIP 192.0.2.10 (keepalived - the nodes' own)
             ┌────────────────────────────────────────────────────┐
        ┌────┴────┐  heartbeat, leader, split handling, clocks ┌───┴─────┐
        │ otp1    │◄──────────────────────────────────────────►│ otp2    │
        │ .11     │       (--ha-peer-node: the other otp node) │ .12     │
        └──┬───┬──┘                                            └──┬───┬──┘
  agent 9443│   │5432 TLS verify-full              agent 9443 │   │5432 TLS verify-full
           ▼   ▼                                                ▼   ▼
        ┌─────────┐   logical replication, both ways      ┌─────────┐
        │ db1 .21 │◄─────────────────────────────────────►│ db2 .22 │
        │ PG 16 + │   hostssl, verify-full                │ PG 16 + │
        │ agent   │   (--ha-peer: the other DATABASE)     │ agent   │
        └─────────┘                                       └─────────┘
```

1. On each database server: `./install.sh --db-server postgres --otp-node OTP1 --otp-node OTP2`.
2. otp1: `otp --db-agent-join -` (db1's code), then its database moved onto db1.
3. otp1: `otp --ha-setup --ha-peer DB2 --ha-peer-node OTP2 --node-name otp1`. **`--ha-peer` is
   the other database server, `--ha-peer-node` the other otp node.** db1's agent prepares db1
   (wal_level, listening, pg_hba.conf for db2, otp2 and otp1), restarts it, publishes the tables
   and opens its firewall. `ha_address` is db1; `agent.json` keeps `peer_node` (otp2) and
   `node_address` (otp1's own address toward otp2). The bundle carries `peer.node`.
4. otp2: `otp --db-agent-join -` (db2's code), then `otp --ha-join BUNDLE --node-name otp2`: db2
   is prepared by its agent, every row is copied from db1, both subscriptions are made,
   config.json gets `db_host` = db2, and db2's agent is told the cluster's authorities.
5. On either node: `otp --ha-tls-repair` (or *High availability → Repair*): each node issues its
   server's certificate, its agent puts it in - verify-full, hostssl.

*High availability → Making it two* shows these commands filled in, on a node whose database is
on its agent's server.

What is the nodes' own takes the other **otp node** (`peer_node`), never the other database
server: the clocks' peers, the addresses the firewall always lets in, keepalived's other node
and its own address (`node_address`), the split's look at the other machine. The other database
server's clock is said as *the database server of otp2* and never corrects the heartbeats.

Rebuild (`otp --ha-resync`), pause and resume, renewals and the authority's roll work as with a
PostgreSQL on each node; the root parts go through the agents. A node's own address changed on
*Settings → Network*: its agent lets the new address into its server before anything changes,
and the other node's agent does once the replicated row comes over.

Without `--ha-peer-node` and without an agent, `--ha-setup` is what it always was: `--ha-peer`
is the other node. `--ha-peer-node` on a node whose database is not on its agent's server is
refused. MariaDB does not replicate; the shared layout (`--ha-shared`) is unchanged - that
server stays its administrator's.

## Moving

**A node has one database agent, and it is the agent of the server its database is on.**

| From → to | What to do | `db_admin` afterwards |
|---|---|---|
| this machine / SQLite → an agent's server | connect its agent (*Connect a database server…*), then *Move the database onto it…* | `agent:` that agent |
| agent A's server → agent B's server | connect agent B first - it takes A's place (A is told this node leaves it); then move | `agent:` B |
| an agent's server → this machine, SQLite, or a server no agent looks after | move | `local` - the agent let go by the move |
| a node of a cluster | refused: take the cluster apart first | unchanged |

- **Make it for me**: on the agent's server, step *Reaching it* of the wizard offers *Make the
  database and the account for me* - the agent makes the database, the account (its password
  made up when none is typed, shown once), lets this node in (`pg_hba.conf`, or `'user'@'node'`
  on MariaDB) and opens its firewall. PostgreSQL started again by its agent when it must listen
  on its network addresses first (never while this node's own database runs on it). Elsewhere
  an administrator of that server is asked, as before.
- **The encryption is the server's own**: `db_tls` / `db_tls_ca` of the server in use are not
  carried to another server (another engine, address or port) - turned on there afterwards,
  *Database → TLS*.
- **What described the old server is left behind**: the moved database does not get the rows
  `dbtls:server:NODE`, `dbagent:node:NODE`, `load:db:NODE`; the new server's are written as they
  come. The database left behind is not touched.
- **Off the agent's server**: once `config.json` is switched the agent is let go
  (`agent.json` → `agent.json.forgotten`, as `--db-agent-forget`) and told this node leaves
  it; the wizard's last step says so. Moving back means connecting it again (a new code).
- **High availability**: refused on a node of a cluster; with each node's database on a server
  of its own the refusal says so, with the way out (switch the replication off,
  `otp --ha-standalone --yes` on both nodes, move, build the cluster again). Connecting another
  agent in place of the one the cluster's database is on is refused too.
- Without an agent the wizard is as it always was.

## This machine's database

No agent is needed to see a database that runs on otp's own machine. *Settings → The database →
Show this machine's database as a database server* (`db_local_card`, off by default, offered for
PostgreSQL and MariaDB only) draws the card *Database server* for it, above *Encryption to the
database server*.

| | |
|---|---|
| Who looks | Each node whose database is on its own machine (localhost, 127.0.0.1, ::1 or a socket) and has no agent - every 30 s (`OTP_DBLOCAL_EVERY`), with its own connection to the database and `/proc`. |
| What it reads | The engine's version, whether it runs and since when, TLS, the connections, the disk of its data (`statvfs` of its folder, where otp's account may read its name, else the usual place), the memory, the processors and the load, the machine's uptime, the end of the certificate otp gave PostgreSQL (Encryption to the database server, or the link between the databases). |
| Where it goes | This node's row `dblocal:node:NODE` in `meta`, without a password. The other node of a cluster reads it with every node's rows; rows of nodes not in the cluster, or older than a week, are not shown. |
| The page | A tile per node (this node's first); another node silent for more than 2 minutes in amber, a certificate ending within 14 days in red. *Look now*; *Renew the certificate* when otp gave PostgreSQL its certificate; *Restart the database…* while PostgreSQL's settings wait for a restart and install.sh let otp restart it. `GET /api/db-agent` has `local: [...]`. |
| Not there | The agent's rows, join codes, *Forget*, the dots on other cards, rows in the meter or on High availability, alerts. With an agent the card is the agent's. |
| Off | Nothing read, written or shown; `GET /api/db-agent` without `local`. Switching it off takes this node's row away (also at a start with the setting off). A move to another server leaves the row behind. |

## Leaving

- `otp --db-agent-forget --yes`, or *Forget the agent…*: the agent takes this node off its list
  (`leave`), and the node goes back to `db_admin local` (`agent.json.forgotten` is kept). The
  database is not touched. An agent that does not answer keeps the node's certificate until
  `otp_db_agent.py --forget NODE` is run on its server.
- In layout B the agent is not forgotten while the replication runs through it: `--db-agent-forget`,
  `--db-agent-leave` and the card refuse it - take the cluster apart first
  (`otp --ha-standalone`).
- `install.sh --uninstall` on a node keeps the join (it keeps `/var/lib/otp`). A node going away
  for good runs `otp --db-agent-leave --yes` first.
- On the database server: `otp_db_agent.py --status` lists the nodes, and those not heard from
  for 30 days. `otp_db_agent.py --forget NODE` takes one away (then
  `systemctl restart otp-db-agent`).

## Upgrading

Upgrade the agents and otp together: `./install.sh --db-agent` from the new otp's folder on each
database server. The agent restarts, and its nodes stay joined. Until it is upgraded, the card,
`--status` and the alert say that the agent is another version.

## Files

| Where | What |
|---|---|
| `/usr/local/lib/otp-db-agent/` | `otp_db_agent.py`, `otp_pg_ops.py`, `otp_web.py`, `release` |
| `/etc/otp-db-agent/agent.json` | the agent's configuration (root's, 0600); its certificate, `enroll.key`, `clients.json`, `join.json` beside it |
| `/var/lib/otp-db-agent/` | `nonces.json`, `server-cert.json` (the server certificate's owner) |
| `/var/log/otp-db-agent/audit.log` | every request and refusal - never a key, a signature or a code |
| `/var/lib/otp/db-agent/` (the node) | `agent.json`, `client.crt/key`, `client-ca.pem`, `sign.key` |
