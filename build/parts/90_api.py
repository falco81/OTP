

# ---------------------------------------------------------------------------
# The API the web pages ask
# ---------------------------------------------------------------------------
# On 127.0.0.1 only, and only for whoever holds the token in /run/otp - which
# is the web server's group and nobody else. The PHP pages relay to it and
# add nothing: the session travels as a header, and this decides what that
# session may have. Two kinds of session: an administrator's (`admin`) and a
# person enrolling their own token (`portal`), which can reach nothing but
# its own token.

ROLE_RANK = {'readonly': 1, 'tokenadmin': 2, 'fulladmin': 3}


class ApiError(Exception):
    def __init__(self, status, words, detail=''):
        Exception.__init__(self, words)
        self.status = status
        self.detail = detail


def api_token(make=False):
    if make:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        write_replacing(TOKEN_FILE, token + '\n', 0o640)
        try:
            import grp
            gid = grp.getgrnam(WEB_GROUP).gr_gid
            os.chown(str(TOKEN_FILE), -1, gid)
            os.chmod(str(RUN_DIR), 0o750)
            os.chown(str(RUN_DIR), -1, gid)
        except (KeyError, OSError, ImportError):
            pass
        return token
    try:
        return TOKEN_FILE.read_text().strip()
    except OSError:
        return ''


def _int_id(v):
    """An id from a request: a whole number, or ValueError said plainly."""
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        raise ValueError('an id is a number')


BODY_WORDS = ('name', 'to', 'mail_to', 'dest', 'note', 'code', 'password', 'passphrase', 'lang',
              'kind', 'action', 'mail_fmt', 'display', 'user', 'old', 'new', 'q',
              'state', 'via', 'mode', 'fingerprint', 'label')


def _no_constant(word):
    raise ValueError('%s is not a number' % word)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = 'otp'
    protocol_version = 'HTTP/1.1'
    # A connection that says nothing for a minute is closed (1.0.101): each
    # held a thread for ever, and any program on this machine could open
    # thousands without the key.
    timeout = 60

    def log_message(self, fmt, *args):
        if debugging('api'):
            log('api %s' % (fmt % args), 'debug')

    # ---- the plumbing ---------------------------------------------------------
    @property
    def d(self):
        return self.server.daemon

    @property
    def store(self):
        return self.server.daemon.store

    @property
    def reader(self):
        """The long lists' own connection (1.0.101)."""
        return self.server.daemon.reader()

    def client_ip(self):
        said = str(self.headers.get('X-Otp-Client') or '').strip()
        return said if re.match(r'^[0-9a-fA-F:.]{2,45}\Z', said) else self.client_address[0]

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        if hasattr(self, '_body'):
            return self._body
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            raise ApiError(400, 'the length of the body is not a number')
        if n < 0:
            raise ApiError(400, 'the length of the body is not a number')
        if n > 8 * 1024 * 1024:
            raise ApiError(413, 'that is more than this takes')
        raw = self.rfile.read(n) if n else b''
        try:
            # NaN and Infinity are not numbers anybody means (1.0.103).
            self._body = json.loads(raw.decode('utf-8'), parse_constant=_no_constant) \
                if raw else {}
        except (ValueError, RecursionError):            # [[[[... too (1.0.139)
            raise ApiError(400, 'the body is not JSON')
        if not isinstance(self._body, dict):
            raise ApiError(400, 'the body is not an object')
        # What is a word is a word (1.0.103): a list where a name belongs was
        # made into the text "['x']" - a token by that name, a mail to it.
        for k in BODY_WORDS:
            v = self._body.get(k)
            if isinstance(v, (list, dict, bool)):
                raise ApiError(400, '%s is a piece of text here' % k)
            if isinstance(v, float) and k != 'code':
                raise ApiError(400, '%s is a piece of text here' % k)
        return self._body

    def body_to_file(self, path, most):
        """A request body that is a file, written down a lump at a time."""
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            raise ApiError(400, 'no file arrived')
        if n > most:
            raise ApiError(413, 'that file is bigger than this takes')
        left = n
        with open(str(path), 'wb') as out:
            while left > 0:
                lump = self.rfile.read(min(left, 1 << 20))
                if not lump:
                    raise ApiError(400, 'the file did not arrive whole')
                out.write(lump)
                left -= len(lump)
        self._body = {}
        return n

    def send_bytes(self, data, name, kind='application/octet-stream'):
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Disposition', 'attachment; filename="%s"' % name)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path, name):
        # Opened before a header is sent (1.0.61): a file it may not read -
        # a copy root made on the command line - went out as "200" and then
        # a 500 in the middle of the download.
        try:
            f = open(str(path), 'rb')
        except PermissionError:
            raise ApiError(403, '%s cannot be read by the service (made by root on the command '
                                'line?): chown otp:otp it, then again' % name)
        except FileNotFoundError:
            raise ApiError(404, 'there is no such file: %s' % name)
        with f:
            self._send_open_file(f, name)

    def _send_open_file(self, f, name):
        size = os.fstat(f.fileno()).st_size
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', 'attachment; filename="%s"' % name)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        shutil.copyfileobj(f, self.wfile, 1 << 18)

    def do_GET(self):
        self.route('GET')

    def do_POST(self):
        self.route('POST')

    def route(self, method):
        # A body of its own for each request (1.0.146): on a kept-alive
        # connection the handler is the same, and the last one's was read again.
        self.__dict__.pop('_body', None)
        url = urlparse(self.path)
        self.args = {k: v[-1] for k, v in parse_qs(url.query).items()}
        path = url.path.rstrip('/')
        self.route_path = path
        if path != '/api/health':
            want = api_token()
            given = str(self.headers.get('X-Otp-Token') or '')
            if not want or not hmac.compare_digest(want, given):
                return self.send_json({'ok': False, 'error': 'not this API’s token'}, 403)
        fn = ROUTES.get((method, path))
        if not fn:
            return self.send_json({'ok': False, 'error': 'no such endpoint: %s %s'
                                   % (method, path)}, 404)
        self._held = None
        self._failed = False
        try:
            got = fn(self)
            if got is not None:
                self.send_json(got if 'ok' in got else dict(ok=True, **got))
        except ApiError as e:
            # What went wrong in detail - a domain controller's name, a bind
            # DN - only to somebody signed in (1.0.33); the rest is in the log.
            detail = e.detail if self._signed_in() else None
            if e.detail and not detail:
                log('%s %s: %s (%s)' % (method, path, e, e.detail), 'info')
            self.send_json({'ok': False, 'error': str(e), 'detail': detail}, e.status)
        except (ValueError, BadSetting, RadiusError) as e:
            said = str(e)
            if said.startswith(('invalid literal for int()', 'could not convert string to float',
                                'cannot convert float')):
                # Python's words for a field that is not a number (1.0.103).
                said = 'a field that is a number holds something else'
            self.send_json({'ok': False, 'error': said}, 400)
        except LdapError as e:
            # The domain controller's name and its TLS - only to somebody
            # signed in (1.0.136), as an ApiError's detail is.
            if self._signed_in():
                self.send_json({'ok': False, 'error': str(e), 'detail': e.detail}, 502)
            else:
                log('%s %s: the directory: %s (%s)' % (method, path, e, e.detail), 'warn')
                self.send_json({'ok': False, 'error': 'the directory could not be asked just '
                                'now - try again in a moment', 'detail': None}, 502)
        except DbError as e:
            # Where the database is, only to somebody signed in (1.0.146).
            if self._signed_in():
                self.send_json({'ok': False, 'error': str(e)}, 503)
            else:
                log('%s %s: the database: %s' % (method, path, e), 'warn')
                self.send_json({'ok': False, 'error': 'the database cannot be reached just now '
                                                      '- try again in a moment'}, 503)
        except (TypeError, AttributeError, KeyError) as e:
            # A field of the wrong kind - null where a number goes, a list
            # where an object does (1.0.44): the request's fault, said so,
            # and the trace kept in case it was not.
            log('%s %s could not be read: %s\n%s' % (method, path, e, traceback.format_exc()),
                'warn')
            self.send_json({'ok': False, 'error': 'the request is not in the shape this '
                                                  'takes (a field of the wrong kind)'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            # The page went away before its answer did (1.0.61): nothing broke.
            pass
        except Exception as e:
            # A value the database cannot keep - a number out of its range, a
            # text too long for its column (1.0.103): the request's fault.
            kind = type(e).__name__
            if kind in ('DataError', 'NumericValueOutOfRange', 'StringDataRightTruncation',
                        'InvalidTextRepresentation', 'OverflowError') or \
                    (kind == 'OperationalError' and 'out of range' in str(e).lower()):
                log('%s %s: a value the database cannot keep: %s' % (method, path, e), 'info')
                self.send_json({'ok': False, 'error': 'a value is too big or of the wrong kind '
                                                      'for the database'}, 400)
                return
            log('the API broke on %s %s: %s\n%s' % (method, path, e, traceback.format_exc()),
                'error')
            # The words of the exception stay in the log (1.0.33).
            self.send_json({'ok': False, 'error': 'it broke - the reason is in the log of the '
                                                  'service (/var/log/otp/otp.log)'}, 500)
        finally:
            self._release()

    def _signed_in(self):
        token = str(self.headers.get('X-Otp-Session') or '')
        if not token:
            return False
        try:
            # Only a look: an error must not keep a session alive. (1.0.36)
            return bool(self.store.session_get(
                token, 'admin', int(CONFIG.get('session_idle_min') or 120) * 60, touch=False) or
                self.store.session_get(
                token, 'portal', int(CONFIG.get('portal_session_min') or 15) * 60, touch=False))
        except Exception:                               # noqa: BLE001
            return False

    def arg(self, name, default=''):
        return self.args.get(name, default)

    def num(self, name, default, lo=0, hi=10 ** 9):
        try:
            return max(lo, min(hi, int(float(self.args.get(name, default)))))
        except (TypeError, ValueError, OverflowError):
            return default

    # ---- who is asking ----------------------------------------------------------
    def session(self, kind):
        token = str(self.headers.get('X-Otp-Session') or '')
        if kind == 'admin':
            idle = int(CONFIG.get('session_idle_min') or 120) * 60
        else:
            idle = int(CONFIG.get('portal_session_min') or 15) * 60
        return self.store.session_get(token, kind, idle)

    def me(self, role='readonly'):
        s = self.session('admin')
        if not s:
            raise ApiError(401, 'not signed in, or the sign-in has run out')
        acc = self.store.account(s['name'])
        if not acc or acc.get('disabled'):
            self.store.session_end(self.headers.get('X-Otp-Session'))
            raise ApiError(401, 'that account may no longer sign in')
        if acc.get('source') == 'directory':
            acc = self.directory_recheck(acc)
        s['role'] = acc['role']
        # The second step first (1.0.125): until it is given, the sign-in may
        # do that and nothing else.
        if mfa_pending(s) and getattr(self, 'route_path', '') not in MFA_ALLOWED:
            raise ApiError(401, 'the second step of signing in is not done yet')
        if acc.get('must_change') and getattr(self, 'route_path', '') not in MUST_CHANGE_ALLOWED:
            raise ApiError(403, 'change the password first')
        if ROLE_RANK.get(s['role'], 0) < ROLE_RANK[role]:
            raise ApiError(403, {'fulladmin': 'only a full administrator may do that',
                                 'tokenadmin': 'only a token administrator may do that'}
                           .get(role, 'that account may not do that'))
        s['account'] = acc
        return s

    def portal_link(self):
        """The enrolment pages' address, for a token's mail: from the name the
        pages were reached by, never from what the page sent (1.0.33)."""
        host = str(self.headers.get('X-Otp-Host') or '')
        if not re.fullmatch(r'([A-Za-z0-9.-]{1,253}|\[[0-9A-Fa-f:.]{2,45}\])(:[0-9]{1,5})?', host):
            return ''
        return 'https://%s/' % host

    DIR_CHECKED = {}
    DIR_CHECK_S = 600

    def directory_recheck(self, acc):
        """Somebody signed in from the directory, asked about again every ten
        minutes (1.0.33): switched off there, or out of every group that gives
        a role, and the sign-in ends - not hours later when it runs out. A
        directory that cannot be reached leaves them as they are."""
        name = acc['name']
        t = time.time()
        if t - self.DIR_CHECKED.get(name.lower(), 0) < self.DIR_CHECK_S:
            return acc
        ad = self.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
        if not ad:
            self.end_all(name, 'the directory administrators sign in against is gone')
        try:
            who, how = admin_name_parts(name)
            entry = ad.find_user(who, how)
            role = None
            if entry and not entry_unusable(entry, locked=False):
                role = admin_role_for(ad.groups_of(entry, True), ad)
        except Exception as e:                          # noqa: BLE001
            # Asked again in a minute, not on every click: a directory that
            # does not answer would hold each page for its whole timeout. (1.0.36)
            self.DIR_CHECKED[name.lower()] = t - self.DIR_CHECK_S + 60
            log('the directory could not be asked about %s: %s' % (name, e), 'warn')
            return acc
        self.DIR_CHECKED[name.lower()] = t
        if not role:
            self.end_all(name, 'the directory no longer gives %s a role here' % name)
        if role != acc.get('role'):
            self.store.set_account(name, role=role)
            self.store.add_event('accounts', 'the directory gives %s the role %s now (was %s)'
                                 % (name, role, acc.get('role')), 'warn')
            acc = self.store.account(name)
        return acc

    def end_all(self, name, why):
        self.store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                          ('admin', name.lower()))
        self.store.add_event('accounts', '%s: signed out everywhere' % why, 'warn')
        raise ApiError(401, 'that account may no longer sign in')

    THROTTLE_LOCK = threading.Lock()
    THROTTLE_TIDIED = [0.0]

    def throttle(self, kind, tries, wait_min, name='', ip_tries=None, name_tries=None,
                 what='wrong passwords'):
        """A sign-in attempt, counted before the password is asked (1.0.33):
        thirty at once from one address all slipped past a count made after
        the slow check. The attempt holds a place until it is known to have
        gone well, and gives it back then. Counted per address and, more
        loosely, per name, so many addresses cannot share out the guessing
        of one password."""
        ip = self.client_ip()
        try:
            a = ipaddress.ip_address(str(ip).split('%')[0])
            if a.version == 6 and not a.ipv4_mapped:
                # One /64 is one machine's to choose from (1.0.101): counted
                # per address, each guess came from a new one.
                ip = str(ipaddress.ip_network('%s/64' % a, strict=False))
        except ValueError:
            pass
        keys = [(kind, ip)]
        if name:
            # Counted per person, not per spelling (1.0.44): DOMAIN\\novak,
            # novak@anything and Novak are all novak here.
            who = str(name).strip().lower()
            # "admin>person" (a test of somebody's sign-in) keeps its admin
            # (1.0.146): CORP\\novak made it novak alone, one count for all.
            pre, sep, who = who.rpartition('>')
            who = who.split('\\', 1)[-1].rsplit('@', 1)[0].strip()
            keys.append((kind + '-name', (pre + sep + who)[:190]))
        t = time.time()
        span = wait_min * 60
        with self.THROTTLE_LOCK:
            for i, key in enumerate(keys):
                # Each limit its own where asked (1.0.103): a code typed on the
                # enrolment pages is one person's, and five typos of one
                # person locked the whole office behind its address out.
                limit = (ip_tries or tries) if i == 0 else (name_tries or tries * 4)
                fails = [x for x in self.d.login_fails[key] if t - x < span]
                self.d.login_fails[key] = fails
                info = self.d.login_info.setdefault(key, {'others': []})
                info.update(limit=limit, span=span, what=what, at=t)
                other = (str(name).strip()[:120] if i == 0 else str(ip)) if name or i else ''
                if other:
                    if other in info['others']:
                        info['others'].remove(other)
                    info['others'] = (info['others'] + [other])[-6:]
                if len(fails) >= limit:
                    raise ApiError(429, 'too many %s %s: try again in %s'
                                   % (what, 'from %s' % ip if i == 0 else 'for this name',
                                      human_span(span - (t - fails[0]))))
            for key in keys:
                self.d.login_fails[key].append(t)
            # Tidied at most every 30 s (1.0.59): past 20 000 names all still
            # waiting, every sign-in scanned the whole map under this lock.
            # Past 50 000 the oldest half goes - memory has an end.
            fl = self.d.login_fails
            if len(fl) > 20000 and t - self.THROTTLE_TIDIED[0] > 30:
                self.THROTTLE_TIDIED[0] = t
                # Kept for the longest wait of any kind (1.0.61), not this
                # kind's: a 5 min kind tidied away 15 min lockouts.
                keep_s = max(span, 6 * 3600)
                for k in [k for k, v in fl.items() if not v or t - v[-1] > keep_s]:
                    fl.pop(k, None)
                    self.d.login_info.pop(k, None)
                if len(fl) > 50000:
                    # Addresses go before names (1.0.61): many addresses must
                    # not flush the count of the one name being guessed.
                    order = sorted(fl, key=lambda k: (str(k[0]).endswith('-name'),
                                                      fl[k][-1] if fl[k] else 0))
                    for k in order[:len(fl) // 2]:
                        if k not in keys:
                            fl.pop(k, None)
                            self.d.login_info.pop(k, None)
        self._held = (keys, t)
        return keys

    def failed(self, key):
        """The attempt went wrong: the place it holds stays taken."""
        self._failed = True

    def _release(self):
        held = getattr(self, '_held', None)
        if not held or getattr(self, '_failed', False):
            return
        keys, t = held
        with self.THROTTLE_LOCK:
            for key in keys:
                got = self.d.login_fails.get(key)
                if got and t in got:
                    got.remove(t)
        self._held = None


ROUTES = {}
# What an administrator who still has to change their password may do.
MUST_CHANGE_ALLOWED = ('/api/auth/password', '/api/auth/logout', '/api/auth/whoami')


def route(method, path):
    def wrap(fn):
        ROUTES[(method, path)] = fn
        return fn
    return wrap


# ---- health and signing in -------------------------------------------------------
HEALTH_SEEN = {}


# ---- who is locked out (1.0.112) ---------------------------------------------------
# Each node counts the wrong passwords that reach it, in memory. Every node
# writes its list into meta when it changes, so the pages of either show both;
# a lockout is cleared by the node that holds it - asked through meta when it
# is the other one.
LOCKOUT_KINDS = {
    'admin': 'signing in to these pages',
    'portal': 'signing in to the enrolment pages',
    'portal-verify': 'a code typed on the enrolment pages',
    'portal-send': 'codes sent from the enrolment pages',
    'portal-confirm': 'confirming a token on the enrolment pages',
    'portal-reissue': 'a new token on the enrolment pages',
    'portal-codes': 'recovery codes shown on the enrolment pages',
    # Kept in the database for the whole cluster (1.0.116), not in a node's
    # memory: codes sent to a person, and a token locked by wrong codes.
    'codes-sent': 'codes sent by e-mail or SMS',
    'token-locked': 'the token, after wrong codes',
    'password': 'changing a password',
    'code-test': 'trying a code (Tokens)',
    'radtest': 'a RADIUS test (Test)',
    'texts-test': 'a test message (Message texts)',
    'radius-src': 'signing in to the VPN, from one place',
}
LOCKOUTS_SENT = {'sig': None, 'at': 0.0}
THROTTLE_GUARD = threading.Lock()


def lockouts_view(d):
    """What this node counts now: one line per address or name with a wrong
    attempt still counted, locked or not yet."""
    t = time.time()
    rows = []
    for key, fails in list(d.login_fails.items()):
        info = d.login_info.get(key) or {}
        span = float(info.get('span') or 0)
        if not span:
            continue
        fails = [x for x in fails if t - x < span]
        kind, who = key
        if info.get('guard'):
            # A place counted by the sign-in protection (1.0.137): blocked
            # for its own time, by its refusals or by its names.
            until = float(info.get('blocked_until') or 0)
            blocked = until > t
            if not fails and not blocked:
                continue
            names = [n for n, ts in (info.get('names') or {}).items() if t - ts < span]
            last = max(fails[-1] if fails else 0, float(info.get('blocked_at') or 0))
            rows.append({
                'kind': kind, 'who': who, 'by': 'place', 'what': LOCKOUT_KINDS.get(kind, kind),
                'base': kind, 'words': info.get('what') or 'wrong sign-ins',
                'fails': len(fails), 'limit': int(info.get('limit') or 0),
                'names': len(names), 'names_limit': int(info.get('names_limit') or 0),
                'locked': blocked, 'until': until if blocked else None,
                'why': info.get('blocked_why') if blocked else '',
                'forgets': max(until, (fails[-1] + span) if fails else 0),
                'first': fails[0] if fails else last, 'last': last,
                'others': list(info.get('others') or [])})
            continue
        if not fails:
            continue
        by_name = kind.endswith('-name')
        base = kind[:-5] if by_name else kind
        limit = int(info.get('limit') or 0)
        locked = bool(limit) and len(fails) >= limit
        rows.append({
            'kind': kind, 'who': who, 'by': 'name' if by_name else 'address',
            'what': LOCKOUT_KINDS.get(base, base), 'base': base,
            'words': info.get('what') or 'wrong passwords',
            'fails': len(fails), 'limit': limit, 'locked': locked,
            'until': (fails[0] + span) if locked else None,
            'forgets': fails[-1] + span, 'first': fails[0], 'last': fails[-1],
            'others': list(info.get('others') or [])})
    rows.sort(key=lambda r: (not r['locked'], -r['last']))
    return rows


def lockouts_clear(d, which=None):
    """Forget counts: which is a list of (kind, who); None - every one."""
    n = 0
    with ApiHandler.THROTTLE_LOCK:
        keys = list(d.login_fails) if which is None else \
            [tuple(k) for k in which if tuple(k) in d.login_fails]
        for k in keys:
            if d.login_fails.pop(k, None):
                n += 1
            d.login_info.pop(k, None)
    LOCKOUTS_SENT['sig'] = None
    return n


def lockouts_publish(d, force=False):
    rows = lockouts_view(d)
    sig = json.dumps([(r['kind'], r['who'], r['fails'], r['locked']) for r in rows])
    now = time.time()
    if not force and sig == LOCKOUTS_SENT['sig'] and now - LOCKOUTS_SENT['at'] < 60:
        return rows
    many = bool(CONFIG.get('ha_mode')) or len(d.cluster_nodes()) > 1
    if many:
        d.store.set_meta('lockouts:' + node_name(), json.dumps({'at': now, 'rows': rows}))
    LOCKOUTS_SENT.update(sig=sig, at=now)
    return rows


def lockouts_tick(d):
    """Asked by the other node's pages to clear something here? Then the list."""
    key = 'lockouts:ask:' + node_name()
    raw = d.store.get_meta(key)
    if raw:
        d.store.db.run('DELETE FROM meta WHERE k = ?', (key,))
        try:
            asks = json.loads(raw)
        except ValueError:
            asks = []
        for a in asks if isinstance(asks, list) else []:
            if not isinstance(a, dict):
                continue
            n = lockouts_clear(d, None if a.get('all') else [a.get('key') or []])
            lockouts_said(d.store, a, n)
        lockouts_publish(d, force=True)
        return
    lockouts_publish(d)


def lockouts_said(store, a, n):
    by = str(a.get('by') or '?')
    if a.get('all'):
        words = '%s cleared every lockout and count of wrong attempts on %s (%d)' % (
            by, node_name(), n)
    else:
        k = a.get('key') or ['', '']
        base = str(k[0])[:-5] if str(k[0]).endswith('-name') else str(k[0])
        words = '%s cleared the count of wrong attempts of %s %s (%s) on %s' % (
            by, 'the name' if str(k[0]).endswith('-name') else 'the address', k[1],
            LOCKOUT_KINDS.get(base, base), node_name())
    store.add_event('sign-ins', words, 'warn', who=by)


def lockouts_shared(store):
    """What the database holds for every node (1.0.116): the codes sent to a
    person within the window, and tokens locked after wrong codes."""
    t = time.time()
    rows = []
    span = 60 * int(CONFIG.get('code_send_window_min') or 15)
    limit = int(CONFIG.get('code_send_max') or 5)
    per = {}
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'codesent:%'"):
        try:
            per.setdefault(node_key_name('codesent', r['k']), []).extend(
                float(x) for x in json.loads(r['v'] or '[]'))
        except (ValueError, TypeError):
            continue
    for who, times in per.items():          # every node's row of a person together (1.0.146)
        times = sorted(x for x in times if t - x < span)
        if not times:
            continue
        locked = len(times) >= limit
        rows.append({'kind': 'codes-sent', 'who': who, 'by': 'name',
                     'what': LOCKOUT_KINDS['codes-sent'], 'base': 'codes-sent',
                     'words': 'codes sent', 'fails': len(times), 'limit': limit,
                     'locked': locked,
                     'until': (times[len(times) - limit] + span) if locked else None,
                     'forgets': times[-1] + span, 'first': times[0], 'last': times[-1],
                     'others': []})
    after = int(CONFIG.get('lockout_after') or 0)
    for r in store.db.rows('SELECT name, locked_until, failures, fail_times, last_from FROM '
                           'tokens WHERE locked_until > ?', (t,)):
        try:
            fails = [float(x) for x in json.loads(r['fail_times'] or '[]')]
        except (ValueError, TypeError):
            fails = []
        until = float(r['locked_until'])
        rows.append({'kind': 'token-locked', 'who': r['name'], 'by': 'token',
                     'what': LOCKOUT_KINDS['token-locked'], 'base': 'token-locked',
                     'words': 'wrong codes', 'fails': int(r['failures'] or 0),
                     'limit': after, 'locked': True, 'until': until, 'forgets': until,
                     'first': min(fails) if fails else until, 'last': max(fails) if fails
                     else until, 'others': []})
    rows.sort(key=lambda r: (not r['locked'], -r['last']))
    return rows


def lockouts_shared_clear(store, kind, who, by):
    if kind == 'codes-sent':
        n = node_key_drop(store, 'codesent', who)
        store.add_event('sign-ins', '%s cleared the count of codes sent to %s' % (by, who),
                        'warn', who=by)
        return n
    if kind == 'token-locked':
        if not store.token(who):
            return 0
        store.token_write(who, {'failures': 0, 'fail_times': '[]', 'locked_until': None})
        node_key_drop(store, 'scratchguard', who)
        store.add_event('tokens', '%s let %s try again at once' % (by, who), who=by)
        return 1
    return 0


@route('GET', '/api/lockouts')
def _lockouts(h):
    h.me('fulladmin')
    me = node_name()
    out = [{'node': me, 'me': True, 'fresh': True, 'rows': lockouts_view(h.d)}]
    now = time.time()
    for n in h.d.cluster_nodes():
        if n == me:
            continue
        try:
            got = json.loads(h.store.get_meta('lockouts:' + n) or '{}')
        except ValueError:
            got = {}
        rows = [r for r in (got.get('rows') or []) if float(r.get('forgets') or 0) > now]
        for r in rows:
            if r.get('locked') and float(r.get('until') or 0) <= now:
                r['locked'] = False
        out.append({'node': n, 'me': False, 'fresh': now - float(got.get('at') or 0) < 120,
                    'at': got.get('at'), 'rows': rows})
    out.append({'node': '*', 'me': False, 'fresh': True, 'shared': True,
                'rows': lockouts_shared(h.store)})
    return {'nodes': out, 'now': now, 'cluster': len(out) > 2}


@route('POST', '/api/lockouts')
def _lockouts_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    nodes = [node_name()] + [n for n in h.d.cluster_nodes() if n != node_name()]
    if act == 'clear' and str(b.get('kind') or '') in ('codes-sent', 'token-locked'):
        n = lockouts_shared_clear(h.store, str(b.get('kind')), norm_name(b.get('who') or ''),
                                  s['name'])
        if not n:
            raise ApiError(404, 'that is not counted any more')
        return {'message': 'cleared', 'told': []}
    if act == 'clear_all':
        want = nodes
        ask = {'all': 1, 'by': s['name']}
        shared = lockouts_shared(h.store)
        for r in shared:
            lockouts_shared_clear(h.store, r['kind'], r['who'], s['name'])
    elif act == 'clear':
        kind, who = str(b.get('kind') or ''), str(b.get('who') or '')
        base = kind[:-5] if kind.endswith('-name') else kind
        if base not in LOCKOUT_KINDS or not who:
            raise ApiError(400, 'which lockout?')
        node = str(b.get('node') or node_name())
        if node not in nodes:
            raise ApiError(400, 'there is no node %s' % node)
        want = [node]
        ask = {'key': [kind, who], 'by': s['name']}
    else:
        raise ApiError(400, 'no such thing to do')
    told = []
    for n in want:
        if n == node_name():
            got = lockouts_clear(h.d, None if ask.get('all') else [ask['key']])
            lockouts_said(h.store, ask, got)
            lockouts_publish(h.d, force=True)
        else:
            # The other node clears it within five seconds.
            with THROTTLE_GUARD:
                try:
                    pending = json.loads(h.store.get_meta('lockouts:ask:' + n) or '[]')
                except ValueError:
                    pending = []
                pending = (pending if isinstance(pending, list) else [])[-50:] + [ask]
                h.store.set_meta('lockouts:ask:' + n, json.dumps(pending))
            told.append(n)
    return {'message': 'cleared', 'told': told}


@route('GET', '/api/health')
def _health(h):
    """Asked without the API token, so it says only what the pages need
    before anybody is signed in: that the database opens, whether any
    account exists at all (the sign-in page says how to make the first one
    otherwise), the language and this node's name. No version, no count."""
    # The database asked at most once a second (1.0.57): /healthz is public,
    # and every load balancer, monitor and the web address's own check ask it.
    got = HEALTH_SEEN.get('db')
    if got and time.time() - got[0] < 1.0:
        users, db_ok, maint = got[1]
    else:
        try:
            users = 1 if h.store.db.value('SELECT 1 FROM accounts LIMIT 1') else 0
            db_ok = True
        except Exception:
            users, db_ok = 0, False
        try:
            maint = bool(maintenance_now(h.store).get('on'))
        except Exception:                               # noqa: BLE001
            maint = False
        HEALTH_SEEN['db'] = (time.time(), (users, db_ok, maint))
    out = {'ok': True, 'users': users, 'database': {'ok': db_ok},
           'lang': CONFIG.get('ui_lang') or 'cs', 'node': node_name(),
           'maintenance': maint,
           # For a balancer of RADIUS and for monitoring (1.0.47): whether
           # RADIUS listens, and - asked for - whether replication runs.
           'radius': bool(getattr(getattr(h.d, 'radius', None), 'bound', None))}
    if h.arg('check') == 'all' and CONFIG.get('ha_mode') == 'replicated':
        try:
            rep = ha_repl_state(h.store)
            out['replication'] = {'ok': bool(rep.get('healthy')), 'lost': bool(rep.get('lost'))}
        except Exception:                               # noqa: BLE001
            out['replication'] = {'ok': False}
    return out


DUMMY_PW_HASH = password_hash(secrets.token_urlsafe(18))

ROLE_GROUP_KEYS = (('admin_group_full', 'fulladmin'), ('admin_group_token', 'tokenadmin'),
                   ('admin_group_readonly', 'readonly'))


def admin_role_for(have, ad=None):
    """Which role these groups earn - full administrator first - or None.
    Only a group named for a role lets anybody in (1.0.33): with none named,
    nobody from the directory gets in at all. Before, being anywhere in the
    directory was then enough to read every log and every token."""
    for key, role in ROLE_GROUP_KEYS:
        wanted = dn_list(CONFIG.get(key))
        if wanted and group_matches(wanted, have, ad):
            return role
    return None


def admin_name_parts(name):
    """`DOMAIN\\novak`, `novak@example.cz` or `novak`, as the directory is asked."""
    name = name.strip()
    if '\\' in name:
        name = name.split('\\', 1)[1]
    return name, ('upn' if '@' in name else 'sam')


def admin_ask_directory(h, name, password):
    """One sign-in, asked of the directory in `admin_directory`, and what it
    earns here. Nothing is made and no session is opened."""
    ad = h.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
    if not ad:
        return None
    who, how = admin_name_parts(name)
    try:
        entry = ad.find_user(who, how)
    except LdapUnreachable as e:
        raise ApiError(503, 'the directory cannot be reached', str(e))
    if not entry:
        return {'ok': False, 'missing': True, 'said': 'the directory has nobody called %s' % who,
                'directory': ad.name}
    if entry_unusable(entry):
        return {'ok': False, 'said': 'the account may not sign in: %s' % entry_unusable(entry),
                'dn': entry['dn'], 'directory': ad.name}
    try:
        ad.password_ok(entry, password)
    except LdapUnreachable as e:
        raise ApiError(503, 'the directory cannot be reached', str(e))
    except LdapError as e:
        return {'ok': False, 'said': str(e) or 'the password is not right', 'dn': entry['dn'],
                'directory': ad.name}
    have = ad.groups_of(entry, True)
    return {'ok': True, 'name': who, 'role': admin_role_for(have, ad), 'dn': entry['dn'],
            'display': entry.get('display') or '', 'directory': ad.name, 'entry': entry,
            'groups': sorted({cn for _, cn in have}, key=str.lower)}


def admin_from_directory(h, name, password):
    """An administrator signed in against the directory named in
    `admin_directory`: the role is that of the first group they are in."""
    said = admin_ask_directory(h, name, password)
    if said is None:
        return None
    if not said['ok']:
        # What the directory said goes into the log only: the answer must not
        # tell the caller whether the name exists there.
        h.store.add_event('sign-ins', 'the directory did not sign %s in from %s: %s'
                          % (name, h.client_ip(), said.get('said') or '?'), 'warn')
        raise ApiError(401, 'the name or the password is not right')
    if not said['role']:
        # Said as a wrong password is (1.0.101): a 403 told anybody trying
        # names and passwords that this one was right.
        h.store.add_event('sign-ins', 'the directory knows %s, and none of the groups given a '
                          'role here holds them (from %s)' % (said['name'], h.client_ip()), 'warn')
        raise ApiError(401, 'the name or the password is not right')
    name, role, entry = said['name'], said['role'], said['entry']
    # One person, one account, whatever way the name was typed (1.0.101):
    # novak, novak@corp.cz and CORP\novak are the same entry in the
    # directory - found by its DN. Kept under their typed name, each
    # spelling was an account of its own, and switching one off left the
    # others to sign in with.
    same = [a for a in h.store.db.rows("SELECT * FROM accounts WHERE source = 'directory'")
            if str(a.get('dn') or '').lower() == str(entry['dn']).lower()]
    off = [a for a in same if a.get('disabled')]
    if off:
        return off[0]
    if same:
        name = same[0]['name']
    acc = h.store.account(name)
    groups = '; '.join(said['groups'])[:2000]
    if acc:
        if acc.get('source') != 'directory':
            return None
        h.store.set_account(name, role=role, display=entry.get('display') or '',
                            dn=entry['dn'], group_list=groups)
    else:
        h.store.add_account(name, role, None, source='directory',
                            note='signed in from %s' % said['directory'],
                            display=entry.get('display') or '', dn=entry['dn'], groups=groups)
    return h.store.account(name)


@route('POST', '/api/auth/login')
def _login(h):
    b = h.body()
    # No account has a longer name (1.0.146): megabytes typed went into the log.
    name = str(b.get('name') or '').strip()[:190]
    password = str(b.get('password') or '')
    key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),
                     int(CONFIG.get('login_wait_min') or 15), name=name)
    acc = h.store.account(name) or (h.store.account(admin_name_parts(name)[0])
                                    if CONFIG.get('admin_directory') else None)
    ok = None
    if acc and acc.get('source') != 'directory':
        ok = acc if (acc.get('pw') and password_ok(password, acc['pw'])) else None
    elif not acc and not CONFIG.get('admin_directory'):
        # As long as for a name that is there (1.0.33): how long the answer
        # took told which names exist.
        password_ok(password, DUMMY_PW_HASH)
    elif CONFIG.get('admin_directory') and password:
        if not acc:
            # The time of a password hash spent here too (1.0.101): a wrong
            # password of a local account took a hash longer than a name that
            # is not there, which went straight to the directory.
            password_ok(password, DUMMY_PW_HASH)
        try:
            ok = admin_from_directory(h, name, password)
        except ApiError as e:
            h.failed(key)
            h.store.add_event('sign-ins', '%s could not sign in from %s: %s'
                              % (name, h.client_ip(), e), 'warn')
            raise
    if not ok:
        h.failed(key)
        h.store.add_event('sign-ins', 'a wrong password for %s from %s'
                          % (name or '(nobody)', h.client_ip()), 'warn')
        raise ApiError(401, 'the name or the password is not right')
    if ok.get('disabled'):
        # Said as a wrong password is, and counted as one (1.0.57): the
        # difference told that the password was right.
        h.failed(key)
        h.store.add_event('sign-ins', '%s, switched off, tried to sign in from %s'
                          % (ok['name'], h.client_ip()), 'warn')
        raise ApiError(401, 'the name or the password is not right')
    # The second step, when it is asked for (1.0.125): the sign-in is made,
    # and may do nothing but give it.
    stage = mfa_stage(h.store, ok['name']) if CONFIG.get('admin_2fa') else ''
    token = h.store.session_new('admin', ok['name'], ok['role'], h.client_ip(),
                                CONFIG.get('session_hours') or 12,
                                data={'mfa': stage} if stage else None)
    h.store.set_account(ok['name'], last_in=time.time(), last_from=h.client_ip())
    h.store.add_event('sign-ins', '%s signed in from %s%s' % (
        ok['name'], h.client_ip(), {'check': ' - the second step to give',
                                     'enrol': ' - the second step to set up'}.get(stage, '')),
                      who=ok['name'])
    return {'token': token, 'who': {'name': ok['name'], 'role': ok['role'] if not stage else ''},
            'must_change': bool(ok.get('must_change')), 'mfa': stage}


# ---- editing the columns, switched on for one sign-in --------------------------
# Held here in memory, as on isemon: signing out, a sign-in running out and a
# restart of the service all switch it off again. Off, a layout already kept
# is drawn just the same; nothing can be changed.
COLS_EDITING = {}
COLS_EDITING_LOCK = threading.Lock()


def _cols_key(token):
    return hashlib.sha256(str(token or '').encode('utf-8', 'replace')).hexdigest()


# Kept with the sign-in's own row since 1.0.13 - in memory it was this node's
# alone, and behind a load balancer the next request found it switched off.
def _session_row(token):
    store = HA_STORE.get('store')
    if not store or not token:
        return None, None
    row = store.db.row('SELECT id, data FROM sessions WHERE token_hash = ?',
                       (hashlib.sha256(str(token).encode()).hexdigest(),))
    if not row:
        return store, None
    try:
        row['data'] = json.loads(row.get('data') or '{}')
    except ValueError:
        row['data'] = {}
    return store, row


def cols_editing(token):
    _, row = _session_row(token)
    return bool(row and row['data'].get('cols_edit'))


def set_cols_editing(token, on):
    store, row = _session_row(token)
    if not row:
        return False
    data = row['data']
    if on:
        data['cols_edit'] = 1
    else:
        data.pop('cols_edit', None)
    store.session_set_data(row['id'], data)
    return bool(on)


SETTINGS_FILE_KIND = 'otp-user-settings'


@route('POST', '/api/auth/logout')
def _logout(h):
    token = h.headers.get('X-Otp-Session')
    h.store.session_end(token)
    set_cols_editing(token, False)
    return {}


@route('POST', '/api/auth/columns')
def _columns(h):
    """Anybody signed in, a read-only account as well: this is how the page
    looks to that one person and changes nothing anybody else sees."""
    s = h.me()
    b = h.body()
    token = h.headers.get('X-Otp-Session') or ''
    if 'edit' in b:
        set_cols_editing(token, bool(b.get('edit')))
        if 'cols' not in b:
            return {'edit': cols_editing(token)}
    reset = bool(b.get('reset'))
    # Putting them back is always allowed; changing them only with the switch
    # on, so a page that misbehaves cannot rearrange somebody's tables while
    # they are only reading them.
    if not reset and not cols_editing(token):
        raise ApiError(409, 'switch on "Edit the columns" under your name first: the columns '
                       'are not being edited from this sign-in')
    try:
        kept = h.store.put_user_cols(s['name'], {} if reset else (b.get('cols') or {}))
    except ValueError as e:
        raise ApiError(400, str(e))
    if reset:
        h.store.add_event('accounts', '%s put the columns of every table back as they come'
                          % s['name'], who=s['name'])
    return {'tables': len(kept), 'edit': cols_editing(token)}


@route('GET', '/api/auth/settings')
def _my_settings(h):
    """What a person has set for themselves on the page, as one object that
    can be saved to a file and read back - here or on another machine. Never
    the password, the role or anything else about the account."""
    s = h.me()
    return {'name': s['name'], 'version': __version__, 'kind': SETTINGS_FILE_KIND,
            'settings': {'columns': h.store.user_cols(s['name']),
                         'prefs': h.store.user_prefs(s['name'])}}


@route('POST', '/api/auth/settings')
def _my_settings_put(h):
    s = h.me()
    b = h.body()
    got = b.get('settings')
    if not isinstance(got, dict):
        raise ApiError(400, 'that is not a file of settings: there is no "settings" in it')
    known = ('columns', 'prefs')
    ignored = sorted(k for k in got if k not in known)
    # Every section checked before any of them is written.
    for section, check, words in (('columns', h.store.clean_cols, 'the columns'),
                                  ('prefs', h.store.clean_prefs, 'the choices')):
        if section in got:
            try:
                check(got[section] if got[section] is not None else {})
            except (ValueError, TypeError, AttributeError) as e:
                raise ApiError(400, '%s in that file: %s' % (words, e))
    took = {}
    if 'columns' in got:
        took['columns'] = len(h.store.put_user_cols(s['name'], got['columns'] or {}))
    if 'prefs' in got:
        took['prefs'] = len(h.store.put_user_prefs(s['name'], got['prefs'] or {}))
    if not took:
        raise ApiError(400, 'nothing in that file is a setting this version keeps'
                       + (' (it holds: %s)' % ', '.join(ignored) if ignored else ''))
    h.store.add_event('accounts', '%s read their own settings back from a file (%s)'
                      % (s['name'], ', '.join('%s: %d' % kv for kv in took.items())),
                      who=s['name'])
    return {'took': took, 'ignored': ignored}


@route('GET', '/api/auth/whoami')
def _whoami(h):
    s = h.session('admin')
    if not s:
        return {'who': None}
    acc = h.store.account(s['name'])
    if not acc or acc.get('disabled'):
        return {'who': None}
    if mfa_pending(s):
        # No role until the second step is given: the pages that ask who it
        # is (a database or a package sent) refuse it.
        return {'who': {'name': acc['name'], 'role': '', 'display': acc.get('display') or '',
                        'mfa': mfa_pending(s)}}
    try:
        prefs = json.loads(acc.get('prefs') or '{}')
    except ValueError:
        prefs = {}
    # The page is drawn with the person's own layout of the tables from the
    # first frame, rather than as it comes and then again.
    return {'idle_min': int(CONFIG.get('session_idle_min') or 120),
            'who': {'name': acc['name'], 'role': acc['role'], 'source': acc.get('source'),
                    'display': acc.get('display') or '', 'must_change': bool(
                        acc.get('must_change')), 'prefs': prefs,
                    'cols': h.store.user_cols(acc['name']),
                    'cols_edit': cols_editing(h.headers.get('X-Otp-Session') or '')}}


@route('POST', '/api/auth/password')
def _password(h):
    s = h.me()
    b = h.body()
    acc = s['account']
    if acc.get('source') == 'directory':
        raise ApiError(400, 'this account signs in with its directory password, which is '
                       'changed in the directory')
    # Counted as sign-ins are (1.0.57): a session left open was a way to
    # guess the password without end.
    key = h.throttle('password', int(CONFIG.get('login_tries') or 5), 5, name=acc['name'])
    if not password_ok(str(b.get('old') or ''), acc.get('pw')):
        h.failed(key)
        raise ApiError(400, 'the password you have now is not right')
    h.store.set_account(acc['name'], password=str(b.get('new') or ''), must_change=0)
    # Every other sign-in with the old password ends (1.0.33).
    h.store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ? AND token_hash <> ?',
                   ('admin', acc['name'].lower(), hashlib.sha256(
                       str(h.headers.get('X-Otp-Session') or '').encode()).hexdigest()))
    h.store.add_event('accounts', '%s changed their own password' % acc['name'],
                      who=acc['name'])
    # The first password, written down by the installer, is no use to anybody
    # now - and stays readable no longer (1.0.33).
    first = STATE_DIR / 'first-login.txt'
    try:
        if first.exists() and ('name: %s\n' % acc['name']) in first.read_text():
            first.unlink()
    except OSError:
        pass
    return {'message': 'the password is changed'}


@route('POST', '/api/auth/prefs')
def _prefs(h):
    s = h.me()
    acc = s['account']
    try:
        prefs = json.loads(acc.get('prefs') or '{}')
    except ValueError:
        prefs = {}
    b = h.body()
    if 'lang' in b:
        if str(b['lang']) not in ('cs', 'en'):
            raise ApiError(400, 'no such language here')
        prefs['lang'] = str(b['lang'])
    h.store.set_account(acc['name'], prefs=json.dumps(prefs))
    return {'prefs': prefs}


# ---- what it is doing --------------------------------------------------------------
@route('GET', '/api/status')
def _status(h):
    s = h.me()
    out = h.d.status()
    out['role'] = s['role']
    # The outgoing mail at a glance (1.0.95): what waits and what failed,
    # for the badge beside Mail. Counted at most every 10 s.
    now = time.time()
    if now - MAILQ_COUNT_CACHE[0] > 10:
        try:
            MAILQ_COUNT_CACHE[1] = mailq_counts(h.store)
        except Exception:                               # noqa: BLE001
            pass
        MAILQ_COUNT_CACHE[0] = now
    out['mailq'] = MAILQ_COUNT_CACHE[1]
    return out


MAILQ_COUNT_CACHE = [0.0, {}]
MAILQ_SEARCH_COLS = ('to_addr', 'state', 'kind', 'name', 'by_who', 'said', 'subject', 'tries',
                     'node')
MAILQ_SEARCH_TABLE = ('CREATE TABLE t (i INTEGER, to_addr TEXT, state TEXT, kind TEXT, '
                      'name TEXT, by_who TEXT, said TEXT, subject TEXT, tries INTEGER, node TEXT)')


def mailq_search_row(r):
    return {'to_addr': ' '.join(r.get('to') or []), 'state': r.get('state') or '',
            'kind': r.get('kind') or '', 'name': r.get('name') or '', 'by_who': r.get('by') or '',
            'said': r.get('said') or '', 'subject': mailq_subject_kept(r.get('subject'), r.get('kind')),
            'tries': int(r.get('tries') or 0), 'node': r.get('node') or ''}


@route('GET', '/api/software')
def _software(h):
    """What every node runs on (1.0.99): this one asked now, the others as
    their last heartbeat said."""
    h.me()
    me = node_name()
    out = [{'name': me, 'me': True, 'alive': True, 'software': software_info(h.store)}]
    try:
        for n in ha_nodes(h.store):
            if n['name'] != me:
                out.append({'name': n['name'], 'me': False, 'alive': bool(n.get('alive')),
                            'age': int(n.get('age') or 0), 'software': n.get('software') or {}})
    except Exception:                                   # noqa: BLE001
        pass
    return {'nodes': out}


@route('GET', '/api/mailq')
def _mailq(h):
    """The outgoing mail (1.0.95): what waits, what went, what failed."""
    h.me()
    q = h.arg('q')
    state = h.arg('state')
    every = mailq_all(h.store)
    rows = [r for r in every
            if (not state or r.get('state') == state or
                (state == 'open' and r.get('state') in ('waiting', 'sending', 'failed')))]
    # The same words as every list (1.0.96): fields, values, OR, NOT, ~.
    try:
        keep = memory_search('mailq', MAILQ_SEARCH_TABLE, MAILQ_SEARCH_COLS,
                             [mailq_search_row(r) for r in rows], q) if q.strip() else None
    except ListQueryError as e:
        return {'rows': [], 'total': 0, 'q_error': str(e),
                'counts': {k: 0 for k in MAILQ_STATES}, 'node': node_name(),
                'retry_hours': int(CONFIG.get('mail_retry_hours') or 24),
                'keep_days': int(CONFIG.get('mail_keep_days') or 14),
                'mode': CONFIG.get('mail_mode') or 'off'}
    if keep is not None:
        rows = [rows[i] for i in sorted(keep)]
    limit, offset = h.num('limit', 100, 1, 1000), h.num('offset', 0)
    counts = collections.Counter(r.get('state') for r in every)
    MAILQ_COUNT_CACHE[0] = 0
    return {'rows': [mailq_view(r) for r in rows[offset:offset + limit]], 'total': len(rows),
            'counts': {k: int(counts.get(k, 0)) for k in MAILQ_STATES},
            'node': node_name(), 'retry_hours': int(CONFIG.get('mail_retry_hours') or 24),
            'keep_days': int(CONFIG.get('mail_keep_days') or 14),
            'mode': CONFIG.get('mail_mode') or 'off'}


@route('GET', '/api/mailq/one')
def _mailq_one(h):
    h.me()
    rec, _raw = mailq_read(h.store, h.arg('id'))
    if not rec:
        raise ApiError(404, 'that mail is not in the outgoing mail any more')
    out = mailq_view(rec)
    out['history'] = rec.get('history') or []
    out['steps'] = rec.get('steps') or []
    out['has_body'] = bool(h.store.get_meta(MAILB_PREFIX + h.arg('id')))
    return out


@route('POST', '/api/mailq')
def _mailq_do(h):
    s = h.me('tokenadmin')
    b = h.body()
    act = str(b.get('action') or '')
    ids = b.get('ids') or []
    if not isinstance(ids, list) or not all(isinstance(x, str) and
                                            re.fullmatch(r'[0-9]{13}-[0-9a-f]{8}', x)
                                            for x in ids):
        raise ApiError(400, 'ids is a list of the mails\' own ids')
    if act in ('retry_all', 'drop_sent', 'drop_failed'):
        want = {'retry_all': ('waiting', 'failed'), 'drop_sent': ('sent',),
                'drop_failed': ('failed', 'expired')}[act]
        ids = [r['qid'] for r in mailq_all(h.store) if r.get('state') in want]
        act = 'retry' if act == 'retry_all' else 'drop'
    MAILQ_COUNT_CACHE[0] = 0
    if act == 'retry':
        if (CONFIG.get('mail_mode') or 'off') == 'off':
            raise ApiError(409, 'sending mail is switched off - Settings → Mail')
        done, skipped = mailq_retry(h.store, ids, s['name'])
        codes = MAILQ_RETRY_WHY.get('code', 0)
        rest = len(skipped) - codes
        msg = '%d mail(s) are being sent again now' % len(done)
        if codes:
            # Said for what it is (1.0.103): a code past its time.
            msg += ' - %d code(s) to sign in with are past their time and no good any more' % codes
        if rest:
            msg += ' - %d could not be (sent already, or what they held is gone)' % rest
        return {'done': len(done), 'skipped': len(skipped), 'message': msg}
    if act == 'drop':
        n = mailq_drop(h.store, ids, s['name'])
        return {'done': n, 'message': '%d mail(s) taken out of the outgoing mail' % n}
    raise ApiError(400, 'no such thing to do with the outgoing mail')


@route('GET', '/api/dashboard')
def _dashboard(h):
    h.me()
    return h.store.overview(h.num('hours', 24, 1, 24 * 400),
                            since=h.num('since', 0, 0, 10 ** 11) or None,
                            until=h.num('until', 0, 0, 10 ** 11) or None)


def list_query(listname, text):
    """(query, error words): what a search box asked, read as fields."""
    try:
        return ListQuery(listname, text), ''
    except ListQueryError as e:
        return None, str(e)


@route('GET', '/api/suggest')
def _suggest(h):
    """The fields of one list, or what one of them holds - what the search
    box over the list offers as somebody types (1.0.19)."""
    h.me()
    name = h.arg('list')
    if name not in LIST_FIELDS:
        raise ApiError(400, 'no such list')
    field = h.arg('field').lower()
    if not field:
        said = LIST_FIELD_SAYS.get(name) or LIST_FIELD_SAYS.get('radius')
        return {'fields': [list(f) for f in said]}
    hours = h.num('hours', 0, 0, 24 * 3650)
    # What the log held in the last 90 days when no time is given (1.0.101):
    # the whole log counted again on every key pressed was seconds a time.
    since = time.time() - (hours or 24 * 90) * 3600 if name in ('radius', 'otp', 'events') \
        else (time.time() - hours * 3600 if hours else 0)
    typed = h.arg('typed')[:120]
    if name == 'mailq':
        # Its rows are in no table: what the field holds, counted here.
        col = (LIST_FIELDS['mailq'].get(field) or ('', ''))[0]
        got = collections.Counter()
        for r in mailq_all(h.store):
            v = str(mailq_search_row(r).get(col) or '')
            for one in (v.split() if col == 'to_addr' else [v]):
                if one and (not typed or typed.strip('*').lower() in one.lower()):
                    got[one] += 1
        return {'values': [{'val': v, 'n': n} for v, n in got.most_common(15)]}
    if name == 'radius':
        # The Log is two lists in one: a field either of them holds.
        got = h.reader.list_values('radius', field, typed, since)
        more = h.reader.list_values('otp', field, typed, since)
        seen = {g['val'].lower(): g for g in got}
        for m in more:
            if m['val'].lower() in seen:
                seen[m['val'].lower()]['n'] += m['n']
            else:
                got.append(m)
        got.sort(key=lambda x: -x['n'])
        return {'values': got[:15]}
    return {'values': h.reader.list_values(name, field, typed, since)}


@route('GET', '/api/radius')
def _radius(h):
    h.me()
    lq, bad = list_query('radius', h.arg('q'))
    if bad:
        return {'rows': [], 'total': 0, 'q_error': bad, 'clients': []}
    rows, total = h.reader.radius_rows(
        hours=h.num('hours', 24, 1, 24 * 3650), q=lq.words, extra=(lq.sql, lq.args),
        result=h.arg('result'),
        client=h.arg('client'), limit=h.num('limit', 100, 1, 1000),
        offset=h.num('offset', 0), sort=h.arg('sort', 'ts'),
        desc=h.arg('desc', '1') != '0', user=h.arg('user'))
    return {'rows': rows, 'total': total,
            'clients': [c['name'] for c in h.store.clients()]}


@route('GET', '/api/activity')
def _activity(h):
    """The one log of the pages: every RADIUS request - with what the token
    said about its code - and every code checked anywhere else (the
    enrolment pages, a test, the command line), newest first."""
    h.me()
    hours = h.num('hours', 24, 1, 24 * 3650)
    q, kind, result = h.arg('q'), h.arg('kind'), h.arg('result')
    client = h.arg('client')
    limit, offset = h.num('limit', 100, 1, 1000), h.num('offset', 0, 0, 10 ** 9)
    if offset > 20000:
        # Said, not quietly turned into page 200 again (1.0.57).
        raise ApiError(400, 'that is further back than these pages go: narrow the time window '
                            'or the search')
    want = offset + limit
    out, total = [], 0
    rq, bad = list_query('radius', q)
    oq, bad2 = list_query('otp', q)
    if bad or bad2:
        return {'rows': [], 'total': 0, 'q_error': bad or bad2,
                'clients': [c['name'] for c in h.store.clients()]}
    # One hour of the chart, counted and paged here (1.0.36): picked out of
    # the first page in the browser, the count was the day's, and an older
    # hour came out empty.
    since, until = h.num('since', 0, 0, 10 ** 11), h.num('until', 0, 0, 10 ** 11)

    def span(sql, args):
        parts, args = ([sql] if sql else []), list(args or [])
        if since:
            parts.append('ts >= ?')
            args.append(since)
        if until:
            parts.append('ts < ?')
            args.append(until)
        return ' AND '.join('(%s)' % x for x in parts), args
    rq.sql, rq.args = span(rq.sql, rq.args)
    oq.sql, oq.args = span(oq.sql, oq.args)
    if kind != 'codes':
        rows, n = h.reader.radius_rows(hours=hours, q=rq.words, extra=(rq.sql, rq.args),
                                      result=result, client=client, limit=want, offset=0)
        total += n
        for r in rows:
            out.append({'kind': 'radius', 'id': r['id'], 'ts': r['ts'], 'name': r.get('username'),
                        'realm': r.get('realm'), 'result': r.get('result'),
                        'why': r.get('reason') or r.get('otp') or '',
                        'code': r.get('otp') or '', 'source': r.get('client') or '',
                        'from': r.get('calling') or r.get('src') or '',
                        'device': r.get('device') or '', 'ms': r.get('took_ms'),
                        'node': r.get('node') or ''})
    if kind != 'radius' and not client and result in ('', 'access', 'accept', 'reject'):
        ok = None if result in ('', 'access') else result == 'accept'
        rows, n = h.reader.otp_rows(hours=hours, q=oq.words, ok=ok, limit=want, offset=0,
                                   not_how='radius', extra=(oq.sql, oq.args))
        total += n
        for r in rows:
            out.append({'kind': 'code', 'id': r['id'], 'ts': r['ts'], 'name': r.get('name'),
                        'result': 'accept' if r.get('ok') else 'reject',
                        'why': r.get('said') or '', 'code': r.get('said') or '',
                        'source': r.get('how') or '', 'from': r.get('src') or '',
                        'device': '', 'ms': None, 'rid': r.get('rid') or '',
                        'node': r.get('node') or ''})
    out.sort(key=lambda x: (x['ts'] or 0, x['id']), reverse=True)
    return {'rows': out[offset:offset + limit], 'total': min(total, 20000 + limit),
            'more_than': total > 20000 + limit,
            'clients': [c['name'] for c in h.store.clients()]}


@route('GET', '/api/radius/row')
def _radius_row(h):
    h.me()
    r = h.store.radius_row(h.num('id', 0))
    if not r:
        raise ApiError(404, 'there is no such request')
    return {'row': r}


@route('GET', '/api/otp')
def _otp(h):
    h.me()
    ok = h.arg('ok')
    rows, total = h.store.otp_rows(hours=h.num('hours', 24, 1, 24 * 3650), q=h.arg('q'),
                                   ok=None if ok == '' else ok == '1',
                                   limit=h.num('limit', 100, 1, 1000),
                                   offset=h.num('offset', 0), name=h.arg('name'))
    return {'rows': rows, 'total': total}


# ---- the tokens -----------------------------------------------------------------------
@route('GET', '/api/tokens')
def _tokens(h):
    h.me()
    lq, bad = list_query('tokens', h.arg('q'))
    if bad:
        return {'rows': [], 'total': 0, 'q_error': bad, 'counts': h.store.token_counts()}
    rows, total = h.store.tokens(q=lq.words, extra=(lq.sql, lq.args), state=h.arg('state'),
                                 limit=h.num('limit', 100, 1, 5000), offset=h.num('offset', 0),
                                 sort=h.arg('sort', 'name'), desc=h.arg('desc') == '1',
                                 kind=h.arg('kind'))
    for r in rows:
        r['last_client'] = h.store.client_name_of(r)
    # What "as the setting" is, for the table to show (1.0.85).
    return {'rows': rows, 'total': total, 'counts': h.store.token_counts(),
            'lang_default': code_lang(),
            'fmt_default': 'text' if CONFIG.get('code_mail_fmt') == 'text' else 'html'}


def totp_file_text(tok):
    """One token as the file totpcgi (google-authenticator) keeps for it:
    the key, its options, the recovery codes not used yet - what the import
    reads back (1.0.20)."""
    secret = unseal_secret(tok.get('secret') or '', token_bind(tok.get('name')))
    if not secret:
        return None
    lines = [secret]
    tries = int(CONFIG.get('rate_limit_tries') or 0)
    if tries:
        lines.append('" RATE_LIMIT %d %d' % (tries, int(CONFIG.get('rate_limit_s') or 30)))
    w = tok.get('window_steps')
    w = Tokens.window(tok)     # the same as the check uses: 0 is 0 (1.0.36)
    lines.append('" WINDOW_SIZE %d' % (w * 2 + 1))
    if CONFIG.get('totp_disallow_reuse'):
        lines.append('" DISALLOW_REUSE')
    lines.append('" TOTP_AUTH')
    for c in codes_open(tok) or []:
        if isinstance(c, dict):
            if not c.get('used'):
                lines.append(str(c.get('c')))
        else:
            lines.append(str(c))
    return '\n'.join(lines) + '\n'


@route('GET', '/api/tokens/export')
def _tokens_export(h):
    """Tokens as totpcgi files: one token as its .totp, several as a ZIP of
    them. Every key in it signs its owner in, so: a full administrator only,
    where showing keys is allowed, and every export written down."""
    s = h.me('fulladmin')
    if not CONFIG.get('admin_show_key'):
        raise ApiError(403, 'showing the keys of tokens is switched off (Settings - Tokens)')
    one = norm_name(h.arg('name'))
    if one:
        tok = h.store.token(one)
        if not tok:
            raise ApiError(404, 'there is no token for %s' % one)
        if token_kind(tok) != 'totp':
            raise ApiError(400, '%s gets its codes by mail or SMS: there is no key to export' % one)
        text = totp_file_text(tok)
        if text is None:
            raise ApiError(409, 'the key of this token cannot be opened on this machine')
        h.store.add_event('tokens', '%s exported the token of %s as a .totp file' % (
            s['name'], one), 'warn', who=s['name'])
        h.send_bytes(text.encode('utf-8'), totp_file_name(one),
                     'text/plain; charset=utf-8')
        return None
    lq, bad = list_query('tokens', h.arg('q'))
    if bad:
        raise ApiError(400, bad)
    rows, _ = h.store.tokens(q=lq.words, extra=(lq.sql, lq.args), state=h.arg('state'),
                             limit=100000)
    buf = io.BytesIO()
    done, lost, odd = 0, [], []
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            tok = h.store.token(r['name'])
            if token_kind(tok) != 'totp':
                continue                # codes by mail or SMS: no key to take away (1.0.76)
            text = totp_file_text(tok or {})
            if text is None:
                lost.append(r['name'])
                continue
            if int(tok.get('digits') or 6) != 6 or int(tok.get('period') or 30) != 30 or \
                    str(tok.get('algorithm') or 'SHA1').upper() != 'SHA1':
                odd.append('%s (%s digits, %s s, %s)' % (r['name'], tok.get('digits'),
                                                         tok.get('period'), tok.get('algorithm')))
            z.writestr(totp_file_name(r['name']), text)
            done += 1
        notes = ['%d token(s) exported by %s on %s at %s.' % (
            done, s['name'], node_name(), time.strftime('%Y-%m-%d %H:%M:%S')), '',
            'Each file is what totpcgi (google-authenticator) keeps for one person: the key,',
            'its options and the recovery codes not used yet. otp reads them back under',
            'Settings - Bringing tokens over, or: otp --import-totpcgi DIR', '']
        if odd:
            notes += ['Not 6 digits, 30 s and SHA-1 - totpcgi itself cannot check these:'] + \
                     ['  ' + x for x in odd] + ['']
        if lost:
            notes += ['Left out - their keys cannot be opened on this machine:'] + \
                     ['  ' + x for x in lost] + ['']
        notes += ['Every key here signs its owner in. Keep this file as you keep passwords.']
        z.writestr('README.txt', '\n'.join(notes) + '\n')
    h.store.add_event('tokens', '%s exported %d token(s) as .totp files%s' % (
        s['name'], done, (' (filter: %s)' % h.arg('q')) if h.arg('q') else ''), 'warn',
        who=s['name'])
    h.send_bytes(buf.getvalue(), 'otp-tokens-%s.zip' % time.strftime('%Y%m%d-%H%M%S'),
                 'application/zip')
    return None


def mailq_said(e):
    """A mail that did not go now, and what happens to it (1.0.95)."""
    if getattr(e, 'queued', None) == 'waiting':
        return ('not taken yet: %s - it waits in the outgoing mail and is tried again by '
                'itself (Settings → Mail)' % e)
    return str(e)


def mail_reply_words(steps):
    """What the receiving server said when it took the message, for the
    event: its queue id is what its own log can be searched by."""
    last = (steps or [{}])[-1].get('said', '') if steps else ''
    return (' - the server said: %s' % last.split(' · ', 1)[1]) if ' · ' in last else ''


def mailed_get(store, name):
    """Where a token's mail last went, and how (1.0.27): {to, lang, codes,
    at, by}, or {} when it never was mailed."""
    try:
        got = json.loads(store.get_meta('mailed:' + norm_name(name), '') or '{}')
        return got if isinstance(got, dict) else {}
    except ValueError:
        return {}


def mailed_set(store, name, to, lang, codes, by):
    store.set_meta('mailed:' + norm_name(name), json.dumps(
        {'to': to, 'lang': lang, 'codes': bool(codes), 'at': int(time.time()), 'by': by}))


def mailed_drop(store, name):
    store.db.run('DELETE FROM meta WHERE k = ?', ('mailed:' + norm_name(name),))


@route('GET', '/api/token')
def _token(h):
    h.me()
    name = norm_name(h.arg('name'))
    tok = h.store.token(name)
    checks, _ = h.store.otp_rows(hours=24 * 365, name=name, limit=30)
    reqs, _ = h.store.radius_rows(hours=24 * 365, user=name, limit=30)
    if not reqs and '@' not in name:
        reqs, _ = h.store.radius_rows(hours=24 * 365, q=name, limit=30)
    shown = h.store.token_shown(tok) if tok else None
    if shown:
        shown['last_client'] = h.store.client_name_of(tok)
    return {'token': shown, 'checks': checks, 'requests': reqs,
            'name': name, 'mailed': mailed_get(h.store, name) if tok else {}}


SEND_TEST_LOCK = threading.Lock()
SEND_TEST_SEEN = {}


@route('POST', '/api/token')
def _token_do(h):
    s = h.me('tokenadmin')
    b = h.body()
    act = str(b.get('action') or '')
    name = norm_name(b.get('name'))
    who = s['name']
    if act == 'fill_names':
        h.me('tokenadmin')
        got = h.d.fill_names(by=who)
        return dict(got, message='%d token(s) given their owner\'s name; %d not found in the '
                    'directory, %d with no directory to ask, %d could not be asked'
                    % (got['filled'], got['not_found'], got['no_directory'], got['trouble']))
    if not name:
        raise ApiError(400, 'which token?')
    if act == 'enroll' and not h.store.token(name):
        # A new token under its realm's own suffix (1.0.117): made for
        # novak@dpmo.local, it is novak@dpmo.cz where dpmo.local is another
        # suffix of that realm - the name RADIUS looks it up by.
        main = norm_name(realm_main_name(name, h.store.realm_for(name)))
        if main != name:
            name = main
    # One at a time per name, as a confirm is (1.0.61): switching off a
    # waiting token while its owner confirmed it switched it back on; a
    # rename takes the new name's lock as well, the two in one order.
    names = sorted({name, norm_name(b.get('to'))} if act == 'rename' and b.get('to')
                   else {name})
    locks = {id(lk): lk for lk in (h.d.tokens.lock_of(one) for one in names)}
    with contextlib.ExitStack() as held:
        for key in sorted(locks):       # always in one order, whoever takes two
            held.enter_context(locks[key])
        return _token_act(h, s, b, act, name, who)


def token_same_person(store, name):
    """Another name of the same person with a token in use - one RADIUS would
    stop using once `name` has one (1.0.139): under another suffix of the
    realm, or the same account in another realm on the same directory."""
    if '@' not in name:
        return ''
    realm = store.realm_for(name)
    if not realm:
        return ''
    cands = realm_names(name, realm)[1:]
    if realm.get('lookup') == 'sam' and realm.get('directory'):
        who = name.rpartition('@')[0]
        here = str(realm.get('directory') or '').lower()
        for r in store.realms():
            if r['id'] != realm['id'] and r.get('lookup') == 'sam' and \
                    str(r.get('directory') or '').lower() == here and \
                    r.get('suffix') not in (None, '', '*'):
                cands.append(Authenticator.token_name('%s@%s' % (who, r['suffix']), r))
    for c in cands:
        c = norm_name(c)
        t = store.token(c) if c != name else None
        if t and t.get('state') != 'pending':
            return c
    return ''


def _token_act(h, s, b, act, name, who):
    tk = h.d.tokens
    if act in ('disable', 'enable', 'unlock', 'note', 'window', 'drop_staged') and \
            not h.store.token(name):
        # Written by name, these made an empty token of a name that had none.
        # (1.0.36)
        raise ApiError(404, 'there is no token %s' % name)
    if act == 'enroll':
        had = h.store.token(name)
        if had and had.get('state') != 'pending' and s['role'] != 'fulladmin':
            # Replacing a token in use hands out a working key for somebody
            # else (1.0.57): a full administrator's to do. A token
            # administrator makes new ones.
            raise ApiError(403, '%s already has a token in use: only a full administrator '
                                'replaces it (or the person, on the enrolment pages)' % name)
        other = token_same_person(h.store, name) if s['role'] != 'fulladmin' else ''
        if other:
            # The same person under another name (1.0.139): the new token
            # would be the one RADIUS takes - a working key for somebody else.
            raise ApiError(403, '%s is the same person as %s, who has a token in use: only a '
                                'full administrator replaces it' % (name, other))
        display = str(b.get('display') or '').strip()
        note = b.get('note')
        if had and not str(note or '').strip():
            note = None             # a new key keeps the note it had (1.0.36)
        kind = str(b.get('kind') or 'totp')
        if kind in ('mail', 'sms'):
            # A token that gets its codes by mail or SMS (1.0.76): where they
            # go, and recovery codes - nothing to scan.
            try:
                got = tk.enroll_sent(name, 'admin:' + who, kind, b.get('dest'), display=display,
                                     note=note, lang=b.get('lang'))
            except ValueError as e:
                raise ApiError(400, str(e))
            if not display and not (had or {}).get('display'):
                try:
                    h.d.fill_names([name], quiet=True)
                except Exception:                       # noqa: BLE001
                    pass
            h.store.add_event('tokens', '%s %s a token for %s: codes by %s to %s' % (
                who, 'replaced' if had else 'made', name, 'mail' if kind == 'mail' else 'SMS',
                got['dest']), 'warn' if had else 'info', who=who)
            return {'made': got, 'message': 'the token for %s is made: its codes go by %s to %s'
                    % (name, 'mail' if kind == 'mail' else 'SMS', got['dest'])}
        if kind != 'totp':
            raise ApiError(400, 'a token is totp, mail or sms')
        got = tk.enroll(name, 'admin:' + who, pending=bool(b.get('pending')),
                        note=note, display=display)
        if not display and not (had or {}).get('display'):
            # The person's name from the directory at once (1.0.20), not when
            # somebody next presses Names from the directory.
            try:
                h.d.fill_names([name], quiet=True)
            except Exception:                           # noqa: BLE001
                pass
        h.store.add_event('tokens', '%s %s a token for %s' % (
            who, 'replaced' if had else 'made', name), 'warn' if had else 'info', who=who)
        out = {'made': got, 'message': 'the token for %s is made' % name}
        to = str(b.get('mail_to') or '').strip()
        if b.get('mail') and to:
            # Its QR code - and the recovery codes, where asked - to the person
            # it is for (1.0.20). The token stays made whatever the mail does.
            if not re.match(r'^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+\Z', to):
                out['mail_error'] = '%s is not a mail address' % to
                return out
            lang = str(b.get('mail_lang') or CONFIG.get('mail_lang') or 'cs')
            lang = lang if lang in MAIL_WORDS else 'cs'
            tokrow = h.store.token(name) or {}
            try:
                msg = token_mail(to, name, got, codes=got.get('scratch') if b.get('mail_codes')
                                 else None, lang=lang, display=str(b.get('display') or
                                                                   tokrow.get('display') or ''),
                                 by=who, pending=bool(b.get('pending')),
                                 portal_url=h.portal_link())
                steps = mail_deliver(h.store, msg, [to], kind='token', name=name, by=who,
                                     purpose='made')
                out['mail_steps'] = steps
                out['message'] += '; the QR code was sent to %s' % to
                h.store.add_event('mail', '%s sent the token of %s to %s%s%s' % (
                    who, name, to, ' with its recovery codes' if b.get('mail_codes') else '',
                    mail_reply_words(steps)), who=who)
                mailed_set(h.store, name, to, lang, b.get('mail_codes'), who)
            except MailError as e:
                out['mail_error'] = mailq_said(e)
                out['mail_steps'] = e.steps
                out['mail_queued'] = e.queued == 'waiting'
                h.store.add_event('mail', 'the token of %s could not be sent to %s: %s' % (
                    name, to, mailq_said(e)), 'warn', who=who)
        return out
    if not h.store.token(name):
        raise ApiError(404, 'there is no token for %s' % name)
    kind_now = token_kind(h.store.token(name))
    if kind_now != 'totp' and act in ('code_now', 'show', 'mail', 'stage'):
        raise ApiError(400, '%s gets its codes by %s: there is no key or QR code to show or send'
                       % (name, 'mail' if kind_now == 'mail' else 'SMS'))
    if act == 'dest':
        # Where a mail or SMS token's codes go (1.0.76). Of a token in use,
        # a full administrator's to change (1.0.94): it sends somebody's
        # sign-in codes elsewhere, as replacing the token would.
        if (h.store.token(name) or {}).get('state') != 'pending' and s['role'] != 'fulladmin':
            raise ApiError(403, 'the codes of a token in use go elsewhere only by a full '
                                'administrator\'s hand (or the person\'s, on the enrolment pages)')
        try:
            dest = tk.dest_change(name, b.get('dest'))
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('tokens', '%s changed where the codes of %s go: %s' % (who, name, dest),
                          'warn', who=who)
        return {'message': 'the codes of %s go to %s now' % (name, dest), 'dest': dest}
    if act in ('lang', 'mail_fmt'):
        # The language of a token's codes and questions, and whether its mail
        # is HTML or plain text (1.0.82). Empty: as the settings say.
        v = str(b.get('value') or '')
        if v not in (('', 'cs', 'en') if act == 'lang' else ('', 'html', 'text')):
            raise ApiError(400, 'no such choice: %s' % v)
        h.store.token_update(h.store.token(name)['id'], {act: v})
        h.store.add_event('tokens', '%s set the %s of %s: %s' % (
            who, 'language' if act == 'lang' else 'mail format', name, v or 'as the settings say'),
            who=who)
        return {'message': 'saved'}
    if act == 'send_test':
        # A message the way a code would go, with a code that opens nothing.
        tok = h.store.token(name)
        # Not without end (1.0.136): one a token in 30 s, ten in an hour -
        # a phone flooded, or a bill run up, from the pages.
        now = time.time()
        with SEND_TEST_LOCK:
            seen = [t for t in SEND_TEST_SEEN.get(name, []) if now - t < 3600]
            if seen and now - seen[-1] < 30:
                raise ApiError(429, 'a test went to %s a moment ago - wait half a minute' % name)
            if len(seen) >= 10:
                raise ApiError(429, 'ten tests went to %s in the last hour - that is enough'
                               % name)
            SEND_TEST_SEEN[name] = seen + [now]
            if len(SEND_TEST_SEEN) > 5000:
                SEND_TEST_SEEN.clear()
        began = time.time()
        try:
            said = code_send(h.store, kind_now, tok.get('dest') or '', code_new(), 'signin',
                             name=name)
        except (MailError, SmsError, ValueError) as e:
            h.store.add_event('tokens', 'a test code for %s could not be sent: %s' % (name, e),
                              'warn', who=who)
            raise ApiError(502, 'it could not be sent: %s' % e)
        h.store.add_event('tokens', '%s sent a test message to where the codes of %s go'
                          % (who, name), who=who)
        return {'message': 'sent to %s in %.1f s - %s' % (tok.get('dest'), time.time() - began,
                                                         said)}
    if act == 'code_now':
        # The code the phone shows right now (1.0.40): a full administrator
        # only - it signs that person in for half a minute - and every look
        # written down. Not the key: the code ages out by itself.
        h.me('fulladmin')
        # As the key itself (1.0.44): the code signs that person in, so it is
        # shown only where the key may be.
        if not CONFIG.get('admin_show_key'):
            raise ApiError(403, 'showing the key of a token is switched off '
                                '(Settings -> The tokens)')
        tok = h.store.token(name)
        if not tok:
            raise ApiError(404, 'there is no token %s' % name)
        secret = unseal_secret(tok.get('secret') or '', token_bind(tok.get('name')))
        if not secret:
            raise ApiError(409, 'the key of this token cannot be opened on this machine')
        key = b32_clean(secret)
        digits = int(tok.get('digits') or 6)
        period = int(tok.get('period') or 30)
        algo = tok.get('algorithm') or 'SHA1'
        now = time.time()
        step = totp_step(now, period)
        # Written down whatever the page says (1.0.44): once per person and
        # token in five minutes, so the page asking for the next code every
        # half minute does not fill the events.
        seen_key = (who, name)
        with CODE_NOW_LOCK:
            last = CODE_NOW_SEEN.get(seen_key, 0)
            if b.get('first') or now - last > 300:
                CODE_NOW_SEEN[seen_key] = now
                fresh = True
            else:
                fresh = False
            if len(CODE_NOW_SEEN) > 2000:
                CODE_NOW_SEEN.clear()
        if fresh:
            h.store.add_event('tokens', '%s looked at the code the token of %s shows now'
                              % (who, name), 'warn', who=who)
        return {'code': hotp(key, step, digits, algo), 'next': hotp(key, step + 1, digits, algo),
                'period': period, 'digits': digits, 'now': now,
                'ends': (step + 1) * period, 'state': tok.get('state')}
    if act == 'show':
        # The key of somebody's second factor: a full administrator only,
        # where the setting allows it, and every look written down.
        h.me('fulladmin')
        if not CONFIG.get('admin_show_key'):
            raise ApiError(403, 'showing the key of a token is switched off '
                                '(Settings -> The tokens)')
        tok = h.store.token(name)
        staged = bool(tok.get('pending_secret')) and b.get('which') == 'waiting'
        secret = unseal_secret((tok.get('pending_secret') if staged else tok.get('secret')) or '',
                               token_bind(tok.get('name')))
        if not secret:
            raise ApiError(409, 'the key of this token cannot be opened (the key file of the '
                                'database is not the one it was sealed with)')
        if staged:
            # The waiting key in its own shape (1.0.32), not the old token's.
            sh = tk.staged_shape(name)
            got = tk.picture(name, secret, sh['digits'], sh['period'], sh['algorithm'],
                             sh['issuer'] or None)
        else:
            got = tk.picture(name, secret, tok.get('digits'), tok.get('period'),
                             tok.get('algorithm'), tok.get('issuer'))
        got['name'] = name
        got['scratch'] = []
        h.store.add_event('tokens', '%s looked at the key of the %stoken of %s'
                          % (who, 'waiting ' if staged else '', name), 'warn', who=who)
        return {'made': got}
    if act == 'codes':
        # The recovery codes left, shown again: the same rule as the key.
        h.me('fulladmin')
        if not CONFIG.get('admin_show_key'):
            raise ApiError(403, 'showing the key of a token is switched off '
                                '(Settings -> The tokens)')
        tok = h.store.token(name)
        codes = codes_open(tok)
        if codes is None:
            raise ApiError(409, 'the recovery codes of this token were not kept to be shown '
                                'again (it was made by an older version); make new ones')
        h.store.add_event('tokens', '%s looked at the recovery codes of %s' % (who, name),
                          'warn', who=who)
        return {'scratch': codes}
    if act == 'mail':
        # The token's QR code mailed again (1.0.27). The key leaves the
        # machine as when it is shown, so the same rule: a full administrator,
        # where showing keys is allowed.
        h.me('fulladmin')
        if not CONFIG.get('admin_show_key'):
            raise ApiError(403, 'showing - and so mailing - the key of a token is switched off '
                                '(Settings -> The tokens)')
        to = str(b.get('mail_to') or '').strip()
        if not re.match(r'^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+\Z', to):
            raise ApiError(400, '%s is not a mail address' % (to or 'nothing'))
        tok = h.store.token(name)
        secret = unseal_secret(tok.get('secret') or '', token_bind(tok.get('name')))
        if not secret:
            raise ApiError(409, 'the key of this token cannot be opened (the key file of the '
                                'database is not the one it was sealed with)')
        got = tk.picture(name, secret, tok.get('digits'), tok.get('period'),
                         tok.get('algorithm'), tok.get('issuer'))
        codes = None
        if b.get('mail_codes'):
            kept = codes_open(tok)
            if kept is None:
                raise ApiError(409, 'the recovery codes of this token were not kept to be sent '
                                    'again; send it without them, or make new ones first')
            codes = [c['c'] for c in kept if not c.get('used')]
        lang = str(b.get('mail_lang') or CONFIG.get('mail_lang') or 'cs')
        lang = lang if lang in MAIL_WORDS else 'cs'
        try:
            msg = token_mail(to, name, got, codes=codes, lang=lang,
                             display=str(tok.get('display') or ''), by=who,
                             pending=tok.get('state') == 'pending',
                             portal_url=h.portal_link())
            steps = mail_deliver(h.store, msg, [to], kind='token', name=name, by=who,
                                 purpose='again')
        except MailError as e:
            h.store.add_event('mail', 'the token of %s could not be sent to %s: %s' % (
                name, to, mailq_said(e)), 'warn', who=who)
            return {'sent': False, 'said': mailq_said(e), 'steps': e.steps,
                    'queued': e.queued == 'waiting'}
        mailed_set(h.store, name, to, lang, codes, who)
        h.store.add_event('mail', '%s sent the token of %s to %s again%s%s' % (
            who, name, to, ' with its recovery codes' if codes else '',
            mail_reply_words(steps)), 'warn', who=who)
        return {'sent': True, 'steps': steps, 'message': 'sent to %s' % to,
                'mailed': mailed_get(h.store, name)}
    if act in ('disable', 'enable'):
        if act == 'enable' and (h.store.token(name) or {}).get('state') != 'disabled':
            # Not switched off: nothing to switch on (1.0.61) - a waiting
            # token was made active by it.
            return {'message': 'it is not switched off'}
        h.store.token_write(name, {'state': token_switch_state(h.store, name, act == 'enable'),
                                   'failures': 0, 'fail_times': '[]', 'locked_until': None})
        h.store.add_event('tokens', '%s switched the token of %s %s' % (
            who, name, 'off' if act == 'disable' else 'on'), who=who)
        return {'message': 'switched %s' % ('off' if act == 'disable' else 'on')}
    if act == 'delete':
        # A token in use taken away, then made anew, was a token administrator's
        # way round the rule that only a full administrator replaces one
        # (1.0.94): switching it off is theirs, taking it away is not.
        if (h.store.token(name) or {}).get('state') not in ('pending', None) and \
                s['role'] != 'fulladmin':
            raise ApiError(403, 'only a full administrator takes away a token in use - '
                                'switch it off instead')
        h.store.token_drop(name)
        mailed_drop(h.store, name)
        tk._staged_forget(name)
        token_meta_forget(h.store, name)
        h.store.add_event('tokens', '%s took away the token of %s' % (who, name), 'warn',
                          who=who)
        return {'message': 'the token of %s is gone' % name}
    if act == 'scratch':
        # New recovery codes are working credentials of somebody else that
        # leave no trace on their phone (1.0.33): the same rule as showing a
        # key - a full administrator, where that is allowed - and a warning
        # in the events.
        h.me('fulladmin')
        if not CONFIG.get('admin_show_key'):
            raise ApiError(403, 'new recovery codes are shown to whoever makes them, and showing '
                                'codes and keys is switched off (Settings -> The tokens)')
        codes = tk.new_scratch(name, who)
        h.store.add_event('tokens', '%s made new recovery codes for %s' % (who, name), 'warn',
                          who=who)
        return {'scratch': codes, 'message': '%d new recovery codes' % len(codes)}
    if act == 'unlock':
        h.store.token_write(name, {'failures': 0, 'fail_times': '[]', 'locked_until': None})
        node_key_drop(h.store, 'scratchguard', name)
        h.store.add_event('tokens', '%s let %s try again at once' % (who, name), who=who)
        return {'message': 'the wrong codes are forgotten'}
    if act == 'rename':
        h.me('fulladmin')       # with a key known, a rename makes it somebody else's (1.0.57)
        # Into another realm: the part after the @ changes, and with it the
        # name the VPN has to send. The key and the history stay; the
        # recovery codes are made again under the new name where they were
        # kept to be shown, since their hashes are of the name too. (1.0.11)
        to = norm_name(b.get('to'))
        # The same rule as a new token's (1.0.44).
        if not to or not re.match(r'^[^\s@,;=\x00-\x1f\x7f]+(@[A-Za-z0-9.-]+)?\Z', to) or \
                len(to) > 180 or not isinstance(b.get('to'), str):
            raise ApiError(400, 'that is not a name: a name, or a name@realm - no spaces, '
                                'commas, semicolons or =, 180 characters at most')
        if to == norm_name(name):
            raise ApiError(400, 'that is the name it has')
        if h.store.token(to):
            raise ApiError(409, 'there is a token for %s already' % to)
        tok = h.store.token(name)
        if tok.get('pending_secret'):
            raise ApiError(409, 'a new key is waiting for a code from it: confirm it or throw it '
                                'away first')
        fields = {'name': to}
        codes = codes_open(tok)
        kept = True
        # Its sealed secrets are tied to its name: sealed again for the new
        # one (1.0.33), or they would no longer open.
        plain = unseal_secret(tok.get('secret') or '', token_bind(tok.get('name')))
        if plain:
            fields['secret'] = seal_secret(plain, token_bind(to))
        if codes is not None:
            fields['scratch'] = json.dumps([scratch_hash(to, c['c']) if isinstance(c, dict)
                                            else scratch_hash(to, c) for c in codes
                                            if not (isinstance(c, dict) and c.get('used'))])
            fields['scratch_sealed'] = seal_codes(codes, token_bind(to))
            fields['scratch_left'] = len(json.loads(fields['scratch']))     # 1.0.61
        elif tok.get('scratch_left'):
            kept = False
            fields.update(scratch='[]', scratch_left=0)
        # Moved to somebody else, the owner's name is theirs now (1.0.19).
        if norm_name(to).split('@', 1)[0] != norm_name(name).split('@', 1)[0]:
            fields['display'] = ''
        h.store.db.update('tokens', tok['id'], fields)
        h.store.db.run('UPDATE otp_log SET name = ? WHERE name = ?', (to, tok['name']))
        # What was kept aside under the old name goes with it (1.0.61).
        h.store.db.run('UPDATE meta SET k = ? WHERE k = ?',
                       ('disabled_from:' + norm_name(to), 'disabled_from:' + norm_name(name)))
        # Where its mail went goes with it - but only within the same
        # person: somebody else's token is not mailed to the old address.
        was = mailed_get(h.store, name)
        mailed_drop(h.store, name)
        if was and not fields.get('display') == '':
            mailed_set(h.store, to, was.get('to'), was.get('lang'), was.get('codes'),
                       was.get('by'))
        if fields.get('display') == '':
            h.d.fill_names_later([to])
        h.store.add_event('tokens', '%s moved the token of %s to %s' % (who, tok['name'], to),
                          'warn', who=who)
        return {'name': to, 'message': 'the token is now %s%s' % (
            to, '' if kept else '; its recovery codes were not kept to be made again under the '
                                'new name, so make new ones')}
    if act == 'note':
        h.store.token_write(name, {'note': str(b.get('note') or '')[:400]})
        h.store.add_event('tokens', '%s changed the note of %s' % (who, name), who=who)
        return {'message': 'the note is saved'}
    if act == 'window':
        w = int(b.get('window', -1))
        if not -1 <= w <= 20:
            raise ApiError(400, 'the window is -1 (the setting) or 0 to 20 steps')
        h.store.token_write(name, {'window_steps': w})
        h.store.add_event('tokens', '%s set the clock drift of %s to %s' % (
            who, name, 'the setting' if w < 0 else '%d step(s)' % w), who=who)
        return {'message': 'saved'}
    if act == 'test':
        # Counted per administrator and token (1.0.57): a dry test counts
        # nothing on the token, and so could be asked without end.
        h.throttle('code-test', 10, 5, name='%s>%s' % (who, name))
        ok, said, facts = tk.check(name, str(b.get('code') or ''), how='test',
                                   src=h.client_ip(), dry=not b.get('use'))
        if not ok:
            h.failed('code-test')
        return {'good': ok, 'said': said, 'facts': facts}
    if act == 'confirm':
        ok, said = tk.confirm(name, str(b.get('code') or ''), how='admin', src=h.client_ip())
        if ok:
            h.store.add_event('tokens', '%s confirmed the token of %s' % (who, name), who=who)
        return {'good': ok, 'said': said}
    if act == 'drop_staged':
        tk.drop_staged(name)
        h.store.add_event('tokens', '%s threw away the replacement waiting for %s' % (who, name),
                          who=who)
        return {'message': 'the waiting replacement is gone; the old token stays'}
    raise ApiError(400, 'no such thing to do to a token: %s' % act)


def totp_file_name(name):
    """The file a token goes into, and its name read back from it (1.0.146):
    jan+1@x.cz and jan_1@x.cz were both jan_1@x.cz.totp - one lost in the ZIP
    - and o'neil@x.cz came back as o_neil@x.cz, which RADIUS never looks up."""
    from urllib.parse import quote
    return quote(str(name), safe='@.-_') + '.totp'


def totp_file_owner(fname):
    from urllib.parse import unquote
    fname = os.path.basename(str(fname or ''))
    return unquote(fname[:-5] if fname.endswith('.totp') else fname)


def totp_files_in_zip(b64, label, out):
    """The .totp files inside a ZIP the page sent (1.0.33) - a totpcgi
    folder zipped, or another otp's export. Read in memory with limits on
    everything: how big, how many, how far it unpacks. Nothing is written to
    disk and no name inside is used as a path."""
    try:
        raw = base64.b64decode(str(b64), validate=True)
    except (ValueError, binascii.Error):
        out.append({'name': label, 'said': 'not imported: not a ZIP the page could send'})
        return []
    got = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > 50000:
                raise ValueError('more than 50 000 files in it')
            total = 0
            for info in infos:
                base = info.filename.replace('\\', '/').rsplit('/', 1)[-1]
                if info.is_dir() or not base.endswith('.totp') or base.startswith('.') or \
                        '__MACOSX/' in info.filename:
                    continue
                if info.file_size > 64 * 1024:
                    out.append({'name': base, 'said': 'not imported: too big for a .totp file'})
                    continue
                total += info.file_size
                if total > 64 * 1024 * 1024:
                    raise ValueError('it unpacks to more than 64 MB')
                with z.open(info) as f:
                    data = f.read(64 * 1024 + 1)
                if len(data) > 64 * 1024:
                    out.append({'name': base, 'said': 'not imported: too big for a .totp file'})
                    continue
                got.append({'name': base, 'text': data.decode('utf-8', 'replace')})
    except (zipfile.BadZipFile, ValueError, RuntimeError, NotImplementedError) as e:
        out.append({'name': label, 'said': 'not imported: %s' % e})
        return []
    if not got:
        out.append({'name': label, 'said': 'not imported: no .totp file in it'})
    return got


@route('POST', '/api/tokens/backup')
def _tokens_backup(h):
    """Every token chosen, of every kind, as one file (1.0.96): locked with
    a passphrase when one is given. A full administrator's, where keys may
    be shown, and written down."""
    s = h.me('fulladmin')
    if not CONFIG.get('admin_show_key'):
        raise ApiError(403, 'showing the keys of tokens is switched off (Settings - Tokens)')
    b = h.body()
    lq, bad = list_query('tokens', str(b.get('q') or ''))
    if bad:
        raise ApiError(400, bad)
    kind = str(b.get('kind') or '')
    rows, _ = h.store.tokens(q=lq.words, extra=(lq.sql, lq.args), state=str(b.get('state') or ''),
                             limit=1000000, kind=kind if kind in ('totp', 'mail', 'sms') else '')
    data = tokens_backup(h.store, [r['name'] for r in rows], s['name'])
    phrase = str(b.get('passphrase') or '')
    # Always locked (1.0.136): every key and recovery code is in it.
    if len(phrase) < 8:
        raise ApiError(400, 'a passphrase of 8 characters at least: the file holds every key')
    text = json.dumps(bundle_lock(data, phrase, kind=TOKENS_KIND), indent=1)
    h.store.add_event('tokens', '%s backed up %d token(s)%s%s' % (
        s['name'], data['count'], ' locked with a passphrase' if phrase else ' (not locked)',
        (' - %d left out, their keys cannot be opened here' % len(data['lost']))
        if data['lost'] else ''), 'warn', who=s['name'])
    return {'file': text, 'count': data['count'], 'lost': data['lost'], 'locked': bool(phrase),
            'name': 'otp-tokens-%s-%s.json' % (re.sub(r'[^A-Za-z0-9_-]', '_', node_name()),
                                               time.strftime('%Y%m%d-%H%M'))}


@route('POST', '/api/token/import')
def _token_import(h):
    s = h.me('fulladmin')
    b = h.body()
    out = []
    files = []
    # A whole backup (1.0.96): looked into first ("peek"), then all of it
    # or the tokens picked read back. .totp files and ZIPs of them as ever.
    phrase = str(b.get('passphrase') or '')
    want = set(norm_name(x) for x in (b.get('names') or []) if isinstance(x, str))
    repl_names = set(norm_name(x) for x in (b.get('replace_names') or []) if isinstance(x, str))
    backups = []
    for one in b.get('files') or []:
        if not isinstance(one, dict) or one.get('zip'):
            continue
        try:
            got = tokens_backup_open(str(one.get('text') or ''), phrase)
        except PermissionError as e:
            raise ApiError(423, str(e))
        except ValueError as e:
            raise ApiError(400, '%s: %s' % (one.get('name') or 'the file', e))
        if got is not None:
            backups.append((one, got))
    if backups:
        if b.get('action') == 'peek':
            seen = []
            cols = sorted(set([c for c, _k in LIST_FIELDS['tokens'].values() if c] +
                              list(LIST_WORD_COLUMNS['tokens'])))
            nums = set(c for c, k in LIST_FIELDS['tokens'].values() if k == 'num')
            table = 'CREATE TABLE t (i INTEGER, %s)' % ', '.join(
                '%s %s' % (c, 'INTEGER' if c in nums else 'TEXT') for c in cols)
            mem = []
            for one, got in backups:
                for t in got['tokens']:
                    if not isinstance(t, dict):
                        continue
                    n = norm_name(t.get('name'))
                    seen.append({'name': n, 'kind': t.get('kind') or 'totp',
                                 'dest': t.get('dest') or '', 'state': t.get('state') or '',
                                 'codes': len([c for c in t.get('codes') or []
                                               if not (isinstance(c, dict) and c.get('used'))]),
                                 'display': t.get('display') or '', 'here': bool(h.store.token(n))})
                    left = len([c for c in t.get('codes') or []
                                if not (isinstance(c, dict) and c.get('used'))])
                    mem.append({'name': n, 'state': t.get('state') or '',
                                'kind': '' if (t.get('kind') or 'totp') == 'totp' else t.get('kind'),
                                'dest': t.get('dest') or '', 'lang': t.get('lang') or '',
                                'mail_fmt': t.get('mail_fmt') or '', 'note': t.get('note') or '',
                                'display': t.get('display') or '',
                                'created_by': t.get('created_by') or '',
                                'last_from': t.get('last_from') or '',
                                'last_how': t.get('last_how') or '', 'scratch_left': left,
                                'failures': 0, 'digits': int(t.get('digits') or 6)})
            # Searched with the words of the token list (1.0.96).
            q = str(b.get('q') or '')
            if q.strip():
                try:
                    keep = set(memory_search('tokens', table, cols, mem, q))
                except ListQueryError as e:
                    return {'q_error': str(e), 'backup': {'tokens': [], 'count': len(seen)}}
                seen = [x for i, x in enumerate(seen) if i in keep]
            first = backups[0][1]
            return {'backup': {'count': len(mem), 'shown': len(seen), 'made': first.get('made') or first.get('_made'),
                               'by': first.get('by'), 'node': first.get('node') or first.get('_from'),
                               'version': first.get('version'), 'lost': first.get('lost') or [],
                               'tokens': seen}}
        for one, got in backups:
            for t in got['tokens']:
                n = norm_name((t or {}).get('name') if isinstance(t, dict) else '')
                if want and n not in want:
                    continue
                try:
                    # Replaced one by one as the page chose (1.0.100), or all.
                    said = token_restore(h.store, t, 'restore:' + s['name'],
                                         replace=bool(b.get('replace')) or n in repl_names)
                except (ValueError, TypeError) as e:
                    said = 'not restored: %s' % e
                out.append({'name': n, 'said': said})
        h.store.add_event('tokens', '%s restored %d token(s) from a backup' % (
            s['name'], len([o for o in out if str(o['said']).startswith('restored')])),
            'warn', who=s['name'])
        return {'done': out}
    for one in b.get('files') or []:
        if one.get('zip'):
            files.extend(totp_files_in_zip(one.get('zip'), str(one.get('name') or 'the ZIP'),
                                           out))
        else:
            files.append(one)
    for one in files:
        fname = os.path.basename(str(one.get('name') or ''))
        name = totp_file_owner(fname)
        if want and norm_name(name) not in want:
            continue
        try:
            said = import_totp(h.store, name, str(one.get('text') or ''), 'import:' + s['name'],
                               replace=bool(b.get('replace')))
        except ValueError as e:
            said = 'not imported: %s' % e
        out.append({'name': norm_name(name), 'said': said})
    h.store.add_event('tokens', '%s imported %d token file(s)' % (s['name'], len(out)),
                      who=s['name'])
    # Their owners' names from the directory, as an enrolment on the pages
    # would have given them - in the background, the list is not kept waiting.
    h.d.fill_names_later([o['name'] for o in out if str(o['said']).startswith('imported')],
                         by=s['name'])
    return {'done': out}


# ---- clients, realms, directories -----------------------------------------------------
@route('GET', '/api/clients')
def _clients(h):
    s = h.me()
    clients = h.store.clients()
    if s['role'] != 'fulladmin':
        # Not even the last two characters to whoever cannot change it (1.0.33).
        for c in clients:
            c['secret'] = '••••••' if c.get('secret') else ''
    return {'clients': clients, 'realms': [r['name'] + ' (' + (r['suffix'] or '-')
                                                     + ')' for r in h.store.realms()],
            'suffixes': [r['suffix'] for r in h.store.realms() if r['suffix'] not in ('*', '')],
            'may_change': s['role'] == 'fulladmin'}


@route('POST', '/api/clients')
def _clients_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    if act == 'save':
        c = b.get('client') or {}
        ident = h.store.client_save(c, s['name'])
        h.store.add_event('clients', '%s saved the RADIUS client %s (%s)' % (
            s['name'], c.get('name'), c.get('address')), who=s['name'])
        h.d.changed('clients')
        return {'id': ident, 'message': 'the client %s is saved' % c.get('name')}
    if act == 'delete':
        one = next((c for c in h.store.clients() if c['id'] == _int_id(b.get('id'))), None)
        if not one:
            raise ApiError(404, 'there is no such client')     # 1.0.103
        h.store.client_drop(one['id'])
        h.store.add_event('clients', '%s took away the RADIUS client %s' % (
            s['name'], one.get('name')), 'warn', who=s['name'])
        h.d.changed('clients')
        return {'message': 'the client is gone'}
    if act == 'secret':
        h.me('fulladmin')
        one = next((c for c in h.store.clients(with_secret=True)
                    if c['id'] == int(b.get('id') or 0)), None)
        if not one:
            raise ApiError(404, 'no such client')
        h.store.add_event('clients', '%s looked at the shared secret of %s' % (
            s['name'], one['name']), who=s['name'])
        return {'secret': one['secret']}
    raise ApiError(400, 'no such thing to do to a client')


def realm_alias_tokens(store, realm):
    """Tokens kept under one of the realm's other suffixes (1.0.117) - made
    before it was one - with the name each would have now, and whether a
    token is there already under it."""
    out = []
    if realm.get('token_name') == 'bare' or realm.get('suffix') in (None, '', '*'):
        return out
    for al in realm.get('aliases') or []:
        for row in store.db.rows('SELECT name FROM tokens WHERE LOWER(name) LIKE ? '
                                 'ORDER BY name', ('%@' + al,)):
            to = norm_name(realm_main_name(row['name'], realm))
            out.append({'name': row['name'], 'to': to, 'clash': bool(store.token(to))})
            if len(out) >= 500:
                return out
    return out


@route('GET', '/api/realms')
def _realms(h):
    s = h.me()
    realms = h.store.realms()
    for r in realms:
        if r.get('aliases'):
            r['alias_tokens'] = realm_alias_tokens(h.store, r)
    return {'realms': realms, 'directories': [d['name'] for d in
                                                       h.store.directories()],
            'reply_attrs': list(REPLY_ATTRS), 'reply_catalogue': reply_catalogue(),
            'channels': code_channels(),            # mail, sms - set up (1.0.76)
            'may_change': s['role'] == 'fulladmin'}


@route('POST', '/api/realms')
def _realms_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    if act == 'save':
        r = b.get('realm') or {}
        absorb = [str(x) for x in (b.get('absorb') or []) if str(x).strip()][:10]
        before = {x['name'] for x in h.store.realms()}
        ident = h.store.realm_save(r, s['name'], absorb=absorb)
        gone = sorted(before - {x['name'] for x in h.store.realms()} - {r.get('name')})
        h.store.add_event('realms', '%s saved the realm %s%s' % (
            s['name'], r.get('name'), ('; taken into it: %s - their suffixes are its own now, '
                                       'their groups follow its own' % ', '.join(gone))
            if gone else ''), 'warn' if gone else 'info', who=s['name'])
        h.d.changed('realms')
        return {'id': ident, 'message': 'the realm %s is saved' % r.get('name')}
    if act == 'delete':
        one = next((r for r in h.store.realms() if r['id'] == _int_id(b.get('id'))), None)
        if not one:
            raise ApiError(404, 'there is no such realm')      # 1.0.103
        h.store.realm_drop(one['id'])
        h.store.add_event('realms', '%s took away the realm %s' % (s['name'], one['name']),
                          'warn', who=s['name'])
        h.d.changed('realms')
        return {'message': 'the realm is gone'}
    if act == 'move_alias_tokens':
        # Under the realm's own suffix (1.0.117), each as a rename is: the
        # key sealed again, the recovery codes kept, the log following it.
        # One that would land on a token already there is left as it is.
        one = next((r for r in h.store.realms() if r['id'] == _int_id(b.get('id'))), None)
        if not one:
            raise ApiError(404, 'there is no such realm')
        moved, left = [], []
        for t in realm_alias_tokens(h.store, one):
            if t['clash']:
                left.append(t['name'])
                continue
            names = sorted({t['name'], t['to']})
            locks = {id(lk): lk for lk in (h.d.tokens.lock_of(n) for n in names)}
            try:
                with contextlib.ExitStack() as held:
                    for key in sorted(locks):
                        held.enter_context(locks[key])
                    _token_act(h, s, {'to': t['to']}, 'rename', t['name'], s['name'])
                moved.append(t['name'])
            except ApiError as e:
                left.append('%s (%s)' % (t['name'], e))
        h.store.add_event('realms', '%s moved %d token(s) under @%s in the realm %s%s' % (
            s['name'], len(moved), one['suffix'], one['name'],
            ('; left as they are: %s' % ', '.join(left[:20])) if left else ''), who=s['name'])
        return {'moved': moved, 'left': left, 'message': '%d token(s) moved under @%s%s' % (
            len(moved), one['suffix'], ('; %d left as they are - a token is there under the '
                                       'new name already' % len(left)) if left else '')}
    if act == 'try':
        name = Authenticator.full_name(str(b.get('user') or ''), str(b.get('realm') or ''))
        realm = h.store.realm_for(name)
        return {'name': name, 'realm': realm['name'] if realm else None}
    raise ApiError(400, 'no such thing to do to a realm')


@route('GET', '/api/directories')
def _dirs(h):
    s = h.me()
    dirs = h.store.directories()
    if s['role'] != 'fulladmin':
        for d in dirs:
            if d.get('bind_pw'):
                d['bind_pw'] = '••••••'
    return {'directories': dirs, 'may_change': s['role'] == 'fulladmin'}


@route('POST', '/api/directories')
def _dirs_do(h):
    b = h.body()
    act = b.get('action')
    if act in ('save', 'delete'):
        s = h.me('fulladmin')
        if act == 'save':
            one = b.get('directory') or {}
            ident = h.store.directory_save(one, s['name'])
            h.store.add_event('directories', '%s saved the directory %s' % (
                s['name'], one.get('name')), who=s['name'])
            h.d.changed('directories')
            return {'id': ident, 'message': 'the directory %s is saved' % one.get('name')}
        one = next((x for x in h.store.directories() if x['id'] == _int_id(b.get('id'))), None)
        if not one:
            raise ApiError(404, 'there is no such directory')  # 1.0.103
        h.store.directory_drop(one['id'])
        h.store.add_event('directories', '%s took away the directory %s' % (s['name'], one['name']),
                          'warn', who=s['name'])
        h.d.changed('directories')
        return {'message': 'the directory is gone'}
    if act == 'whois':
        # What the directory says about one person - an account here (asked of
        # the directory administrators sign in against) or the owner of a
        # token (asked of the directory of the realm the name falls in).
        h.me('tokenadmin')      # as its siblings (1.0.57), not every reader
        who = str(b.get('user') or '').strip()
        if not who:
            raise ApiError(400, 'who?')
        realm = None
        if b.get('kind') == 'account':
            dname = str(CONFIG.get('admin_directory') or '')
        else:
            realm = h.store.realm_for(who)
            dname = (realm or {}).get('directory') or ''
        ad = h.d.dirs.get(dname.lower()) if dname else None
        if not ad:
            raise ApiError(404, 'no directory answers for %s' % who)
        bare, how = admin_name_parts(who)
        if realm and realm.get('lookup') in ('upn', 'sam'):
            how = realm['lookup']
            bare = who if how == 'upn' else who.split('@', 1)[0]
        t = time.time()
        try:
            entry = ad.find_user(bare, how)
            groups = ad.groups_of(entry, True) if entry else []
        except LdapUnreachable as e:
            log('the directory could not be reached: %s' % e, 'warn')
            raise ApiError(503, 'the directory cannot be reached just now')
        # Each group with where it lives and what it gives here (1.0.19, as
        # isemon's person card): an administrators' role, or the way into a
        # realm - the ones that matter are drawn first, as cards.
        listed = []
        seen = set()
        realms = [r for r in h.store.realms() if r.get('enabled')]
        for dn, cn in sorted(groups, key=lambda g: str(g[1]).lower()):
            if dn.lower() in seen:
                continue
            seen.add(dn.lower())
            gives = []
            for key, role in ROLE_GROUP_KEYS:
                if group_matches(dn_list(CONFIG.get(key)), [(dn, cn)], ad):
                    gives.append({'role': role})
            for r in realms:
                if r.get('groups') and group_matches(r['groups'], [(dn, cn)], ad):
                    gives.append({'realm': r['name']})
            listed.append({'name': cn, 'dn': dn, 'gives': gives})
        acc = h.store.account(who) if b.get('kind') == 'account' else None
        tok = h.store.token(who) if b.get('kind') != 'account' else None
        return {'entry': entry, 'groups': sorted({cn for _, cn in groups}, key=str.lower),
                'group_list': listed, 'realm': (realm or {}).get('name') or '',
                'role': (acc or {}).get('role') or '', 'token': bool(tok),
                'token_state': (tok or {}).get('state') or '',
                'directory': ad.name, 'took_ms': int((time.time() - t) * 1000)}
    if act == 'people':
        # People in the directory of a realm whose names hold what is typed -
        # what the boxes offer while somebody types a name (1.0.19).
        h.me('tokenadmin')
        like = str(b.get('like') or '').strip()
        rname = str(b.get('realm') or '').strip().lower()
        realm = next((r for r in h.store.realms() if r['name'].lower() == rname
                      or str(r.get('suffix') or '').lower() == rname.lstrip('@')), None)
        if not realm:
            realm = h.store.realm_for(like) if '@' in like else None
        dname = str(b.get('directory') or '').strip()
        if dname:
            # One directory by its name, as the Look a name up box asks it:
            # the people as that directory names them.
            ad = h.d.dirs.get(dname.lower())
            if not ad:
                return {'people': []}
            try:
                found = ad.find_users(like.split('@', 1)[0], max(1, min(50, int(b.get('limit') or 20))))
            except LdapUnreachable as e:
                log('the directory could not be reached: %s' % e, 'warn')
                raise ApiError(503, 'the directory cannot be reached just now')
            return {'people': [{'name': (u['upn'] or u['sam'] or '').lower(),
                                'display': u['display'], 'mail': u['mail'],
                                'mobile': u.get('mobile') or '',
                                'disabled': u['disabled'], 'token': ''} for u in found]}
        if not realm or not realm.get('directory'):
            return {'people': [], 'realm': (realm or {}).get('name') or ''}
        ad = h.d.dirs.get(str(realm['directory']).lower())
        if not ad:
            return {'people': [], 'realm': realm['name']}
        try:
            found = ad.find_users(like.split('@', 1)[0], max(1, min(50, int(b.get('limit') or 20))))
        except LdapUnreachable as e:
            log('the directory could not be reached: %s' % e, 'warn')
            raise ApiError(503, 'the directory cannot be reached just now')
        suffix = str(realm.get('suffix') or '')
        out = []
        for u in found:
            if realm.get('lookup') == 'upn' and u['upn']:
                name = u['upn'].lower()
            elif suffix and suffix != '*':
                name = '%s@%s' % ((u['sam'] or '').lower(), suffix.lower())
            else:
                name = (u['upn'] or u['sam'] or '').lower()
            if realm.get('token_name') == 'bare':
                name = name.split('@', 1)[0]
            # A name this realm does not take is no use (1.0.103): a UPN with
            # another suffix (pkolar@corpnet.loc for the realm corpnet.cz) made
            # a token no realm answers for, and the VPN refused it.
            if name and realm.get('token_name') != 'bare':
                took = h.store.realm_for(name)
                if not took or took.get('id') != realm.get('id'):
                    continue
            tok = h.store.token(name) if name else None
            out.append({'name': name, 'display': u['display'], 'mail': u['mail'],
                        'mobile': u.get('mobile') or '',
                        'disabled': u['disabled'], 'token': (tok or {}).get('state') or ''})
        return {'people': out, 'realm': realm['name']}
    if act == 'ca':
        s = h.me('fulladmin')
        one = next((x for x in h.store.directories() if x['id'] == int(b.get('id') or 0)), None)
        if not one:
            raise ApiError(404, 'there is no such directory')
        pem = str(b.get('ca') or '').strip()
        mode = str(b.get('mode') or ('add' if pem else 'clear'))
        before = len(one.get('ca_list') or [])
        try:
            h.store.directory_set_ca(one['id'], pem, mode, str(b.get('fingerprint') or ''))
        except ValueError as e:
            raise ApiError(400, str(e))
        after = next((x for x in h.store.directories() if x['id'] == one['id']), {})
        n = len(after.get('ca_list') or [])
        words = {'add': 'added %d certificate(s) to' % max(0, n - before),
                 'set': 'replaced', 'drop': 'took a certificate out of',
                 'clear': 'took away'}.get(mode, 'changed')
        h.store.add_event('directories', '%s %s the certificate authorities of %s (%d kept)' % (
            s['name'], words, one['name'], n), who=s['name'])
        h.d.changed('directories')
        if mode == 'add' and n == before:
            msg = 'every one of those certificates is kept already'
        else:
            msg = '%s keeps %d certificate(s)' % (one['name'], n)
        return {'message': msg, 'ca_list': after.get('ca_list') or []}
    if act == 'try':
        who = h.me('fulladmin')['name']
        if not CONFIG.get('admin_directory'):
            raise ApiError(400, 'no directory signs administrators in yet: choose one in '
                                '"Sign administrators in against the directory" and save')
        # Counted and written down (1.0.139), as a radtest is: each try is a
        # directory password, and wrong ones lock the account there.
        user = str(b.get('user') or '')
        key = h.throttle('radtest', 20, 5, name='%s>%s' % (who, user[:120]), ip_tries=100)
        said = admin_ask_directory(h, user, str(b.get('password') or ''))
        if said is None:
            raise ApiError(404, 'the directory %s is not set up' % CONFIG.get('admin_directory'))
        said.pop('entry', None)
        if not said.get('ok'):
            h.failed(key)
        h.store.add_event('accounts', '%s tried the directory sign-in of %s: %s' % (
            who, user[:120], 'it would sign in' if said.get('ok') else 'refused'), who=who)
        return {'tried': said}
    h.me('tokenadmin')
    if act not in ('check', 'groups', 'lookup'):
        raise ApiError(400, 'no such thing to do with a directory')     # 1.0.103
    ad = h.d.dirs.get(str(b.get('name') or '').lower())
    if not ad:
        raise ApiError(404, 'there is no directory called %s (switched on)' % b.get('name'))
    if act == 'check':
        return {'check': ad.check()}
    if act == 'groups':
        groups = ad.find_groups(str(b.get('like') or ''), limit=5000)
        return {'groups': groups, 'capped': len(groups) >= 5000}
    if act == 'lookup':
        who = str(b.get('user') or '').strip()
        how = str(b.get('how') or ('upn' if '@' in who else 'sam'))
        t = time.time()
        entry = ad.find_user(who, how)
        groups = ad.groups_of(entry, True) if entry else []
        return {'entry': entry, 'groups': [cn for _, cn in groups],
                'took_ms': int((time.time() - t) * 1000)}
    raise ApiError(400, 'no such thing to do with a directory')


# ---- trying it --------------------------------------------------------------------------
@route('POST', '/api/radtest')
def _radtest(h):
    s = h.me('tokenadmin')
    b = h.body()
    node = str(b.get('node') or '').strip()
    if node and node != node_name():
        # Asked on another node of the cluster (1.0.45): through the
        # database both open, the password sealed with the key both have.
        # Counted here too (1.0.94): it tries a directory password as well.
        rkey = h.throttle('radtest', 20, 5, name='%s>%s' % (s['name'], str(b.get('user') or '')[:120]),
                      ip_tries=100)
        got = radtest_elsewhere(h.store, node, s['name'], h.client_ip(), b)
        if not (isinstance(got, dict) and got.get('result') in ('accept', 'challenge')):
            h.failed(rkey)
        return got
    server = str(b.get('server') or '127.0.0.1')
    if server not in ('127.0.0.1', '::1', 'localhost'):
        h.me('fulladmin')
    # Counted per administrator and person tried (1.0.57): each test tries a
    # directory password, and nothing else limited how many.
    rkey = h.throttle('radtest', 20, 5, name='%s>%s' % (s['name'], str(b.get('user') or '')[:120]),
                      ip_tries=100)
    got = radtest_do(h.store, h.d, s['name'], h.client_ip(), b)
    # The first step of a mail or SMS token is a challenge, not a wrong
    # password (1.0.103): counted as one here (not on the other node), it
    # locked every administrator of the address out after a few tests.
    if not (isinstance(got, dict) and got.get('result') in ('accept', 'challenge')):
        h.failed(rkey)
    return got


def radtest_do(store, daemon, by, src, b):
    """One test of a name and a password, on this node - asked on its pages,
    or by another node of the cluster for its pages."""
    user = str(b.get('user') or '')
    password = str(b.get('password') or '')
    how = str(b.get('how') or 'udp')
    # The answer to a second window (1.0.81): the code, with the State the
    # first answer carried.
    state = str(b.get('state') or '').strip().lower()
    if state.startswith('0x'):
        state = state[2:]
    if state and not re.fullmatch(r'[0-9a-f]{2,500}', state):
        raise ApiError(400, 'the State is hex')
    if how == 'direct':
        client = next((c for c in store.clients() if c['id'] == int(b.get('client') or 0)),
                      None)
        realm = (client or {}).get('realm') or str(b.get('realm') or '')
        if state:
            d = daemon.auth.answer(user, password, bytes.fromhex(state), realm, src=src,
                                   rid='', how='test')
        else:
            d = daemon.auth.decide(user, password, realm, src=src, rid='', how='test')
        store.radius_add({
            'ts': d.began, 'client': '%s (a test by %s)' % ((client or {}).get('name') or
                                                            'no client', by),
            'nas_ip': '', 'src': src, 'packet': 'Access-Request',
            'username': d.user or user, 'realm': d.realm, 'calling': '', 'called': '',
            'result': d.result, 'reason': d.reason, 'otp': d.otp, 'rid': '',
            'took_ms': int((time.time() - d.began) * 1000), 'attrs': '[]',
            'reply': json.dumps(d.reply), 'steps': json.dumps(d.steps), 'device': '',
            'tunnel': ''})
        return {'result': d.result, 'reason': d.reason, 'steps': d.steps, 'reply': d.reply,
                'user': d.user, 'realm': d.realm, 'how': 'direct', 'node': node_name(),
                'state': bytes(d.state).hex() if d.state else '', 'message': d.message}
    secret = str(b.get('secret') or '')
    if not secret:
        local = store.client_for('127.0.0.1')
        if not local:
            raise ApiError(400, 'there is no client for 127.0.0.1 to send the test from: add '
                           'one (the installer makes "localhost"), or give the secret')
        secret = local['_secret']
    port = int(b.get('port') or CONFIG.get('radius_auth_port') or 1812)
    server = str(b.get('server') or '127.0.0.1')
    code, words, took = radius_ask(server, port, secret, user, password,
                                   extra=[('State', '0x' + state)] if state else ())
    got_state = next((v for k, v in words if k == 'State'), '')
    row = store.db.row("SELECT id FROM radius_log WHERE username = ? ORDER BY id DESC "
                       "LIMIT 1", (Authenticator.full_name(
                           user, (store.client_for('127.0.0.1') or {}).get('realm', '')),))
    return {'result': {2: 'accept', 3: 'reject', 11: 'challenge'}.get(code, str(code)),
            'answer': words, 'took_ms': took, 'row': row['id'] if row else None,
            'how': 'udp', 'node': node_name(), 'cli': 'radtest %s %s %s %d <secret>' % (
                user, '******', server, port),
            'state': str(got_state)[2:] if str(got_state).startswith('0x') else '',
            'message': next((v for k, v in words if k == 'Reply-Message'), '')}


RADTEST_WAIT_S = 25


def radtest_elsewhere(store, node, by, src, b):
    alive = {n['name']: n for n in ha_nodes(store)}
    if node not in alive:
        raise ApiError(404, 'there is no node called %s' % node)
    if not alive[node].get('alive'):
        raise ApiError(409, '%s has not been heard from for %d s' % (
            node, int(alive[node].get('age') or 0)))
    ident = secrets.token_hex(8)
    ask = {'by': by, 'src': src, 'at': time.time(), 'from': node_name(),
           'user': str(b.get('user') or ''), 'how': str(b.get('how') or 'udp'),
           'client': b.get('client'), 'realm': str(b.get('realm') or ''),
           # The second window's answer goes with its State (1.0.84).
           'state': str(b.get('state') or '')[:600],
           'password': seal_secret(str(b.get('password') or ''), 'radtest:' + ident)}
    # Written straight into the other node's database (1.0.87), not left to
    # replication: one direction of it stopped, or behind, and the test was
    # never seen there. Replication only when that database cannot be
    # reached from here.
    k_ask = 'radtest:ask:%s:%s' % (node, ident)
    k_ans, k_took = 'radtest:answer:' + ident, 'radtest:taken:' + ident
    far, far_err = None, ''
    if CONFIG.get('ha_mode') == 'replicated':
        try:
            far = ha_peer_db()
        except Exception as e:                          # noqa: BLE001
            far_err = str(e).split('\n')[0][:200]
    where = far or store.db
    # Two tests waiting on the other node at most (1.0.101): each holds a
    # worker of the pages while it waits.
    if not RADTEST_PEER.acquire(False):
        if far:
            far.close()
        raise ApiError(429, 'tests on the other node are running already - try again in a '
                            'moment')
    try:
        where.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k_ask, json.dumps(ask)))
    except Exception:
        RADTEST_PEER.release()
        if far:
            far.close()
        raise
    t0 = time.time()

    def look(k):
        got = where.value('SELECT v FROM meta WHERE k = ?', (k,))
        return got if got is not None or where is store.db else store.get_meta(k)
    try:
        while time.time() - t0 < RADTEST_WAIT_S:
            got = look(k_ans)
            if got:
                out = json.loads(got)
                if out.get('error'):
                    raise ApiError(int(out.get('status') or 400), out['error'])
                return out
            time.sleep(0.3)
        raise ApiError(504, radtest_why_not(store, node, where, far_err, look(k_took), t0,
                                            look(k_ask) is not None))
    finally:
        RADTEST_PEER.release()
        for db in ((far, store.db) if far else (store.db,)):
            try:
                db.run('DELETE FROM meta WHERE k IN (?, ?, ?)', (k_ask, k_ans, k_took))
            except Exception:                           # noqa: BLE001
                pass
        if far:
            try:
                far.close()
            except Exception:                           # noqa: BLE001
                pass


RADTEST_PEER = threading.BoundedSemaphore(2)


def radtest_why_not(store, node, where, far_err, took, t0, still_there):
    """What the page says when the other node did not answer (1.0.87)."""
    beat = next((n for n in ha_nodes(store) if n['name'] == node), {})
    ver = str(beat.get('version') or '')
    if took:
        try:
            at = float(took) - t0
        except ValueError:
            at = 0
        return ('%s took the test %.1f s after it was asked, but did not finish it within %d s: '
                'the directory or the RADIUS port there answer slowly or not at all - its Log '
                'and Events say more' % (node, max(at, 0), RADTEST_WAIT_S))
    if where is not store.db:
        if still_there:
            return ('%s has the test in its database but did not take it within %d s: is otp '
                    'running there%s? (systemctl status otp, journalctl -u otp)' % (
                        node, RADTEST_WAIT_S, ' - it is %s, this is %s' % (ver, __version__)
                        if ver and ver != __version__ else ''))
        return '%s took the test but its answer did not come back within %d s' % (
            node, RADTEST_WAIT_S)
    rep = {}
    try:
        rep = ha_repl_state(store)
    except Exception:                                   # noqa: BLE001
        pass
    why = []
    if far_err:
        why.append('its database could not be reached from here (%s)' % far_err)
    if rep.get('mode') == 'replicated' and not rep.get('healthy'):
        why.append('the replication between the nodes is not running as it should - see '
                   'Settings → High availability')
    return '%s did not answer the test within %d s%s' % (
        node, RADTEST_WAIT_S, ': ' + '; '.join(why) if why else '')


def radtest_serve(daemon):
    """Tests the other node's pages asked of this one (1.0.45)."""
    store = daemon.store
    me = node_name()
    # The first characters of the key compared as they are (1.0.89). The
    # range k >= 'radtest:ask:otp2:' AND k < 'radtest:ask:otp2;' of 1.0.57
    # was empty in a database with a language's collation (en_US.UTF-8,
    # cs_CZ.UTF-8 - what PostgreSQL takes from the system), which leaves
    # ':' and ';' out of the first comparison: the other node never saw a
    # test asked of it. substr compares the characters, in both engines.
    lo = 'radtest:ask:%s:' % me
    rows = [r for r in store.db.rows('SELECT k, v FROM meta WHERE substr(k, 1, %d) = ?'
                                     % len(lo), (lo,))
            if r['k'].startswith(lo)]
    for r in rows:
        ident = r['k'].rsplit(':', 1)[1]
        # Taken once: the row out first, so a second look does not run it again.
        store.db.run('DELETE FROM meta WHERE k = ?', (r['k'],))
        try:
            # Seen and taken (1.0.87): the asking node says so if it waits too long.
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)',
                         ('radtest:taken:' + ident, repr(time.time())))
        except Exception:                               # noqa: BLE001
            pass
        try:
            ask = json.loads(r['v'] or '{}')
            if time.time() - float(ask.get('at') or 0) > RADTEST_WAIT_S:
                continue
            ask['password'] = unseal_secret(ask.get('password') or '', 'radtest:' + ident)
            out = radtest_do(store, daemon, '%s on %s' % (ask.get('by'), ask.get('from')),
                             ask.get('src') or '', ask)
        except ApiError as e:
            out = {'error': str(e), 'status': e.status}
        except Exception as e:                          # noqa: BLE001
            out = {'error': 'the test could not be made on %s: %s' % (me, e), 'status': 500}
        try:
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)',
                         ('radtest:answer:' + ident, json.dumps(out, default=str)))
        except Exception as e:                          # noqa: BLE001
            log('the answer to a test asked by the other node could not be written: %s' % e,
                'warn')


# ---- settings, accounts, events, the database --------------------------------------------
@route('GET', '/api/settings')
def _settings(h):
    s = h.me()
    full = s['role'] == 'fulladmin'
    return {'settings': h.d.settings_state(full), 'may_change': full, 'panes': PANES,
            'only_when': ONLY_WHEN, 'config_file': str(CONFIG_FILE),
            'database': h.store.db.where(), 'directories': [d['name'] for d in
                                                            h.store.directories()],
            'realms': [r['suffix'] for r in h.store.realms()
                       if r.get('suffix') and r['suffix'] != '*'],
            'isemon': h.d.shipper.state() if h.d.shipper else {},
            'node': node_name(), 'nodes': h.d.cluster_nodes(),
            'cluster': bool(CONFIG.get('ha_mode')) or len(h.d.cluster_nodes()) > 1}


@route('POST', '/api/settings')
def _settings_do(h):
    s = h.me('fulladmin')
    b = h.body()
    asked = b.get('settings') or {}
    moved = [k for k in asked if k in ('db_engine', 'db_host', 'db_port', 'db_name', 'db_user',
                                         'db_password') and
             not (k == 'db_password' and is_masked(asked[k])) and
             str(asked[k]) != str(CONFIG.get(k) if CONFIG.get(k) is not None else '')]
    ha = [k for k in asked if k in ('ha_mode', 'ha_slot', 'ha_peer', 'ha_peer_port', 'ha_address',
                                    'ha_tls', 'ha_tls_ca')
          and str(asked[k]) != str(CONFIG.get(k) if CONFIG.get(k) is not None else '')]
    if ha:
        # The cluster is made and taken apart by its own steps (1.0.57).
        raise ApiError(400, 'the cluster is changed on Settings - High availability or with '
                            'otp --ha-setup / --ha-join / --ha-standalone (%s not saved)'
                       % ', '.join(ha))
    if moved:
        # Saved here, the next restart opened a database nothing had been
        # carried into (1.0.37). The way to another one is the four steps.
        raise ApiError(400, 'the database is changed on Settings - The database with its own '
                            'steps: Try it, Set it up, Carry everything across, Start using it '
                            '(%s not saved)' % ', '.join(moved))
    try:
        return h.d.save_settings(asked, by=s['name'], node=b.get('node'),
                                 drawn_by=b.get('drawn_by'))
    except NodeMoved as e:
        raise ApiError(409, str(e))
    except BadSetting as e:
        raise ApiError(400, str(e))


@route('POST', '/api/isemon')
def _isemon_do(h):
    s = h.me('fulladmin')
    if not h.d.shipper:
        raise ApiError(503, 'nothing is being sent from this process')
    h.d.shipper.put('otp', 'daemon', 'a test from otp %s, sent by %s - isemon reads nothing '
                    'from this line' % (__version__, s['name']))
    h.d.shipper.flush(3)
    time.sleep(0.3)
    return {'isemon': h.d.shipper.state()}


@route('GET', '/api/users')
def _users(h):
    s = h.me()
    mfa = mfa_all(h.store)
    users = h.store.accounts()
    for u in users:
        u['mfa'] = mfa.get(str(u.get('name') or '').lower())
    return {'users': users, 'may_change': s['role'] == 'fulladmin',
            'mfa_on': bool(CONFIG.get('admin_2fa')),
            'roles': [{'role': r, 'words': ROLE_WORDS[r]} for r in ROLES_ALL]}


@route('POST', '/api/users')
def _users_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act, name = b.get('action'), str(b.get('name') or '').strip()
    who = s['name']
    if act == 'add':
        h.store.add_account(name, b.get('role') or 'readonly', b.get('password'),
                            note=b.get('note') or '', must_change=b.get('must_change', 1))
        h.store.add_event('accounts', '%s made the account %s (%s)' % (who, name,
                                                                         b.get('role')), who=who)
        return {'message': 'the account %s is made' % name}
    acc = h.store.account(name)
    if not name:
        raise ApiError(400, 'which account?')                          # 1.0.103
    if not acc:
        raise ApiError(404, 'there is no account called %s' % name)
    if act in ('delete', 'disable') or (act == 'role' and b.get('role') != 'fulladmin'):
        if acc['role'] == 'fulladmin' and not h.store.fulladmins_left(but=name):
            raise ApiError(400, 'that is the last full administrator who can sign in')
    if act == 'delete':
        h.store.drop_account(name)
        h.store.add_event('accounts', '%s removed the account %s' % (who, name), 'warn', who=who)
        return {'message': 'the account %s is gone' % name}
    if act == 'role':
        h.store.set_account(name, role=b.get('role'))
        h.store.add_event('accounts', '%s made %s %s' % (who, name,
                                                         ROLE_WORDS.get(b.get('role'))), who=who)
        return {'message': 'saved'}
    if act == 'mfa_reset':
        had = mfa_reset(h.store, acc['name'], who)
        h.store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                       ('admin', acc['name'].lower()))
        return {'message': ('the second step of %s is reset: they set it up again at the next '
                            'sign-in; their sign-ins are ended' if had else
                            '%s had no second step set up') % acc['name']}
    if act == 'reset_cols':
        h.store.put_user_cols(acc['name'], {})
        h.store.add_event('accounts', '%s put the columns of every table back as they come '
                          'for %s' % (who, acc['name']), who=who)
        return {'message': 'the columns of %s are back as they come; they see it at their '
                           'next page load' % acc['name']}
    if act == 'password':
        h.store.set_account(name, password=b.get('password'), must_change=int(bool(
            b.get('must_change', 1))))
        h.store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                       ('admin', name.lower()))
        h.store.add_event('accounts', '%s set a new password for %s; their sign-ins are ended'
                          % (who, name), 'warn', who=who)
        return {'message': 'the password is set'}
    if act in ('disable', 'enable'):
        h.store.set_account(name, disabled=1 if act == 'disable' else 0)
        if act == 'disable':
            h.store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                           ('admin', name.lower()))
        h.store.add_event('accounts', '%s switched %s %s' % (who, name, 'off' if
                                                            act == 'disable' else 'on'), who=who)
        return {'message': 'saved'}
    raise ApiError(400, 'no such thing to do to an account')


@route('GET', '/api/sessions')
def _sessions(h):
    h.me('fulladmin')
    # The list is of who could still ask: the ones that sat too long are
    # tidied first (1.0.15), not shown as signed in for hours.
    h.store.sessions_tidy(int(CONFIG.get('session_idle_min') or 120) * 60,
                          int(CONFIG.get('portal_session_min') or 15) * 60)
    return {'sessions': h.store.sessions()}


@route('POST', '/api/sessions')
def _sessions_do(h):
    s = h.me('fulladmin')
    ident = int(h.body().get('id') or 0)
    row = h.store.db.row('SELECT kind, name, ip FROM sessions WHERE id = ?', (ident,))
    if not row:
        # Gone already (1.0.61): not written down as "ended the sign-in of ?".
        raise ApiError(404, 'that sign-in has ended already')
    h.store.session_drop(ident)
    h.store.add_event('sign-ins', '%s ended the sign-in of %s%s' % (
        s['name'], (row or {}).get('name') or '?', (' from %s' % row['ip']) if row and
        row.get('ip') else ''), 'warn', who=s['name'])
    return {'message': 'ended'}


def time_span(h, lq):
    """The time picker's window (1.0.53), `from` and `to` as seconds since
    1970, added to what the search box asked."""
    since, until = h.num('from', 0, 0, 10 ** 11), h.num('to', 0, 0, 10 ** 11)
    parts, args = ([lq.sql] if lq.sql else []), list(lq.args or [])
    if since:
        parts.append('ts >= ?')
        args.append(since)
    if until:
        parts.append('ts < ?')
        args.append(until)
    lq.sql, lq.args = ' AND '.join('(%s)' % x for x in parts), args
    return since, until


@route('GET', '/api/events')
def _events(h):
    h.me()
    lq, bad = list_query('events', h.arg('q'))
    if bad:
        return {'rows': [], 'total': 0, 'q_error': bad, 'kinds': h.reader.event_kinds()}
    time_span(h, lq)
    rows, total = h.reader.events(h.num('limit', 100, 1, 1000), h.num('offset', 0),
                                 lq.words, h.arg('kind'), extra=(lq.sql, lq.args))
    return {'rows': rows, 'total': total, 'kinds': h.reader.event_kinds()}


@route('GET', '/api/enrolment')
def _enrolment(h):
    h.me()
    since = h.num('since', 0, 0, 10 ** 9)
    lq, bad = list_query('enrolment', h.arg('q'))
    if bad:
        return {'rows': [], 'total': 0, 'q_error': bad, 'counts': {}, 'on': True}
    t_from, t_to = time_span(h, lq)
    rows, total = h.store.enrolment(h.num('limit', 100, 1, 1000), h.num('offset', 0),
                                    lq.words, h.arg('step'), since, extra=(lq.sql, lq.args))
    return {'rows': rows, 'total': total,
            'counts': h.store.enrolment_counts(since, t_from, t_to),
            'on': bool(CONFIG.get('portal'))}


@route('GET', '/api/mail')
def _mail(h):
    h.me()
    return {'mode': CONFIG.get('mail_mode') or 'off', 'ca_list': describe_certificates(
        mail_ca_pem(h.store)), 'from': CONFIG.get('mail_from') or '',
        'sms_ca_list': describe_certificates(sms_ca_pem(h.store)),
        'lang': CONFIG.get('mail_lang') or 'cs', 'codes': bool(CONFIG.get('mail_codes'))}


@route('POST', '/api/mail')
def _mail_do(h):
    b = h.body()
    act = str(b.get('action') or '')
    if act == 'test':
        s = h.me('fulladmin')
        to = str(b.get('to') or '').strip()
        if not re.match(r'^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+\Z', to):
            raise ApiError(400, 'a mail address to send it to')
        began = time.time()
        try:
            lang = str(b.get('lang') or 'cs')
            if b.get('kind') == 'token':
                # A token's mail as it would go, with a key made up for it
                # (1.0.27): whether that gets through - pictures, codes and
                # all - is not the same question as whether a line of text
                # does. The key opens nothing.
                fake = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
                pic = h.d.tokens.picture('novak@example.cz', fake)
                msg = token_mail(to, 'novak@example.cz', pic,
                                 codes=['%08d' % secrets.randbelow(10 ** 8) for _ in range(5)],
                                 lang=lang if lang in MAIL_WORDS else 'cs',
                                 display='Jan Novák' if lang == 'cs' else 'John Doe',
                                 by=s['name'])
            elif b.get('kind') in ('code', 'verify'):
                # The mail of a sign-in code, or of checking an address on
                # the enrolment pages (1.0.78) - with a code that opens nothing.
                msg = code_message('mail', to, code_new(),
                                   'signin' if b.get('kind') == 'code' else 'verify',
                                   lang=lang if lang in CODE_TEXTS else None,
                                   name='novak@example.cz',
                                   display='Jan Novák' if lang == 'cs' else 'John Doe')
            else:
                msg = test_mail(to, lang)
            # Through the outgoing mail, as codes go (1.0.103): tried now, and
            # if the other side does not take it yet (greylisting) tried again
            # by itself - or straight, once, with every step said here.
            queued = str(b.get('via') or '') == 'queue'
            if queued:
                steps = mail_deliver(h.store, msg, [to], kind='test', by=s['name'],
                                     purpose='test')
            else:
                steps = mail_send(h.store, msg, [to])
        except MailError as e:
            h.store.add_event('mail', 'a test mail to %s failed: %s' % (to, e), 'warn',
                              who=s['name'])
            return {'sent': False, 'said': str(e), 'steps': e.steps,
                    'queued': getattr(e, 'queued', None) if str(b.get('via') or '') == 'queue'
                    else None,
                    'took_ms': int((time.time() - began) * 1000)}
        h.store.add_event('mail', '%s sent a test mail%s to %s%s' % (
            s['name'], {'token': ' shaped as a token\'s', 'code': ' shaped as a sign-in code\'s',
                        'verify': ' shaped as an address check\'s'}.get(b.get('kind'), ''), to,
            mail_reply_words(steps)), who=s['name'])
        return {'sent': True, 'said': 'sent to %s' % to, 'steps': steps,
                'queued': 'sent' if str(b.get('via') or '') == 'queue' else None,
                'took_ms': int((time.time() - began) * 1000)}
    if act == 'sms_test':
        # An SMS the way a sign-in code goes (1.0.76), with a code that opens
        # nothing, and what the gateway said.
        s = h.me('fulladmin')
        try:
            to = phone_checked(b.get('to'))
        except ValueError as e:
            raise ApiError(400, str(e))
        began = time.time()
        try:
            said = sms_send(to, code_message('sms', to, code_new(), 'verify'))
        except SmsError as e:
            h.store.add_event('settings', 'a test SMS to %s failed: %s' % (to, e), 'warn',
                              who=s['name'])
            return {'sent': False, 'said': str(e), 'took_ms': int((time.time() - began) * 1000)}
        h.store.add_event('settings', '%s sent a test SMS to %s' % (s['name'], to), who=s['name'])
        return {'sent': True, 'said': said, 'to': to,
                'took_ms': int((time.time() - began) * 1000)}
    if act == 'sms_ca':
        # The Teltonika gateway's certificates (1.0.89).
        s = h.me('fulladmin')
        mode = str(b.get('mode') or 'add')
        try:
            got = sms_ca_set(h.store, b.get('ca'), mode, str(b.get('fingerprint') or ''))
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('settings', '%s %s the certificates of the SMS gateway'
                          % (s['name'], {'add': 'added to', 'drop': 'took one out of'}.get(
                              mode, 'emptied')), who=s['name'])
        return {'ca_list': got, 'message': 'the SMS gateway is checked against %d certificate(s)'
                % len(got)}
    if act == 'tel_test':
        # The Teltonika tried without sending anything (1.0.113).
        s = h.me('fulladmin')
        began = time.time()
        got = tel_test()
        got['took_ms'] = int((time.time() - began) * 1000)
        bad = [x for x in got['steps'] if not x['ok']]
        h.store.add_event('settings', '%s tried the SMS gateway %s: %s' % (
            s['name'], got.get('host') or '?', 'it answers' if got['ok'] else
            (bad[0]['said'] if bad else 'it did not answer')), 'info' if got['ok'] else 'warn',
            who=s['name'])
        return got
    if act == 'sms_ca_fetch':
        # What the gateway shows, for the administrator to look at and trust.
        h.me('fulladmin')
        try:
            pem = tel_peer_chain()
        except SmsError as e:
            raise ApiError(502, str(e))
        return {'pem': pem, 'certs': describe_certificates(pem)}
    if act == 'ca':
        s = h.me('fulladmin')
        mode = str(b.get('mode') or 'add')
        try:
            got = mail_ca_set(h.store, b.get('ca'), mode, str(b.get('fingerprint') or ''))
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('settings', '%s %s the certificate authorities of the mail server'
                          % (s['name'], {'add': 'added to', 'drop': 'took one out of'}.get(
                              mode, 'emptied')), who=s['name'])
        return {'ca_list': got, 'message': 'the mail server keeps %d certificate(s)' % len(got)}
    if act == 'mail_of':
        # A person's mail address out of the directory of their realm, for
        # the box beside "Make a token" (1.0.20).
        h.me('tokenadmin')
        who = str(b.get('user') or '').strip()
        realm = h.store.realm_for(who)
        ad = h.d.dirs.get(str((realm or {}).get('directory') or '').lower())
        if not ad:
            return {'mail': '', 'display': ''}
        how = realm.get('lookup') if realm.get('lookup') in ('upn', 'sam') else (
            'upn' if '@' in who else 'sam')
        try:
            entry = ad.find_user(who if how == 'upn' else who.split('@', 1)[0], how)
        except Exception:
            entry = None
        return {'mail': (entry or {}).get('mail') or '', 'display': (entry or {}).get('display')
                or '', 'mobile': (entry or {}).get('mobile') or ''}
    raise ApiError(400, 'no such thing to do')


@route('GET', '/api/log')
def _log(h):
    h.me('fulladmin')
    return {'lines': log_tail(h.num('lines', 400, 10, 5000)), 'file': str(LOG_DIR / 'otp.log')}


def _db_files(h):
    db = h.store.db
    disk, grew, parts = db_disk(h.store)
    return {'copies': kept_copies(), 'dumps': kept_dumps(db.engine), 'dump': dump_info(db.engine),
            'keep': int(CONFIG.get('backup_keep') or 14), 'disk': disk, 'growth': grew,
            'parts': parts, 'cache': db_cache(h.store), 'drivers': drivers_state(),
            'erasable': db_erasable(h.store), 'tune': tune_state(h.store),
            'backup_dir': str(BACKUP_DIR), 'dump_dir': str(DUMP_DIR)}


@route('GET', '/api/db')
def _db(h):
    h.me()
    db = h.store.db
    files = _db_files(h)
    return dict(files, **{'engine': db.engine, 'words': ENGINE_WORDS.get(db.engine), 'where': db.where(),
            'version': db.version(), 'size': db.size(), 'free': db_free_inside(db),
            'counts': h.store.counts(), 'tables': db_table_sizes(db), 'backups': backups(),
            'key': str(sealing_key_path()), 'key_there': bool(sealing_key()),
            'config_file': str(CONFIG_FILE), 'job': job_read(), 'node': node_name(),
            'tuned': bool(json.loads(h.store.get_meta('tune_before:' + node_name()) or '{}')),
            'retain': {k: CONFIG.get(k) for k in ('retain_radius_days', 'retain_otp_days',
                                                    'retain_events_days')}})


def _kept_path(name, kind):
    name = os.path.basename(str(name or ''))
    if not NAME_RE.match(name):
        raise ApiError(404, 'there is no such file')
    folder = DUMP_DIR if kind == 'dump' else BACKUP_DIR
    path = folder / name
    if not path.is_file():
        raise ApiError(404, 'there is no such file: %s' % name)
    return path


def copy_with_key(src_path, dst_path, key_hex):
    """A copy with the key that opens its tokens written into its first line."""
    import gzip
    if not re.match(r'^[0-9a-f]{64}\Z', str(key_hex or '')):
        raise ApiError(409, 'the key beside the copy does not read')
    with gzip.open(str(src_path), 'rt', encoding='utf-8') as src, \
            gzip.open(str(dst_path), 'wt', encoding='utf-8') as dst:
        head = json.loads(src.readline())
        head['key'] = key_hex
        dst.write(json.dumps(head, default=str) + '\n')
        shutil.copyfileobj(src, dst, 1 << 20)


@route('GET', '/api/db/download')
def _db_download(h):
    s = h.me('fulladmin')
    # Made by the page's question first (1.0.123): the file with its key,
    # waiting for this one browser - the passphrase never in an address.
    if h.arg('ticket'):
        v = dbkey_ticket_take(h.arg('ticket'), s['name'])
        if not v:
            raise ApiError(404, 'that download is not waiting any more: ask for it again')
        try:
            h.send_file(v['path'], v['name'])
        finally:
            shutil.rmtree(str(v['dir']), ignore_errors=True)
        return None
    name, kind = h.arg('name'), h.arg('kind')
    if name:
        path = _kept_path(name, kind)
        h.store.add_event('backups', '%s downloaded %s, without the key that opens its tokens'
                          % (s['name'], path.name), who=s['name'])
        h.send_file(path, path.name)
        return None
    # Made now, for the machine somebody is sitting at, and not kept here.
    tmp = Path(tempfile.mkdtemp(prefix='otp-download-', dir=str(STATE_DIR)))
    try:
        path = _db_made_now(h, kind, tmp)
        h.store.add_event('backups', '%s downloaded %s, made for it, without the key that opens '
                          'its tokens' % (s['name'], path.name), who=s['name'])
        h.send_file(path, path.name)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return None


def _db_made_now(h, kind, folder):
    if kind == 'dump':
        return make_dump(h.store, 'download', folder=folder)
    path = Path(folder) / ('otp-copy-%s-download.json.gz' % _stamp())
    dump_tables(h.store.db, path)
    return path


def _db_download_ticket(h, s, b):
    """The file asked for - kept or made now - with the key that opens its
    tokens, locked with the passphrase given: made, and left for the browser
    to fetch with the ticket."""
    by = s['name']
    dbkey_passphrase_checked(b.get('passphrase'))
    kind = 'dump' if b.get('kind') == 'dump' else ''
    work = Path(tempfile.mkdtemp(prefix='otp-dl-', dir=str(STATE_DIR)))
    os.chmod(str(work), 0o700)
    try:
        if b.get('name'):
            src = _kept_path(b.get('name'), kind)
            keyf = _key_beside(src)
            # The key beside a kept one is the one that opens it - the one in
            # use now may be newer.
            if keyf.is_file() and sealing_key() and \
                    keyf.read_text().strip() != sealing_key().hex():
                raise ApiError(409, 'the key beside %s is not the one in use now: download it '
                                    'without the key, and the .key beside it from the machine'
                                    % src.name)
        else:
            src = _db_made_now(h, kind, work)
        out = dbkey_bundle(src, src.name, b.get('passphrase'), work)
        if src.parent == work:
            src.unlink()
    except ApiError:
        shutil.rmtree(str(work), ignore_errors=True)
        raise
    except ValueError as e:
        shutil.rmtree(str(work), ignore_errors=True)
        raise ApiError(400, str(e))
    h.store.add_event('backups', '%s downloaded %s WITH the key that opens its tokens, locked with '
                      'a passphrase' % (by, out.name), 'warn', who=by)
    return {'ticket': dbkey_ticket_put(out, out.name, by), 'name': out.name}


@route('POST', '/api/db/restore')
def _db_restore(h):
    s = h.me('fulladmin')
    fd, tmp = tempfile.mkstemp(prefix='otp-upload-', dir=str(STATE_DIR))
    os.close(fd)
    tmp = Path(tmp)
    try:
        h.body_to_file(tmp, 4 * 1024 ** 3)
        if dbkey_is_bundle(tmp):
            # With its key, locked (1.0.123): kept here, opened with the
            # passphrase once it is given.
            work = Path(tempfile.mkdtemp(prefix='otp-peek-', dir=str(STATE_DIR)))
            try:
                inner, _k, head = dbkey_open(tmp, work)
                said, why = db_file_peek(inner, h.store.db.engine)
            except ValueError as e:
                raise ApiError(400, str(e))
            finally:
                shutil.rmtree(str(work), ignore_errors=True)
            if said is None:
                raise ApiError(400, why)
            return {'says': said, 'upload': dbkey_keep_upload(tmp), 'locked': True,
                    'file': head.get('file')}
        if h.arg('check'):
            said, why = db_file_peek(tmp, h.store.db.engine)
            if said is None:
                raise ApiError(400, why)
            return {'says': said}
        try:
            got = db_file_restore(h.store, tmp, s['name'], from_name='the page')
        except ValueError as e:
            raise ApiError(400, str(e))
        h.d.reload_all('a database was put back') if hasattr(h.d, 'reload_all') else None
        BIND_STRICT['tokens'] = False
        bind_tokens(h.store)
        return got
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


@route('POST', '/api/db')
def _db_do(h):
    s = h.me('fulladmin')
    act = h.body().get('action')
    if act == 'backup':
        out = make_backup(h.store, 'by %s' % s['name'])
        return {'message': 'a copy was made: %s' % out.name}
    if act == 'tidy':
        return {'message': 'tidied: %s' % h.store.tidy()}
    b = h.body()
    if act == 'job':
        return {'job': job_read()}
    if act == 'dump':
        try:
            out = make_dump(h.store, 'by-hand')
        except ValueError as e:
            raise ApiError(400, str(e))
        return {'name': out.name, 'bytes': out.stat().st_size,
                'message': 'made: %s' % out.name}
    if act == 'download_ticket':
        return _db_download_ticket(h, s, b)
    if act == 'upload_restore':
        try:
            src = dbkey_upload(b.get('upload'))
        except ValueError as e:
            raise ApiError(400, str(e))
        passphrase = str(b.get('passphrase') or '')
        if b.get('check'):
            work = Path(tempfile.mkdtemp(prefix='otp-peek-', dir=str(STATE_DIR)))
            os.chmod(str(work), 0o700)
            try:
                inner, _k, _head = dbkey_open(src, work, passphrase)
                said, why = db_file_peek(inner, h.store.db.engine)
            except ValueError as e:
                raise ApiError(400, str(e))
            finally:
                shutil.rmtree(str(work), ignore_errors=True)
            if said is None:
                raise ApiError(400, why)
            said['with_key'] = True
            return {'says': said}
        # Put back as a job the page follows (1.0.123): a big database takes
        # longer than a page waits for an answer.
        store, daemon, by = h.store, h.d, s['name']

        def work_(progress):
            work = Path(tempfile.mkdtemp(prefix='otp-putback-', dir=str(STATE_DIR)))
            os.chmod(str(work), 0o700)
            try:
                progress(1, 3, 'the file opened with its passphrase')
                inner, keyf, head = dbkey_open(src, work, passphrase)
                progress(2, 3, 'put back')
                got = db_file_restore(store, inner, by, key_file=keyf,
                                      from_name=head.get('file') or 'a file with its key')
                progress(3, 3, 'done')
                try:
                    daemon.reload_all('a database was put back')
                except Exception:                       # noqa: BLE001
                    pass
                BIND_STRICT['tokens'] = False
                bind_tokens(store)
                return got
            finally:
                shutil.rmtree(str(work), ignore_errors=True)
                try:
                    src.unlink()
                except OSError:
                    pass
        try:
            db_job('putting a database back with its key', work_)
        except ValueError as e:
            raise ApiError(409, str(e))
        return {'message': 'the database is being put back', 'job': job_read()}
    if act in ('restore_kept', 'delete'):
        path = _kept_path(b.get('name'), b.get('kind'))
        if act == 'delete':
            for f in (path, _key_beside(path)):
                try:
                    f.unlink()
                except OSError:
                    pass
            h.store.add_event('backups', '%s deleted %s' % (s['name'], path.name), 'warn',
                              who=s['name'])
            return {'message': '%s is deleted' % path.name}
        if b.get('check'):
            said, why = db_file_peek(path, h.store.db.engine)
            if said is None:
                raise ApiError(400, why)
            return {'says': said}
        try:
            got = db_file_restore(h.store, path, s['name'], key_file=_key_beside(path),
                                  from_name=path.name)
        except ValueError as e:
            raise ApiError(400, str(e))
        if hasattr(h.d, 'reload_all'):
            h.d.reload_all('a database was put back')
        BIND_STRICT['tokens'] = False
        bind_tokens(h.store)
        return got
    if act == 'erase':
        try:
            return {'job': db_erase_job(h.store, list(b.get('groups') or []),
                                        bool(b.get('tidy')), s['name'])}
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'tune_restart':
        try:
            return tune_restart(h.store, s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
    if CONFIG.get('ha_mode') and act in ('move', 'use', 'empty'):
        raise ApiError(409, 'this node is one of a cluster: its database is not moved from here '
                            '(switch the replication off first - Settings → High availability)')
    try:
        if act in ('try', 'setup', 'empty', 'move', 'use'):
            c = engine_asked(b.get('settings') or {})
            words = ENGINE_WORDS.get(c['db_engine'])
            if act == 'try':
                got = db_try(c)
                got['in_use'] = same_database(c, h.store.db)
                return got
            if act == 'setup':
                if c['db_engine'] == 'sqlite':
                    raise ApiError(400, 'the file on this machine needs no setting up')
                first = db_try(c) if c.get('db_password') else {'reached': False}
                fresh = ''
                if first.get('reached') and first.get('writable'):
                    made = ['the database and the account are there already, and it gets in']
                else:
                    who = str(b.get('admin_user') or '').strip()
                    if not who:
                        raise ApiError(400, 'an administrator of that server is needed to make '
                                            'a database and an account on it')
                    if not c.get('db_password'):
                        fresh = c['db_password'] = db_password_made()
                    made = db_make(c, who, str(b.get('admin_password') or ''))
                keep = {k: c[k] for k in DB_KEYS if k != 'db_engine'}
                write_file_settings(keep)
                far = db_open(c)
                try:
                    far.make_tables()
                    far.add_missing_columns()
                finally:
                    far.close()
                got = db_try(c)
                h.store.add_event('settings', '%s set up %s at %s' % (s['name'], words,
                                                                       db_where(c)), who=s['name'])
                return {'made': made, 'password': fresh, 'kept_in': str(CONFIG_FILE),
                        'try': got, 'message': '%s at %s is ready' % (words, db_where(c))}
            if same_database(c, h.store.db) and act in ('empty', 'move'):
                raise ApiError(400, 'that is the database in use; this only ever touches the '
                                    'other one')
            if act == 'empty':
                got = db_try(c)
                if not got.get('reached'):
                    raise ApiError(400, got.get('trouble') or 'it cannot be reached')
                gone = db_empty(c)
                h.store.add_event('settings', '%s emptied %s at %s' % (s['name'], words,
                                                                        db_where(c)), 'warn',
                                  who=s['name'])
                return {'message': 'emptied: %d table(s) thrown away' % len(gone)}
            if act == 'move':
                got = db_try(c)
                if not got.get('reached'):
                    raise ApiError(400, got.get('trouble') or 'it cannot be reached')
                if not got.get('writable'):
                    raise ApiError(400, 'that account may not write to it')
                if got.get('rows'):
                    raise ApiError(400, 'there are %d record(s) in it already. Moving into a '
                                        'database that is not empty would mix two '
                                        'installations; empty it first if it really is spare.'
                                   % got['rows'])
                return {'job': db_move(h.store, c, s['name'])}
            if act == 'use':
                if same_database(c, h.store.db):
                    raise ApiError(400, 'that is the database in use already')
                got = db_try(c)
                if not got.get('reached'):
                    raise ApiError(400, got.get('trouble') or 'it cannot be reached')
                if not got.get('rows') and not b.get('even_empty'):
                    raise ApiError(400, 'it is empty: carry everything across first')
                # An older copy is not taken for this one (1.0.37): going back
                # to a database left behind by an earlier move opened what it
                # held then, and everything since was out of sight.
                if not b.get('even_older'):
                    try:
                        far = db_open(c)
                        try:
                            there = float(far.value('SELECT MAX(ts) FROM events') or 0)
                        finally:
                            far.close()
                        here = float(h.store.db.value('SELECT MAX(ts) FROM events') or 0)
                    except Exception:                   # noqa: BLE001
                        there = here = 0
                    if there and here and there < here - 60:
                        raise ApiError(409, 'it holds an older copy: its newest event is from '
                                            '%s, this one\'s from %s. Empty it and carry '
                                            'everything across first, so nothing written '
                                            'since is left behind.' % (
                                                datetime.fromtimestamp(there).strftime(
                                                    '%d-%m-%Y %H:%M'),
                                                datetime.fromtimestamp(here).strftime(
                                                    '%d-%m-%Y %H:%M')))
                write_file_settings({k: c[k] for k in DB_KEYS})
                h.store.add_event('settings', '%s switched the database to %s at %s; the '
                                  'daemon starts again on it' % (s['name'], words, db_where(c)),
                                  'warn', who=s['name'])
                log('the database is now %s; starting again on it' % db_where(c), 'warn')
                # systemd starts it again (Restart=always), on the new one.
                threading.Timer(1.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
                return {'message': 'the daemon starts again on %s in a moment' % words,
                        'restarting': True}
        if act == 'check':
            own = db_own(h.store)
            try:
                got = db_check(own or h.store.db)
            finally:
                if own:
                    own.close()
            h.store.add_event('settings', '%s checked the database: %s' % (
                s['name'], 'nothing broken' if got['ok'] else 'TROUBLE'),
                'info' if got['ok'] else 'warn', who=s['name'])
            return got
        if act == 'statistics':
            own = db_own(h.store)
            try:
                return {'message': db_statistics(own or h.store.db)}
            finally:
                if own:
                    own.close()
        if act == 'give_back':
            by = s['name']

            def work(progress):
                got = db_give_back(h.store, progress)
                h.store.add_event('settings', '%s gave the disk back: %s -> %s'
                                  % (by, got['before'], got['after']), who=by)
                return got
            return {'job': db_job('giving the disk back', work)}
        if act == 'prune':
            days = 0 if b.get('everything') else int(b.get('days') or 0)
            if days < 1 and not b.get('everything'):
                raise ApiError(400, 'older than how many days? 1 at least')
            gone = db_prune(h.store, days)
            h.store.add_event('settings', '%s forgot the requests and checks older than %d '
                              'day(s): %s' % (s['name'], days, gone), 'warn', who=s['name'])
            return {'message': 'forgotten: %d request(s), %d check(s) of a code'
                    % (gone['radius_log'], gone['otp_log'])}
        if act == 'tune_plan':
            return tune_plan_for(h.store, b.get('machine') or {})
        if act == 'tune_apply':
            return tune_apply(h.store, b.get('machine') or {}, str(b.get('admin_user') or ''),
                              str(b.get('admin_password') or ''), s['name'])
        if act == 'tune_undo':
            return tune_undo(h.store, str(b.get('admin_user') or ''),
                             str(b.get('admin_password') or ''), s['name'])
    except ApiError:
        raise
    except ValueError as e:
        raise ApiError(400, str(e))
    except Exception as e:
        raise ApiError(400, str(e).split('\n')[0][:300])
    raise ApiError(400, 'no such thing to do to the database')


@route('GET', '/api/export')
def _export(h):
    s = h.me('fulladmin')
    whole = h.arg('secrets') == '1'
    out = config_export(h.store, whole)
    if whole:
        # Locked with a passphrase made here (1.0.136), as the cluster's
        # bundle is: the file leaves this machine with every shared secret,
        # password and private key in it.
        phrase = ha_passphrase()
        h.store.add_event('settings', 'the configuration was exported with the secrets in it '
                          '(locked with a passphrase)', 'warn', who=s['name'])
        return {'bundle': bundle_lock({'config': out}, phrase, kind=CONFIG_BUNDLE_KIND),
                'passphrase': phrase}
    return {'config': out}


@route('POST', '/api/import')
def _import(h):
    s = h.me('fulladmin')
    conf = h.body().get('config') or {}
    if isinstance(conf, dict) and conf.get('kind') == CONFIG_BUNDLE_KIND:
        try:
            conf = bundle_open(conf, str(h.body().get('passphrase') or ''),
                               kinds=(CONFIG_BUNDLE_KIND,)).get('config') or {}
        except ValueError as e:
            raise ApiError(400, str(e))
    if isinstance(conf, dict) and isinstance(conf.get('config'), dict):
        conf = conf['config']           # the command line's file, whole (1.0.62)

    def not_me_out(acc):
        access_not_me_out(h, h.store, acc, {})
    said = config_import(h.store, h.d, conf, s['name'], keep_account=s['name'],
                         access_check=not_me_out, replace=bool(h.body().get('replace')))
    return {'message': 'imported: %s%s' % (
        ', '.join('%s %d' % kv for kv in sorted(said.items()) if ':' not in kv[0]) or 'nothing',
        ''.join('; %d %s' % (v, k) for k, v in sorted(said.items()) if ':' in k)),
            'imported': dict(said)}


# ---- the whole configuration as one file (1.0.62) ------------------------------------
# Everything that is set up rather than recorded: the settings (those of each
# node too), the RADIUS clients, the realms, the directories, the accounts of
# the pages, the certificates and keys of the pages and the web address, the
# web address itself, who may reach which page, the firewall and the mail
# server's authorities. Not the tokens - they are in the copies of the
# database. With the secrets it carries what opens all of it in the clear.
CONFIG_FORMAT = 2
CONFIG_BUNDLE_KIND = 'otp-config-locked'


def config_export(store, whole):
    settings = store.settings_saved()
    # Secrets kept in the database are sealed with this machine's key
    # (1.0.33): exported as they are, they came back sealed twice and opened
    # nowhere. Opened for an export with the secrets, left out otherwise.
    for k in list(settings):
        base = k.split('@', 1)[0]
        if base in SEALED_KEYS:
            if whole and settings[k]:
                settings[k] = unseal_secret(settings[k]) or ''
            else:
                settings.pop(k)
    accounts = []
    for a in store.db.rows('SELECT name, role, pw, source, disabled, must_change, note, display, '
                           'dn, group_list, prefs, cols FROM accounts ORDER BY name'):
        a = dict(a)
        if not whole:
            a.pop('pw', None)
        accounts.append(a)
    tls = {}
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'web:tls:%'"):
        try:
            prof = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        for kk in ('key', 'pending_key'):
            if prof.get(kk):
                if whole:
                    prof[kk] = unseal_secret(prof[kk], 'web:tls') or ''
                else:
                    prof.pop(kk)
        tls[r['k'][len('web:tls:'):]] = prof

    def meta_json(k):
        try:
            return json.loads(store.get_meta(k) or 'null')
        except ValueError:
            return None
    return {'otp': __version__, 'made': time.time(), 'format': CONFIG_FORMAT,
            'node': node_name(), 'secrets': bool(whole),
            'settings': settings,
            'clients': store.clients(with_secret=whole, last=False),
            'realms': store.realms(),
            'directories': store.directories(with_secret=whole, last=False),
            'accounts': accounts,
            'web': {'tls': tls, 'access': meta_json('web:access'), 'vip': meta_json('web:vip')},
            'firewall': meta_json('fw:conf'),
            'mail_ca': mail_ca_pem(store),
            'sms_ca': sms_ca_pem(store),
            'logo': (lambda o: {k: o.get(k) for k in ('type', 'b64', 'name')}
                     if o else None)(logo_read(store, 'portal')),
            'art': art_read(store, 'portal'),
            'admin_logo': (lambda o: {k: o.get(k) for k in ('type', 'b64', 'name')}
                           if o else None)(logo_read(store, 'admin')),
            'admin_art': art_read(store, 'admin')}


def config_import(store, daemon, conf, by, keep_account='', access_check=None, nodes_as=None,
                  replace=False):
    """A configuration file put in. Checked whole before anything is saved;
    whatever was saved is in use even where something after it stopped.
    Returns what was imported, counted."""
    if not isinstance(conf, dict):
        raise ApiError(400, 'the configuration is not an object')
    for part in ('directories', 'realms', 'clients', 'accounts'):
        if not isinstance(conf.get(part) or [], list) or \
                not all(isinstance(x, dict) for x in conf.get(part) or []):
            raise ApiError(400, '%s is not a list of objects' % part)
    for part in ('settings', 'web', 'firewall'):
        if not isinstance(conf.get(part) or {}, dict):
            raise ApiError(400, '%s is not an object' % part)
    # Checked before anything is saved (1.0.44): a realm naming a directory
    # that neither is here nor comes with it stopped the import halfway.
    dirs = set(x['name'].lower() for x in store.directories()) | \
        set(str(d.get('name') or '').lower() for d in conf.get('directories') or [])
    for r in conf.get('realms') or []:
        if r.get('directory') and str(r['directory']).lower() not in dirs:
            raise ApiError(400, 'the realm %s names the directory %s, which is neither here '
                                'nor in the file - nothing was imported'
                           % (r.get('name'), r['directory']))
    web = conf.get('web') or {}
    access = None
    if web.get('access'):
        access = access_checked_api(web['access'])
        if access_check:
            access_check(access)
    # The certificates of the pages: a node of this cluster keeps its own
    # name; a file of one other machine's (a new machine put in its place)
    # is this node's.
    tls_in = web.get('tls') or {}
    if not isinstance(tls_in, dict):
        raise ApiError(400, 'web.tls is not an object')
    here = set(tls_targets(store))
    mapping = dict(nodes_as or {})
    src = str(conf.get('node') or '')
    if src and src not in here and src not in mapping and not CONFIG.get('ha_mode'):
        mapping[src] = node_name()      # the file of the machine this one replaces
    foreign = [t for t in tls_in if t != 'vip' and t not in here and t not in mapping]
    if len(foreign) == 1 and len([t for t in tls_in if t != 'vip']) == 1:
        mapping[foreign[0]] = node_name()
    fw = conf.get('firewall') or None
    rules_left_out = 0
    if fw:
        rules = []
        for r in fw.get('rules') or []:
            if not isinstance(r, dict):
                raise ApiError(400, 'a firewall rule is not an object')
            # A rule of one node, named as this machine names it (1.0.146): one of
            # a node this machine does not have stopped the whole import.
            r = dict(r)
            if r.get('scope') in mapping:
                r['scope'] = mapping[r['scope']]
            try:
                one = fw_rule_checked(r, store)
            except ApiError as e:
                if 'no node' not in str(e):
                    raise
                rules_left_out += 1
                continue
            for k in ('id', 'scope', 'disabled'):
                if k in r:
                    one[k] = r[k]
            rules.append(one)
        fw = dict(fw, rules=rules, off=[k for k in (fw.get('off') or [])
                                         if k in FW_AUTO_OPTIONAL])
    for t, prof in tls_in.items():
        if not isinstance(prof, dict):
            raise ApiError(400, 'the TLS of %s is not an object' % t)
        for kk in ('cert', 'key', 'chain', 'root', 'pending_key', 'csr'):
            if prof.get(kk) is not None and not isinstance(prof.get(kk), str):
                raise ApiError(400, 'the TLS of %s: %s is not text' % (t, kk))
        # Checked as the page checks it (1.0.94): a word where a number
        # belongs stopped the web side being applied at all.
        try:
            prof.update(tls_policy_checked(prof))
        except (ValueError, TypeError) as e:
            raise ApiError(400, 'the TLS of %s in the file: %s' % (t, e))
    vip_in = web.get('vip')
    if isinstance(vip_in, dict) and vip_in.get('address'):
        try:
            vip_in.update(vip_checked(vip_in, store))
        except (ValueError, TypeError) as e:
            raise ApiError(400, 'the web address in the file: %s' % e)
    logos_in = {}
    for slot, k in (('portal', 'logo'), ('admin', 'admin_logo')):
        one = conf.get(k)
        if isinstance(one, dict) and one.get('b64'):
            try:
                logos_in[slot] = base64.b64decode(str(one['b64']), validate=True)
                logo_check(logos_in[slot])
            except (binascii.Error, ValueError) as e:
                raise ApiError(400, 'the picture of the sign-in in the file: %s' % e)
        elif one is not None and not isinstance(one, dict):
            raise ApiError(400, 'the picture of the sign-in in the file is not an object')
    pem = str(conf.get('mail_ca') or '').strip()
    if pem and not all(describe_certificate(b) for b in split_certificates(pem)):
        raise ApiError(400, 'the mail server\'s authorities in the file are not certificates')
    sms_pem = str(conf.get('sms_ca') or '').strip()
    if sms_pem and not all(describe_certificate(b) for b in split_certificates(sms_pem)):
        raise ApiError(400, 'the SMS gateway\'s certificates in the file are not certificates')

    said = collections.Counter()
    imported_keys = set()
    if rules_left_out:
        said['firewall rules left out: of a node not here'] = rules_left_out
    try:
        for d in conf.get('directories') or []:
            d = dict(d)
            old = store.directory(d.get('name'))
            d['id'] = old['id'] if old else None
            store.directory_save(d, by)
            said['directories'] += 1
        for r in conf.get('realms') or []:
            r = dict(r)
            old = next((x for x in store.realms() if x['name'] == r.get('name')), None)
            r['id'] = old['id'] if old else None
            store.realm_save(r, by)
            said['realms'] += 1
        for c in conf.get('clients') or []:
            c = dict(c)
            old = next((x for x in store.clients() if x['name'] == c.get('name')), None)
            c['id'] = old['id'] if old else None
            if is_masked(c.get('secret')) and not old:
                # Said, not left out without a word (1.0.103): an export without
                # its secrets cannot make a client its NAS would be answered by.
                said['clients left out: no shared secret in the file'] += 1
                continue
            store.client_save(c, by)
            said['clients'] += 1
        if conf.get('settings'):
            # Never what belongs to this machine alone (1.0.57): an imported
            # file switched the database or the cluster at the next restart.
            # A node's own value (key@node) comes too (1.0.62).
            want, per_node = {}, []
            for k, v in conf['settings'].items():
                base, _at, node = str(k).partition('@')
                if base not in DEFAULTS or base in FILE_ONLY_KEYS:
                    continue
                if node and (base not in NODE_KEYS or not re.match(r'^[A-Za-z0-9._-]{1,64}\Z', node)):
                    continue
                if base in SEALED_KEYS and str(v or '').startswith('sealed:'):
                    continue
                if node:
                    per_node.append((base, mapping.get(node, node), v))
                else:
                    want[base] = v
            if want:
                daemon.save_settings(want, by)
                said['settings'] += len(want)
            # A node's own after the shared ones (1.0.146): on a machine of its
            # own a node's value is kept as the plain key, and the file's shared
            # value saved after it wrote over it.
            for base, node, v in per_node:
                try:
                    daemon.save_settings({base: v}, by, node=node)
                    said['settings'] += 1
                    imported_keys.update((base, '%s@%s' % (base, node)))
                except BadSetting:
                    pass            # a node this cluster does not have
        for a in conf.get('accounts') or []:
            name = str(a.get('name') or '').strip()
            if not name or name.lower() == str(keep_account or '').lower():
                continue                # never the one importing: not shut out by a file
            if not ACCOUNT_NAME_RE.match(name):
                continue                # a name the pages would not take (1.0.101)
            role = str(a.get('role') or 'readonly')
            if role not in ROLES_ALL:
                continue
            fields = {'role': role, 'disabled': int(bool(a.get('disabled'))),
                      'must_change': int(bool(a.get('must_change'))),
                      'note': str(a.get('note') or '')[:400],
                      'display': str(a.get('display') or ''), 'dn': str(a.get('dn') or ''),
                      'group_list': str(a.get('group_list') or ''),
                      'source': str(a.get('source') or 'local')}
            pw = a.get('pw')
            # Only a password's hash as this program makes it: never text
            # taken for one.
            if not (isinstance(pw, str) and pw.startswith('pbkdf2_sha256$')):
                pw = ''
            old = store.account(name)
            if old:
                if isinstance(pw, str) and pw:
                    fields['pw'] = pw
                store.db.run('UPDATE accounts SET %s WHERE id = ?' % ', '.join(
                    '%s = ?' % k for k in fields), tuple(fields.values()) + (old['id'],))
                if (fields.get('pw') and fields['pw'] != old.get('pw')) or fields['disabled'] or \
                        fields['role'] != old.get('role'):
                    # Its sign-ins ended (1.0.101), as a password set on the
                    # pages ends them: the old password's sessions went on.
                    store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                                 ('admin', name.lower()))
            else:
                if fields['source'] == 'local' and not (isinstance(pw, str) and pw):
                    # Without its password (an export without the secrets): made,
                    # switched off, until somebody gives it one.
                    fields['disabled'] = 1
                    said['accounts switched off: no password in the file'] += 1
                store.db.run('DELETE FROM meta WHERE k = ?', ('adm2fa:' + name.lower(),))
                store.db.insert('accounts', dict(fields, name=name, pw=pw or '',
                                                 created=time.time(), last_in=None,
                                                 last_from='', prefs=str(a.get('prefs') or '{}')))
            said['accounts'] += 1
        for t, prof in tls_in.items():
            prof = dict(prof)
            for kk in ('key', 'pending_key'):
                if prof.get(kk):
                    prof[kk] = seal_secret(prof[kk], 'web:tls')
                else:
                    prof.pop(kk, None)
            target = mapping.get(t, t)
            if not prof.get('key') and (_json_meta(store, 'web:tls:' + target) or {}).get('key'):
                # A file without the secrets does not take a key away.
                prof['key'] = _json_meta(store, 'web:tls:' + target)['key']
            tls_save(store, target, prof, by)
            said['certificates'] += 1
        if access is not None:
            fw_trial_begin(store, by)
            store.set_meta('web:access', json.dumps(dict(access, at=time.time(), by=by)))
            said['page access'] += 1
        if isinstance(web.get('vip'), dict):
            vip = dict(web['vip'])
            if not CONFIG.get('ha_mode'):
                vip['on'] = False       # a web address is a cluster's
            store.set_meta('web:vip', json.dumps(dict(vip, at=time.time(), by=by)))
            said['web address'] += 1
        if fw is not None:
            fw_trial_begin(store, by)
            store.set_meta('fw:conf', json.dumps(dict(fw, at=time.time(), by=by)))
            said['firewall'] += 1
        if pem:
            store.set_meta(MAIL_CA_META, '\n'.join(split_certificates(pem)))
            said['mail authorities'] += 1
        if sms_pem:
            store.set_meta(SMS_CA_META, '\n'.join(split_certificates(sms_pem)))
            said['SMS gateway certificates'] += 1
        for slot, k, ak in (('portal', 'logo', 'art'), ('admin', 'admin_logo', 'admin_art')):
            if slot in logos_in:
                logo_set(store, slot, logos_in[slot], by, str(conf[k].get('name') or ''))
            elif k in conf and replace and logo_read(store, slot):
                logo_set(store, slot, b'', by)
            want = conf.get(ak)
            if slot == 'admin' and want is None and isinstance(conf.get('art'), dict) \
                    and conf['art'].get('admin'):
                want = conf['art']                      # a file from 1.0.71
                if 'admin' not in logos_in and 'portal' in logos_in:
                    logo_set(store, 'admin', logos_in['portal'], by,
                             str((conf.get('logo') or {}).get('name') or ''))
            if isinstance(want, dict) and want.get('art') in ART_NAMES:
                try:
                    art_set(store, slot, want['art'])
                except ValueError:
                    art_set(store, slot, ART_SLOTS[slot][2])
                said['sign-in pictures'] += 1
        if replace:
            # The file as the whole of it (1.0.62): what is here and not in
            # the file goes - the clients, realms, directories and accounts
            # (never the one importing), and the settings back to their
            # defaults. Realms before the directories they name.
            def names(part):
                return set(str(x.get('name') or '').lower() for x in conf.get(part) or [])
            for c in store.clients():
                if c['name'].lower() not in names('clients'):
                    store.client_drop(c['id'])
                    said['clients taken away'] += 1
            for r in store.realms():
                if r['name'].lower() not in names('realms'):
                    store.realm_drop(r['id'], force=True)
                    said['realms taken away'] += 1
            for d in store.directories():
                if d['name'].lower() not in names('directories'):
                    store.directory_drop(d['id'])
                    said['directories taken away'] += 1
            if 'accounts' in conf:
                for a in store.db.rows('SELECT name FROM accounts'):
                    if a['name'].lower() not in names('accounts') and \
                            a['name'].lower() != str(keep_account or '').lower():
                        store.drop_account(a['name'])
                        said['accounts taken away'] += 1
            if 'settings' in conf:
                have = set(str(k) for k in (conf.get('settings') or {})) | imported_keys
                for k in list(store.settings_saved()):
                    base = k.split('@', 1)[0]
                    if k not in have and base in DEFAULTS and base not in FILE_ONLY_KEYS and \
                            not (base in SEALED_KEYS and conf.get('secrets') is not True):
                        store.drop_setting(k)
                        said['settings back to default'] += 1
    except (ValueError, BadSetting) as e:
        if said:
            raise ApiError(400, '%s - imported before it stopped: %s' % (e, ', '.join(
                '%s %d' % kv for kv in sorted(said.items()))))
        raise
    finally:
        # Whatever was saved is in use, even when something after it was not
        # (1.0.44).
        if said:
            try:
                daemon.changed('all')
                # Read in here too (1.0.62): a setting put back to its default
                # stayed at the old value in this process until a restart.
                daemon.reload_all('a configuration was imported')
            except Exception:                           # noqa: BLE001
                bump(store)
            store.add_event('settings', '%s imported a configuration: %s' % (by, dict(said)),
                            who=by)
    if not said:
        raise ApiError(400, 'there is nothing in this file to import - is it an export of otp?')
    return said


# ---- the enrolment pages -------------------------------------------------------------
def portal_me(h):
    s = h.session('portal')
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    # Switched off while somebody was signed in, it is off for them too (1.0.33).
    if not CONFIG.get('portal'):
        h.store.session_end(h.headers.get('X-Otp-Session'))
        raise ApiError(403, 'enrolling a token here is switched off')
    return s


# The pictures of the two sign-ins (1.0.71; each its own since 1.0.72):
# which one ({art, sha}) and a picture of the site's own (JSON with base64).
ART_SLOTS = {'portal': ('portal:art', 'portal:logo', 'phone'),
             'admin': ('admin:art', 'admin:logo', 'radius')}
LOGO_META = 'portal:logo'
LOGO_MAX = 512 * 1024
ART_NAMES = ('phone', 'radius', 'authapp', 'totp', 'otpcode', 'twostep', 'vpn', 'timeline',
             'recovery', 'clock', 'key', 'qr', 'lock', 'none', 'custom')


def art_slot(slot):
    if slot not in ART_SLOTS:
        raise ApiError(400, 'portal or admin')
    return ART_SLOTS[slot]


def logo_kind(raw):
    """What sort of picture the bytes are, by their first bytes - never by
    the name they came with."""
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if raw.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    head = raw[:4096].lstrip(b'\xef\xbb\xbf \t\r\n').lower()
    if (head.startswith(b'<svg') or head.startswith(b'<?xml') or head.startswith(b'<!--')
            or head.startswith(b'<!doctype svg')) and b'<svg' in raw[:65536].lower():
        return 'image/svg+xml'
    return None


def logo_check(raw):
    if not raw:
        raise ValueError('the file is empty')
    if len(raw) > LOGO_MAX:
        raise ValueError('the picture is %s - at most 512 KB' % bytes_words(len(raw)))
    kind = logo_kind(raw)
    if not kind:
        raise ValueError('that is not a picture this takes: PNG, JPEG, GIF, WebP or SVG')
    if kind == 'image/svg+xml':
        # Shown only as an <img> and sent with a policy that runs nothing,
        # but an SVG with a script or a link out is turned away all the same.
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the SVG is not UTF-8 text')
        low = text.lower()
        if (re.search(r'<\s*(script|foreignobject|iframe|embed|object)\b', low)
                or re.search(r'\son[a-z]+\s*=', low) or 'javascript:' in low
                or '<!entity' in low
                or re.search(r'(href|src)\s*=\s*["\']\s*(https?:|//|data:text)', low)):
            raise ValueError('the SVG holds a script, an event handler or a link out - '
                             'save it as a plain picture (or as PNG) and again')
    return kind


def _art_meta(store, k):
    try:
        got = json.loads(store.get_meta(k) or 'null')
    except Exception:
        return None
    return got if isinstance(got, dict) else None


def logo_read(store, slot='portal'):
    _, lk, _ = art_slot(slot)
    got = _art_meta(store, lk)
    if not got and slot == 'admin' and _admin_as_1071(store):
        got = _art_meta(store, ART_SLOTS['portal'][1])
    return got if got and got.get('b64') else None


def _admin_as_1071(store):
    """1.0.71 had one picture, put on the administration's sign-in too with
    'admin': true - read so until the administration's own is picked."""
    return store.get_meta(ART_SLOTS['admin'][0]) is None and bool(
        (_art_meta(store, ART_SLOTS['portal'][0]) or {}).get('admin'))


def art_read(store, slot='portal'):
    """Which picture a sign-in shows - a few bytes, read by every page."""
    ak, _, default = art_slot(slot)
    got = _art_meta(store, ak)
    if got is None and slot == 'admin' and _admin_as_1071(store):
        got = _art_meta(store, ART_SLOTS['portal'][0])
    got = got or {}
    art = got.get('art') if got.get('art') in ART_NAMES else default
    return {'art': art, 'sha': str(got.get('sha') or '') if art == 'custom' else ''}


def art_set(store, slot, art):
    ak, _, _ = art_slot(slot)
    one = {'art': art, 'sha': ''}
    if art == 'custom':
        logo = logo_read(store, slot)
        if not logo:
            raise ValueError('there is no picture of your own yet - upload one first')
        one['sha'] = logo.get('sha') or ''
        if slot == 'admin' and not _art_meta(store, ART_SLOTS['admin'][1]):
            store.set_meta(ART_SLOTS['admin'][1], json.dumps(logo))  # 1.0.71's, its own now
    store.set_meta(ak, json.dumps(one))
    return one


def logo_set(store, slot, raw, by, name=''):
    """A picture of the site's own, kept in the database - so it is the same
    on both nodes of a cluster, in every backup and in the configuration
    file. b'' takes it away (and the drawing that page came with is shown)."""
    _, lk, default = art_slot(slot)
    if not raw:
        if slot == 'admin' and _admin_as_1071(store):
            store.set_meta(ART_SLOTS['admin'][0], json.dumps(art_read(store, 'admin')))
        store.set_meta(lk, '')
        if art_read(store, slot)['art'] == 'custom':
            art_set(store, slot, default)
        return None
    kind = logo_check(raw)
    one = {'type': kind, 'b64': base64.b64encode(raw).decode('ascii'),
           'sha': hashlib.sha256(raw).hexdigest()[:16], 'bytes': len(raw),
           'name': str(name or '')[:120], 'at': time.time(), 'by': by}
    store.set_meta(lk, json.dumps(one))
    return one


def art_state(store, slot):
    logo = logo_read(store, slot)
    return dict(art_read(store, slot), default=ART_SLOTS[slot][2],
                logo={k: logo.get(k) for k in ('type', 'sha', 'bytes', 'name', 'at', 'by')}
                if logo else None)


@route('GET', '/api/portal/logo')
def _portal_logo(h):
    # Anybody: it is the picture on a sign-in. Only the picture.
    one = logo_read(h.store, 'admin' if h.arg('slot') == 'admin' else 'portal')
    if not one:
        return {'logo': None}
    return {'logo': {'type': one.get('type'), 'b64': one.get('b64'), 'sha': one.get('sha')}}


@route('GET', '/api/portal/art')
def _portal_art(h):
    h.me()
    return {'names': list(ART_NAMES), 'portal': art_state(h.store, 'portal'),
            'admin': art_state(h.store, 'admin')}


@route('POST', '/api/portal/art')
def _portal_art_set(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    slot = str(b.get('slot') or 'portal')
    art_slot(slot)
    where = {'portal': 'the enrolment pages', 'admin': 'the administration'}[slot]
    who = s['name']
    try:
        if act == 'pick':
            art = str(b.get('art') or '')
            if art not in ART_NAMES:
                raise ApiError(400, 'no such picture: %s' % art)
            art_set(h.store, slot, art)
            h.store.add_event('settings', '%s picked the picture of the sign-in of %s: %s'
                              % (who, where, art), who=who)
        elif act == 'reset':
            art_set(h.store, slot, ART_SLOTS[slot][2])
            h.store.add_event('settings', '%s put the picture of the sign-in of %s back to '
                              'the one it came with' % (who, where), who=who)
        elif act == 'upload':
            data = str(b.get('data') or '')
            if data.startswith('data:'):
                data = data.split(',', 1)[-1]
            try:
                raw = base64.b64decode(data, validate=True)
            except (binascii.Error, ValueError):
                raise ApiError(400, 'the picture did not arrive whole')
            if not raw:
                # Nothing is not a picture (1.0.94): it took the one there away.
                raise ApiError(400, 'no picture arrived')
            one = logo_set(h.store, slot, raw, who, str(b.get('name') or ''))
            art_set(h.store, slot, 'custom')
            h.store.add_event('settings', '%s put a picture of their own on the sign-in of %s '
                              '(%s, %s)' % (who, where,
                                           one['type'].split('/')[1].split('+')[0].upper(),
                                           bytes_words(one['bytes'])), who=who)
        elif act == 'save':
            # All of one sign-in's changes at once, as the save bar sends
            # them (1.0.73): a picture of your own taken away or uploaded,
            # then which picture is shown.
            art = str(b.get('art') or '')
            if art not in ART_NAMES:
                raise ApiError(400, 'no such picture: %s' % art)
            raw = None
            if b.get('data'):
                data = str(b.get('data'))
                if data.startswith('data:'):
                    data = data.split(',', 1)[-1]
                try:
                    raw = base64.b64decode(data, validate=True)
                except (binascii.Error, ValueError):
                    raise ApiError(400, 'the picture did not arrive whole')
                logo_check(raw)
            if b.get('forget') and not raw:
                logo_set(h.store, slot, b'', who)
                h.store.add_event('settings', '%s took away the picture of their own of the '
                                  'sign-in of %s' % (who, where), who=who)
            if raw:
                one = logo_set(h.store, slot, raw, who, str(b.get('name') or ''))
                h.store.add_event('settings', '%s put a picture of their own on the sign-in of '
                                  '%s (%s, %s)' % (who, where,
                                                  one['type'].split('/')[1].split('+')[0].upper(),
                                                  bytes_words(one['bytes'])), who=who)
            if art_read(h.store, slot)['art'] != art or raw:
                art_set(h.store, slot, art)
                h.store.add_event('settings', '%s picked the picture of the sign-in of %s: %s'
                                  % (who, where, art), who=who)
        elif act == 'forget':
            logo_set(h.store, slot, b'', who)
            h.store.add_event('settings', '%s took away the picture of their own of the '
                              'sign-in of %s' % (who, where), who=who)
        else:
            raise ApiError(400, 'save, pick, upload, forget or reset')
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'names': list(ART_NAMES), 'portal': art_state(h.store, 'portal'),
            'admin': art_state(h.store, 'admin'), 'message': 'saved - every node shows it'}


@route('GET', '/api/portal/info')
def _portal_info(h):
    return {'on': bool(CONFIG.get('portal')), 'title': CONFIG.get('portal_title') or '',
            'art': art_read(h.store, 'portal'), 'admin_art': art_read(h.store, 'admin'),
            'hint': CONFIG.get('portal_hint') or '', 'help': CONFIG.get('portal_help') or '',
            'lang': CONFIG.get('ui_lang') or 'cs', 'issuer': CONFIG.get('totp_issuer') or '',
            'site': CONFIG.get('site_name') or short_host()}


@route('POST', '/api/portal/login')
def _portal_login(h):
    if not CONFIG.get('portal'):
        raise ApiError(403, 'enrolling a token here is switched off')
    b = h.body()
    name = str(b.get('name') or '').strip()
    password = str(b.get('password') or '')
    key = h.throttle('portal', int(CONFIG.get('portal_tries') or 5),
                     int(CONFIG.get('portal_wait_min') or 15), name=name)
    full = Authenticator.full_name(name, CONFIG.get('portal_realm') or
                                   CONFIG.get('default_realm') or '')
    realm = h.store.realm_for(full) if full else None
    if not any(r.get('directory') for r in h.store.realms()):
        # Nobody can enrol yet - and the one trying is most likely the
        # administrator who has just installed this, at the wrong door.
        raise ApiError(503, 'nobody can enrol here yet: no realm with a directory is set up. '
                            'Administrators sign in at /admin/')
    if not realm or not realm.get('directory'):
        h.failed(key)
        raise ApiError(401, 'the name or the password is not right')
    ad = h.d.auth.directory(realm['directory'])
    if not ad:
        raise ApiError(503, 'the directory of this realm is not set up')
    how = realm.get('lookup') if realm.get('lookup') in ('upn', 'sam') else (
        'upn' if '@' in full else 'sam')
    try:
        entry = Authenticator.find_person(ad, full, how, realm)
        if not entry:
            raise LdapError('there is no such account')
        if entry_unusable(entry):
            raise LdapError('the account may not sign in: %s' % entry_unusable(entry))
        ad.password_ok(entry, password)
    except LdapUnreachable as e:
        log('the enrolment pages could not reach the directory: %s' % e, 'warn')
        raise ApiError(503, 'the directory cannot be reached just now')
    except LdapError as e:
        h.failed(key)
        h.store.add_event('enrolment', '%s could not sign in to the enrolment pages from %s: %s'
                          % (full, h.client_ip(), e), 'warn', who=full)
        raise ApiError(401, 'the name or the password is not right')
    # The realm's groups always: nobody enrols a token the VPN would refuse.
    # "Who may enrol" can only narrow that further, never widen it.
    who = CONFIG.get('portal_who') or 'realm_groups'
    musts = []
    if realm.get('groups'):
        musts.append(realm['groups'])
    if who == 'groups' and dn_list(CONFIG.get('portal_groups')):
        musts.append([{'group': g} for g in dn_list(CONFIG.get('portal_groups'))])
    let_in = []
    if musts:
        have = ad.groups_of(entry, bool(realm.get('nested', 1)))
        # The groups of the realm that let this person in, for "About you"
        # on the page (1.0.113).
        for w in realm.get('groups') or []:
            try:
                if group_matches([w], have, ad):
                    g = str(w.get('group') if isinstance(w, dict) else w)
                    let_in.append(cn_of(g) or g)
            except Exception:                           # noqa: BLE001
                pass
        if not all(group_matches(w, have, ad) for w in musts):
            names = ', '.join(cn_of(w.get('group') or '') or w.get('group') or ''
                              for m in musts for w in m[:6])
            h.store.add_event('enrolment', '%s may not enrol a token: in none of the groups '
                              '(%s)' % (full, names), 'warn', who=full)
            h.d.tokens._said(Authenticator.token_name(full, realm), False,
                             'Not in the groups of the realm %s: may not enrol' % realm['name'],
                             'portal', h.client_ip(), '')
            # Counted as a wrong password is (1.0.101): the answer tells that
            # the password was right, so guessing it this way meets the same
            # limit.
            h.failed(key)
            raise ApiError(403, 'this account may not have a token here - ask the '
                           'administrator')
    tname, _how = Authenticator.token_for(h.store, full, realm)
    # The same person under another spelling (1.0.44): DOMAIN\\name, another
    # realm on the same directory, other letters' case. A token they have
    # already under any of them is the one this session is about, so that
    # the directory password alone never makes a second one.
    if not h.store.token(tname):
        same = portal_same_person(h.store, realm, entry)
        if same:
            h.store.add_event('enrolment', '%s signed in as %s: the token %s is theirs already'
                              % (full, tname, same), 'warn', who=same)
            tname = same
    token = h.store.session_new('portal', tname, 'portal', h.client_ip(),
                                max(1, int(CONFIG.get('portal_session_min') or 15)) / 60.0 * 4,
                                {'display': entry.get('display') or '', 'dn': entry['dn'],
                                 'realm': realm['name'], 'login': full,
                                 # What the page offers for a code by mail or SMS (1.0.76).
                                 'mail': entry.get('mail') or '',
                                 'mobile': entry.get('mobile') or '',
                                 # What the page shows under the name (1.0.113).
                                 'about': {'sam': entry.get('sam') or '',
                                           'upn': entry.get('upn') or '',
                                           'department': entry.get('department') or '',
                                           'title': entry.get('title') or '',
                                           'phone': entry.get('phone') or '',
                                           'expires': entry.get('expires') or None,
                                           'pw_set': entry.get('pw_set') or None,
                                           'groups': let_in[:20],
                                           'directory': realm.get('directory') or ''}})
    h.store.add_event('enrolment', '%s signed in to the enrolment pages from %s'
                      % (tname, h.client_ip()), who=tname)
    return {'token': token, 'name': tname}


def portal_same_person(store, realm, entry):
    """The name of a token the directory entry already has under another
    spelling: its userPrincipalName, its account name with the suffix of
    any realm on the same directory, or bare - '' when none."""
    sam = str(entry.get('sam') or '').strip()
    upn = str(entry.get('upn') or '').strip()
    names = []
    if upn:
        names.append(upn)
    if sam:
        names.append(sam)
        for r in store.realms():
            if str(r.get('directory') or '').lower() != str(realm.get('directory') or '').lower():
                continue
            suf = str(r.get('suffix') or '')
            if suf and suf != '*':
                names.append('%s@%s' % (sam, suf))
                # And under its other suffixes (1.0.117), for a token made
                # before they were.
                for al in r.get('aliases') or []:
                    names.append('%s@%s' % (sam, al))
    here = str(realm.get('directory') or '').lower()

    def same_directory(cand):
        # Only a name whose own realm reads the same directory is the same
        # person (1.0.59): a bare "novak" can be a different Novak in a realm
        # on another directory.
        r = store.realm_for(cand)
        return bool(r) and str(r.get('directory') or '').lower() == here
    names = [n for n in names if same_directory(n)]
    seen = set()
    for n in names:
        for cand in (n, n.lower()):
            if cand in seen:
                continue
            seen.add(cand)
            if store.token(cand):
                return norm_name(cand)
    want = set(x.lower() for x in names)
    if want:
        for row in store.db.rows('SELECT name FROM tokens WHERE LOWER(name) IN (%s)'
                                 % ','.join('?' * len(want)), tuple(sorted(want))):
            if same_directory(row['name']):
                return row['name']
    return ''


def token_meta_forget(store, name):
    """What was kept beside a token that is gone (1.0.61)."""
    try:
        store.db.run('DELETE FROM meta WHERE k = ?', ('disabled_from:' + norm_name(name),))
    except Exception:                                   # noqa: BLE001
        pass


def token_switch_state(store, name, on):
    """The state a token is switched to (1.0.59). Switched off, the state it
    had is kept aside; switched on, a token that was waiting for its first
    code waits again rather than coming into use with a key never proven
    scanned."""
    name = norm_name(name)
    if not on:
        cur = (store.token(name) or {}).get('state') or 'active'
        if cur != 'disabled':
            store.set_meta('disabled_from:' + name, cur)
        return 'disabled'
    was = store.get_meta('disabled_from:' + name, '') or 'active'
    try:
        store.db.run('DELETE FROM meta WHERE k = ?', ('disabled_from:' + name,))
    except Exception:                                   # noqa: BLE001
        pass
    return 'pending' if was == 'pending' else 'active'


@route('POST', '/api/portal/logout')
def _portal_logout(h):
    h.store.session_end(h.headers.get('X-Otp-Session'))
    return {}


def portal_methods(h, s):
    """The kinds of token this person may choose (1.0.76): what their realm
    offers, less a way of sending that is not set up."""
    data = s.get('data') or {}
    realm = h.store.realm_for(data.get('login') or s['name'])
    chan = code_channels()
    return [k for k in realm_methods(realm) if k == 'totp' or k in chan]


def portal_state(h, s):
    tok = h.store.token(s['name'])
    shown = h.store.token_shown(tok)
    data = s.get('data') or {}
    ver = data.get('verify') or {}
    if ver and float(ver.get('exp') or 0) < time.time():
        ver = {}
    about = dict(data.get('about') or {})
    about.update(login=data.get('login') or '', realm=data.get('realm') or '',
                 mail=data.get('mail') or '', mobile=data.get('mobile') or '')
    return {'name': s['name'], 'display': data.get('display') or '',
            'about': about,
            'methods': portal_methods(h, s),
            'suggest': {'mail': data.get('mail') or '', 'sms': data.get('mobile') or ''},
            'verify': {'kind': ver.get('kind'), 'dest': dest_masked(ver.get('kind'),
                                                                     ver.get('dest'))}
            if ver else None,
            'may_replace': bool(data.get('may_replace')),
            'code_digits': int(CONFIG.get('code_digits') or 6),
            'mail_fmt_default': 'text' if CONFIG.get('code_mail_fmt') == 'text' else 'html',
            'token': shown, 'confirm': bool(CONFIG.get('portal_confirm')),
            'reissue': bool(CONFIG.get('portal_reissue')),
            'show_secret': bool(CONFIG.get('portal_show_secret')),
            'show_scratch': bool(CONFIG.get('portal_scratch')),
            'codes_view': bool(CONFIG.get('portal_codes_view')) and bool(shown) and
            bool((shown or {}).get('scratch_kept')),
            'title': CONFIG.get('portal_title') or '', 'help': CONFIG.get('portal_help') or ''}


@route('GET', '/api/portal/me')
def _portal_whoami(h):
    s = h.session('portal')
    if not s:
        return {'me': None}
    if not CONFIG.get('portal'):
        # Switched off meanwhile: nothing more of it shown (1.0.44).
        h.store.session_end(h.headers.get('X-Otp-Session'))
        return {'me': None}
    return {'me': portal_state(h, s)}


def _picture_for_page(got):
    if not CONFIG.get('portal_show_secret'):
        got = dict(got)
        got.pop('secret', None)
        got.pop('secret_spaced', None)
    if not CONFIG.get('portal_scratch'):
        got = dict(got)
        got['scratch'] = []
    return got


def portal_data_set(h, s, **changes):
    """What the enrolment session remembers, changed (1.0.76) - only the keys
    given, over what the database holds now (1.0.101)."""
    data = h.store.session_merge(s['id'], changes)
    if data is None:
        data = dict(s.get('data') or {})
        for k, v in changes.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
    s['data'] = data
    return data


@route('POST', '/api/portal/enroll')
def _portal_enroll(h):
    s = portal_me(h)
    b = h.body()
    kind = str(b.get('kind') or 'totp')
    if kind not in portal_methods(h, s):
        raise ApiError(403, 'that way of getting codes is not offered here')
    may_replace = bool((s.get('data') or {}).get('may_replace'))
    if may_replace and h.d.tokens.blocked(s['name']):
        # Switched off or locked meanwhile (1.0.94).
        portal_data_set(h, s, may_replace=None)
        raise ApiError(403, 'the token cannot be replaced here: %s' % h.d.tokens.blocked(s['name']))
    if kind in ('mail', 'sms'):
        # A code sent by mail or SMS (1.0.76): the address or the number is
        # proven first - a code goes there, and is typed back here - and only
        # then is the token made.
        tok = h.store.token(s['name'])
        if tok and tok.get('state') != 'pending' and not may_replace:
            raise ApiError(409, 'there is a token already; it can be replaced with a code '
                                'from it')
        ver_was = (s.get('data') or {}).get('verify') or {}
        if b.get('again') and not b.get('dest') and ver_was.get('kind') == kind:
            # Sent again to where the check in this session goes (1.0.98):
            # the page reloaded meanwhile knows only that it is masked.
            # The language chosen for the check kept (1.0.103): the page
            # reloaded meanwhile sends its own, which is not that choice.
            b = dict(b, dest=ver_was.get('dest'), mail_fmt=ver_was.get('mail_fmt') or b.get('mail_fmt'),
                     lang=ver_was.get('lang') or b.get('lang'))
        try:
            dest = dest_checked(kind, b.get('dest'))
        except ValueError as e:
            raise ApiError(400, str(e))
        # Every code sent holds its place (1.0.101): a code sent "went well"
        # and gave it back, so only the count per name below bounded how
        # many SMS a signed-in person could have sent - to any number. Now
        # also per address of the page and per destination.
        # Per address ten times what one person may have sent - many people
        # sit behind one address - and the person's own count below.
        key = h.throttle('portal-send', 10 * int(CONFIG.get('code_send_max') or 5),
                         int(CONFIG.get('code_send_window_min') or 15), name=s['name'],
                         what='codes sent')
        if not code_send_allowed(h.store, s['name']) or \
                not code_send_allowed(h.store, 'to:%s:%s' % (kind, dest.lower())):
            # Nothing sent: the address's place given back (1.0.103).
            raise ApiError(429, 'too many codes were sent - wait %d min and try again'
                           % code_send_wait_min(h.store, 'to:%s:%s' % (kind, dest.lower())))
        h.failed(key)       # a code that goes holds its place
        code = code_new()
        page_lang = str(b.get('lang') or '')
        page_lang = page_lang if page_lang in ('cs', 'en') else ''
        # What the person chose (1.0.83): HTML or plain text, for a mail.
        fmt = str(b.get('mail_fmt') or '')
        fmt = fmt if (kind == 'mail' and fmt in ('html', 'text')) else ''
        try:
            code_send(h.store, kind, dest, code, 'verify', name=s['name'],
                      lang=page_lang or None, fmt=fmt or None)
        except (MailError, SmsError) as e:
            h.store.add_event('enrolment', 'the code to check %s for %s could not be sent: %s'
                              % (dest, s['name'], e), 'warn', who=s['name'])
            raise ApiError(502, 'the code could not be sent: %s' % e)
        portal_data_set(h, s, verify={'kind': kind, 'dest': dest, 'code': code_hash(s['name'], code),
                                      'exp': time.time() + int(CONFIG.get('code_ttl_s') or 300),
                                      'tries': 0, 'lang': page_lang, 'mail_fmt': fmt})
        h.store.add_event('enrolment', '%s asked for a code by %s to %s, to check it' % (
            s['name'], 'mail' if kind == 'mail' else 'SMS', dest), who=s['name'])
        return {'verify': {'kind': kind, 'dest': dest_masked(kind, dest)},
                'me': portal_state(h, s)}
    confirm = bool(CONFIG.get('portal_confirm'))
    if may_replace and h.store.token(s['name']):
        # The old one proven on this page (a recovery code, or a code sent
        # to it): a new app token beside it until a code confirms it.
        got = (h.d.tokens.stage_replacement(s['name'], 'self') if confirm
               else h.d.tokens.enroll(s['name'], 'self', pending=False))
        portal_data_set(h, s, may_replace=None)
        if str(b.get('lang') or '') in ('cs', 'en'):
            h.store.token_write(s['name'], {'lang': str(b.get('lang'))})
        h.store.add_event('enrolment', '%s is replacing their token with the app' % s['name'],
                          who=s['name'])
        return {'made': _picture_for_page(got), 'confirm': confirm}
    # Looked at and written under the name's lock (1.0.59): two tabs, or a
    # confirm in one, no longer slip between the look and the write.
    with h.d.tokens.lock_of(norm_name(s['name'])):
        tok = h.store.token(s['name'])
        if tok and tok.get('state') != 'pending':
            raise ApiError(409, 'there is a token already; it can be replaced with a code '
                                'from it')
        got = h.d.tokens.enroll(s['name'], 'self', pending=confirm,
                                display=(s.get('data') or {}).get('display') or '')
        if str(b.get('lang') or '') in ('cs', 'en'):       # its second window's language (1.0.82)
            h.store.token_write(s['name'], {'lang': str(b.get('lang'))})
    h.store.add_event('enrolment', '%s enrolled a token for themselves%s' % (
        s['name'], ', waiting for a code' if confirm else ''), who=s['name'])
    return {'made': _picture_for_page(got), 'confirm': confirm}


@route('POST', '/api/portal/verify')
def _portal_verify(h):
    """The code sent to an address or a number, typed back (1.0.76): the
    token is made."""
    s = portal_me(h)
    data = s.get('data') or {}
    ver = data.get('verify') or {}
    if not ver or float(ver.get('exp') or 0) < time.time():
        portal_data_set(h, s, verify=None)
        raise ApiError(410, 'the code ran out - ask for a new one')
    # Counted where many requests at once cannot each see "no tries yet"
    # (1.0.94) - the tries in the session are read at the start of each.
    key = h.throttle('portal-verify', int(CONFIG.get('code_tries') or 3) + 2,
                     int(CONFIG.get('portal_wait_min') or 15), name=s['name'], ip_tries=50,
                     name_tries=int(CONFIG.get('code_tries') or 3) * 3, what='wrong codes')
    code = re.sub(r'\s', '', str(h.body().get('code') or ''))
    if not hmac.compare_digest(code_hash(s['name'], code), str(ver.get('code') or '')):
        h.failed(key)
        # Counted on the code as it is now (1.0.101): a copy read at the
        # start and written back brought back a code another request had
        # taken, or lost another's count.
        last = h.store.session_count_try(s['id'], 'verify', ver.get('code'),
                                         int(CONFIG.get('code_tries') or 3))
        if last:
            raise ApiError(403, 'that was not the code - and it was the last try: ask for a '
                                'new one')
        raise ApiError(403, 'that is not the code that was sent')
    # Taken once (1.0.101): two requests with the right code at once both
    # read it before either cleared it.
    if not h.store.session_take(s['id'], 'verify'):
        raise ApiError(409, 'that code was taken already')
    # Looked at again now (1.0.136), as making the token is: switched off,
    # locked or confirmed by its owner while the code was on its way, it is
    # not replaced by one whose codes go where this session said.
    tok = h.store.token(s['name'])
    may_replace = bool(data.get('may_replace'))
    if tok and tok.get('state') != 'pending' and not may_replace:
        portal_data_set(h, s, verify=None)
        raise ApiError(409, 'there is a token already; it can be replaced with a code from it')
    if may_replace and h.d.tokens.blocked(s['name']):
        portal_data_set(h, s, verify=None, may_replace=None)
        raise ApiError(403, 'the token cannot be replaced here: %s'
                       % h.d.tokens.blocked(s['name']))
    got = h.d.tokens.enroll_sent(s['name'], 'self', ver['kind'], ver['dest'],
                                 display=data.get('display') or '', lang=ver.get('lang') or None,
                                 mail_fmt=ver.get('mail_fmt') or None)
    portal_data_set(h, s, verify=None, may_replace=None)
    h.store.add_event('enrolment', '%s set up their sign-in: codes by %s to %s' % (
        s['name'], 'mail' if ver['kind'] == 'mail' else 'SMS', ver['dest']), who=s['name'])
    made = {'kind': got['kind'], 'dest': got['dest'],
            'scratch': got['scratch'] if CONFIG.get('portal_scratch') else []}
    return {'made': made, 'me': portal_state(h, s)}


@route('POST', '/api/portal/sendold')
def _portal_sendold(h):
    """A code to where the codes go now (1.0.76): proof of the old token on
    the way to replacing it, as a code from the old phone is."""
    s = portal_me(h)
    if not CONFIG.get('portal_reissue') and not CONFIG.get('portal_codes_view'):
        raise ApiError(403, 'a token can only be replaced by an administrator here')
    tok = h.store.token(s['name'])
    kind = token_kind(tok)
    if not tok or kind == 'totp':
        raise ApiError(400, 'this token gets no codes sent')
    # A token switched off or locked out stays so (1.0.94): its owner does
    # not switch it on again by replacing it.
    stop = h.d.tokens.blocked(s['name'])
    if stop:
        raise ApiError(403, 'the token cannot be replaced here: %s' % stop)
    if not code_send_allowed(h.store, s['name']):
        raise ApiError(429, 'too many codes were sent - wait %d min and try again'
                       % code_send_wait_min(h.store, s['name']))
    code = code_new()
    page_lang = str(h.body().get('lang') or '')
    try:
        code_send(h.store, kind, tok.get('dest') or '', code, 'signin', name=s['name'],
                  lang=page_lang if page_lang in ('cs', 'en') else None)
    except (MailError, SmsError) as e:
        raise ApiError(502, 'the code could not be sent: %s' % e)
    portal_data_set(h, s, old={'code': code_hash(s['name'], code),
                               'exp': time.time() + int(CONFIG.get('code_ttl_s') or 300)})
    return {'sent_to': dest_masked(kind, tok.get('dest'))}


@route('POST', '/api/portal/codes')
def _portal_codes(h):
    """The person's own recovery codes, shown again (1.0.113) - only with a
    code from the token itself: the directory password alone must never
    hand over a second factor."""
    s = portal_me(h)
    if not CONFIG.get('portal_codes_view'):
        raise ApiError(403, 'the recovery codes are shown only when the token is made here')
    tok = h.store.token(s['name'])
    if not tok or tok.get('state') == 'pending':
        raise ApiError(400, 'there is no token in use yet')
    stop = h.d.tokens.blocked(s['name'])
    if stop:
        raise ApiError(403, 'not while the token is blocked: %s' % stop)
    key = h.throttle('portal-codes', int(CONFIG.get('portal_tries') or 5),
                     int(CONFIG.get('portal_wait_min') or 15), name=s['name'], ip_tries=30,
                     name_tries=2 * int(CONFIG.get('portal_tries') or 5), what='wrong codes')
    code = re.sub(r'\s', '', str(h.body().get('code') or ''))
    old = (s.get('data') or {}).get('old') or {}
    if old and float(old.get('exp') or 0) >= time.time() and \
            hmac.compare_digest(code_hash(s['name'], code), str(old.get('code') or '')):
        ok, said = True, 'Code sent accepted'
        if not h.store.session_take(s['id'], 'old'):
            ok, said = False, SAY_REUSED
    else:
        ok, said, _f = h.d.tokens.check(s['name'], code, how='portal', src=h.client_ip())
    if not ok:
        h.failed(key)
        raise ApiError(403, 'the code was not taken: %s' % said)
    shown = codes_open(h.store.token(s['name']))
    if shown is None:
        raise ApiError(409, 'the recovery codes of this token are kept only in a form that '
                            'cannot be shown - ask the administrator for new ones')
    h.store.add_event('enrolment', '%s looked at their recovery codes from %s'
                      % (s['name'], h.client_ip()), 'warn', who=s['name'])
    return {'codes': [{'code': c.get('c') if isinstance(c, dict) else str(c),
                       'used': (c.get('used') if isinstance(c, dict) else None)}
                      for c in shown]}


@route('POST', '/api/portal/confirm')
def _portal_confirm(h):
    s = portal_me(h)
    # Its own limit too (1.0.101), whatever the token's pause and lockout
    # are set to.
    key = h.throttle('portal-confirm', 10, int(CONFIG.get('portal_wait_min') or 15),
                     name=s['name'], ip_tries=50, name_tries=10, what='wrong codes')
    ok, said = h.d.tokens.confirm(s['name'], str(h.body().get('code') or ''), 'portal',
                                  h.client_ip())
    if ok:
        h.store.add_event('enrolment', '%s confirmed their token' % s['name'], who=s['name'])
    else:
        h.failed(key)
    return {'good': ok, 'said': said, 'me': portal_state(h, s)}


@route('POST', '/api/portal/reissue')
def _portal_reissue(h):
    s = portal_me(h)
    if not CONFIG.get('portal_reissue'):
        raise ApiError(403, 'a token can only be replaced by an administrator here')
    b = h.body()
    # Its own count (1.0.103), not the sign-in's: a wrong old code here no
    # longer locked the sign-in of everybody at the address.
    key = h.throttle('portal-reissue', int(CONFIG.get('portal_tries') or 5),
                     int(CONFIG.get('portal_wait_min') or 15), name=s['name'], ip_tries=30,
                     name_tries=2 * int(CONFIG.get('portal_tries') or 5),
                     what='wrong passwords or codes')
    realm = h.store.realm_for((s.get('data') or {}).get('login') or s['name'])
    ad = h.d.auth.directory(realm['directory']) if realm else None
    if not ad:
        raise ApiError(503, 'the directory of this realm is not set up')
    try:
        ad.password_ok({'dn': (s.get('data') or {}).get('dn')}, str(b.get('password') or ''))
    except LdapUnreachable as e:
        log('the enrolment pages could not reach the directory: %s' % e, 'warn')
        raise ApiError(503, 'the directory cannot be reached just now')
    except LdapError:
        h.failed(key)
        # 403, not 401 (1.0.33): a 401 signs the page out, and the person
        # lost the words saying what was wrong.
        raise ApiError(403, 'the password is not right')
    stop = h.d.tokens.blocked(s['name'])
    if stop:
        raise ApiError(403, 'the token cannot be replaced here: %s' % stop)
    code = re.sub(r'\s', '', str(b.get('code') or ''))
    old = (s.get('data') or {}).get('old') or {}
    if old and float(old.get('exp') or 0) >= time.time() and \
            hmac.compare_digest(code_hash(s['name'], code), str(old.get('code') or '')):
        ok, said = True, 'Code sent accepted'               # 1.0.76
        if not h.store.session_take(s['id'], 'old'):         # once (1.0.101)
            ok, said = False, SAY_REUSED
        s['data'] = dict(s.get('data') or {})
        s['data'].pop('old', None)
    else:
        ok, said, _f = h.d.tokens.check(s['name'], code, how='portal', src=h.client_ip())
    if not ok:
        h.failed(key)
        raise ApiError(403, 'the code from the old token was not taken: %s' % said)
    want = str(b.get('kind') or 'totp')
    if want != 'totp' or token_kind(h.store.token(s['name'])) != 'totp':
        # Another way, or away from one (1.0.76): the page asks which, and
        # the old token goes on working until the new one is made.
        portal_data_set(h, s, may_replace=True)
        h.store.add_event('enrolment', '%s proved their token and may set up another way'
                          % s['name'], who=s['name'])
        return {'choose': True, 'me': portal_state(h, s)}
    if CONFIG.get('portal_confirm'):
        got = h.d.tokens.stage_replacement(s['name'], 'self')
    else:
        got = h.d.tokens.enroll(s['name'], 'self', pending=False)
    h.store.add_event('enrolment', '%s is replacing their token' % s['name'], who=s['name'])
    return {'made': _picture_for_page(got), 'confirm': bool(CONFIG.get('portal_confirm'))}


@route('POST', '/api/portal/cancel')
def _portal_cancel(h):
    s = portal_me(h)
    if (s.get('data') or {}).get('verify') or (s.get('data') or {}).get('may_replace'):
        # An address being checked, or a new way being chosen (1.0.76): given
        # up, and the token there is (if any) stays as it is.
        portal_data_set(h, s, verify=None, may_replace=None, old=None)
        return {'me': portal_state(h, s)}
    with h.d.tokens.lock_of(norm_name(s['name'])):      # with confirm (1.0.59)
        tok = h.store.token(s['name'])
        if tok and tok.get('pending_secret'):
            h.d.tokens.drop_staged(s['name'])
            h.store.add_event('enrolment', '%s stopped replacing their token' % s['name'],
                              who=s['name'])
        elif tok and tok.get('state') == 'pending':
            h.store.token_drop(s['name'])
            token_meta_forget(h.store, s['name'])
            h.store.add_event('enrolment', '%s threw away the token they had not confirmed'
                              % s['name'], who=s['name'])
    return {'me': portal_state(h, s)}


class ApiHttpServer(ThreadingHTTPServer):
    """The API's HTTP server, with room for many connections waiting at once
    (1.0.33): the default queue of five dropped the sixth of twenty pages
    asking at the same moment."""
    request_queue_size = 256
    daemon_threads = True
    # At most this many at once (1.0.101); past it a connection is closed at
    # once rather than given a thread.
    MOST = 256

    def __init__(self, *a, **kw):
        self.slots = threading.BoundedSemaphore(self.MOST)
        ThreadingHTTPServer.__init__(self, *a, **kw)

    def process_request(self, request, client_address):
        if not self.slots.acquire(False):
            log_sparing('api-full', 'the API has %d connections open already: one more was '
                        'closed' % self.MOST, 'warn')
            self.shutdown_request(request)
            return
        try:
            ThreadingHTTPServer.process_request(self, request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            ThreadingHTTPServer.process_request_thread(self, request, client_address)
        finally:
            self.slots.release()


class ApiServer(object):
    def __init__(self, daemon):
        self.daemon = daemon
        self.httpd = None

    def start(self):
        port = int(CONFIG.get('api_port') or 9861)
        # The port first, the key after (1.0.61): somebody else's program on
        # the port would otherwise have been handed the new key by the pages.
        self.httpd = ApiHttpServer(('127.0.0.1', port), ApiHandler)
        api_token(make=True)
        self.httpd.daemon_threads = True
        self.httpd.daemon = self.daemon
        threading.Thread(target=self.httpd.serve_forever, name='api', daemon=True).start()
        # Said beside the key (1.0.59): the pages read the port from here, so
        # api_port changed in the settings no longer leaves them asking 9861.
        try:
            write_replacing(RUN_DIR / 'api-port', '%d\n' % port, 0o644)
        except OSError as e:
            log('the API port could not be written down for the pages: %s' % e, 'warn')
        log('the API is on 127.0.0.1:%d' % port)

    def stop(self):
        try:
            self.httpd.shutdown()
        except Exception:
            pass


# ---- maintenance and upgrades (1.0.37) -----------------------------------------------
def _upgrade_view(h):
    meta = None
    try:
        meta = json.loads(h.store.get_meta('upgrade:pkg') or 'null')
    except ValueError:
        meta = None
    nodes = []
    for n in ha_nodes(h.store):
        n = dict(n)
        n['maintenance'] = maintenance_row(h.store, n['name'])
        nodes.append(n)
    if not nodes:
        nodes = [{'name': node_name(), 'version': __version__, 'me': True, 'alive': True,
                  'maintenance': maintenance_row(h.store)}]
    ok, why = upgrade_checks(h.store, meta, pages=True)
    plan = upgrade_plan(h.store)
    # A finished one hidden by Hide this (1.0.123).
    if plan and plan.get('state') != 'running' and \
            h.store.get_meta('upgrade:seen') == str(plan.get('id') or plan.get('at')):
        plan = None
    return {'node': node_name(), 'version': __version__, 'nodes': nodes, 'package': meta,
            'plan': plan, 'ready': ok, 'not_ready': why,
            'downgrade_on': bool(CONFIG.get('upgrade_downgrade')),
            'mode': CONFIG.get('ha_mode') or '',
            'helper': UPGRADE_HELPER.exists(),
            'path_unit': Path('/etc/systemd/system/otp-upgrade.path').exists(),
            'log': upgrade_log_tail(120), 'web': online_view(h.store)}


@route('GET', '/api/upgrade')
def _upgrade(h):
    h.me('fulladmin')
    return _upgrade_view(h)


@route('POST', '/api/upgrade/package')
def _upgrade_package(h):
    s = h.me('fulladmin')
    UPGRADE_DIR.mkdir(mode=0o750, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='incoming-', suffix='.tar.gz', dir=str(UPGRADE_DIR))
    os.close(fd)
    tmp = Path(tmp)
    try:
        h.body_to_file(tmp, UPGRADE_MOST)
        try:
            info = upgrade_inspect(tmp)
        except ValueError as e:
            h.store.add_event('starting and stopping', '%s sent a package that was refused: %s'
                              % (s['name'], e), 'warn', who=s['name'])
            raise ApiError(400, str(e))
        if info.get('older'):
            raise ApiError(400, '%s is older than %s, which runs here: going back is done on '
                                'the command line' % (info['version'], info.get('installed')))
        plan = upgrade_plan(h.store)
        if plan and plan['state'] == 'running':
            raise ApiError(409, 'an upgrade is going on: wait for it, or stop it first')
        meta = upgrade_store_package(h.store, tmp, info, s['name'])
        h.store.add_event('starting and stopping', '%s sent otp %s (signed by %s), ready to '
                          'be put in' % (s['name'], meta['version'], meta.get('signed_by')),
                          'warn', who=s['name'])
        return dict(_upgrade_view(h), message='otp %s is checked and ready' % meta['version'])
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


@route('POST', '/api/upgrade')
def _upgrade_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    try:
        if act == 'start':
            upgrade_start(h.store, s['name'], pages=True)
            return dict(_upgrade_view(h), message='the upgrade has begun')
        if act == 'online_look':
            row = online_look(h.store, s['name'])
            if row.get('error'):
                raise ValueError('%s: %s' % (row.get('url'), row['error']))
            n = row.get('newest') or {}
            return dict(_upgrade_view(h), message=(
                'otp %s is there - newer than %s' % (n['version'], __version__) if row.get('newer')
                else ('nothing newer than %s' % __version__ if n else 'no otp package there')))
        if str(act or '').startswith('downgrade') and not CONFIG.get('upgrade_downgrade'):
            # Offered on the pages only when switched on (1.0.144).
            raise ValueError('going back to an older version is not offered on these pages: '
                             'switch it on in Settings → Upgrades')
        if act == 'downgrade_changelog':
            return {'changelog': downgrade_changelog(b.get('version'))}
        if act == 'downgrade_list':
            # Going back (1.0.143): the older versions there, and what stands
            # in the way of each.
            return {'downgrade': downgrade_list(h.store)}
        if act == 'downgrade_get':
            plan = upgrade_plan(h.store)
            if plan and plan['state'] == 'running':
                raise ValueError('an upgrade is going on: wait for it, or stop it first')
            meta = downgrade_fetch(h.store, str(b.get('version') or ''), s['name'])
            if b.get('start'):
                upgrade_start(h.store, s['name'], pages=True)
                return dict(_upgrade_view(h), message='otp %s fetched and checked; going back '
                            'to it has begun' % meta['version'])
            return dict(_upgrade_view(h), message='otp %s is fetched, checked for this database '
                        'and ready to go back to' % meta['version'])
        if act == 'online_get':
            plan = upgrade_plan(h.store)
            if plan and plan['state'] == 'running':
                raise ValueError('an upgrade is going on: wait for it, or stop it first')
            meta = online_fetch(h.store, str(b.get('version') or ''), s['name'])
            if b.get('start'):
                upgrade_start(h.store, s['name'], pages=True)
                return dict(_upgrade_view(h), message='otp %s fetched and checked; the upgrade '
                            'has begun' % meta['version'])
            return dict(_upgrade_view(h), message='otp %s is fetched, checked and ready'
                        % meta['version'])
        if act == 'hide':
            plan = upgrade_plan(h.store)
            if plan and plan.get('state') == 'running':
                raise ValueError('the upgrade is going on')
            if plan:
                h.store.set_meta('upgrade:seen', str(plan.get('id') or plan.get('at')))
            return _upgrade_view(h)
        if act == 'cancel':
            upgrade_cancel(h.store, s['name'])
            return dict(_upgrade_view(h), message='the upgrade is stopped')
        if act == 'maintenance':
            name = str(b.get('node') or node_name())
            if name not in [n['name'] for n in ha_nodes(h.store)] + [node_name()]:
                raise ValueError('there is no node %s' % name)
            on = bool(b.get('on'))
            maintenance_set(h.store, on, str(b.get('why') or 'by hand'), s['name'], name)
            return dict(_upgrade_view(h), message='%s: maintenance %s' % (
                name, 'on' if on else 'off'))
        if act == 'forget':
            plan = upgrade_plan(h.store)
            if plan and plan['state'] == 'running':
                raise ValueError('an upgrade is going on with it')
            h.store.db.run("DELETE FROM meta WHERE k LIKE 'upgrade:piece:%'")
            h.store.db.run("DELETE FROM meta WHERE k = 'upgrade:pkg'")
            return dict(_upgrade_view(h), message='the package is forgotten')
    except ValueError as e:
        raise ApiError(400, str(e))
    except (OSError, tarfile.TarError, subprocess.SubprocessError) as e:
        # The address not answering, a package cut off (1.0.146): said, not an
        # error 500 with its trace in the log.
        raise ApiError(502, 'the address could not be read: %s'
                       % (getattr(e, 'reason', None) or e))
    raise ApiError(400, 'no such thing to do')


# ---- high availability (1.0.13) ---------------------------------------------------
CODE_NOW_SEEN = {}
CODE_NOW_LOCK = threading.Lock()


@route('GET', '/api/ha')
def _ha(h):
    h.me()
    return {'node': node_name(), 'address': node_address(), 'nodes': ha_nodes(h.store),
            'replication': ha_repl_state(h.store), 'job': job_read(),
            'checks': ha_checks(h.store), 'engine': h.store.db.engine,
            'mode': CONFIG.get('ha_mode') or '',
            'db_where': h.store.db.where(), 'db_host': CONFIG.get('db_host') or '',
            'config_file': str(CONFIG_FILE), 'version': __version__, 'lb': lb_facts(h.store),
            'errbase': _json_meta(h.store, 'ha:errbase:' + node_name()) or {},
            # How the link between the databases is protected (1.0.101), and
            # where the button that protects it is (1.0.104).
            'db_tls': CONFIG.get('db_tls') or '', 'link_tls': _hatls_view_safe(h.store),
            'readdress': readdress_view(h.store) if CONFIG.get('ha_mode') == 'replicated' else None}


def _hatls_view_safe(store):
    try:
        return hatls_view(store) if CONFIG.get('ha_mode') == 'replicated' else None
    except Exception as e:                              # noqa: BLE001
        return {'error': str(e)[:200]}


def lb_facts(store):
    """What the load balancer guides on the pages fill in (1.0.52): the real
    names, addresses and ports of this installation."""
    server_name, proxies = '', []
    for p in NGINX_CONF_PATHS:
        try:
            text = Path(p).read_text()
        except OSError:
            continue
        m = re.search(r'(?m)^\s*listen[^;]*443[^;]*;[\s\S]*?^\s*server_name\s+([^;\s]+)', text)
        if m:
            server_name = m.group(1)
        b = re.search(r'# REALIP-BEGIN(.*?)# REALIP-END', text, re.S)
        if b:
            proxies = re.findall(r'set_real_ip_from\s+([^;\s]+);', b.group(1))
        break
    v = vip_conf(store)
    clients = [{'name': c.get('name'), 'address': c.get('address')} for c in store.clients()
               if c.get('enabled')][:20]
    return {'server_name': server_name, 'trusted': proxies,
            'auth_port': int(CONFIG.get('radius_auth_port') or 1812),
            'acct_port': int(CONFIG.get('radius_acct_port') or 0),
            'vip': {'on': bool(v.get('on')), 'address': v.get('address') or '',
                    'fqdn': v.get('fqdn') or ''},
            'clients': clients}


@route('GET', '/api/ha/history')
def _ha_history(h):
    h.me()
    return {'rows': ha_history(h.store, h.num('limit', 300, 1, 2000), h.num('from', 0, 0, 10 ** 11),
                               h.num('to', 0, 0, 10 ** 11)), 'node': node_name()}


@route('POST', '/api/ha')
def _ha_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    if act == 'readdress':
        # A node's address changed: this node's side put right, the other
        # told (1.0.106).
        try:
            return ha_readdress(h.store, str(b.get('mine') or ''), str(b.get('peer') or ''),
                                by=s['name'], daemon=h.d)
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'tls_off':
        # TLS between the databases off again, both nodes (1.0.107).
        try:
            return hatls_off(h.store, s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'tls_link':
        # Encrypt and check the link between the databases, both nodes,
        # without stopping anything (1.0.104).
        try:
            return hatls_start(h.store, s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'errors':
        h.store.add_event('settings', '%s read the replication errors in PostgreSQL\'s log'
                          % s['name'], who=s['name'])
        return repl_errors(h.store, ask_log=bool(b.get('log', True)))
    if act == 'history_clear':
        # What the nodes saw is deleted; what was done by hand stays in
        # Events (the audit) and is only no longer shown here (1.0.56).
        now = time.time()
        n = h.store.db.run("DELETE FROM events WHERE kind = 'ha' AND ts <= ?", (now,))
        h.store.set_meta('ha:history_cleared', str(now))
        h.store.add_event('settings', '%s cleared the cluster\'s history' % s['name'], 'warn',
                          who=s['name'])
        return {'message': 'the history is cleared', 'gone': n if isinstance(n, int) else None}
    if act == 'errors_clear':
        repl_errors_clear(h.store, s['name'])
        h.store.add_event('settings', '%s cleared the replication errors of %s (counted from now '
                          'on)' % (s['name'], node_name()), who=s['name'])
        return {'message': 'cleared: the errors are counted from now on', **repl_errors(
            h.store, ask_log=False)}
    if act == 'bundle':
        try:
            if CONFIG.get('ha_mode') == 'replicated':
                # The second node of two replicating ones - or the same one
                # again, after it was lost or reinstalled.
                data = {'mode': 'replicated', 'key': sealing_key(make=True).hex(),
                        'pg_major': int(h.store.db.value('SHOW server_version_num')) // 10000,
                        'slot': 3 - int(CONFIG.get('ha_slot') or 1),
                        'db': {'db_name': CONFIG.get('db_name'), 'db_user': CONFIG.get('db_user'),
                               'db_password': CONFIG.get('db_password')},
                        'peer': {'name': node_name(), 'slot': int(CONFIG.get('ha_slot') or 1),
                                 'address': CONFIG.get('ha_address') or node_address(),
                                 'port': int(CONFIG.get('db_port') or 5432)},
                        'cluster': CONFIG.get('site_name') or 'otp'}
                data['db']['db_host'] = data['peer']['address']
            else:
                data = ha_bundle_data(h.store, str(b.get('db_host') or '').strip())
        except ValueError as e:
            raise ApiError(400, str(e))
        phrase = ha_passphrase()
        locked = bundle_lock(data, phrase)
        h.store.add_event('settings', '%s made a bundle for a second node to join this one '
                          '(the database at %s) - it carries the key that opens every token'
                          % (s['name'], data['db']['db_host']), 'warn', who=s['name'])
        return {'bundle': locked, 'passphrase': phrase, 'db_host': data['db'].get('db_host', ''),
                'mode': data.get('mode') or 'shared',
                'name': 'otp-join-%s-%s.json' % (node_name(), datetime.now().strftime('%Y%m%d'))}
    if act == 'join':
        try:
            data = bundle_open(b.get('bundle'), str(b.get('passphrase') or ''))
            if data.get('mode') == 'replicated':
                raise ValueError('this bundle makes this node replicate with its own PostgreSQL, '
                                 'which takes root on this machine (installing and setting up '
                                 'PostgreSQL): copy it here and run  otp --ha-join FILE  as root')
            got = ha_join(data, str(b.get('name') or '').strip(), bool(b.get('even_if_data')),
                          s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('settings', '%s joined this node to the cluster of %s; it starts '
                          'again on %s' % (s['name'], (data.get('peer') or {}).get('name', '?'),
                                           got['where']), 'warn', who=s['name'])
        log('joining the cluster: starting again on %s' % got['where'], 'warn')
        threading.Timer(1.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
        got['restarting'] = True
        return got
    if act in ('pause', 'resume', 'pause_in', 'pause_out', 'resume_in', 'resume_out', 'stop',
               'refresh'):
        want = str(b.get('node') or '')
        if want and want != node_name() and act.endswith(('_in', '_out')):
            # One direction is the other one's opposite (1.0.94): behind a
            # balancer the request can reach the node the page did not show.
            raise ApiError(409, 'this request reached %s, not %s: open the page of %s itself '
                                '(its own address) to do that' % (node_name(), want, want))
        try:
            return ha_control(h.store, act, s['name'])
        except (ValueError, DbError) as e:
            raise ApiError(400, str(e).split('\n')[0][:400])
        except Exception as e:                          # noqa: BLE001
            raise ApiError(400, str(e).split('\n')[0][:400])
    if act == 'resync':
        want = str(b.get('node') or '')
        if want and want != node_name():
            # Behind a balancer the request can come to the other node
            # (1.0.59): it is refused, not that node rebuilt instead.
            raise ApiError(409, 'this request reached %s, not %s: open the page of %s itself '
                                '(its own address) to rebuild it' % (node_name(), want, want))
        try:
            return {'job': ha_resync_job(h.store, s['name'])}
        except ValueError as e:
            raise ApiError(400, str(e))
    if act == 'forget':
        try:
            ha_forget(h.store, str(b.get('name') or ''))
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('settings', '%s took the node %s off the list' % (s['name'], b.get('name')),
                          who=s['name'])
        return {'message': 'gone from the list; it comes back by itself if it is still running'}
    raise ApiError(400, 'no such thing to do')


# ---- TLS and the cluster's web address (1.0.47) ------------------------------------
@route('GET', '/api/web')
def _web(h):
    me = h.me()
    store = h.store
    nodes = []
    for n in ha_nodes(store):
        one = {k: n.get(k) for k in ('name', 'me', 'alive', 'address', 'version', 'maintenance',
                                     'age', 'host')}
        one['web'] = web_state(store) if n['me'] else (n.get('web') or {})
        nodes.append(one)
    if not any(x['me'] for x in nodes):
        nodes.insert(0, {'name': node_name(), 'me': True, 'alive': True,
                         'address': node_address(), 'web': web_state(store)})
    v = vip_conf(store)
    holder = [x['name'] for x in nodes if (x.get('web') or {}).get('vip_here')]
    return {'node': node_name(), 'cluster': bool(CONFIG.get('ha_mode')), 'nodes': nodes,
            'vip': dict(v, prefer_now=vip_prefer(store, v) if CONFIG.get('ha_mode') else '',
                        holder=holder),
            'tls': {t: tls_view(tls_profile(store, t)) for t in tls_targets(store)},
            'presets': TLS_PRESETS, 'dh': DH_WORDS,
            'may': me.get('role') == 'fulladmin'}


@route('POST', '/api/web')
def _web_do(h):
    s = h.me('fulladmin')
    who = s['name']
    b = h.body()
    act = str(b.get('action') or '')
    store = h.store
    target = str(b.get('target') or '')
    if act.startswith('tls_'):
        if target not in tls_targets(store):
            raise ApiError(400, 'there is no node or address called %s' % target)
        prof = tls_profile(store, target) or {}
        words = 'the web address' if target == 'vip' else target
    if act in ('tls_upload', 'tls_selfsigned'):
        if act == 'tls_upload':
            pfx = b''
            if b.get('pfx'):
                try:
                    pfx = base64.b64decode(str(b['pfx']), validate=True)
                except (ValueError, binascii.Error):
                    raise ApiError(400, 'the PFX / PKCS#12 file did not arrive whole')
                if len(pfx) > 200000:
                    raise ApiError(400, 'that is far bigger than any certificate file')
            pending = unseal_secret(prof['pending_key'], 'web:tls') if prof.get('pending_key') \
                else ''
            got = cert_bundle(b.get('cert'), b.get('key'), b.get('chain'), b.get('root'), pfx,
                              str(b.get('password') or ''), pending)
            how = 'uploaded'
        else:
            names = [x.strip() for x in re.split(r'[\s,;]+', str(b.get('names') or '')) if x.strip()]
            key, crt = make_selfsigned(str(b.get('cn') or '').strip(), names,
                                       int(b.get('days') or 825), str(b.get('kind') or 'rsa2048'),
                                       org=str(b.get('org') or ''))
            got = cert_bundle(crt, key)
            how = 'self-signed, made here'
        info = got['info']
        if info.get('not_after') and info['not_after'] < time.time():
            raise ApiError(400, 'this certificate ran out on %s' % stamp(info['not_after']))
        prof.update(cert=got['cert'], chain=got['chain'], root=got['root'],
                    key=seal_secret(got['key'], 'web:tls'), info=info,
                    chain_info=got['chain_info'], root_info=got['root_info'],
                    verify=got['verify'], how=how)
        prof.pop('pending_key', None)
        prof.pop('csr', None)
        prof.setdefault('preset', 'standard')
        prof.setdefault('dh', 'none')
        tls_save(store, target, prof, who)
        store.add_event('settings', '%s put a certificate in for %s: %s (until %s)' % (
            who, words, info.get('subject'), stamp(info.get('not_after')) if info.get('not_after') else '?'), 'warn', who=who)
        return {'message': 'the certificate of %s is kept; the node%s put%s it in within a few '
                           'seconds' % (words, 's' if target == 'vip' else '',
                                        '' if target == 'vip' else 's'),
                'tls': tls_view(prof)}
    if act == 'tls_csr':
        names = [x.strip() for x in re.split(r'[\s,;]+', str(b.get('names') or '')) if x.strip()]
        key, csr = make_csr(str(b.get('cn') or '').strip(), names, str(b.get('kind') or 'rsa2048'),
                            org=str(b.get('org') or ''), unit=str(b.get('unit') or ''),
                            country=str(b.get('country') or ''), city=str(b.get('city') or ''))
        prof.update(pending_key=seal_secret(key, 'web:tls'), csr=csr,
                    csr_at=time.time(), csr_cn=str(b.get('cn') or ''))
        tls_save(store, target, prof, who)
        store.add_event('settings', '%s made a certificate request for %s (%s)'
                        % (who, words, b.get('cn')), who=who)
        return {'message': 'the request is made: give it to your certificate authority, then '
                           'upload what it sends back - the key waits here', 'csr': csr,
                'tls': tls_view(prof)}
    if act == 'tls_csr_drop':
        prof.pop('pending_key', None)
        prof.pop('csr', None)
        tls_save(store, target, prof, who)
        return {'message': 'the request and its waiting key are gone', 'tls': tls_view(prof)}
    if act == 'tls_policy':
        prof.update(tls_policy_checked(b))
        tls_save(store, target, prof, who)
        store.add_event('settings', '%s changed the TLS settings of %s: %s, DH %s%s' % (
            who, words, prof['preset'], prof['dh'],
            ', HSTS %d s' % prof['hsts'] if prof.get('hsts') else ''), who=who)
        slow = prof['dh'] in ('gen3072', 'gen4096')
        return {'message': 'the TLS settings of %s are kept%s' % (
            words, '; making the DH parameters takes a while' if slow else ''),
                'tls': tls_view(prof)}
    if act == 'tls_forget':
        store.db.run('DELETE FROM meta WHERE k = ?', ('web:tls:' + target,))
        store.add_event('settings', '%s: otp no longer looks after the TLS of %s (nginx keeps '
                        'what it has)' % (who, words), 'warn', who=who)
        return {'message': 'otp no longer looks after the TLS of %s; nginx keeps the files it '
                           'has' % words}
    if act == 'tls_pem':
        if not prof.get('cert'):
            raise ApiError(404, 'no certificate is kept for %s' % words)
        return {'pem': prof['cert'] + (prof.get('chain') or ''), 'csr': prof.get('csr') or ''}
    if act in ('vip_save', 'vip_on', 'vip_off', 'vip_move'):
        if not CONFIG.get('ha_mode'):
            raise ApiError(409, 'the web address is for a cluster: make this node one of two '
                                'first (Settings - High availability)')
    if act == 'vip_save':
        v = vip_set(store, who, **vip_checked(b, store))
        store.add_event('settings', '%s set the web address: %s%s, VRRP id %d' % (
            who, v['address'], ' (%s)' % v['fqdn'] if v['fqdn'] else '', v['vrid']), who=who)
        return {'message': 'the web address is kept%s' % (
            '; each node puts it in within a few seconds' if v.get('on') else
            ' - turn it on when ready')}
    if act == 'vip_on':
        v = vip_conf(store)
        if not v.get('address'):
            raise ApiError(400, 'give the address first')
        vip_set(store, who, on=True)
        store.add_event('settings', '%s turned the web address %s on' % (who, v['address']),
                        'warn', who=who)
        return {'message': 'the web address is on: each node installs keepalived if it has to '
                           'and the address comes up on %s' % vip_prefer(store)}
    if act == 'vip_off':
        vip_set(store, who, on=False)
        store.add_event('settings', '%s turned the web address off' % who, 'warn', who=who)
        return {'message': 'the web address is off: keepalived stops on both nodes'}
    if act == 'vip_mode':
        mode = str(b.get('mode') or '')
        if mode not in ('back', 'stays'):
            raise ApiError(400, 'back or stays')
        changes = {'mode': mode}
        if mode == 'back':
            to = str(b.get('prefer') or '')
            if to and to not in {n['name'] for n in ha_nodes(store)}:
                raise ApiError(400, 'there is no node called %s' % to)
            if to:
                changes['prefer'] = to
        vip_set(store, who, **changes)
        v = vip_conf(store)
        store.add_event('settings', '%s: the web address %s' % (who, (
            'always goes back to %s' % vip_prefer(store, v)) if mode == 'back' else
            'stays where it is - it moves only when that node fails or by hand'), 'warn',
            who=who)
        return {'message': 'kept'}
    if act == 'vip_move':
        to = str(b.get('to') or '')
        nodes = {n['name']: n for n in ha_nodes(store)}
        if to not in nodes:
            raise ApiError(400, 'there is no node called %s' % to)
        if not nodes[to].get('alive'):
            raise ApiError(409, '%s is not answering: the address cannot go there' % to)
        if vip_conf(store).get('mode') == 'stays':
            vip_set(store, who, move_to=to, move_at=time.time())
            store.add_event('settings', '%s moved the web address to %s (it stays there)'
                            % (who, to), 'warn', who=who)
            return {'message': 'the web address goes to %s within a few seconds and stays '
                               'there' % to}
        vip_set(store, who, prefer=to)
        store.add_event('settings', '%s moved the web address to %s' % (who, to), 'warn', who=who)
        return {'message': 'the web address goes to %s within a few seconds (if it is healthy)'
                           % to}
    if act == 'retry':
        node = str(b.get('node') or node_name())
        if node not in {n['name'] for n in ha_nodes(store)} | {node_name()}:
            raise ApiError(400, 'there is no node called %s' % node)
        store.set_meta('web:retry:' + node, str(time.time()))
        return {'message': '%s tries again within a few seconds' % node}
    raise ApiError(400, 'no such thing to do')


# ---- the local firewall, who may reach which pages (1.0.52) ---------------------------
FW_WAIT = threading.Lock()


@route('GET', '/api/firewall')
def _firewall(h):
    me = h.me('tokenadmin')     # the map of the network, not for every reader (1.0.57)
    store = h.store
    fresh = h.arg('fresh')
    if fresh and fresh in ('1', node_name()):
        fw_now_ask()            # this node's firewall read again, now (1.0.67)
    elif fresh and fresh in [n['name'] for n in ha_nodes(store) if not n['me']]:
        # The other node's (1.0.71): asked through the database, and waited
        # for - its daemon looks every 5 s, root reads it, the row comes back.
        t0 = time.time()
        try:
            had = float(json.loads(store.get_meta('fw:now:' + fresh) or '{}').get('full_at') or 0)
        except (ValueError, AttributeError, TypeError):
            had = 0
        store.set_meta('fw:ask:' + fresh, str(t0))
        # One page waiting at a time (1.0.101): each held a worker of the
        # pages for up to 15 s, and a dozen of them stalled the enrolment
        # pages and the health check with it. The others are answered with
        # what is known now.
        if FW_WAIT.acquire(False):
            try:
                while time.time() - t0 < 15:
                    time.sleep(0.5)
                    try:
                        if float(json.loads(store.get_meta('fw:now:' + fresh) or '{}')
                                 .get('full_at') or 0) > had:
                            break
                    except (ValueError, AttributeError, TypeError):
                        pass
            finally:
                FW_WAIT.release()
    nodes = []
    for n in ha_nodes(store):
        w = web_state(store) if n['me'] else (n.get('web') or {})
        fwv = dict(w.get('fw') or {})
        if not n['me']:
            try:
                fwv.update(json.loads(store.get_meta('fw:now:' + n['name']) or '{}'))
            except ValueError:
                pass
        nodes.append({'name': n['name'], 'me': n['me'], 'alive': n.get('alive'),
                      'address': n.get('address'), 'version': n.get('version'),
                      'fw': fwv, 'access': w.get('access') or {},
                      'state': w.get('state') or '', 'said': w.get('said') or [],
                      'current': w.get('current'), 'waiting': w.get('waiting'),
                      'progress': w.get('progress'),
                      'auto': fw_auto(store, n['name'])})
    if not any(x['me'] for x in nodes):
        w = web_state(store)
        nodes.insert(0, {'name': node_name(), 'me': True, 'alive': True,
                         'address': node_address(), 'fw': w.get('fw') or {},
                         'access': w.get('access') or {}, 'state': w.get('state') or '',
                         'said': w.get('said') or [], 'current': w.get('current'),
                         'waiting': w.get('waiting'), 'progress': w.get('progress'),
                         'auto': fw_auto(store, node_name())})
    c = fw_conf(store)
    a = access_conf(store)
    if not a:
        # Not set here yet: what nginx says now, from this node.
        now = next((x['access'] for x in nodes if x['me']), {}) or {}
        a = {k: {'any': bool((now.get(k) or {}).get('any', k == 'health')),
                 'from': list((now.get(k) or {}).get('from') or [])} for k in ACCESS_WORDS}
        a['from_nginx'] = True
    return {'node': node_name(), 'cluster': bool(CONFIG.get('ha_mode')), 'nodes': nodes,
            'conf': {'on': bool(c.get('on')), 'set': bool(c.get('set')), 'off': c.get('off') or [],
                     'rules': c.get('rules') or [], 'by': c.get('by'), 'at': c.get('at')},
            'access': a, 'access_words': ACCESS_WORDS,
            'inner': {x['name']: cluster_addresses(store, x['name']) for x in nodes},
            'optional': list(FW_AUTO_OPTIONAL), 'may': me.get('role') == 'fulladmin'}


def access_not_me_out(h, store, a, b):
    """Not the administration shut to the one saving it (1.0.57) - from every
    place it can be set (1.0.59)."""
    adm = a.get('admin') or {}
    if adm.get('any') or b.get('even_if_me'):
        return
    try:
        me_ip = ipaddress.ip_address(h.client_ip())
        inside = me_ip.is_loopback or any(
            me_ip in ipaddress.ip_network(n, strict=False) for n in adm.get('from') or [])
    except ValueError:
        inside = True
    if not inside and h.client_ip() not in cluster_addresses(store, node_name()):
        raise ApiError(409, 'your own address (%s) is not among the networks that may reach '
                            'the administration: you would be shut out. Add it, or let '
                            'everybody in' % h.client_ip())


@route('POST', '/api/trial')
def _trial_do(h):
    """A change on trial (1.0.137): keep it, or put back what was there."""
    s = h.me('fulladmin')
    b = h.body()
    kind, act = str(b.get('kind') or ''), str(b.get('action') or '')
    if act not in ('keep', 'back'):
        raise ApiError(400, 'keep or back')
    try:
        if kind == 'net':
            node = str(b.get('node') or '')
            if node not in [n['name'] for n in ha_nodes(h.store)] + [node_name()]:
                raise ApiError(400, 'there is no node %s' % node)
            return {'message': net_trial_answer(h.store, node, act, s['name'])}
        if kind == 'fw':
            return {'message': fw_trial_answer(h.store, act, s['name'])}
    except ValueError as e:
        raise ApiError(409, str(e))
    raise ApiError(400, 'net or fw')


@route('POST', '/api/firewall')
def _firewall_do(h):
    s = h.me('fulladmin')
    who = s['name']
    b = h.body()
    act = str(b.get('action') or '')
    store = h.store
    c = fw_conf(store)
    if act == 'rule_check':
        return {'rule': fw_rule_checked(b.get('rule') if isinstance(b.get('rule'), dict) else {},
                                        store)}
    if act == 'save':
        # Everything at once, from the save bar (1.0.54).
        raw = b.get('rules') or []
        if not isinstance(raw, list) or len(raw) > 200:
            raise ApiError(400, 'two hundred rules at most')
        rules = []
        for x in raw:
            if not isinstance(x, dict):
                raise ApiError(400, 'a rule is not an object')
            r = fw_rule_checked(x, store)
            r['id'] = re.sub(r'[^0-9a-z]', '', str(x.get('id') or ''))[:16] or secrets.token_hex(4)
            if r['id'].startswith('n'):
                r['id'] = secrets.token_hex(4)
            rules.append(r)
        off = [k for k in (b.get('off') or []) if k in FW_AUTO_OPTIONAL]
        was = fw_conf(store)
        said = []
        if 'access' in b and isinstance(b.get('access'), dict):
            a = access_checked_api(b['access'])
            access_not_me_out(h, store, a, b)
            fw_trial_begin(store, who)
            store.set_meta('web:access', json.dumps(dict(a, at=time.time(), by=who)))
            said.append('who may reach the pages: %s' % '; '.join(
                '%s %s' % (k, 'everybody' if v['any'] else ', '.join(v['from']))
                for k, v in a.items()))
        on = bool(b.get('on'))
        if on != bool(was.get('on')):
            said.append('otp\'s firewall rules %s' % ('on' if on else 'off'))
        if rules != (was.get('rules') or []):
            said.append('%d rule(s) of your own' % len(rules))
        if sorted(off) != sorted(was.get('off') or []):
            said.append('turned off: %s' % (', '.join(off) or 'nothing'))
        fw_set(store, who, on=on, off=off, rules=rules)
        if said:
            store.add_event('settings', '%s changed the firewall and access: %s'
                            % (who, ' · '.join(said)), 'warn', who=who)
        return {'message': 'saved; each node puts it in within a few seconds'}
    if act in ('on', 'off'):
        fw_set(store, who, on=act == 'on')
        store.add_event('settings', '%s turned otp\'s firewall rules %s' % (who, act), 'warn',
                        who=who)
        return {'message': 'otp\'s rules are %s; each node puts that in within a few seconds'
                           % ('on' if act == 'on' else 'taken away (the rest of the firewall '
                                                       'stays as it was)')}
    if act == 'auto':
        key = str(b.get('key') or '')
        if key not in FW_AUTO_OPTIONAL:
            raise ApiError(400, 'that one cannot be turned off')
        off = [k for k in c.get('off') or [] if k != key]
        if not b.get('on'):
            off.append(key)
        fw_set(store, who, off=off)
        store.add_event('settings', '%s turned the firewall rule for %s %s' % (
            who, key, 'on' if b.get('on') else 'off'), 'warn', who=who)
        return {'message': 'kept'}
    if act in ('rule_add', 'rule_save'):
        r = fw_rule_checked(b.get('rule') if isinstance(b.get('rule'), dict) else {}, store)
        rules = list(c.get('rules') or [])
        if act == 'rule_add':
            if len(rules) >= 200:
                raise ApiError(400, 'two hundred rules at most')
            r['id'] = secrets.token_hex(4)
            rules.append(r)
        else:
            i = next((i for i, x in enumerate(rules) if x.get('id') == b.get('id')), None)
            if i is None:
                raise ApiError(404, 'no such rule')
            r['id'] = rules[i]['id']
            rules[i] = r
        fw_set(store, who, rules=rules)
        store.add_event('settings', '%s %s a firewall rule: %s %s%s%s (%s)' % (
            who, 'added' if act == 'rule_add' else 'changed', r['action'], r['proto'],
            ' ' + r['port'] if r['port'] else '', ' from ' + r['source'] if r['source'] else '',
            r['scope']), 'warn', who=who)
        return {'message': 'kept', 'id': r['id']}
    if act == 'rule_drop':
        rules = [x for x in c.get('rules') or [] if x.get('id') != b.get('id')]
        fw_set(store, who, rules=rules)
        store.add_event('settings', '%s took a firewall rule away' % who, 'warn', who=who)
        return {'message': 'gone'}
    if act == 'rule_move':
        rules = list(c.get('rules') or [])
        i = next((i for i, x in enumerate(rules) if x.get('id') == b.get('id')), None)
        if i is None:
            raise ApiError(404, 'no such rule')
        j = i + (-1 if b.get('dir') == 'up' else 1)
        if 0 <= j < len(rules):
            rules[i], rules[j] = rules[j], rules[i]
            fw_set(store, who, rules=rules)
            # The order decides which rule wins (1.0.146): written down as the others.
            store.add_event('settings', '%s moved a firewall rule %s (now %d of %d)' % (
                who, 'up' if j < i else 'down', j + 1, len(rules)), 'warn', who=who)
        return {'message': 'moved'}
    if act == 'access':
        a = access_checked_api(b)
        access_not_me_out(h, store, a, b)      # here too (1.0.59)
        fw_trial_begin(store, who)
        store.set_meta('web:access', json.dumps(dict(a, at=time.time(), by=who)))
        store.add_event('settings', '%s set who may reach the pages: %s' % (who, '; '.join(
            '%s %s' % (k, 'everybody' if v['any'] else ', '.join(v['from'])) for k, v in a.items())),
            'warn', who=who)
        return {'message': 'kept; each node\'s nginx takes it within a few seconds (the other '
                           'node and the web address are always let in)'}
    raise ApiError(400, 'no such thing to do')


# ---- the texts of the messages (1.0.103) -------------------------------------------
@route('GET', '/api/texts')
def _texts(h):
    s = h.me()
    mid = h.arg('render')
    if mid:
        if not text_message(mid):
            raise ApiError(404, 'no such message')
        lang = h.arg('lang') if h.arg('lang') in TEXT_LANGS else 'cs'
        return text_render(h.store, mid, lang, mark=h.arg('mark') == '1')
    return {'messages': text_state(h.store), 'placeholders': TEXT_PLACEHOLDERS,
            'langs': list(TEXT_LANGS), 'may_change': s['role'] == 'fulladmin',
            'samples': {lang: text_samples(lang) for lang in TEXT_LANGS},
            'sender': '%s <%s>' % (CONFIG.get('mail_from_name') or CONFIG.get('site_name') or
                                   socket.gethostname(), CONFIG.get('mail_from') or ''),
            'sms_plain': bool(CONFIG.get('sms_plain', 1)), 'node': node_name(),
            'ha': bool(CONFIG.get('ha_mode'))}


@route('POST', '/api/texts')
def _texts_do(h):
    b = h.body()
    act = str(b.get('action') or '')
    s = h.me('fulladmin') if act in ('save', 'reset', 'test') else h.me()
    mid = str(b.get('id') or '')
    m = text_message(mid)
    lang = str(b.get('lang') or '')
    if not m or lang not in TEXT_LANGS:
        raise ApiError(400, 'no such message or language')
    fields = b.get('fields') if isinstance(b.get('fields'), dict) else {}
    if act == 'preview':
        # What the editor holds now, each field checked and cleaned as a
        # save would - and said which one is wrong, not saved.
        clean, bad = {}, {}
        for f in m['fields']:
            if f[0] in fields:
                try:
                    clean[f[0]] = text_check(f, fields[f[0]])
                except ValueError as e:
                    bad[f[0]] = str(e)
        out = text_render(h.store, mid, lang, clean)
        out['bad'] = bad
        out['clean'] = clean
        return out
    if act == 'save':
        try:
            new = text_save(h.store, mid, lang, fields, s['name'],
                            was_at=b.get('was_at') if 'was_at' in b else None)
        except TextConflict as e:
            raise ApiError(409, str(e))
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.add_event('settings', '%s changed the texts of “%s” (%s)'
                          % (s['name'], m['title'], lang.upper()), who=s['name'])
        return {'message': 'saved - both nodes send these words now', 'saved': new,
                'state': text_state(h.store, mid)[0]}
    if act == 'reset':
        keys = [str(k) for k in (b.get('keys') or []) if isinstance(k, str)]
        text_reset(h.store, mid, lang, keys or None)
        h.store.add_event('settings', '%s put %s of “%s” (%s) back as it comes'
                          % (s['name'], 'the texts' if not keys else ', '.join(keys), m['title'],
                             lang.upper()), 'warn', who=s['name'])
        return {'message': 'put back as it comes', 'state': text_state(h.store, mid)[0]}
    if act == 'test':
        key = h.throttle('texts-test', 10, 15, name=s['name'])
        h.failed(key)
        to = str(b.get('to') or '').strip()
        clean = {}
        for f in m['fields']:
            if f[0] in fields:
                try:
                    clean[f[0]] = text_check(f, fields[f[0]])
                except ValueError as e:
                    raise ApiError(400, str(e))
        w = text_words(mid, lang, clean)
        smp = text_samples(lang)
        try:
            if m['kind'] == 'sms':
                to = dest_checked('sms', to)
                said = sms_send(to, sms_plain(w[m['fields'][0][0]].format(**smp)))
            elif m['kind'] == 'mail':
                to = dest_checked('mail', to)
                if m['group'] == 'code':
                    msg = code_message('mail', to, smp['code'], m['purpose'], lang=lang,
                                       name=smp['account'], display=smp['name'], fmt='html', w=w)
                else:
                    picture = {'issuer': smp['site'], 'digits': smp['digits'],
                               'period': smp['period'], 'secret': 'JBSWY3DPEHPK3PXP',
                               'secret_spaced': 'JBSW Y3DP EHPK 3PXP', 'label': smp['account'],
                               'uri': 'otpauth://totp/example?secret=JBSWY3DPEHPK3PXP'}
                    msg = token_mail(to, smp['account'], picture,
                                     codes=['10473829', '58261047', '39182754', '74629103',
                                            '21857364'],
                                     lang=lang, display=smp['name'], by=s['name'], pending=True,
                                     w=w)
                steps = mail_deliver(h.store, msg, [to], kind='test', by=s['name'],
                                     purpose='texts')
                last = [x for x in steps if x.get('ok')]
                said = (last[-1].get('said') or 'sent') if last else 'sent'
            else:
                raise ApiError(400, 'what the VPN shows cannot be sent')
        except ValueError as e:
            raise ApiError(400, str(e))
        except (MailError, SmsError) as e:
            raise ApiError(502, str(e))
        h.store.add_event('settings', '%s sent a sample of “%s” (%s) to %s'
                          % (s['name'], m['title'], lang.upper(), to), who=s['name'])
        return {'message': 'sent to %s with sample values: %s' % (to, said)}
    raise ApiError(400, 'no such thing to do with the texts')
