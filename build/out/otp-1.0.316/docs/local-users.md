# Local users of the machines - 1.0.243

*Settings → Local users* (full admin only): the users of each node's own system - who may sign in to
the machine itself, over SSH or at its console. They are not the accounts of these pages (*Accounts*).

In a cluster every change goes to **every node at once**, or to the nodes you tick; a standalone server
has the one node. Each node's root helper (`otp_web.py`, `otp-web.path`) does it with the system's own
tools - `useradd`, `usermod`, `chpasswd -e`, `chage`, `gpasswd`, `userdel` - exactly as an administrator
would at the console.

## What is shown

One row a user, a column a node: whether the user is there, locked there, or there with another UID.
Above the list, the accounts with no shell (often a package's) are hidden until *Also the N accounts
with no shell* is ticked. A user's pencil opens the facts node by node - UID, home folder, shell,
groups, the password (none / set on a day / to be changed at the next sign-in), locked or not, sudo.

**root** is first and **shown only**: its password, its shell and whether it may sign in are changed
on the machine itself, never from these pages - the API refuses any change of it. Accounts of the
system (outside `UID_MIN`..`UID_MAX` of `/etc/login.defs`) and the services' own (otp, postgres,
nginx, sshd…) are neither shown nor changed.

## What can be done

| | |
|---|---|
| **Add a user** | name, full name, shell (from `/etc/shells`), a password (or none: SSH keys only), *to be changed at the first sign-in*, sudo; the same UID on every node - the lowest of the normal range no node uses |
| **Make it on more nodes** | a user on one node only made on the others too, with its UID |
| **Name and shell** | the full name (GECOS) and the shell |
| **Password** | a new one, typed twice; *to be changed at the next sign-in* if wanted |
| **Give / take sudo** | membership of `wheel` (RHEL) or `sudo` (Debian, Ubuntu) - root with their own password |
| **Lock / unlock** | locked: the password put out of use *and* the account expired - no SSH key lets them in either; nothing of theirs is taken away |
| **Take the user away** | `userdel`, with the home folder or without; refused while they are signed in or run something |

The SSH keys of a user are in *SSH keys* (*Whose keys*) once the user is there; who may sign in over
SSH at all is in *SSH server and notices*.

## The password policy (1.0.245)

*Password policy* under the list: one policy for every local user of the cluster, put in by each
node into its **system's own files** - so that it holds however a password is changed: `passwd`, a
password run out at sign-in, these pages. **Not set by otp (the default), nothing is written**: each
node keeps what its system has; the card shows it (*In effect on the nodes*).

| Rule | Where it goes |
|---|---|
| characters at least, kinds of characters at least (small, capitals, digits, the others), the same character in a row at most, characters not in the old one, no word of the dictionary, not the user's name | `/etc/security/pwquality.conf.d/50-otp.conf` (pam_pwquality; `pwquality.conf` itself untouched) |
| the last passwords not taken again | `/etc/security/pwhistory.conf`, otp's lines between marks (pam_pwhistory) |
| good for (days), warned so many days before, the least days between two changes | `/etc/login.defs` (`PASS_MAX_DAYS`, `PASS_WARN_AGE`, `PASS_MIN_DAYS`) for the users made from then on - the values before kept; *Also for the users there now* gives them to every local user (`chage`), root never |
| locked after so many wrong, for so long, counted within | `/etc/security/faillock.conf`, otp's lines between marks (pam_faillock); root is never locked |

With **authselect** (RHEL, Rocky, AlmaLinux) the features that put the modules into PAM are switched on
where they are not - `with-pwhistory`, `with-faillock` - and off again when no longer needed, only those
otp switched on. Without authselect the modules must be in PAM already; the card says on which node
one is not (*pam_pwquality is not in its PAM…*).

Switched off again (*Set by otp on every node* off), every file is as it was before: the drop-in and
otp's lines go, login.defs' values come back, the features otp switched on go. The aging given to the
users there is left as it is.

A password typed on these pages is checked against the policy before it goes anywhere: by `pwscore`
(the system's own rules and dictionary) where it is installed, by the rules above where not.

**With SSH keys, otp's codes and sudo.** A password that runs out is asked to be changed at the next
sign-in over SSH too, with a key or with otp's code (sshd runs PAM's account step for every sign-in).
So a user with **no password** (a key only) gets **no aging**: made from the pages without a password,
`chage -M -1`; *Also for the users there now* leaves them out; given a password later, they get the
policy's aging then. otp's code is no password: its PAM lines (`[success=done … default=die]`) end the
auth step before pam_faillock, so a wrong code is never counted, and a lock by wrong passwords keeps
out a password only - never a key or a code. **sudo** (and so a normal user's `otp --console`) asks for
the user's own password: a user with sudo needs one, and the policy is the one for it; one locked by
wrong passwords cannot use sudo until the lock ends. root is never locked and never given aging.

Each user's own aging (*Password aging* in their popup): good for, warned before, the least days
between two changes - `chage`, on the nodes chosen; when the password runs out is shown.


Typed on one node's page, it never leaves that node as itself: the node makes its hash (SHA-512 crypt,
`openssl passwd -6` from standard input), seals it with the cluster's key, and asks that of each node.
Each node's root helper hands it to `chpasswd -e` on its standard input - never on a command line, never
in a log. Once a node said it is done, the sealed hash is taken out of the asking row (after 15 minutes
in any case); Events say who changed which user on which nodes, never the password.

## The guard of root's actions

The rows a change is asked in (`host:users:want:…`) are among those the guard signs
(*High security → the guard of root's actions*): with it on, a row written straight into the database -
a user with sudo, say - is done by no node.

## Command line and console

```
otp --local-users                                   # the users of each node
otp --local-user add jnovak --local-full-name "Jan Novák" --local-must-change   # the password is asked
otp --local-user password jnovak                    # asked at the terminal, twice
otp --local-user sudo-on jnovak                     # sudo-off
otp --local-user lock jnovak                        # unlock
otp --local-user drop-home jnovak                   # drop: the home folder kept
otp --local-user lock jnovak --local-nodes otp2     # one node only
otp --local-user aging jnovak --local-max-days 90 --local-warn-days 14
otp --local-policy                                  # the password policy: as set, in effect on each node
otp --local-policy-set managed=1 minlen=14 minclass=3 remember=5 max_days=180 deny=5
otp --local-policy-set managed=0                    # back to each system's own
```

In `otp --console`: *Certificates, updates, restarts, tests → Local users of the nodes*, *Add a local
user*, *A new password for a local user*, *Lock, unlock, sudo or take away a local user*, *The password
policy of local users: how it stands*, *Set the password policy of local users*.
