#!/bin/bash
# stands in for opt-upgrade.path on both test nodes
while true; do
  if [ -e /var/lib/otp/upgrade/request.json ]; then
    echo "$(date +%T) A: helper" >> /tmp/claude-0/up/watch.log
    python3 -I /usr/local/lib/otp/otp_upgrade.py >> /tmp/claude-0/up/watch.log 2>&1
  fi
  if [ -e /tmp/nodeb/state/upgrade/request.json ]; then
    echo "$(date +%T) B: helper" >> /tmp/claude-0/up/watch.log
    OTP_STATE=/tmp/nodeb/state python3 -I /usr/local/lib/otp/otp_upgrade.py >> /tmp/claude-0/up/watch.log 2>&1
    echo "$(date +%T) B: restart" >> /tmp/claude-0/up/watch.log
    bash /tmp/claude-0/up/startb.sh
  fi
  sleep 1
done
