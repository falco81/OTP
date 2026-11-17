## 1.0.304 — 17 November 2026

**Bug fixes** (the hunt, round 3): the pages during an upgrade.

- **A save that fails during an upgrade is said**: *Not saved: otp is being upgraded - try again once it answers*. Everything that failed was silent while a cluster's upgrade ran - a change pressed on the node not being upgraded, refused or timed out, said nothing at all. A look that fails (asked again by itself) stays silent, the band explains it.
- **A daemon down after the upgrade ended is "not answering"**, not "in maintenance" for half an hour: an answer that said the upgrade was done or had failed was taken as "away for the upgrade".
- **The sign-in page during an upgrade loads itself again only when the daemon really answers** (its database open too - it loaded again every 2 s while the database was opening) **and never under somebody typing** a name, a password or a code: *It is back - load the page again* instead.

