## 1.0.325 — 23 November 2026

**Bug fix (remote backups)**: putting back a backup sent from the page that failed (a passphrase mistyped, no room) deleted the file sent - up to 4 GB to send again. It is kept for another try for its hour.

**Bug fix (outgoing mail)**: a mail taken out of the queue while it was being sent came back into the list - as sent, or as waiting with nothing left to send. It stays out.

**Bug fix**: a column missing from a table with a constraint of its own (the used codes') was asked for with a broken ALTER TABLE every ten minutes for good. It is added.

