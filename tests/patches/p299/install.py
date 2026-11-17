# 1.0.299: install.sh --upgrade tells the pages how far it is: /var/www/otp/.upgrade.json.
#   python3 install.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/install.sh'


def edit(pairs):
    s = open(F).read()
    for a, b in pairs:
        assert s.count(a) == 1, (s.count(a), a[:90])
        s = s.replace(a, b)
    open(F, 'w').write(s)


edit([
("""step()  { printf '\\n%s==> %s%s\\n' "$C_HEAD" "$1" "$C_OFF"; }
""",
 """# How far an upgrade is, for the pages (1.0.299): $WEB_DIR/.upgrade.json - root's, written whole
# (a temporary file renamed over it), read by PHP straight from the disk while the daemon, nginx
# and PHP restart; nginx serves no dot name. Only while --upgrade runs; never a reason to stop.
UPG_TELL=""; UPG_PART=0; UPG_PARTS=0; UPG_WORDS=""; UPG_ID=""; UPG_FROM=""; UPG_BY=""
UPG_NODE=""; UPG_STARTED=0; UPG_DOWN=false; UPG_ENDED=""; UPG_AFTER=""
upg_clean() { printf '%s' "${1:-}" | tr -d '\\000-\\037\\177"\\\\' | cut -c1-200 || true; }
upgrade_tell() {        # STATE [WORDS] [SAID]
    [[ -n "$UPG_TELL" && -z "${DRY_RUN:-}" && -d "$WEB_DIR" && ! -L "$WEB_DIR" ]] || return 0
    local st="$1" words="${2:-$UPG_WORDS}" said="${3:-}" tmp=""
    if (( UPG_PART > UPG_PARTS )); then UPG_PARTS=$UPG_PART; fi
    tmp="$(mktemp "$WEB_DIR/.upgrade.json.XXXXXX" 2>/dev/null)" || return 0
    if printf '{"state":"%s","id":"%s","version":"%s","from":"%s","by":"%s","node":"%s","part":%d,"parts":%d,"words":"%s","started":%d,"at":%d,"said":"%s","downgrade":%s}\\n' \\
            "$st" "$(upg_clean "$UPG_ID")" "$(upg_clean "$VERSION")" "$(upg_clean "$UPG_FROM")" \\
            "$(upg_clean "$UPG_BY")" "$(upg_clean "$UPG_NODE")" "$UPG_PART" "$UPG_PARTS" \\
            "$(upg_clean "$words")" "$UPG_STARTED" "$(date +%s)" "$(upg_clean "$said")" "$UPG_DOWN" \\
            > "$tmp" 2>/dev/null && chmod 0644 "$tmp" 2>/dev/null && mv -f "$tmp" "$WEB_DIR/.upgrade.json" 2>/dev/null; then
        return 0
    fi
    rm -f "$tmp" 2>/dev/null || true
    return 0
}
# The end of --upgrade, said once (1.0.299): done, or failed with what runs now.
upgrade_told_end() {
    local rc="${1:-0}"
    [[ -n "$UPG_TELL" && -z "$UPG_ENDED" ]] || return 0
    UPG_ENDED=yes
    if [[ "$rc" -eq 0 ]]; then
        upgrade_tell done "otp $VERSION runs"
    else
        upgrade_tell failed "$UPG_WORDS" "install.sh --upgrade stopped (exit $rc) - ${UPG_AFTER:-look at what it said}"
    fi
    return 0
}
step()  {
    printf '\\n%s==> %s%s\\n' "$C_HEAD" "$1" "$C_OFF"
    if [[ -n "$UPG_TELL" ]]; then UPG_PART=$((UPG_PART + 1)); UPG_WORDS="$1"; upgrade_tell running "$1"; fi
    return 0
}
"""),
("""    step "Upgrading otp to $VERSION"
    id "$SERVICE_USER" >/dev/null 2>&1 || fail "otp is not installed here; run this without --upgrade"
""",
 """    step "Upgrading otp to $VERSION"
    id "$SERVICE_USER" >/dev/null 2>&1 || fail "otp is not installed here; run this without --upgrade"
    # How far it is, for the pages (1.0.299): from the pages the root helper has said step 1 (the
    # package checked) already; the steps of an upgrade counted as they will come.
    UPG_ID="$(upg_clean "${OTP_UPGRADE_ID:-cli-$(date +%s)}")"
    UPG_BY="${OTP_UPGRADE_BY:-${SUDO_USER:-root} on the command line}"
    UPG_STARTED="${OTP_UPGRADE_STARTED:-}"
    [[ "$UPG_STARTED" =~ ^[0-9]{9,11}$ ]] || UPG_STARTED="$(date +%s)"
    UPG_FROM="$("$LIB_DIR/python" "$LIB_DIR/otp.py" --version 2>/dev/null | grep -oE '[0-9]+\\.[0-9]+\\.[0-9]+' | head -n 1 || true)"
    if [[ -n "$UPG_FROM" && "$UPG_FROM" != "$VERSION" && \\
          "$(printf '%s\\n%s\\n' "$UPG_FROM" "$VERSION" | sort -V | head -n 1 || true)" == "$VERSION" ]]; then
        UPG_DOWN=true
    fi
    UPG_NODE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("node_name") or "")' \\
                "$CONFIG_DIR/config.json" 2>/dev/null || true)"
    [[ -n "$UPG_NODE" ]] || UPG_NODE="$(hostname -s 2>/dev/null || true)"
    UPG_PART=1
    if [[ -n "${OTP_UPGRADE_FROM_PAGES:-}" ]]; then UPG_PART=2; fi
    UPG_WORDS="Upgrading otp to $VERSION"
    upg_db="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("db_engine") or "")' \\
              "$CONFIG_DIR/config.json" 2>/dev/null || true)"
    # The daemon, Python, the service restarting, Done, To be done by hand - and what may come too.
    UPG_PARTS=$((UPG_PART + 5))
    if [[ -n "$WITH_DB" || "$upg_db" == postgres || "$upg_db" == mariadb ]]; then UPG_PARTS=$((UPG_PARTS + 1)); fi
    if [[ -n "$MIGRATED" ]]; then UPG_PARTS=$((UPG_PARTS + 1)); fi
    if [[ -n "$WITH_WEB" && ( -e "$NGINX_CONF" || -d "$WEB_DIR" ) ]]; then UPG_PARTS=$((UPG_PARTS + 2)); fi
    UPG_AFTER="${UPG_FROM:+otp $UPG_FROM runs as it did}"
    UPG_TELL=yes
    upgrade_tell running
    trap 'upgrade_told_end $?' EXIT
    trap 'exit 130' INT
    trap 'exit 129' HUP
    trap 'exit 143' TERM
"""),
("""    upgrade_rescue() {
        local rc=$?
        [[ "${UPGRADE_STAGE:-}" == started && $rc -ne 0 && -z "$DRY_RUN" ]] || return 0
        warn "the upgrade stopped half way (exit $rc); the daemon is started again as it is"
        systemctl restart otp.service >/dev/null 2>&1 || true
        # The new program in place and not staying up (1.0.287): the version before, as it was.
        if [[ "${UPGRADE_PROGRAM:-}" == new ]] && ! otp_stays_up && upgrade_put_old_back; then
            systemctl restart otp.service >/dev/null 2>&1 || true
            otp_stays_up && warn "the version before runs again - look at what stopped the new one (journalctl -u otp)"
        fi""",
 """    upgrade_rescue() {
        local rc=${1:-$?}
        [[ "${UPGRADE_STAGE:-}" == started && $rc -ne 0 && -z "$DRY_RUN" ]] || return 0
        warn "the upgrade stopped half way (exit $rc); the daemon is started again as it is"
        systemctl restart otp.service >/dev/null 2>&1 || true
        UPG_AFTER="otp.service was started again as it is"
        # The new program in place and not staying up (1.0.287): the version before, as it was.
        if [[ "${UPGRADE_PROGRAM:-}" == new ]] && ! otp_stays_up && upgrade_put_old_back; then
            systemctl restart otp.service >/dev/null 2>&1 || true
            UPG_AFTER="the version before was put back"
            if otp_stays_up; then
                warn "the version before runs again - look at what stopped the new one (journalctl -u otp)"
                UPG_AFTER="otp ${UPG_FROM:-of before} runs again"
            fi
        fi"""),
("""    trap upgrade_rescue EXIT
""",
 """    # The pages told the end after the rescue (1.0.299): what runs then.
    trap 'upg_rc=$?; upgrade_rescue "$upg_rc"; upgrade_told_end "$upg_rc"' EXIT
"""),
("""    root_facts_write
    restart_daemon
    UPGRADE_STAGE=done""",
 """    # Its own step for the pages (1.0.299): the daemon, and so these pages' API, restart now.
    UPG_PART=$((UPG_PART + 1)); UPG_WORDS="The service restarts"; upgrade_tell running
    root_facts_write
    restart_daemon
    UPGRADE_STAGE=done"""),
])
print('ok')
