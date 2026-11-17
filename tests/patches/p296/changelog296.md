## 1.0.296 — 17 November 2026

**Bug fixes** (the hunt, third round).

- **The RADIUS server's counters** (Dashboard, the metrics, SNMP): *accept*, *challenge* and *reject* are counted once, when the answer is ready - a request whose answer could not be built was counted as accepted and taken back, and counts from many requests at once could be lost or make the dashboard fail with "dictionary changed size".
- **The periodic report by mail**: one that did not go (mail off or failing) is tried again in 30 minutes - it was taken as sent and the period was lost until the next one; one waiting in the outgoing mail counts as sent.

