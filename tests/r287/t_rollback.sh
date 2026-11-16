#!/bin/bash
# t_rollback.sh VERSION - 1.0.287: an upgrade whose daemon does not start puts the version before back.
# The installed VERSION upgraded (install.sh --upgrade) to a copy of itself whose otp.py stops at once when
# started as the daemon: the upgrade fails, the version before is in place again (its otp.py, deploy/, pages)
# and the daemon runs. Then the same package unbroken: it goes in, and nothing of the version before is kept.
V=${1:-1.0.287}
SRC=/home/claude/build/out/otp-$V
W=$(mktemp -d /tmp/claude-0/rollback.XXXXXX)
n=0; good=0
ok() { n=$((n+1)); if [ "$2" = 0 ]; then good=$((good+1)); echo "ok   $1"; else echo "FAIL $1"; fi; }
before=$(sha256sum /usr/local/lib/otp/otp.py | cut -c1-64)
pages=$(sha256sum /var/www/otp/assets/admin.js | cut -c1-64)
cp -a "$SRC" "$W/pkg"
# the daemon of the copy stops at once (the command line works, as install.sh needs it)
HOW=${2:-daemon}       # daemon: the daemon stops at its start; program: the program does not run at all
python3 - "$W/pkg/otp.py" "$HOW" <<'EOF'
import sys
p, how = sys.argv[1], sys.argv[2]
s = open(p).read()
if how == 'program':
    s = s.replace('from __future__ import annotations', 'from __future__ import annotations\nimport otp_module_not_there', 1)
else:
    i = s.index('from __future__ import annotations')
    i = s.index('\n', i) + 1
    s = s[:i] + "import sys as _s\nif '--daemon' in _s.argv:\n    raise SystemExit('broken on purpose (t_rollback)')\n" + s[i:]
open(p, 'w').write(s)
EOF
echo '/* broken on purpose */' >> "$W/pkg/web/assets/admin.js"
(cd "$W/pkg" && bash install.sh --upgrade --yes > "$W/broken.log" 2>&1); rc=$?
ok "the broken upgrade fails (exit $rc)" "$([ $rc -ne 0 ] && echo 0 || echo 1)"
grep -q "the version before is put back" "$W/broken.log"; ok "...says the version before is put back" $?
now=$(sha256sum /usr/local/lib/otp/otp.py | cut -c1-64)
[ "$now" = "$before" ]; ok "...otp.py is the version before" $?
[ "$(sha256sum /var/www/otp/assets/admin.js | cut -c1-64)" = "$pages" ]; ok "...the pages are the version before" $?
sleep 3
pgrep -f "^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon" >/dev/null; ok "...the daemon runs" $?
curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/admin/ | grep -q 200; ok "...the pages answer" $?
# the same package unbroken
(cd "$SRC" && bash install.sh --upgrade --yes > "$W/good.log" 2>&1); rc=$?
ok "the package unbroken goes in (exit $rc)" "$rc"
[ ! -e /usr/local/lib/otp/.before-upgrade ]; ok "...nothing of the version before kept" $?
pgrep -f "^/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon" >/dev/null; ok "...the daemon runs" $?
echo "ALL $good / $n"
