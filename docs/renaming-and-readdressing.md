# Renaming a node and changing its address

What otp needs when a server gets a new name or a new IP address - on one
server and in a cluster of two - and how to put it right from the pages or
from the command line. Everything here works on a running installation; the
pair is not taken apart and built again (that was the only way before 1.0.106).

| You changed | One server | A cluster of two |
|---|---|---|
| The machine's host name (`hostnamectl`) | nothing for otp | nothing for otp |
| otp's name of the node (`node_name`) | [rename it](#1-renaming-a-node) | [rename it](#1-renaming-a-node), one node at a time |
| An IP address | [the outside only](#3-one-server-a-new-address) | [tell the cluster](#2-a-node-got-a-new-address) |
| The name people type in the browser | [certificate](#4-certificates-of-the-pages) | [certificate](#4-certificates-of-the-pages) |

---

## 1. Renaming a node

otp calls each node by its own name (`node_name` in `/etc/otp/config.json`;
when it is not set, the machine's short host name at the time it was
installed). Replication does not use the names, so a node can be renamed at
any time.

**On the pages:** *Settings → High availability → Each node's own settings →
The name of this node*, then restart the service on that node.

**On the command line, as root, on the node itself:**

```bash
otp --set node_name=otp3
systemctl restart otp
otp --ha-status          # the new name; the old one is gone from the list
```

On the restart the node carries over everything kept under its old name:

- its own settings (the values marked *its own*);
- its maintenance, if it was in maintenance;
- its certificate and TLS settings of the pages;
- its place in the web address (preferred node, interface);
- the encrypted link between the databases - its progress is started again
  under the new name and its database certificate is renewed by itself.

The old name leaves the list of nodes. If `config.json` was edited by hand
while otp was stopped (or the rename was made before 1.0.48), carry it over
once with:

```bash
otp --ha-renamed OLD-NAME
```

The machine's own host name (`hostnamectl set-hostname`) does not matter to
otp once `node_name` is set. *What to call this installation* (`site_name`,
*Settings → About*) is the cluster's name at the top of the pages, not a
node's.

---

## 2. A node got a new address

Each node keeps the other node's address in three places, and its own in one:

| Where | What |
|---|---|
| `/etc/otp/config.json` | `ha_peer` - the other node; `ha_address` - this node, as the other reaches it |
| its PostgreSQL subscription | the connection to the other node's PostgreSQL |
| its `pg_hba.conf` | the line that lets the other node into the database (`host` or, once the link is encrypted, `hostssl`) |

When an address changes, replication stops: one node no longer finds the
other, and the other's `pg_hba.conf` no longer lets it in. Both nodes go on
answering RADIUS and the pages from their own database; what is written
meanwhile waits (up to 16 GB) and goes over once the addresses are right.

### Where to do it: on the node whose address did NOT change

That node can still reach the other at its new address (its own line in the
other's `pg_hba.conf` still matches), so it puts its own side right **and
tells the other node**, which does its part by itself within seconds.

**On the pages** of the unchanged node: *Settings → High availability → The
addresses of the two nodes*. Put the new address into *The other node is at*,
press *Save the new addresses*. The result lists what was done, and anything
left to do.

**On the command line** of the unchanged node (as root):

```bash
otp --ha-readdress                          # what this node has now, and the machine's addresses
otp --ha-readdress --ha-peer 192.0.2.22     # the other node is at 192.0.2.22 now
```

What happens, in order:

1. This node's `pg_hba.conf`: the other node's line moves to the new address,
   `host`/`hostssl` kept (by the root helper, `otp-web.path`; the file as it
   was is kept beside it as `pg_hba.conf.otp-before-readdress`; PostgreSQL is
   reloaded, not restarted).
2. `ha_peer` in this node's `config.json`, and its subscription's connection,
   go to the new address. Replication from the other node starts again.
3. The other node is told, straight into its database: *you are reached at
   192.0.2.22 now*. It writes `ha_address` into its `config.json`, makes its
   database a new certificate for the new address (when the link is
   encrypted) and carries on. Replication to it starts again.
4. The firewall rules, keepalived (the web address) and nginx follow on both
   nodes by themselves - they are made from these settings.

### Both nodes got new addresses

Do it on both. On each node give both addresses: its own and the other's.

```bash
# on otp1 (now 192.0.2.21), the other (otp2) now 192.0.2.22
otp --ha-readdress --ha-address 192.0.2.21 --ha-peer 192.0.2.22
# on otp2
otp --ha-readdress --ha-address 192.0.2.22 --ha-peer 192.0.2.21
```

The first one cannot tell the other node yet (the other one still lets in
only the old address) and says so; the second one completes it.

### Only this node's own address changed, and the other cannot be reached

On the pages: *This node is reached at*, or `otp --ha-readdress --ha-address
NEW` on this node. It writes `ha_address` and renews its database
certificate, but the other node keeps refusing it until the other node is
told - do that on the other node as above (*The other node is at*). The page
warns when `config.json` names an address this machine no longer has.

### What is never changed by this

- **The RADIUS clients** (the VPN, the firewalls, the load balancer) still
  send to the old address: change the RADIUS server's address there.
- **DNS** names pointing at the old address.
- **The web address (VIP)** itself, if it has to move to another network:
  *Settings → High availability → The web address*, or
  `otp --vip-set NEW/PREFIX`.
- A **load balancer** in front of the pages: its list of nodes.

---

## 3. One server: a new address

otp itself does not keep its own address on a single server: RADIUS listens
on all addresses and the pages are served by nginx on all of them. Change:

- the RADIUS server's address on the VPN and every client;
- DNS;
- the certificate of the pages, if it names the address
  ([section 4](#4-certificates-of-the-pages));
- *Settings → Firewall and access*, if a rule names the old address or network.

---

## 4. Certificates of the pages

The certificate of the pages is for a name (and sometimes an address). After
a rename or a new address that people use in the browser, give the node (or
the web address) a certificate for the new name: *Settings → Certificates and
TLS → Upload*, *Request (CSR)* or *Self-signed*, or on the command line:

```bash
otp --tls-for otp3 --tls-import otp3.pem otp3.key chain.pem
```

A certificate saved in otp is also put back by itself when nginx's file is
missing or different - after a restore, a reinstall of nginx, a file changed
by hand.

The certificates of the **link between the databases** are otp's own and need
nothing: each node makes itself a new one whenever its names or addresses
change, and 45 days before one ends.

---

## 5. Checking afterwards

```bash
otp --ha-status                # both nodes, both directions running
otp --ha-readdress             # the addresses as each node has them
```

On the pages, *Settings → High availability*:

- **Replication**: *both directions running*, nothing waiting to go over;
- the bar about the link between the databases: green, *encrypted and
  checked (verify-full)*, with the certificate of each node (it may show the
  steps for a few seconds while a node makes itself a new one);
- **The addresses of the two nodes**: no warning;
- *Events*: what each node did, with the old and the new address.

Then try a sign-in through the VPN.

---

## 6. When it does not work

| What you see | What to do |
|---|---|
| *the root helper of this node did not answer* | `systemctl status otp-web.path` - start it (`systemctl enable --now otp-web.path`), then save again |
| *the other node could not be reached ... to be told* | do the other node's part on its own pages, or `otp --ha-readdress ...` there |
| *pg_hba.conf has no line of otp's ...* | the file was written by hand: add `host DB USER NEW-ADDRESS/32 scram-sha-256` (or `hostssl`) yourself, `systemctl reload postgresql`, then save again |
| the link bar stays at *link verify-full* | the other node's certificate does not name the address yet - it makes a new one by itself within a minute; *Repair* in the bar starts both nodes again |
| replication says *needs a look* for long | *The errors...* on the Replication card shows PostgreSQL's own words |
| nothing helps | the old way still works: `otp --ha-standalone --yes` on one node, then `otp --ha-setup --ha-peer NEW` and `otp --ha-join` (operations.md, section 11) - the joining node's database is replaced with the other's |

Every change is written into *Events* on the node that made it, with who did
it and what was there before.
