# ---------------------------------------------------------------------------
# The database's word, signed (1.0.231): root's actions only from rows written by otp
# ---------------------------------------------------------------------------
# What a node has done as root - the firewall, sshd and root's SSH keys, the network, a
# restart, the system's updates and their proxy, the time servers, nginx's certificates, the
# VIP, the TLS of the database link - follows rows of the database: settings, rows of `meta`,
# requests one node leaves for another. Anybody who can write the database (its server, a
# db_password found out, a copy of it put back) could write those rows, and the node did as
# they said - even signing in to these pages, with an account or a session put in the table.
#
# Every such row is signed now when otp writes it: an HMAC under a key worked out from
# secrets.key, which is in no database (both nodes of a cluster have it). The signature is a row
# of its own beside it, `sig:<kind>:<hash of the name>:<node>` = {"n": counter, "m": mac} - versions
# before this one see a row of meta they do not know, and leave it. With `db_guard` on (a
# setting of config.json, never of the database; off by default - as until now) a node takes
# a row it acts on as root only when its signature is right and its counter not older than the
# one it saw last (kept in its own file, not in the database): a row written by somebody else
# reads as not there - an older signed row put back as well. Settings keep their last good
# value then; RADIUS, the codes and the tokens are never held up by any of it.
#
# Not against the other node of a cluster: it holds the same key, and root on it is root of the
# cluster's database anyway.

DBGUARD_META_EXACT = frozenset((
    'web:vip', 'web:access', 'fw:conf', 'fw:trial', 'fw_trial_back', 'ntp:conf', 'power:plan',
    'readdress:ask', 'hatls:ca', 'hatls:want', 'host:osup:plan', 'host:sshd:conf',
    'host:sshd:keep', 'host:sshd:back', 'sshotp:gate', 'host:logs:again', 'upgrade:plan',
    'upgrade:pkg', 'acme_push:conf', 'acme_push:pairing', 'hisec:waive', 'host:pwpolicy:conf',
    'rbackup:targets'))
DBGUARD_META_PREFIXES = (
    'web:tls:', 'web:retry:', 'ntp:sync:', 'net:want:', 'net:job:', 'net:undo:', 'net:keep:',
    'net:back:', 'readdress:dropold:', 'hatls:node:', 'dbtls:server:', 'ask:want:',
    'host:sshkeys:want:', 'host:rootkey:', 'host:osup:checkwant:', 'sshotp:u:', 'sshotp:port:',
    'console:want:', 'acme_push:key:', 'adm2fa:', 'host:selinux:want:',
    'host:users:want:', 'host:keep:', 'host:putback:', 'rbackup:now:',
    # The system's trusted roots each node puts in as root (1.0.265): the set wanted.
    'oscerts:want:')
# Settings whose word reaches root, or who may sign in to these pages.
DBGUARD_SETTINGS = frozenset((
    'acme', 'acme_challenge', 'acme_for', 'acme_node_name', 'radius_auth_port',
    'radius_acct_port', 'snmp', 'snmp_from', 'snmp_port', 'net_confirm_min', 'fw_confirm_min',
    'web_proxy', 'web_proxy_from', 'web_proxy_header', 'web_proxy_recursive', 'web_proxy_port',
    'portal_sso', 'portal_sso_from', 'portal_sso_header', 'portal_sso_key', 'portal_sso_logout',
    'proxy', 'proxy_url', 'proxy_user', 'proxy_password', 'proxy_os', 'proxy_no', 'proxy_update',
    'osup_check', 'osup_check_at', 'osup_auto', 'osup_auto_every', 'osup_auto_day',
    'osup_auto_at', 'osup_auto_reboot', 'osup_auto_what', 'power_auto', 'power_auto_every',
    'power_auto_day', 'power_auto_at', 'power_auto_needed', 'logs_journal_mb',
    'logs_journal_days', 'logs_keep', 'logs_max_mb', 'ssh_gate_port', 'upgrade_downgrade',
    'upgrade_check', 'upgrade_url', 'high_security', 'admin_directory', 'admin_group_full',
    'admin_group_token', 'admin_group_readonly', 'admin_2fa', 'admin_2fa_app', 'admin_2fa_mail',
    'admin_2fa_sms', 'admin_2fa_passkey', 'session_hours', 'session_idle_min', 'login_tries', 'login_wait_min',
    'mail_mode', 'mail_from', 'smtp_host', 'smtp_port', 'smtp_security', 'smtp_auth',
    'smtp_user', 'smtp_password', 'sms_mode', 'sms_url', 'sms_token', 'sms_spool_dir',
    'sms_tel_host', 'sms_tel_user', 'sms_tel_password', 'sms_tel_https', 'sms_tel_verify',
    # The remote backups (1.0.248): a destination and its password written by somebody else had
    # every backup - with secrets.key, the key of this very guard - sent to them.
    'rbackup', 'rbackup_at', 'rbackup_every', 'rbackup_day', 'rbackup_keep', 'rbackup_keep_days',
    'rbackup_verify', 'rbackup_password',
    # The DNS of ACME (1.0.248): its key went to the server named - any sealed secret of the
    # database put in its place (the directory's password, say) went to a server of theirs.
    'acme_dns', 'acme_dns_url', 'acme_dns_key', 'acme_dns_user', 'acme_dns_server',
    'acme_dns_token', 'acme_dns_tsig_alg', 'acme_dns_tsig_name', 'acme_dns_tsig_secret',
    'acme_desec_token', 'acme_desec_domain'))
# Rows signed only since a version (1.0.248): written unsigned by the versions before it, they
# are signed once as they are at the first start of that version with the guard on - until then
# they were acted on whoever wrote them, and refused at once they had stopped what they drive.
DBGUARD_SINCE = {
    '1.0.248': {'meta': ('rbackup:targets',), 'meta_prefixes': ('rbackup:now:',),
                'settings': ('rbackup', 'rbackup_at', 'rbackup_every', 'rbackup_day', 'rbackup_keep',
                             'rbackup_keep_days', 'rbackup_verify', 'rbackup_password',
                             'acme_dns', 'acme_dns_url', 'acme_dns_key', 'acme_dns_user', 'acme_dns_server',
                             'acme_dns_token', 'acme_dns_tsig_alg', 'acme_dns_tsig_name', 'acme_dns_tsig_secret',
                             'acme_desec_token', 'acme_desec_domain')},
    # The signed marks of a sign-in's second step ('xm'): a node before 1.0.255 writes none.
    '1.0.255': {}}
# How long a node not heard from is still counted as one of the cluster's (1.0.251).
DBGUARD_PEER_DAY_S = 86400
DBGUARD_FILE = STATE_DIR / 'guard.json'
DBGUARD = {'seen': None, 'good': None, 'seen_h': None, 'dirty': 0.0, 'refused': {}, 'nodes': {},
           'adopted': [], 'behind': set(), 'lock': threading.Lock()}


def dbguard_on():
    return bool(CONFIG.get('db_guard'))


def dbguard_key():
    key = sealing_key()
    return hmac.new(key, b'otp-db-guard-1', hashlib.sha256).digest() if key else None


def dbguard_meta_kept(k):
    """Whether a row of meta is one that is signed."""
    k = str(k or '')
    return k in DBGUARD_META_EXACT or k.startswith(DBGUARD_META_PREFIXES)


def dbguard_meta_signed(k):
    """Signed when written: those above, and the nodes' heartbeats (checked only where root
    uses them - the firewall's cluster rule, nginx's access, the VIP's and chrony's peer)."""
    return dbguard_meta_kept(k) or str(k or '').startswith('node:')


def dbguard_setting_kept(k):
    return str(k or '').split('@', 1)[0] in DBGUARD_SETTINGS


def _dbguard_hash(ident):
    return hashlib.sha256(str(ident).encode('utf-8')).hexdigest()[:40]


def _dbguard_sid(kind, ident, node=None):
    """This node's signature of a row (each node writes only its own - two nodes making one row
    at once is a duplicate key that stops replication for good)."""
    return 'sig:%s:%s:%s' % (kind, _dbguard_hash(ident), node or node_name())


def _dbguard_head_rows(db, head):
    """The rows of meta whose key starts with `head` (letters, digits and colons only), read by
    the key's index: a range on SQLite and MariaDB (their keys compare byte by byte), LIKE on
    PostgreSQL (a collation of a language may not order the colon as a byte would)."""
    if db.engine == 'postgres':
        return db.rows("SELECT k, v FROM meta WHERE k LIKE ?", (head + '%',))
    return db.rows("SELECT k, v FROM meta WHERE k >= ? AND k < ?", (head, head[:-1] + ';'))


def _dbguard_sigs(db, kind, ident):
    """Every node's signature of a row: [(k, n, mac)]."""
    # A range of the key, not LIKE (1.0.231): LIKE read the whole of meta on SQLite at every
    # heartbeat - RADIUS waited behind it.
    head = 'sig:%s:%s:' % (kind, _dbguard_hash(ident))
    out = []
    for r in _dbguard_head_rows(db, head):
        if not r['k'].startswith(head):
            continue
        try:
            sig = json.loads(r['v'] or 'null')
            out.append((r['k'], int(sig.get('n') or 0), str(sig.get('m') or '')))
        except (ValueError, TypeError, AttributeError):
            continue
    return out


def _dbguard_mac(key, kind, ident, n, value):
    body = b'\x01deleted' if value is None else b'\x00' + str(value).encode('utf-8', 'surrogatepass')
    msg = ('%s\x00%s\x00%d' % (kind, ident, int(n))).encode('utf-8', 'surrogatepass') + body
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _dbguard_load():
    with DBGUARD['lock']:
        if DBGUARD['seen'] is None:
            DBGUARD['had_file'] = DBGUARD_FILE.exists()
            try:
                got = json.loads(DBGUARD_FILE.read_text())
            except (OSError, ValueError):
                got = {}
            DBGUARD['seen'] = dict(odict(got.get('seen'))) if isinstance(got, dict) else {}
            DBGUARD['good'] = dict(odict(got.get('good'))) if isinstance(got, dict) else {}
            DBGUARD['seen_h'] = dict(odict(got.get('seen_h'))) if isinstance(got, dict) else {}
            DBGUARD['adopted'] = list(got.get('adopted') or []) if isinstance(got, dict) else []


def dbguard_flush(force=False):
    """The counters seen and the settings last found good, to this node's own file."""
    if DBGUARD['seen'] is None or not DBGUARD['dirty']:
        return
    if not force and time.time() - DBGUARD['dirty'] < 3:
        return
    with DBGUARD['lock']:
        if not DBGUARD.get('had_file'):
            # The file made now, by this version (1.0.248): nothing of a version before here is
            # this node's own to take as otp's at a later start (dbguard_adopt, bind_tokens).
            DBGUARD['adopted'] = sorted(set(DBGUARD.get('adopted') or []) | set(DBGUARD_SINCE) |
                                        {'tokens'})
        data = json.dumps({'seen': DBGUARD['seen'], 'good': DBGUARD['good'],
                           'seen_h': DBGUARD['seen_h'] or {}, 'adopted': DBGUARD.get('adopted') or []})
        DBGUARD['dirty'] = 0.0
    try:
        # The state folder's owner's even when root writes it (1.0.249: a copy put back, a rename from
        # the command line) - left root's, the service could not read its counts at all.
        owner = None
        if os.geteuid() == 0:
            st = os.stat(str(STATE_DIR))
            owner = (st.st_uid, st.st_gid)
        write_replacing(DBGUARD_FILE, data, 0o600, owner=owner)
        # The file is there from now on (1.0.252): still taken as missing, every flush put the
        # versions held back for a node of a version before into 'adopted' again - a warning a
        # minute, and its rows never taken in once it ran the new version.
        DBGUARD['had_file'] = True
    except Exception as e:                              # noqa: BLE001
        log_sparing('guard-file', 'the counters of signed rows could not be written to %s: %s'
                    % (DBGUARD_FILE, e), 'warn', every=600)


def dbguard_sign(db, kind, ident, value, far=False):
    """The row's signature written beside it, in `db` - this node's database, or (`far`) the
    other node's for a row written straight there: only over this node's signature already
    there, never a new row (replication brings that). Without the key nothing is written."""
    key = dbguard_key()
    if not key:
        return False
    sid = _dbguard_sid(kind, ident)
    for _ in range(6):
        try:
            sigs = _dbguard_sigs(db, kind, ident)
        except Exception:                               # noqa: BLE001
            if getattr(db, 'in_tx', False):
                raise
            return False
        raw = db.value('SELECT v FROM meta WHERE k = ?', (sid,))
        # Newer than every node's (1.0.231): read in this order by every node, whatever the
        # clocks say.
        n = max([int(time.time() * 1000)] + [x[1] + 1 for x in sigs])
        new = json.dumps({'n': n, 'm': _dbguard_mac(key, kind, ident, n, value)})
        try:
            if raw is None:
                if far:
                    return False
                db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (sid, new))
                return True
            if db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (new, sid, raw)):
                return True
        except Exception:                               # noqa: BLE001
            # Inside a transaction (1.0.234): PostgreSQL has given it up already, so every
            # try after this failed too and the COMMIT became a ROLLBACK, saying nothing -
            # the row and its signature were lost without a word. Said to the caller.
            if getattr(db, 'in_tx', False):
                raise
            continue
    return False


def _dbguard_ver(v):
    try:
        return tuple(int(x) for x in str(v).split('.')[:3])
    except (TypeError, ValueError):
        return ()


def _dbguard_not_yet(kind, ident):
    """A row signed only since a version not taken in yet (1.0.250): while a node of a version
    before it is still in the cluster, it writes such rows unsigned - they were refused, and the
    same error came at every tick for as long as they were there. Until every node runs it they
    are taken as they were before it, then signed once as they are (dbguard_adopt_tick)."""
    k = str(ident or '')
    if kind == 'm':
        hit = [v for v, w in DBGUARD_SINCE.items()
               if k in w.get('meta', ()) or k.startswith(tuple(w.get('meta_prefixes', ())))]
    elif kind == 's':
        hit = [v for v, w in DBGUARD_SINCE.items() if k.split('@', 1)[0] in w.get('settings', ())]
    else:
        return False
    if not hit:
        return False
    # Only while such a node is seen alive (by its signed heartbeat): with none, checked as before.
    behind = DBGUARD.get('behind') or ()
    return any(v in behind for v in hit)


def dbguard_ok(db, kind, ident, value, quiet=False, early=True):
    """Whether a row is as otp wrote it: True whenever the guard is off."""
    if not dbguard_on():
        return True
    if early and _dbguard_not_yet(kind, ident):
        return True
    key = dbguard_key()
    sid = 'sig:%s:%s:*' % (kind, _dbguard_hash(ident))
    why = ''
    try:
        sigs = _dbguard_sigs(db, kind, ident)
    except Exception:                                   # noqa: BLE001
        sigs = []
    if not key:
        why = 'this node has no key to check it with'
    elif not sigs:
        why = 'it is not signed'
    else:
        good = [n for _k, n, m in sigs if hmac.compare_digest(m, _dbguard_mac(key, kind, ident, n, value))]
        if not good:
            why = 'its signature is not right'
        else:
            n = max(good)
            vh = hashlib.sha256(json.dumps(value).encode('utf-8')).hexdigest()[:16]
            _dbguard_load()
            with DBGUARD['lock']:
                seen = int(DBGUARD['seen'].get(sid) or 0)
                hs = DBGUARD['seen_h']
                if hs is None:
                    hs = DBGUARD['seen_h'] = {}
                # An older signature of the same value is no older row (1.0.234): a row signed
                # here and again straight in the other node's database came over by
                # replication with the first signature after the second was seen - refused
                # there for good, though nothing had changed.
                if n < seen and hs.get(sid) != vh:
                    why = 'it is an older one put back'
                elif n > seen:
                    DBGUARD['seen'][sid] = n
                    hs[sid] = vh
                    DBGUARD['dirty'] = DBGUARD['dirty'] or time.time()
    if not why:
        with DBGUARD['lock']:
            DBGUARD['refused'].pop(sid, None)       # good again: no longer listed (1.0.234)
        return True
    if quiet:
        return False                                # asked again by the caller (1.0.234)
    with DBGUARD['lock']:
        was = DBGUARD['refused'].get(sid)
        DBGUARD['refused'][sid] = {'kind': kind, 'what': str(ident)[:120], 'why': why,
                                 'at': time.time(), 'first': (was or {}).get('first') or time.time()}
        if len(DBGUARD['refused']) > 200:
            for old in sorted(DBGUARD['refused'], key=lambda s: DBGUARD['refused'][s]['at'])[:50]:
                DBGUARD['refused'].pop(old, None)
    if not quiet:
        log_sparing('guard:' + sid, 'a row of the database not written by otp is not acted on: %s '
                    '%s - %s' % ({'m': 'meta', 's': 'the setting', 'a': 'the account',
                                  'x': 'a sign-in', 'xm': 'the second step of a sign-in',
                                  'd': 'the directory'}.get(kind, kind),
                                 str(ident)[:120], why), 'error', every=600)
    return False


def dbguard_settings(saved, store):
    """The settings of the database, those that reach root taken only as signed - else as
    they were last found good, else as config.json and the defaults have them."""
    if not dbguard_on() or store is None:
        return saved
    _dbguard_load()
    out = dict(saved)
    raw = {}
    try:
        raw = {r['k']: r['v'] for r in store.db.rows('SELECT k, v FROM settings')}
    except Exception:                                   # noqa: BLE001
        return saved
    keys = set(k for k in raw if dbguard_setting_kept(k)) | set(
        k for k in (DBGUARD['good'] or {}) if k not in raw)
    for k in keys:
        v = raw.get(k)
        if dbguard_ok(store.db, 's', k, v):
            with DBGUARD['lock']:
                if v is None:
                    DBGUARD['good'].pop(k, None)
                elif DBGUARD['good'].get(k) != v:
                    DBGUARD['good'][k] = v
                    DBGUARD['dirty'] = DBGUARD['dirty'] or time.time()
            continue
        good = (DBGUARD['good'] or {}).get(k)
        if good is None:
            out.pop(k, None)
        else:
            try:
                out[k] = json.loads(good)
            except (TypeError, ValueError):
                out.pop(k, None)
    return out


def dbguard_rows(db, rows):
    """Rows of meta read straight with SQL: those that are signed, the others left out."""
    if not dbguard_on():
        return rows
    return [r for r in rows if not dbguard_meta_kept(r.get('k')) or dbguard_ok(db, 'm', r['k'], r.get('v'))]


ACCOUNT_SIGNED = ('name', 'role', 'pw', 'source', 'disabled', 'must_change', 'dn')
DIRECTORY_SIGNED = ('name', 'hosts', 'port', 'tls', 'verify', 'ca', 'base', 'bind_dn', 'bind_pw',
                    'user_attr', 'enabled', 'weak')


def dbguard_row_text(row, cols):
    return json.dumps([None if row.get(c) is None else str(row.get(c)) for c in cols])


def dbguard_account_sign(db, name):
    row = db.row('SELECT * FROM accounts WHERE LOWER(name) = ?', (str(name or '').strip().lower(),))
    dbguard_sign(db, 'a', str(name or '').strip().lower(), dbguard_row_text(row, ACCOUNT_SIGNED) if row else None)


def dbguard_account_ok(db, row):
    if not row or not dbguard_on():
        return True
    return dbguard_ok(db, 'a', str(row.get('name') or '').lower(), dbguard_row_text(row, ACCOUNT_SIGNED))


def dbguard_directory_sign(db, name):
    row = db.row('SELECT * FROM directories WHERE LOWER(name) = ?', (str(name or '').lower(),))
    dbguard_sign(db, 'd', str(name or '').lower(), dbguard_row_text(row, DIRECTORY_SIGNED) if row else None)


def dbguard_directory_ok(db, name):
    if not dbguard_on():
        return True
    row = db.row('SELECT * FROM directories WHERE LOWER(name) = ?', (str(name or '').lower(),))
    return bool(row) and dbguard_ok(db, 'd', str(name or '').lower(), dbguard_row_text(row, DIRECTORY_SIGNED))


SESSION_SIGNED = ('kind', 'name', 'role', 'created', 'expires')


def dbguard_session_text(row):
    return json.dumps([str(row.get('kind') or ''), str(row.get('name') or ''),
                       str(row.get('role') or ''), '%.3f' % fnum(row.get('created')),
                       '%.3f' % fnum(row.get('expires'))])


# The marks of a sign-in's second step (1.0.255): signed too, as a signature of their own ('xm')
# beside the one versions before sign ('x', kept as it was - a node of 1.0.254 in the cluster takes
# the sign-ins of this one). The data of a session is not signed: one who could write the database
# took the "second step to give" out of a sign-in opened with the password alone, and had the pages.
SESSION_MARKS = ('mfa', 'mfa_ok', 'mfa_off')


def dbguard_session_marks(row):
    data = row.get('data')
    if not isinstance(data, dict):
        try:
            data = json.loads(data or '{}')
        except (TypeError, ValueError):
            data = {}
    data = data if isinstance(data, dict) else {}
    return json.dumps([dbguard_session_text(row)] + [str(data.get(k) or '') for k in SESSION_MARKS])


def dbguard_session_marks_ok(db, row):
    """Whether the marks of the second step in an admin sign-in are as otp wrote them (1.0.255) -
    asked only with the guard and the second step both on. A sign-in opened by 1.0.254 has none
    signed: it is ended once, as its marks cannot be told from ones written by somebody else."""
    if not dbguard_on() or not CONFIG.get('admin_2fa'):
        return True
    try:
        none = not _dbguard_sigs(db, 'xm', row['token_hash'])
    except Exception:                                   # noqa: BLE001
        none = False
    if none and '1.0.255' in (DBGUARD.get('behind') or ()):
        # A node of 1.0.254 alive in the cluster: it signs no marks - every sign-in it opened was
        # refused here, again each time the pages moved over. Taken as before while it is.
        return True
    if none:
        # Not listed among the rows refused: every sign-in kept over the upgrade is one.
        log_sparing('guard-xm-none', 'a sign-in to the pages with no signed marks of its second '
                    'step (opened before 1.0.255, or changed by somebody else) is asked to sign in '
                    'again', every=600)
        return False
    return dbguard_ok(db, 'xm', row['token_hash'], dbguard_session_marks(row))


def dbguard_meta_gone(db, k):
    """With the guard on, whether a signed row of meta reads as not there only because somebody
    else changed it (1.0.255): there but not signed by otp, or taken away while its last signature
    is of a value. Only the first since 1.0.255: a row not there is told from no reset of an older
    version. False with the guard off, and for a row never signed (nothing to tell by)."""
    if not dbguard_on():
        return False
    try:
        raw = db.value('SELECT v FROM meta WHERE k = ?', (k,))
        if raw is not None:
            # Read again once, as get_meta does: the row and its signature are two reads.
            return not dbguard_ok(db, 'm', k, raw, quiet=True) and \
                not dbguard_ok(db, 'm', k, db.value('SELECT v FROM meta WHERE k = ?', (k,)))
        # A row not there is not held: versions before 1.0.248 took it away unsigned (a reset, an
        # account deleted and made again) and left its last signature behind - such an account
        # was held, its administrator locked out until another one reset it.
        return False
    except Exception:                                   # noqa: BLE001
        return False


def dbguard_node_ok(store, name):
    """Whether a node's heartbeat is otp's - before its address is let through the firewall,
    into nginx's lists, or taken for the VIP's and chrony's peer."""
    if not dbguard_on() or name == node_name():
        return True
    try:
        raw = store.db.value('SELECT v FROM meta WHERE k = ?', ('node:' + name,))
    except Exception:                                   # noqa: BLE001
        return False
    if raw is None:
        return False
    try:
        addr = str((json.loads(raw) or {}).get('address') or '')
    except (TypeError, ValueError, AttributeError):
        addr = ''
    if dbguard_ok(store.db, 'm', 'node:' + name, raw, quiet=True):
        with DBGUARD['lock']:
            DBGUARD['nodes'][name] = (addr, time.time())
        return True
    # The heartbeat and its signature come over in two pieces from a node before 1.0.232
    # (two statements): read between them, the new one is not signed yet. The address it
    # had when it was last signed is still taken (1.0.232) - a row written by somebody else
    # cannot point the cluster anywhere new by it.
    with DBGUARD['lock']:
        known = DBGUARD['nodes'].get(name)
    # For a few minutes only (1.0.234): long enough for a signature behind its row, not a
    # row written by somebody else kept for ever.
    if addr and known and known[0] == addr and time.time() - known[1] < 180:
        return True
    return dbguard_ok(store.db, 'm', 'node:' + name, raw)


class SimpleStore(object):
    """A database alone, as dbguard_resign needs it."""

    def __init__(self, db):
        self.db = db

    def add_event(self, *a, **k):
        return None


def dbguard_forget_seen(why=''):
    """The newest signatures seen of each row forgotten, nothing signed (1.0.234): after this
    node's database was taken from the other node, its rows are as old as they are there."""
    _dbguard_load()
    with DBGUARD['lock']:
        DBGUARD['seen'] = {}
        DBGUARD['seen_h'] = {}
        DBGUARD['refused'] = {}
        DBGUARD['good'] = {}        # the values last found good were of that database (1.0.249)
        DBGUARD['dirty'] = time.time()
    dbguard_flush(force=True)
    if why:
        log('the guard against writes to the database starts its counts again: %s' % why)


def dbguard_resign(store, why=''):
    """Every row that is signed, signed again as it is now - when the guard is switched on, and
    after this node itself put rows in from elsewhere (a copy put back, an import, the
    database moved, a node renamed): what is there now is otp's word."""
    db = store.db
    n = 0
    if not dbguard_key():
        return 0
    for r in db.rows('SELECT k, v FROM meta'):
        if dbguard_meta_signed(r['k']):
            n += bool(dbguard_sign(db, 'm', r['k'], r['v']))
    for r in db.rows('SELECT k, v FROM settings'):
        if dbguard_setting_kept(r['k']):
            n += bool(dbguard_sign(db, 's', r['k'], r['v']))
    for r in db.rows('SELECT * FROM accounts'):
        n += bool(dbguard_sign(db, 'a', str(r['name']).lower(), dbguard_row_text(r, ACCOUNT_SIGNED)))
    for r in db.rows('SELECT * FROM directories'):
        n += bool(dbguard_sign(db, 'd', str(r['name']).lower(), dbguard_row_text(r, DIRECTORY_SIGNED)))
    for r in db.rows("SELECT * FROM sessions WHERE kind = 'admin'"):
        n += bool(dbguard_sign(db, 'x', r['token_hash'], dbguard_session_text(r)))
        dbguard_sign(db, 'xm', r['token_hash'], dbguard_session_marks(r))      # 1.0.255
    # What is seen from now on starts here: older ones put back are older than these.
    with DBGUARD['lock']:
        DBGUARD['seen'] = {}
        DBGUARD['seen_h'] = {}
        DBGUARD['good'] = {}
        DBGUARD['refused'] = {}
        # Every row signed as it is now (1.0.249): nothing left for a version's first start to
        # take as otp's word - switched on while running, the next start signed rows put in since.
        DBGUARD['adopted'] = sorted(set(DBGUARD.get('adopted') or []) | set(DBGUARD_SINCE) | {'tokens'})
        DBGUARD['dirty'] = time.time()
    dbguard_flush(force=True)
    if why:
        try:
            store.add_event('security', 'the rows of the database that reach root signed again '
                            '(%d) - %s' % (n, why), 'warn')
        except Exception:                               # noqa: BLE001
            pass
    return n


def _dbguard_older_nodes(store):
    """The other nodes, by the version their heartbeat - otp's, by its signature - says: every
    one heard from within a day, not only those alive (1.0.251) - a node of a version before
    restarting, or put back after an upgrade that failed, had no heartbeat of the last seconds;
    the rows were taken in meanwhile, and what it wrote once back was refused for ever."""
    out = {}
    try:
        # Whatever the mode says (1.0.252): a cluster on one database made before ha_mode, or by
        # hand, has none - and a node alone lists only itself.
        nodes = ha_nodes(store)
    except Exception:                                   # noqa: BLE001
        nodes = []
    for n in nodes:
        if n.get('me') or not n.get('version') or \
                not (n.get('alive') or fnum(n.get('age'), 1e9) < DBGUARD_PEER_DAY_S):
            continue
        try:
            raw = store.db.value('SELECT v FROM meta WHERE k = ?', ('node:' + n['name'],))
        except Exception:                               # noqa: BLE001
            continue
        if raw is not None and dbguard_ok(store.db, 'm', 'node:' + n['name'], raw, quiet=True):
            out[n['name']] = str(n['version'])
    return out


def dbguard_refused_tidy(store):
    """Rows of meta refused and gone since, no longer listed as refused (1.0.251): taken away by
    the node that wrote them, they stayed lit on the card until the next start. Only rows of
    meta - an ask, a job: a setting, an account or a directory taken away is itself what the
    guard is there for, the last good one is held and stays listed."""
    with DBGUARD['lock']:
        rows = [(sid, str(e.get('what') or '')) for sid, e in odict(DBGUARD.get('refused')).items()
                if isinstance(e, dict) and e.get('kind') == 'm']
    gone = []
    for sid, k in rows:
        if not k or len(k) >= 120:
            continue                                    # its name cut short: not looked for
        try:
            there = store.db.value('SELECT 1 FROM meta WHERE k = ?', (k,))
        except Exception:                               # noqa: BLE001
            return 0
        if there is None and sid == 'sig:m:%s:*' % _dbguard_hash(k):
            gone.append(sid)
    if gone:
        with DBGUARD['lock']:
            for sid in gone:
                DBGUARD['refused'].pop(sid, None)
    return len(gone)


def dbguard_adopt_tick(store):
    """Once a minute: a version's rows taken in once every node alive runs it - and again taken
    as before it while a node of a version before is back (switched on, or joined, with one
    still there), until it runs it too (1.0.250)."""
    if not dbguard_on() or not dbguard_key():
        return
    dbguard_refused_tidy(store)
    if not DBGUARD_SINCE:
        return
    older = _dbguard_older_nodes(store)
    behind = {ver for ver in DBGUARD_SINCE
              if any(_dbguard_ver(v) < _dbguard_ver(ver) for v in older.values())}
    _dbguard_load()
    with DBGUARD['lock']:
        DBGUARD['behind'] = behind
        had = set(DBGUARD.get('adopted') or [])
        if had & behind:
            DBGUARD['adopted'] = sorted(had - behind)
            DBGUARD['dirty'] = time.time()
        due = set(DBGUARD_SINCE) - set(DBGUARD['adopted']) - behind
    if had & behind:
        dbguard_flush(force=True)
        log('the rows signed only since %s are taken as before it while %s runs a version before'
            % (', '.join(sorted(had & behind)), ', '.join(sorted(older))), 'warn')
    if due:
        dbguard_adopt(store)


def dbguard_adopt(store):
    """At the start: the rows signed only since this version (DBGUARD_SINCE), found without a
    signature that is right, signed once as they are - each version's once, noted in guard.json
    (the other node, still of a version before, wrote them unsigned meanwhile)."""
    if not dbguard_on() or not dbguard_key():
        return []
    _dbguard_load()
    done = set(DBGUARD.get('adopted') or [])
    if not DBGUARD.get('had_file'):
        # A node with no counts of its own yet - installed anew, joining (1.0.248): it ran no
        # version before with the guard, so there is nothing of its own to take as otp's - only
        # rows of the database, which somebody may have put in. Rows of a version before are
        # signed by the node that ran it, at its own first start.
        with DBGUARD['lock']:
            DBGUARD['adopted'] = sorted(done | set(DBGUARD_SINCE) | {'tokens'})
            DBGUARD['dirty'] = time.time()
        dbguard_flush(force=True)
        return []
    db = store.db
    said = []
    older = _dbguard_older_nodes(store)
    DBGUARD['behind'] = {ver for ver in DBGUARD_SINCE
                         if any(_dbguard_ver(v) < _dbguard_ver(ver) for v in older.values())}
    for ver, what in sorted(DBGUARD_SINCE.items()):
        if ver in done:
            continue
        # Not while a node of a version before it is alive (1.0.250): it goes on writing these
        # rows unsigned - signed here now, its next one was refused, for ever.
        if any(_dbguard_ver(v) < _dbguard_ver(ver) for v in older.values()):
            continue
        for r in db.rows('SELECT k, v FROM meta'):
            k = str(r['k'])
            if (k in what.get('meta', ()) or k.startswith(tuple(what.get('meta_prefixes', ())))) and \
                    not dbguard_ok(db, 'm', k, r['v'], quiet=True, early=False) and \
                    dbguard_sign(db, 'm', k, r['v']):
                said.append(k)
        for r in db.rows('SELECT k, v FROM settings'):
            k = str(r['k'])
            if k.split('@', 1)[0] in what.get('settings', ()) and \
                    not dbguard_ok(db, 's', k, r['v'], quiet=True, early=False) and \
                    dbguard_sign(db, 's', k, r['v']):
                said.append(k)
        with DBGUARD['lock']:
            DBGUARD['adopted'] = sorted(set(DBGUARD.get('adopted') or []) | {ver})
            DBGUARD['dirty'] = time.time()
    dbguard_flush(force=True)
    if said:
        try:
            store.add_event('security', 'rows signed only since this version, found unsigned, '
                            'taken as otp\'s word once: %s' % ', '.join(sorted(said))[:900], 'warn')
        except Exception:                               # noqa: BLE001
            pass
    return said


def dbguard_tidy(store):
    """Signatures of sign-ins that are over."""
    try:
        hashes = [r['token_hash'] for r in store.db.rows(
            "SELECT token_hash FROM sessions WHERE kind = 'admin'")]
        have = {_dbguard_sid('x', t) for t in hashes}
        # The marks' signatures (1.0.255) as the sign-ins' own.
        have_m = {_dbguard_sid('xm', t) for t in hashes}
        for r in _dbguard_head_rows(store.db, 'sig:x:') + _dbguard_head_rows(store.db, 'sig:xm:'):
            if r['k'] not in have and r['k'] not in have_m and r['k'].endswith(':' + node_name()):
                try:
                    if time.time() * 1000 - float((json.loads(r['v']) or {}).get('n') or 0) < 3600e3:
                        continue
                except (ValueError, TypeError, AttributeError):
                    pass
                store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))
        # Their counts too (1.0.252): two for every sign-in to the pages, in memory and guard.json,
        # kept for ever.
        pre = {k.rsplit(':', 1)[0] for k in have}
        pre = pre | {k.rsplit(':', 1)[0] for k in have_m}
        _dbguard_load()
        with DBGUARD['lock']:
            for m in ('seen', 'seen_h'):
                d = DBGUARD.get(m) or {}
                for k in [k for k in d if k.startswith(('sig:x:', 'sig:xm:')) and
                          k.rsplit(':', 1)[0] not in pre]:
                    d.pop(k, None)
                    DBGUARD['dirty'] = DBGUARD['dirty'] or time.time()
    except Exception:                                   # noqa: BLE001
        pass
    dbguard_flush()


def dbguard_view():
    _dbguard_load()
    with DBGUARD['lock']:
        refused = sorted(DBGUARD['refused'].values(), key=lambda x: -x['at'])[:50]
    return {'on': dbguard_on(), 'key': bool(dbguard_key()), 'refused': refused}
