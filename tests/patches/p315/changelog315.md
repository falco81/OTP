## 1.0.315 — 21 November 2026

**New on the command line and in the console** (*Certificates, updates, restarts, tests*), as the pages have them:

- `otp --alerts` – what is wrong now, as *Settings → Alerts* shows it; exit code 1 when anything is bad, so a monitoring script can ask. `--alerts check` looks again now, `--alerts test` mails a test alert, `--alerts report` mails the last period's report, `--alerts forget` forgets what was sent.
- `otp --mailq [open|waiting|sending|sent|failed|expired]` – the outgoing mail; `--mailq retry-all` sends what waits or failed again, `--mailq drop-sent` / `drop-failed` takes it out (`--yes`). `--mailq-one ID` shows one mail and every try of it; `--mailq-retry ID,ID` and `--mailq-drop ID,ID` do it to those only.
- `otp --sessions` – who is signed in to the pages; `otp --session-end ID --yes` ends a sign-in (written down in the events, as on the pages).
- `otp --firewall` – otp's firewall rules and who may reach the pages; `--firewall on` / `off --yes` puts them on or takes them away. `otp --web-access admin=any --yes` (or `admin=NET,NET`, also `portal=`, `api=` …) sets who may reach which pages – the way back in when the pages were closed to the wrong network. A change is kept only for the trial time unless `otp --change-keep fw` keeps it, as on the pages.

**Bug fix**: what an update left to be done by hand went out as an alert cut in the middle of a word after 300 characters (*… on Settings → Firewall and ac*). It is now cut only past 600 characters, where a word ends, and the cut is shown (…).

**Bug fix**: an option that only goes with another (`--pending`, `--yes`, `--limit 5`, `--role …`) given alone from a script or cron – where nobody types – started a second daemon in the foreground, and the script hung. It is now refused at once with exit code 2. `otp` alone does what it always did; the service is started as `otp --daemon`.

