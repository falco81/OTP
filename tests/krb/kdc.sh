#!/bin/bash
# kdc.sh DIR - a Kerberos realm CORPNET.LOC of its own for the tests (MIT krb5-kdc, port 18888),
# made once in DIR and started if it is not running. The principals: the people of the mock
# directory (falco: full admin, pkolar: read only, nested and outsider: no role, gone: switched
# off there, edvorak: its state unreadable, ghost: not in the directory, admin: a local account of otp), the web service's names, and two names of one
# key (svc1, svc2: a ticket for svc2 is taken by a keytab of svc1 alone).
# Each person has a keytab DIR/<name>.keytab, and a ticket made by: kinit -k -t ... .
set -e
PEOPLE='falco edvorak jnovak nogroups ghost admin pkolar nested outsider gone'
D=${1:-/tmp/claude-0/kdc}
mkdir -p "$D"
cd "$D"
export KRB5_CONFIG=$D/krb5.conf KRB5_KDC_PROFILE=$D/kdc.conf
cat > krb5.conf <<EOF
[libdefaults]
  default_realm = CORPNET.LOC
  dns_lookup_kdc = false
  dns_lookup_realm = false
  rdns = false
[realms]
  CORPNET.LOC = {
    kdc = 127.0.0.1:18888
  }
EOF
cat > kdc.conf <<EOF
[kdcdefaults]
  kdc_ports = 18888
  kdc_tcp_ports = 18888
[realms]
  CORPNET.LOC = {
    database_name = $D/principal
    key_stash_file = $D/stash
    acl_file = $D/kadm5.acl
    supported_enctypes = aes256-cts-hmac-sha1-96:normal aes128-cts-hmac-sha1-96:normal
  }
EOF
if [ ! -f "$D/principal" ]; then
  kdb5_util create -s -r CORPNET.LOC -P "$(head -c 18 /dev/urandom | base64)" >/dev/null 2>&1
  for p in HTTP/otp.corpnet.loc HTTP/nodea.corpnet.loc HTTP/nodeb.corpnet.loc HTTP/other.corpnet.loc; do
    kadmin.local -q "addprinc -randkey $p" >/dev/null 2>&1
  done
  PW=$(head -c 12 /dev/urandom | base64)
  for p in HTTP/svc1.corpnet.loc HTTP/svc2.corpnet.loc; do
    printf '%s\n%s\n' "$PW" "$PW" | kadmin.local -q "addprinc -e aes256-cts-hmac-sha1-96:onlyrealm $p" >/dev/null 2>&1
  done
  kadmin.local -q "ktadd -k $D/http.keytab HTTP/otp.corpnet.loc HTTP/nodea.corpnet.loc HTTP/nodeb.corpnet.loc" >/dev/null
  kadmin.local -q "ktadd -norandkey -k $D/svc1.keytab HTTP/svc1.corpnet.loc" >/dev/null
  kadmin.local -q "ktadd -k $D/other.keytab HTTP/other.corpnet.loc" >/dev/null
fi
# The people (added to a realm made before them too).
for p in $PEOPLE; do
  if [ ! -f "$D/$p.keytab" ]; then
    kadmin.local -q "addprinc -randkey $p" >/dev/null 2>&1
    kadmin.local -q "ktadd -k $D/$p.keytab $p" >/dev/null
  fi
done
chmod 644 "$D"/*.keytab
# Its own KDC, known by its pid file (never looked for by name: another test's may run).
if ! { [ -f "$D/kdc.pid" ] && kill -0 "$(cat "$D/kdc.pid")" 2>/dev/null; }; then
  krb5kdc -r CORPNET.LOC -P "$D/kdc.pid"
  sleep 1
fi
for p in $PEOPLE; do
  KRB5CCNAME=FILE:$D/$p.cc kinit -k -t "$D/$p.keytab" "$p"
done
echo "kdc ready in $D"
