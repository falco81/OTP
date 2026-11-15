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
for t in r2[4-9]*/t_*.py cert/t_cert.py krb/t_krb.py; do
  case "$t" in *_ha*|*/t_ha*|r261/*|r268/*|r265/t_load.py|r265/t_pages_perf.py|r265/t_radius_perf.py) continue;; esac
  one "$t"
done
for t in r2[4-9]*/ui_*.js cert/ui_cert.js krb/ui_krb.js; do
  case "$t" in *_ha*) continue;; esac
  one "$t"
done
echo "== done $(date +%T)"
