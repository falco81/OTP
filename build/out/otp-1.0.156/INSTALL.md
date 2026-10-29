# otp — installing it

A one-time password server for a VPN: RADIUS, TOTP codes, Active Directory,
and pages where people enrol their own token. One Python file, the standard
library, and PHP pages that only relay to it.

---

## The short version

```bash
tar xzf otp-1.0.156.tar.gz
cd otp-1.0.156
sudo ./install.sh --server-name otp.example.local
```

It asks a handful of questions, installs everything, makes the first account
and prints its password. Then:

- `https://otp.example.local/admin/` — the administration pages
- `https://otp.example.local/` — the enrolment pages, for everybody else

To see what it would do without doing it:

```bash
sudo ./install.sh --dry-run
```

Replacing an old totpcgi + FreeRADIUS server in the same step, with every
token it has:

```bash
mkdir /root/old-otp && cd /root/old-otp && unzip /root/otp.zip   # its etc/raddb and etc/totpcgi
cd /root/otp-1.0.156
sudo ./install.sh --server-name otp.example.local \
     --import-legacy /root/old-otp \
     --radius-from 192.0.2.1/32 \
     --isemon isemon.example.local:514/tcp
```

See [docs/migration-from-totpcgi.md](docs/migration-from-totpcgi.md) for what comes over and what to
check afterwards.

---

## What it needs

- AlmaLinux 9 (or Rocky / RHEL 9 or 10). Debian 12 and Ubuntu 24.04 work as
  well; there the installer does less by itself.
- Python 3.8 or newer. install.sh runs otp on the newest one the distribution
  offers beside its own: on RHEL, Rocky and AlmaLinux 9 it installs
  `python3.12` (and `python3.12-psycopg2` / `python3.12-PyMySQL` for the
  database) from AppStream, as the system's python3 there is 3.9. The choice
  is the link `/usr/local/lib/otp/python`; the service and the `otp` command
  start it. `--python PATH` picks one, `--system-python` keeps the system's.
- nginx and PHP-FPM 8.x for the pages. The installer puts PHP on a release
  fixed for php2shell (below).
- chrony for the clock - codes from the app are worked out from it. install.sh
  installs it, stops systemd-timesyncd if that runs, and enables chronyd, on a
  fresh install and on every `--upgrade` (also one started from the pages).
  Its own `/etc/chrony.conf` is kept; Settings → Time sets other servers.
- UDP 1812 and 1813 open from the VPN concentrators.
- A read-only account in Active Directory (`otp@example.local`), and LDAPS
  to the domain controllers — with the CA certificate if they use your own.

---

## What it installs, and where

| What | Where |
|---|---|
| the daemon | `/usr/local/lib/otp/otp.py`, linked as `/usr/local/bin/otp` and `/usr/local/bin/otp` (the same command) |
| what it is set up with | `/etc/otp/config.json` — only the database settings (`db_*`) need be here; everything saved on the pages lives in the database and wins over this file |
| everything it records | `/var/lib/otp/otp.db` (SQLite), or MariaDB / PostgreSQL |
| the key that seals the token keys | `/var/lib/otp/secrets.key` — **keep it with every copy of the database** |
| copies | `/var/lib/otp/backups/` — one a day, each with the key beside it |
| its own log | `/var/log/otp/otp.log` |
| the logs for isemon | `/var/log/otp/totp.cgi.log`, `/var/log/otp/radius-detail.log` |
| the API token the pages use | `/run/otp/api-token` (group `otp-web`) |
| the pages | `/var/www/otp/` (enrolment `/`, administration `/admin/`) |
| the service | `/etc/systemd/system/otp.service` (user `otp`) |
| nginx | `/etc/nginx/conf.d/otp.conf`, certificate in `/etc/nginx/certs/` |
| PHP-FPM | the pool `/etc/php-fpm.d/otp.conf` (user `otp-www`, socket `/run/php-fpm/otp.sock`) and `/etc/php.d/99-php2shell.ini` |
| rotation | `/etc/logrotate.d/otp` |
| the first password | printed at the end of the install; only where the service had to make an account itself is it in `/var/lib/otp/first-login.txt` (gone once the password is changed) |

Accounts: `otp` runs the daemon; `otp-www` runs PHP; the group `otp-web`
may read the API token. Nothing runs as root after the start.

---

## Every option

```
--server-name HOST        the pages' hostname (default otp.example.local)
--admin-allow CIDR[,..]   who may reach the administration pages
--portal-allow CIDR[,..]  who may reach the enrolment pages (both default to RFC 1918)
--radius-from CIDR[,..]   who may send RADIUS through firewalld: the VPN concentrators
--admin-user NAME         the first account (admin)
--admin-password PASS     its password (otherwise one is made and printed)
--cert FILE --key FILE    the TLS certificate and key (otherwise a self-signed one)
--import-legacy ROOT      bring an old totpcgi + FreeRADIUS server over
--isemon HOST[:PORT][/tcp] send the logs to isemon
--isemon-hostname NAME    the host name isemon files them under (default otp)
--site-name NAME          what to call this installation on the pages
--with-db ENGINE          the Python driver for mariadb, postgres or both
--python PATH             run otp on this Python rather than the newest found
--system-python           run otp on the system's own python3
--php-stream X.Y          the AppStream PHP stream for a machine with no PHP yet (default 8.3)
--remi                    PHP 8.4 from Remi's repository instead
--no-php-update           leave PHP as it is (it is still checked)
--no-web                  the daemon only
--no-db-restart           the pages may not restart a PostgreSQL here after tuning it
--upgrade                 replace the program and pages, fix PHP, restart; keep the rest
--rewrite-nginx           write the nginx file afresh (otherwise one that is there is kept)
--uninstall               remove the service and the pages; keep the data (always asks)
--dry-run                 print what would happen
--yes                     never ask
```

---

## PHP and php2shell

The pages are PHP, so the PHP running them must not have php2shell
(CVE-2026-109618 / CVE-2026-109619, remote code execution through a crafted
multipart request, fixed upstream on 21 October 2026 in 8.2.35, 8.3.36, 8.4.27
and 8.5.12). The installer:

1. leaves a PHP that is installed and fixed exactly as it is — nothing is
   installed, no stream is switched, nothing restarted, and no version is
   pinned: newer builds and streams come with `dnf upgrade` / `apt upgrade`;
   a PHP that is installed but not fixed only has its own packages upgraded,
   on the stream it is on; a machine with no PHP gets the AppStream stream
   `php:8.3` (`--php-stream`) when no stream is enabled yet — an enabled one is
   kept. AlmaLinux ships the fix as 8.3.36-1 (8.2.35-1 on `php:8.2`; the
   default 8.0 has it backported);
2. checks the result by its version and, when a distribution backported the
   fix under an old number, by the changelog of php-fpm (`rpm -q --changelog php-fpm`, CVE-2026-109618);
3. offers PHP 8.4 from Remi's repository if AppStream has no fixed build yet;
4. adds a guard whatever happens: `/etc/php.d/99-php2shell.ini` and the pool
   switch off what the attack needs, and nginx refuses every multipart request
   (none of otp's pages sends one);
5. reloads php-fpm only when otp's pool or the guard file changed (or its
   socket is missing); a PHP that needed nothing is not touched.

The administration pages say so in red, at the top, for as long as the PHP
running them is not fixed. More in [docs/php2shell.md](docs/php2shell.md).

---

## After installing

```bash
otp --status                    # everything at once
otp --check                     # the configuration, the directory, the ports
otp --radtest someone 123456    # a RADIUS request from this machine
```

1. Sign in to `https://<host>/admin/` with the first account and change its
   password (the account menu, top right).
2. **Settings → Active Directory**: the domain controllers, the reading
   account, the CA certificate. *Check it* says which step fails, if one does.
3. **Settings → Realms**: what comes after the @ — the directory, the groups
   that let in, the password mode, what goes back to the VPN.
4. **Settings → Clients**: the ASA — its address and shared secret, and the
   realm added to names that come without one.
5. **Settings → The enrolment pages**: who may enrol, and the help text.
6. **Settings → isemon**: where to send the logs ([docs/isemon.md](docs/isemon.md)).
7. Enrol a token for yourself at `https://<host>/` and try it from the
   **Test** tab, then from the ASA.

On the ASA (the code alone, the directory password asked elsewhere — what the
old server did):

```
aaa-server OTP protocol radius
aaa-server OTP (inside) host 192.0.2.10
 key <the shared secret>
 authentication-port 1812
 accounting-port 1813
 timeout 15
```

---

## Upgrading, uninstalling

```bash
sudo ./install.sh --upgrade      # new program and pages, PHP fixed, restarted
sudo ./install.sh --uninstall    # service and pages gone; /var/lib/otp and /etc/otp kept
```

From the pages, and node by node in a cluster: [docs/upgrades.md](docs/upgrades.md).

Every procedure - PostgreSQL 16 on AlmaLinux 9, moving to it, building a
cluster, a node down or lost, leaving the cluster - step by step:
[docs/operations.md](docs/operations.md). Certificates, TLS and the web
address (VIP), with what to open in the firewall: [docs/tls-and-vip.md](docs/tls-and-vip.md).
Load balancers: [docs/load-balancers.md](docs/load-balancers.md).

### From an installation called "opt" (1.0.36 and older)

Up to 1.0.36 the program was installed as **opt** (`opt.service`,
`/usr/local/lib/opt`, `/var/lib/opt`, `/etc/opt-otp`, the accounts `opt`,
`opt-web`, `opt-www`). `sudo ./install.sh --upgrade` of this version renames
all of it to **otp** once and keeps everything in it - settings, tokens,
accounts, logs, copies, the key, nginx's file and certificate - and renames a
database called opt on this machine (PostgreSQL or MariaDB) and its account
to otp, and replication's objects on both nodes of a cluster. In a cluster,
upgrade one node, then the other. After it there is no `opt` anywhere:
`systemctl status otp`, `otp --status`.
