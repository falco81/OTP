# ---- a copy or a dump with the key that opens its tokens (1.0.123) -----------------
# A copy or a dump alone opens no token anywhere else: the key that opens them
# is a file of its own (the .key beside it, /var/lib/otp/secrets.key). Downloaded
# from the page it can now go with the key in ONE file - a plain tar holding
#   otp-db.json          what it is (the file's name, size, sha256, where made)
#   <the file>           the copy or the dump, as it is
#   secrets.key.locked   the key, locked with a passphrase given on the page
#                        (the lock of the cluster's bundle: scrypt, HMAC)
# and the same file sent back to Put a copy back / Put a dump back is opened
# with that passphrase and put back with its key. The passphrase is never
# kept: lost, the key in the file is lost with it.
DBKEY_KIND = 'otp-db-key'
DBKEY_TAR_KIND = 'otp-db-with-key'
DBKEY_SUFFIX = '.with-key.tar'
DB_UPLOADS = STATE_DIR / 'db-uploads'
DB_TICKETS_DIR = STATE_DIR / 'db-downloads'
DB_TICKETS = {}
DB_TICKETS_LOCK = threading.Lock()
DBKEY_MIN_PASS = 10


def _sha256_file(path):
    h = hashlib.sha256()
    with open(str(path), 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dbkey_passphrase_checked(passphrase):
    p = str(passphrase or '')
    if len(p) < DBKEY_MIN_PASS:
        raise ValueError('a passphrase of %d characters at least - it is all that guards the '
                         'key in the file' % DBKEY_MIN_PASS)
    return p


def dbkey_bundle(src, name, passphrase, work):
    """`src` (a copy or a dump called `name`) and this machine's key, locked
    with `passphrase`, in one tar in `work`. Its path."""
    passphrase = dbkey_passphrase_checked(passphrase)
    key = sealing_key()
    if not key:
        raise ValueError('this machine has no key that opens the tokens')
    sha = _sha256_file(src)
    locked = bundle_lock({'key': key.hex(), 'file': name, 'sha256': sha}, passphrase,
                         kind=DBKEY_KIND)
    head = {'kind': DBKEY_TAR_KIND, 'format': 1, 'file': name,
            'bytes': Path(src).stat().st_size, 'sha256': sha, 'made': time.time(),
            'node': node_name(), 'site': CONFIG.get('site_name') or '', 'version': __version__}
    out = Path(work) / (name + DBKEY_SUFFIX)
    with tarfile.open(str(out), 'w') as tf:
        for arc, data in (('otp-db.json', json.dumps(head, indent=1).encode('utf-8')),
                          ('secrets.key.locked', json.dumps(locked).encode('utf-8'))):
            ti = tarfile.TarInfo(arc)
            ti.size = len(data)
            ti.mtime = int(time.time())
            ti.mode = 0o600
            tf.addfile(ti, io.BytesIO(data))
        ti = tf.gettarinfo(str(src), arcname=name)
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ''
        ti.mode = 0o600
        with open(str(src), 'rb') as f:
            tf.addfile(ti, f)
    os.chmod(str(out), 0o600)
    return out


def dbkey_is_bundle(path):
    """Whether `path` is a file made by dbkey_bundle (its head, not its name)."""
    try:
        if not tarfile.is_tarfile(str(path)):
            return False
        with tarfile.open(str(path), 'r:') as tf:
            m = tf.getmember('otp-db.json')
            f = tf.extractfile(m)
            head = json.loads(f.read(1 << 16).decode('utf-8')) if f else {}
        return isinstance(head, dict) and head.get('kind') == DBKEY_TAR_KIND
    except (KeyError, OSError, ValueError, tarfile.TarError):
        return False


def dbkey_open(path, work, passphrase=None):
    """The file inside it, taken out into `work`, and - with the passphrase -
    the key next to it: (file, key file or None, head)."""
    try:
        tf = tarfile.open(str(path), 'r:')
    except (OSError, tarfile.TarError) as e:
        raise ValueError('that file does not open: %s' % e)
    with tf:
        members = {}
        for m in tf.getmembers():
            # Only plain files, by plain names: nothing it says goes anywhere
            # but where it is put.
            if not m.isreg() or '/' in m.name or m.name in ('', '.', '..') or '\\' in m.name:
                raise ValueError('that file holds something otp does not put in one: %s' % m.name)
            members[m.name] = m
        try:
            head = json.loads(tf.extractfile(members['otp-db.json']).read(1 << 16).decode('utf-8'))
            locked = json.loads(tf.extractfile(members['secrets.key.locked']).read(1 << 20)
                                .decode('utf-8'))
        except (KeyError, ValueError, AttributeError):
            raise ValueError('that is not a database with its key made by otp')
        name = os.path.basename(str(head.get('file') or ''))
        if head.get('kind') != DBKEY_TAR_KIND or not NAME_RE.match(name) or name not in members:
            raise ValueError('that is not a database with its key made by otp')
        out = Path(work) / name
        src = tf.extractfile(members[name])
        fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
    if _sha256_file(out) != head.get('sha256'):
        raise ValueError('the file inside is not the one it was made with (damaged on the way?)')
    keyf = None
    if passphrase is not None:
        try:
            got = bundle_open(locked, str(passphrase), kinds=(DBKEY_KIND,))
        except ValueError as e:
            if 'passphrase' in str(e):
                raise ValueError('that passphrase does not open the key in the file')
            raise
        if got.get('sha256') != head.get('sha256') or \
                not re.match(r'^[0-9a-f]{64}\Z', str(got.get('key') or '')):
            raise ValueError('the key in the file is not the one made with it')
        keyf = Path(work) / 'secrets.key'
        write_replacing(keyf, got['key'] + '\n', 0o600)
    return out, keyf, head


def dbkey_keep_upload(tmp):
    """An upload kept for an hour to be put back with its passphrase: its id."""
    DB_UPLOADS.mkdir(mode=0o700, exist_ok=True)
    now = time.time()
    for p in DB_UPLOADS.iterdir():
        try:
            if now - p.stat().st_mtime > 3600:
                p.unlink()
        except OSError:
            pass
    up = secrets.token_hex(8)
    shutil.move(str(tmp), str(DB_UPLOADS / up))
    os.chmod(str(DB_UPLOADS / up), 0o600)
    return up


def dbkey_upload(up):
    if not re.match(r'^[0-9a-f]{16}\Z', str(up or '')):
        raise ValueError('which file?')
    p = DB_UPLOADS / up
    if not p.is_file():
        raise ValueError('the file sent is not here any more (an hour has gone by?): send it again')
    return p


def dbkey_ticket_put(path, name, who):
    """A file made for a download, waiting ten minutes for the one browser
    that asked for it: its ticket."""
    now = time.time()
    with DB_TICKETS_LOCK:
        for t, v in list(DB_TICKETS.items()):
            if now - v['at'] > 600:
                shutil.rmtree(str(v['dir']), ignore_errors=True)
                DB_TICKETS.pop(t, None)
        t = secrets.token_hex(16)
        DB_TICKETS[t] = {'path': Path(path), 'name': name, 'who': who, 'at': now,
                         'dir': Path(path).parent}
    return t


def dbkey_ticket_take(t, who):
    with DB_TICKETS_LOCK:
        v = DB_TICKETS.pop(str(t or ''), None)
    if not v or v['who'] != who or time.time() - v['at'] > 600:
        if v:
            shutil.rmtree(str(v['dir']), ignore_errors=True)
        return None
    return v
