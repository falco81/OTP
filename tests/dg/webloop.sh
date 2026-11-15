#!/bin/bash
# otp-web.path, as it were (a container without systemd): root's helper run whenever one of the
# files it watches is there.
while true; do
  for f in /var/lib/otp/web/request.json /var/lib/otp/web/*.ask; do
    if [ -e "$f" ]; then
      /usr/bin/python3 -I /usr/local/lib/otp/otp_web.py >> /tmp/claude-0/webloop.log 2>&1
      break
    fi
  done
  sleep 1
done
