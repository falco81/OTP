## 1.0.306 — 18 November 2026

**Bug fixes** (the hunt, round 5): mail, alerts, SNMP, RADIUS repeats.

- **An alert or a report that some recipients took is sent**: with one address gone (550), the same alert went to every recipient again every 15 min and the report every 30, for as long as it lasted. The address that refused it is said in the alerts' log.
- **The report's "Who was refused" counts refusals**, not the challenges of a sign-in in two windows: every user of such a realm was listed, as many times as they signed in.
- **SNMP**: the clock guard's values (ms) and the time of the last backup are kept in an Integer32 - a clock months off, or a time after 2038, made a strict manager refuse the whole answer.
- **RADIUS: a repeat of a request refused late is answered**: the late refusal was kept for repeats only once it was written down; with the database slower than the delay, a NAS repeat arriving after the refusal went was swallowed as "repeated" and got nothing.

