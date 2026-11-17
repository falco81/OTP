# 1.0.307: backups and the outgoing mail (hunt round 6) - the weekly check of a node that does not make
# the night's copy (one database for the cluster) is not "cannot be put back"; age never takes away the
# newest three backups; the outgoing mail's tick decides on each mail as it is now, not as it was when
# the tick began.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('86v_verify.py', [
("""        elif CONFIG.get('backup_daily'):
            res['checks'].append({'what': what, 'ok': False,
                                  'said': 'there is no nightly copy in %s' % DUMP_DIR})""",
 """        elif CONFIG.get('backup_daily') and CONFIG.get('ha_mode') != 'replicated' and in_cluster(store):
            # One database for the cluster (1.0.307): the night's copy is made by the node that took
            # the night's turn - none here is no fault of this node's backup.
            res['checks'].append({'what': what, 'ok': True,
                                  'said': 'none here - one database for the cluster: the night\\'s copy is made by '
                                          'the node that takes the night\\'s turn'})
        elif CONFIG.get('backup_daily'):
            res['checks'].append({'what': what, 'ok': False,
                                  'said': 'there is no nightly copy in %s' % DUMP_DIR})"""),
])

edit('86b_rbackup.py', [
("""        if (keep and i >= keep) or (days and now - when > days * 86400):""",
 """        # Never the newest three by age (1.0.307): a clock stepped ahead, or backups that failed
        # longer than the days kept, took every older backup away at once - one left.
        if (keep and i >= keep) or (days and i >= RB_AGE_KEEP_MIN and now - when > days * 86400):"""),
("""def rb_room(store, times=2):""",
 """RB_AGE_KEEP_MIN = 3


def rb_room(store, times=2):"""),
])

edit('86_mail.py', [
("""            if state in ('waiting', 'sending') and \\
                    now > fnum(rec.get('expires')) + (120 if state != 'sending' else 600):
                _, raw = mailq_read(store, qid)
                if raw:
                    rec.pop('qid', None)""",
 """            if state in ('waiting', 'sending') and \\
                    now > fnum(rec.get('expires')) + (120 if state != 'sending' else 600):
                # Decided on the mail as it is now (1.0.307): the list was read when the tick began,
                # and a slow tick (the server away) gave up a mail sent again meanwhile.
                fresh, raw = mailq_read(store, qid)
                t2 = time.time()
                if raw and fresh and fresh.get('state') in ('waiting', 'sending') and \\
                        t2 > fnum(fresh.get('expires')) + (120 if fresh.get('state') != 'sending' else 600):
                    rec = fresh
                    rec.pop('qid', None)"""),
("""            if state == 'sending' and now - fnum(rec.get('last_try')) > stuck and \\
                    (mine or rec.get('node') not in alive):
                # Left half way by a node that stopped: tried again.
                _, raw = mailq_read(store, qid)
                if raw:
                    rec.pop('qid', None)""",
 """            if state == 'sending' and now - fnum(rec.get('last_try')) > stuck and \\
                    (mine or rec.get('node') not in alive):
                # Left half way by a node that stopped: tried again - as it is now (1.0.307).
                fresh, raw = mailq_read(store, qid)
                if raw and fresh and fresh.get('state') == 'sending' and \\
                        time.time() - fnum(fresh.get('last_try')) > stuck:
                    rec = fresh
                    rec.pop('qid', None)"""),
])
print('ok')
