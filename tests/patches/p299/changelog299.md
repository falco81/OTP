## 1.0.299 — 17 November 2026

**The pages follow an upgrade while the things that serve them restart** - the daemon and its API, PHP and nginx. Standalone and in a cluster (both nodes, behind the VIP address).

- **A band under every page's header** while an upgrade runs: the version, from which, who started it, how long so far, a bar, the step (*step 7 of 9 · The pages*) and, in a cluster, every node's state. The plan comes with every status from whichever node answers - behind the VIP address the other node while this one is upgraded.
- **This node's progress in a file the pages read themselves** - `/var/www/otp/.upgrade.json`, root's: the root helper writes the package checked (or refused), `install.sh --upgrade` each of its steps, `done` at its end and `failed` from its EXIT trap (a signal too), with what runs then. An upgrade on the command line writes it too; nginx never serves it.
- **While the daemon is away**, every call of the pages is answered *503 upgrading* with how far it is, not "the daemon is not answering"; the page says *restarting* (also while nginx and PHP restart and nothing answers), asks every 2 s, the pill says *in maintenance* - never the red bar or a red toast. `?api=upgrade-state` answers without the daemon.
- **At the end the page loads the new version by itself, once** - as soon as the version it was upgraded to answers (a VIP address moving to the node done already counts), never back to an older one; with unsaved changes it offers *Load it again*.
- **A failure**: a red band with the reason and a way to *Upgrades*; × hides it for that upgrade.
- **The sign-in page** during an upgrade shows the band itself (from the file) and loads again when the daemon is back - not "the daemon is not answering".
- **`/healthz`**: `503 maintenance NODE: being upgraded to X` while the daemon is away in an upgrade (still 503; the VIP address does not depend on it).
- Docs: *Upgrades → The pages while it runs*.

