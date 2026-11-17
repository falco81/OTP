# 1.0.300 docs: SELinux - what is refused sorted, put right by id, otp's local rules.
import sys
F = sys.argv[1].rstrip('/') + '/docs/selinux.md'
s = open(F).read()
a = """## The report, for otp's module (1.0.236)"""
b = """## What SELinux refuses, sorted by what puts it right (1.0.300)

*Look again* is a whole analysis, by that node's root helper: every `AVC`, `USER_AVC` and
`SELINUX_ERR` since the machine started (since otp's needs were last put in), read with the
records of its event - the program (`SYSCALL`, `PROCTITLE`), the whole path (`PATH`), the port -,
grouped by what was refused (source and target type, class, permissions, program, path or port),
each group put to `audit2why`, and sorted into one kind. A finding's id is a hash of what was
refused (12 hex): the same refusal has the same id at every look.

| Kind | Meaning | Put right by |
|---|---|---|
| *allowed now* | the policy loaded now allows it | - (not listed, said as settled) |
| **A boolean** | `audit2why` names a boolean | `setsebool -P NAME 1` - never one that allows far more (`*exec*`, `unconfined`, `*_manage_all*`, `*_read_all*`, `ptrace`, `deny_*`, `httpd_unified`...) |
| **A label** | one of otp's files is not labelled as `matchpathcon` says | `restorecon -R -v` of its folder |
| **A port** | a confined service otp works with (nginx, sshd, chronyd, PostgreSQL, rsyslog) on one of otp's ports of no type | `semanage port -a -t TYPE -p PROTO PORT` - never a port of another service's type |
| **A rule of otp's** | nothing of the policy allows it, and exactly that is safe | one rule in otp's own **local module `otp_local`**: `(optional otp_local_ID (allow SRC TGT (CLASS (PERMS))))` |
| **Not for a button** | otp's, but too much to allow from a page | said why - never put right: a security-sensitive target (`shadow_t`, `security_t`, the policy, keys, audit, `sudo_*`, home...), running or changing far more (`execute`, `transition`, `ptrace`, `relabel*`, capabilities such as `sys_admin`, `dac_override`...), the system's own classes, writes to types of many files (`etc_t`, `usr_t`, `bin_t`, `var_t`, `tmp_t`...) |
| **Not otp's** | another program of the machine | shown, never put right here; one of the services otp works with (the web server, keepalived, sshd...) still counts before enforcing, as until now |

**Whose it is**: the daemon (its command line `otp.py`, or a program under `/usr/local/lib/otp`),
the programs it runs that have a domain of their own (`hostname`, `ip`, `ssh-keygen`, `ssh`/`scp`/`sftp`,
`ping`, `chronyc`), and the confined services it works with **only on otp's paths** (`/usr/local/lib/otp`,
`/var/lib/otp`, `/var/www/otp`, `/run/otp`, `/etc/otp`, `/var/log/otp`, `/etc/pki/otp`, its nginx,
php-fpm, sshd and logrotate drop-ins, keepalived's check) **or otp's ports**.

**Put in what is selected (N)**: every finding that may be put right comes ticked (a group has
*select all*); a confirm lists exactly what root will do. **The page sends only the ids**: root
finds each in its own audit log again and works out every fix itself - a request never carries a
rule, a path or a command. Root switches the boolean on, labels the folder, gives the port its type,
writes `otp_local` again from its list and loads it (`semodule -i`, a copy kept as `.in-policy`);
each step is written in Events, and it looks again at once. **It works under enforcing too** -
nothing has to be switched off. What was put right is noted with its time: a refusal of it from
before no longer counts, one from after comes back. A module that does not load keeps none of its
new rules. *otp's local rules (N)* lists each rule with **Take it away**; the last one taken away
takes `otp_local` out of the policy. `--uninstall` takes it away with `otp_server`.

In a cluster each node has its own card, its own audit log, its own `otp_local` - put right on the
node where it was refused, by that node's root helper (whichever node answers the pages).

*Switch to enforcing* stays locked while anything is left to put right or not for a button - the
card says how many of each.

The module `otp_server` itself (1.0.300) lets the daemon start the programs above in their own
domains: `otp.service` runs with `NoNewPrivileges=yes`, which forbids the transition unless the
policy allows it (`process2 { nnp_transition nosuid_transition }`) - under enforcing they would not
run at all. Only the transition, only into those domains, each in a block of its own.

## The report, for otp's module (1.0.236)"""
assert s.count(a) == 1
s = s.replace(a, b)
a2 = """make it. In it: what SELinux refused since the start (raw and readable, `audit2why`, and"""
b2 = """make it. In it (1.0.300: also `findings.json` - what was refused, sorted, and otp's local rules -
and `os/`: every process with its domain, every boolean, port type and module, what was changed on
this machine - `semanage ... -l -C`, `semanage export` - and every listening socket): what SELinux
refused since the start (raw and readable, `audit2why`, and"""
assert s.count(a2) == 1
s = s.replace(a2, b2)
a3 = """```bash
otp --selinux-report           # the report of this node, as a file
```"""
b3 = a3 + """
```bash
otp --selinux-fix ID...        # put right by the ids --selinux-check lists, or "all" - asked first
```
```bash
otp --selinux-rules            # otp's local rules (otp_local)
```
```bash
otp --selinux-take-away ID     # one of them taken away
```"""
assert s.count(a3) == 1
s = s.replace(a3, b3)
open(F, 'w').write(s)
print('ok')
