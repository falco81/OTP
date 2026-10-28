#!/bin/bash
p=$(cat /tmp/nodeb/state/otp.lock 2>/dev/null | tr -dc 0-9)
if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then kill "$p"; for i in $(seq 1 20); do kill -0 "$p" 2>/dev/null || break; sleep 0.5; done; fi
mkdir -p /tmp/nodeb/log; chown -R otp:otp /tmp/nodeb/log /tmp/nodeb/state 2>/dev/null
cd /tmp
setsid runuser -u otp -g otp -G otp-web -- env OTP_VIP_HEALTH_URL=none OTP_RUN=/run/otp-b OTP_CONFIG=/tmp/nodeb/config.json OTP_STATE=/tmp/nodeb/state OTP_LOGDIR=/tmp/nodeb/log OTP_UPGRADE_DRAIN_S=5 /opt/uvpy/cpython-3.9.25-linux-x86_64-gnu/bin/python3.9 /usr/local/lib/otp/otp.py --daemon > /tmp/nodeb/out.log 2>&1 < /dev/null &
