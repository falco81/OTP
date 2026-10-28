# otp - the working tree (branch `workspace`)

What the releases on `main` (`release/otp-X.Y.Z.tar.gz`) are built from.
Never put the release signing key here.

- `build/parts/*.py` - otp.py in parts; `build/build.sh` joins them (its list sets the order)
  into `build/out/otp-VERSION/otp.py`.
- `build/out/otp-VERSION/` - everything else of the package, edited in place:
  `web/`, `deploy/`, `docs/`, `install.sh`, `CHANGELOG.md`, `README.md`.
- `build/bump.sh NEW` - a new version (copies the out folder, sets `__version__`).
- `build/pack.sh VERSION` - builds the Czech language pack (`i18n/make_cs.py`), signs
  (`build/sign.sh`, needs `build/keys/otp-release-1.key` - not in git) and makes the archive.
- `build/release_push.sh VERSION` - puts the archive into `release/` on `main`, keeping the
  newest ten.
- `i18n/` - the Czech strings (`cs_NNN.py`, registered in `make_cs.py`).
- `tests/` - the scripts used against the sandbox: UI (Playwright), console (pexpect + pyte),
  load, challenge/response, network trial, HA helpers.

See the project doc `claude/otp-handoff.md` for the rules and the whole workflow.
