#!/bin/bash
# suite.sh VERSION - every test that runs without the sandbox, one after the other
V=${1:?version}
cd "$(dirname "$0")"
python3 -I ../build/out/otp-$V/test/checks.py 2>/dev/null | tail -1 || true
for t in acme/t_acme.py ask/t_ask.py verify/t_verify.py hisec/t_hisec.py exp/t_totpzip.py siem/t_siem.py \
         alerts/t_alerts.py power/t_power.py host/t_host.py sshd/t_sshd.py chal/t_chal.py cz/t_cz.py \
         adm/t_admin_groups.py dg/t_down.py dg/t_root.py; do
  [ -f "$t" ] || continue
  echo "== $t $( (cd $(dirname $t) && timeout 900 python3 $(basename $t) $V 2>&1) | grep -E '^FAIL|ALL [0-9]|^[0-9]+/[0-9]+' | tr '\n' ' ')"
done
