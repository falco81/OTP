## 1.0.302 — 17 November 2026

**Bug fixes** (the hunt, round 1): SELinux's root helper.

- **Another program's refusal on otp's files is never offered as a rule**: a rule for `user_t` or a confined daemon reading `/run/otp/api-token` was ticked on the card. A program is otp's by its executable under `/usr/local/lib/otp` or otp's own command line in full - never by a name it gives itself (`comm` "otp-…").
- **restorecon only on otp's own real paths**: the path is what a program asked for - with `..`, or through a link inside otp's folder, `restorecon -R` went wherever it led (up to `/`).
- **otp_local's list is written only once the policy took it**: a take-away whose `semodule` failed (its store locked by dnf) left a rule in the policy that the card no longer listed nor could take away; the file goes back as the policy has it.
- **A batch whose module does not load keeps its other fixes** (a boolean, a label, a port) as put right; **a port of the type it needs already** is settled - it was said to be "another service's".

