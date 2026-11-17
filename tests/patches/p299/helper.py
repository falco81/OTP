# 1.0.299: otp_upgrade.py tells the pages how far an upgrade is - /var/www/otp/.upgrade.json.
#   python3 helper.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/deploy/otp_upgrade.py'


def edit(pairs):
    s = open(F).read()
    for a, b in pairs:
        assert s.count(a) == 1, (s.count(a), a[:90])
        s = s.replace(a, b)
    open(F, 'w').write(s)


edit([
("""FLOOR_FILE = os.path.join(LIB_DIR, 'downgrade-floor')
""",
 """FLOOR_FILE = os.path.join(LIB_DIR, 'downgrade-floor')
# How far an upgrade is, for the pages (1.0.299): beside them, a dot name nginx never serves, read
# by PHP straight from the disk while the daemon, nginx and PHP restart. install.sh --upgrade
# writes its steps there itself; this writes the first (the package checked) and a refusal.
PAGES_FILE = os.environ.get('OTP_PAGES_UPGRADE', '/var/www/otp/.upgrade.json')
"""),
("""def status(**fields):
    fields['at'] = time.time()
    write_safely(os.path.join(UPGRADE_DIR, 'status.json'), json.dumps(fields))
""",
 """def status(**fields):
    fields['at'] = time.time()
    write_safely(os.path.join(UPGRADE_DIR, 'status.json'), json.dumps(fields))


def pages_said():
    \"\"\"What the pages' file says now ({} when nothing, or nothing that reads).\"\"\"
    try:
        fd = os.open(PAGES_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            got = json.loads(f.read(65536).decode('utf-8'))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def _node_name():
    \"\"\"This node's name as otp knows it (its settings), else the machine's short name.\"\"\"
    try:
        with open(os.environ.get('OTP_CONFIG', '/etc/otp/config.json'), encoding='utf-8') as f:
            got = json.load(f).get('node_name')
        if isinstance(got, str) and got:
            return got
    except (OSError, ValueError, AttributeError):
        pass
    return os.uname()[1].split('.')[0]


def pages_tell(state, ident, version, by='', part=1, parts=0, words='', said='', frm='',
               downgrade=False, started=None):
    \"\"\"The pages' file written whole (1.0.299): a new file in its own folder - root's - renamed
    over it, 0644. Never a reason for the upgrade to stop: no folder (no pages here), a link in
    its place, anything at all - nothing is written.\"\"\"
    def text(v, most=200):
        return re.sub(r'[\\x00-\\x1f\\x7f]', '', str(v or ''))[:most]
    try:
        folder = os.path.dirname(PAGES_FILE)
        st = os.lstat(folder)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            return
        dfd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return
    try:
        now = time.time()
        row = {'state': state, 'id': text(ident, 64), 'version': text(version, 20),
               'from': text(frm, 20), 'by': text(by, 100), 'node': text(_node_name(), 64),
               'part': int(part), 'parts': int(parts), 'words': text(words),
               'started': int(started or now), 'at': int(now), 'said': text(said, 300),
               'downgrade': bool(downgrade)}
        name = os.path.basename(PAGES_FILE)
        tmp = '%s.%d.%d' % (name, os.getpid(), int(now * 1e6) % 10 ** 9)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dfd)
        with os.fdopen(fd, 'w') as out:
            os.fchmod(out.fileno(), 0o644)
            out.write(json.dumps(row) + '\\n')
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
    except (OSError, ValueError, TypeError):
        try:
            os.unlink(tmp, dir_fd=dfd)
        except (OSError, NameError):
            pass
    finally:
        os.close(dfd)
"""),
("""def put_in(package, ident='', want_sha='', by='the command line', log_to=None,
           downgrade=False):""",
 """def put_in(package, ident='', want_sha='', by='the command line', log_to=None,
           downgrade=False, started=None):"""),
("""               'OTP_UPGRADE_BY': str(by)[:100]}""",
 """               'OTP_UPGRADE_BY': str(by)[:100]}
        # Its id and when it began, for the pages' file install.sh goes on writing (1.0.299).
        if ident:
            env['OTP_UPGRADE_ID'] = re.sub(r'[^A-Za-z0-9._-]', '', str(ident))[:64]
        if started:
            env['OTP_UPGRADE_STARTED'] = str(int(started))"""),
("""        status(id=ident, state='running', version=r.get('version'), pid=os.getpid())
        rc, info, _ = put_in(os.path.join(UPGRADE_DIR, name), ident,
                             str(r.get('sha') or ''), r.get('by') or 'the pages', log_to,
                             downgrade=r.get('downgrade') is True)
        status(id=ident, state='done' if rc == 0 else 'failed', rc=rc,
               version=info['version'], tail=log_lines[-40:])
    except Refused as e:
        log_to('refused: %s' % e)
        status(id=ident, state='failed', rc=-1, said=str(e), tail=log_lines[-40:])
    except Exception as e:                       # noqa: BLE001 - said, never lost
        log_to('broke: %s' % e)
        status(id=ident, state='failed', rc=-2, said='the upgrade broke: %s' % e,
               tail=log_lines[-40:])""",
 """        status(id=ident, state='running', version=r.get('version'), pid=os.getpid())
        told.update(version=str(r.get('version') or ''), by=str(r.get('by') or 'the pages'),
                    frm=installed_version(), downgrade=r.get('downgrade') is True)
        pages_tell('running', ident, words='root checks the package', **told)
        rc, info, _ = put_in(os.path.join(UPGRADE_DIR, name), ident,
                             str(r.get('sha') or ''), r.get('by') or 'the pages', log_to,
                             downgrade=r.get('downgrade') is True, started=told['started'])
        status(id=ident, state='done' if rc == 0 else 'failed', rc=rc,
               version=info['version'], tail=log_lines[-40:])
        was = pages_said()
        mine = was.get('id') == ident
        if rc == 0 and not (mine and was.get('state') == 'done'):
            pages_tell('done', ident, part=was.get('part') or 1, parts=was.get('parts') or 0,
                       words='otp %s runs' % info['version'], **told)
        elif rc != 0 and not (mine and was.get('state') == 'failed'):
            pages_tell('failed', ident, part=was.get('part') or 1, parts=was.get('parts') or 0,
                       words=was.get('words') if mine else '',
                       said='install.sh --upgrade ended with %d' % rc, **told)
    except Refused as e:
        log_to('refused: %s' % e)
        status(id=ident, state='failed', rc=-1, said=str(e), tail=log_lines[-40:])
        if told.get('version'):
            pages_tell('failed', ident, words='root checks the package', said=str(e), **told)
    except Exception as e:                       # noqa: BLE001 - said, never lost
        log_to('broke: %s' % e)
        status(id=ident, state='failed', rc=-2, said='the upgrade broke: %s' % e,
               tail=log_lines[-40:])
        if told.get('version'):
            pages_tell('failed', ident, said='the upgrade broke: %s' % e, **told)"""),
("""    ident = ''
    log_path = os.path.join(UPGRADE_DIR, 'last.log')""",
 """    ident = ''
    told = {'started': time.time()}             # what the pages' file says of it (1.0.299)
    log_path = os.path.join(UPGRADE_DIR, 'last.log')"""),
])
print('ok')
