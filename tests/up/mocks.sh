#!/bin/bash
cd /tmp/claude-0
(cd /home/claude/build/out/otp-1.0.157/test && exec python3 mockldap.py 3899 >/tmp/claude-0/mock.log 2>&1) &
python3 chal/smtpsink.py >/tmp/claude-0/smtpsink.out 2>&1 &
python3 chal/tlssink.py >/tmp/claude-0/tlssink.out 2>&1 &
python3 zigmock/mocksms.py 18110 admin trbsecret >/tmp/claude-0/zig.out 2>&1 &
python3 zigtls/tls.py >/tmp/claude-0/zigtls.out 2>&1 &
wait
