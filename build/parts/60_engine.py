

# ---------------------------------------------------------------------------
# A directory, as the realms and the sign-ins use it
# ---------------------------------------------------------------------------
# Several servers, asked in the order given: one that cannot be reached is
# passed over for the next, one that answers is believed. Two questions are
# asked of it all day - who is this, and which groups are they in - and
# their answers are kept for a minute, because a VPN asks twice in a row for
# the same person more often than not.

AD_UAC_DISABLED = 0x2
AD_NEVER = (0, 0x7FFFFFFFFFFFFFFF)
USER_ATTRS = ('distinguishedName', 'sAMAccountName', 'userPrincipalName', 'displayName',
              'mail', 'userAccountControl', 'accountExpires', 'memberOf', 'lockoutTime',
              'pwdLastSet', 'department', 'title', 'mobile', 'telephoneNumber',
              'objectClass', 'msDS-User-Account-Control-Computed', 'objectSid')
# msDS-User-Account-Control-Computed (1.0.101): what AD works out now -
# locked out (0x10) and the password expired (0x800000). lockoutTime alone
# stays set after the lockout is over.
AD_UACC_LOCKED = 0x10
AD_UACC_PW_EXPIRED = 0x800000
# Where a person's e-mail address and mobile number are read (1.0.229), in the order tried -
# the first with a value is taken. As until now unless changed on the directory's card.
DIR_MAIL_DEFAULT = ('mail',)
# The name of an attribute (RFC 4512): a word of letters, digits and dashes - any of a schema of
# one's own (extensionAttribute5, companyMobile) - or its OID, 1.2.840.113556.1.4.1234.
DIR_ATTR_NAME = re.compile(r'^(?:[A-Za-z][A-Za-z0-9-]{0,99}|[0-9]+(?:\.[0-9]+){1,40})\Z')
DIR_MOBILE_DEFAULT = ('mobile', 'telephoneNumber')


def dir_attr_list(value, default):
    """The attributes of a mapping as saved - "mobile, telephoneNumber" - or the default."""
    out = []
    for one in re.split(r'[,;\s]+', str(value or '')):
        one = one.strip()
        if one and DIR_ATTR_NAME.match(one) and one.lower() not in [x.lower() for x in out]:
            out.append(one)
    return tuple(out[:4]) or tuple(default)


def dir_attr_checked(value, what):
    """The mapping typed on the card, checked: '' for the default."""
    words = [w for w in re.split(r'[,;\s]+', str(value or '').strip()) if w]
    if len(words) > 4:
        raise ValueError('%s: four attributes at most' % what)
    for w in words:
        if not DIR_ATTR_NAME.match(w):
            raise ValueError('%s: %r is not the name of an attribute' % (what, w))
    return ', '.join(words)


def entry_mail(a, attrs):
    """The e-mail address of an entry (its attributes, names in small letters) by the mapping:
    proxyAddresses read as Exchange keeps it - the primary SMTP: one first, no prefix."""
    for attr in attrs:
        vals = [str(v).strip() for v in (a.get(attr.lower()) or []) if str(v).strip()]
        if attr.lower() == 'proxyaddresses':
            smtp = [v for v in vals if v.lower().startswith('smtp:')]
            smtp.sort(key=lambda v: not v.startswith('SMTP:'))
            vals = [v.split(':', 1)[1] for v in smtp]
        if vals:
            return vals[0]
    return ''


def entry_first(a, attrs):
    for attr in attrs:
        for v in a.get(attr.lower()) or []:
            if str(v).strip():
                return str(v).strip()
    return ''


def _ad_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _ad_span(v, zero_is=None):
    """An interval of Active Directory (negative hundreds of nanoseconds) as seconds; the
    largest negative number is "never". `zero_is`: what 0 means for this one."""
    n = _ad_int(v)
    if n is None:
        return None
    if n == 0:
        return zero_is
    if n <= -0x7FFFFFFFFFFFFFFF or n >= 0x7FFFFFFFFFFFFFFF:
        return 'never'
    return abs(n) / 1e7


def policy_recommend(pol):
    """The cap of wrong directory passwords for these pages that keeps the account from being
    locked by guesses made here: below the lowest lockout threshold that may apply."""
    lock = pol.get('lockout') or {}
    found = []
    if (lock.get('threshold') or 0) > 0:
        found.append((lock['threshold'], 'the domain', lock.get('window_s')))
    for p in pol.get('psos') or []:
        if (p.get('threshold') or 0) > 0:
            found.append((p['threshold'], 'the policy %s' % p['name'], p.get('window_s')))
    if not found:
        return {'tries': 10, 'window_min': 30, 'threshold': 0, 'from': '',
                'why': 'The directory never locks an account after wrong passwords - a cap here '
                       'still slows down guessing.'}
    t, src, _w = min(found, key=lambda x: x[0])
    windows = [w for _t, _s, w in found if isinstance(w, (int, float))]
    window = int(math.ceil(max(windows) / 60.0)) if windows else 30
    tries = max(1, t - 2) if t > 3 else max(1, t - 1)
    if t <= 1:
        # Locked at the first wrong password (1.0.234): no cap here keeps it from that.
        return {'tries': 1, 'window_min': max(1, min(1440, window)), 'threshold': t, 'from': src,
                'why': 'The account is locked at its first wrong password - no cap here can keep '
                       'that from happening; 1 at least keeps it to one wrong password from here.'}
    if src == 'the domain':
        why = ('The domain locks an account after %d wrong passwords: %d here leave the person %d '
               'of their own before it locks.' % (t, tries, t - tries))
    else:
        why = ('The policy %s locks an account after %d wrong passwords: %d here leave the person %d '
               'of their own before it locks.' % (src[len('the policy '):], t, tries, t - tries))
    return {'tries': tries, 'window_min': max(1, min(1440, window)), 'threshold': t, 'from': src,
            'why': why}


def ad_time(value):
    """A Windows time (hundreds of nanoseconds since 1601) as seconds since
    1970, or None for never."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n in AD_NEVER or n <= 0:
        return None
    return n / 10000000.0 - 11644473600


class Directory(object):
    """One directory from the table, made usable."""

    CACHE_S = 60
    USER_CACHE_S = 15

    def __init__(self, row):
        self.row = row
        self.name = row['name']
        self.hosts = [h.strip() for h in str(row.get('hosts') or '').split(',') if h.strip()]
        self.port = int(row.get('port') or 636)
        self.tls = row.get('tls') or 'ldaps'
        # NULL (a row imported or moved without it) is verify, never off (1.0.57).
        self.verify = row.get('verify') is None or bool(int(row.get('verify') or 0))
        self.ca = row.get('ca') or ''
        self.weak = bool(int(row.get('weak') or 0))    # old, weak certificates (1.0.77)
        self.base = row.get('base') or ''
        self.bind_dn = row.get('bind_dn') or ''
        self.bind_pw = row.get('bind_pw') or ''
        self.timeout = float(row.get('timeout_s') or 10)
        self.mail_attrs = dir_attr_list(row.get('mail_attr'), DIR_MAIL_DEFAULT)
        self.mobile_attrs = dir_attr_list(row.get('mobile_attr'), DIR_MOBILE_DEFAULT)
        have = {x.lower() for x in USER_ATTRS}
        self.user_attrs = USER_ATTRS + tuple(x for x in self.mail_attrs + self.mobile_attrs
                                             if x.lower() not in have)
        self.cache = {}
        self.lock = threading.Lock()
        self.last_good = None

    def _hostport(self, host):
        host = str(host).strip()
        # [fd00::1]:636 and [fd00::1] as well (1.0.44); a bare IPv6 address
        # has no port of its own.
        m = re.match(r'^\[([^\]]+)\](?::(\d+))?\Z', host)
        if m:
            return m.group(1), int(m.group(2) or self.port)
        m = re.match(r'^([^:]+)(?::(\d+))?\Z', host)
        if m:
            return m.group(1), int(m.group(2) or self.port)
        return host, self.port

    # Servers that did not answer, and until when they are passed over
    # (1.0.101): every request asked each of them in turn and waited out its
    # timeout first - with two dead servers of 10 s, every sign-in of every
    # realm waited 20 s and the workers were all taken. Shared by every
    # directory object (a reload makes new ones).
    DEAD = {}
    DEAD_S = 30
    DEAD_LOCK = threading.Lock()

    # How many RADIUS workers one directory may hold at once (1.0.149): half
    # of them. A directory answering in seconds took every worker, and the
    # realms of the code alone - which never ask it - went unanswered too.
    BUSY = {}
    BUSY_LOCK = threading.Lock()
    BUSY_FREED = threading.Condition(BUSY_LOCK)
    BUSY_WAIT_S = 2.0
    BUSY_TOOK = {}                  # how long a request held it lately, by directory (1.0.224)
    BUSY_WAITING = {}
    BUSY_QUICK_S = 0.5

    @contextlib.contextmanager
    def held(self):
        if not threading.current_thread().name.startswith('radius'):
            yield                       # the pages and the command line: not counted
            return
        # The workers running, not the setting (1.0.265): changed on the page, the setting
        # counted 64 workers while 16 ran - a slow directory took them all.
        workers = int(RADIUS_WORKERS_RUNNING[0] or CONFIG.get('radius_workers') or 16)
        most = max(2, workers // 2)
        key = self.name.lower()
        # A place waited for (1.0.222), a little: refused the moment 8 were inside, a
        # directory answering in milliseconds turned right passwords away whenever some
        # came at once. One that is really slow still holds no more than its half - the
        # wait is short and the realms of the code alone keep the rest.
        until = time.monotonic() + min(self.BUSY_WAIT_S, float(getattr(self, 'timeout', 0) or 10))
        # Waited for only while the directory answers quickly (1.0.224): a worker waiting is a
        # worker taken from everybody, and with a directory slow the realms of the code alone
        # waited behind them again - refused at once then, as before 1.0.222. And no more
        # waiting than a quarter of the workers.
        quick = self.BUSY_TOOK.get(key, 0.0) < self.BUSY_QUICK_S
        with self.BUSY_FREED:
            waited = False
            while True:
                n = self.BUSY.get(key, 0)
                # Every directory together too (1.0.186): two of them listed (the
                # same domain controllers twice, say) held every worker between
                # them, and the realms of the code alone waited.
                total = sum(self.BUSY.values())
                if n < most and total < max(2, workers - 4):
                    break
                left = until - time.monotonic()
                if left <= 0 or not quick or (not waited and sum(self.BUSY_WAITING.values()) >=
                                              max(1, workers // 4)):
                    many = n if n >= most else total
                    if quick:
                        # The directory answers quickly; the requests wait here - for this
                        # node's CPU, its database (1.0.265). Said so, not "answering slowly".
                        e = LdapUnreachable('this node is busy: %d requests wait for the directory '
                                            '%s already - this one is not added to them'
                                            % (many, self.name))
                    elif n >= most:
                        e = LdapUnreachable('%s is answering slowly: %d requests wait on it already - '
                                            'this one is not added to them' % (self.name, n))
                    else:
                        e = LdapUnreachable('the directories are answering slowly: %d requests wait '
                                            'on them already - this one is not added to them' % total)
                    e.held = True       # this node's own limit - not the directory gone (1.0.224)
                    # The refusal's reason (1.0.265): no longer "LDAP server(s) have gone away".
                    e.busy_said = 'this node is busy: %d requests wait for the directory %s%s' % (
                        many, self.name, '' if quick else ', which answers slowly (%d ms a request)'
                        % int(self.BUSY_TOOK.get(key, 0.0) * 1000))
                    if waited:
                        # Given back (1.0.226): kept, four refused waits stopped every wait after
                        # them until a restart.
                        self.BUSY_WAITING[key] = max(0, self.BUSY_WAITING.get(key, 1) - 1)
                    raise e
                if not waited:
                    waited = True
                    self.BUSY_WAITING[key] = self.BUSY_WAITING.get(key, 0) + 1
                try:
                    self.BUSY_FREED.wait(left)
                except BaseException:
                    self.BUSY_WAITING[key] = max(0, self.BUSY_WAITING.get(key, 1) - 1)
                    raise
            if waited:
                self.BUSY_WAITING[key] = max(0, self.BUSY_WAITING.get(key, 1) - 1)
            self.BUSY[key] = n + 1
        # Only the time spent waiting on the directory itself is its own (1.0.265): measured
        # from the start to the end, this node's own work - TLS, reading the answers, the
        # other threads holding the CPU - counted as the directory slow, and past 0.5 s
        # every request beyond the limit was refused at once.
        was_io = getattr(LDAP_IO, 's', None)
        LDAP_IO.s = 0.0
        try:
            yield
        finally:
            took = float(getattr(LDAP_IO, 's', 0.0) or 0.0)
            LDAP_IO.s = was_io
            with self.BUSY_FREED:
                self.BUSY[key] = max(0, self.BUSY.get(key, 1) - 1)
                was = self.BUSY_TOOK.get(key)
                self.BUSY_TOOK[key] = took if was is None else was * 0.7 + took * 0.3
                self.BUSY_FREED.notify_all()

    def _order(self):
        """The servers in the order to ask them: the one that answered last
        first, those that did not answer lately last - and when none has,
        one try every few seconds, the rest refused at once."""
        order = [h for h in self.hosts if h]
        if self.last_good in order:
            order.remove(self.last_good)
            order.insert(0, self.last_good)
        t = time.time()
        with self.DEAD_LOCK:
            live = [h for h in order if self.DEAD.get(h.lower(), 0) <= t]
            if live:
                return live + [h for h in order if h not in live]
            probe = self.DEAD.get('probe:' + self.name.lower(), 0)
            if probe > t - 5:
                return []
            self.DEAD['probe:' + self.name.lower()] = t
        return order[:1]

    def _down(self, host):
        with self.DEAD_LOCK:
            if len(self.DEAD) > 1000:
                self.DEAD.clear()
            self.DEAD[str(host).lower()] = time.time() + self.DEAD_S
        self._pool_drop(host)

    # ---- the reading account's connections kept (1.0.265) -----------------------------
    # A new TCP connection, TLS and a bind of the reading account for every look-up was most
    # of what a sign-in cost the directory and this node. A few are kept a server, signed in
    # as the reading account only (a person's password is always checked on a connection of
    # its own, closed after it): taken by one request at a time, given back only after an
    # answer read whole, looked at before each use (closed by the server, data nobody asked
    # for: thrown away), and closed after 30 s unused or 5 min of age - a domain controller
    # restarted, a new certificate, the order of the servers are not missed for long. A kept
    # one that fails is not the server down: the same server is asked again on a new one.
    POOL = {}
    POOL_LOCK = threading.Lock()
    POOL_MOST = 8
    POOL_IDLE_S = 30.0
    POOL_AGE_S = 300.0
    POOL_SWEPT = [0.0]

    def _pool_key(self, host):
        h, p = self._hostport(host)
        return (h.lower(), p, self.tls, hashlib.sha256(self.ca.encode('utf-8')).hexdigest(),
                self.verify, self.weak, self.timeout, self.bind_dn,
                hashlib.sha256(str(self.bind_pw).encode('utf-8')).hexdigest())

    @staticmethod
    def _link_fresh(link):
        sock = getattr(link, 'sock', None)
        if sock is None or link.buffer:
            return False
        try:
            if isinstance(sock, ssl.SSLSocket) and sock.pending():
                return False
            readable, _w, _x = select.select([sock], [], [], 0)
            # Anything to read before a question is the server closing, or a notice of
            # disconnection - not to be read as the answer to the next one.
            return not readable
        except (OSError, ValueError):
            return False

    @classmethod
    def _pool_sweep(cls, force=False):
        t = time.monotonic()
        if not force and t - cls.POOL_SWEPT[0] < 10:
            return
        cls.POOL_SWEPT[0] = t
        old = []
        with cls.POOL_LOCK:
            for key in list(cls.POOL):
                keep = []
                for one in cls.POOL[key]:
                    (old if t - one[1] > cls.POOL_IDLE_S or t - one[2] > cls.POOL_AGE_S
                     else keep).append(one)
                if keep:
                    cls.POOL[key] = keep
                else:
                    del cls.POOL[key]
        for one in old:
            one[0].close()

    def _pool_take(self):
        """A kept connection to the first server that would be asked, or None. Nothing is
        marked or probed here: link() does that when there is none."""
        order = [h for h in self.hosts if h]
        if self.last_good in order:
            order.remove(self.last_good)
            order.insert(0, self.last_good)
        t = time.time()
        with self.DEAD_LOCK:
            live = [h for h in order if self.DEAD.get(h.lower(), 0) <= t]
        if not live:
            return None
        self._pool_sweep()
        key = self._pool_key(live[0])
        m = time.monotonic()
        while True:
            with self.POOL_LOCK:
                got = self.POOL.get(key)
                one = got.pop() if got else None
                if got is not None and not got:
                    self.POOL.pop(key, None)
            if one is None:
                return None
            link, put_at, born = one
            if m - put_at <= self.POOL_IDLE_S and m - born <= self.POOL_AGE_S and \
                    self._link_fresh(link):
                link.otp_host = live[0]
                link.otp_pooled = born
                return link
            link.close()

    def _pool_give(self, link):
        """Kept for the next request - only whole and clean."""
        host = getattr(link, 'otp_host', None)
        if not host or getattr(link, 'sock', None) is None or link.buffer:
            link.close()
            return
        try:
            link.sock.settimeout(link.timeout)
        except (OSError, ValueError):
            link.close()
            return
        link._deadline = 0
        link.__dict__.pop('PAGES_MOST', None)       # a search's own page cap, not the next one's
        m = time.monotonic()
        born = getattr(link, 'otp_pooled', None) or m
        if m - born > self.POOL_AGE_S:
            link.close()
            return
        key = self._pool_key(host)
        with self.POOL_LOCK:
            got = self.POOL.setdefault(key, [])
            if len(got) < self.POOL_MOST:
                got.append((link, m, born))
                return
        link.close()

    def _pool_drop(self, host):
        """Every kept connection to `host` closed - it failed or was found closed."""
        h, p = self._hostport(host)
        gone = []
        with self.POOL_LOCK:
            for key in list(self.POOL):
                if key[0] == h.lower() and key[1] == p:
                    gone += self.POOL.pop(key)
        for one in gone:
            one[0].close()

    def _up(self, host):
        with self.DEAD_LOCK:
            self.DEAD.pop(str(host).lower(), None)

    def link(self, bind=True):
        """A conversation with the first server that answers, signed in as the
        reading account. LdapUnreachable where none of them can be."""
        tried = []
        order = self._order()
        if not order:
            tried.append('every server failed within the last %d s' % self.DEAD_S)
        refused = None
        for host in order:
            h, p = self._hostport(host)
            one = Ldap(h, p, self.tls, self.ca, self.verify, self.timeout, self.weak)
            try:
                one.open()
                if bind and self.bind_dn:
                    try:
                        one.bind(self.bind_dn, self.bind_pw)
                    except LdapUnreachable:
                        raise
                    except LdapError as e:
                        if e.code in LDAP_TRY_ANOTHER or e.code is None:
                            # Busy, unavailable, an answer that does not read
                            # (1.0.59): that server's trouble - the next one.
                            raise
                        one.close()
                        # The reading account refused - an answer of the
                        # server itself - is the same on every server: no
                        # point going round them all.
                        refused = LdapUnreachable('the account this reads the directory with '
                                                  '(%s) was refused by %s: %s'
                                                  % (self.bind_dn, h, e), e.code, e.detail)
                        refused.refused = True      # the directory's answer, everywhere the same
                        break
                self.last_good = host
                self._up(host)
                one.otp_host = host
                return one
            except (LdapError, OSError, ValueError) as e:
                # Unreachable, timed out, the line dropped, StartTLS hung
                # (1.0.57): the next server is asked - a server that takes
                # the connection and then says nothing no longer stops
                # every sign-in.
                one.close()
                self._down(host)
                tried.append('%s: %s' % (h, e))
                if host == self.last_good:
                    self.last_good = None
        if refused is not None:
            raise refused
        raise LdapUnreachable('no server of %s could be reached (%s)'
                              % (self.name, '; '.join(tried) or 'none is set'))

    def asked(self, do):
        """do(link) on the first server that answers - and on the next when
        the search itself is not answered (1.0.149): a server that took the
        connection and the reading account's bind but then left its searches
        unanswered was never passed over, the other server never asked, and
        every RADIUS worker waited on it in turn."""
        with self.held():
            return self._asked(do)

    def _asked(self, do):
        last = None
        tries = max(1, len(self.hosts))
        stale = 0
        while tries > 0:
            # A kept connection first (1.0.265), a new one where there is none.
            link = self._pool_take() if stale < 2 else None
            pooled = link is not None
            if link is None:
                link = self.link()
            host = getattr(link, 'otp_host', None)
            done = False
            try:
                got = do(link)
                done = True
                return got
            except (LdapError, OSError) as e:
                if isinstance(e, LdapError) and not (isinstance(e, LdapUnreachable) or
                                                     e.code in LDAP_TRY_ANOTHER):
                    raise
                # One that did not answer in time is a server hung, not a connection gone stale
                # (1.0.270): asked again at once, the same server was waited on twice.
                hung = isinstance(e, LdapUnreachable) and ('within' in str(e))
                if pooled and isinstance(e, (LdapUnreachable, OSError)) and not hung:
                    # Closed by the server while it was kept: asked again on a new one, the
                    # server not marked down for it.
                    stale += 1
                    if host:
                        self._pool_drop(host)
                    continue
                last = e
                if host:
                    self._down(host)
                    if self.last_good == host:
                        self.last_good = None
            finally:
                if done:
                    self._pool_give(link)
                else:
                    link.close()
            tries -= 1
        raise last if isinstance(last, LdapUnreachable) else LdapUnreachable(str(last))

    def find_user(self, name, how='upn'):
        """The entry of one account, or None. `how` is upn (the whole
        name@realm against userPrincipalName), sam (the part before the @
        against sAMAccountName) or mail."""
        key = ('u', how, str(name).lower())
        with self.lock:
            got = self.cache.get(key)
            # An account's own entry - disabled, expired, locked - kept 15 s,
            # not a minute (1.0.136): a realm of the code alone relies on it.
            if got and time.time() - got[0] < self.USER_CACHE_S:
                return got[1]
        said = str(name or '').strip()
        if how == 'sam':
            said = said.split('@', 1)[0].split('\\')[-1]
            want = ldap_equal(self.row.get('user_attr') or 'sAMAccountName', said)
        elif how == 'mail':
            # By the attributes the address is read from (1.0.229): "mail" unless changed.
            ors = [ldap_equal(x, ('smtp:' + said) if x.lower() == 'proxyaddresses' else said)
                   for x in self.mail_attrs]
            want = ors[0] if len(ors) == 1 else ldap_or(*ors)
        else:
            want = ldap_equal('userPrincipalName', said)
        flt = ldap_and(ldap_equal('objectClass', 'user'), want)
        # Three, not two (1.0.101): a computer's account among them is
        # dropped below, and must not hide a second person of the name.
        rows = self.asked(lambda link: link.search(self.base, flt, self.user_attrs, scope=2,
                                                   limit=3))
        entry = None
        # A computer's account is not a person's (1.0.101): objectClass=user
        # takes them in on AD, and anybody in the domain may make up to ten
        # with a password of their own choosing - which then outlive them.
        rows = [r for r in rows if not computer_account(r)]
        if rows:
            r = rows[0]
            a = {k.lower(): v for k, v in r['attrs'].items()}
            first = lambda k: (a.get(k.lower()) or [''])[0]
            uac = 0
            try:
                uac = int(first('userAccountControl') or 0)
            except ValueError:
                pass
            try:
                uacc = int(first('msDS-User-Account-Control-Computed') or 0)
            except ValueError:
                uacc = 0
            entry = {'dn': r['dn'], 'sam': first('sAMAccountName'),
                     'upn': first('userPrincipalName'), 'display': first('displayName'),
                     'mail': entry_mail(a, self.mail_attrs), 'uac': uac,
                     'disabled': bool(uac & AD_UAC_DISABLED),
                     'expires': ad_time(first('accountExpires')),
                     'locked': bool(uacc & AD_UACC_LOCKED),
                     'pw_expired': bool(uacc & AD_UACC_PW_EXPIRED),
                     # An AD account (it has a sAMAccountName) whose state
                     # could not be read: not taken as "in use" (1.0.101).
                     'uac_unread': bool(first('sAMAccountName')) and not first('userAccountControl'),
                     # Ranged too (memberOf;range=0-1499, 1.0.59).
                     'member_of': [g for k, v in a.items()
                                   if k == 'memberof' or k.startswith('memberof;range=')
                                   for g in (v or [])],
                     'department': first('department'), 'title': first('title'),
                     # For a code by SMS (1.0.76): what the enrolment page offers - read
                     # where the directory's card says (1.0.229).
                     'mobile': entry_first(a, self.mobile_attrs),
                     'phone': first('telephoneNumber'),
                     'pw_set': ad_time(first('pwdLastSet')),
                     # The account's SID (1.0.275): what a certificate of AD CS names since KB5014754.
                     'sid': sid_text(bytes.fromhex(first('objectSid'))) if re.match(
                         r'^[0-9a-f]{16,136}\Z', first('objectSid') or '') else '',
                     'many': len(rows) > 1}
        self._cache_put(key, entry)
        return entry

    CACHE_MOST = 5000

    def _cache_put(self, key, value):
        """Kept, the oldest let go past CACHE_MOST (1.0.265) - not the whole cache cleared at
        once, every person's next sign-in then asking the directory again together."""
        with self.lock:
            self.cache.pop(key, None)       # to the end: the order is the order written
            self.cache[key] = (time.time(), value)
            while len(self.cache) > self.CACHE_MOST:
                del self.cache[next(iter(self.cache))]

    def groups_of(self, entry, nested=True):
        """[(dn, cn)] of every group the account is in - with the groups
        inside groups where `nested`, which on Active Directory is one search
        with the in-chain matching rule rather than a walk of the tree."""
        if not entry:
            return []
        if not nested:
            return [(g, cn_of(g)) for g in entry.get('member_of') or []]
        key = ('g', entry['dn'].lower())
        with self.lock:
            got = self.cache.get(key)
            if got and time.time() - got[0] < self.CACHE_S:
                return got[1]
        def do(link):
            link.PAGES_MOST = 20        # a sign-in's groups, not a census (1.0.59)
            # From the root of the domain (1.0.153), as group_dns looks: a base
            # for the people (OU=Users,...) left out every group kept beside
            # it (OU=Groups,...), and nobody was in any group.
            return link.search(self.domain_root(), ldap_and(ldap_equal('objectClass', 'group'),
                                                   ldap_in_chain('member', entry['dn'])),
                               ('cn',), scope=2, limit=5000, paged=True)
        rows = self.asked(do)
        out = [(r['dn'], (r['attrs'].get('cn') or [cn_of(r['dn'])])[0]) for r in rows]
        self._cache_put(key, out)                 # as find_user keeps it (1.0.209, 1.0.265)
        return out

    def domain_root(self):
        """DC=corpnet,DC=loc out of the base the people are looked for under."""
        dcs = [p for p in re.split(r'(?<!\\),', str(self.base or '')) if
               p.strip().lower().startswith('dc=')]
        return ','.join(p.strip() for p in dcs) or self.base

    def group_dns(self, name):
        """The DN of the one group a name given without its place stands for
        (1.0.101), as a set of 0 or 1 lower-case DNs. Matched by its name
        alone, any group anywhere under the base called alike - one a
        helpdesk or an OU's admin could make - passed as the real one, the
        administrators' group too. So: the group whose sAMAccountName it is
        (one in a domain, never two); where nothing has one, the group
        whose cn it is - and if more than one is, none of them."""
        said = str(name or '').strip()
        key = ('gn', said.lower())
        with self.lock:
            got = self.cache.get(key)
            if got and time.time() - got[0] < self.CACHE_S:
                return got[1]
        # From the root of the domain, not the base the accounts are looked
        # for under: groups often live elsewhere (OU=Groups beside OU=Users).
        where = self.domain_root()
        def do(link):
            link.PAGES_MOST = 5
            return link.search(where, ldap_and(
                ldap_equal('objectClass', 'group'),
                ldap_or(ldap_equal('sAMAccountName', said), ldap_equal('cn', said))),
                ('cn', 'sAMAccountName'), scope=2, limit=50, paged=True)
        rows = self.asked(do)

        def first(r, a):
            for k, v in r['attrs'].items():
                if k.lower() == a and v:
                    return str(v[0])
            return ''
        by_sam = [r['dn'] for r in rows if first(r, 'samaccountname').lower() == said.lower()]
        by_cn = [r['dn'] for r in rows if (first(r, 'cn') or cn_of(r['dn'])).lower() == said.lower()]
        pick = by_sam if by_sam else by_cn
        out = {pick[0].lower()} if len(pick) == 1 else set()
        if len(pick) > 1:
            log_sparing('group-many-' + said.lower(), 'the group %s named without its place '
                        'answers to %d groups in %s (%s): none of them is taken - give it as '
                        'its full DN' % (said, len(pick), self.name, '; '.join(pick[:4])), 'warn')
        self._cache_put(key, out)
        return out

    def password_ok(self, entry, password):
        """True, or LdapError with the directory's reason in words."""
        if not str(password or ''):
            raise LdapNotAsked('a password is needed')
        if not str((entry or {}).get('dn') or '').strip():
            # A bind with no name and a password is an anonymous one on many
            # servers (1.0.101): never asked.
            raise LdapNotAsked('no account to check the password of')
        if any(ord(c) < 32 or ord(c) == 127 for c in str(password)):
            # Cut at a NUL somewhere on the way, a password is empty - and an
            # empty one binds anonymously (1.0.101).
            raise LdapNotAsked('the password holds a control character')
        with self.held():
            return self._password_ok(entry, password)

    def _password_ok(self, entry, password):
        tried = []
        order = self._order()
        if not order:
            tried.append('every server failed within the last %d s' % self.DEAD_S)
        for host in order:
            h, p = self._hostport(host)
            one = Ldap(h, p, self.tls, self.ca, self.verify, self.timeout, self.weak)
            try:
                one.open()
            except (LdapError, OSError) as e:
                self._down(host)
                tried.append(str(e))
                continue
            try:
                one.bind(entry['dn'], password)
                self._up(host)
                return True
            except LdapUnreachable as e:
                # The line dropped mid-bind: the next server is asked, the
                # password is not called wrong (1.0.44).
                self._down(host)
                tried.append(str(e))
                continue
            except LdapError as e:
                # Busy, unavailable, or an answer that does not read (1.0.59):
                # not the directory's word on the password - the next one.
                # Signing or encryption demanded, an operations error, an answer that is not the
                # server's word on anything (1.0.270): not a wrong password either - counted as one,
                # a correct password used up the person's tries.
                if e.code in LDAP_TRY_ANOTHER or e.code is None or e.code in LDAP_NOT_THE_PASSWORD:
                    tried.append(str(e))
                    continue
                raise
            finally:
                one.close()
        raise LdapUnreachable('no server of %s could be reached (%s)'
                              % (self.name, '; '.join(tried)))

    # ---- the domain's policy of passwords and lockouts (1.0.232) ----------------------------
    POLICY_ATTRS = ('name', 'lockoutThreshold', 'lockoutDuration', 'lockOutObservationWindow',
                    'minPwdLength', 'pwdHistoryLength', 'maxPwdAge', 'minPwdAge', 'pwdProperties')
    PSO_ATTRS = ('name', 'cn', 'msDS-PasswordSettingsPrecedence', 'msDS-LockoutThreshold',
                 'msDS-LockoutObservationWindow', 'msDS-LockoutDuration', 'msDS-MinimumPasswordLength',
                 'msDS-PasswordComplexityEnabled', 'msDS-PasswordHistoryLength',
                 'msDS-MaximumPasswordAge', 'msDS-MinimumPasswordAge',
                 'msDS-PasswordReversibleEncryptionEnabled', 'msDS-PSOAppliesTo')

    def domain_dn(self):
        dcs = [p.strip() for p in re.split(r'(?<!\\),', self.base or '') if p.strip().lower().startswith('dc=')]
        return ','.join(dcs)

    def policy(self):
        """How the domain locks accounts and what it asks of passwords, as its root object and
        the fine-grained policies (where this account may read them) say, with a cap of wrong
        passwords to recommend for these pages."""
        t = time.time()
        dom = self.domain_dn()
        if not dom:
            def root(link):
                return link.search('', ldap_present('objectClass'), ('defaultNamingContext',), scope=0, limit=1)
            got = self.asked(root)
            a = {k.lower(): v for k, v in (got[0]['attrs'] if got else {}).items()}
            dom = (a.get('defaultnamingcontext') or [''])[0]
        if not dom:
            raise LdapError('the domain is not known: the base names no DC=')
        rows = self.asked(lambda link: link.search(dom, ldap_present('objectClass'), self.POLICY_ATTRS,
                                                   scope=0, limit=1))
        if not rows:
            raise LdapError('the domain %s did not answer for its own object' % dom)
        a = {k.lower(): v for k, v in rows[0]['attrs'].items()}
        one = lambda k: (a.get(k.lower()) or [None])[0]
        props = _ad_int(one('pwdProperties')) or 0
        out = {'domain': dom, 'name': one('name') or dom, 'directory': self.name,
               'lockout': {'threshold': _ad_int(one('lockoutThreshold')) or 0,
                           'window_s': _ad_span(one('lockOutObservationWindow')),
                           'duration_s': _ad_span(one('lockoutDuration'), zero_is='manual')},
               'password': {'min_length': _ad_int(one('minPwdLength')) or 0,
                            'history': _ad_int(one('pwdHistoryLength')) or 0,
                            'max_age_s': _ad_span(one('maxPwdAge'), zero_is='never'),
                            'min_age_s': _ad_span(one('minPwdAge'), zero_is=0),
                            'complex': bool(props & 1), 'reversible': bool(props & 16),
                            'admin_lockout': bool(props & 8)},
               'psos': [], 'psos_said': ''}
        try:
            box = 'CN=Password Settings Container,CN=System,' + dom
            got = self.asked(lambda link: link.search(box, ldap_equal('objectClass', 'msDS-PasswordSettings'),
                                                      self.PSO_ATTRS, scope=1, limit=200))
            for r in got:
                p = {k.lower(): v for k, v in r['attrs'].items()}
                pv = lambda k: (p.get(k.lower()) or [None])[0]
                out['psos'].append({
                    'name': pv('name') or pv('cn') or r['dn'].split(',')[0][3:],
                    'precedence': _ad_int(pv('msDS-PasswordSettingsPrecedence')),
                    'threshold': _ad_int(pv('msDS-LockoutThreshold')),
                    'window_s': _ad_span(pv('msDS-LockoutObservationWindow')),
                    'duration_s': _ad_span(pv('msDS-LockoutDuration'), zero_is='manual'),
                    'min_length': _ad_int(pv('msDS-MinimumPasswordLength')),
                    'complex': str(pv('msDS-PasswordComplexityEnabled') or '').upper() == 'TRUE',
                    'history': _ad_int(pv('msDS-PasswordHistoryLength')),
                    'max_age_s': _ad_span(pv('msDS-MaximumPasswordAge'), zero_is='never'),
                    'reversible': str(pv('msDS-PasswordReversibleEncryptionEnabled') or '').upper() == 'TRUE',
                    'applies': [cn_of(x) or x for x in (p.get('msds-psoappliesto') or [])][:20]})
            out['psos'].sort(key=lambda x: (x['precedence'] is None, x['precedence'] or 0))
            if not got:
                out['psos_said'] = 'none that this account may read - the account otp reads with ' \
                                   'usually may not see them; the domain\'s own policy is used'
        except LdapUnreachable:
            raise
        except LdapError as e:
            out['psos_said'] = 'not readable with the account otp reads with (%s)' % str(e)[:120]
        out['recommend'] = policy_recommend(out)
        out['took_ms'] = int((time.time() - t) * 1000)
        out['at'] = time.time()
        return out

    def find_users(self, like, limit=25):
        """People whose name, account, principal name or mail holds what is
        typed - for the boxes that offer a person as one types (1.0.19)."""
        like = str(like or '').strip()
        if len(like) < 2:
            return []
        attr = self.row.get('user_attr') or 'sAMAccountName'
        want = ldap_and(ldap_equal('objectClass', 'user'),
                        ldap_or(ldap_contains(attr, like), ldap_contains('userPrincipalName', like),
                                ldap_contains('displayName', like), ldap_contains('mail', like)))
        link = self.link()
        try:
            rows = link.search(self.base, want, tuple(dict.fromkeys(
                ('sAMAccountName', 'userPrincipalName', 'displayName', 'userAccountControl', attr)
                + self.mail_attrs + self.mobile_attrs)), scope=2, limit=limit + 10)
        finally:
            link.close()
        out = []
        for r in rows:
            a = {k.lower(): v for k, v in r['attrs'].items()}
            first = lambda k: (a.get(k.lower()) or [''])[0]
            if str(first('sAMAccountName')).endswith('$'):
                continue                         # a computer, not a person
            try:
                uac = int(first('userAccountControl') or 0)
            except ValueError:
                uac = 0
            out.append({'dn': r['dn'], 'sam': first(attr) or first('sAMAccountName'),
                        'upn': first('userPrincipalName'), 'display': first('displayName'),
                        'mail': entry_mail(a, self.mail_attrs),
                        'disabled': bool(uac & AD_UAC_DISABLED),
                        'mobile': entry_first(a, self.mobile_attrs)})
        low = like.lower()
        out.sort(key=lambda u: (not (u['sam'] or '').lower().startswith(low),
                                not (u['display'] or '').lower().startswith(low),
                                (u['display'] or u['sam'] or '').lower()))
        return out[:limit]

    def find_groups(self, like='', limit=300):
        """Group names for a picker."""
        want = ldap_equal('objectClass', 'group')
        if like.strip():
            want = ldap_and(want, ldap_contains('cn', like.strip()))
        link = self.link()
        try:
            rows = link.search(self.base, want, ('cn', 'description'), scope=2,
                               limit=limit, paged=True)
        finally:
            link.close()
        out = [{'dn': r['dn'], 'cn': (r['attrs'].get('cn') or [cn_of(r['dn'])])[0],
                'description': (r['attrs'].get('description') or [''])[0]} for r in rows]
        return sorted(out, key=lambda g: g['cn'].lower())

    def check(self):
        """Every server, step by step, the way isemon's directory check reads."""
        out = []
        began = time.time()
        for host in self.hosts:
            h, p = self._hostport(host)
            steps = []
            one = Ldap(h, p, self.tls, self.ca, self.verify, self.timeout, self.weak)
            t = time.time()
            try:
                one.open()
                steps.append({'what': 'reached %s:%d%s' % (h, p, {
                    'ldaps': ' over TLS', 'starttls': ' and started TLS'}.get(self.tls, '')),
                    'ok': True, 'said': '%d ms' % int((time.time() - t) * 1000)})
            except (LdapError, OSError) as e:
                steps.append({'what': 'reach the server %s:%d' % (h, p), 'ok': False, 'said': str(e)})
                out.append({'host': h, 'port': p, 'steps': steps, 'ok': False})
                continue
            try:
                if self.bind_dn:
                    one.bind(self.bind_dn, self.bind_pw)
                    steps.append({'what': 'signed in as %s' % self.bind_dn, 'ok': True,
                                  'said': ''})
                rows = one.search(self.base, ldap_present('objectClass'), ('objectClass',),
                                  scope=0, limit=1)
                steps.append({'what': 'read the base %s' % self.base, 'ok': bool(rows),
                              'said': '' if rows else 'nothing is there - is the base right?'})
                n = len(one.search(self.base, ldap_equal('objectClass', 'group'), ('cn',),
                                   scope=2, limit=5000, paged=True))
                steps.append({'what': 'counted the groups', 'ok': True,
                              'said': '%d group(s) under the base' % n})
                out.append({'host': h, 'port': p, 'steps': steps, 'ok': bool(rows)})
            except LdapError as e:
                steps.append({'what': 'the next step', 'ok': False, 'said': str(e),
                              'detail': e.detail})
                out.append({'host': h, 'port': p, 'steps': steps, 'ok': False})
            finally:
                one.close()
        return {'name': self.name, 'servers': out, 'ok': bool(out) and all(s['ok'] for s in out),
                'took_ms': int((time.time() - began) * 1000), 'tls': self.tls,
                'verify': self.verify, 'weak': self.weak}


def lockout_minutes(n):
    """How long a token is locked after its n-th wrong code in a row, or 0.

    Locked at every `lockout_after` wrong codes - 10, 20, 30... - and each
    time twice as long as the time before, up to a day (1.0.101). The count
    is no longer set back to 0 when the lock is set (as 1.0.94 did): that
    gave a patient guesser 10 more codes every quarter of an hour, for ever
    - some 870 a day against a realm that asks for the code alone. It goes
    back to 0 only when a right code is given or an administrator unlocks
    the token; the owner's first typo after a lock does not lock it again.
    """
    after = split_limit('lockout_after')
    if not after or n < after or n % after:
        return 0
    base = max(1, int(CONFIG.get('lockout_min') or 15))
    rounds = n // after - 1
    return int(min(base * (2 ** min(rounds, 16)), max(base, 24 * 60)))


def lockout_said(store, name, n, mins):
    """A lock written to the log and, so somebody sees it, to the events."""
    log('the token of %s is locked out for %d min after %d wrong codes in a row'
        % (name, mins, n), 'warn')
    try:
        store.add_event('tokens', 'the token of %s is locked out for %d min after %d wrong '
                        'codes in a row - somebody may be guessing its codes' % (name, mins, n),
                        'warn', who='otp')
    except Exception:                                   # noqa: BLE001
        pass


SCRATCH_GUARD_MOST = 20          # a day's refused tries from one place (1.0.101, 1.0.149)
SCRATCH_GUARD_ALL = 100          # ... and from everywhere together (1.0.149)
SCRATCH_GUARD_S = 86400
# One place's count, in this node's memory (1.0.149): a stranger who knew only
# a name sent 20 wrong passwords and the person's recovery codes were not
# taken for a day - just when the phone was lost. Now one place rests alone;
# all of them together only at five times as many.
SCRATCH_PLACES = {}
SCRATCH_PLACES_LOCK = threading.Lock()
REQUEST_PLACE = threading.local()


def scratch_guard_times(store, name):
    # Every node's row (1.0.146), see node_key.
    return [x for x in node_key_times(store, 'scratchguard', name)
            if time.time() - x < SCRATCH_GUARD_S]


def scratch_guard_cleared(store, name):
    """When the recovery codes of NAME were last given back (Unlock), on any
    node and by any way - the pages, the command line (1.0.187): what each
    daemon keeps of the places they were tried from is older than that."""
    try:
        return float(store.get_meta('scratchclear:' + norm_name(name)) or 0)
    except (TypeError, ValueError):
        return 0.0


def scratch_guard_give_back(store, name):
    node_key_drop(store, 'scratchguard', name)
    store.set_meta('scratchclear:' + norm_name(name), repr(time.time()))
    scratch_guard_clear(name)


def _scratch_place(name, place, add=False, since=0.0):
    k = (norm_name(name), str(place or '')[:64])
    t = time.time()
    with SCRATCH_PLACES_LOCK:
        if len(SCRATCH_PLACES) > 20000:
            SCRATCH_PLACES.clear()
        got = [x for x in SCRATCH_PLACES.get(k, []) if t - x < SCRATCH_GUARD_S and x > since]
        if add:
            got = (got + [t])[-SCRATCH_GUARD_MOST * 2:]
        if got:
            SCRATCH_PLACES[k] = got
        else:
            SCRATCH_PLACES.pop(k, None)
        return len(got)


def scratch_guard_clear(name):
    n = norm_name(name)
    with SCRATCH_PLACES_LOCK:
        for k in [k for k in SCRATCH_PLACES if k[0] == n]:
            del SCRATCH_PLACES[k]


def scratch_guard_note(store, name, place=''):
    """One request whose password and recovery code could not both be right
    (1.0.101) - see the RADIUS side. Written only over what was read."""
    # No place known (no Calling-Station-Id): every request one "place", and its
    # limit everybody's - a stranger with the name alone stopped its owner's
    # recovery codes for a day (1.0.205). Then only the day's limit counts.
    here = _scratch_place(name, place, add=True, since=scratch_guard_cleared(store, name)) \
        if place else 0
    before = len(scratch_guard_times(store, name))
    node_key_add(store, 'scratchguard', name, SCRATCH_GUARD_S, SCRATCH_GUARD_ALL * 2)
    times = scratch_guard_times(store, name)
    # Said once, as the count goes past it (1.0.147): two nodes at once went
    # from 19 to 21, and "exactly 20" was never seen.
    if before < SCRATCH_GUARD_ALL <= len(times) or here == SCRATCH_GUARD_MOST:
        store.add_event('tokens', 'the recovery codes of %s are not taken for a day%s: %d '
                        'requests in a day had a wrong password or a wrong recovery code - '
                        'somebody may be guessing them (Unlock it on the token gives them back)'
                        % (norm_name(name), '' if len(times) >= SCRATCH_GUARD_ALL else
                           ' from %s' % (place or 'one place'),
                           len(times) if len(times) >= SCRATCH_GUARD_ALL else here),
                        'warn', who='otp')


def scratch_guarded(store, name, place=None):
    if place is None:
        place = getattr(REQUEST_PLACE, 'v', '') or ''
    return (bool(place) and _scratch_place(name, place, since=scratch_guard_cleared(store, name))
            >= SCRATCH_GUARD_MOST) or len(scratch_guard_times(store, name)) >= SCRATCH_GUARD_ALL


def entry_unusable(entry, locked=True):
    """Why the directory's account may not sign in now, or None (1.0.101):
    switched off, run out, locked out, its password expired - or, on AD,
    its state not readable at all, which is not taken as "in use"."""
    if not entry:
        return 'there is no such account'
    if entry.get('disabled'):
        return 'it is disabled in the directory'
    if entry.get('uac_unread'):
        return 'the directory does not say whether it is in use (userAccountControl cannot be read)'
    if entry.get('expires') and entry['expires'] < time.time():
        return 'it expired %s' % stamp(entry['expires'])
    if locked and entry.get('locked'):
        return 'it is locked out in the directory'
    if locked and entry.get('pw_expired'):
        return 'its password has expired in the directory'
    return None


def computer_account(r):
    """Whether a search result is a computer's account (1.0.101)."""
    a = {k.lower(): v for k, v in odict(r.get('attrs')).items()}
    if any(str(x).lower() == 'computer' for x in a.get('objectclass') or []):
        return True
    return str((a.get('samaccountname') or [''])[0]).endswith('$')


def dn_norm(dn):
    """A DN as it is compared (1.0.205): lower case, no spaces around the
    commas and equals signs that part it - "CN=VPN Users, OU=Groups" copied
    from a page matched nothing AD said."""
    return re.sub(r'(?<!\\)\s*([,=])\s*', r'\1', str(dn or '').strip().lower())


def group_matches(wanted, have, ad=None):
    """Whether any group in `have` ([(dn, cn)]) is one of `wanted` (names or
    DNs). Returns the wanted entry that matched first, in `wanted`'s order.

    A name without its place is the one group `ad` says it is (1.0.101), by
    its DN - never any group of that cn wherever it is. Without `ad` to ask,
    a name alone matches nothing."""
    by_dn = {dn_norm(dn) for dn, _ in have}
    by_cn = {str(cn).lower() for _, cn in have}
    for one in wanted:
        said = str(one.get('group') if isinstance(one, dict) else one).strip()
        if not said:
            continue
        if '=' in said and ',' in said:
            if dn_norm(said) in by_dn:
                return one
        elif said.lower() in by_cn and ad is not None:
            try:
                dns = {dn_norm(x) for x in ad.group_dns(said)}
            except LdapUnreachable:
                # The directory not answering is not "not a member" (1.0.205):
                # said as it is, and never counted as somebody guessing.
                raise
            except LdapError as e:
                # Not known which group it is: no match, never a guess.
                log_sparing('group-dns', 'the group %s could not be looked up in %s: %s'
                            % (said, ad.name, e), 'warn')
                dns = set()
            if dns & by_dn:
                return one
    return None


# ---------------------------------------------------------------------------
# The tokens themselves
# ---------------------------------------------------------------------------
# The words a check of a code ends in are totpcgi's own, letter for letter:
# isemon reads them out of the token log and turns them into its own words
# (`OTP_SAYS`), and anything that already watches a token server knows them.
SAY_OK = 'Valid token used'
SAY_OK_DRIFT = 'Valid token within window size used'
SAY_SCRATCH = 'Scratch-token used'
SAY_BAD = 'Not a valid token'
SAY_REUSED = 'Token has already been used once'
SAY_RATE = 'Rate-limit reached, please try again later'
SAY_LOCKED = 'Locked out after too many wrong codes, please try again later'
SAY_NONE = 'No token is enrolled for this account'
SAY_OFF = 'This token is switched off'
SAY_PENDING = 'This token has not been confirmed yet'
SAY_LOST = 'The key of this token cannot be opened on this machine'


def seal_codes(codes, bind=None):
    """Recovery codes kept so that an administrator can show them again -
    each with when it was used, if it was: sealed with the key of the tokens,
    beside their hashes, which are what a code is checked against."""
    if not codes:
        return ''
    out = []
    for c in codes:
        out.append(dict(c) if isinstance(c, dict) else {'c': str(c), 'used': None})
    return seal_secret(json.dumps(out), bind)


def open_codes(value, bind=None):
    """The codes `seal_codes` kept, as [{c, used}] - also the plain JSON list
    an older version left in pending_scratch. None when none are kept."""
    if not value:
        return None
    text = unseal_secret(value, bind)
    if text is None and str(value).lstrip().startswith('[') and not dbguard_on():
        # A plain list of an older version - not with the guard on (1.0.248): written into a
        # row by somebody without the key, its codes were made the token's recovery codes.
        text = value
    try:
        got = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(got, list):
        return None
    return [dict(x) if isinstance(x, dict) else {'c': str(x), 'used': None} for x in got]


# The checks of a code a RADIUS worker makes, kept until its answer went (1.0.186).
OTP_LOG_LATER = threading.local()


class Tokens(object):
    """Making, checking and looking after tokens."""

    def __init__(self, store):
        self.store = store
        # A fixed row of locks, a name always to the same one: two checks of
        # one token wait for each other, and the row cannot grow however
        # many names are tried.
        self.locks = [threading.RLock() for _ in range(1024)]  # re-entered (1.0.59)
        self.on_check = None                       # (name, ok, said, how, src, rid)

    def lock_of(self, name):
        return self.locks[zlib.crc32(str(name).encode('utf-8')) % len(self.locks)]

    # ---- made ------------------------------------------------------------------
    def label_for(self, name):
        tpl = str(CONFIG.get('totp_label') or '{user}')
        return tpl.replace('{user}', name).replace('{name}', name.split('@', 1)[0])[:190]

    def fresh(self):
        """A new key and new recovery codes, not yet anybody's."""
        secret = b32_new(20)
        codes = scratch_new(int(CONFIG.get('scratch_count') or 0),
                            int(CONFIG.get('scratch_digits') or 8))
        return secret, codes

    def picture(self, name, secret, digits=None, period=None, algorithm=None, issuer=None):
        """What the person scans, in every shape a page wants it."""
        digits = int(digits or CONFIG.get('totp_digits') or 6)
        period = int(period or CONFIG.get('totp_period') or 30)
        algorithm = str(algorithm or CONFIG.get('totp_algorithm') or 'SHA1')
        issuer = issuer if issuer is not None else str(CONFIG.get('totp_issuer') or '')
        uri = otpauth_uri(secret, self.label_for(name), issuer, digits, period, algorithm)
        return {'uri': uri, 'qr': qr_data_uri(uri), 'secret': secret,
                'secret_spaced': ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4)),
                'issuer': issuer, 'label': self.label_for(name), 'digits': digits,
                'period': period, 'algorithm': algorithm}

    def enroll(self, name, by, pending=False, secret=None, codes=None, display='', note=None):
        """A token for `name`, replacing any there was. `pending` makes it wait
        for a code before it is used. Returns the picture and the codes."""
        # One at a time per name, with confirm (1.0.59): a confirm landing on
        # a key written meanwhile made an unproven key active.
        with self.lock_of(norm_name(name)):
            return self._enroll(name, by, pending, secret, codes, display, note)

    def _enroll(self, name, by, pending=False, secret=None, codes=None, display='', note=None,
                extra=None):
        name = norm_name(name)
        if not name:
            raise ValueError('a token needs a name')
        # 180 at most (1.0.44): staged:NAME and mailed:NAME have to fit a key.
        # No control character either (1.0.103): a NUL is stored as U+FFFD,
        # and the key sealed to the name as sent never opened again.
        if not re.match(r'^[^\s,;=\x00-\x1f\x7f]{1,180}\Z', name):
            raise ValueError('a name has no spaces, commas, semicolons or = in it, and '
                             'is 180 characters at most')
        if secret is None:
            secret, codes = self.fresh()
        codes = list(codes or [])
        # The picture first (1.0.103): one that cannot be made (an issuer too
        # long for a QR code) refused before the token's key was replaced -
        # the old key gone and the new one never shown.
        out = self.picture(name, secret)
        fields = {
            'secret': seal_secret(secret, token_bind(name)),
            'digits': int(CONFIG.get('totp_digits') or 6),
            'period': int(CONFIG.get('totp_period') or 30),
            'algorithm': str(CONFIG.get('totp_algorithm') or 'SHA1'),
            'state': 'pending' if pending else 'active', 'last_step': 0,
            'scratch': json.dumps([scratch_hash(name, c) for c in codes]),
            'scratch_sealed': seal_codes(codes, token_bind(name)),
            'scratch_left': len(codes), 'created': time.time(), 'created_by': str(by)[:190],
            'activated': None if pending else time.time(), 'failures': 0,
            'fail_times': '[]', 'locked_until': None,
            'issuer': str(CONFIG.get('totp_issuer') or ''),
            'label': self.label_for(name), 'pending_secret': None, 'pending_scratch': None,
            'pending_at': None, 'pending_by': None, 'last_used': None, 'last_from': '',
            'last_how': '', 'kind': '', 'dest': ''}
        if display:
            fields['display'] = str(display)[:300]
        if note is not None:
            fields['note'] = str(note)[:400]
        if extra:
            fields.update(extra)
        self.store.token_write(name, fields)
        self._staged_forget(name)
        try:                            # a new token was never switched off (1.0.61)
            self.store.drop_meta('disabled_from:' + name)
        except Exception:                               # noqa: BLE001
            pass
        out['scratch'] = codes
        out['name'] = name
        return out

    def enroll_sent(self, name, by, kind, dest, display='', note=None, lang=None,
                    mail_fmt=None):
        """A token that gets its codes sent (1.0.76): by mail or SMS to
        `dest`. No key anybody scans - one is kept all the same, never shown,
        so everything that reads a token's columns reads this one too - and
        recovery codes as any token has. In use at once: the address or the
        number was proven by the one who made it."""
        if kind not in ('mail', 'sms'):
            raise ValueError('a token that gets codes sent is mail or sms')
        dest = dest_checked(kind, dest)
        name = norm_name(name)
        with self.lock_of(name):
            out = self._enroll(name, by, pending=False, display=display, note=note,
                               extra=dict({'kind': kind, 'dest': dest,
                                           'digits': int(CONFIG.get('code_digits') or 6),
                                           'issuer': '', 'label': ''},
                                          **dict({'lang': lang} if lang in ('cs', 'en') else {},
                                                 **({'mail_fmt': mail_fmt}
                                                    if mail_fmt in ('html', 'text') else {}))))
        return {'name': name, 'kind': kind, 'dest': dest, 'scratch': out.get('scratch') or []}

    def dest_change(self, name, dest):
        """Where a mail or SMS token's codes go."""
        name = norm_name(name)
        with self.lock_of(name):
            tok = self.store.token(name)
            kind = token_kind(tok)
            if not tok or kind == 'totp':
                raise ValueError('%s has no token that gets codes sent' % name)
            dest = dest_checked(kind, dest)
            self.store.token_update(tok['id'], {'dest': dest})
        return dest

    def used_sent(self, name, how):
        """A sent code was right: written on the token as a code from the
        phone would be."""
        self.store.db.run("UPDATE tokens SET last_used = ?, failures = 0, fail_times = '[]', "
                          'last_how = ? WHERE name = ?', (time.time(), how, norm_name(name)))

    # ---- the shape of a key waiting beside an old one (1.0.32) ----------
    # A replacement is made with the settings of the day - digits, period,
    # hash - which need not be the old token's: an imported SHA-1 six-digit
    # token replaced while the settings say SHA-512 and eight digits. The
    # token's own columns describe the old key until the new one is
    # confirmed, so the new key's shape is kept beside it.
    def staged_shape(self, name):
        got = json_obj(self.store.get_meta('staged:' + norm_name(name), '')) or {}
        return {'digits': int(got.get('digits') or CONFIG.get('totp_digits') or 6),
                'period': int(got.get('period') or CONFIG.get('totp_period') or 30),
                'algorithm': str(got.get('algorithm') or CONFIG.get('totp_algorithm') or 'SHA1'),
                'issuer': str(got.get('issuer') if got.get('issuer') is not None
                              else CONFIG.get('totp_issuer') or ''),
                'fails': int(got.get('fails') or 0),
                'fail_times': got.get('fail_times') if isinstance(got.get('fail_times'), list)
                else []}

    def _staged_forget(self, name):
        try:
            self.store.drop_meta('staged:' + norm_name(name))
        except Exception:                               # noqa: BLE001
            pass

    def stage_replacement(self, name, by):
        """A new key for somebody who has a token already, kept beside the
        old one until a code from the new one proves it was scanned. The old
        one goes on working until then."""
        name = norm_name(name)
        with self.lock_of(name):
            return self._stage_replacement(name, by)

    def _stage_replacement(self, name, by):
        if not self.store.token(name):
            raise ValueError('%s has no token to replace' % name)
        secret, codes = self.fresh()
        shape = {'digits': int(CONFIG.get('totp_digits') or 6),
                 'period': int(CONFIG.get('totp_period') or 30),
                 'algorithm': str(CONFIG.get('totp_algorithm') or 'SHA1'),
                 'issuer': str(CONFIG.get('totp_issuer') or '')}
        out = self.picture(name, secret, shape['digits'], shape['period'], shape['algorithm'],
                           shape['issuer'] or None)        # first (1.0.103)
        self.store.set_meta('staged:' + name, json.dumps(shape))
        self.store.token_write(name, {
            'pending_secret': seal_secret(secret, token_bind(name)),
            'pending_scratch': seal_codes(codes, token_bind(name)), 'pending_at': time.time(),
            'pending_by': str(by)[:190]})
        out['scratch'] = codes
        out['name'] = name
        return out

    def confirm(self, name, code, how='portal', src=''):
        """A code from a token that is waiting - a new one, or a replacement
        staged beside an old one. (ok, words)."""
        name = norm_name(name)
        code = code_typed(code)     # the Czech row, full-width digits (1.0.226)
        # One at a time per name, as a check is (1.0.33).
        with self.lock_of(name):
            return self._confirm(name, code, how, src)

    def _confirm(self, name, code, how='portal', src=''):
        tok = self.store.token(name)
        if not tok:
            return False, SAY_NONE
        staged = bool(tok.get('pending_secret'))
        # Only a token that waits is confirmed: a new one, or one with a
        # replacement staged. A token an administrator switched off is not
        # brought back by its owner's code (1.0.15), and an active one with
        # nothing staged has nothing to confirm.
        if tok.get('state') == 'disabled':
            return False, SAY_OFF
        if not staged and tok.get('state') != 'pending':
            return False, 'There is nothing to confirm: this token is in use already'
        sealed = tok['pending_secret'] if staged else tok['secret']
        secret = unseal_secret(sealed or '', token_bind(name))
        if not secret:
            return False, SAY_LOST
        # A staged key is checked with its own shape, not the old token's.
        shape = self.staged_shape(name) if staged else {
            'digits': tok['digits'] or 6, 'period': tok['period'] or 30,
            'algorithm': tok['algorithm'] or 'SHA1', 'issuer': tok.get('issuer') or ''}
        # Throttled like a sign-in (1.0.33): the same pause after wrong codes,
        # so the page cannot be used to guess a waiting key's codes quickly.
        t = clock_now('locks')          # clock_locks (1.0.222)
        try:
            # A waiting replacement counts its wrong codes beside its own
            # shape (1.0.61): in the token's own they paused the token still
            # in use as well.
            fails = [float(x) for x in (shape.get('fail_times') if staged
                                        else json.loads(tok.get('fail_times') or '[]')) or []]
        except (ValueError, TypeError):
            fails = []
        tries = split_limit('rate_limit_tries')
        fails = [x for x in fails if abs(t - x) < int(CONFIG.get('rate_limit_s') or 30)]
        if fnum(tok.get('locked_until')) > t:
            self._said(name, False, SAY_LOCKED + ' (confirming a new token)', how, src, '')
            return False, SAY_LOCKED
        if tries and len(fails) >= tries:
            self._said(name, False, SAY_RATE + ' (confirming a new token)', how, src, '')
            return False, SAY_RATE
        step = totp_match(secret, code, clock_now('codes'), shape['digits'], shape['period'],
                          shape['algorithm'], self.window(tok))
        if step is None and staged:
            # A replacement's wrong codes do not lock the token still in use
            # (1.0.59) - the phone answering with the old account is the
            # usual wrong code here. They are counted against the waiting key:
            # past the lockout count it is thrown away, to be made again.
            # Counted by a conditional write (1.0.224), as a token's own wrong codes are: two
            # nodes reading the count and writing it back lost half of them.
            k = 'staged:' + name
            for _round in range(20):
                raw = self.store.get_meta(k, '') or ''
                now_shape = dict(self.staged_shape(name))
                was_fails = [float(x) for x in now_shape.get('fail_times') or []
                             if isinstance(x, (int, float))]
                now_shape['fail_times'] = [x for x in was_fails if abs(t - x) < int(
                    CONFIG.get('rate_limit_s') or 30)] + [t]
                now_shape['fails'] = int(now_shape.get('fails') or 0) + 1
                if not raw:
                    shape = now_shape
                    break
                if self.store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?',
                                     (json.dumps(now_shape), k, raw)):
                    shape = now_shape
                    break
                time.sleep(random.random() * 0.01)
            else:
                shape['fail_times'] = fails + [t]
                shape['fails'] = int(shape.get('fails') or 0) + 1
            written = bool(raw) and shape is now_shape
            after = split_limit('lockout_after')
            if after and shape['fails'] >= after:
                self.drop_staged(name)
                self._said(name, False, SAY_BAD + ' (confirming a new token - too many, '
                           'the new key is thrown away)', how, src, '')
                return False, (SAY_BAD + '. Too many wrong codes: the new key was thrown '
                               'away - the token in use goes on working; make a new one.')
            if not written:
                self.store.set_meta('staged:' + name, json.dumps(shape))
            self._said(name, False, SAY_BAD + ' (confirming a new token)', how, src, '')
            return False, SAY_BAD + '. ' + self.why_wrong(secret, code, shape)
        if step is None:
            # Counted toward the lockout as well (1.0.44), not only the short
            # pause: a waiting key could be guessed at day after day.
            n = self._failure_counted(tok['id'])
            # The same lock as a wrong code to sign in with (1.0.101).
            mins = lockout_minutes(n)
            self._fail_noted(tok['id'], t, int(CONFIG.get('rate_limit_s') or 30), mins)
            if mins:
                lockout_said(self.store, name, n, mins)
            self._said(name, False, SAY_BAD + ' (confirming a new token)', how, src, '')
            return False, SAY_BAD + '. ' + self.why_wrong(secret, code, shape)
        # last_step never goes down for the same key: its code of a step
        # already used stays used. A new key starts from its own step
        # (1.0.33): steps of another period are not comparable - a 30 s
        # token replaced by a 60 s one refused every code after.
        fields = {'state': 'active', 'activated': time.time(),
                  'last_step': int(step) if staged else max(int(step),
                                                             int(tok.get('last_step') or 0)),
                  'failures': 0, 'fail_times': '[]', 'locked_until': None}
        if staged:
            codes = [x['c'] for x in (open_codes(tok.get('pending_scratch'),
                                                 token_bind(name)) or [])]
            # A token that got codes sent becomes the app's (1.0.76).
            fields.update({'kind': '', 'dest': ''})
            fields.update({'secret': tok['pending_secret'], 'pending_secret': None,
                           'pending_scratch': None, 'pending_at': None, 'pending_by': None,
                           'scratch': json.dumps([scratch_hash(name, c) for c in codes]),
                           'scratch_sealed': seal_codes(codes, token_bind(name)),
                           'scratch_left': len(codes), 'created': time.time(),
                           'created_by': tok.get('pending_by') or how,
                           'digits': shape['digits'], 'period': shape['period'],
                           'algorithm': shape['algorithm'],
                           'label': self.label_for(name),
                           'issuer': shape['issuer'],
                           # The old key's use is not the new one's (1.0.36).
                           'last_used': None, 'last_from': '', 'last_how': ''})
        # Only onto the key that was proven (1.0.224): a new key made meanwhile on the other
        # node (the pages open on both, "start again" in one) was made the one in use - the
        # person was told "confirmed", and every code of the phone refused after.
        cols = sorted(fields)
        guard, args = ('pending_secret = ?', tok.get('pending_secret')) if staged else \
            ('secret = ?', tok.get('secret'))
        won = self.store.db.run('UPDATE tokens SET %s WHERE id = ? AND %s' % (
            ', '.join('%s = ?' % c for c in cols), guard),
            tuple(fields[c] for c in cols) + (tok['id'], args))
        if not won:
            self._said(name, False, 'The key changed meanwhile (confirming a new token)', how, src, '')
            return False, 'the key changed meanwhile - start again'
        try:
            self.store.token_counts_stale()      # pending to active: counted again (1.0.270)
        except Exception:                               # noqa: BLE001
            pass
        if staged:
            self._staged_forget(name)
        self._said(name, True, 'Token confirmed', how, src, '')
        return True, 'Token confirmed'

    @staticmethod
    def why_wrong(secret, code, tok):
        """What a wrong code most likely means, for the person typing it."""
        period = int(tok.get('period') or 30)
        far = totp_match(secret, code, clock_now('codes'), tok.get('digits') or 6, period,
                         tok.get('algorithm') or 'SHA1', 40)
        if far is not None:
            off = (far - totp_step(clock_now('codes'), period)) * period
            return ('It is this token\'s code, but from %d s %s: the clock of the phone is '
                    'wrong - set it to the network\'s time.' % (abs(off), 'ago' if off < 0
                                                                 else 'ahead'))
        return ('It is not a code of this token. If the application shows several accounts '
                'of this name, an older one is answering - type the code of the newest, or '
                'take the old one out of the application.')

    def drop_staged(self, name):
        with self.lock_of(norm_name(name)):
            self._drop_staged(name)

    def _drop_staged(self, name):
        tok = self.store.token(name)
        if not tok:
            self._staged_forget(name)
            return
        self.store.token_update(tok['id'], {'pending_secret': None, 'pending_scratch': None,
                                      'pending_at': None, 'pending_by': None})
        self._staged_forget(name)

    def new_scratch(self, name, by=''):
        name = norm_name(name)
        if not self.store.token(name):
            raise ValueError('%s has no token' % name)
        codes = scratch_new(int(CONFIG.get('scratch_count') or 0) or 5,
                            int(CONFIG.get('scratch_digits') or 8))
        row = {'scratch': json.dumps([scratch_hash(name, c) for c in codes]),
               'scratch_sealed': seal_codes(codes, token_bind(name)),
               'scratch_left': len(codes)}
        if (self.store.token(name) or {}).get('pending_secret'):
            # A new key waiting to be confirmed (1.0.207): its own codes took the
            # place of these at the confirmation, and the ones just handed out were
            # wrong from then on - the same ones for it.
            row['pending_scratch'] = seal_codes(codes, token_bind(name))
        self.store.token_write(name, row)
        return codes

    @staticmethod
    def window(tok):
        w = tok.get('window_steps')
        if w is None or int(w) < 0:
            return int(CONFIG.get('totp_window') or 0)
        return int(w)

    # ---- checked ---------------------------------------------------------------
    def check(self, name, code, how='radius', src='127.0.0.1', rid='', dry=False, quiet=False):
        """Whether `code` is right for the token of `name`. (ok, words, facts)
        - the words totpcgi would have said. `quiet`: not written down - the
        probe that finds where a password ends and its code begins."""
        name = norm_name(name)
        code = str(code or '').strip()
        with self.lock_of(name):
            ok, said, facts = self._check(name, code, dry)
        # A dry check - the administrator's test - is written down like any
        # other, marked as such; the only thing it leaves alone is the code,
        # which stays usable.
        if not quiet:
            self._said(name, ok, said, how + '-dry' if dry else how, src, rid, facts.get('off'))
        return ok, said, facts

    def _failure_counted(self, tok_id):
        """One more wrong code on the token, and which one it is - each
        wrong code its own number (1.0.101). Counted up and read back, two
        at once both read 11 and neither was the 10th: the lock at every
        tenth was skipped."""
        for _round in range(16):
            n = int(self.store.db.value('SELECT COALESCE(failures, 0) FROM tokens WHERE id = ?',
                                        (tok_id,)) or 0)
            if self.store.db.run('UPDATE tokens SET failures = ? WHERE id = ? AND '
                                 'COALESCE(failures, 0) = ?', (n + 1, tok_id, n)):
                return n + 1
        self.store.db.run('UPDATE tokens SET failures = COALESCE(failures, 0) + 1 WHERE id = ?',
                          (tok_id,))
        return int(self.store.db.value('SELECT failures FROM tokens WHERE id = ?',
                                       (tok_id,)) or 0)

    def _own_step_landed(self, tok_id, step, t):
        """Whether this request's own use of a code is in the database: its step with its
        exact time (no other request writes the same float)."""
        try:
            row = self.store.db.row('SELECT last_step, last_used FROM tokens WHERE id = ?', (tok_id,))
        except Exception:                               # noqa: BLE001
            return False
        return bool(row) and int(row.get('last_step') or 0) == int(step) and \
            abs(fnum(row.get('last_used')) - float(t)) < 1e-6

    def _fail_noted(self, tok_id, t, span, mins):
        """The time of a wrong code added to the token's recent ones, and the
        lock set - by a conditional update (1.0.101): two nodes each reading
        the list and writing it back with their own time added lost one of
        them, and a guesser sending to both nodes at once got twice the
        tries the pause allows."""
        fails = []
        for _round in range(40):
            if _round > 2:
                # Many at once (1.0.222): after 8 lost rounds the list was written as
                # this one time alone, and the pause counted fewer tries than were made.
                time.sleep(random.random() * 0.004 * min(_round, 10))
            was = self.store.db.value('SELECT fail_times FROM tokens WHERE id = ?', (tok_id,))
            try:
                fails = [float(x) for x in json.loads(was or '[]')]
            except (ValueError, TypeError):
                fails = []
            fails = [x for x in fails if abs(t - x) < span] + [t]
            # As many as the pause counts (1.0.139): rate_limit_tries goes to
            # 100, and with more than 50 the pause never came.
            keep = max(50, int(CONFIG.get('rate_limit_tries') or 0))
            sets, args = 'fail_times = ?', [json.dumps(fails[-keep:])]
            if mins:
                sets += ', locked_until = ?'
                args.append(t + 60 * mins)
            if was is None:
                hit = self.store.db.run('UPDATE tokens SET %s WHERE id = ? AND fail_times IS NULL'
                                        % sets, tuple(args) + (tok_id,))
            else:
                hit = self.store.db.run('UPDATE tokens SET %s WHERE id = ? AND fail_times = ?'
                                        % sets, tuple(args) + (tok_id, was))
            if hit:
                break
        else:
            fields = {'fail_times': json.dumps(fails[-max(50, int(CONFIG.get('rate_limit_tries') or 0)):]
                                               or [t])}
            if mins:
                fields['locked_until'] = t + 60 * mins
            self.store.token_update(tok_id, fields)

    def blocked(self, name):
        """What the token would say before any code is looked at - locked out,
        paused, switched off - or None. Asked before the directory password
        (1.0.57), so a locked token is not a free way to guess AD passwords."""
        tok = self.store.token(norm_name(name))
        if not tok:
            return None
        t = clock_now('locks')
        if tok.get('state') == 'disabled':
            return SAY_OFF
        if fnum(tok.get('locked_until')) > t:
            return SAY_LOCKED
        tries = split_limit('rate_limit_tries')
        span = int(CONFIG.get('rate_limit_s') or 30)
        try:
            fails = [float(x) for x in json.loads(tok.get('fail_times') or '[]')]
        except (ValueError, TypeError):
            fails = []
        if tries and len([x for x in fails if abs(t - x) < span]) >= tries:
            return SAY_RATE
        return None

    def _check(self, name, code, dry):
        tok = self.store.token(name)
        facts = {}
        if not tok:
            return False, SAY_NONE, facts
        if tok.get('state') == 'disabled':
            return False, SAY_OFF, facts
        if tok.get('state') == 'pending':
            return False, SAY_PENDING, facts
        t = clock_now('locks')          # pauses, lockouts (clock_locks, 1.0.222)
        tc = clock_now('codes')         # the code's step (clock_codes, 1.0.222)
        try:
            fails = [float(x) for x in json.loads(tok.get('fail_times') or '[]')]
        except (ValueError, TypeError):
            fails = []
        tries = split_limit('rate_limit_tries')
        span = int(CONFIG.get('rate_limit_s') or 30)
        fails = [x for x in fails if abs(t - x) < span]
        # A lockout after many wrong codes in a row, however slowly they
        # came (1.0.33): the short pause alone let a patient guesser try
        # thousands of codes a day.
        if fnum(tok.get('locked_until')) > t:
            return False, SAY_LOCKED, facts
        if tries and len(fails) >= tries:
            return False, SAY_RATE, facts
        secret = unseal_secret(tok.get('secret') or '', token_bind(name))
        # Only a token of the app needs its key (1.0.149): one by mail or SMS
        # put back from a backup has none, and its recovery codes were
        # refused as "cannot be opened".
        if not secret and token_kind(tok) == 'totp':
            return False, SAY_LOST, facts
        digits = int(tok.get('digits') or 6)
        # "123 456" as the phone shows it (1.0.214): taken on the pages, a wrong code
        # through RADIUS - and counted. The spaces inside go, as there.
        code = code_sep_gone(code)
        # The Czech row, full-width digits (1.0.226) - and "++++++" for 111111 too (1.0.227):
        # "+" is ASCII, so it was never read as the Czech row and a right code was counted.
        if re.fullmatch(r'[0-9]{4,12}', code_typed(code), re.ASCII):
            code = code_typed(code)
        # Digits 0-9 and nothing else: \d also takes Arabic-Indic and other
        # digits, which then broke the comparison and left the request
        # unanswered and unwritten (1.0.33).
        plain = re.fullmatch(r'[0-9]+', code, re.ASCII) is not None

        def failed(said):
            # A dry check - the administrator's test, or the probe that finds
            # where a password ends and its code begins - counts nothing
            # (1.0.33): it is not somebody trying to sign in, and it counted
            # one typo three times.
            if dry:
                return False, said, facts
            # Counted in the database itself (1.0.44): two nodes reading
            # n and both writing n+1 lost one wrong code each time.
            n = self._failure_counted(tok['id'])
            mins = lockout_minutes(n)
            self._fail_noted(tok['id'], t, span, mins)
            if mins:
                lockout_said(self.store, name, n, mins)
            return False, said, facts
        if not plain:
            return failed(SAY_BAD)

        def scratch_try():
            """A recovery code: used once. None when it is not one."""
            if scratch_guarded(self.store, name):
                return None             # resting after many guesses (1.0.101)
            kept = json_obj(tok.get('scratch'), list) or []        # a list only (1.0.250)
            key = sealing_key()
            hit, h = scratch_find(name, code, kept, key)
            if hit and hit != h and dbguard_on():
                # A code in the shape of before 1.0.14 (a hash without the key) - with the guard
                # on only if the token's sealed copy has it too (1.0.248): anybody who can write
                # the database could make such a hash of a code of theirs.
                shown_ = codes_open(tok) or []
                if not key or not any(not one.get('used') and hmac.compare_digest(
                        scratch_hash(name, one.get('c') or '', key), h) for one in shown_):
                    hit = None
            if hit:
                was = tok.get('scratch') or '[]'
                if not dry and split_scratch_refused(self.store, 'scratch', name, h):
                    # Recovery codes only with the other node asked (1.0.218, split_scratch):
                    # one used up for good is the code most worth not letting in twice.
                    # Refused before anything is written, and not counted as wrong.
                    return False, SPLIT_SAY_SCRATCH, facts
                if not dry:
                    kept.remove(hit)
                    shown = codes_open(tok)
                    if shown is not None:
                        for one in shown:
                            if not one.get('used') and hmac.compare_digest(
                                    scratch_hash(name, one['c'], key), h):
                                one['used'] = t
                        # The rest, which were kept in the old shape too if
                        # this one was, written in the new one.
                        # (Without a sealed copy the others stay as they
                        # are until each is used.)
                        if hit != h:
                            kept = [scratch_hash(name, one['c'], key) for one in shown
                                    if not one.get('used')]
                    # Only if the codes are still the ones read: a recovery
                    # code used on the other node at the same moment is not
                    # used twice. (1.0.13)
                    id_h = scratch_id_hash(tok['id'], code, key)
                    # In one transaction (1.0.214), as a code from the phone: a database
                    # dropping half way left the code used here and refused by the other node.
                    try:
                        with self.store.db.transaction():
                            won = self.store.db.run(
                                'UPDATE tokens SET scratch = ?, scratch_sealed = ?, scratch_left = ?, '
                                "last_used = ?, last_how = 'scratch', failures = 0, fail_times = '[]' "
                                'WHERE id = ? AND scratch = ?',
                                (json.dumps(kept), seal_codes(shown, token_bind(name)) if shown is not None else
                                 (tok.get('scratch_sealed') or ''), len(kept), t, tok['id'], was))
                            if not won:
                                return False, SAY_REUSED, facts
                            # And used once anywhere (1.0.101): the row above can be
                            # written back by the other node's older copy of it.
                            if not once_take(self.store, 'scratch', name, h, peer=False):
                                return False, SAY_REUSED, facts
                            # By the id too (1.0.214), whatever the token is called by then.
                            if not once_take(self.store, 'scratch', '#%d' % tok['id'], id_h, peer=False):
                                return False, SAY_REUSED, facts
                    except Exception:
                        # The COMMIT's answer lost (1.0.222), as for a code from the phone.
                        try:
                            row = self.store.db.row('SELECT scratch, last_used FROM tokens WHERE id = ?',
                                                    (tok['id'],))
                        except Exception:               # noqa: BLE001
                            row = None
                        if not row or row.get('scratch') != json.dumps(kept) or \
                                abs(fnum(row.get('last_used')) - float(t)) > 1e-6:
                            raise
                        log('the database answered the end of a sign-in late: %s\'s recovery code '
                            'was written and is let in' % name, 'warn')
                    if not once_peer_free(self.store, 'scratch', name, h) or \
                            not once_peer_free(self.store, 'scratch', '#%d' % tok['id'], id_h):
                        return False, SAY_REUSED, facts
                elif hit != h:
                    # Dry, so the code stays; but an entry in the old shape is
                    # rewritten in the new one now that it is known.
                    kept[kept.index(hit)] = h
                    self.store.db.run('UPDATE tokens SET scratch = ? WHERE id = ? AND scratch = ?',
                                      (json.dumps(kept), tok['id'], was))
                facts['scratch_left'] = len(kept)
                return True, SAY_SCRATCH, facts
            # A recovery code used once and sent again (1.0.214): said as used, not
            # counted as a wrong code - as a code from the phone used again is not. A
            # NAS asking again, or a person trying it twice, paused or locked the token.
            if key and re.fullmatch(r'\d{6,12}', code or ''):
                try:
                    if self.store.db.value('SELECT 1 FROM token_once WHERE k IN (?, ?)',
                                           (once_key('scratch', name,
                                                     scratch_hash(name, code, key)),
                                            once_key('scratch', '#%d' % tok['id'],
                                                     scratch_id_hash(tok['id'], code, key)))):
                        return False, SAY_REUSED, facts
                except Exception:                       # noqa: BLE001
                    pass
            return None
        if token_kind(tok) != 'totp':
            # A token that gets its codes sent (1.0.76): what is checked here
            # is only ever a recovery code - the sent code is the
            # challenge's, and the key it keeps is never on any phone.
            got = scratch_try()
            return got if got is not None else failed(SAY_BAD)
        if len(code) != digits:
            got = scratch_try()
            return got if got is not None else failed(SAY_BAD)
        step = totp_match(secret, code, tc, digits, tok.get('period') or 30,
                          tok.get('algorithm') or 'SHA1', self.window(tok))
        if step is None:
            # A recovery code as long as a code from the phone (1.0.33): with
            # the two lengths set alike, recovery codes were never tried.
            got = scratch_try()
            return got if got is not None else failed(SAY_BAD)
        facts['off'] = step - totp_step(tc, tok.get('period') or 30)
        if CONFIG.get('totp_disallow_reuse', 1) and step <= int(tok.get('last_step') or 0):
            # Refused, but not counted as a wrong code (1.0.57): it is the
            # right code a second time - a NAS that sent the request again,
            # or to the other node - and counting it locked people out.
            return False, SAY_REUSED, facts
        if not dry:
            if CONFIG.get('totp_disallow_reuse', 1):
                # Used up with one conditional UPDATE: of two nodes asked for
                # the same code at the same moment, only one changes the row.
                # The step used once anywhere (1.0.101): on two replicating
                # nodes the UPDATE below holds only on its own database.
                # Tied to this key - the key itself, through an HMAC: the same
                # on both nodes whatever its sealed form, new with every key.
                once_v = '%s:%s:%s' % (tok['id'], hmac.new(sealing_key() or b'', str(secret).encode(),
                                                          hashlib.sha256).hexdigest()[:16], step)
                # All three in one transaction (1.0.214): the database dropping between
                # them left the code used here, the request unanswered, and the other
                # node - asked next by the NAS - refused it as used. The other node's
                # database asked after, the row not held meanwhile.
                try:
                    with self.store.db.transaction():
                        won = self.store.db.run(
                            'UPDATE tokens SET last_step = ?, last_used = ?, failures = 0, '
                            "fail_times = '[]', last_how = 'code' WHERE id = ? AND "
                            'COALESCE(last_step, 0) < ? AND secret = ?',
                            (step, t, tok['id'], step, tok.get('secret')))
                        if not won:
                            # The key itself replaced meanwhile (1.0.222): the old key's step
                            # written onto the new one let the old code in and refused the new
                            # key's codes as used - for decades, with another period.
                            now_sealed = self.store.db.value('SELECT secret FROM tokens WHERE id = ?',
                                                             (tok['id'],))
                            if now_sealed != tok.get('secret'):
                                # ...or only sealed again, the same key (1.0.224: a node binding
                                # its tokens at start) - a right code was refused.
                                if not now_sealed or unseal_secret(
                                        now_sealed, token_bind(tok.get('name'))) != secret:
                                    return False, SAY_BAD, facts
                                won = self.store.db.run(
                                    'UPDATE tokens SET last_step = ?, last_used = ?, failures = 0, '
                                    "fail_times = '[]', last_how = 'code' WHERE id = ? AND "
                                    'COALESCE(last_step, 0) < ? AND secret = ?',
                                    (step, t, tok['id'], step, now_sealed))
                            if not won:
                                return False, SAY_REUSED, facts
                        if not once_take(self.store, 'step', name, once_v, peer=False):
                            return False, SAY_REUSED, facts
                        # By the token's id as well (1.0.214): renamed on the other node meanwhile,
                        # the step used under the old name was not found under the new one. The
                        # name's key stays for a node of an older version, in a rolling upgrade.
                        if not once_take(self.store, 'step', '#%d' % tok['id'], once_v, peer=False):
                            return False, SAY_REUSED, facts
                except Exception:
                    # The COMMIT's answer lost (1.0.222): the database wrote it all, the
                    # connection dropped before it said so, the request went unanswered and
                    # the NAS's retry - here or on the other node - was refused as used. This
                    # request's own write looked for: there, it was let in; not there, no answer.
                    if not self._own_step_landed(tok['id'], step, t):
                        raise
                    log('the database answered the end of a sign-in late: %s\'s code was written '
                        'and is let in' % name, 'warn')
                if not once_peer_free(self.store, 'step', name, once_v) or \
                        not once_peer_free(self.store, 'step', '#%d' % tok['id'], once_v):
                    return False, SAY_REUSED, facts
            else:
                # Never back (1.0.222): an older code used with reuse let in set last_step
                # back, and the codes used since were good again once it was refused again.
                won = self.store.db.run(
                    'UPDATE tokens SET last_step = CASE WHEN COALESCE(last_step, 0) < ? THEN ? '
                    "ELSE last_step END, last_used = ?, failures = 0, fail_times = '[]', "
                    "last_how = 'code' WHERE id = ? AND secret = ?",
                    (step, step, t, tok['id'], tok.get('secret')))
                # MariaDB counts the rows changed, not those found: the same code again
                # at the same instant changes nothing - asked, not taken for a new key.
                if not won:
                    now_sealed = self.store.db.value('SELECT secret FROM tokens WHERE id = ?',
                                                     (tok['id'],))
                    if now_sealed != tok.get('secret'):
                        # Only sealed again, the same key (1.0.226, as with reuse refused).
                        if not now_sealed or unseal_secret(
                                now_sealed, token_bind(tok.get('name'))) != secret:
                            return False, SAY_BAD, facts
                        self.store.db.run(
                            'UPDATE tokens SET last_step = CASE WHEN COALESCE(last_step, 0) < ? '
                            "THEN ? ELSE last_step END, last_used = ?, failures = 0, fail_times = '[]', "
                            "last_how = 'code' WHERE id = ? AND secret = ?",
                            (step, step, t, tok['id'], now_sealed))
        return True, (SAY_OK if facts['off'] == 0 else SAY_OK_DRIFT), facts

    def mark_from(self, name, src, client=''):
        # One UPDATE (1.0.33): read and written again, it was two round trips
        # on every request let in. With the RADIUS client it came through
        # (1.0.58).
        self.store.db.run('UPDATE tokens SET last_from = ?, last_client = ? WHERE name = ?',
                          (str(src or '')[:120], str(client or '')[:120], norm_name(name)))

    def _said(self, name, ok, said, how, src, rid, off=None):
        row = {'ts': time.time(), 'name': name, 'ok': 1 if ok else 0, 'said': said, 'how': how,
               'src': str(src or '')[:120], 'rid': str(rid or '')[:120],
               'step_off': int(off) if off is not None else None}
        later = getattr(OTP_LOG_LATER, 'rows', None)
        if later is not None:
            # A RADIUS worker's: written once the answer went (1.0.186).
            later.append(row)
        else:
            try:
                self.store.otp_add(row)
            except Exception as e:
                log('the check of a code could not be written down: %s' % e, 'warn')
        if self.on_check:
            try:
                self.on_check(name, ok, said, how, src, rid)
            except Exception as e:
                log('the check of a code could not be sent on: %s' % e, 'warn')


# ---------------------------------------------------------------------------
# Sending the logs to isemon
# ---------------------------------------------------------------------------
# isemon reads a token server through two files rsyslog writes for it: what
# totpcgi said about every code (`totp.cgi`), and every RADIUS packet the
# FreeRADIUS in front of it wrote into its detail files, one to a line
# (`radius-detail`). This writes both, in exactly those shapes, as syslog to
# isemon's receiver - and into files here as well - so that isemon reads this
# server with the readers it already has and nothing changed on its side.

SYSLOG_FACILITY = {'auth': 4, 'authpriv': 10, 'local5': 21, 'daemon': 3, 'user': 1}


def syslog_targets(text, strict=False):
    """`host[:port][/udp|/tcp|/tls]` (or `tls://host:port`), comma separated,
    as (host, port, proto). TLS (1.0.172): 6514 when no port is given."""
    out = []
    for one in re.split(r'[,;\s]+', str(text or '')):
        one = one.strip()
        if not one:
            continue
        m = re.match(r'^(?:(udp|tcp|tls)://)?(\[[0-9a-fA-F:]+\]|[A-Za-z0-9.\-]+)(?::(\d+))?'
                     r'(?:/(udp|tcp|tls))?/?\Z', one, re.I)
        if not m:
            if strict:
                raise BadSetting('isemon_targets: %r is not host[:port][/udp|/tcp|/tls]' % one)
            continue
        proto = (m.group(4) or m.group(1) or 'udp').lower()
        port = int(m.group(3) or (6514 if proto == 'tls' else 514))
        if strict and not 0 < port < 65536:
            raise BadSetting('isemon_targets: %d is not a port' % port)
        out.append((m.group(2).strip('[]'), port, proto))
    return out


def syslog_stamp(ts=None):
    """`Oct 22 15:31:02` - RFC 3164, the shape the readers on the other side
    expect: no year, no zone, the day padded with a space."""
    t = datetime.fromtimestamp(float(ts if ts is not None else time.time()))
    return '%s %2d %s' % (t.strftime('%b'), t.day, t.strftime('%H:%M:%S'))


def detail_quote(value):
    """A value as FreeRADIUS writes it in a detail file: a string in quotes,
    with its quotes and backslashes escaped."""
    said = str(value)
    if re.match(r'^(0x[0-9a-fA-F]*|\d+|\d+\.\d+\.\d+\.\d+)\Z', said) or said in (
            'Access-Request', 'Access-Accept', 'Access-Reject', 'Access-Challenge',
            'Accounting-Request') or re.match(r'^[A-Z][A-Za-z0-9.-]*\Z', said) and \
            said in [w for d in RADIUS_VALUES.values() for w in d.values()]:
        return said
    return '"%s"' % said.replace('\\', '\\\\').replace('"', '\\"')


def _conn_alive(sock):
    """Whether a connection the other side never writes into is still open:
    readable means closed (or, over TLS, a session ticket - read, and still
    open)."""
    try:
        r, _w, _x = select.select([sock], [], [], 0)
    except (OSError, ValueError):
        return False
    if not r:
        return True
    was = sock.gettimeout()
    try:
        sock.setblocking(False)
        got = sock.recv(4096)
        return bool(got)
    except (ssl.SSLWantReadError, BlockingIOError):
        return True
    except (OSError, ssl.SSLError):
        return False
    finally:
        try:
            sock.settimeout(was)
        except OSError:
            pass


class Shipper(object):
    """A queue and a thread that empties it into isemon's receivers and the
    files here. Nothing that answers a VPN ever waits for any of it."""

    def __init__(self):
        self.q = queue.Queue(maxsize=20000)
        self.targets = []
        self.tcp = {}
        self.udp4 = None
        self.udp6 = None
        self.files = {}
        self.sent = collections.Counter()
        self.trouble = {}
        self.down = {}              # a TCP target that failed: (until, wait) - 1.0.59
        self.missed = collections.Counter()
        self.dropped = 0
        self.last_sent = 0.0
        self.ctx = None
        self.stop_flag = False
        self.thread = threading.Thread(target=self.run, name='shipper', daemon=True)
        self.configure()
        self.thread.start()

    def configure(self):
        self.targets = syslog_targets(CONFIG.get('isemon_targets')) if CONFIG.get('isemon') \
            else []
        self.ctx = None                 # the TLS settings may have changed (1.0.172)
        # And every connection made again when they did (1.0.206): one made
        # unchecked went on unchecked for weeks, as SIEM's did.
        tls = (CONFIG.get('isemon_verify'), CONFIG.get('isemon_ca'), CONFIG.get('isemon_mtls'))
        again = tls != getattr(self, '_tls_was', tls)
        self._tls_was = tls
        for key, sock in list(self.tcp.items()):
            if again or key not in self.targets:
                try:
                    sock.close()
                except OSError:
                    pass
                self.tcp.pop(key, None)
        # The trouble of a target no longer sent to, gone with it (1.0.249): its alert stayed
        # until the next restart.
        keep = {'%s:%d/%s' % t for t in self.targets}
        for d in (self.trouble, getattr(self, 'down', None) or {}):
            for k in list(d):
                if (not str(k).startswith('file:') or not CONFIG.get('ship_files')) and k not in keep:
                    d.pop(k, None)

    def host(self):
        return str(CONFIG.get('isemon_hostname') or '').strip() or short_host()

    # ---- what is said ----------------------------------------------------------
    def put(self, tag, facility, words, ts=None, file_name=None):
        if not CONFIG.get('isemon') and not CONFIG.get('ship_files'):
            return
        most = int(CONFIG.get('isemon_max_bytes') or 1800)
        if len(words.encode('utf-8')) > most:
            words = words.encode('utf-8')[:most].decode('utf-8', 'ignore') + ' ...TRUNCATED'
        line = '%s %s %s[%d]: %s' % (syslog_stamp(ts), self.host(), tag, os.getpid(),
                                     words.replace('\n', ' ').replace('\r', ' '))
        pri = SYSLOG_FACILITY.get(facility, 1) * 8 + 5          # notice
        try:
            self.q.put_nowait((pri, line, file_name))
        except queue.Full:
            self.dropped += 1

    def token_line(self, name, ok, said, how, src, rid):
        """`totp.cgi[pid]: Success: user=..., mode=PAM_SM_AUTH, host=..., rid=...,
        message=...` - totpcgi's own line, with the request id isemon joins it
        to the RADIUS packet by."""
        if how not in ('radius', 'test'):
            mode = 'PROVISION' if how == 'portal' else how.upper()
        else:
            mode = 'PAM_SM_AUTH'
        clean = lambda s: re.sub(r'[\r\n]', ' ', str(s or ''))
        rid = re.sub(r'[^A-Za-z0-9.:_-]', '', str(rid or ''))[:64]
        words = '%s: user=%s, mode=%s, host=%s, %smessage=%s' % (
            'Success' if ok else 'Failure', re.sub(r'[,=\s]', '_', clean(name)), mode, '127.0.0.1',
            ('rid=%s, ' % rid) if rid else '', clean(said))
        self.put('totp.cgi', 'auth', words, file_name='totp.cgi.log')

    def detail_line(self, nas, kind, ts, pairs, ident=''):
        """`radius-detail[pid]: nas=... id=... file=auth-detail-YYYYMMDD ts=[ctime]
        Name = value, ...` - one detail record a line, the way the shipper
        isemon ships with writes it."""
        if not CONFIG.get('isemon_detail', 1):
            return
        fname = '%s-%s' % (kind, datetime.fromtimestamp(ts).strftime('%Y%m%d'))
        body = ', '.join('%s = %s' % (k, detail_quote(v)) for k, v in pairs)
        rid = ident or hashlib.sha1(('%s|%s|%s|%s' % (nas, fname, ts, body))
                                    .encode('utf-8', 'replace')).hexdigest()[:16]
        words = 'nas=%s id=%s file=%s ts=[%s] %s' % (nas, rid, fname, time.ctime(ts), body)
        self.put('radius-detail', 'local5', words, file_name='radius-detail.log')

    def event_line(self, kind, words, level, who):
        if CONFIG.get('isemon_events'):
            self.put('otp', 'daemon', '%s: %s%s' % (kind, words, (' (by %s)' % who) if who
                                                    else ''), file_name=None)

    # ---- sending ---------------------------------------------------------------
    def run(self):
        while not self.stop_flag:
            try:
                pri, line, file_name = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            # Nothing ends this thread (1.0.186): one error took isemon's
            # sending and its files away until a restart.
            try:
                if file_name and CONFIG.get('ship_files'):
                    self._to_file(file_name, line)
                if CONFIG.get('isemon'):
                    for target in list(self.targets):
                        self._to_target(target, '<%d>%s' % (pri, line))
            except Exception as e:                      # noqa: BLE001
                log_sparing('shipper', 'isemon: a line could not go: %s' % e, 'warn', every=300)

    def _to_file(self, name, line):
        path = LOG_DIR / name
        f = self.files.get(name)
        try:
            # Looked at for a rotation once a second a file (1.0.265), not at every line - two
            # stats a line for each request were a tenth of what writing a request cost.
            now = time.monotonic()
            looked = getattr(self, 'files_looked', None)
            if looked is None:
                looked = self.files_looked = {}
            if f is not None and (f.closed or now - looked.get(name, 0.0) >= 1.0):
                looked[name] = now
                try:
                    if f.closed or os.fstat(f.fileno()).st_ino != os.stat(path).st_ino:
                        raise OSError('rotated')
                except (OSError, ValueError):
                    try:
                        f.close()
                    except (OSError, ValueError):
                        pass
                    self.files.pop(name, None)
                    f = None
            if f is None:
                try:
                    f = open(path, 'a', encoding='utf-8')
                except FileNotFoundError:
                    # The folder made only when it is not there (1.0.265), not before each open.
                    LOG_DIR.mkdir(parents=True, exist_ok=True)
                    f = open(path, 'a', encoding='utf-8')
                self.files[name] = f
                looked[name] = now
            f.write(line + '\n')
            f.flush()
            if self.trouble:
                self.trouble.pop('file:' + name, None)  # written again: no trouble (1.0.249)
        except (OSError, ValueError) as e:
            self.trouble['file:' + name] = str(e)

    def _to_target(self, target, data):
        host, port, proto = target
        key = '%s:%d/%s' % target
        raw = data.encode('utf-8', 'replace')
        try:
            if proto == 'udp':
                fam = socket.AF_INET6 if ':' in host else socket.AF_INET
                if fam == socket.AF_INET6:
                    if self.udp6 is None:
                        self.udp6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    self.udp6.sendto(raw, (host, port))
                else:
                    if self.udp4 is None:
                        self.udp4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.udp4.sendto(raw, (host, port))
            else:
                # A TCP target that cannot be reached is left alone for a
                # while (1.0.59): every line waited 5 s on it, the queue
                # filled, and the files here lost lines with it.
                until, wait = self.down.get(key, (0.0, 0.0))
                if time.time() < until:
                    self.missed[key] += 1
                    return
                sock = self.tcp.get(target)
                if sock is not None and not _conn_alive(sock):
                    # Closed by the other side - isemon restarted (1.0.172): the
                    # first line written into it would have been lost unsaid.
                    try:
                        sock.close()
                    except OSError:
                        pass
                    sock = None
                    self.tcp.pop(target, None)
                for attempt in (1, 2):
                    if sock is None:
                        sock = socket.create_connection((host, port), timeout=5)
                        if proto == 'tls':
                            # Encrypted, isemon's certificate checked (1.0.172).
                            if self.ctx is None:
                                self.ctx = isemon_tls_ctx()
                            sock = self.ctx.wrap_socket(sock, server_hostname=host)
                        sock.settimeout(5)
                        self.tcp[target] = sock
                    try:
                        sock.sendall(raw + b'\n')
                        break
                    except OSError:
                        try:
                            sock.close()
                        except OSError:
                            pass
                        sock = None
                        self.tcp.pop(target, None)
                        if attempt == 2:
                            raise
            self.sent[key] += 1
            self.last_sent = time.time()
            self.trouble.pop(key, None)
            self.down.pop(key, None)
        except (OSError, ssl.SSLError, ValueError) as e:
            if key not in self.trouble:
                log('isemon at %s cannot be sent to: %s' % (key, e), 'warn')
            if proto != 'udp':
                _u, wait = self.down.get(key, (0.0, 0.0))
                wait = min(300.0, max(15.0, wait * 2))
                self.down[key] = (time.time() + wait, wait)
                self.missed[key] += 1
                e = '%s - tried again in %d s, %d line(s) not sent to it' % (
                    e, int(wait), self.missed[key])
            self.trouble[key] = '%s (%s)' % (e, datetime.now().strftime('%H:%M:%S'))

    def state(self):
        return {'on': bool(CONFIG.get('isemon')), 'host': self.host(),
                'targets': ['%s:%d/%s' % t for t in self.targets],
                'tls': {'verify': bool(CONFIG.get('isemon_verify', 1)),
                        'mtls': bool(CONFIG.get('isemon_mtls')),
                        'ca': 'given' if str(CONFIG.get('isemon_ca') or '').strip() else 'system'},
                'sent': dict(self.sent), 'trouble': dict(self.trouble),
                'queued': self.q.qsize(), 'dropped': self.dropped,
                'last_sent': self.last_sent, 'files': bool(CONFIG.get('ship_files')),
                'file_dir': str(LOG_DIR)}

    def flush(self, wait=3.0):
        until = time.time() + wait
        while not self.q.empty() and time.time() < until:
            time.sleep(0.05)


def codes_open(tok):
    """A token's recovery codes as kept to be shown again, each one no longer
    in its list of hashes marked used (1.0.61). Two nodes using a code each
    at the same moment end with the same list of hashes, but each node's
    sealed copy may still hold the other's code as unused - and a rename,
    an export or the codes view would have brought it back."""
    shown = open_codes(tok.get('scratch_sealed'), token_bind(tok.get('name')))
    if shown is None:
        return None
    try:
        kept = [str(k) for k in json.loads(tok.get('scratch') or '[]')]
    except (ValueError, TypeError):
        return shown
    key = sealing_key()
    for one in shown:
        if isinstance(one, dict) and not one.get('used') and \
                not scratch_find(tok.get('name'), one.get('c'), kept, key)[0]:
            one['used'] = time.time()
    return shown
