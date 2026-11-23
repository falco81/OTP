"""1.0.323 (parts): a lockout clear asked of the other node never lost; a backup of tokens with odd
values searched; the second step's wait said from the count that refused."""
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
("""    key = 'lockouts:ask:' + node_name()
    raw = d.store.get_meta(key)
    if raw:
        d.store.drop_meta(key)
""",
 """    key = 'lockouts:ask:' + node_name()
    raw = d.store.get_meta(key)
    if raw:
        # Only the asks read (1.0.323): one added by the other node between the read and the
        # delete was deleted unread - said cleared "within five seconds", never cleared.
        if dbguard_meta_signed(key):
            d.store.drop_meta(key)
        else:
            d.store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (key, raw))
"""),
])

edit('50_storage.py', [
("""                         [[i] + [r.get(c) for c in cols] for i, r in enumerate(rows)])
""",
 """                         # A list or an object in a file (1.0.323) as its text: sqlite took no
                         # such value, and the search ended in a 500.
                         [[i] + [_mem_value(r.get(c)) for c in cols] for i, r in enumerate(rows)])
"""),
("""def memory_search(listname, create, cols, rows, text):
""",
 """def _mem_value(v):
    if v is None or isinstance(v, (str, int, float)):
        return v
    try:
        return json.dumps(v, ensure_ascii=False, default=str)
    except Exception:                                   # noqa: BLE001
        return str(v)


def memory_search(listname, create, cols, rows, text):
"""),
])

edit('90m_mfa.py', [
("""        raise ApiError(429, 'too many codes sent lately - try again in %d min'
                       % code_send_wait_min(h.store, 'adm:' + str(s['name']).lower()), extra={'send': st})
""",
 """        # The wait of the count that refused (1.0.323): the address's, said as the account's -
        # "in 1 min", refused for 15.
        raise ApiError(429, 'too many codes sent lately - try again in %d min'
                       % code_send_wait_min(h.store, dkey if a_ok else akey), extra={'send': st})
"""),
])
