set -e
cd /home/claude/build && bash build.sh
cp out/otp-1.0.153/otp.py /usr/local/lib/otp/otp.py
cp out/otp-1.0.153/deploy/otp_web.py /usr/local/lib/otp/otp_web.py
cp -r out/otp-1.0.153/web/* /var/www/otp/
PATH=/home/claude/shim:$PATH systemctl restart otp
bash /tmp/claude-0/up/startb.sh
sleep 4
