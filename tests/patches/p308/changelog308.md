## 1.0.308 — 17 November 2026

**Bug fixes** (the hunt, round 7): an administrator's second step.

- **Wrong codes are counted on the account** too, in the database - every sign-in and node together: signing in again with the password gave five more guesses each time. Past 20 in a day no more codes are taken until another full administrator resets the second step (*Accounts*) or the day is over.
- **Codes by mail or SMS are limited per account and per address**, as the portal's are (`code_send_max` in `code_send_window_min`): five per sign-in only, and signing in again - or setting the step up, with any address or number typed in - sent more without end.

