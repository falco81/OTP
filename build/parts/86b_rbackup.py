

import ftplib
import tarfile


# ---------------------------------------------------------------------------
# Backups to another machine (1.0.109)
# ---------------------------------------------------------------------------
# One file that brings any loss back - one server or a cluster, onto a
# machine installed from nothing: the whole database (an engine-independent
# copy: tokens, settings, accounts, certificates, the web address, the
# firewall, the texts, the logs), the key that opens the tokens, the machine's
# config.json and the files it names, a manifest with the checksum of each,
# and RESTORE.md - the exact steps. Locked with a password kept in the
# settings (openssl enc, AES-256-CBC, PBKDF2-SHA256: opened with otp, or with
# openssl alone on any machine). RESTORE.md and a .sha256 also go beside it,
# not locked, so the steps can be read before anything is opened.
#
# Where they go: a folder (an NFS or other mount), FTP, FTPS (explicit or
# implicit), SFTP, SCP or SMB, each with its name and password, SSH keys made
# here or brought, the server's host key or certificate checked, a client
# certificate for FTPS. Each node makes and sends its own (its config.json is
# its own); old ones are taken away as kept-count and age say.
RB_KINDS = ('folder', 'ftp', 'ftps', 'sftp', 'scp', 'smb')
RB_KIND_WORDS = {'folder': 'a folder', 'ftp': 'FTP', 'ftps': 'FTPS', 'sftp': 'SFTP',
                 'scp': 'SCP (ssh)', 'smb': 'SMB (Windows share, Samba)'}
RB_PORTS = {'ftp': 21, 'ftps': 21, 'sftp': 22, 'scp': 22, 'smb': 445}
RB_SEALED = ('password', 'key', 'client_key', 'key_pass')
RB_BIND = 'rbackup'
RB_LOCK = threading.Lock()
RB_JOB = {'running': False, 'what': '', 'says': '', 'done': 0, 'whole': 0, 'error': '',
          'began': 0, 'ended': 0, 'result': None, 'by': ''}
RB_ITER = 600000
RB_NAME_RE = re.compile(r'^otp-backup-(?P<site>[A-Za-z0-9_.-]+?)-(?P<node>[A-Za-z0-9_.-]+)-'
                        r'(?P<stamp>\d{8}-\d{6})\.tar\.gz(?P<enc>\.enc)?\Z')
RB_TIMEOUT = 60


class RbError(Exception):
    pass


def rb_clean(text, what, most=200, pattern=None, empty=True):
    t = str(text if text is not None else '').strip()
    if not t and empty:
        return ''
    if len(t) > most or re.search(r'[\x00-\x1f\x7f]', t):
        raise ValueError('%s: at most %d characters, one line' % (what, most))
    if pattern and t and not re.match(pattern, t):
        raise ValueError('%s: %r is not one' % (what, t[:60]))
    return t


def rb_slug(text):
    return re.sub(r'[^A-Za-z0-9_.]+', '_', str(text or 'otp')).strip('_.')[:40] or 'otp'


# ---- the destinations ---------------------------------------------------------------
def rb_targets(store):
    try:
        got = json.loads(store.get_meta('rbackup:targets') or '[]')
    except ValueError:
        got = []
    return [t for t in got if isinstance(t, dict) and t.get('id')]


def rb_put_targets(store, targets):
    store.set_meta('rbackup:targets', json.dumps(targets))


def rb_target(store, tid):
    return next((t for t in rb_targets(store) if t['id'] == str(tid)), None)


def rb_secret(t, k):
    v = t.get(k) or ''
    return (unseal_secret(v, bind=RB_BIND) or '') if v else ''


def ssh_fingerprints(lines):
    """The SHA256 fingerprints of known_hosts lines, as ssh-keygen says them."""
    if not lines.strip() or not shutil.which('ssh-keygen'):
        return []
    got = subprocess.run(['ssh-keygen', '-lf', '-'], input=lines, capture_output=True,
                         text=True, timeout=20)
    return [x.strip() for x in got.stdout.splitlines() if x.strip()]


def rb_view(t):
    """A destination as the pages see it: nothing secret, what it has said."""
    out = {k: v for k, v in t.items() if k not in RB_SEALED}
    for k in RB_SEALED:
        out['has_' + k] = bool(t.get(k))
    out['kind_words'] = RB_KIND_WORDS.get(t.get('kind'), t.get('kind'))
    if t.get('password'):
        out['password'] = secret_shown(rb_secret(t, 'password'), last=True)
    if t.get('hostkey'):
        out['hostkey_fp'] = ssh_fingerprints(t['hostkey'])
    if t.get('client_cert'):
        try:
            out['client_cert_info'] = cert_info(t['client_cert'])
        except Exception:                               # noqa: BLE001
            out['client_cert_info'] = None
    if t.get('ca'):
        try:
            out['ca_info'] = cert_info(t['ca'])
        except Exception:                               # noqa: BLE001
            out['ca_info'] = None
    return out


def rb_checked(data, old=None):
    """A destination as typed on the pages, checked; secrets left out or as
    dots keep what was there."""
    old = dict(old or {})
    if not isinstance(data, dict):
        raise ValueError('a destination is an object')
    kind = str(data.get('kind') or old.get('kind') or '')
    if kind not in RB_KINDS:
        raise ValueError('the kind is one of %s' % ', '.join(RB_KINDS))
    t = {'id': old.get('id') or secrets.token_hex(6), 'kind': kind}
    t['name'] = rb_clean(data.get('name'), 'the name', 60) or \
        ('%s %s' % (RB_KIND_WORDS[kind], data.get('host') or data.get('path') or '')).strip()
    t['enabled'] = 1 if data.get('enabled', old.get('enabled', 1)) else 0
    t['path'] = rb_clean(data.get('path'), 'the folder', 400)
    if kind == 'folder':
        if not t['path'].startswith('/'):
            raise ValueError('the folder is a whole path on this machine (/mnt/backup/otp)')
        if re.search(r'(^|/)\.\.(/|$)', t['path']):
            raise ValueError('the folder has no .. in it')
    else:
        t['host'] = rb_clean(data.get('host'), 'the server', 253,
                             r'^[A-Za-z0-9][A-Za-z0-9.:_-]*\Z', empty=False)
        try:
            port = int(data.get('port') or RB_PORTS.get(kind) or 0)
        except (TypeError, ValueError):
            raise ValueError('the port is a number')
        if kind == 'ftps' and data.get('implicit') and not data.get('port'):
            port = 990
        if not 1 <= port <= 65535:
            raise ValueError('the port is 1 to 65535')
        t['port'] = port
        t['user'] = rb_clean(data.get('user'), 'the account', 128, r'^[^\s:@/\\]+\Z') or ''
        # Nothing a tool on the way reads as more (1.0.136): smbclient takes
        # ; as the next command whatever the quotes, ssh a leading - as an
        # option of its own.
        if t['user'].startswith('-'):
            raise ValueError('the account does not begin with -')
        if re.search(r'[;"]', t['path']) or t['path'].lstrip().startswith('-'):
            raise ValueError('the folder has no ; or " in it, and does not begin with -')
        if kind != 'smb' and re.search(r'(^|/)\.\.(/|$)', t['path']):
            raise ValueError('the folder has no .. in it')
    pw = data.get('password')
    if pw is None or is_masked(pw):
        t['password'] = old.get('password') or ''
    else:
        pw = str(pw)
        if len(pw) > 512 or '\n' in pw or '\x00' in pw:
            raise ValueError('the password is one line, at most 512 characters')
        t['password'] = seal_secret(pw, bind=RB_BIND) if pw else ''
    if kind in ('sftp', 'scp'):
        for k in ('key', 'pub', 'ssh_cert', 'hostkey', 'key_pass'):
            if k in old:
                t[k] = old[k]
        if data.get('ssh_cert') is not None:
            c = str(data.get('ssh_cert') or '').strip()
            if c and not re.match(r'^[a-z0-9@.-]+-cert-v01@openssh\.com AAAA[A-Za-z0-9+/=]+( .*)?\Z',
                                  c):
                raise ValueError('the SSH certificate is the one line of a ...-cert.pub file')
            t['ssh_cert'] = c
    if kind in ('ftp', 'ftps'):
        t['passive'] = 0 if data.get('passive', old.get('passive', 1)) in (0, '0', False) else 1
    if kind == 'ftps':
        t['implicit'] = 1 if data.get('implicit', old.get('implicit')) else 0
        check = str(data.get('tls_check') or old.get('tls_check') or 'system')
        if check not in ('system', 'ca', 'pin', 'none'):
            raise ValueError('the server certificate is checked against system, ca, pin or none')
        t['tls_check'] = check
        for k in ('ca', 'pin', 'client_cert', 'client_key'):
            if k in old:
                t[k] = old[k]
        if data.get('ca') is not None:
            ca = str(data.get('ca') or '').strip()
            if ca and not PEM_CERT.search(ca):
                raise ValueError('the authority is a PEM certificate (-----BEGIN CERTIFICATE-----)')
            t['ca'] = '\n'.join(m.group(0) for m in PEM_CERT.finditer(ca)) + '\n' if ca else ''
        if data.get('pin') is not None:
            pin = re.sub(r'[^0-9A-Fa-f]', '', str(data.get('pin') or '')).lower()
            if pin and len(pin) != 64:
                raise ValueError('the pinned fingerprint is SHA-256: 64 hex digits')
            t['pin'] = pin
        if check == 'ca' and not t.get('ca'):
            raise ValueError('checked against an authority: give its certificate')
        if check == 'pin' and not t.get('pin'):
            raise ValueError('pinned: the fingerprint is needed - Try it shows the server\'s')
    if kind == 'smb':
        t['share'] = rb_clean(data.get('share'), 'the share', 80, r'^[^\\/:*?"<>|;-][^\\/:*?"<>|;]*\Z',
                              empty=False)
        t['domain'] = rb_clean(data.get('domain'), 'the domain', 64, r'^[A-Za-z0-9._-]+\Z')
        t['smb_encrypt'] = 1 if data.get('smb_encrypt', old.get('smb_encrypt', 1)) else 0
        if re.search(r'(^|[\\/])\.\.([\\/]|$)', t['path']):
            raise ValueError('the folder has no .. in it')
    for k in ('last', 'made'):
        if k in old:
            t[k] = old[k]
    return t


def rb_save(store, data, by):
    with RB_LOCK:
        targets = rb_targets(store)
        old = next((x for x in targets if x['id'] == str(data.get('id') or '')), None)
        if data.get('id') and not old:
            raise ValueError('no such destination')
        t = rb_checked(data, old)
        if old:
            targets = [t if x['id'] == t['id'] else x for x in targets]
        else:
            t['made'] = time.time()
            if len(targets) >= 20:
                raise ValueError('20 destinations at most')
            targets.append(t)
        rb_put_targets(store, targets)
    store.add_event('settings', '%s %s the backup destination %s (%s)' % (
        by, 'changed' if old else 'added', t['name'], RB_KIND_WORDS[t['kind']]), who=by)
    return t


def rb_set_fields(store, tid, by, said, **fields):
    with RB_LOCK:
        targets = rb_targets(store)
        t = next((x for x in targets if x['id'] == str(tid)), None)
        if not t:
            raise ValueError('no such destination')
        for k, v in fields.items():
            if v is None:
                t.pop(k, None)
            else:
                t[k] = v
        rb_put_targets(store, targets)
    if said:
        store.add_event('settings', '%s: the backup destination %s - %s' % (by, t['name'], said),
                        who=by)
    return t


def rb_delete(store, tid, by):
    with RB_LOCK:
        targets = rb_targets(store)
        t = next((x for x in targets if x['id'] == str(tid)), None)
        if not t:
            raise ValueError('no such destination')
        rb_put_targets(store, [x for x in targets if x['id'] != t['id']])
    store.add_event('settings', '%s took away the backup destination %s' % (by, t['name']),
                    'warn', who=by)


# ---- keys and certificates ----------------------------------------------------------
def ssh_keygen(comment):
    if not shutil.which('ssh-keygen'):
        raise ValueError('ssh-keygen is not on this machine (dnf install openssh-clients)')
    with tempfile.TemporaryDirectory(prefix='otp-key-') as d:
        path = os.path.join(d, 'k')
        got = subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', comment,
                              '-f', path], capture_output=True, text=True, timeout=30)
        if got.returncode != 0:
            raise ValueError('ssh-keygen: %s' % (got.stderr or got.stdout).strip()[:200])
        with open(path) as f:
            private = f.read()
        with open(path + '.pub') as f:
            public = f.read().strip()
    return private, public


def ssh_public_of(private, passphrase=''):
    """The public half of a private key given - and that it is one."""
    if not shutil.which('ssh-keygen'):
        raise ValueError('ssh-keygen is not on this machine (dnf install openssh-clients)')
    private = str(private or '').replace('\r\n', '\n').strip() + '\n'
    if 'PRIVATE KEY-----' not in private:
        raise ValueError('that is not a private key (-----BEGIN OPENSSH PRIVATE KEY----- or '
                         'another PEM private key)')
    with tempfile.TemporaryDirectory(prefix='otp-key-') as d:
        path = os.path.join(d, 'k')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(private)
        # The passphrase through SSH_ASKPASS, not on the command line where
        # `ps` shows it (1.0.136).
        env = dict(os.environ, DISPLAY=':0', SSH_ASKPASS_REQUIRE='force')
        if passphrase:
            ask = os.path.join(d, 'ask')
            with open(ask, 'w') as f:
                f.write('#!/bin/sh\nprintf "%s\\n" "$OTP_RB_SECRET"\n')
            os.chmod(ask, 0o700)
            env.update(SSH_ASKPASS=ask, OTP_RB_SECRET=passphrase)
            argv = ['ssh-keygen', '-y', '-f', path]
        else:
            argv = ['ssh-keygen', '-y', '-P', '', '-f', path]
        got = subprocess.run(argv, capture_output=True, text=True, timeout=20, env=env,
                             stdin=subprocess.DEVNULL)
    if got.returncode != 0:
        said = (got.stderr or got.stdout).strip()
        if 'passphrase' in said.lower() or 'incorrect' in said.lower():
            raise ValueError('the key is locked with a passphrase: give it too')
        raise ValueError('ssh-keygen does not read it: %s' % said[:200])
    return private, got.stdout.strip()


def rb_client_cert_make(cn, days=1825):
    """A key and a self-signed client certificate for FTPS."""
    key = new_key('ec')
    with tempfile.TemporaryDirectory(prefix='otp-crt-') as d:
        kf = os.path.join(d, 'k.pem')
        with open(kf, 'w') as f:
            f.write(key)
        os.chmod(kf, 0o600)
        cn = re.sub(r'[^A-Za-z0-9.@_-]', '', str(cn or 'otp-backup'))[:64] or 'otp-backup'
        crt = _openssl(['req', '-new', '-x509', '-key', kf, '-days', str(int(days)), '-subj',
                        '/CN=' + cn, '-addext', 'extendedKeyUsage=clientAuth',
                        '-addext', 'keyUsage=critical,digitalSignature'],
                       what='the certificate').decode()
    return key, crt


def rb_client_cert_given(text, password=''):
    """A client certificate brought: PEM (certificate and key, in any order)
    or PFX (base64 of it, with its password)."""
    text = str(text or '').strip()
    if 'BEGIN' in text:
        certs = [m.group(0) for m in PEM_CERT.finditer(text)]
        m = re.search(r'-----BEGIN (?:[A-Z ]*)PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z ]*)'
                      r'PRIVATE KEY-----', text)
        if not certs or not m:
            raise ValueError('a client certificate needs its certificate and its private key')
        key = m.group(0) + '\n'
        if 'ENCRYPTED' in key:
            key = _openssl(['pkey', '-passin', 'env:OTP_PW'], key.encode(),
                           env={'OTP_PW': password}, what='the key (its password)').decode()
        if _pub_of_key(key).strip() != _pub_of_cert(certs[0]).strip():
            raise ValueError('the key is not the one of this certificate')
        return key, '\n'.join(certs) + '\n'
    try:
        pfx = base64.b64decode(text, validate=False)
    except (binascii.Error, ValueError):
        raise ValueError('neither PEM nor PFX')
    with tempfile.TemporaryDirectory(prefix='otp-pfx-') as d:
        pf = os.path.join(d, 'c.pfx')
        with open(pf, 'wb') as f:
            f.write(pfx)
        both = ''
        for extra in ([], ['-legacy']):
            try:
                both = _openssl(['pkcs12', '-in', pf, '-nodes', '-passin', 'env:OTP_PW'] + extra,
                                env={'OTP_PW': password}, what='the PFX (its password?)').decode()
                break
            except ValueError:
                if extra:
                    raise
    return rb_client_cert_given(both)


# ---- the transports ------------------------------------------------------------------
class RbFolder(object):
    def __init__(self, t):
        self.t = t
        self.dir = t['path']

    def open(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
        except OSError as e:
            raise RbError('the folder %s cannot be made: %s' % (self.dir, e))
        if not os.access(self.dir, os.W_OK):
            raise RbError('the otp account may not write into %s' % self.dir)

    def put(self, local, name):
        part = os.path.join(self.dir, '.%s.part' % name)
        shutil.copyfile(local, part)
        os.chmod(part, 0o640)
        os.replace(part, os.path.join(self.dir, name))

    def get(self, name, local):
        shutil.copyfile(os.path.join(self.dir, rb_safe_name(name)), local)

    def list(self):
        out = []
        for e in os.scandir(self.dir):
            if e.is_file() and not e.name.startswith('.'):
                st = e.stat()
                out.append({'name': e.name, 'size': st.st_size, 'mtime': st.st_mtime})
        return out

    def delete(self, name):
        os.unlink(os.path.join(self.dir, rb_safe_name(name)))

    def close(self):
        pass


def rb_safe_name(name):
    name = str(name or '')
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,200}\Z', name):
        raise RbError('not a file name of a backup: %r' % name[:80])
    return name


class _ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTPS on its own port (990): TLS from the first byte."""
    def connect(self, host='', port=0, timeout=-999, source_address=None):
        if host:
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.af = self.sock.family
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile('r', encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome


class _ReuseMixin(object):
    """The data connection resumes the control connection's TLS session:
    vsftpd, ProFTPD and FileZilla Server refuse one that does not (522)."""
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host,
                                            session=self.sock.session)
        return conn, size


class RbFtpTls(_ReuseMixin, ftplib.FTP_TLS):
    pass


class RbFtpTlsImplicit(_ReuseMixin, _ImplicitFTP_TLS):
    pass


class RbFtp(object):
    def __init__(self, t):
        self.t = t
        self.ftp = None
        self.tmp = None
        self.seen = {}

    def _context(self):
        t = self.t
        check = t.get('tls_check') or 'system'
        if check == 'ca':
            ctx = ssl.create_default_context(cadata=t.get('ca') or '')
        elif check == 'system':
            ctx = ssl.create_default_context()
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if t.get('client_cert') and t.get('client_key'):
            self.tmp = tempfile.mkdtemp(prefix='otp-ftps-')
            cf, kf = os.path.join(self.tmp, 'c.pem'), os.path.join(self.tmp, 'k.pem')
            with open(cf, 'w') as f:
                f.write(t['client_cert'])
            fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(rb_secret(t, 'client_key'))
            ctx.load_cert_chain(cf, kf)
        return ctx

    def open(self):
        t = self.t
        try:
            if t['kind'] == 'ftps':
                cls = RbFtpTlsImplicit if t.get('implicit') else RbFtpTls
                self.ftp = cls(context=self._context(), timeout=RB_TIMEOUT)
                self.ftp.connect(t['host'], int(t['port']))
                if not t.get('implicit'):
                    self.ftp.auth()
                der = self.ftp.sock.getpeercert(True)
                fp = hashlib.sha256(der).hexdigest() if der else ''
                self.seen = {'fingerprint': fp}
                try:
                    pem = ssl.DER_cert_to_PEM_cert(der)
                    self.seen['cert'] = cert_info(pem)
                except Exception:                       # noqa: BLE001
                    pass
                if (t.get('tls_check') == 'pin') and fp != (t.get('pin') or ''):
                    raise RbError('the server answers with another certificate than the one '
                                  'pinned (SHA-256 %s)' % fp)
            else:
                self.ftp = ftplib.FTP(timeout=RB_TIMEOUT)
                self.ftp.connect(t['host'], int(t['port']))
            self.ftp.login(t.get('user') or 'anonymous', rb_secret(t, 'password'))
            if t['kind'] == 'ftps':
                self.ftp.prot_p()
            self.ftp.set_pasv(bool(t.get('passive', 1)))
            self._cd(t.get('path') or '')
        except ssl.SSLCertVerificationError as e:
            raise RbError('the server\'s certificate is not trusted: %s - check it against '
                          'its authority, or pin it' % e.verify_message)
        except ftplib.error_perm as e:
            raise RbError('the FTP server said: %s' % str(e)[:200])
        except (OSError, EOFError, ftplib.Error) as e:
            raise RbError(str(e)[:200] or e.__class__.__name__)

    def _cd(self, path):
        if not path:
            return
        if path.startswith('/'):
            self.ftp.cwd('/')
        for part in [p for p in path.split('/') if p]:
            try:
                self.ftp.cwd(part)
            except ftplib.error_perm:
                self.ftp.mkd(part)
                self.ftp.cwd(part)

    def put(self, local, name):
        with open(local, 'rb') as f:
            self.ftp.storbinary('STOR .%s.part' % name, f, blocksize=262144)
        try:
            self.ftp.delete(name)
        except ftplib.error_perm:
            pass
        self.ftp.rename('.%s.part' % name, name)

    def get(self, name, local):
        with open(local, 'wb') as f:
            self.ftp.retrbinary('RETR %s' % rb_safe_name(name), f.write, blocksize=262144)

    def list(self):
        out = []
        try:
            for name, facts in self.ftp.mlsd(facts=['type', 'size', 'modify']):
                if facts.get('type') == 'file':
                    m = facts.get('modify') or ''
                    try:
                        mt = datetime.strptime(m[:14], '%Y%m%d%H%M%S').replace(
                            tzinfo=timezone.utc).timestamp()
                    except ValueError:
                        mt = 0
                    out.append({'name': name, 'size': int(facts.get('size') or 0), 'mtime': mt})
            return out
        except ftplib.error_perm:
            pass
        for name in self.ftp.nlst():
            name = name.rsplit('/', 1)[-1]
            if name in ('.', '..'):
                continue
            try:
                size = self.ftp.size(name) or 0
            except ftplib.error_perm:
                continue            # a folder
            out.append({'name': name, 'size': size, 'mtime': 0})
        return out

    def delete(self, name):
        self.ftp.delete(rb_safe_name(name))

    def close(self):
        try:
            if self.ftp:
                self.ftp.quit()
        except Exception:                               # noqa: BLE001
            try:
                self.ftp.close()
            except Exception:                           # noqa: BLE001
                pass
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)


def ssh_keyscan(host, port):
    """The server's host keys, as known_hosts lines - and their fingerprints."""
    if not shutil.which('ssh-keyscan'):
        raise ValueError('ssh-keyscan is not on this machine (dnf install openssh-clients)')
    got = subprocess.run(['ssh-keyscan', '-T', '10', '-p', str(int(port)), host],
                         capture_output=True, text=True, timeout=30)
    lines = [x for x in got.stdout.splitlines() if x.strip() and not x.startswith('#')]
    if not lines:
        raise ValueError('%s:%s did not show a host key: %s' % (
            host, port, (got.stderr or '').strip().splitlines()[-1:] or 'no answer'))
    return '\n'.join(lines) + '\n', ssh_fingerprints('\n'.join(lines) + '\n')


class RbSsh(object):
    """SFTP (the sftp program) or SCP (scp, and ssh for the list and the
    deleting) - OpenSSH itself, the server's host key checked against the one
    trusted on the pages, a key of its own or a password."""
    def __init__(self, t):
        self.t = t
        self.d = None

    def open(self):
        t = self.t
        tools = ['ssh'] + (['sftp'] if t['kind'] == 'sftp' else ['scp'])
        for tool in tools:
            if not shutil.which(tool):
                raise RbError('%s is not on this machine (dnf install openssh-clients)' % tool)
        if not t.get('hostkey'):
            raise RbError('the server\'s host key is not trusted yet: Try it, then trust the '
                          'fingerprint it shows')
        self.d = tempfile.mkdtemp(prefix='otp-ssh-')
        kh = os.path.join(self.d, 'known_hosts')
        with open(kh, 'w') as f:
            f.write(t['hostkey'])
        self.opts = ['-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + kh,
                     '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=20',
                     '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=4',
                     '-o', 'LogLevel=ERROR', '-o', 'IdentitiesOnly=yes', '-F', '/dev/null']
        key = rb_secret(t, 'key')
        if key:
            kf = os.path.join(self.d, 'id')
            fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(key if key.endswith('\n') else key + '\n')
            self.opts += ['-i', kf]
            if t.get('ssh_cert'):
                cf = os.path.join(self.d, 'id-cert.pub')
                with open(cf, 'w') as f:
                    f.write(t['ssh_cert'] + '\n')
                self.opts += ['-o', 'CertificateFile=' + cf]
        else:
            self.opts += ['-o', 'IdentityFile=/dev/null']
        # A password (or the key's passphrase) through SSH_ASKPASS: never on
        # a command line, never in a file of the otp account's.
        self.env = dict(os.environ, DISPLAY=':0', SSH_ASKPASS_REQUIRE='force')
        secret = rb_secret(t, 'password') or rb_secret(t, 'key_pass')
        ask = os.path.join(self.d, 'ask')
        with open(ask, 'w') as f:
            f.write('#!/bin/sh\nprintf "%s\\n" "$OTP_RB_SECRET"\n')
        os.chmod(ask, 0o700)
        self.env.update(SSH_ASKPASS=ask, OTP_RB_SECRET=secret)
        auths = ['publickey'] if key else []
        if rb_secret(t, 'password'):
            auths += ['password', 'keyboard-interactive']
        if not auths:
            raise RbError('neither a key nor a password is set')
        self.opts += ['-o', 'PreferredAuthentications=' + ','.join(auths),
                      '-o', 'NumberOfPasswordPrompts=1']
        if rb_secret(t, 'password') or rb_secret(t, 'key_pass'):
            # sftp -b asks ssh for batch mode, which takes no password; the
            # first value given wins, and this comes first.
            self.opts += ['-o', 'BatchMode=no']
        self.dest = '%s@%s' % (t.get('user') or 'root', t['host'])
        self.dir = (t.get('path') or '').rstrip('/') or '.'
        # Signed in and the folder made, at once - the errors said here.
        if t['kind'] == 'sftp':
            parts = [p for p in self.dir.split('/') if p and p != '.']
            cmds = []
            acc = '/' if self.dir.startswith('/') else ''
            for p in parts:
                acc = (acc + '/' + p) if acc not in ('', '/') else (acc + p)
                cmds.append('-mkdir "%s"' % acc)
            cmds.append('cd "%s"' % self.dir)
            self._sftp(cmds)
        else:
            self._ssh('mkdir -p -- %s && test -w %s' % (shlex_quote(self.dir),
                                                        shlex_quote(self.dir)))

    def _run(self, args, what, stdin=None, timeout=3600):
        got = subprocess.run(args, input=stdin, capture_output=True, text=True,
                             timeout=timeout, env=self.env, start_new_session=True)
        if got.returncode != 0:
            said = (got.stderr or got.stdout or '').strip().splitlines()
            said = [x for x in said if x.strip() and not x.startswith('Warning: Permanently')]
            tail = ' / '.join(said[-3:])[:300] or 'it said nothing (exit %d)' % got.returncode
            if 'Host key verification failed' in tail or 'REMOTE HOST IDENTIFICATION' in tail:
                tail = ('the server shows another host key than the one trusted - if it was '
                        'reinstalled on purpose, Try it and trust the new one')
            elif 'Permission denied' in tail:
                tail = 'the server did not let the account in (%s)' % tail
            raise RbError('%s: %s' % (what, tail))
        return got.stdout

    def _ssh(self, command):
        return self._run(['ssh'] + self.opts + ['-p', str(int(self.t['port'])), self.dest,
                                                command], 'ssh')

    def _sftp(self, cmds, timeout=3600):
        batch = os.path.join(self.d, 'batch')
        with open(batch, 'w') as f:
            f.write('\n'.join(cmds) + '\n')
        return self._run(['sftp'] + self.opts + ['-P', str(int(self.t['port'])), '-b', batch,
                                                 self.dest], 'sftp', timeout=timeout)

    def put(self, local, name):
        name = rb_safe_name(name)
        if self.t['kind'] == 'sftp':
            self._sftp(['cd "%s"' % self.dir, 'put "%s" ".%s.part"' % (local, name),
                        '-rm "%s"' % name, 'rename ".%s.part" "%s"' % (name, name)])
        else:
            self._run(['scp'] + self.opts + ['-P', str(int(self.t['port'])), '-q', local,
                                             '%s:%s/.%s.part' % (self.dest, self.dir, name)],
                      'scp')
            self._ssh('mv -f -- %s %s' % (shlex_quote('%s/.%s.part' % (self.dir, name)),
                                          shlex_quote('%s/%s' % (self.dir, name))))

    def get(self, name, local):
        name = rb_safe_name(name)
        if self.t['kind'] == 'sftp':
            self._sftp(['cd "%s"' % self.dir, 'get "%s" "%s"' % (name, local)])
        else:
            self._run(['scp'] + self.opts + ['-P', str(int(self.t['port'])), '-q',
                                             '%s:%s/%s' % (self.dest, self.dir, name), local],
                      'scp')

    def list(self):
        if self.t['kind'] == 'sftp':
            text = self._sftp(['cd "%s"' % self.dir, 'ls -ln'])
        else:
            text = self._ssh('LC_ALL=C ls -ln -- %s' % shlex_quote(self.dir))
        out = []
        for line in text.splitlines():
            f = line.split(None, 8)
            if len(f) == 9 and f[0].startswith('-'):
                name = f[8].rsplit('/', 1)[-1]
                try:
                    out.append({'name': name, 'size': int(f[4]), 'mtime': 0})
                except ValueError:
                    pass
        return out

    def delete(self, name):
        name = rb_safe_name(name)
        if self.t['kind'] == 'sftp':
            self._sftp(['cd "%s"' % self.dir, 'rm "%s"' % name])
        else:
            self._ssh('rm -f -- %s' % shlex_quote('%s/%s' % (self.dir, name)))

    def close(self):
        if self.d:
            shutil.rmtree(self.d, ignore_errors=True)


class RbSmb(object):
    """SMB through smbclient: an authentication file of its own (never the
    password on a command line), SMB2 at least, SMB3 encryption when asked."""
    def __init__(self, t):
        self.t = t
        self.d = None

    def open(self):
        t = self.t
        if not shutil.which('smbclient'):
            raise RbError('smbclient is not on this machine (dnf install samba-client)')
        self.d = tempfile.mkdtemp(prefix='otp-smb-')
        auth = os.path.join(self.d, 'auth')
        fd = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write('username = %s\npassword = %s\n' % (t.get('user') or 'guest',
                                                       rb_secret(t, 'password')))
            if t.get('domain'):
                f.write('domain = %s\n' % t['domain'])
        self.args = ['smbclient', '//%s/%s' % (t['host'], t['share']), '-A', auth,
                     '-p', str(int(t['port'])), '--option=client min protocol=SMB2',
                     '-t', str(RB_TIMEOUT)]
        if t.get('smb_encrypt'):
            self.args += ['--client-protection=encrypt']
        self.dir = (t.get('path') or '').replace('/', '\\').strip('\\')
        cmds = []
        acc = ''
        for p in [x for x in self.dir.split('\\') if x]:
            acc = (acc + '\\' + p) if acc else p
            cmds.append('mkdir "%s"' % acc)
        self._run(cmds + ['cd "\\%s"' % self.dir, 'ls'], ignore=('NT_STATUS_OBJECT_NAME_COLLISION',))

    def _run(self, cmds, ignore=(), timeout=3600):
        got = subprocess.run(self.args + ['-c', '; '.join(cmds)], capture_output=True, text=True,
                             timeout=timeout, cwd=self.d, start_new_session=True)
        text = (got.stdout or '') + (got.stderr or '')
        bad = [x for x in text.splitlines() if 'NT_STATUS_' in x and
               not any(i in x for i in ignore)]
        if got.returncode != 0 or bad:
            said = ' / '.join((bad or text.strip().splitlines() or ['no answer'])[-2:])[:300]
            if 'NT_STATUS_LOGON_FAILURE' in said:
                said = 'the server did not take the account and password (%s)' % said
            elif 'NT_STATUS_BAD_NETWORK_NAME' in said:
                said = 'there is no share %s on %s' % (self.t['share'], self.t['host'])
            elif 'protection' in said.lower() and 'unknown' in said.lower():
                said = ('this smbclient does not know --client-protection: switch "SMB3 '
                        'encryption required" off or install a newer samba-client')
            raise RbError('smbclient: %s' % said)
        return got.stdout or ''

    def _cd(self):
        return 'cd "\\%s"' % self.dir

    def put(self, local, name):
        name = rb_safe_name(name)
        self._run([self._cd(), 'put "%s" ".%s.part"' % (local, name), 'del "%s"' % name,
                   'rename ".%s.part" "%s"' % (name, name)], ignore=('NT_STATUS_NO_SUCH_FILE',
                                                                   'NT_STATUS_OBJECT_NAME_NOT_FOUND'))

    def get(self, name, local):
        self._run([self._cd(), 'get "%s" "%s"' % (rb_safe_name(name), local)])

    def list(self):
        out = []
        for line in self._run([self._cd(), 'ls']).splitlines():
            m = re.match(r'^\s\s(.+?)\s+([ADHNRS]*)\s+(\d+)\s+(\w{3} \w{3}\s+\d+ [\d:]+ \d{4})\s*$',
                         line)
            if m and 'D' not in m.group(2) and m.group(1) not in ('.', '..'):
                try:
                    mt = datetime.strptime(re.sub(r'\s+', ' ', m.group(4)),
                                           '%a %b %d %H:%M:%S %Y').timestamp()
                except ValueError:
                    mt = 0
                out.append({'name': m.group(1), 'size': int(m.group(3)), 'mtime': mt})
        return out

    def delete(self, name):
        self._run([self._cd(), 'del "%s"' % rb_safe_name(name)])

    def close(self):
        if self.d:
            shutil.rmtree(self.d, ignore_errors=True)


def rb_said(e):
    """An error in words, whatever library raised it."""
    if isinstance(e, EOFError):
        return 'the server closed the connection'
    if isinstance(e, socket.timeout):
        return 'the server did not answer in time'
    if isinstance(e, ssl.SSLCertVerificationError):
        return ('the server\'s certificate is not trusted: %s - check it against its authority, '
                'or pin it' % e.verify_message)
    if isinstance(e, ftplib.Error):
        return 'the FTP server said: %s' % str(e)[:300]
    return scrub_secret(str(e) or e.__class__.__name__)[:400]


def rb_transport(t):
    return {'folder': RbFolder, 'ftp': RbFtp, 'ftps': RbFtp, 'sftp': RbSsh, 'scp': RbSsh,
            'smb': RbSmb}[t['kind']](t)


def rb_try(t):
    """Signed in, a small file written, seen in the list, taken away again."""
    out = {'ok': False, 'steps': []}
    began = time.time()
    tr = rb_transport(t)
    try:
        tr.open()
        out['steps'].append('signed in, the folder is there')
        if getattr(tr, 'seen', None):
            out['server_cert'] = tr.seen
        name = 'otp-try-%s-%s.txt' % (rb_slug(node_name()), secrets.token_hex(4))
        with tempfile.NamedTemporaryFile('w', prefix='otp-try-', delete=False) as f:
            f.write('otp %s on %s tried this destination at %s - this file is taken away again\n'
                    % (__version__, node_name(), datetime.now().isoformat(timespec='seconds')))
            local = f.name
        try:
            tr.put(local, name)
        finally:
            os.unlink(local)
        out['steps'].append('a file written')
        names = [x['name'] for x in tr.list()]
        if name not in names:
            raise RbError('the file written is not in the list the server gives')
        out['steps'].append('it is in the list (%d file(s) there)' % len(names))
        tr.delete(name)
        out['steps'].append('taken away again')
        out['ok'] = True
    except Exception as e:                              # noqa: BLE001
        out['error'] = rb_said(e)
        if getattr(tr, 'seen', None):
            out['server_cert'] = tr.seen
    finally:
        tr.close()
    out['secs'] = round(time.time() - began, 1)
    return out


# ---- the backup itself -----------------------------------------------------------------
def rb_password():
    return str(CONFIG.get('rbackup_password') or '')


def rb_files_named():
    """Files config.json names that live outside the database: the
    authority of a database on another machine."""
    out = []
    for k in ('db_tls_ca',):
        p = str(CONFIG.get(k) or '')
        if p and os.path.isfile(p):
            out.append(p)
    return out


def rb_restore_md(m):
    """RESTORE.md: the exact steps, filled in with what this backup is."""
    enc = m.get('encrypted')
    name = m['file']
    tar = name[:-4] if enc else name
    ha = m.get('ha_mode') == 'replicated'
    site, node, ver = m.get('site') or 'otp', m.get('node') or '?', m.get('otp') or '?'
    lines = [
        '# Restoring otp from %s' % name, '',
        '| | |', '|---|---|',
        '| Made | %s |' % m.get('made_words'),
        '| Installation | %s |' % site,
        '| Node | %s (%s) |' % (node, m.get('host') or ''),
        '| otp | %s |' % ver,
        '| Database | %s |' % m.get('engine_words'),
        '| Cluster | %s |' % (('two nodes, replicated - this is node %s of 2; the other was %s'
                               % (m.get('ha_slot'), m.get('ha_peer'))) if ha else
                              ('two nodes, one shared database' if m.get('ha_mode') == 'shared'
                               else 'one server')),
        '| Locked | %s |' % ('yes - AES-256-CBC, PBKDF2-SHA256, %d rounds (openssl enc)'
                             % RB_ITER if enc else '**no** - anybody with the file has every '
                             'token: keep it as you would the server'),
        '| Tokens | %s |' % m.get('tokens', '?'),
        '', 'Everything is in it: the whole database (tokens and their recovery codes, the RADIUS',
        'clients, realms, directories, accounts, every setting, the certificates and keys of the',
        'pages, the web address, the firewall, the message texts, the logs), the key that opens',
        'the tokens (`secrets.key`) and this machine\'s `/etc/otp/config.json`.', '',
        'Keep the password of the backups apart from the backups (a password vault): without it',
        'the file cannot be opened - by anybody.', '',
        '## 0. Check the file', '', '```bash',
        'sha256sum -c %s.sha256          # "%s: OK"' % (name, name), '```', '',
    ]
    if enc:
        lines += ['## 1. Open it', '',
                  'otp opens it by itself (step 3). With openssl alone, on any machine:', '',
                  '```bash',
                  'openssl enc -d -aes-256-cbc -pbkdf2 -iter %d -md sha256 -in %s -out %s'
                  % (RB_ITER, name, tar),
                  '# it asks for the password of the backups',
                  'tar tzf %s                    # what is inside' % tar, '```', '']
    else:
        lines += ['## 1. It is not locked', '', '```bash',
                  'tar tzf %s' % tar, '```', '']
    lines += [
        'Inside: `otp-copy.json.gz` (the database, in a shape SQLite, MariaDB and PostgreSQL',
        'all take), `secrets.key`, `config.json`, `manifest.json` (a checksum of each file),',
        'this file, and the files config.json names (`files/`).', '',
        '## 2. A machine to put it on', '',
        'AlmaLinux / Rocky / RHEL 9 (or the machine it came from). Install otp **%s or newer**' % ver,
        'from its package - the same way as the first time:', '', '```bash',
        'tar xzf otp-%s.tar.gz && cd otp-%s' % (ver, ver),
        './install.sh                     # SQLite unless you choose otherwise',
        '```', '',
        'The backup goes into whichever database the new machine uses - SQLite after a plain',
        'install is fine. PostgreSQL (needed again for a cluster) can be chosen afterwards:',
        '`./install.sh --with-db postgres --yes`, then *Settings → The database → Try it → Set it',
        'up → Carry everything across → Start using it* (PostgreSQL 16 or later).', '',
        '## 3. Put it back', '', '```bash',
        'otp --restore-bundle %s          # shows what is in it, asks for the password' % name,
        'otp --restore-bundle %s --yes    # puts it back' % name,
        'systemctl restart otp', '```', '',
        'The password may come from a file instead (`--passphrase-file FILE`, one line) or from',
        'the environment (`OTP_BACKUP_PASSWORD`).', '',
        'What it does: a copy of what the new machine has is made first; then the database is',
        'replaced with the one in the backup, `secrets.key` is put in place and the node keeps',
        'its name (`%s`). The new machine\'s own database connection in config.json stays as' % node,
        'it is - it belongs to the new machine. The other files config.json named are in `files/`.',
        '',
    ]
    if ha:
        lines += [
            '## 4. A cluster of two', '',
            '- **One node lost, the other alive:** do not put this back. Install the lost node',
            '  again and join it to the living one - it copies every row from it:',
            '  `otp --ha-bundle FILE` on the living node, `otp --ha-join FILE` on the new one',
            '  (docs/high-availability.md, "When a node is lost").',
            '- **Both lost:** put this backup back on one new machine (steps 2-3). It comes back as',
            '  one server with everything. Move it to PostgreSQL (step 2), then make it two again:',
            '  `otp --ha-setup --ha-peer ADDRESS-OF-THE-SECOND --node-name %s` on it; on the' % node,
            '  second `./install.sh --with-db postgres --yes` and `otp --ha-join FILE`',
            '  (docs/high-availability.md, "Building it - replicated"). The web address, the',
            '  firewall, the certificates of the pages and the encrypted link between the',
            '  databases come back by themselves from the database.',
            '- Each node sends its own backups; either node\'s newest is the whole cluster\'s data.',
            '',
        ]
    lines += [
        '## %d. Check it' % (5 if ha else 4), '', '```bash',
        'otp --status                     # tokens, clients, realms, the database',
        'otp --radtest NAME CODE          # one sign-in', '```', '',
        'Then sign in to the pages with an account from the backup. RADIUS clients, DNS and a',
        'load balancer point at the new machine\'s address if it has another one',
        '(docs/renaming-and-readdressing.md).', '',
        '## By hand, without --restore-bundle', '', '```bash',
        'systemctl stop otp',
        'install -o otp -g otp -m 0600 secrets.key /var/lib/otp/secrets.key',
        'otp --restore otp-copy.json.gz --yes',
        'systemctl start otp', '```', '',
        '---', 'Made by otp %s on %s. The whole subject: docs/backup-and-recovery.md and' % (
            __version__, node),
        'docs/remote-backups.md in the package.', '']
    return '\n'.join(lines)


def rb_manifest(store, base, tokens='?'):
    """What a backup made now is: the head of its manifest and of RESTORE.md."""
    pw = rb_password()
    m = {'otp': __version__, 'made': time.time(),
         'made_words': datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z').strip(),
         'site': CONFIG.get('site_name') or 'otp', 'node': node_name(),
         'host': socket.getfqdn(), 'engine': store.db.engine,
         'engine_words': ENGINE_WORDS.get(store.db.engine, store.db.engine),
         'ha_mode': CONFIG.get('ha_mode') or '', 'ha_slot': CONFIG.get('ha_slot'),
         'ha_peer': CONFIG.get('ha_peer') or '', 'tokens': tokens,
         'encrypted': bool(pw), 'iter': RB_ITER if pw else 0,
         'file': base + ('.tar.gz.enc' if pw else '.tar.gz'), 'files': {}}
    return m


def rb_restore_guide(store):
    """RESTORE.md as a backup made now would carry it (1.0.110) - for reading
    on the pages before anything is lost. No secret is in it."""
    site = rb_slug(CONFIG.get('site_name') or 'otp')
    node = rb_slug(node_name())
    try:
        tokens = int(store.db.value('SELECT COUNT(*) FROM tokens') or 0)
    except Exception:                                   # noqa: BLE001
        tokens = '?'
    base = 'otp-backup-%s-%s-%s' % (site, node, datetime.now().strftime('%Y%m%d-%H%M%S'))
    m = rb_manifest(store, base, tokens)
    return {'md': rb_restore_md(m), 'name': 'RESTORE-%s-%s.md' % (site, node),
            'file': m['file']}


def rb_build(store, work, progress=None):
    """The backup, built in `work`: (path of the file to send, its name,
    manifest, RESTORE.md text)."""
    def say(n, t):
        if progress:
            progress(n, 6, t)
    stamp_ = datetime.now().strftime('%Y%m%d-%H%M%S')
    site = rb_slug(CONFIG.get('site_name') or 'otp')
    node = rb_slug(node_name())
    base = 'otp-backup-%s-%s-%s' % (site, node, stamp_)
    inner = os.path.join(work, 'in')
    os.makedirs(inner, mode=0o700)
    say(1, 'the database is copied')
    copy = os.path.join(inner, 'otp-copy.json.gz')
    with open(copy, 'wb') as f:
        dump_tables(store.db, f)
    key = sealing_key()
    if not key:
        raise RbError('this machine has no key that opens the tokens - nothing worth sending')
    with open(os.path.join(inner, 'secrets.key'), 'w') as f:
        f.write(key.hex() + '\n')
    try:
        shutil.copyfile(str(CONFIG_FILE), os.path.join(inner, 'config.json'))
    except OSError as e:
        raise RbError('%s cannot be read: %s' % (CONFIG_FILE, e))
    extra = rb_files_named()
    if extra:
        os.makedirs(os.path.join(inner, 'files'))
        for p in extra:
            shutil.copyfile(p, os.path.join(inner, 'files', os.path.basename(p)))
    say(2, 'what is in it is counted')
    try:
        tokens = int(store.db.value('SELECT COUNT(*) FROM tokens') or 0)
    except Exception:                                   # noqa: BLE001
        tokens = '?'
    pw = rb_password()
    m = rb_manifest(store, base, tokens)
    for root, _dirs, files in os.walk(inner):
        for n in sorted(files):
            p = os.path.join(root, n)
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
            m['files'][os.path.relpath(p, inner)] = {'sha256': h.hexdigest(),
                                                    'bytes': os.path.getsize(p)}
    md = rb_restore_md(m)
    with open(os.path.join(inner, 'RESTORE.md'), 'w') as f:
        f.write(md)
    with open(os.path.join(inner, 'manifest.json'), 'w') as f:
        json.dump(m, f, indent=2, default=str)
    say(3, 'packed')
    tar = os.path.join(work, base + '.tar.gz')
    with tarfile.open(tar, 'w:gz', compresslevel=6) as tf:
        for n in sorted(os.listdir(inner)):
            tf.add(os.path.join(inner, n), arcname='%s/%s' % (base, n))
    shutil.rmtree(inner, ignore_errors=True)
    out = tar
    if pw:
        say(4, 'locked with the password of the backups')
        out = tar + '.enc'
        _openssl(['enc', '-aes-256-cbc', '-pbkdf2', '-iter', str(RB_ITER), '-md', 'sha256',
                  '-salt', '-in', tar, '-out', out, '-pass', 'env:OTP_RB_PASS'],
                 env={'OTP_RB_PASS': pw}, what='locking it')
        os.unlink(tar)
    h = hashlib.sha256()
    with open(out, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    m['sha256'] = h.hexdigest()
    m['bytes'] = os.path.getsize(out)
    with open(os.path.join(work, m['file'] + '.sha256'), 'w') as f:
        f.write('%s  %s\n' % (m['sha256'], m['file']))
    with open(os.path.join(work, base + '-RESTORE.md'), 'w') as f:
        f.write(md)
    return out, m, md


def rb_companions(name):
    m = RB_NAME_RE.match(name)
    if not m:
        return []
    base = name.split('.tar.gz')[0]
    return [name + '.sha256', base + '-RESTORE.md']


def rb_retain(tr, keep, days, now=None):
    """This node's backups at a destination beyond what is kept, taken away -
    never the newest."""
    now = now or time.time()
    mine = rb_slug(node_name())
    files = tr.list()
    names = set(x['name'] for x in files)
    ours = []
    for x in files:
        m = RB_NAME_RE.match(x['name'])
        if m and m.group('node') == mine and m.group('site') == rb_slug(
                CONFIG.get('site_name') or 'otp'):
            try:
                when = datetime.strptime(m.group('stamp'), '%Y%m%d-%H%M%S').timestamp()
            except ValueError:
                continue
            ours.append((when, x['name']))
    ours.sort(reverse=True)
    gone = []
    for i, (when, name) in enumerate(ours):
        if i == 0:
            continue
        if (keep and i >= keep) or (days and now - when > days * 86400):
            for n in [name] + [c for c in rb_companions(name) if c in names]:
                try:
                    tr.delete(n)
                except Exception:                       # noqa: BLE001
                    pass
            gone.append(name)
    return gone


def rb_run(store, by, only=None, progress=None):
    """Made once, sent to every destination switched on (or the ones asked):
    the result of each, kept in the history."""
    targets = [t for t in rb_targets(store)
               if (only and t['id'] in only) or (not only and t.get('enabled'))]
    if not targets:
        raise RbError('no destination is switched on')
    # Never sent unlocked (1.0.136): it holds the key every token is sealed
    # with, the whole database and config.json - whoever reads the share
    # could unseal every token.
    if not rb_password():
        raise RbError('the backups have no password: set one (Settings - Backups - '
                      'Backups to other machines) - unlocked, a copy would hand the key of '
                      'every token to whoever can read the destination')
    work = tempfile.mkdtemp(prefix='otp-rbackup-', dir=str(STATE_DIR))
    os.chmod(work, 0o700)
    began = time.time()
    run = {'at': began, 'by': by, 'node': node_name(), 'targets': [], 'ok': False}
    try:
        path, m, _md = rb_build(store, work, progress)
        run.update(file=m['file'], bytes=m['bytes'], encrypted=m['encrypted'],
                   tokens=m['tokens'])
        sha = os.path.join(work, m['file'] + '.sha256')
        md = os.path.join(work, m['file'].split('.tar.gz')[0] + '-RESTORE.md')
        for i, t in enumerate(targets):
            if progress:
                progress(5, 6, 'sent to %s (%d of %d)' % (t['name'], i + 1, len(targets)))
            one = {'id': t['id'], 'name': t['name'], 'kind': t['kind'], 'ok': False}
            t0 = time.time()
            tr = rb_transport(t)
            try:
                tr.open()
                tr.put(path, m['file'])
                tr.put(sha, os.path.basename(sha))
                tr.put(md, os.path.basename(md))
                got = {x['name']: x['size'] for x in tr.list()}
                if got.get(m['file']) not in (None, m['bytes']):
                    raise RbError('the server holds %s bytes of it, not %s' % (
                        got.get(m['file']), m['bytes']))
                one['ok'] = True
                try:
                    one['taken_away'] = rb_retain(tr, int(CONFIG.get('rbackup_keep') or 0),
                                                  int(CONFIG.get('rbackup_keep_days') or 0))
                except Exception as e:                  # noqa: BLE001
                    one['retain_error'] = str(e)[:200]
            except Exception as e:                      # noqa: BLE001
                one['error'] = rb_said(e)
            finally:
                tr.close()
            one['secs'] = round(time.time() - t0, 1)
            run['targets'].append(one)
            rb_set_fields(store, t['id'], '', '', last={
                'at': time.time(), 'ok': one['ok'], 'error': one.get('error') or '',
                'file': m['file'], 'bytes': m['bytes']})
        run['ok'] = all(x['ok'] for x in run['targets'])
    except (RbError, OSError, ValueError, subprocess.SubprocessError) as e:
        run['error'] = scrub_secret(str(e))[:400]
    finally:
        shutil.rmtree(work, ignore_errors=True)
    run['secs'] = round(time.time() - began, 1)
    rb_history_add(store, run)
    good = [x['name'] for x in run['targets'] if x['ok']]
    bad = ['%s (%s)' % (x['name'], x.get('error')) for x in run['targets'] if not x['ok']]
    store.add_event('backups', 'a backup of %s (%s) %s%s%s' % (
        node_name(), human_bytes(run.get('bytes') or 0), ('went to ' + ', '.join(good))
        if good else 'went nowhere', ('; not to ' + '; '.join(bad)) if bad else '',
        ('; ' + run['error']) if run.get('error') else ''),
        'info' if run['ok'] else 'bad', who=by)
    log('remote backup: %s' % ('sent to ' + ', '.join(good) if good else 'not sent')
        + (' - failed: ' + '; '.join(bad) if bad else '')
        + (' - ' + run['error'] if run.get('error') else ''), 'info' if run['ok'] else 'warn')
    return run


def human_bytes(n):
    n = float(n or 0)
    for unit in ('B', 'kB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return ('%d %s' % (n, unit)) if unit == 'B' else ('%.1f %s' % (n, unit))
        n /= 1024.0
    return '%d B' % n


def rb_history(store):
    try:
        got = json.loads(store.get_meta('rbackup:runs') or '[]')
    except ValueError:
        got = []
    return [x for x in got if isinstance(x, dict)]


def rb_history_forget(store, at=None, file=None):
    """One line off the list (at and file), or all of it (1.0.110). The
    backups themselves stay where they went."""
    with RB_LOCK:
        runs = rb_history(store)
        if at is None:
            left = []
        else:
            left = [r for r in runs if not (abs(float(r.get('at') or 0) - float(at)) < 0.001 and
                                           str(r.get('file') or '') == str(file or ''))]
        store.set_meta('rbackup:runs', json.dumps(left, default=str))
        return len(runs) - len(left)


def rb_history_add(store, run):
    with RB_LOCK:
        runs = [run] + rb_history(store)
        store.set_meta('rbackup:runs', json.dumps(runs[:60], default=str))


def rb_job_start(store, by, only=None):
    """In a thread of its own; the page follows RB_JOB."""
    with RB_LOCK:
        if RB_JOB['running']:
            raise ValueError('a backup is being made already')
        RB_JOB.update(running=True, what='backup', says='starting', done=0, whole=6, error='',
                      began=time.time(), ended=0, result=None, by=by)

    def progress(done, whole, says):
        RB_JOB.update(done=done, whole=whole, says=says)

    def work():
        try:
            RB_JOB['result'] = rb_run(store, by, only, progress)
            if RB_JOB['result'].get('error'):
                RB_JOB['error'] = RB_JOB['result']['error']
        except Exception as e:                          # noqa: BLE001
            RB_JOB['error'] = scrub_secret(str(e))[:400]
            log('remote backup failed: %s' % e, 'error')
        finally:
            RB_JOB.update(running=False, ended=time.time())
    threading.Thread(target=work, name='rbackup', daemon=True).start()
    return dict(RB_JOB)


def rb_due(store, last_day):
    """Whether the scheduled backup is due now; the day it is for."""
    if not CONFIG.get('rbackup'):
        return None
    try:
        hh, mm = (int(x) for x in str(CONFIG.get('rbackup_at') or '04:00').split(':', 1))
    except ValueError:
        hh, mm = 4, 0
    now = datetime.now()
    if (now.hour, now.minute) < (hh, mm):
        return None
    if str(CONFIG.get('rbackup_every') or 'daily') == 'weekly' and \
            now.isoweekday() != int(CONFIG.get('rbackup_day') or 7):
        return None
    today = now.strftime('%Y-%m-%d')
    return today if today != last_day else None


def rb_tick(daemon):
    """Once a minute from the daemon's loop: the scheduled backup, this node's."""
    store = daemon.store
    day = rb_due(store, getattr(daemon, '_rb_day', ''))
    if not day or RB_JOB['running']:
        return
    daemon._rb_day = day
    if not claim_once(store, 'rbackup_day:' + node_name(), day):
        return
    if not any(t.get('enabled') for t in rb_targets(store)):
        return
    rb_job_start(store, 'otp (scheduled)')


# ---- putting one back -----------------------------------------------------------------
def rb_open(path, password, work):
    """A backup file opened into `work`: its folder and its manifest - every
    file checked against the checksum the manifest has."""
    src = path
    with open(path, 'rb') as f:
        head = f.read(8)
    if head.startswith(b'Salted__'):
        if not password:
            raise RbError('the backup is locked: its password is needed')
        src = os.path.join(work, 'b.tar.gz')
        try:
            _openssl(['enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', str(RB_ITER), '-md',
                      'sha256', '-in', path, '-out', src, '-pass', 'env:OTP_RB_PASS'],
                     env={'OTP_RB_PASS': password}, what='opening it')
        except ValueError:
            raise RbError('the password does not open it (or the file is damaged)')
    elif not head.startswith(b'\x1f\x8b'):
        raise RbError('that is not a backup of otp (neither locked nor a .tar.gz)')
    out = os.path.join(work, 'x')
    os.makedirs(out, mode=0o700)
    with tarfile.open(src, 'r:gz') as tf:
        members = tf.getmembers()
        tops = set()
        for mb in members:
            parts = mb.name.split('/')
            if mb.name.startswith('/') or '..' in parts or not (mb.isfile() or mb.isdir()):
                raise RbError('the archive has a file it may not have: %r' % mb.name[:100])
            tops.add(parts[0])
        if len(tops) != 1:
            raise RbError('the archive is not one backup')
        # Unpacked only when it fits (1.0.136): a small file that unpacks to
        # more than the disk has would fill /var/lib/otp, the database's too.
        total = sum(mb.size for mb in members if mb.isfile())
        try:
            free = shutil.disk_usage(work).free
        except OSError:
            free = None
        if free is not None and total > free - 512 * 1024 * 1024:
            raise RbError('unpacked it is %s, more than there is room for here (%s free)'
                          % (human_bytes(total), human_bytes(max(0, free))))
        for mb in members:
            if mb.isfile():
                dst = os.path.join(out, *mb.name.split('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with tf.extractfile(mb) as s, open(dst, 'wb') as d:
                    shutil.copyfileobj(s, d)
    top = os.path.join(out, tops.pop())
    try:
        with open(os.path.join(top, 'manifest.json')) as f:
            m = json.load(f)
    except (OSError, ValueError):
        raise RbError('there is no manifest in it')
    for rel, want in (m.get('files') or {}).items():
        p = os.path.join(top, *rel.split('/'))
        h = hashlib.sha256()
        try:
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
        except OSError:
            raise RbError('%s is missing from it' % rel)
        if h.hexdigest() != want.get('sha256'):
            raise RbError('%s is damaged (its checksum is not the one in the manifest)' % rel)
    return top, m


def rb_restore(store, path, password, by, keep_node_name=False, need_admin=True):
    """Everything in a backup put back on this machine: the database, the key
    of the tokens, the node's name. The connection to the database in
    config.json stays this machine's."""
    work = tempfile.mkdtemp(prefix='otp-putback-', dir=str(STATE_DIR))
    os.chmod(work, 0o700)
    try:
        top, m = rb_open(path, password, work)
        got = db_file_restore(store, os.path.join(top, 'otp-copy.json.gz'), by,
                              key_file=os.path.join(top, 'secrets.key'),
                              from_name=os.path.basename(str(path)), need_admin=need_admin)
        said = [got.get('key') or '']
        old_name = node_name()
        if m.get('node') and not keep_node_name and m['node'] != old_name and \
                not CONFIG.get('ha_mode'):
            write_file_settings({'node_name': m['node']})
            CONFIG['node_name'] = m['node']
            try:
                node_carry(store, old_name, m['node'], by=by)
            except Exception:                           # noqa: BLE001
                pass
            said.append('this machine is node %s again (it was %s)' % (m['node'], old_name))
        store.add_event('backups', '%s put back the backup %s (made %s on %s, otp %s)' % (
            by, os.path.basename(str(path)), m.get('made_words'), m.get('node'), m.get('otp')),
            'warn', who=by)
        return {'manifest': m, 'safety': got.get('safety'), 'said': [x for x in said if x]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def rb_fetch(store, tid, name, dst):
    t = rb_target(store, tid)
    if not t:
        raise ValueError('no such destination')
    if not RB_NAME_RE.match(str(name or '')):
        raise ValueError('not a backup of otp: %r' % str(name)[:80])
    tr = rb_transport(t)
    try:
        tr.open()
        tr.get(name, dst)
    finally:
        tr.close()


def rb_remote_list(store, tid):
    t = rb_target(store, tid)
    if not t:
        raise ValueError('no such destination')
    tr = rb_transport(t)
    try:
        tr.open()
        files = tr.list()
    finally:
        tr.close()
    names = set(x['name'] for x in files)
    out = []
    for x in files:
        m = RB_NAME_RE.match(x['name'])
        if not m:
            continue
        try:
            when = datetime.strptime(m.group('stamp'), '%Y%m%d-%H%M%S').timestamp()
        except ValueError:
            when = x.get('mtime') or 0
        out.append({'name': x['name'], 'bytes': x['size'], 'when': when,
                    'node': m.group('node'), 'site': m.group('site'),
                    'encrypted': bool(m.group('enc')),
                    'mine': m.group('node') == rb_slug(node_name()),
                    'sha256': (x['name'] + '.sha256') in names})
    out.sort(key=lambda x: -x['when'])
    return out

