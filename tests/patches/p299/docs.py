# 1.0.299 docs: how the pages follow an upgrade.   python3 docs.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/docs/upgrades.md'
s = open(F).read()
a = """`otp --upgrade-status` shows the same on the command line, and
`otp --upgrade-cancel` stops it.
"""
b = a + """
### The pages while it runs (1.0.299)

Every page shows how far it is in a band under its header - the version, from
which, who started it, how long so far, a bar, the step (`step 7 of 9 · The
pages`) and, in a cluster, every node's state. The pages are served by the very
things an upgrade restarts (the daemon and its API, PHP, nginx), so:

- **This node's progress is in a file the pages read themselves**:
  `/var/www/otp/.upgrade.json`, root's (0644), written whole - `otp_upgrade.py`
  writes the first step (the package checked) and a refusal, `install.sh
  --upgrade` each of its steps, `done` at its end and `failed` from its EXIT
  trap (a signal too), with what runs then. nginx serves no dot name. PHP
  believes it while it runs for 30 min after its last word, `done` and
  `failed` for 10 min. An upgrade on the command line writes it too.
- **While the daemon is away**, every API call of the pages is answered 503
  with `upgrading` (how far it is) instead of "the daemon is not answering";
  `/admin/?api=upgrade-state` answers without the daemon at all. The page says
  *restarting* - never the red bar or a red toast - asks again every 2 s, and
  says so too while nginx and PHP restart and nothing answers it.
- **Behind the VIP address** the node answering is the other one while this
  one is upgraded: the band follows the cluster's plan from whichever node
  answers.
- **At the end** the page loads the pages of the version it was upgraded to by
  itself, once - as soon as that version answers (a VIP address moving to the
  node done already counts), never back to an older one. With unsaved changes
  it offers *Load it again* instead.
- **A failure** is a red band with the reason and a way to *Upgrades* (what
  `install.sh` said); × hides it for that upgrade.
- **Signed out** meanwhile, the sign-in page shows the same band from the file
  and loads again by itself when the daemon answers.
- **`/healthz`** says `503 maintenance NODE: being upgraded to X` while the
  daemon is away in an upgrade - a monitor sees maintenance, not down. The VIP
  address is not decided by it (`otp-vip-check`): unchanged.
"""
assert s.count(a) == 1
open(F, 'w').write(s.replace(a, b))
print('ok')
