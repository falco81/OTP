"""1.0.334 (parts): a move to PostgreSQL from SQLite or MariaDB no longer refused for good as "an
older copy"; a setting saved on a node whose clock is behind the other's kept by both; the other
node's rows of the recovery codes' guard no longer tidied here."""
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


edit('90_api.py', [
("""    a, b = db_fingerprint(here), db_fingerprint(far)
""",
 """    a, b = db_fingerprint(here), db_fingerprint(far)
    # The times of a token's key, state and recovery codes are written by PostgreSQL's trigger
    # alone (1.0.334): carried from SQLite or MariaDB, where they are empty, PostgreSQL wrote the
    # time of the carry into every row - "an older copy: the tokens", however often carried.
    # Compared only where this one has them.
    if a.get('tokens') and b.get('tokens'):
        b['tokens'] = tuple(y if x is not None or i < 2 else None
                            for i, (x, y) in enumerate(zip(a['tokens'], b['tokens'])))
"""),
])

edit('50_storage.py', [
("""    def save_setting(self, k, v, by=''):
        row = {'k': k, 'v': json.dumps(v), 'at': time.time(), 'by_who': str(by or '')[:190]}
""",
 """    def save_setting(self, k, v, by=''):
        # Later than the one it replaces (1.0.334), as a token's times are (1.0.214): saved on a
        # node whose clock is behind the other's, the other kept its own as the newer - the two
        # held different values until the next change.
        at = time.time()
        try:
            was = self.db.value('SELECT at FROM settings WHERE k = ?', (k,))
            if was is not None and float(was) >= at:
                at = float(was) + 0.001
        except (TypeError, ValueError, DbError):
            pass
        row = {'k': k, 'v': json.dumps(v), 'at': at, 'by_who': str(by or '')[:190]}
"""),
])

edit('87_ha.py', [
("""    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'scratchguard:%'"):
        try:
            last = max([float(x) for x in json.loads(r['v'] or '[]')] or [0])
        except (ValueError, TypeError):
            last = 0
        if t - last > 86400:
""",
 """    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'scratchguard:%'"):
        # Each node its own rows (1.0.334), as the codes' and the questions' (1.0.327): the other's
        # deleted here as it added a time to it lost that count.
        if not _tidy_mine(store, r['k']):
            continue
        try:
            last = max([float(x) for x in json.loads(r['v'] or '[]')] or [0])
        except (ValueError, TypeError):
            last = 0
        if t - last > 86400:
"""),
])
