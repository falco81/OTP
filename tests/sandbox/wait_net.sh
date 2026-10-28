until grep -q "network: done\|came up without\|replication is not running" /tmp/nodeb/log/otp.log; do sleep 3; done
