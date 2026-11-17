# 1.0.303: the upgrade, round 2 of the hunt - a failed upgrade by hand always said failed; root's helper
# keeps what install.sh said when it stopped it; who asked, why it failed and its id only for a real
# sign-in; the sign-in page's "failed" line one sentence (translated).   python3 fix.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('install.sh', [
("""        if [[ -n "$MAINT_BY_US" ]]; then
            sleep 3
            as_otp --maintenance off >/dev/null 2>&1 && warn "this node is back in service - look at what stopped the upgrade"
        fi
    }""",
 """        if [[ -n "$MAINT_BY_US" ]]; then
            sleep 3
            if as_otp --maintenance off >/dev/null 2>&1; then
                warn "this node is back in service - look at what stopped the upgrade"
            fi
        fi
        # Never a failure of its own (1.0.303): under set -e a maintenance that would not go off
        # ended the EXIT trap here - the pages' file stayed "running" for 30 min.
        return 0
    }"""),
("""    trap 'upg_rc=$?; upgrade_rescue "$upg_rc"; upgrade_told_end "$upg_rc"' EXIT""",
 """    trap 'upg_rc=$?; upgrade_rescue "$upg_rc" || true; upgrade_told_end "$upg_rc" || true' EXIT"""),
])

edit('deploy/otp_upgrade.py', [
("""    except Refused as e:
        log_to('refused: %s' % e)
        status(id=ident, state='failed', rc=-1, said=str(e), tail=log_lines[-40:])
        if told.get('version'):
            pages_tell('failed', ident, words='root checks the package', said=str(e), **told)""",
 """    except Refused as e:
        log_to('refused: %s' % e)
        status(id=ident, state='failed', rc=-1, said=str(e), tail=log_lines[-40:])
        if told.get('version'):
            # What install.sh said when it was stopped (1.0.303) - its step, what runs now - kept:
            # written over, the pages showed "root checks the package" and lost it.
            was = pages_said()
            mine = was.get('id') == ident
            if not (mine and was.get('state') == 'failed'):
                pages_tell('failed', ident, part=(was.get('part') or 1) if mine else 1,
                           parts=(was.get('parts') or 0) if mine else 0,
                           words=(was.get('words') if mine else '') or 'root checks the package',
                           said=str(e), **told)"""),
])

edit('web/otp-api.php', [
("""    $u = otp_upgrading(otp_session() !== '');
    if ($u === null) {
        return false;
    }""",
 """    /* Who asked, why it failed and its id never here (1.0.303): the daemon that would say whether
       the cookie is a real sign-in is what is away - a cookie of the right form was enough. */
    $u = otp_upgrading(false);
    if ($u === null) {
        return false;
    }"""),
])

edit('web/admin/index.php', [
("""        [$hs] = otp_call('/api/health', 'GET', null, 3.0);
        echo json_encode(['ok' => true, 'upgrading' => otp_upgrading(otp_session() !== ''),""",
 """        [$hs] = otp_call('/api/health', 'GET', null, 3.0);
        /* The whole of it only for a real sign-in (1.0.303), asked of the daemon - not for a cookie
           of the right form: who asked, why it failed, its id. */
        $real = $hs === 200 && otp_session() !== '' && otp_whoami() !== null;
        echo json_encode(['ok' => true, 'upgrading' => otp_upgrading($real),"""),
("""$upg     = $me ? null : otp_upgrading(otp_session() !== '');""",
 """$upg     = $me ? null : otp_upgrading(false);       /* signed out: never who asked, nor why (1.0.303) */"""),
("""      <div class="offline">The upgrade to otp <span data-no-i18n><?= h($upg['version']) ?></span> failed<?= $upg['said'] !== '' ? ': <span data-no-i18n>' . h($upg['said']) . '</span>' : '' ?></div>""",
 """      <div class="offline"><?= h('The upgrade to otp ' . $upg['version'] . ' failed') ?></div>"""),
])
print('ok')
