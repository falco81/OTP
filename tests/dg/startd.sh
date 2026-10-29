#!/bin/bash
# the daemon as otp.service would run it (no systemd here)
for p in $(pgrep -f "^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon"); do kill $p; done
sleep 2
mkdir -p /run/otp && chown otp:otp /run/otp 2>/dev/null
cd / && nohup runuser -u otp -- env MALLOC_ARENA_MAX=2 /usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon >> /tmp/claude-0/dg/daemon.out 2>&1 &
