"""1.0.328 (parts): a copy of the database from one moment; the last full administrator not taken
away by two at once; port 80's names for the ACME CA taken back when ACME is off; a request to
the database agent not done after the node stopped waiting for it."""
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


edit('20_db.py', [
("""    with gzip.open(out if hasattr(out, 'write') else str(out), 'wt', encoding='utf-8') as f:
        f.write(json.dumps({'otp': __version__, 'schema': SCHEMA_VERSION,
                            'made': time.time(), 'engine': db.engine,
                            'machine': machine_info()}, default=str) + '\\n')
        for table in (tables or TABLES):
""",
 """    # One moment (1.0.328): each table, and each 2000 rows of one, was read by a statement of
    # its own, minutes apart on a big database while RADIUS and the pages wrote - a token
    # renamed meanwhile was missing from the copy, or its rows in meta did not match it. In
    # the process of its own that makes the copy (child): one transaction that reads alone -
    # its own connection, so it holds nothing against RADIUS.
    snap = child and _dump_snapshot_begin(db)
    try:
        _dump_tables_into(db, out, tables, gzip)
    except BaseException:
        if snap:
            _dump_snapshot_end(db, ok=False)
        raise
    if snap:
        _dump_snapshot_end(db, ok=True)
    return out


def _dump_snapshot_begin(db):
    \"\"\"The copy's transaction begun: True, or False where it could not be (as before).\"\"\"
    try:
        if db.engine == 'postgres':
            db.run('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        elif db.engine == 'mariadb':
            db.run('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            db.run('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
        else:
            db.run('BEGIN')         # WAL: the writers go on, the copy reads one moment
        db.in_tx = True             # a connection lost meanwhile: an error, not a new one
        return True
    except Exception as e:                              # noqa: BLE001
        log('the copy is read without one transaction: %s' % e, 'warn')
        return False


def _dump_snapshot_end(db, ok):
    db.in_tx = False
    try:
        db.run('COMMIT' if ok else 'ROLLBACK')
    except Exception:                                   # noqa: BLE001
        pass


def _dump_tables_into(db, out, tables, gzip):
    with gzip.open(out if hasattr(out, 'write') else str(out), 'wt', encoding='utf-8') as f:
        f.write(json.dumps({'otp': __version__, 'schema': SCHEMA_VERSION,
                            'made': time.time(), 'engine': db.engine,
                            'machine': machine_info()}, default=str) + '\\n')
        for table in (tables or TABLES):
"""),
("""                if not rows or table in ('meta', 'settings'):
                    break
    return out


def _dump_tables_child(out):
""",
 """                if not rows or table in ('meta', 'settings'):
                    break


def _dump_tables_child(out):
"""),
])

edit('50_storage.py', [
("""    def fulladmins_left(self, but='', dirs=None):
""",
 """    def fulladmin_change(self, apply, undo, dirs=None):
        \"\"\"A full administrator taken away - `apply` done, and undone by `undo` when then nobody
        is left who can sign in (1.0.328): two full administrators each taking the other away at
        once (two tabs, two nodes of one database) each counted the other as left - both went,
        and only root's command line got anybody in again. One at a time on this node; counted
        again after the change, so another node's change at the same moment is seen too.\"\"\"
        with FULLADMIN_LOCK:
            apply()
            if not self.fulladmins_left(dirs=dirs):
                undo()
                raise ValueError('that is the last full administrator who can sign in')

    def fulladmins_left(self, but='', dirs=None):
"""),
])
edit('00_head.py', [
("""SETTING_TALL = (""",
 """FULLADMIN_LOCK = threading.Lock()        # the last full administrator (1.0.328)
SETTING_TALL = ("""),
])

edit('90_api.py', [
("""            raise ApiError(400, 'that is the last full administrator who can sign in')
    if act == 'delete':
        h.store.drop_account(name)
""",
 """            raise ApiError(400, 'that is the last full administrator who can sign in')
        # Counted again after the change (1.0.328): another one taking the last other away
        # at the same moment. Taken away as switched off first, so it can be put back.
        role_was, off_was = acc['role'], int(acc.get('disabled') or 0)
        try:
            h.store.fulladmin_change(
                (lambda: h.store.set_account(name, role=b.get('role'))) if act == 'role' else
                (lambda: h.store.set_account(name, disabled=1)),
                (lambda: h.store.set_account(name, role=role_was)) if act == 'role' else
                (lambda: h.store.set_account(name, disabled=off_was)),
                dirs=getattr(h.d, 'dirs', None))
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'delete':
        h.store.drop_account(name)
"""),
])

edit('95_cli.py', [
("""                raise ValueError('that is the last full administrator who can sign in')
            if flag == 'set_role':
                if acc.get('source') == 'directory':
""",
 """                raise ValueError('that is the last full administrator who can sign in')
            if (flag in ('del_user', 'disable_user') or (flag == 'set_role' and args.role != 'fulladmin')) \\
                    and acc.get('role') == 'fulladmin' and not (flag == 'set_role' and acc.get('source') == 'directory'):
                # Counted again after the change, as the pages do (1.0.328).
                role_was, off_was = acc['role'], int(acc.get('disabled') or 0)
                store.fulladmin_change(
                    (lambda: store.set_account(name, role=args.role)) if flag == 'set_role' else
                    (lambda: store.set_account(name, disabled=1)),
                    (lambda: store.set_account(name, role=role_was)) if flag == 'set_role' else
                    (lambda: store.set_account(name, disabled=off_was)))
            if flag == 'set_role':
                if acc.get('source') == 'directory':
"""),
])

edit('88w_web.py', [
("""    if CONFIG.get('acme'):
        out['acme'] = acme_http_names(store)
    return out
""",
 """    # Off (1.0.328): the names it had put on port 80 taken back - none, said as none. Root's
    # helper leaves a port 80 it never put names on as it is.
    out['acme'] = acme_http_names(store) if CONFIG.get('acme') else []
    return out
"""),
])

edit('90d_dbagent.py', [
("""    body = json.dumps({'op': op, 'args': args}).encode()
""",
 """    # How long this node waits (1.0.328): an agent busy with another node's long operation
    # did this one after the node had given up and said it failed. A newer agent does not
    # begin it once that is over; an older one reads no more than op and args.
    body = json.dumps({'op': op, 'args': args, 'wait_s': max(5, int(timeout) - 5)}).encode()
"""),
])
