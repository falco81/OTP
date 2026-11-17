# 1.0.298: bug fixes - the weekly backup check with no destination switched on; forgetting a
# check's row of another node; SNMP's certificate end past 2038.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('86v_verify.py', [
("""    if (CONFIG.get('rbackup_verify') or 'off') != 'weekly':
        return False
    rows = _meta_json(store, 'rbackup:verified:' + node_name(), list) or []
    last = float(rows[0].get('at') or 0) if isinstance(rows, list) and rows else 0""",
 """    if (CONFIG.get('rbackup_verify') or 'off') != 'weekly':
        return False
    # Not with no destination switched on (1.0.298): it failed at once, wrote nothing, and was
    # started again every hour for good.
    try:
        if not any(t.get('enabled') for t in rb_targets(store)):
            return False
    except Exception:                                   # noqa: BLE001
        pass
    rows = _meta_json(store, 'rbackup:verified:' + node_name(), list) or []
    first = rows[0] if isinstance(rows, list) and rows else None
    last = fnum(first.get('at')) if isinstance(first, dict) else 0"""),
("""        if len(keep) != len(rows):
            n += len(rows) - len(keep)
            store.set_meta(r['k'], json.dumps(keep))""",
 """        if len(keep) != len(rows):
            n += len(rows) - len(keep)
            # Another node's row by UPDATE only (1.0.298), as the history's: set_meta may insert,
            # and the two nodes writing it at once met as one key twice in the replication.
            if r['k'] == 'rbackup:verified:' + node_name():
                store.set_meta(r['k'], json.dumps(keep))
            else:
                store.db.run('UPDATE meta SET v = ? WHERE k = ?', (json.dumps(keep), r['k']))"""),
])

edit('90s_snmp.py', [
("""                         (B + (6, 1, 1, 5, i), 'int', end)]""",
 """                         # Integer32 (1.0.298): a certificate ending after 2038 was 5 bytes and a
                         # strict manager refused the whole answer.
                         (B + (6, 1, 1, 5, i), 'int', max(-2 ** 31, min(end, 2 ** 31 - 1)))]"""),
])
print('ok')
