"""1.0.322 (parts): a copy made by a newer otp refused unless asked for on the command line; a
backup put back on a node of a shared database keeps the node's name; the split watch's probe
closes only its own connection."""
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


edit('85_dbfiles.py', [
("""        admins = con.execute("SELECT COUNT(*) FROM accounts WHERE role = 'fulladmin' AND "
                             "COALESCE(disabled, 0) = 0").fetchone()[0]
    except sqlite3.Error as e:
        return None, 'that database could not be read: %s' % e
    finally:
        con.close()
    return {'kind': 'sqlite', 'counts': counts, 'admins': admins,
            'tables': len([t for t in TABLES if t in names])}, ''
""",
 """        admins = con.execute("SELECT COUNT(*) FROM accounts WHERE role = 'fulladmin' AND "
                             "COALESCE(disabled, 0) = 0").fetchone()[0]
        # The version that made its tables last (1.0.322): what a newer one wrote is told apart.
        made = ''
        if 'meta' in names:
            for (v,) in con.execute("SELECT v FROM meta WHERE k LIKE 'schema:%'"):
                if _ver_tuple(v) > _ver_tuple(made or '0'):
                    made = str(v)
    except sqlite3.Error as e:
        return None, 'that database could not be read: %s' % e
    finally:
        con.close()
    return {'kind': 'sqlite', 'counts': counts, 'admins': admins, 'version': made or None,
            'tables': len([t for t in TABLES if t in names])}, ''
"""),
("""        said['no_admin'] = True
    said['bytes'] = Path(path).stat().st_size
    return said, ''
""",
 """        said['no_admin'] = True
    said['bytes'] = Path(path).stat().st_size
    # Made by a newer otp (1.0.322): its tables, columns and settings this version does not know
    # were left out or misread without a word - and every guard of a downgrade went round.
    v = said.get('version')
    if v and _ver_tuple(v) > _ver_tuple(__version__):
        said['newer'] = str(v)
    return said, ''
"""),
("""def db_file_restore(store, path, by, key_file=None, from_name='', need_admin=True):
    \"\"\"Put a copy or a dump back over everything. A copy of what is replaced
    is made first and kept with the others.\"\"\"
    engine = store.db.engine
    said, why = db_file_peek(path, engine, need_admin)
    if said is None:
        raise ValueError(why)
""",
 """def db_file_restore(store, path, by, key_file=None, from_name='', need_admin=True,
                    allow_newer=False):
    \"\"\"Put a copy or a dump back over everything. A copy of what is replaced
    is made first and kept with the others.\"\"\"
    engine = store.db.engine
    said, why = db_file_peek(path, engine, need_admin)
    if said is None:
        raise ValueError(why)
    if said.get('newer') and not allow_newer:
        raise ValueError(newer_copy_words(said['newer']))
"""),
("""def _sqlite_to_copy(path, out):
""",
 """def newer_copy_words(v):
    return ('that copy was made by otp %s, newer than %s here: what this version does not know of '
            'it (tables, columns, settings) would be lost or misread - install otp %s or newer '
            'here first, or put it back anyway on the command line with --allow-newer'
            % (v, __version__, v))


def _sqlite_to_copy(path, out):
"""),
])

edit('86b_rbackup.py', [
("""def rb_restore(store, path, password, by, keep_node_name=False, need_admin=True):
""",
 """def rb_restore(store, path, password, by, keep_node_name=False, need_admin=True, allow_newer=False):
"""),
("""        top, m = rb_open(path, password, work)
""",
 """        top, m = rb_open(path, password, work)
        if m.get('otp') and _ver_tuple(m['otp']) > _ver_tuple(__version__) and not allow_newer:
            raise ValueError(newer_copy_words(m['otp']))      # (1.0.322)
"""),
("""                              from_name=os.path.basename(str(path)), need_admin=need_admin)
""",
 """                              from_name=os.path.basename(str(path)), need_admin=need_admin,
                              allow_newer=allow_newer)
"""),
("""        if m.get('node') and not keep_node_name and m['node'] != old_name and \\
                not CONFIG.get('ha_mode'):
""",
 """        # Not on a node of a cluster of one shared database either (1.0.322): ha_mode is empty
        # there, and node2 became node1 - both nodes with one name.
        if m.get('node') and not keep_node_name and m['node'] != old_name and \\
                not in_cluster(store):
"""),
])

edit('95_cli.py', [
("""    g.add_argument('--passphrase-file', metavar='FILE', help='with --restore-bundle: the '
""",
 """    g.add_argument('--allow-newer', action='store_true', help='with --restore or --restore-bundle: '
                   'put back a copy made by a newer otp all the same (what this version does not '
                   'know of it is lost)')
    g.add_argument('--passphrase-file', metavar='FILE', help='with --restore-bundle: the '
"""),
("""            got = rb_restore(store, path, password, cli_who(),
                             keep_node_name=args.keep_node_name, need_admin=False)
""",
 """            got = rb_restore(store, path, password, cli_who(),
                             keep_node_name=args.keep_node_name, need_admin=False,
                             allow_newer=args.allow_newer)
"""),
("""            got = db_file_restore(store, args.restore, cli_who(),
                                  key_file=_key_beside(args.restore), need_admin=False)
""",
 """            got = db_file_restore(store, args.restore, cli_who(),
                                  key_file=_key_beside(args.restore), need_admin=False,
                                  allow_newer=args.allow_newer)
"""),
])

edit('87y_split.py', [
("""    def ask():
        try:
            db = SPLIT['peer_db']
""",
 """    def ask():
        db = None
        try:
            db = SPLIT['peer_db']
"""),
("""            got['e'] = str(e).split('\\n')[0][:200]
            try:
                if SPLIT['peer_db'] is not None:
                    SPLIT['peer_db'].close()
            except Exception:                           # noqa: BLE001
                pass
            SPLIT['peer_db'] = None
""",
 """            got['e'] = str(e).split('\\n')[0][:200]
            # Its own connection only (1.0.322): a probe late past its 3.5 s closed the next one's.
            try:
                if db is not None:
                    db.close()
            except Exception:                           # noqa: BLE001
                pass
            if SPLIT['peer_db'] is db:
                SPLIT['peer_db'] = None
"""),
])
