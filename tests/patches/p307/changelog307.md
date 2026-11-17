## 1.0.307 — 17 November 2026

**Bug fixes** (the hunt, round 6): backups and the outgoing mail.

- **Age never takes the newest three backups away**: a clock stepped ahead, or backups that failed longer than the days kept, took every older backup away at once - one left.
- **The weekly check of a node that does not make the night's copy** (one database for the cluster - the other node takes the night's turn) is not "cannot be put back".
- **The outgoing mail decides on each mail as it is now**, not as it was when its tick began: a slow tick (the server away) gave up a mail sent again by hand meanwhile.

