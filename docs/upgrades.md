# Upgrades and maintenance

Two ways to put in a new version. Both stay: use whichever suits you.

| | Command line | The pages |
|---|---|---|
| Where | on each node, as root | *Settings → Upgrades*, as a full administrator |
| How | `./install.sh --upgrade` | send the `.tar.gz`, press *Upgrade* |
| One server | out of service for a minute or two | the same |
| A cluster | node by node, by hand | every node in turn, by itself |

## From any version

Any older version - back to the first `opt` 1.0.0 - is upgraded straight to
this one, on SQLite, MariaDB and PostgreSQL: the tables are brought up to date
when the new version starts (columns added, nothing taken away), `opt` is
renamed to `otp` by install.sh, and copies made by any older version go back
into this one. Tested from every release 1.0.0 - 1.0.61 on SQLite and from
releases across that range on MariaDB and PostgreSQL (1.0.62). In a cluster the nodes are upgraded one after the other; while
one is new and the other old, what the new one writes into a table that gained
a column waits in its replication until the other is upgraded too, and then
goes over - nothing is lost.

## Maintenance

A node **in maintenance** answers no RADIUS request and its `/healthz` says
`503 maintenance`, so the VPN and the load balancer take it for down and use
the other node. Its pages go on working, so it can be looked at and brought
back.

```
otp --maintenance on --why "new disk"     # out of service
otp --maintenance status                  # which (exit 3 while in maintenance)
otp --maintenance off                     # back in service
otp --maintenance on --node otp2          # another node of the cluster
```

With the web address on ([tls-and-vip.md](tls-and-vip.md)), a node in
maintenance also gives the address up to the other node.

On the pages: *Settings → Upgrades → The nodes*, or the *Maintenance and
upgrades* card on the Overview. With a single server, maintenance means
nobody can sign in to the VPN.

## On the command line

```
tar xzf otp-X.Y.Z.tar.gz && cd otp-X.Y.Z
sudo ./install.sh --upgrade
```

From 1.0.37 on, `install.sh --upgrade` takes the node out of service before it
touches anything (and waits 20 s in a cluster, for the balancer and the VPN to
notice), and puts it back once the new version answers. A node that was in
maintenance already stays in it. In a cluster, upgrade one node, check it
(`otp --check`, `otp --ha-status`), then the other.

## From the pages

*Settings → Upgrades*:

1. **Send the package** - the `otp-X.Y.Z.tar.gz` as released. It is checked at
   once (below) and kept in the database, so every node of a cluster has it.
2. **Upgrade.** One server: it is put in and restarted. A cluster: one node at
   a time - the others first, the node the page came from last:
   1. the node goes into maintenance, and waits 20 s for the balancer;
   2. the package is handed to root (see below), which runs its
      `install.sh --upgrade`;
   3. the node comes back as the new version, checks that its database opens
      and RADIUS listens, reads the list of replicated tables again, and leaves
      maintenance;
   4. only then the next node begins.

   A node that fails stops the upgrade there, goes back into service as it
   runs, and the page shows what `install.sh` said. *Stop it* leaves the nodes
   not yet begun as they are.

`otp --upgrade-status` shows the same on the command line, and
`otp --upgrade-cancel` stops it.

### What makes it safe

The service runs as `otp`, which may not write a byte of the program. The
pages therefore never install anything themselves:

- The node lays the package and a request down in `/var/lib/otp/upgrade/`.
  systemd sees the request (`otp-upgrade.path`) and starts
  `otp-upgrade.service`, which runs `/usr/local/lib/otp/otp_upgrade.py` **as
  root**. It is the only thing that unit can do.
- Root copies the package to a folder of its own before reading it, so it
  cannot be changed under the check, and checks it again from the start:
  - **signed**: `MANIFEST` lists the SHA-256 of every file and `MANIFEST.sig`
    is its Ed25519 signature, by one of the keys in
    `/usr/local/lib/otp/release-keys/` - root's alone, put there only by
    `install.sh`;
  - every file is the one signed, and nothing else is in it: no link, no
    device, no path outside its one folder;
  - it is not older than what is installed (going back is done on the command
    line).
- Then it runs the package's own `install.sh --upgrade --yes`, exactly as
  somebody would by hand, and writes what it said to
  `/var/lib/otp/upgrade/last.log`.

A package that was changed, or signed by a key the server does not know, is
refused - put it in on the command line if you trust it. The first version
with this (1.0.37) has to be put in on the command line once: that installs the
units and the key.

## A cluster: what goes where

Settings, clients, realms, directories, tokens and accounts are the cluster's
and replicate. A few settings belong to one machine and each node has its own
(*Settings → High availability → Each node's own settings*): the address RADIUS
listens on, the port the pages ask the daemon on, the name it greets mail
servers with, the name isemon files it under, and the debug switches. The
database address and the cluster's wiring are in each node's
`/etc/otp/config.json` and never replicate. Maintenance, heartbeats and the
upgrade's progress are kept per node.

A new version may add a column. Between the upgrade of the first node and the
second, the older one takes nothing from the newer (the change waits in the
newer one's replication slot) and catches up as soon as it is upgraded - which
is why the upgrade goes straight on to the next node.

## The operating system

- **Ordinary updates** (`dnf upgrade`, a new kernel, a minor PostgreSQL):
  node by node - `otp --maintenance on`, update, reboot,
  `otp --ha-status` shows both directions running, `otp --maintenance off`,
  then the other node. The live node keeps what the other misses (up to 16 GB).
- **A new major release** (AlmaLinux 9 → 10, PostgreSQL 16 → 17): do not
  upgrade in place - `pg_upgrade` does not carry the replication slots. Make a
  bundle on the live node (`otp --ha-bundle FILE`), reinstall the other node
  from scratch, `otp --ha-join FILE` on it; then the same the other way round.
