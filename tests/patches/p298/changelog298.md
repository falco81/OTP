## 1.0.298 — 17 November 2026

**Bug fixes** (the hunt, fifth round).

- **Backups → the weekly check** with no destination switched on is not started - it failed at once, wrote nothing, and was started again every hour.
- **Forgetting a check of another node's backup** writes that node's row in place only - both nodes writing it at once could meet as one key twice in the replication.
- **SNMP: the end of a certificate after 2038** is given as the largest Integer32 - a strict manager refused the whole answer.
- **An administrator's second step**: the answer of a way given up (another way chosen while the QR code was being made or the code sent) is no longer drawn into the way now shown.

