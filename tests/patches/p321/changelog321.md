## 1.0.321 — 23 November 2026

**Bug fix (command line)**:
- `otp --local-user drop|drop-home NAME` run from a script or cron took the user (and the home folder) away on every node without being asked, and at a terminal asked even with `--yes`. It now goes as every other step that takes something away: `--yes`, or *yes* typed at a terminal - refused otherwise. `--sso-key` the same: from a script without `--yes` it shut the balancer out unasked.
- `otp --api` on a route that sends or takes a file (the database's download, a backup's) ended in a traceback. It says so in words, before the route runs - a download no longer makes a copy of the database for nothing.
- `otp --api GET '/api/...?q=a%20b'` passed *a%20b* as it was; the query is read as the pages read it.
- A directory's certificate check, once off (`--no-verify`), could not be put back on from the command line or the console. `--dir-cert-check on|off`, and a field of the console's form.
- `--local-user`'s help left out *aging*.

**Bug fix (console)**: changing a directory from LDAPS to StartTLS (or back) kept the old way's port - StartTLS on 636, and the directory stopped answering. The new way's port is taken unless another one was written.

**Bug fix (pages)**:
- The page's decimal mark (*1,5* in Czech) in the load meter (rates, GHz, load), the Time pane (offsets, frequency, the clock's difference) and the remote backups' *Try it*.
- The proxy's and isemon's *Try it* asked again every second while the last ask was still out; an answer of a finished try could end the next one - its cards left *being tried* and the button on mid-try. One ask at a time, each try ended once.
- The network's and the restart's views of a node that was restarting held up to ten requests at once, and the rest of the page waited behind them. One at a time.
- Some dates were written in the browser's language, not the page's (the balancer's last sign-ins, the report's period, SELinux, the Kerberos keytab, a passkey's name).

