## 1.0.305 — 17 November 2026

**Bug fixes** (the hunt, round 4): SELinux.

- **Two refusals of one event each get audit2why's word** (a folder searched and its file read): the second wrote over the first, which then was never "allowed now", never got its boolean - and still counted against enforcing.
- **A rule the same as one in otp_local already is not put in twice** (two programs of otp's refused the same): taking one away left the other allowing it.
- **A boolean, a folder, a port done once a batch**: each `setsebool -P` builds the whole policy again - a batch of many took longer than the pages wait.

