#!/bin/bash
# newsb.sh SANDBOX VERSION - a new HA sandbox, made and joined (1.0.247): the PostgreSQL clusters
# are shared by every sandbox, and a replication slot's name is the cluster's - every other
# sandbox's subscriptions are dropped first (that sandbox no longer replicates).
set -e
S=${1:?sandbox}; V=${2:?version}; H=/home/claude/work/hasb; O=/home/claude/build/out/otp-$V
for port in 5432 5433; do
  for db in $(runuser -u postgres -- psql -p $port -XAtq -c "SELECT datname FROM pg_database WHERE datname LIKE 'otp_%'"); do
    for sub in $(runuser -u postgres -- psql -p $port -d $db -XAtq -c "SELECT subname FROM pg_subscription"); do
      for q in "ALTER SUBSCRIPTION $sub DISABLE" "ALTER SUBSCRIPTION $sub SET (slot_name = NONE)" "DROP SUBSCRIPTION $sub"; do
        runuser -u postgres -- psql -p $port -d $db -XAtq -c "$q" >/dev/null 2>&1 || true
      done
    done
  done
done
sleep 2
for port in 5432 5433; do
  runuser -u postgres -- psql -p $port -XAtq -c "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_name LIKE 'otp_from_%' AND NOT active" >/dev/null 2>&1 || true
done
bash $H/setup.sh $S
for n in a b; do cp $O/deploy/nginx-otp.conf $S/$n/nginx/otp.conf; done
echo $S > $H/current
. $H/env.sh a
out=$(python3 -I $O/otp.py --no-color --ha-setup --ha-peer 10.99.0.2 --ha-peer-port 5433 --ha-address 10.99.0.1 --yes --ha-bundle $S/bundle.json 2>&1)
ph=$(echo "$out" | sed -n 's/.*shown only now: *\([^ ]*\).*/\1/p')
. $H/env.sh b
OTP_HA_PASSPHRASE=$ph python3 -I $O/otp.py --no-color --ha-join $S/bundle.json --node-name nodeb --ha-address 10.99.0.2 --yes > $S/join.out 2>&1
mkdir -p $S/a/state/web $S/b/state/web
echo "made and joined: $S"
