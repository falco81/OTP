# The light HA sandbox (1.0.140)

Two otp nodes on one machine, without nginx, PHP or keepalived: PostgreSQL 16
clusters `main` (5432, node A) and `second` (5433, node B), addresses
10.99.0.1 / 10.99.0.2 (and .3 for a trial) on `lo`, a fake NetworkManager
(`nmcli`, `hostnamectl` here, the profile as a file), the root helpers in a
loop, the daemons as root. Nothing is deleted; each run gets a new folder.

    apt-get install -y iproute2; pip install psycopg2-binary
    bash setup.sh /tmp/sb1                       # remembered in ./current
    . env.sh a; python3 -I .../otp.py --ha-setup --ha-peer 10.99.0.2 --ha-peer-port 5433 \
        --ha-address 10.99.0.1 --yes --ha-bundle /tmp/sb1/bundle.json
    # both clusters: a last pg_hba line  host all all 10.99.0.0/24 scram-sha-256
    # (both nodes share one source address here), then pg_ctlcluster 16 X reload
    . env.sh b; OTP_HA_PASSPHRASE=... python3 -I .../otp.py --ha-join /tmp/sb1/bundle.json \
        --node-name nodeb --ha-address 10.99.0.2 --yes
    mkdir -p /tmp/sb1/{a,b}/state/web
    nohup bash helpers.sh VERSION &  ;  bash start.sh a VERSION; bash start.sh b VERSION
    . env.sh a; otp --ha-tls-repair; otp --set net_confirm_min=1
    . env.sh b; python3 -I t_trial.py VERSION [keep] [ADDR/PREFIX HOSTNAME]

`t_trial.py` puts node B on a new network on trial, simulates the reboots
(start.sh ... reboot) and compares eleven things before and after.
