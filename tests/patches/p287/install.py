# 1.0.287 install.sh: an upgrade whose daemon does not start puts the version before back - python3 install.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('install.sh', [(
"""restart_daemon() {
    run systemctl reenable otp.service >/dev/null 2>&1 || run systemctl enable otp.service >/dev/null
    run systemctl restart otp.service
    [[ -n "$DRY_RUN" ]] && return 0
    sleep 2
    if systemctl is-active --quiet otp.service; then
        good "otp.service is running"
    else""",
"""restart_daemon() {
    run systemctl reenable otp.service >/dev/null 2>&1 || run systemctl enable otp.service >/dev/null
    run systemctl restart otp.service
    [[ -n "$DRY_RUN" ]] && return 0
    sleep 2
    # Still running ten seconds later, not started again meanwhile (1.0.287): a daemon that falls over
    # while it opens the database was "running" at 2 s - and systemd starts it again by itself.
    if otp_stays_up; then
        good "otp.service is running"
    else"""), (
"""install_colour() {      # colorama: the command line in colour, as isemon's""",
"""# The version before an upgrade, kept until the new one runs (1.0.287): a release whose daemon does not
# start here (a module missing, a crash at its start) was left in place - the rescue started it again,
# and the node stayed without RADIUS until somebody repaired it by hand. Its program, deploy/ and pages.
UPGRADE_OLD="$LIB_DIR/.before-upgrade"
otp_stays_up() {
    local n0 n1
    n0="$(systemctl show -p NRestarts --value otp.service 2>/dev/null || true)"
    sleep 10
    n1="$(systemctl show -p NRestarts --value otp.service 2>/dev/null || true)"
    systemctl is-active --quiet otp.service && [[ "${n0:-0}" == "${n1:-0}" ]] &&
        "$LIB_DIR/python" "$LIB_DIR/otp.py" --version >/dev/null 2>&1      # and the program there runs at all
}
upgrade_keep_old() {
    [[ -n "$DRY_RUN" || ! -f "$LIB_DIR/otp.py" ]] && return 0
    rm -rf "$UPGRADE_OLD"
    mkdir -p -m 0700 "$UPGRADE_OLD" || return 0
    cp -p "$LIB_DIR/otp.py" "$UPGRADE_OLD/otp.py" || { rm -rf "$UPGRADE_OLD"; return 0; }
    # Never a reason to stop the upgrade: a copy that cannot be made (a full disk) is none.
    if [[ -d "$LIB_DIR/deploy" ]]; then cp -rp "$LIB_DIR/deploy" "$UPGRADE_OLD/deploy" || { rm -rf "$UPGRADE_OLD"; return 0; }; fi
    if [[ -f "$LIB_DIR/CHANGELOG.md" ]]; then cp -p "$LIB_DIR/CHANGELOG.md" "$UPGRADE_OLD/CHANGELOG.md" || true; fi
    if [[ -f "$UNIT_FILE" ]]; then cp -p "$UNIT_FILE" "$UPGRADE_OLD/otp.service" || { rm -rf "$UPGRADE_OLD"; return 0; }; fi
    if [[ -d "$WEB_DIR" && ! -L "$WEB_DIR" ]]; then cp -rp "$WEB_DIR" "$UPGRADE_OLD/web" || { rm -rf "$UPGRADE_OLD"; return 0; }; fi
    touch "$UPGRADE_OLD/complete" || rm -rf "$UPGRADE_OLD"
    return 0
}
upgrade_put_old_back() {
    [[ -f "$UPGRADE_OLD/complete" ]] || return 1
    warn "the version before is put back: its program, deploy/ and pages"
    install -m 0755 "$UPGRADE_OLD/otp.py" "$LIB_DIR/otp.py" || return 1
    if [[ -d "$UPGRADE_OLD/deploy" ]]; then rm -rf "$LIB_DIR/deploy"; cp -rp "$UPGRADE_OLD/deploy" "$LIB_DIR/deploy"; fi
    if [[ -f "$UPGRADE_OLD/CHANGELOG.md" ]]; then cp -p "$UPGRADE_OLD/CHANGELOG.md" "$LIB_DIR/CHANGELOG.md" || true; fi
    # root's helpers as that version had them, its unit (and systemd told), its pages
    local f
    for f in otp_web.py otp_upgrade.py otp-vip-check; do
        if [[ -f "$LIB_DIR/deploy/$f" && -f "$LIB_DIR/$f" ]]; then install -m 0755 "$LIB_DIR/deploy/$f" "$LIB_DIR/$f" || true; fi
    done
    if [[ -f "$UPGRADE_OLD/otp.service" ]]; then
        install -m 0644 "$UPGRADE_OLD/otp.service" "$UNIT_FILE" || true
        systemctl daemon-reload >/dev/null 2>&1 || true
    fi
    if [[ -d "$UPGRADE_OLD/web" ]]; then
        rm -rf "$WEB_DIR"; cp -rp "$UPGRADE_OLD/web" "$WEB_DIR"
        if command -v restorecon >/dev/null 2>&1; then restorecon -R "$WEB_DIR" >/dev/null 2>&1 || true; fi
    fi
    return 0
}

install_colour() {      # colorama: the command line in colour, as isemon's"""), (
"""        warn "the upgrade stopped half way (exit $rc); the daemon is started again as it is"
        systemctl restart otp.service >/dev/null 2>&1 || true""",
"""        warn "the upgrade stopped half way (exit $rc); the daemon is started again as it is"
        systemctl restart otp.service >/dev/null 2>&1 || true
        # The new program in place and not staying up (1.0.287): the version before, as it was.
        if [[ "${UPGRADE_PROGRAM:-}" == new ]] && ! otp_stays_up && upgrade_put_old_back; then
            systemctl restart otp.service >/dev/null 2>&1 || true
            otp_stays_up && warn "the version before runs again - look at what stopped the new one (journalctl -u otp)"
        fi"""), (
"""    install_program
    install_db_drivers
    if [[ -n "$MIGRATED" ]]; then""",
"""    upgrade_keep_old
    UPGRADE_PROGRAM=new
    install_program
    install_db_drivers
    if [[ -n "$MIGRATED" ]]; then"""), (
"""    restart_daemon
    UPGRADE_STAGE=done""",
"""    restart_daemon
    UPGRADE_STAGE=done
    [[ -z "$DRY_RUN" ]] && rm -rf "$UPGRADE_OLD\"""")])
print('1.0.287 install.sh patched')
