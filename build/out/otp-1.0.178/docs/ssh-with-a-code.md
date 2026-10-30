# SSH to the nodes with a code from otp

*Settings → SSH server → Signing in with a code from otp* (1.0.178). sshd of
every node then asks for a code from the account's token where it would ask for
the account's password - through `pam_radius` and the RADIUS of the node itself. Both nodes
and a node alone alike: each asks its own daemon on 127.0.0.1, so a node whose
partner is down still lets you in.

It needs *otp sets the SSH server* on, and it is put in on trial like every
other change there: keep the session you have open, open a new one, then
*Keep it*.

## What otp does on each node

- Installs `pam_radius` if it is not there - `dnf -y install pam_radius` (RHEL
  and the like: from **EPEL**, so `dnf install epel-release` first) or
  `apt-get -y install libpam-radius-auth`.
- Makes the RADIUS client **SSH of the nodes - pam_radius** for 127.0.0.1 with a
  long random secret (or uses an enabled client that already covers
  127.0.0.1). RADIUS must listen on 127.0.0.1 - *Listen on* is 0.0.0.0, `::`
  or 127.0.0.1; another single address is refused when saved.
- Writes `/etc/otp/pam_radius.conf` (mode 0600, root) with that secret and the
  node's RADIUS port. The secret never goes on a command line.
- Puts a block of its own into `/etc/pam.d/sshd`, before its first `auth` line,
  between the lines `# otp: SSH with a code from otp (RADIUS) ... (begin)` and
  `(end)`:

  ```
  auth [success=1 default=ignore] pam_succeed_if.so quiet user = root
  auth [success=done new_authtok_reqd=done ignore=ignore default=die] pam_radius_auth.so conf=/etc/otp/pam_radius.conf localifdown
  ```

  With *Only these accounts* the first line is `user notin a:b` instead; with
  passwords off a `auth requisite pam_deny.so` follows, and there is no
  `localifdown`.
- Sets `UsePAM yes` and `KbdInteractiveAuthentication yes` in its drop-in, so
  sshd asks through PAM.

Switched off (or *otp sets the SSH server* off, or the trial not kept): the
block, the file and the drop-in's lines go; `/etc/pam.d/sshd` is exactly as it
was before.

## The settings

| Setting | |
|---|---|
| Ask for a code from otp | on / off |
| Only these accounts | separated by spaces; empty: everybody (but root, below) |
| Root too | off: root signs in as before - your way in if otp itself is in trouble |
| The system password when otp does not answer | `localifdown`: pam_radius steps aside and the account's own password is asked. Only with passwords on |

## The accounts

The name typed at `ssh` is the name otp looks up - in a realm with no suffix.
The user needs a token there; *Settings → Realms* decides what is asked (the
code alone, or a password and the code).

A key alone still lets in: sshd asks PAM only where it would ask for a password
(`AuthenticationMethods` is not changed). To want a key **and** a code, set
`AuthenticationMethods publickey,keyboard-interactive` yourself in a file of
your own under `/etc/ssh/sshd_config.d/`.

## High security

The rule *SSH: passwords* turns passwords off - and with them the fallback: with
otp not answering nobody but a key gets in. Root left out keeps the way in.

## Things that break it

- **A kernel booted with `ipv6.disable=1`.** pam_radius 2.0 opens an IPv6 socket
  first and gives up without one - every sign-in fails as *authentication
  information cannot be recovered*. Boot with IPv6 (it may stay unconfigured).
- SELinux keeps sshd from asking RADIUS while the boolean `authlogin_radius` is
  off - otp turns it on (`setsebool -P authlogin_radius on`) when it puts the
  block in, and leaves it on when the block goes.
- A `/etc/pam.d/sshd` changed by hand between the two marker lines is
  overwritten.

## Checking

On each node, *Settings → SSH server* says per node whether the code is asked
(pam_radius), not asked, or pam_radius is not there. The RADIUS log shows each
sign-in from the client *SSH of the nodes - pam_radius*.
