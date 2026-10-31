# . env.sh a|b  - the environment of one node (daemon, CLI, root helper)
n=$1; S=$(cat /home/claude/work/hasb/current); H=/home/claude/work/hasb
export OTP_CONFIG=$S/$n/config.json OTP_STATE=$S/$n/state OTP_LOGDIR=$S/$n/log OTP_STAY_ROOT=1
export OTP_HA_CA=$S/$n/ha-ca.pem OTP_HA_NO_RESTART=1 OTP_NET_LOOPBACK_OK=1
export PGPORT=$([ $n = a ] && echo 5432 || echo 5433)
export FAKENM_DIR=$S/$n/fakenm OTP_NMCLI=$H/nmcli OTP_HOSTNAMECTL=$H/hostnamectl
export OTP_HOSTS_FILE=$S/$n/hosts OTP_POWER_CMD=$S/$n/power OTP_VIP_NO_SERVICES=1
export OTP_NET_SNAP_DIR=$S/$n/netsnap OTP_NM_PROFILE_DIRS=$S/$n/fakenm/profiles/
export OTP_SYSCTL6=$S/$n/sysctl6.conf OTP_BTIME_FILE=$S/$n/btime
export OTP_CHRONY_CONF=$S/$n/chrony.conf OTP_NTP_NO_SERVICE=1
export OTP_CONSOLE_FLAG=$S/$n/console-login
export OTP_RUN=$S/$n/run
export OTP_VIP_KA_CONF=$S/$n/keepalived.conf
export OTP_VIP_HEALTH_URL=none
export OTP_VIP_NGINX_DIR=$S/$n/nginx
export OTP_VIP_CERT_DIR=$S/$n/certs
export OTP_OSUP_PM=/home/claude/ws/tests/host/fakepm.sh
export OTP_OSUP_LOCK=$S/$n/osup.lock
export OTP_ACME_EVERY=5 OTP_ACME_SETTLE=0.5 OTP_ACME_RETRY=20
export OTP_VIP_HERE_BY_ROLE=1
