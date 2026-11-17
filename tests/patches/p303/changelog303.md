## 1.0.303 — 17 November 2026

**Bug fixes** (the hunt, round 2): the pages during an upgrade.

- **An upgrade on the command line that failed always says so**: when the rescue could not take the node out of maintenance again, `install.sh`'s EXIT trap stopped half way (`set -e`) - the pages kept "being upgraded" for 30 min, hid "The daemon is not answering" and `/healthz` said maintenance.
- **Root's helper keeps what install.sh said when it stopped it** (its deadline, the service stopped): the step it was on and which version runs now - written over with "root checks the package".
- **Who started an upgrade, why it failed and its id only for a real sign-in**: a cookie of the right form was enough on `?api=upgrade-state`, the sign-in page and the answers while the daemon was away.
- **The sign-in page's "The upgrade to otp X failed"** is one sentence - in Czech it came out half translated.

