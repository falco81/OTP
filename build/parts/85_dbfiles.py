
# ---------------------------------------------------------------------------
# The files kept beside the database, the disk under it, and putting one back
# ---------------------------------------------------------------------------
# As on isemon (1.10.160 on): two kinds of file are kept.
#
#   A *copy* is made by this program: every row of every table, written as a
#   portable file, which goes back into any of the three engines. That is
#   what carries an installation from the file to a server and back.
#
#   A *dump* is made by the engine's own program - pg_dump, mariadb-dump, or
#   for the file SQLite's own backup, which is the file. It is a fraction of
#   the size, the server's own tools read it, and it goes back into the
#   engine it came off.
#
# Every one of either kind has the key that opens the tokens beside it, in a
# file of its own, because one without the other is nothing.

DUMP_DIR = STATE_DIR / 'dumps'
DUMP_SUFFIX = {'sqlite': '.db', 'mariadb': '.sql.gz', 'postgres': '.pgc', 'copy': '.json.gz'}
DUMP_WORDS = {'sqlite': 'a copy of the file', 'mariadb': 'a MariaDB dump',
              'postgres': 'a PostgreSQL dump', 'copy': 'a portable copy'}
DUMP_TOOLS = {'sqlite': (),
              'mariadb': (('making one', ('mariadb-dump', 'mysqldump')),
                          ('putting one back', ('mariadb', 'mysql'))),
              'postgres': (('making one', ('pg_dump',)),
                           ('putting one back', ('pg_restore',)))}
DUMP_INSTALL = {'mariadb': 'dnf install mariadb (it is the client, not the server)',
                'postgres': 'dnf install postgresql (it is the client, not the server)'}
DRIVERS = {'mariadb': ('pymysql', 'python3-PyMySQL'),
           'postgres': ('psycopg2', 'python3-psycopg2')}
NAME_RE = re.compile(r'^o(?:tp|pt)-(sqlite|mariadb|postgres|copy)?-?(\d{8}-\d{6})(?:-([a-z-]+))?'
                     r'(\.db|\.sql\.gz|\.pgc|\.json\.gz)$')


def drivers_state():
    """Whether the driver for each server engine is installed - said before
    somebody types an address rather than after they press a button."""
    out = {}
    for engine, (module, package) in DRIVERS.items():
        try:
            __import__(module)
            out[engine] = {'ready': True, 'package': package}
        except Exception as e:                          # noqa: BLE001
            out[engine] = {'ready': False, 'package': package,
                           'says': 'the driver %s is not installed (%s)' % (module, e)}
    return out


def dump_info(engine):
    """Which program tonight's dump will be made with, and whether it is here."""
    out = {'engine': engine, 'words': DUMP_WORDS.get(engine, engine),
           'suffix': DUMP_SUFFIX.get(engine, ''), 'where': str(DUMP_DIR),
           'install': DUMP_INSTALL.get(engine, ''), 'ready': True, 'why': ''}
    for what, names in DUMP_TOOLS.get(engine, ()):
        if not any(shutil.which(n) for n in names):
            out.update(ready=False, why='%s is not on this machine, so a dump cannot be %s'
                       % (names[0], 'made' if what == 'making one' else 'put back'))
            break
    return out


def _tool(names):
    for one in names:
        got = shutil.which(one)
        if got:
            return got
    raise ValueError('%s is not on this machine' % names[0])


def _db_conf():
    return {k: CONFIG.get(k) for k in DB_KEYS}


def safe_db_name(c):
    """The database's name, as it may stand on a command line: never one
    that reads as an option (1.0.33)."""
    name = str(c.get('db_name') or '')
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,62}\Z', name):
        raise DbError('the database name %r is not letters, digits and _' % name[:60])
    return name


def _my_cnf(c):
    """A defaults file holding the password and nothing else, 0600, gone the
    moment the program has finished with it: `--password=` on a command line
    is readable by everybody on the machine while it runs."""
    handle, name = tempfile.mkstemp(prefix='otp-my-', suffix='.cnf')
    os.close(handle)
    os.chmod(name, 0o600)
    with open(name, 'w') as f:
        said = str(c.get('db_password') or '')
        if any(ord(ch) < 32 for ch in said):
            raise DbError('the database password has a line break or another control '
                          'character in it')
        f.write('[client]\npassword="%s"\n' % said.replace('\\', '\\\\').replace('"', '\\"'))
    return name


def _my_args(c, cnf):
    out = ['--defaults-extra-file=%s' % cnf,
           '--host=%s' % (str(c.get('db_host') or '127.0.0.1').strip('[]')),
           '--port=%d' % int(c.get('db_port') or 3306),
           '--user=%s' % (c.get('db_user') or '')]
    # The dump and restore tools encrypted as the daemon's own connection is
    # (1.0.36).
    mode = str((c.get('db_tls') if 'db_tls' in c else CONFIG.get('db_tls')) or '')
    ca = str((c.get('db_tls_ca') if 'db_tls_ca' in c else CONFIG.get('db_tls_ca')) or '')
    if mode:
        out.append('--ssl')
        if mode in ('verify-ca', 'verify-full'):
            out.append('--ssl-verify-server-cert')
        if ca:
            out.append('--ssl-ca=%s' % ca)
    return out


def _pg_args(c):
    return ['--host=%s' % (str(c.get('db_host') or '127.0.0.1').strip('[]')),
            '--port=%d' % int(c.get('db_port') or 5432),
            '--username=%s' % (c.get('db_user') or ''), '--no-password']


def _pg_env(c):
    env = dict(os.environ)
    env['PGPASSWORD'] = str(c.get('db_password') or '')
    env['PGCONNECT_TIMEOUT'] = str(int(c.get('db_timeout_s') or 10))
    mode = str((c.get('db_tls') if 'db_tls' in c else CONFIG.get('db_tls')) or '')
    ca = str((c.get('db_tls_ca') if 'db_tls_ca' in c else CONFIG.get('db_tls_ca')) or '')
    if mode:
        env['PGSSLMODE'] = mode
        if ca:
            env['PGSSLROOTCERT'] = ca
    return env


def _run(args, words, stdin=None, stdout=None, env=None, seconds=3600):
    try:
        got = subprocess.run(args, stdin=stdin, stdout=stdout if stdout is not None
                             else subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                             timeout=seconds)
    except subprocess.TimeoutExpired:
        raise ValueError('%s took longer than %d s and was stopped' % (words, seconds))
    if got.returncode != 0:
        said = (got.stderr or b'').decode('utf-8', 'replace').strip().split('\n')
        raise ValueError('%s failed: %s' % (words, (said[-1] if said else
                                                     'exit %d' % got.returncode)[:300]))
    return got.stdout


def _stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def _key_beside(path):
    p = str(path)
    for suf in ('.json.gz', '.sql.gz', '.pgc', '.db'):
        if p.endswith(suf):
            return Path(p[:-len(suf)] + '.key')
    return Path(p + '.key')


def _write_key_beside(path):
    key = sealing_key()
    if key:
        write_replacing(_key_beside(path), key.hex() + '\n', 0o600)


def _kind_of_name(name):
    for kind, suf in (('copy', '.json.gz'), ('mariadb', '.sql.gz'), ('postgres', '.pgc'),
                      ('sqlite', '.db')):
        if name.endswith(suf):
            return kind
    return ''


def _prune(folder, pattern, keep):
    files = sorted((f for f in folder.glob(pattern) if NAME_RE.match(f.name)),
                   key=lambda f: f.stat().st_mtime)
    for old in files[:-keep] if keep > 0 and len(files) > keep else []:
        for f in (old, _key_beside(old)):
            try:
                f.unlink()
            except OSError:
                pass


def copy_engine(path):
    """Which engine a copy was taken off: its first line says."""
    import gzip
    try:
        with gzip.open(str(path), 'rt', encoding='utf-8') as f:
            return json.loads(f.readline() or '{}').get('engine') or ''
    except Exception:                                   # noqa: BLE001
        return ''


def kept_copies():
    """The copies this program made, newest first."""
    if not BACKUP_DIR.is_dir():
        return []
    out = []
    for f in sorted(list(BACKUP_DIR.glob('otp-*.json.gz')) + list(BACKUP_DIR.glob('opt-*.json.gz')),
                   key=lambda x: x.stat().st_mtime,
                    reverse=True):
        st = f.stat()
        out.append({'name': f.name, 'bytes': st.st_size, 'size': st.st_size, 'at': st.st_mtime,
                    'from': copy_engine(f), 'key': _key_beside(f).exists(), 'kind': 'copy'})
    return out


def kept_dumps(engine):
    """The dumps the engine made of itself, newest first."""
    if not DUMP_DIR.is_dir():
        return []
    out = []
    for f in sorted(DUMP_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        m = NAME_RE.match(f.name)
        if not m:
            continue
        kind = _kind_of_name(f.name)
        came = m.group(1) or ''
        if kind == 'copy':
            came = copy_engine(f) or came
        st = f.stat()
        out.append({'name': f.name, 'bytes': st.st_size, 'at': st.st_mtime, 'kind': kind,
                    'from': came if kind != 'copy' else came,
                    'mine': kind == 'copy' or kind == engine,
                    'key': _key_beside(f).exists()})
    return out


def make_dump(store, label='daily', folder=None):
    """A dump of the database in use by its own engine's program - or, where
    that program is not on this machine, a portable copy in its place."""
    engine = store.db.engine
    folder = Path(folder) if folder else DUMP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    info = dump_info(engine)
    kind = engine if info['ready'] else 'copy'
    name = 'otp-%s-%s-%s%s' % (engine if kind != 'copy' else 'copy', _stamp(),
                              re.sub(r'[^a-z-]', '', label) or 'daily', DUMP_SUFFIX[kind])
    target = folder / name
    part = Path(str(target) + '.part')
    c = _db_conf()
    try:
        if kind == 'copy':
            dump_tables(store.db, part)
        elif engine == 'sqlite':
            # SQLite's own backup: a consistent copy of the file even while the
            # daemon writes to it.
            src = sqlite3.connect(str(store.db.path))
            dst = sqlite3.connect(str(part))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        elif engine == 'mariadb':
            import gzip
            tool = _tool(('mariadb-dump', 'mysqldump'))
            cnf = _my_cnf(c)
            try:
                raw = Path(str(part) + '.raw')
                with open(str(raw), 'wb') as out:
                    _run([tool] + _my_args(c, cnf) + [
                        '--single-transaction', '--quick', '--skip-lock-tables',
                        '--default-character-set=utf8mb4', '--no-tablespaces',
                        '--add-drop-table', '--skip-comments', safe_db_name(c)],
                        'mariadb-dump', stdout=out)
                with open(str(raw), 'rb') as src, gzip.open(str(part), 'wb', 6) as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                raw.unlink()
            finally:
                os.unlink(cnf)
        else:
            tool = _tool(('pg_dump',))
            _run([tool] + _pg_args(c) + ['--format=custom', '--compress=6', '--no-owner',
                                         '--no-privileges', '--file=%s' % part,
                                         '--dbname=%s' % safe_db_name(c)],
                 'pg_dump', env=_pg_env(c))
        os.chmod(str(part), 0o640)
        part.replace(target)
    finally:
        for left in (part, Path(str(part) + '.raw')):
            if left.exists():
                try:
                    left.unlink()
                except OSError:
                    pass
    _write_key_beside(target)
    if folder == DUMP_DIR:
        _prune(DUMP_DIR, 'o[tp][tp]-*', int(CONFIG.get('backup_keep') or 14))
    store.add_event('backups', 'made %s (%s): %s' % (
        DUMP_WORDS[kind], {'daily': 'every night', 'by-hand': 'by hand',
                           'download': 'to be downloaded'}.get(label, label), target.name))
    return target


# ---- what is in a file, without putting any of it back ------------------------
def _magic(path):
    with open(str(path), 'rb') as f:
        return f.read(16)


def _peek_copy(path):
    import gzip
    counts, admins, tables, table = {}, 0, 0, None
    with gzip.open(str(path), 'rt', encoding='utf-8') as f:
        head = json.loads(f.readline() or '{}')
        if 'otp' not in head and 'opt' not in head:      # 'opt': before 1.0.37's new name
            return None, 'that is not a copy made by otp'
        for line in f:
            got = json.loads(line)
            if set(got.keys()) == {'table'}:
                table = got['table']
                tables += 1
                counts.setdefault(table, 0)
                continue
            if table:
                counts[table] += 1
                if table == 'accounts' and got.get('role') == 'fulladmin' \
                        and not got.get('disabled'):
                    admins += 1
    return {'kind': 'copy', 'from': head.get('engine') or '', 'version': head.get('otp') or head.get('opt'),
            'made': head.get('made'), 'counts': counts, 'admins': admins, 'tables': tables,
            'key': bool(head.get('key')), 'machine': head.get('machine')}, ''


def _peek_sqlite(path):
    try:
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    except sqlite3.Error as e:
        return None, 'that file could not be opened: %s' % e
    try:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        if 'accounts' not in names or 'tokens' not in names:
            return None, 'that is not a database of otp: it has no tokens and no accounts'
        counts = {t: con.execute('SELECT COUNT(*) FROM %s' % t).fetchone()[0]
                  for t in TABLES if t in names}
        admins = con.execute("SELECT COUNT(*) FROM accounts WHERE role = 'fulladmin' AND "
                             "COALESCE(disabled, 0) = 0").fetchone()[0]
    except sqlite3.Error as e:
        return None, 'that database could not be read: %s' % e
    finally:
        con.close()
    return {'kind': 'sqlite', 'counts': counts, 'admins': admins,
            'tables': len([t for t in TABLES if t in names])}, ''


def _peek_mariadb(path):
    import gzip
    tables, admins, users, in_users = set(), 0, 0, False
    with gzip.open(str(path), 'rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('CREATE TABLE'):
                got = re.search(r'CREATE TABLE `([^`]+)`', line)
                if got:
                    tables.add(got.group(1))
                continue
            first = line.startswith('INSERT INTO `accounts`')
            if first:
                in_users = True
            elif in_users and not line.startswith('('):
                in_users = False
            if in_users:
                admins += line.count(",'fulladmin',")
                rest = line.split('VALUES', 1)[-1] if first else line
                users += rest.count('),(') + (1 if '(' in rest else 0)
                if line.rstrip().endswith(';'):
                    in_users = False
    if 'accounts' not in tables or 'tokens' not in tables:
        return None, 'that dump is not one of otp - it has no tokens and no accounts'
    return {'kind': 'mariadb', 'counts': {'accounts': users}, 'admins': admins,
            'tables': len(tables)}, ''


def _peek_postgres(path):
    tool = shutil.which('pg_restore')
    if not tool:
        return None, ('pg_restore is not on this machine, so what is in that dump cannot be '
                      'read: %s' % DUMP_INSTALL['postgres'])
    listed = _run([tool, '--list', str(path)], 'pg_restore --list', seconds=300)
    tables = set(re.findall(r'TABLE DATA\s+\S+\s+(\S+)', listed.decode('utf-8', 'replace')))
    if 'accounts' not in tables or 'tokens' not in tables:
        return None, 'that dump is not one of otp - it has no tokens and no accounts'
    rows = _run([tool, '--data-only', '--table=accounts', '--file=-', str(path)],
                'pg_restore', seconds=300).decode('utf-8', 'replace')
    users = admins = 0
    inside = False
    for line in rows.split('\n'):
        if line.startswith('COPY '):
            inside = True
            continue
        if inside:
            if line == '\\.':
                break
            users += 1
            if '\tfulladmin\t' in line:
                admins += 1
    return {'kind': 'postgres', 'counts': {'accounts': users}, 'admins': admins,
            'tables': len(tables)}, ''


def db_file_peek(path, engine, need_admin=True):
    """What is in a copy or a dump, and whether it may be put back here."""
    head = _magic(path)
    try:
        if head.startswith(b'SQLite format 3'):
            said, why = _peek_sqlite(path)
        elif head.startswith(b'PGDMP'):
            said, why = _peek_postgres(path)
        elif head[:2] == b'\x1f\x8b':
            import gzip
            with gzip.open(str(path), 'rb') as f:
                first = f.read(64)
            if first.startswith(b'{'):
                said, why = _peek_copy(path)
            else:
                said, why = _peek_mariadb(path)
        else:
            return None, 'that is neither a copy nor a dump made by otp'
    except Exception as e:                              # noqa: BLE001
        return None, 'that file could not be read: %s' % str(e).split('\n')[0][:200]
    if said is None:
        return None, why
    kind = said['kind']
    if kind not in ('copy', 'sqlite') and kind != engine:
        return None, ('that is %s, and this installation is on %s: a dump goes back only into '
                      'the engine it came off. Use a copy - a copy goes into any of the three.'
                      % (DUMP_WORDS[kind], ENGINE_WORDS.get(engine, engine)))
    if not said.get('admins'):
        # On the command line root makes one afterwards (1.0.62): a copy of
        # a server set up there alone was refused for good.
        if need_admin:
            return None, ('there is no full administrator who can sign in in that file: putting '
                          'it back would lock everybody out of these pages (on the command line '
                          'it can be put back, and an account made after it)')
        said['no_admin'] = True
    said['bytes'] = Path(path).stat().st_size
    return said, ''


def _sqlite_to_copy(path, out):
    """A SQLite file of ours, as a copy: so that it goes back into whatever
    engine is in use, by the same road as every copy."""
    src = Db('sqlite', path=path)
    try:
        dump_tables(src, out, [t for t in TABLES if t in src.tables()])
    finally:
        src.close()
    return out


def db_file_restore(store, path, by, key_file=None, from_name='', need_admin=True):
    """Put a copy or a dump back over everything. A copy of what is replaced
    is made first and kept with the others."""
    engine = store.db.engine
    said, why = db_file_peek(path, engine, need_admin)
    if said is None:
        raise ValueError(why)
    kind = said['kind']
    if CONFIG.get('ha_mode') == 'replicated' and kind in ('postgres', 'mariadb'):
        raise ValueError('a dump puts tables back by making them again, which replication '
                         'does not carry to the other node: put a copy back instead (it goes '
                         'over row by row)')
    # A kept copy is read from a copy of its own (1.0.44): the safety copy
    # below rotates the kept ones, and the oldest - the one being put back -
    # would be the one it took away.
    held = []
    try:
        if Path(path).resolve().parent == Path(BACKUP_DIR).resolve():
            ext = ''.join(Path(path).suffixes[-2:]) if str(path).endswith('.gz') else Path(path).suffix
            fd, tmpname = tempfile.mkstemp(prefix='otp-putback-', suffix=ext, dir=str(STATE_DIR))
            os.close(fd)
            shutil.copyfile(str(path), tmpname)
            os.chmod(tmpname, 0o600)
            held.append(Path(tmpname))
            kf = Path(key_file) if key_file else None
            if kf and kf.exists():
                fd, kname = tempfile.mkstemp(prefix='otp-putback-', suffix='.key', dir=str(STATE_DIR))
                os.close(fd)
                shutil.copyfile(str(kf), kname)
                os.chmod(kname, 0o600)
                held.append(Path(kname))
                key_file = kname
            path = tmpname
        return _db_file_restore(store, path, by, key_file, from_name, kind)
    finally:
        for x in held:
            try:
                x.unlink()
            except OSError:
                pass


def _db_file_restore(store, path, by, key_file, from_name, kind):
    # The key that opens the tokens in it: beside a kept file, or inside a copy
    # that was downloaded with it.
    key_hex = ''
    if key_file and Path(key_file).exists():
        key_hex = Path(key_file).read_text().strip()
    elif kind == 'copy':
        import gzip
        with gzip.open(str(path), 'rt', encoding='utf-8') as f:
            key_hex = str(json.loads(f.readline() or '{}').get('key') or '')
    # In a cluster the other node keeps its own key, and the rows going over
    # would be ones it cannot open (1.0.44): a copy sealed with another key
    # is refused there before anything is replaced.
    if CONFIG.get('ha_mode') == 'replicated' and re.match(r'^[0-9a-f]{64}\Z', key_hex):
        now = sealing_key()
        if now and now.hex() != key_hex:
            raise ValueError('this copy was sealed with another key than the one both nodes '
                             'use; in a cluster it cannot be put back - the other node could '
                             'not open its tokens')
    safety = make_backup(store, 'before putting %s back, by %s' % (from_name or 'a file', by))
    # The link between the databases describes the machines, not the data
    # (1.0.104): the authority and each node's steps as they are now stay;
    # a copy without them leaves them, one from before keeps no older ones.
    try:
        live_tls = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'hatls:%'")
    except Exception:                                   # noqa: BLE001
        live_tls = []
    c = _db_conf()
    if kind == 'copy':
        load_tables(store.db, path)
    elif kind == 'sqlite':
        fd, tmp = tempfile.mkstemp(prefix='otp-restore-', suffix='.json.gz', dir=str(STATE_DIR))
        os.close(fd)                    # not left open, one each time (1.0.139)
        tmp = Path(tmp)
        try:
            _sqlite_to_copy(path, tmp)
            load_tables(store.db, tmp)
        finally:
            tmp.unlink()
    elif kind == 'mariadb':
        import gzip
        tool = _tool(('mariadb', 'mysql'))
        with gzip.open(str(path), 'rb') as sent:
            for n, line in enumerate(sent):
                if line[:1] == b'\\' or line[:7].lower() == b'system ':
                    raise ValueError('line %d of the dump is a client command, not SQL. '
                                     'A dump this program made has none.' % (n + 1))
        cnf = _my_cnf(c)
        # The client is given the SQL itself: a gzip reader has no file
        # descriptor of its own to hand a program, so it is unpacked first.
        fd, raw = tempfile.mkstemp(prefix='otp-sql-', dir=str(STATE_DIR))
        os.close(fd)
        raw = Path(raw)
        try:
            with gzip.open(str(path), 'rb') as src, open(str(raw), 'wb') as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            with open(str(raw), 'rb') as sent:
                _run([tool] + _my_args(c, cnf) + ['--default-character-set=utf8mb4',
                                                  '--local-infile=0', '--binary-mode',
                                                  safe_db_name(c)],
                     'the MariaDB client', stdin=sent)
        finally:
            os.unlink(cnf)
            try:
                raw.unlink()
            except OSError:
                pass
    else:
        tool = _tool(('pg_restore',))
        _run([tool] + _pg_args(c) + ['--single-transaction', '--clean', '--if-exists',
                                     '--no-owner', '--no-privileges',
                                     '--dbname=%s' % safe_db_name(c), str(path)],
             'pg_restore', env=_pg_env(c))
    store.db.make_tables()
    if CONFIG.get('ha_mode') == 'replicated' and store.db.engine == 'postgres':
        ha_sequences(store.db, int(CONFIG.get('ha_slot') or 1))
    for r in live_tls:
        try:
            store.set_meta(r['k'], r['v'])
        except Exception:                               # noqa: BLE001
            pass
    hatls_check_soon()      # and then looked at: what is in place against what is wanted
    key_said = 'the key that opens the tokens stays as it was'
    if re.match(r'^[0-9a-f]{64}\Z', key_hex):
        now = sealing_key()
        if not now or now.hex() != key_hex:
            # The cluster's authority kept from before is sealed with the key
            # going out (1.0.139): opened now, sealed again with the new one -
            # it could not be opened after, and had to be made anew.
            cas = None
            for r in live_tls:
                if r['k'] == 'hatls:ca':
                    try:
                        cas = (json.loads(r['v'] or 'null') or {}).get('cas')
                        for ca in cas or []:
                            ca['key'] = unseal_secret(ca.get('key'), bind='hatls:ca')
                    except (ValueError, AttributeError, TypeError):
                        cas = None
            write_replacing(sealing_key_path(), key_hex + '\n', 0o600)
            key_said = 'the key that opens the tokens came with it and is in use now'
            if cas and all(ca.get('key') for ca in cas):
                for ca in cas:
                    ca['key'] = seal_secret(ca['key'], bind='hatls:ca')
                try:
                    store.set_meta('hatls:ca', json.dumps({'cas': cas}))
                except Exception as e:                  # noqa: BLE001
                    log('the authority of the cluster could not be sealed again: %s' % e, 'warn')
    else:
        # No key came with it (1.0.59): whether the tokens put back open with
        # the key in use is looked at, and said loudly when they do not.
        try:
            rows = store.db.rows('SELECT name, secret FROM tokens WHERE secret IS NOT NULL '
                                 "AND secret <> '' ORDER BY id LIMIT 5")
            if rows and not any(unseal_secret(r['secret'], token_bind(r['name']))
                                for r in rows):
                key_said = ('NO KEY CAME WITH IT and its tokens do not open with the key in '
                            'use: put back the .key file that was beside the dump (or the '
                            'copy from the download) - until then every token is refused')
                store.add_event('backups', 'the database put back from %s came without its key '
                                'and its tokens cannot be opened' % (from_name or 'a file'),
                                'bad', who=by)
        except Exception as e:                          # noqa: BLE001
            log('the tokens put back could not be tried with the key: %s' % e, 'warn')
    bump(store)
    store.add_event('backups', '%s put the database back from %s (%s); what it replaced is in %s'
                    % (by, from_name or 'a file', DUMP_WORDS.get(kind, kind), safety.name),
                    'warn', who=by)
    return {'safety': safety.name, 'kind': kind, 'key': key_said}


# ---- the disk under it ----------------------------------------------------------
def note_size(store):
    """The size of the database, once a day, for how fast it grows."""
    try:
        sizes = json.loads(store.get_meta('db_sizes:' + node_name()) or '{}')
    except ValueError:
        sizes = {}
    today = datetime.now().strftime('%Y-%m-%d')
    if sizes.get('engine') != store.db.engine:
        sizes = {'engine': store.db.engine, 'days': {}}
    if today not in sizes['days']:
        sizes['days'][today] = int(store.db.size() or 0)
        for old in sorted(sizes['days'])[:-60]:
            del sizes['days'][old]
        store.set_meta('db_sizes:' + node_name(), json.dumps(sizes))
    return sizes


def db_growth(store):
    days = note_size(store).get('days', {})
    edge = (datetime.now().timestamp() - 15 * 86400)
    seen = sorted((d, b) for d, b in days.items()
                  if datetime.strptime(d, '%Y-%m-%d').timestamp() >= edge)
    if len(seen) < 2:
        return {'a_day': 0, 'over_days': 0}
    (d0, b0), (d1, b1) = seen[0], seen[-1]
    span = max(1, (datetime.strptime(d1, '%Y-%m-%d') - datetime.strptime(d0, '%Y-%m-%d')).days)
    return {'a_day': max(0, int((b1 - b0) / span)), 'over_days': span}


def _folder_bytes(folder):
    total = 0
    if Path(folder).is_dir():
        for f in Path(folder).iterdir():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def db_disk(store):
    db = store.db
    where = db.path.parent if db.engine == 'sqlite' else STATE_DIR
    out = {'where': str(where), 'total': 0, 'free': 0, 'share': 0, 'days_left': None,
           'holds': 'the database itself, its copies and its dumps' if db.engine == 'sqlite'
           else 'the copies and the dumps - the database itself is on the server'}
    try:
        u = shutil.disk_usage(str(where))
        out.update(total=u.total, free=u.free,
                   share=round(100.0 * (u.total - u.free) / u.total) if u.total else 0)
    except OSError:
        pass
    grew = db_growth(store)
    if grew['a_day'] and out['free']:
        out['days_left'] = int(out['free'] / grew['a_day'])
    parts = []
    if db.engine == 'sqlite':
        for suffix, what in (('', 'the database'), ('-wal', 'what is written, not yet folded in'),
                             ('-shm', 'the index of that')):
            f = Path(str(db.path) + suffix)
            if f.exists():
                parts.append({'name': f.name, 'what': what, 'bytes': f.stat().st_size})
    else:
        parts.append({'name': db.where(), 'what': 'the database, on the server',
                      'bytes': int(db.size() or 0)})
    parts.append({'name': str(BACKUP_DIR), 'what': 'the copies', 'bytes':
                  _folder_bytes(BACKUP_DIR)})
    parts.append({'name': str(DUMP_DIR), 'what': 'the dumps', 'bytes': _folder_bytes(DUMP_DIR)})
    return out, grew, parts


def db_cache(store):
    """The server's own cache, where it is left as installed and the database
    has outgrown it."""
    db = store.db
    if db.engine == 'sqlite':
        return None
    try:
        if db.engine == 'postgres':
            setting = 'shared_buffers'
            cache = int(db.value("SELECT setting::bigint * 8192 FROM pg_settings "
                                 "WHERE name = 'shared_buffers'") or 0)
        else:
            setting = 'innodb_buffer_pool_size'
            r = db.row("SHOW GLOBAL VARIABLES LIKE 'innodb_buffer_pool_size'")
            cache = int(list(r.values())[1]) if r else 0
    except Exception:                                   # noqa: BLE001
        return None
    size = int(db.size() or 0)
    ram = 0
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    ram = int(line.split()[1]) * 1024
    except OSError:
        pass
    return {'engine': ENGINE_WORDS.get(db.engine), 'setting': setting, 'cache': cache,
            'size': size, 'ram': ram, 'low': bool(cache and size > cache)}


# ---- erasing what was collected -----------------------------------------------
ERASABLE = [
    ('radius', 'radius_log', 'the RADIUS requests',
     'every request the VPN sent and what it was answered, with its steps. Nothing reads them '
     'back: they are the record of what happened.'),
    ('otp', 'otp_log', 'the checks of a code',
     'every code typed on the enrolment pages, in a test or through RADIUS, right or wrong. '
     'The tokens themselves are not touched: nobody has to enrol again.'),
    ('events', 'events', 'the event log',
     'what this program noted about itself: sign-ins, changes, copies, starts and stops.'),
]


def db_erasable(store):
    groups = []
    for key, table, name, says in ERASABLE:
        groups.append({'key': key, 'name': name, 'says': says,
                       'rows': int(store.db.value('SELECT COUNT(*) FROM %s' % table) or 0)})
    return {'groups': groups, 'bytes': int(store.db.size() or 0)}


def db_erase_job(store, groups, tidy, by):
    tables = [(t, n) for k, t, n, _ in ERASABLE if k in groups]
    if not tables:
        raise ValueError('nothing was ticked')

    def work(progress):
        progress(0, len(tables) + 2, 'making a copy first')
        copy = make_backup(store, 'before erasing, by %s' % by)
        gone = {}
        for i, (t, n) in enumerate(tables):
            progress(i + 1, len(tables) + 2, 'emptying %s' % n)
            gone[t] = store.db.run('DELETE FROM %s' % t)
        given = None
        if tidy:
            progress(len(tables) + 1, len(tables) + 2, 'giving the disk back')
            given = db_give_back(store, lambda *a: None)
        store.add_event('settings', '%s erased %s (a copy was made first: %s)'
                        % (by, ', '.join(n for _, n in tables), copy.name), 'warn', who=by)
        progress(len(tables) + 2, len(tables) + 2, 'done')
        return {'erased': gone, 'copy': copy.name, 'given': given}
    return db_job('erasing the collected data', work)


# ---- the server's settings: what was done, what waits for a start ---------------
def tune_state(store):
    db = store.db
    out = {'engine': db.engine, 'last': None, 'pending': [], 'lost': [],
           'restart': {'may': False, 'unit': {'postgres': 'postgresql',
                                              'mariadb': 'mariadb'}.get(db.engine, '')}}
    try:
        last = json.loads(store.get_meta('tune_last:' + node_name()) or 'null')
    except ValueError:
        last = None
    out['last'] = last
    if db.engine == 'postgres':
        try:
            out['pending'] = [r['name'] for r in db.rows(
                'SELECT name FROM pg_settings WHERE pending_restart')]
        except Exception:                               # noqa: BLE001
            pass
    elif db.engine == 'mariadb' and last and not last.get('undone') \
            and last.get('engine') == 'mariadb':
        now = tune_current(db, list((last.get('set') or {}).keys()))
        out['lost'] = [n for n, v in (last.get('set') or {}).items()
                       if not tune_same('mariadb', now.get(n, ''), v)]
    return out
