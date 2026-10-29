
# ---- going back to an older version (1.0.143) ---------------------------------------
# Never by putting a database back: the tables stay as they are - every column
# a newer version added is one an older one leaves alone (they are all added
# NULL) - and the older program runs on them. That is safe only for a version
# that reads what the newer ones wrote, so each version says how far back it
# may go (DOWNGRADE_FLOOR), and going back is refused below the highest floor
#   * of any version that ran on this database (each node keeps its own in
#     'downgrade:floor:NODE' - one writer a row, as replication wants), and
#   * of any version installed on this machine (install.sh keeps it in
#     /usr/local/lib/otp/downgrade-floor, root's alone: the otp account cannot
#     lower it, so it cannot take the server back to a version with a hole);
# and the package itself is looked at before anything is put in: a column the
# database has as NOT NULL with no default that the older version does not
# know would make every row it writes there fail. Then it goes the road of an
# upgrade - one node at a time, each in maintenance while it is done.
DOWNGRADE_FLOOR_FILE = UPGRADE_HELPER.parent / 'downgrade-floor'


def downgrade_floor_note(store):
    """This node's floor in the database: the highest of what it had and what
    this version says."""
    k = 'downgrade:floor:' + node_name()
    had = _meta_json(store, k) or {}
    if had and _ver_tuple(had.get('floor')) >= _ver_tuple(DOWNGRADE_FLOOR):
        return
    store.set_meta(k, json.dumps({'floor': DOWNGRADE_FLOOR, 'version': __version__,
                                  'at': time.time()}))


def downgrade_db_floor(store):
    """(floor, set by): the highest floor of any version that ran on this
    database, on any node."""
    best, by = DOWNGRADE_FLOOR, '%s (%s)' % (__version__, node_name())
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'downgrade:floor:%'"):
        try:
            got = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        if isinstance(got, dict) and _ver_tuple(got.get('floor')) > _ver_tuple(best):
            best, by = str(got['floor']), '%s (%s)' % (got.get('version'),
                                                      r['k'][len('downgrade:floor:'):])
    return best, by


def downgrade_root_floor():
    """The floor root keeps, or None where no version that knows it was ever
    installed here."""
    try:
        text = DOWNGRADE_FLOOR_FILE.read_text().strip()
    except OSError:
        return None
    return text if re.match(r'^\d+\.\d+\.\d+\Z', text) else None


def downgrade_why_not(store, version):
    """What stands in the way of going back to `version` - before the package
    is fetched: [] when nothing does."""
    why = []
    v = _ver_tuple(version)
    if v >= _ver_tuple(__version__):
        why.append('%s is not older than %s, which runs here - that is an upgrade'
                   % (version, __version__))
        return why
    floor, by = downgrade_db_floor(store)
    if v < _ver_tuple(floor):
        why.append('older than %s: otp %s, which ran on this database, wrote what older '
                   'versions do not read the same (or have holes it fixed)' % (floor, by))
    root = downgrade_root_floor()
    if root is None:
        why.append('this machine was never upgraded on the command line to a version that '
                   'can go back (install.sh --upgrade once)')
    elif v < _ver_tuple(root):
        why.append('older than %s, the oldest the versions installed on this machine allow'
                   % root)
    return why


def downgrade_live_strict(db):
    """{table: [column]} - the columns of this database that are NOT NULL and
    have no default: a row written without one of them fails."""
    out = {}
    if db.engine == 'sqlite':
        for t in TABLES:
            for r in db.rows('PRAGMA table_info(%s)' % t):
                if r['notnull'] and r['dflt_value'] is None and not r['pk']:
                    out.setdefault(t, []).append(str(r['name']).lower())
        return out
    if db.engine == 'postgres':
        rows = db.rows("SELECT table_name AS t, column_name AS c FROM information_schema.columns "
                       "WHERE table_schema = current_schema() AND is_nullable = 'NO' "
                       "AND column_default IS NULL")
    else:
        rows = db.rows("SELECT table_name AS t, column_name AS c FROM information_schema.columns "
                       "WHERE table_schema = DATABASE() AND is_nullable = 'NO' "
                       "AND column_default IS NULL AND extra NOT LIKE '%auto_increment%'")
    for r in rows:
        t, c = str(r['t']).lower(), str(r['c']).lower()
        if t in TABLES and c != 'id':
            out.setdefault(t, []).append(c)
    return out


# Run in a process of its own, on the package's own otp.py: its tables as it
# makes them, made in a database in memory and read back.
_DOWNGRADE_SCHEMA_PY = r'''
import json, sqlite3, sys
sys.path.insert(0, sys.argv[1])
sys.argv = ['otp']
import otp
c = sqlite3.connect(':memory:')
out = {}
for name, ddl in otp.SCHEMA:
    c.execute(ddl.format(**otp.TYPES['sqlite']))
    out[name] = [str(r[1]).lower() for r in c.execute('PRAGMA table_info(%s)' % name)]
print(json.dumps({'version': otp.__version__, 'tables': out}))
'''


def downgrade_package_schema(path):
    """The tables and columns the package's version knows, read off its own
    otp.py (the package checked and signed first)."""
    work = Path(tempfile.mkdtemp(prefix='otp-down-', dir=str(UPGRADE_DIR)))
    try:
        with tarfile.open(str(path), 'r:gz') as tf:
            member = next((m for m in tf.getmembers()
                           if re.match(r'^otp-[0-9.]+/otp\.py\Z', m.name) and m.isfile()), None)
            if member is None:
                raise ValueError('the package has no otp.py')
            with tf.extractfile(member) as src, open(str(work / 'otp.py'), 'wb') as dst:
                shutil.copyfileobj(src, dst)
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
               'OTP_STATE': str(work), 'OTP_CONFIG': str(work / 'none.json'),
               'OTP_LOGDIR': str(work), 'OTP_RUN': str(work)}
        r = subprocess.run([sys.executable, '-I', '-c', _DOWNGRADE_SCHEMA_PY, str(work)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
                           env=env, cwd=str(work))
        try:
            return json.loads(r.stdout.decode('utf-8', 'replace').strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise ValueError('the tables of the package could not be read: %s'
                             % r.stderr.decode('utf-8', 'replace').strip()[-300:])
    finally:
        shutil.rmtree(str(work), ignore_errors=True)


def downgrade_schema_why(store, path):
    """What in this database the package's version could not live with: []
    when nothing."""
    got = downgrade_package_schema(path)
    knows = got.get('tables') or {}
    why = []
    for t, cols in sorted(downgrade_live_strict(store.db).items()):
        if t not in knows:
            continue                    # a table it never writes
        lack = [c for c in cols if c not in knows[t]]
        if lack:
            why.append('the table %s has %s, which otp %s does not know and every row needs'
                       % (t, ', '.join(lack), got.get('version')))
    return why


def downgrade_list(store):
    """The older versions at upgrade_url, each with what stands in its way."""
    url = online_url()
    if not url:
        raise ValueError('no upgrade_url is set (Settings → Upgrades)')
    out = []
    for p in online_list(url):
        if _ver_tuple(p['version']) >= _ver_tuple(__version__):
            continue
        out.append(dict(p, why=downgrade_why_not(store, p['version'])))
    out.sort(key=lambda p: _ver_tuple(p['version']), reverse=True)
    floor, by = downgrade_db_floor(store)
    return {'url': url, 'here': __version__, 'versions': out, 'floor': floor,
            'floor_by': by, 'root_floor': downgrade_root_floor()}


def downgrade_take(store, path, info, by):
    """A checked package of an older version kept for going back: refused
    when anything stands in its way. Its meta."""
    why = downgrade_why_not(store, info['version'])
    if not why:
        why = downgrade_schema_why(store, path)
    if why:
        store.add_event('starting and stopping', 'going back to otp %s was refused: %s'
                        % (info['version'], '; '.join(why)), 'warn', who=by)
        raise ValueError('otp %s cannot be gone back to: %s' % (info['version'], '; '.join(why)))
    meta = upgrade_store_package(store, path, info, by)
    meta['downgrade'] = True
    store.set_meta('upgrade:pkg', json.dumps(meta))
    store.add_event('starting and stopping', '%s made otp %s ready to go back to (signed by %s; '
                    'the database checked for it)' % (by, meta['version'], meta.get('signed_by')),
                    'warn', who=by)
    return meta


def downgrade_fetch(store, version, by):
    """The older package from upgrade_url, checked, and kept for going back."""
    why = downgrade_why_not(store, version)
    if why:
        raise ValueError('otp %s cannot be gone back to: %s' % (version, '; '.join(why)))
    return online_fetch(store, version, by, older=True)


def downgrade_file(store, path, by):
    """An older package from a file (the command line), checked and kept."""
    info = upgrade_inspect(path)
    if not info.get('older'):
        raise ValueError('otp %s is not older than %s, which runs here - that is an upgrade'
                         % (info['version'], info.get('installed') or __version__))
    return downgrade_take(store, path, info, by)


def changelog_sections(text):
    """{version: its section of CHANGELOG.md, heading and all}."""
    out = {}
    for m in re.finditer(r'^## (\d+\.\d+\.\d+)\b.*?(?=^## |\Z)', text or '', re.M | re.S):
        out[m.group(1)] = m.group(0).strip()[:20000]
    return out


def downgrade_changelog(version):
    """What came in `version`, and what going back to it from here gives up -
    the sections of the versions after it, up to this one (1.0.144). From the
    CHANGELOG.md installed beside otp.py; where that does not have it, from
    the package at upgrade_url (read, not yet checked)."""
    version = str(version or '')
    if not re.match(r'^\d+\.\d+\.\d+\Z', version):
        raise ValueError('which version?')
    try:
        here = changelog_sections((Path(__file__).resolve().parent / 'CHANGELOG.md')
                                  .read_text(encoding='utf-8', errors='replace'))
    except OSError:
        here = {}
    lost = [{'version': v, 'text': here[v]} for v in sorted(
        here, key=_ver_tuple, reverse=True)
        if _ver_tuple(version) < _ver_tuple(v) <= _ver_tuple(__version__)]
    entry, src = here.get(version), 'here'
    if entry is None:
        src = 'package'
        pk = next((p for p in online_list(online_url()) if p['version'] == version), None)
        if not pk:
            raise ValueError('otp %s is not at %s' % (version, online_url()))
        data, _ct, _final = _online_get(pk['url'], limit=UPGRADE_MOST, timeout=120)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
            m = next((x for x in tf.getmembers() if x.isfile() and
                      x.name == 'otp-%s/CHANGELOG.md' % version), None)
            text = tf.extractfile(m).read(4 << 20).decode('utf-8', 'replace') if m else ''
        entry = changelog_sections(text).get(version) or ''
    return {'version': version, 'here': __version__, 'entry': entry, 'from': src,
            'lost': lost}
