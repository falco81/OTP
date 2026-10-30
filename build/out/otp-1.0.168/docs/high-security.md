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
| Mail | to the server unencrypted or only if offered (`smtp_security` none, starttls-if); the certificate not checked; direct delivery without TLS required |
| SMS | the HTTP gateway over `http://`; the telephone gateway without HTTPS or without checking its certificate |
| Database, cluster | MariaDB/PostgreSQL over the network without `verify-ca`/`verify-full`; the replication likewise |
| Backups | plain FTP; FTPS not checking the certificate; SMB not encrypted |
| Syslog | UDP or TCP servers (only `tls://`); the certificate not checked; isemon (plain syslog) |
| The pages | TLS other than *standard* (ECDHE, AEAD) or *modern* (TLS 1.3); the administration reachable from everybody |
| SSH | passwords (or keyboard-interactive); root with a password; more than 4 tries |
| Tokens | debugging; a window of codes wider than one step; a code used again; exports not locked |

While it is on, each of these is refused wherever it is changed - the pages,
the API, `otp --set` - and greyed out on the pages, with why.

## Advised, stopping nothing

The administration without a second step from an app, or with one by mail or
SMS; administrators showing a token's key; the enrolment page showing the key
as text; recovery codes under 10 digits; codes by mail; enrolment for anyone in
a directory; sign-ins to the administration lasting over 8 hours or idle over
30 minutes; a proxy without a password.

Switching it off is always possible, and written down as every setting is.
