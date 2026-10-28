#!/bin/bash
# start.sh a|b VERSION [reboot] - (re)start one daemon; "reboot" gives it a new
# boot time, as a restart of the machine would.
n=${1:?node}; V=${2:?version}
. /home/claude/work/hasb/env.sh $n
for p in $(pgrep -f "otp.py --daemon"); do
  tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -qx "OTP_CONFIG=$OTP_CONFIG" && kill $p
done
sleep 2
[ -f $OTP_BTIME_FILE ] || date +%s > $OTP_BTIME_FILE
[ "$3" = reboot ] && date +%s > $OTP_BTIME_FILE
nohup python3 -I /home/claude/build/out/otp-$V/otp.py --daemon >> $S/$n/daemon.out 2>&1 &
