#!/bin/bash
# suite.sh VERSION - every test that runs without the sandbox, one after the other
V=${1:?version}
cd "$(dirname "$0")"
python3 -I ../build/out/otp-$V/test/checks.py 2>/dev/null | tail -1 || true
for t in load/t_latency.py acme/t_acme.py isemon/t_isemontls.py isemon/t_isetest.py metrics/t_metrics.py snmp/t_snmp.py ask/t_ask.py verify/t_verify.py hisec/t_hisec.py exp/t_totpzip.py siem/t_siem.py \
         alerts/t_alerts.py power/t_power.py host/t_host.py sshd/t_sshd.py sshd/t_pamradius.py sshd/t_sshotp_api.py chal/t_chal.py cz/t_cz.py \
         adm/t_admin_groups.py cli/t_cli.py round/t_round1.py round/t_round2.py round/t_round3.py round/t_round4.py round/t_round5.py round/t_round6.py round/t_round7.py round/t_round8.py round/t_round9.py round/t_round10.py round/t_round11.py round/t_round12.py round/t_round13.py portal/t_firstcode.py dirmap/t_dirmap.py dirpw/t_dirpw.py dbguard/t_dbguard.py dbguard/t_dbguard_host.py fullrestore/t_fullrestore.py acmepush/t_acmepush.py split/t_split.py clock/t_clock.py dg/t_down.py dg/t_root.py; do
  [ -f "$t" ] || continue
  echo "== $t $( (cd $(dirname $t) && timeout 900 python3 $(basename $t) $V 2>&1) | grep -E '^FAIL|ALL [0-9]|^[0-9]+/[0-9]+' | tr '\n' ' ')"
done
