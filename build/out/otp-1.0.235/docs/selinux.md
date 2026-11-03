# SELinux

*Settings → High security → SELinux* (1.0.233), a card for each node; on the server
`otp --selinux-check` (as root). **Nothing changes unless somebody asks:** a machine
where SELinux is disabled stays disabled, and otp runs on it exactly as before.

## What otp needs of it

With SELinux enforcing (RHEL, Rocky, AlmaLinux - the *targeted* policy), the daemon,
its root helper and the upgrade run unconfined, as every service started from
`/usr/local` does. Confined are the programs around them, and these need a few
things the system's policy does not say by itself:

| What | Why | How |
|---|---|---|
| `/run/otp` and the API token labelled `httpd_var_run_t` | the pages (php-fpm, `httpd_t`) read the token; systemd makes `/run/otp` as `var_run_t`, which `httpd_t` may not read | otp's module **`otp_server`** (`/usr/local/lib/otp/otp_server.cil`): file labels only, no rule of its own - for `/run/otp` and `/var/run/otp` both (1.0.234), as the policy reads one as the other (`file_contexts.subs_dist`: `/run` ↔ `/var/run`) |
| `httpd_can_network_connect` on | the pages ask the daemon on `127.0.0.1:9861` (`api_port`) | a boolean |
| `authlogin_radius` on | SSH asks otp for the code (pam_radius in `sshd_t`) - only with *SSH with a code* | a boolean |
| the SSH gate's port as `radius_port_t` | pam_radius sends to it (18129 and up by default) | `semanage port` |
| sshd's port as `ssh_port_t` | sshd on a port other than 22 | `semanage port` |
| PostgreSQL's port as `postgresql_port_t` | a local PostgreSQL on a port other than 5432 | `semanage port` |
| `/var/www/otp`, `/usr/libexec/keepalived/otp-vip-check` | the pages; keepalived's check, which may run unconfined from there | the system's own labels (`restorecon`) |

`install.sh` and every upgrade copy the module beside the program, and put it into the
policy where SELinux is on (only when it changed - `semodule` takes its time), and say so
when the policy still does not label `/run/otp` for the pages (`matchpathcon /run/otp`).
Where SELinux is disabled they do nothing more. `--uninstall` takes the module out; the mode,
the booleans and the ports are the machine's and stay as they are.

## The card

Per node: the mode now and after the next restart, otp's module, the labels of its files,
the booleans and ports above, and **what SELinux refused since the machine started**
(`ausearch -m AVC,USER_AVC -ts boot`, for the web server, keepalived, sshd, chronyd,
PostgreSQL, rsyslog, logrotate and anything with otp in it), grouped and counted.
Looked at two minutes after otp starts and every half hour after that, and at once with
*Look again*; `semanage`, `semodule -l` and `ausearch` run at the lowest CPU and disk
priority (1.0.234). **What was refused before otp's needs were last put in no longer
counts** (1.0.234): *Put in what otp needs*, when it changes anything, starts the count
again - no second restart is needed after the first permissive start. *Switch to
enforcing* never starts it again. **auditd** must run: without it nothing is written down,
and enforcing is refused.

The steps, each asked of that node only and done by its root helper:

1. **Make it ready (permissive)** - from *disabled*: `SELINUX=permissive` in
   `/etc/selinux/config`, every file labelled at the next start (`/.autorelabel`),
   `selinux=0` taken off the kernel's command line (`grubby`) where it is there, otp's
   module put in. **The machine is not restarted**: restart it when it suits
   (*Settings → Restart and power off*), one node at a time - the labelling takes a few
   minutes before it answers. It comes up permissive: nothing is refused, what would be
   is written down. On a permissive node the same button (*Put in what otp needs*) puts
   in the module, the booleans and the ports and labels otp's files again.
2. Let it run a day or two as it is used - sign-ins, the pages, a failover, an upgrade,
   a backup - then *Look again*.
3. **Switch to enforcing** - only from permissive, and only once nothing otp needs is
   missing **and nothing was refused since the start**: `setenforce 1` and
   `SELINUX=enforcing`. Refused otherwise, with what is missing.
4. **Back to permissive** - at once (`setenforce 0`) and after a restart.

Every step is written in Events with who asked; the security check lists what keeps a
node where SELinux is on from being protected as it should (on a disabled node it says
nothing, as before). With the guard against writes to the database on, a step written
straight into the database is not done.

## On the server

```bash
otp --selinux-check            # a report; exit 1 when something is missing
```
```bash
otp --selinux-check --json
```

Something refused that otp did not foresee: `ausearch -m AVC -ts boot | audit2why`
says why, and `audit2allow -M otp-local` makes a local module of it - send the
output of `otp --selinux-check` so it can go into `otp_server`.
