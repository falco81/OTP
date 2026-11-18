"""1.0.312 (parts): the cap of wrong directory passwords counted as the directory counts them."""
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


edit('65_codes.py', [
("""def node_key_add(store, prefix, name, keep, most=None, limit=None):
    \"\"\"`time.time()` added to this node's own row for `name`, written only over
    what was read; the times older than `keep` seconds dropped. True once
    written. With `limit`: False, nothing written, when every node's rows
    together already hold that many - counted again at each try, so of
    requests at once only as many as the limit get past (1.0.147).\"\"\"
    k = node_key(prefix, name)""",
 """def node_key_streak(times, span, now=None):
    \"\"\"The times that count now as a directory counts its wrong passwords (1.0.312): its counter
    goes back to 0 only once `span` has gone by since the LAST one (Active Directory's "Reset
    account lockout counter after"), not each one `span` after itself. The run of times up to the
    newest with no gap of `span` in it - none when the newest is `span` old.\"\"\"
    now = time.time() if now is None else now
    ts = sorted(times, key=lambda x: x[0] if isinstance(x, tuple) else x)
    if not ts:
        return []
    at = (lambda x: x[0] if isinstance(x, tuple) else x)
    if now - at(ts[-1]) >= span:
        return []
    i = len(ts) - 1
    while i > 0 and at(ts[i]) - at(ts[i - 1]) < span:
        i -= 1
    return ts[i:]


def node_key_add(store, prefix, name, keep, most=None, limit=None, streak=None):
    \"\"\"`time.time()` added to this node's own row for `name`, written only over
    what was read; the times older than `keep` seconds dropped. True once
    written. With `limit`: False, nothing written, when every node's rows
    together already hold that many - counted again at each try, so of
    requests at once only as many as the limit get past (1.0.147). With `streak`
    (seconds, 1.0.312): only the run of times counted that a directory counts
    (node_key_streak) - `keep` then long enough to hold that run.\"\"\"
    k = node_key(prefix, name)"""),
("""        times = [x for x in times if t - x < keep]
        if limit is not None:
            others = 0
            for r in node_key_rows(store, prefix, name):
                if r['k'] == k:
                    continue
                try:
                    others += len([x for x in json.loads(r['v'] or '[]') if t - float(x) < keep])
                except (ValueError, TypeError):
                    continue
            if others + len(times) >= limit:
                return False""",
 """        times = [x for x in times if t - x < keep]
        if limit is not None:
            others = 0
            theirs = []
            for r in node_key_rows(store, prefix, name):
                if r['k'] == k:
                    continue
                try:
                    got = [float(x) for x in json.loads(r['v'] or '[]') if t - float(x) < keep]
                except (ValueError, TypeError):
                    continue
                others += len(got)
                theirs += got
            if streak:
                if len(node_key_streak(theirs + times, streak, t)) >= limit:
                    return False
            elif others + len(times) >= limit:
                return False"""),
("""                store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, new))
                return _node_key_recount(store, prefix, name, k, t, keep, limit)
            except Exception:                           # noqa: BLE001
                continue
        if store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (new, k, raw)):
            return _node_key_recount(store, prefix, name, k, t, keep, limit)
    return False


def _node_key_recount(store, prefix, name, k, t, keep, limit):""",
 """                store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, new))
                return _node_key_recount(store, prefix, name, k, t, keep, limit, streak)
            except Exception:                           # noqa: BLE001
                continue
        if store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (new, k, raw)):
            return _node_key_recount(store, prefix, name, k, t, keep, limit, streak)
    return False


def _node_key_recount(store, prefix, name, k, t, keep, limit, streak=None):"""),
("""    every.sort()
    if (t, k) in every[:limit]:""",
 """    every.sort()
    if streak:
        every = node_key_streak(every, streak, t)
    if (t, k) in every[:limit]:"""),
])

edit('90_api.py', [
("""    if not node_key_add(h.store, 'adpw', who, span, limit=most):
        times = sorted(x for x in node_key_times(h.store, 'adpw', who) if time.time() - x < span)
        wait = max(1, int(((times[-most] + span) - time.time()) // 60) + 1) if len(times) >= most else 1""",
 """    # Counted as the directory counts (1.0.312): its counter goes back to 0 only `span` after the
    # LAST wrong password. Each one counted `span` after itself, wrong passwords 10 min apart got
    # past a cap of 3 in 30 min without end - 5 in 40 min locked an account with a threshold of 5.
    if not node_key_add(h.store, 'adpw', who, span * (most + 1), limit=most, streak=span):
        run = node_key_streak(node_key_times(h.store, 'adpw', who), span)
        wait = max(1, int(((run[-1] + span) - time.time()) // 60) + 1) if run else 1"""),
("""        name_, _s, dname = who.partition('|')
        most, pspan = dir_pw_cap_of(store, dname)
        times = sorted(x for x in times if t - x < pspan)
        if not times or most <= 0:
            continue
        locked = len(times) >= most
        rows.append({'kind': 'dir-passwords', 'who': who, 'by': 'name',
                     'what': LOCKOUT_KINDS['dir-passwords'] + (' (%s)' % dname if dname else ''),
                     'base': 'dir-passwords',
                     'words': 'wrong directory passwords', 'fails': len(times), 'limit': most,
                     'locked': locked,
                     'until': (times[len(times) - most] + pspan) if locked else None,""",
 """        name_, _s, dname = who.partition('|')
        most, pspan = dir_pw_cap_of(store, dname)
        # The run the directory counts (1.0.312): free again `pspan` after the last of them.
        times = node_key_streak(times, pspan, t)
        if not times or most <= 0:
            continue
        locked = len(times) >= most
        rows.append({'kind': 'dir-passwords', 'who': who, 'by': 'name',
                     'what': LOCKOUT_KINDS['dir-passwords'] + (' (%s)' % dname if dname else ''),
                     'base': 'dir-passwords',
                     'words': 'wrong directory passwords', 'fails': len(times), 'limit': most,
                     'locked': locked,
                     'until': (times[-1] + pspan) if locked else None,"""),
])
edit('00_head.py', [
("""    'dir_pw_window_min': 'How long a wrong directory password counts towards the cap above. As '
                         'long as the directory\\'s "Reset account lockout counter after", or longer.',""",
 """    'dir_pw_window_min': 'The count goes back to 0 once this long has gone by since the last wrong '
                         'password - as the directory counts it ("Reset account lockout counter after"). '
                         'As long as that, or longer.',"""),
])
print('ok')
