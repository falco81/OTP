#!/bin/bash
# Drop the hunt8r pair: subscriptions (slot detached first), slots, databases, role.
for port in 5432 5433; do
  db=$([ $port = 5432 ] && echo hunt8r_a || echo hunt8r_b)
  sub=$([ $port = 5432 ] && echo hunt8r_from_2 || echo hunt8r_from_1)
  if runuser -u postgres -- psql -p $port -d $db -Atc "select 1" >/dev/null 2>&1; then
    runuser -u postgres -- psql -p $port -d $db -q -c "ALTER SUBSCRIPTION $sub DISABLE" -c "ALTER SUBSCRIPTION $sub SET (slot_name = NONE)" -c "DROP SUBSCRIPTION $sub" 2>&1 | grep -v "does not exist"
  fi
done
for port in 5432 5433; do
  db=$([ $port = 5432 ] && echo hunt8r_a || echo hunt8r_b)
  for s in $(runuser -u postgres -- psql -p $port -Atc "select slot_name from pg_replication_slots where slot_name like 'hunt8r_%'"); do
    runuser -u postgres -- psql -p $port -qAtc "select pg_terminate_backend(active_pid) from pg_replication_slots where slot_name='$s' and active_pid is not null" >/dev/null
    sleep 1; runuser -u postgres -- psql -p $port -qAtc "select pg_drop_replication_slot('$s')" >/dev/null
  done
  runuser -u postgres -- psql -p $port -qc "DROP DATABASE IF EXISTS $db WITH (FORCE)"
done
for port in 5432 5433; do runuser -u postgres -- psql -p $port -qc "DROP ROLE IF EXISTS hunt8r_otp"; done
