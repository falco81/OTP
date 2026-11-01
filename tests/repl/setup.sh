#!/bin/bash
# Two-way replicated pair hunt8r_a (5432) <-> hunt8r_b (5433), as otp sets it up.
set -e
P=hunt8pw
mkdir -p /home/claude/ws/tests/repl/state /home/claude/ws/tests/repl/log; [ -f /home/claude/ws/tests/repl/state/config.json ] || echo {} > /home/claude/ws/tests/repl/state/config.json
[ -s /home/claude/ws/tests/repl/state/secrets.key ] || (python3 -c "import secrets;print(secrets.token_hex(32))" > /home/claude/ws/tests/repl/state/secrets.key; chmod 600 /home/claude/ws/tests/repl/state/secrets.key)
for port in 5432 5433; do
  db=$([ $port = 5432 ] && echo hunt8r_a || echo hunt8r_b)
  runuser -u postgres -- psql -p $port -qAt <<SQL
SELECT 1;
DO \$\$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='hunt8r_otp') THEN CREATE ROLE hunt8r_otp LOGIN PASSWORD '$P'; END IF; END\$\$;
ALTER ROLE hunt8r_otp REPLICATION;
GRANT pg_create_subscription TO hunt8r_otp;
CREATE DATABASE $db OWNER hunt8r_otp ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8';
GRANT CREATE ON DATABASE $db TO hunt8r_otp;
SQL
done
cd /home/claude/ws/tests/repl && /usr/bin/python3.14 mk.py
