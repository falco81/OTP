# Going back (1.0.143) - tests

- `t_down.py VERSION` - the floors and the check of a package against the
  database, on SQLite (15 checks; packages from /home/claude/otp/release).
- `t_root.py VERSION` - otp_upgrade.put_in: refused without asking, without a
  floor, with a floor others may write, below it; on to install.sh when allowed.
- A real install in the container (no nginx/PHP/systemd): a `systemctl` that
  only logs at /usr/local/sbin/systemctl, `install.sh --no-web --yes` of a
  release, `startd.sh` starts the daemon as otp.service would, `rootloop.sh`
  plays otp-upgrade.path (root's helper, then a restart). Then
  `otp --downgrade-check`, `otp --downgrade VERSION --yes`; `t_api.py` asks the
  daemon's API (downgrade_list, downgrade_get) - set the admin password first
  with OTP_PASSWORD=... otp --passwd admin.
