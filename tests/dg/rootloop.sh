#!/bin/bash
# otp-upgrade.path, as it were: a request taken by root, then otp restarted
while true; do
  if [ -f /var/lib/otp/upgrade/request.json ]; then
    /usr/local/lib/otp/python -I /usr/local/lib/otp/otp_upgrade.py >> /tmp/claude-0/dg/rootloop.log 2>&1
    echo "$(date +%T) served; restarting otp" >> /tmp/claude-0/dg/rootloop.log
    bash /tmp/claude-0/dg/startd.sh
  fi
  sleep 2
done
