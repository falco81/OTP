#!/bin/bash
# The two root helpers, once a second. helpers.sh VERSION
V=${1:?version}
while true; do
  for n in a b; do
    ( . /home/claude/work/hasb/env.sh $n
      python3 -I /home/claude/build/out/otp-$V/deploy/otp_web.py >>$S/$n/helper.log 2>&1 )
  done
  sleep 1
done
