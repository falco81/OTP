F=/tmp/claude-0/fakenm
for i in $(seq 1 7200); do
 OTP_NMCLI=$F/nmcli OTP_HOSTNAMECTL=$F/hostnamectl OTP_HOSTS_FILE=$F/hosts_a OTP_POWER_CMD=$F/power_a OTP_CHRONYC=$F/chronyc OTP_TIMEDATECTL=$F/timedatectl OTP_CHRONY_CONF=$F/chrony_a.conf OTP_NTP_NO_SERVICE=1 OTP_VIP_NO_SERVICES= python3 -I /usr/local/lib/otp/otp_web.py >/dev/null 2>&1
 OTP_STATE=/tmp/nodeb/state OTP_NMCLI=$F/nmcli OTP_HOSTNAMECTL=$F/hostnamectl OTP_HOSTS_FILE=$F/hosts_b OTP_POWER_CMD=$F/power_b OTP_CHRONYC=$F/chronyc OTP_TIMEDATECTL=$F/timedatectl OTP_CHRONY_CONF=$F/chrony_b.conf OTP_NTP_NO_SERVICE=1 python3 -I /usr/local/lib/otp/otp_web.py >/dev/null 2>&1
 sleep 1; done
