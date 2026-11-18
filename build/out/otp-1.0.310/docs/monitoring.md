# Monitoring: Prometheus (1.0.173)

*Settings → Monitoring*, for a full administrator. Off until switched on.

Each node answers `https://NODE/metrics` in Prometheus' text format, for itself -
ask every node by its own address (the VIP address is one node at a time).

| Setting | |
|---|---|
| `metrics` | on/off |
| `metrics_token` | what Prometheus sends as `Authorization: Bearer ...` - *Make a token…* makes one and shows it once; kept sealed |
| `metrics_from` | the addresses or networks Prometheus asks from (`10.0.5.0/24, 2001:db8::/64`); empty: anywhere that reaches the pages, with the token |

nginx sends `/metrics` to `metrics.php`, which hands the token to the daemon; the
daemon checks it (and where the request comes from) before it says anything. A
wrong or missing token is a 401, a network not let in a 403, metrics switched off
a 404. An upgrade puts the `location = /metrics` into an nginx file of an older
version by itself.

## prometheus.yml

```yaml
scrape_configs:
  - job_name: otp
    scheme: https
    metrics_path: /metrics
    bearer_token_file: /etc/prometheus/otp.token      # the token, 0600, Prometheus' own
    tls_config:
      ca_file: /etc/prometheus/otp-ca.pem              # the CA of the nodes' certificates, if not a public one
    static_configs:
      - targets: ['10.0.5.11:443', '10.0.5.12:443']
```

The page shows this with the nodes' addresses filled in, and *What this node answers
now*.

## What it says

| Metric | |
|---|---|
| `otp_info{version,node,site,engine}` | 1 |
| `otp_start_time_seconds` | when the daemon started |
| `otp_database_up`, `otp_database_seconds` | the database answers, and how long `SELECT 1` took |
| `otp_radius_listening` | RADIUS listens |
| `otp_radius_requests_total{kind}` | RADIUS packets since the start: `packets`, `accept`, `reject`, `challenge`, `accounting`, `status`, `repeated`, `unknown`, `malformed`, `dropped`, `overflow`, `no_database`, `maintenance`... |
| `otp_radius_queued` | requests waiting for a worker |
| `otp_radius_last_day{result}` | Access-Requests of the last 24 hours (the database's - both nodes) |
| `otp_tokens{state}`, `otp_tokens{kind}` | tokens |
| `otp_clients`, `otp_realms`, `otp_directories` | how many |
| `otp_ha_node_up{node}`, `otp_ha_heartbeat_age_seconds{node}` | the cluster |
| `otp_ha_replication_running{name}`, `otp_ha_replication_errors_total{name}`, `otp_ha_replication_behind_bytes{name}` | replication, as this node's PostgreSQL sees it |
| `otp_certificate_expiry_timestamp_seconds{target,name}` | the pages' certificates - each node's and the VIP address's |
| `otp_mail_queue{state}` | mail waiting or failed |
| `otp_isemon_sent_total{target}`, `otp_isemon_trouble{target}`, `otp_isemon_dropped_total` | isemon |
| `otp_siem_sent_total{target}`, `otp_siem_trouble{target}`, `otp_siem_dropped_total` | syslog / SIEM |
| `otp_alerts_open{level}`, `otp_alert{key,level}` | what the alerts see wrong now |
| `otp_high_security` | high security on |
| `otp_scrape_seconds` | how long the answer took |

## Alerts, for example

```yaml
groups:
  - name: otp
    rules:
      - alert: OtpDown
        expr: up{job="otp"} == 0 or otp_database_up == 0 or otp_radius_listening == 0
        for: 2m
      - alert: OtpReplication
        expr: otp_ha_replication_running == 0 or otp_ha_replication_behind_bytes > 100e6
        for: 5m
      - alert: OtpCertificate
        expr: otp_certificate_expiry_timestamp_seconds - time() < 14 * 86400
      - alert: OtpAlerts
        expr: otp_alerts_open{level="bad"} > 0
        for: 10m
```

## SNMPv3 (1.0.182)

Each node answers SNMPv3 itself: an agent of the otp daemon, in a thread of its
own - no snmpd, nothing in RADIUS' way. *Settings → Monitoring → SNMPv3*.

- **authPriv only.** One user (securityName), the same on every node, with a
  passphrase for authentication and one for encryption (12 characters at least,
  kept sealed like every secret of otp). noAuthNoPriv and authNoPriv are not
  answered. Authentication HMAC-SHA-256 (default), -SHA-512 or -SHA-1 (RFC 3414,
  RFC 7860); encryption AES-128 (default) or AES-256 (RFC 3826; AES-256 with the
  key extended as net-snmp and Zabbix do it - their `AES256`, not Cisco's
  `AES256C`).
- **Each node an engine of its own** - its engine ID made once and kept in
  `/var/lib/otp/snmp-engine`, the engine boots counted in `snmp-boots`. The page
  shows each node's engine ID (click to copy) - a trap receiver needs it.
- **Port 161/udp** on every address of the node (or one, *Listen on*, set for each
  node). Binding 161 needs `CAP_NET_BIND_SERVICE`: `otp.service` has it from
  1.0.182 (`install.sh --upgrade` puts the unit in); nothing else is given to the
  daemon. Where the system's snmpd has 161 already, give otp another port.
- **Only from**: the networks the monitoring asks from; the firewall lets in these
  only (or everybody when none is set) - by itself while SNMPv3 is on, where otp
  looks after the firewall (*Settings → Firewall and access*), and the rule goes
  when it is switched off. Anything else is not answered at all.
- *Settings → Firewall and access* shows it among what otp lets in by itself
  (*SNMPv3*: the port, from where) while it is on.
- Read only: GET, GETNEXT and GETBULK. A SET is refused (notWritable).
- *Ask it* on each node's card: the node asks its own agent on 127.0.0.1 as a
  manager would - discovery, then a GET authPriv.

### What it answers

| OID | |
|---|---|
| `1.3.6.1.2.1.1` | the system group: sysDescr (otp, the version, the node), sysObjectID, sysUpTime, sysContact, sysName, sysLocation |
| `1.3.6.1.6.3.10.2.1` | the engine: its ID, boots, time |
| `1.3.6.1.6.3.15.1.1` | usmStats: unknown users, wrong digests, not in the time window... |
| `1.3.6.1.4.1.8072.9999.9999.7` | **OTP-MIB** (`deploy/OTP-MIB.txt`, and *Download OTP-MIB* on the page) - below |

Under `.7` (1.0.281: everything the application can tell, typed):

| OID `.7.` | | |
|---|---|---|
| `1` | `otpInfo` | the version, the node, the site, the database engine, high security, in a cluster, uptime |
| `2.1`-`2.14` | `otpRadius` | listening, waiting for a worker; packets, Access-Accept/-Reject/-Challenge, accounting, Status-Server, dropped, malformed, from no client, sent again, without the database, in maintenance - Counter64 since the daemon started |
| `2.15`-`2.20`, `2.30` | | the RADIUS clients, realms and directories set; accepted, rejected and challenged in the last 24 hours (both nodes), and a table of every result |
| `3` | `otpDatabase` | up, the latency of `SELECT 1` (microseconds) |
| `4` | `otpTokens` | all, active, pending, disabled, used in 30 days, never used |
| `5` | `otpAlerts` | how many bad and warn, and a table of each thing wrong now (key, level, title, words) |
| `6` | `otpCertificates` | the certificates of the pages: each node's and the VIP address's, days left, the end |
| `7` | `otpCluster` | the nodes: heard from, since when |
| `9` | `otpMetrics` | every sample of `/metrics`: name, labels, value (text) |
| `10` | `otpHost` | the machine: CPU time idle and in all (Counter64, a rate is the monitor's to make), cores, the load (×100), memory and swap (KiB), bytes read and written by the disks, received and sent by the network cards (Counter64), uptime; `otpFsTable` - the file systems otp lives on: size, used, free (KiB), % used, % of inodes |
| `11` | `otpDirectories` | each directory (Active Directory): used, whether a server of it answers this node, its servers |
| `12` | `otpHa` | in a cluster, a VIP address set, **this node holds it**, the address; the replication - each subscription running and its errors, each slot how far behind (bytes) and its WAL |
| `13` | `otpBackups` | the nightly copy: on, when, its age; the backups sent away: on, the newest went, the newest good one and its age (4294967295: none) |
| `14` | `otpMail` | the mail of both nodes: sending, waiting, sent, failed, expired |
| `15` | `otpSignIn` | Windows, the certificate, no password at all, the second step; CRLs kept and not had; OCSP (off/first/only/both), the answers kept and those not good |
| `16` | `otpClock` | the clock guard holding codes back, how it is set, the offset from the time servers, the skew from the other node or the directory, the correction (ms) |
| `17` | `otpLogs` | the logs sent to isemon and to a SIEM: on, in trouble, lines sent and dropped |
| `0` | `otpNotifications` | the traps: raised, cleared, a test |

otp has no enterprise number of its own: its objects are under net-snmp's
`netSnmpPlaypen` (`.1.3.6.1.4.1.8072.9999.9999`), `.7`. Load `OTP-MIB.txt` into
the monitoring (it imports `NET-SNMP-MIB`, which net-snmp and Zabbix have) - or
use the numbers.

```
snmpwalk -v3 -l authPriv -u otpmon -a SHA-256 -A '...' -x AES -X '...' otp1 1.3.6.1.4.1.8072.9999.9999.7
snmpget  -v3 -l authPriv -u otpmon -a SHA-256 -A '...' -x AES -X '...' otp1 \
         1.3.6.1.4.1.8072.9999.9999.7.5.1.0 1.3.6.1.4.1.8072.9999.9999.7.2.1.0
```

### Zabbix 7.0: the template (1.0.281)

*Settings → Monitoring → SNMPv3 → Download the Zabbix 7.0 template* gives
`otp_by_snmp_zabbix7.yaml` (also `deploy/zabbix/` in the package) - the template
**otp by SNMP**, made for the version it comes with:

- **Items** for every object above - RADIUS per second (accepted, rejected,
  challenged, accounting, trouble), the queue, the database and its latency, the
  tokens, the machine (CPU utilization and memory utilization worked out, the
  load, disk and network per second, uptime), the VIP address, the backups, the
  mail, the ways of signing in with CRLs and OCSP, the clock, the logs sent away;
  the version, the site and the system group into the host's inventory.
- **Discovery** (one walk of a table, the rows found by themselves): every
  problem otp sees - each **a problem of its own in Zabbix while it lasts**, gone
  when it is right; the certificates of the pages (days left); the nodes of the
  cluster; the file systems; the directories; the replication both ways; the
  RADIUS results of the last day.
- **Triggers**: no SNMP answer, RADIUS not listening, the database down or slow,
  RADIUS answered without the database, problems and warnings otp sees, CPU and
  memory, the space and the inodes of a file system, a certificate ending (21 and
  7 days), a node not heard from, a directory that does not answer, the
  replication stopped, behind or lost, no nightly copy, a backup sent away failed
  or late, mail failing or piling up, a CRL not had, an OCSP answer not good, the
  clock guard holding codes back, the clock off, the logs in trouble, the VIP
  address moved, otp restarted or updated. The limits are macros
  (`{$OTP.CPU.UTIL.CRIT}`, `{$OTP.FS.PUSED.WARN}`, `{$OTP.CERT.EXPIRY.WARN}`,
  `{$OTP.RBACKUP.AGE.MAX}`...), to be changed on the host.
- **Graphs** and a **dashboard** of five pages: *Overview* (RADIUS, the database,
  problems, warnings, the active tokens, the version; CPU and memory as gauges;
  the RADIUS requests; the problems), *RADIUS*, *Machine*, *Cluster and
  directories*, *Certificates, sign-in, backups*.

In Zabbix 7.0: *Data collection → Templates → Import* the file. Then a host for
**each node** (not the VIP address - each node answers for itself): an SNMP
interface at the node's own address and port, SNMP version 3, security level
*authPriv*, the security name, *SHA256* and *AES128* (or what was chosen above)
with the two passphrases; link **otp by SNMP**. The host's *Monitoring →
Dashboards* has the dashboard. A template of a newer otp is imported over the one
before (its objects keep their UUIDs). For the traps, see below - Zabbix takes
them with `snmptrapd` and its SNMP trap items.

### Traps

*Traps when something is wrong*: an SNMPv2-Trap, authPriv, from the node that
sends the alerts (the one with the VIP address, or the first alive) to every
receiver in *Where traps go* (`host` or `host:port`, 162 by default):

- `otpAlertRaised` (`.7.0.1`) when something goes wrong - what the alerts see
  (*Alerts and reports*), after their delay - and again when a warning becomes
  bad;
- `otpAlertCleared` (`.7.0.2`) when it is right again;
- `otpTestTrap` (`.7.0.3`) from *Send a test trap*.

Each carries `otpTrapKey`, `otpTrapLevel`, `otpTrapTitle`, `otpTrapSaid` and
`otpTrapNode`. Their own record of what was said, apart from the mails: traps go
whether the alerts' mails are on or not.

The receiver knows the user with **each node's engine ID** (a trap is sent by the
node's own engine), in `snmptrapd.conf`:

```
createUser -e 0x80001f8805... otpmon SHA-256 '...' AES '...'
createUser -e 0x80001f8805... otpmon SHA-256 '...' AES '...'
authUser log,execute otpmon priv
```

The page writes those lines with the engine IDs filled in.

## The alerts of the database and of the VIP address (1.0.194)

*Settings → Alerts and reports* has a switch for each:

- **The database and its replication**: the replication stopped, or the database
  of a node in trouble (RADIUS could not use it).
- **The VIP address (VRRP)**: the VIP address on no node, or on both (the nodes do
  not see each other over VRRP), a node whose keepalived gave it up (FAULT), or
  keepalived not running on a node.

Neither is mailed while the cluster is worked on - a node in maintenance, an
upgrade, the system's updates or a restart going on - nor for 10 minutes after
the last of them, while the replication catches up and the VIP address settles.
The same outside of them is mailed as any alert, after *Only once it has lasted*.
One already mailed is not said to be over because maintenance started: it is
kept as it was until it is looked at again.
