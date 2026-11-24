## 1.0.334 — 24 November 2026

**Fixed**: moving the database from SQLite or MariaDB to PostgreSQL - the step before a replicated pair - could not be finished once there was a token: "Start using it" said "it holds an older copy: the tokens changed here since it was carried", however often everything was carried again. The times of a token's key, state and recovery codes are written by PostgreSQL alone, and were compared with the empty ones of SQLite and MariaDB. They are now compared only where the database in use has them.

**Fixed (HA)**: a setting saved on a node whose clock was behind the other's was kept as the older one by the other node - the two held different values until the next change. A setting is now saved as later than the one it replaces, as a token's times are (1.0.214).

**Fixed (HA)**: the other node's rows of the guard on recovery codes were tidied here as well; a count it added at that moment was lost. Each node tidies its own, as the codes' and the questions' (1.0.327).

