#!/bin/bash
# finalv.sh VERSION - the full run against the installed server (standalone): the suite, the tests of
# each release, the certificate and Windows sign-in, the pages in Chromium. One after the other - they
# share nginx, the database and ports. (Rebuilt 1.0.279: the one before lived outside git and was lost.)
V=${1:?version}
T=$(cd "$(dirname "$0")" && pwd)
cd "$T"
one() {   # one test: its last lines that count
  local t=$1; shift
  local d; d=$(dirname "$t"); local b; b=$(basename "$t")
  case "$b" in
    *.js) r=$( (cd "$d" && timeout 1200 node "$b" "$@" 2>&1) | grep -E '^FAIL|ALL [0-9]' | tr '\n' ' ');;
    *) r=$( (cd "$d" && timeout 1200 python3 "$b" $V "$@" 2>&1) | grep -E '^FAIL|ALL [0-9]|^[0-9]+/[0-9]+|Traceback|Error:' | tail -12 | tr '\n' ' ');;
  esac
  echo "== $t ${r:-(nothing said)}"
}
bash suite.sh $V
# dg/t_root puts an older version in (the way back): this one installed again
(cd ../build/out/otp-$V && bash install.sh --yes >/tmp/claude-0/finalv-install.log 2>&1) || echo "== install of $V again: FAIL"
sleep 8
newer() { local r=${1%%/*}; r=${r#r}; [ "$r" -gt "${V##*.}" ] 2>/dev/null; }
for t in r2[4-9]*/t_*.py r3[0-9]*/t_*.py cert/t_cert.py krb/t_krb.py; do
  newer "$t" && continue
  # r253/t_backend takes a file; r262/t_ops_fix a patch of its own day (both kept as they were)
  case "$t" in *_ha*|*/t_ha*|r261/*|r268/*|r253/t_backend.py|r262/t_ops_fix.py|r265/t_load.py|r265/t_pages_perf.py|r265/t_radius_perf.py) continue;; esac
  one "$t"
done
for t in r2[4-9]*/ui_*.js r3[0-9]*/ui_*.js cert/ui_cert.js krb/ui_krb.js; do
  newer "$t" && continue
  # the pages' tests of 1.0.259-1.0.273 that need a mail sink, an AD of 2025 or a PKI set up by hand first
  case "$t" in *_ha*|r259/ui_mfa_send.js|r267/ui_ad2025.js|r269/ui_chain.js|r273/ui_r273.js) continue;; esac
  one "$t"
done
echo "== done $(date +%T)"
