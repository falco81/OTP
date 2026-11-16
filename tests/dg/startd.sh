#!/bin/bash
# the daemon as otp.service would run it (no systemd here)
for p in $(pgrep -f "^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon"); do kill $p; done
# gone before the new one starts, as systemd waits for the stop (30 s at most)
for i in $(seq 1 60); do pgrep -f "^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon" >/dev/null || break; sleep 0.5; done
sleep 1
mkdir -p /run/otp && chown otp:otp-web /run/otp 2>/dev/null
cd / && nohup runuser -u otp -- env MALLOC_ARENA_MAX=2 OTP_CDP_LOCAL=1 /usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon >> /tmp/claude-0/dg/daemon.out 2>&1 &
