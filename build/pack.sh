#!/bin/bash
# pack.sh VERSION - the languages built, the folder signed, the archive made.
# Run after every change to out/otp-VERSION, last of all (1.0.37).
set -euo pipefail
v=${1:?version}
cd /home/claude/build
(cd /home/claude/i18n && python3 make_cs.py >/dev/null)
bash sign.sh "out/otp-$v"
rm -f "out/otp-$v.tar.gz"
(cd out && tar --owner=0 --group=0 -czf "otp-$v.tar.gz" "otp-$v")
echo "out/otp-$v.tar.gz"
