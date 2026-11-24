## 1.0.331 — 24 November 2026

**Fixed (HA, console)**: the live view of the RADIUS requests on the text console hid the other node's requests - the two nodes number their rows each on its own (odd, even), and one place in the log for both passed over the quieter node's. A place for each node now, as the alerts have (1.0.262).

**Fixed (SIEM, isemon)**: events written on the command line or on the console - a password set, an account switched off or removed, the cluster paused, the configuration exported with its secrets - were on the Events page but never sent to the SIEM or isemon: only the daemon sends, and it was told of its own events alone. The command line now puts its events by for the daemon (`/run/otp/cli-events.jsonl`, 256 KB at most), which sends them within seconds.

**Fixed (console)**: keys of the text screen that are not letters were typed as letters - Shift+Tab as "š", Insert as "ŋ", F1 as "ĉ" - into a field, a shared secret entered once among them (every request of that client then refused). Shift+Tab now goes back a field; the others do nothing.

