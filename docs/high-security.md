# High security (1.0.168)

*Settings → High security*, for a full administrator, off by default. On, it
switches off every way of doing something less safely, on every node.

## Switching it on

Switching it on first looks over everything - the settings, the directories,
the RADIUS clients, the backup destinations, the TLS of the pages, who may
reach the administration, and the SSH server as each node's sshd says it is.
What stands against it is listed in a window, each with what to set and a
link to where; it is refused (the daemon too, HTTP 409 with the list) until
the list is empty. The same list is on the page itself, with *Look again*.

## What stands against it

| Where | Refused |
|---|---|
| Active Directory | plain LDAP; the certificate not checked; old, weak TLS |
| RADIUS | answers without a Message-Authenticator; a client that sent one leaving it out; no Sign-in protection; a client's secret under 16 characters |
| Mail | to the server unencrypted or only if offered (`smtp_security` none, starttls-if); the certificate not checked |
| SMS | the HTTP gateway over `http://`; the telephone gateway without HTTPS or without checking its certificate |
| Database, cluster | MariaDB/PostgreSQL over the network without `verify-ca`/`verify-full`; the replication likewise |
| Backups | plain FTP; FTPS not checking the certificate; SMB not encrypted |
| Syslog | UDP or TCP servers (only `tls://`); the certificate not checked; isemon (plain syslog) |
| The pages | TLS other than *standard* (ECDHE, AEAD) or *modern* (TLS 1.3); the administration reachable from everybody |
| SSH | passwords (or keyboard-interactive); root with a password; more than 4 tries |
| Tokens | debugging; a window of codes wider than one step; a code used again; exports not locked |

While it is on, each of these is refused wherever it is changed - the pages,
the API, `otp --set` - and greyed out on the pages, with why.

## Exceptions (1.0.169)

Every rule has a switch on its right: *Exception*. A rule made an exception
stops nothing and is not enforced while high security is on - the rest stay.
While high security is on, an exception is taken back only once the rule is kept
(else high security would stand against itself). Each change is an event. The
rules kept are listed too, folded, each with its switch.

## The security check

What is not as it should be now - the firewall off, no backup going to another
machine or none tried, a backup that cannot be put back, security updates or a
restart waiting, certificates running out - is listed apart, and never stops
high security.

## Before 1.0.169: advised, stopping nothing

Direct delivery with TLS only where the recipient's server offers it (many
offer none, and a mail refused there is a token that never arrives); the
administration without a second step from an app, or with one by mail or
SMS; administrators showing a token's key; the enrolment page showing the key
as text; recovery codes under 10 digits; codes by mail; enrolment for anyone in
a directory; sign-ins to the administration lasting over 8 hours or idle over
30 minutes; a proxy without a password.

Switching it off is always possible, and written down as every setting is.


## Root's actions only from rows otp signed (1.0.231)

*Settings → High security → Guard against writes to the database* (`db_guard`;
a switch, off by default - as until now; until 1.0.232 it was called *Root's actions
only from rows otp signed* and shown as a box for 0 or 1).

Worth it with a cluster or a database on another machine; with SQLite on this
machine (only root and otp can write it) it adds little. Nothing else is to be
set: switch it on, on every node.

What a node does as root follows rows of the database: the firewall, sshd and
root's `authorized_keys`, the network and the host name, a restart or a power-off,
the system's updates and the proxy they go through, chrony's servers, nginx's
certificates, keepalived's VIP, the TLS of the link between the databases - and so
do the accounts and the sign-ins of these pages, through which all of it is asked
for. Anybody who can write the database - its server, a `db_password` found out, a
copy of the database put back - could write those rows, and the node did as they
said.

Since 1.0.231 every such row is signed when otp writes it: an HMAC under a key
worked out from `secrets.key`, which is in no database (both nodes of a cluster have
it). The signature is a row of its own beside it (`sig:<kind>:<hash>:<node>` in `meta`; each
node writes only its own, so replication never meets the same row from both sides);
versions before 1.0.231 leave those rows alone. With `db_guard` **on**, a node:

| Row | Not signed, or an older one put back |
|-----|--------------------------------------|
| a sign-in to these pages (`sessions`) | not taken - "not signed in" |
| an account (`accounts`: name, role, password, source, switched off, DN) | cannot sign in |
| the directory administrators sign in against | not asked |
| a setting that reaches root, or who may sign in (firewall ports, proxy, updates, restarts, logs, ACME, SNMP, the SSH gate, mail and SMS, the administrators' groups and second step, high security) | its last good value stays (else config.json and the default) |
| a row of `meta` that root acts on (`web:vip`, `web:tls:*`, `web:access`, `fw:conf`, `ntp:conf`, `net:*`, `power:plan`, `host:sshkeys:want:*`, `host:sshd:conf`, `host:osup:plan`, `hatls:*`, `readdress:*`, `sshotp:*`, `console:want:*`, `upgrade:plan`, `ask:want:*`, `adm2fa:*` ...) | read as not there - nothing is done |
| another node's heartbeat | its address not let through the firewall, not into nginx's lists, not taken for the VIP's or chrony's peer |

Each node remembers, in its own file (`/var/lib/otp/guard.json`, not in the
database), the newest signature it has seen of each row: a row taken from an
older copy - signature and all - is older, and refused. What is refused is written
in the log and in Events, and listed in the security check.

RADIUS, the codes and the tokens are **never** held up by it: a setting RADIUS
uses keeps its last good value, and nothing of the guard is asked on the RADIUS
path.

**Switching it on** writes `db_guard` into this node's `config.json` - never into
the database, so nobody who can write the database can switch it off - and signs
what the database holds at that moment as otp's word. It is switched off only on
the node itself (its pages, or `otp --set db_guard=0` as root). In a cluster switch
it on on every node, once all of them run 1.0.231 or later (it refuses while one
does not). A copy put back on purpose, a configuration imported, the database moved
and a node renamed are signed again by otp afterwards - they work as before.

**From the command line**: `otp --set db_guard=1` on each node, as root. Since
1.0.232 the running service takes it at once - nothing to reload or restart (in
1.0.231 it waited for `systemctl reload otp`, and that reload took the API token
away from the pages - see below).

**Another node's heartbeat** is a row and its signature, written in one
transaction since 1.0.232. From a node still on 1.0.231 they came over by
replication one after the other, and a node reading between them refused the
heartbeat (*meta node:otp2 - its signature is not right* in the log). Since
1.0.232 the address a node had in its last signed heartbeat is still taken while
a newer one waits for its signature; a heartbeat with another address is not.

**`systemctl reload otp`** (1.0.232): systemd gives the service's `/run/otp` back
to `otp:otp` before it sends the reload. The pages (the `otp-web` group) could then
not read the API token: `/healthz` said *503 - the pages cannot read the daemon's
API token* and the VIP address left the node until otp was restarted. This had
nothing to do with the guard - any reload did it. The daemon now gives `/run/otp`
and the token back to `otp-web` the moment the reload arrives, and checks it every
5 seconds. On 1.0.231 and older, use `systemctl restart otp`, or after a reload:
`chgrp otp-web /run/otp /run/otp/api-token`.

Not against the other node of a cluster: it holds the same key, and root on it is
root of the cluster's database anyway.

## SELinux (1.0.233)

The same pane has a card for SELinux on each node - what otp needs of it, what it refused, and the steps from disabled to permissive to enforcing, each asked by hand. See docs/selinux.md.
