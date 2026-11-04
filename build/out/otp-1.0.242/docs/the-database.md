# The database

Everything otp keeps is in one database: the tokens, the clients, the realms,
the directories, the settings saved on the pages, the accounts, every RADIUS
request, every check of a code, every event.

| Engine | When | Needs |
|---|---|---|
| SQLite — a file, `/var/lib/otp/otp.db` | the default; one server | nothing |
| MariaDB / MySQL | a database server you already run, or two otp servers on one database | `python3-PyMySQL` (`--with-db mariadb`) |
| PostgreSQL | the same | `python3-psycopg2` (`--with-db postgres`) |

The database's own address cannot live in the database, so `db_engine`,
`db_host`, `db_port`, `db_name`, `db_user`, `db_password` and `db_timeout_s`
are kept in `/etc/otp/config.json`. Everything else saved on the pages
lives in the database and wins over that file.

## The key of the tokens

The key of every token, the shared secrets of the clients and the passwords
of the directories are sealed with `/var/lib/otp/secrets.key`. A copy of the
database without that key is a copy whose tokens cannot be opened: every
backup is written with the key beside it (`otp-YYYYMMDD-HHMMSS.key`), and a
copy carried to another machine needs it in `/var/lib/otp/` there.

## Copies

One a day at `backup_at` (03:30), the last `backup_keep` (14) kept, in
`/var/lib/otp/backups/` — gzip'd JSON lines, the same for every engine, so a
copy from SQLite goes into PostgreSQL and the other way round.

```bash
otp --backup                                        # one now
otp --restore /var/lib/otp/backups/otp-….json.gz --yes
```

## Moving to MariaDB

```sql
CREATE DATABASE otp CHARACTER SET utf8mb4;
CREATE USER 'otp'@'localhost' IDENTIFIED BY '…';
GRANT ALL ON otp.* TO 'otp'@'localhost';
```

## Moving to PostgreSQL

```bash
sudo -u postgres psql -c "CREATE USER otp PASSWORD '…'"
sudo -u postgres psql -c "CREATE DATABASE otp OWNER otp"
```

## Then, for either

```bash
otp --backup
systemctl stop otp
# /etc/otp/config.json:
#   {"db_engine": "postgres", "db_host": "127.0.0.1", "db_port": 5432,
#    "db_name": "otp", "db_user": "otp", "db_password": "…"}
otp --restore /var/lib/otp/backups/<the copy just made> --yes
systemctl start otp
otp --status
```

The tables are made by otp itself. `test/engines.sh` runs the whole flow —
restore, a client, a realm, a token, real RADIUS packets, the logs read back,
a copy — on each engine.

## How long things are kept

`retain_radius_days` (180), `retain_otp_days` (180), `retain_events_days`
(365); 0 keeps for ever. The tidying runs every hour, or `otp --tidy`.
