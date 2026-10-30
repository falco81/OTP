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
