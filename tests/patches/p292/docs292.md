## This machine's database

No agent is needed to see a database that runs on otp's own machine. *Settings → The database →
Show this machine's database as a database server* (`db_local_card`, off by default, offered for
PostgreSQL and MariaDB only) draws the card *Database server* for it, above *Encryption to the
database server*.

| | |
|---|---|
| Who looks | Each node whose database is on its own machine (localhost, 127.0.0.1, ::1 or a socket) and has no agent - every 30 s (`OTP_DBLOCAL_EVERY`), with its own connection to the database and `/proc`. |
| What it reads | The engine's version, whether it runs and since when, TLS, the connections, the disk of its data (`statvfs` of its folder, where otp's account may read its name, else the usual place), the memory, the processors and the load, the machine's uptime, the end of the certificate otp gave PostgreSQL (Encryption to the database server, or the link between the databases). |
| Where it goes | This node's row `dblocal:node:NODE` in `meta`, without a password. The other node of a cluster reads it with every node's rows; rows of nodes not in the cluster, or older than a week, are not shown. |
| The page | A tile per node (this node's first); another node silent for more than 2 minutes in amber, a certificate ending within 14 days in red. *Look now*; *Renew the certificate* when otp gave PostgreSQL its certificate; *Restart the database…* while PostgreSQL's settings wait for a restart and install.sh let otp restart it. `GET /api/db-agent` has `local: [...]`. |
| Not there | The agent's rows, join codes, *Forget*, the dots on other cards, rows in the meter or on High availability, alerts. With an agent the card is the agent's. |
| Off | Nothing read, written or shown; `GET /api/db-agent` without `local`. Switching it off takes this node's row away (also at a start with the setting off). A move to another server leaves the row behind. |

