# SSH keys on the pages

*Settings → SSH keys* (full administrators): the keys that may sign in to each node over SSH,
read from every node, a column a node.

## Root (1.0.158)

The lines of `/root/.ssh/authorized_keys`, read from every node - **only shown** (1.0.280): no key
for root is made, put on or taken away from the pages, and the server refuses it too. A way in as
root is put on, or taken away, by root on the node itself. Each key's public half can still be
exported as its `.pub` file.

## Every user who may sign in (1.0.240)

*Whose keys* picks root or a normal user of the nodes: UID_MIN to UID_MAX of
`/etc/login.defs` (1000 to 60000), with a login shell (not `nologin` or `false`). Local users
(`/etc/passwd`); directory users of sssd appear when the machine lists them.

Their own `~/.ssh/authorized_keys`: listed, a key added (a line of your own, or made here - its
private half shown once to hand over, kept nowhere), exported, taken away - on the nodes where
the user is. In a cluster a key is made as root's was until 1.0.279: *The same key on every node*
(where the user is), or *Only on* one node.

The file is read and written **as that user** - by a child of the root helper that has their
UID, GID and groups: `~/.ssh` made 0700 and the file 0600, theirs; a link put there (to
`/etc/shadow`, to `/root/.ssh`) is refused and never followed, so nothing in a user's own home
can make root write anywhere else. A name that is not such a user (a system account, one with
`nologin`, `../root`) is refused. Every change is in Events, with the user's name.
