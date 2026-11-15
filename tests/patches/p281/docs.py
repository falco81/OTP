# 1.0.281 docs/monitoring.md: what the agent answers now, and Zabbix 7.0 - python3 docs.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'
F = O + 'docs/monitoring.md'
s = open(F).read()


def ed(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


ed("""| `1.3.6.1.4.1.8072.9999.9999.7` | **OTP-MIB** (`deploy/OTP-MIB.txt`): the version, node, database engine, high security; RADIUS (listening, queued, packets, accepts, rejects, challenges... as Counter64); the database (up, latency); the tokens; the alerts (how many bad and warn, and a table of each); the certificates (days left); the nodes of the cluster; and `otpMetricTable` - every sample of `/metrics`, name, labels and value |""",
   """| `1.3.6.1.4.1.8072.9999.9999.7` | **OTP-MIB** (`deploy/OTP-MIB.txt`, and *Download OTP-MIB* on the page) - below |""")
ed("""otp has no enterprise number of its own: its objects are under net-snmp's""",
   """Under `.7` (1.0.281: everything the application can tell, typed):

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

otp has no enterprise number of its own: its objects are under net-snmp's""")
ed("""Zabbix: an SNMP interface on each node, SNMPv3, security level authPriv, the
user, *SHA256* and *AES128* (or what was chosen) with the passphrases; items with
the OIDs above (`otpAlertsBad.0` > 0, `otpRadiusListening.0` = 0,
`otpDbUp.0` = 0...).""",
   """### Zabbix 7.0: the template (1.0.281)

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
them with `snmptrapd` and its SNMP trap items.""")
open(F, 'w').write(s)
print('docs patched')
