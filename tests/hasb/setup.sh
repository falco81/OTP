#!/bin/bash
# The HA sandbox, light (1.0.140): two nodes on one machine - two PostgreSQL 16
# clusters (A 5432, B 5433), addresses 10.99.0.1 (A), 10.99.0.2 (B; .3 for a
# trial) on lo, a fake NetworkManager, root helpers in a loop, the daemons as
# root. No nginx/PHP/keepalived. Nothing is deleted: S must not exist yet.
# Usage: setup.sh SANDBOX_DIR   (e.g. /tmp/sb1)
set -e
S=${1:?sandbox dir}
[ -e "$S" ] && { echo "$S exists - give a new one"; exit 1; }
for a in 10.99.0.1 10.99.0.2 10.99.0.3; do ip addr add $a/24 dev lo 2>/dev/null || true; done
pg_lsclusters | grep -q '^16 *second' || pg_createcluster 16 second -p 5433 >/dev/null
pg_ctlcluster 16 main start 2>/dev/null || true; pg_ctlcluster 16 second start 2>/dev/null || true
mkdir -p $S
DB=otp_$(basename $S | tr -c 'a-z0-9\n' '_')
PW=sbpw-$(head -c6 /dev/urandom | od -An -tx1 | tr -d ' \n')
for n in a b; do
  mkdir -p $S/$n/state/web $S/$n/log $S/$n/fakenm/profiles
  port=$([ $n = a ] && echo 5432 || echo 5433)
  ip=$([ $n = a ] && echo 10.99.0.1 || echo 10.99.0.2)
  i=$([ $n = a ] && echo 1 || echo 2)
  cat > $S/$n/config.json <<J
{"db_engine":"postgres","db_host":"127.0.0.1","db_port":$port,"db_name":"$DB","db_user":"$DB",
 "db_password":"$PW","node_name":"node$n","api_port":1986$i,"radius_auth_port":1812$i,
 "radius_acct_port":1813$i,"ha_address":"$ip"}
J
  cat > "$S/$n/fakenm/profiles/System eth0.nmconnection" <<P
[connection]
id=System eth0
802-3-ethernet.mtu=9000
ipv4.addresses=$ip/24,10.99.0.1$i/24
ipv4.dns=10.99.0.53
ipv4.dns-search=example.test
ipv4.gateway=10.99.0.254
ipv4.ignore-auto-dns=yes
ipv4.method=manual
ipv4.routes=10.50.0.0/16 10.99.0.254
ipv6.addresses=
ipv6.dns=
ipv6.gateway=
ipv6.method=disabled
P
  echo node$n > $S/$n/fakenm/hostname
  printf '127.0.0.1 localhost\n%s node%s\n' $ip $n > $S/$n/hosts
  : > $S/$n/power
  runuser -u postgres -- psql -p $port -XAtq -c "CREATE ROLE $DB LOGIN PASSWORD '$PW'" >/dev/null
  runuser -u postgres -- psql -p $port -XAtq -c "CREATE DATABASE $DB OWNER $DB" >/dev/null
done
echo "$S" > /home/claude/work/hasb/current
echo "sandbox made: $S, database $DB"
