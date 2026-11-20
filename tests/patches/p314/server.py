"""1.0.314 (parts): the replication's apply and sync errors mailed, as the setting says; a disk short of
inodes said as that."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('88z_alerts.py', [
("""SMS_HEALTH = {'ok_at': 0.0, 'fail_at': 0.0, 'fails': 0, 'said': ''}
""",
 """SMS_HEALTH = {'ok_at': 0.0, 'fail_at': 0.0, 'fails': 0, 'said': ''}
# This node's subscriptions' apply and sync errors (1.0.314): PostgreSQL counts them for good, so
# what is mailed is a count that went up - when it last did, kept here and said in the health row.
REPL_ERRS = {'n': None, 'at': 0.0, 'by': ''}
REPL_ERRS_FOR_S = 1800


def repl_errors_seen(rs, now=None):
    \"\"\"The errors of this node's subscriptions as ha_repl_state gives them: REPL_ERRS moved on -
    'at' is when their count last went up (never at the first look, nor when it went down: the
    statistics were reset).\"\"\"
    now = time.time() if now is None else now
    inc = [x for x in (rs or {}).get('incoming') or [] if isinstance(x, dict)]
    if not inc:
        return REPL_ERRS
    n = sum(int(fnum(x.get('apply_errors'))) + int(fnum(x.get('sync_errors'))) for x in inc)
    if REPL_ERRS['n'] is not None and n > REPL_ERRS['n']:
        REPL_ERRS['at'] = now
        REPL_ERRS['by'] = ', '.join('%s (%d apply, %d sync)' % (
            x.get('name'), int(fnum(x.get('apply_errors'))), int(fnum(x.get('sync_errors'))))
            for x in inc if fnum(x.get('apply_errors')) or fnum(x.get('sync_errors')))[:300]
    REPL_ERRS['n'] = n
    return REPL_ERRS
"""),
("""    row['name_clash'] = str(said(name_clash_words) or '')[:300]
""",
 """    row['name_clash'] = str(said(name_clash_words) or '')[:300]
    if CONFIG.get('ha_mode') == 'replicated' and daemon.store.db.engine == 'postgres':
        got = said(lambda: repl_errors_seen(ha_repl_state(daemon.store), now))
        if got:
            row['repl_errors'] = {'n': got['n'], 'at': got['at'], 'by': got['by']}
"""),
("""        if rs.get('healthy', True) and behind > mb * 1048576:
            add('repl:behind', 'warn', '',
                _al(lang, 'Replikace zaostává o %s' % human_bytes(behind), 'The replication is %s behind' % human_bytes(behind)),
                str(rs.get('last_msg') or '')[:300], 'ha')
""",
 """        if rs.get('healthy', True) and behind > mb * 1048576:
            add('repl:behind', 'warn', '',
                _al(lang, 'Replikace zaostává o %s' % human_bytes(behind), 'The replication is %s behind' % human_bytes(behind)),
                str(rs.get('last_msg') or '')[:300], 'ha')
        # Its apply and sync errors (1.0.314), as the setting says: none was ever mailed. Each node's
        # own, from its health row - a count that went up in the last half hour.
        for n in names:
            re_ = odict((health.get(n) or {}).get('repl_errors'))
            if re_.get('at') and now - fnum(re_.get('at')) < REPL_ERRS_FOR_S:
                add('repl:errors:' + n, 'warn', n,
                    _al(lang, 'Replikace na %s hlásí chyby' % n, 'The replication on %s ran into errors' % n),
                    _al(lang, 'Chyby při přebírání změn druhého uzlu, naposledy %s: %s. Nastavení → '
                              'Vysoká dostupnost ukazuje poslední hlášku.',
                        'Errors taking the other node\\'s changes, the last %s: %s. Settings → High '
                        'availability shows the last message.') % (
                        _al_when(re_['at']), str(re_.get('by') or '?')[:300]), 'ha')
"""),
("""                if fnum(d.get('pct')) >= pct or fnum(d.get('inodes')) >= pct:
                    add('disk:%s:%s' % (n, d['path']), 'bad' if d['pct'] >= 95 else 'warn', n,
                        _al(lang, 'Na %s dochází místo (%s)' % (n, d['path']),
                            '%s is running out of room (%s)' % (n, d['path'])),
                        _al(lang, 'Zaplněno %s %% - volných %s.', '%s %% full - %s free.')
                        % (d['pct'], human_bytes(d.get('free') or 0)), 'osup')
""",
 """                if fnum(d.get('pct')) >= pct or fnum(d.get('inodes')) >= pct:
                    # Short of inodes said as that (1.0.314): "40 % full" was said of a disk out
                    # of inodes - and nothing to see in df -h.
                    worst = max(fnum(d.get('pct')), fnum(d.get('inodes')))
                    words = _al(lang, 'Zaplněno %s %% - volných %s.', '%s %% full - %s free.') % (
                        d['pct'], human_bytes(d.get('free') or 0))
                    if fnum(d.get('inodes')) >= pct:
                        words += _al(lang, ' Inody (soubory): použito %s %% - viz df -i.',
                                     ' Inodes (files): %s %% used - see df -i.') % d.get('inodes')
                    add('disk:%s:%s' % (n, d['path']), 'bad' if worst >= 95 else 'warn', n,
                        _al(lang, 'Na %s dochází místo (%s)' % (n, d['path']),
                            '%s is running out of room (%s)' % (n, d['path'])),
                        words, 'osup')
"""),
])
