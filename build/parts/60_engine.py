

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
              'objectClass', 'msDS-User-Account-Control-Computed')
# msDS-User-Account-Control-Computed (1.0.101): what AD works out now -
# locked out (0x10) and the password expired (0x800000). lockoutTime alone
# stays set after the lockout is over.
AD_UACC_LOCKED = 0x10
AD_UACC_PW_EXPIRED = 0x800000


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
                        break
                self.last_good = host
                self._up(host)
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
            want = ldap_equal('mail', said)
        else:
            want = ldap_equal('userPrincipalName', said)
        flt = ldap_and(ldap_equal('objectClass', 'user'), want)
        link = self.link()
        try:
            # Three, not two (1.0.101): a computer's account among them is
            # dropped below, and must not hide a second person of the name.
            rows = link.search(self.base, flt, USER_ATTRS, scope=2, limit=3)
        finally:
            link.close()
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
                     'mail': first('mail'), 'uac': uac,
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
                     # For a code by SMS (1.0.76): what the enrolment page offers.
                     'mobile': first('mobile') or first('telephoneNumber'),
                     'phone': first('telephoneNumber'),
                     'pw_set': ad_time(first('pwdLastSet')),
                     'many': len(rows) > 1}
        with self.lock:
            self.cache[key] = (time.time(), entry)
            if len(self.cache) > 5000:
                self.cache.clear()
        return entry

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
        link = self.link()
        link.PAGES_MOST = 20            # a sign-in's groups, not a census (1.0.59)
        try:
            rows = link.search(self.base, ldap_and(ldap_equal('objectClass', 'group'),
                                                   ldap_in_chain('member', entry['dn'])),
                               ('cn',), scope=2, limit=5000, paged=True)
        finally:
            link.close()
        out = [(r['dn'], (r['attrs'].get('cn') or [cn_of(r['dn'])])[0]) for r in rows]
        with self.lock:
            self.cache[key] = (time.time(), out)
        return out

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
        dcs = [p for p in re.split(r'(?<!\\),', str(self.base or '')) if
               p.strip().lower().startswith('dc=')]
        where = ','.join(p.strip() for p in dcs) or self.base
        link = self.link()
        link.PAGES_MOST = 5
        try:
            rows = link.search(where, ldap_and(
                ldap_equal('objectClass', 'group'),
                ldap_or(ldap_equal('sAMAccountName', said), ldap_equal('cn', said))),
                ('cn', 'sAMAccountName'), scope=2, limit=50, paged=True)
        finally:
            link.close()

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
        with self.lock:
            if len(self.cache) > 5000:
                self.cache.clear()
            self.cache[key] = (time.time(), out)
        return out

    def password_ok(self, entry, password):
        """True, or LdapError with the directory's reason in words."""
        if not str(password or ''):
            raise LdapError('a password is needed')
        if not str((entry or {}).get('dn') or '').strip():
            # A bind with no name and a password is an anonymous one on many
            # servers (1.0.101): never asked.
            raise LdapError('no account to check the password of')
        if any(ord(c) < 32 or ord(c) == 127 for c in str(password)):
            # Cut at a NUL somewhere on the way, a password is empty - and an
            # empty one binds anonymously (1.0.101).
            raise LdapError('the password holds a control character')
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
                if e.code in LDAP_TRY_ANOTHER or (e.code is None and 'does not read' in str(e)):
                    tried.append(str(e))
                    continue
                raise
            finally:
                one.close()
        raise LdapUnreachable('no server of %s could be reached (%s)'
                              % (self.name, '; '.join(tried)))

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
            rows = link.search(self.base, want, ('sAMAccountName', 'userPrincipalName',
                                                 'displayName', 'mail', 'userAccountControl',
                                                 'mobile', 'telephoneNumber', attr), scope=2,
                                limit=limit + 10)
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
                        'mail': first('mail'), 'disabled': bool(uac & AD_UAC_DISABLED),
                        'mobile': first('mobile') or first('telephoneNumber')})
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
    after = int(CONFIG.get('lockout_after') or 0)
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


SCRATCH_GUARD_MOST = 20          # a day's refused tries before recovery codes rest (1.0.101)
SCRATCH_GUARD_S = 86400


def scratch_guard_times(store, name):
    try:
        got = [float(x) for x in json.loads(store.get_meta('scratchguard:' + norm_name(name))
                                            or '[]')]
    except (ValueError, TypeError):
        got = []
    return [x for x in got if time.time() - x < SCRATCH_GUARD_S]


def scratch_guard_note(store, name):
    """One request whose password and recovery code could not both be right
    (1.0.101) - see the RADIUS side. Written only over what was read."""
    k = 'scratchguard:' + norm_name(name)
    for _round in range(8):
        raw = store.get_meta(k)
        times = scratch_guard_times(store, name)[-(SCRATCH_GUARD_MOST * 2):] + [time.time()]
        new = json.dumps(times)
        if raw is None:
            try:
                store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, new))
                break
            except Exception:                           # noqa: BLE001
                continue
        if store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (new, k, raw)):
            break
    if len(times) == SCRATCH_GUARD_MOST:
        store.add_event('tokens', 'the recovery codes of %s are not taken for a day: %d '
                        'requests in a day had a wrong password or a wrong recovery code - '
                        'somebody may be guessing them (Unlock it on the token gives them back)'
                        % (norm_name(name), SCRATCH_GUARD_MOST), 'warn', who='otp')


def scratch_guarded(store, name):
    return len(scratch_guard_times(store, name)) >= SCRATCH_GUARD_MOST


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
    a = {k.lower(): v for k, v in (r.get('attrs') or {}).items()}
    if any(str(x).lower() == 'computer' for x in a.get('objectclass') or []):
        return True
    return str((a.get('samaccountname') or [''])[0]).endswith('$')


def group_matches(wanted, have, ad=None):
    """Whether any group in `have` ([(dn, cn)]) is one of `wanted` (names or
    DNs). Returns the wanted entry that matched first, in `wanted`'s order.

    A name without its place is the one group `ad` says it is (1.0.101), by
    its DN - never any group of that cn wherever it is. Without `ad` to ask,
    a name alone matches nothing."""
    by_dn = {dn.lower() for dn, _ in have}
    by_cn = {str(cn).lower() for _, cn in have}
    for one in wanted:
        said = str(one.get('group') if isinstance(one, dict) else one).strip()
        if not said:
            continue
        if '=' in said and ',' in said:
            if said.lower() in by_dn:
                return one
        elif said.lower() in by_cn and ad is not None:
            try:
                dns = ad.group_dns(said)
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
    if text is None and str(value).lstrip().startswith('['):
        text = value
    try:
        got = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(got, list):
        return None
    return [dict(x) if isinstance(x, dict) else {'c': str(x), 'used': None} for x in got]


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
            self.store.db.run('DELETE FROM meta WHERE k = ?', ('disabled_from:' + name,))
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
        try:
            got = json.loads(self.store.get_meta('staged:' + norm_name(name), '') or '{}')
        except ValueError:
            got = {}
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
            self.store.db.run('DELETE FROM meta WHERE k = ?', ('staged:' + norm_name(name),))
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
        t = time.time()
        try:
            # A waiting replacement counts its wrong codes beside its own
            # shape (1.0.61): in the token's own they paused the token still
            # in use as well.
            fails = [float(x) for x in (shape.get('fail_times') if staged
                                        else json.loads(tok.get('fail_times') or '[]')) or []]
        except (ValueError, TypeError):
            fails = []
        tries = int(CONFIG.get('rate_limit_tries') or 0)
        fails = [x for x in fails if t - x < int(CONFIG.get('rate_limit_s') or 30)]
        if float(tok.get('locked_until') or 0) > t:
            self._said(name, False, SAY_LOCKED + ' (confirming a new token)', how, src, '')
            return False, SAY_LOCKED
        if tries and len(fails) >= tries:
            self._said(name, False, SAY_RATE + ' (confirming a new token)', how, src, '')
            return False, SAY_RATE
        step = totp_match(secret, code, None, shape['digits'], shape['period'],
                          shape['algorithm'], self.window(tok))
        if step is None and staged:
            # A replacement's wrong codes do not lock the token still in use
            # (1.0.59) - the phone answering with the old account is the
            # usual wrong code here. They are counted against the waiting key:
            # past the lockout count it is thrown away, to be made again.
            shape['fail_times'] = fails + [t]
            shape['fails'] = int(shape.get('fails') or 0) + 1
            after = int(CONFIG.get('lockout_after') or 0)
            if after and shape['fails'] >= after:
                self.drop_staged(name)
                self._said(name, False, SAY_BAD + ' (confirming a new token - too many, '
                           'the new key is thrown away)', how, src, '')
                return False, (SAY_BAD + '. Too many wrong codes: the new key was thrown '
                               'away - the token in use goes on working; make a new one.')
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
        self.store.token_update(tok['id'], fields)
        if staged:
            self._staged_forget(name)
        self._said(name, True, 'Token confirmed', how, src, '')
        return True, 'Token confirmed'

    @staticmethod
    def why_wrong(secret, code, tok):
        """What a wrong code most likely means, for the person typing it."""
        period = int(tok.get('period') or 30)
        far = totp_match(secret, code, None, tok.get('digits') or 6, period,
                         tok.get('algorithm') or 'SHA1', 40)
        if far is not None:
            off = (far - totp_step(None, period)) * period
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
        self.store.token_write(name, {'scratch': json.dumps([scratch_hash(name, c)
                                                             for c in codes]),
                                      'scratch_sealed': seal_codes(codes, token_bind(name)),
                                      'scratch_left': len(codes)})
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

    def _fail_noted(self, tok_id, t, span, mins):
        """The time of a wrong code added to the token's recent ones, and the
        lock set - by a conditional update (1.0.101): two nodes each reading
        the list and writing it back with their own time added lost one of
        them, and a guesser sending to both nodes at once got twice the
        tries the pause allows."""
        for _round in range(8):
            was = self.store.db.value('SELECT fail_times FROM tokens WHERE id = ?', (tok_id,))
            try:
                fails = [float(x) for x in json.loads(was or '[]')]
            except (ValueError, TypeError):
                fails = []
            fails = [x for x in fails if t - x < span] + [t]
            sets, args = 'fail_times = ?', [json.dumps(fails[-50:])]
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
            fields = {'fail_times': json.dumps([t])}
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
        t = time.time()
        if tok.get('state') == 'disabled':
            return SAY_OFF
        if float(tok.get('locked_until') or 0) > t:
            return SAY_LOCKED
        tries = int(CONFIG.get('rate_limit_tries') or 0)
        span = int(CONFIG.get('rate_limit_s') or 30)
        try:
            fails = [float(x) for x in json.loads(tok.get('fail_times') or '[]')]
        except (ValueError, TypeError):
            fails = []
        if tries and len([x for x in fails if t - x < span]) >= tries:
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
        t = time.time()
        try:
            fails = [float(x) for x in json.loads(tok.get('fail_times') or '[]')]
        except (ValueError, TypeError):
            fails = []
        tries = int(CONFIG.get('rate_limit_tries') or 0)
        span = int(CONFIG.get('rate_limit_s') or 30)
        fails = [x for x in fails if t - x < span]
        # A lockout after many wrong codes in a row, however slowly they
        # came (1.0.33): the short pause alone let a patient guesser try
        # thousands of codes a day.
        if float(tok.get('locked_until') or 0) > t:
            return False, SAY_LOCKED, facts
        if tries and len(fails) >= tries:
            return False, SAY_RATE, facts
        secret = unseal_secret(tok.get('secret') or '', token_bind(name))
        if not secret:
            return False, SAY_LOST, facts
        digits = int(tok.get('digits') or 6)
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
            try:
                kept = json.loads(tok.get('scratch') or '[]')
            except ValueError:
                kept = []
            key = sealing_key()
            hit, h = scratch_find(name, code, kept, key)
            if hit:
                was = tok.get('scratch') or '[]'
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
                    if not once_take(self.store, 'scratch', name, h):
                        return False, SAY_REUSED, facts
                elif hit != h:
                    # Dry, so the code stays; but an entry in the old shape is
                    # rewritten in the new one now that it is known.
                    kept[kept.index(hit)] = h
                    self.store.db.run('UPDATE tokens SET scratch = ? WHERE id = ? AND scratch = ?',
                                      (json.dumps(kept), tok['id'], was))
                facts['scratch_left'] = len(kept)
                return True, SAY_SCRATCH, facts
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
        step = totp_match(secret, code, t, digits, tok.get('period') or 30,
                          tok.get('algorithm') or 'SHA1', self.window(tok))
        if step is None:
            # A recovery code as long as a code from the phone (1.0.33): with
            # the two lengths set alike, recovery codes were never tried.
            got = scratch_try()
            return got if got is not None else failed(SAY_BAD)
        facts['off'] = step - totp_step(t, tok.get('period') or 30)
        if CONFIG.get('totp_disallow_reuse', 1) and step <= int(tok.get('last_step') or 0):
            # Refused, but not counted as a wrong code (1.0.57): it is the
            # right code a second time - a NAS that sent the request again,
            # or to the other node - and counting it locked people out.
            return False, SAY_REUSED, facts
        if not dry:
            if CONFIG.get('totp_disallow_reuse', 1):
                # Used up with one conditional UPDATE: of two nodes asked for
                # the same code at the same moment, only one changes the row.
                won = self.store.db.run(
                    'UPDATE tokens SET last_step = ?, last_used = ?, failures = 0, '
                    "fail_times = '[]', last_how = 'code' WHERE id = ? AND "
                    'COALESCE(last_step, 0) < ?', (step, t, tok['id'], step))
                if not won:
                    return False, SAY_REUSED, facts
                # The step used once anywhere (1.0.101): on two replicating
                # nodes the UPDATE above holds only on its own database.
                # Tied to this key - the key itself, through an HMAC: the same
                # on both nodes whatever its sealed form, new with every key.
                if not once_take(self.store, 'step', name, '%s:%s:%s' % (
                        tok['id'], hmac.new(sealing_key() or b'', str(secret).encode(),
                                            hashlib.sha256).hexdigest()[:16], step)):
                    return False, SAY_REUSED, facts
            else:
                self.store.token_update(tok['id'], {'last_step': step, 'last_used': t,
                                                    'failures': 0, 'fail_times': '[]',
                                                    'last_how': 'code'})
        return True, (SAY_OK if facts['off'] == 0 else SAY_OK_DRIFT), facts

    def mark_from(self, name, src, client=''):
        # One UPDATE (1.0.33): read and written again, it was two round trips
        # on every request let in. With the RADIUS client it came through
        # (1.0.58).
        self.store.db.run('UPDATE tokens SET last_from = ?, last_client = ? WHERE name = ?',
                          (str(src or '')[:120], str(client or '')[:120], norm_name(name)))

    def _said(self, name, ok, said, how, src, rid, off=None):
        try:
            self.store.otp_add({'ts': time.time(), 'name': name, 'ok': 1 if ok else 0,
                                'said': said, 'how': how, 'src': str(src or '')[:120],
                                'rid': str(rid or '')[:120],
                                'step_off': int(off) if off is not None else None})
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
    """`host[:port][/udp|/tcp]`, comma separated, as (host, port, proto)."""
    out = []
    for one in re.split(r'[,;\s]+', str(text or '')):
        one = one.strip()
        if not one:
            continue
        m = re.match(r'^(\[[0-9a-fA-F:]+\]|[A-Za-z0-9.\-]+)(?::(\d+))?(?:/(udp|tcp))?\Z',
                     one, re.I)
        if not m:
            if strict:
                raise BadSetting('isemon_targets: %r is not host[:port][/udp|/tcp]' % one)
            continue
        port = int(m.group(2) or 514)
        if strict and not 0 < port < 65536:
            raise BadSetting('isemon_targets: %d is not a port' % port)
        out.append((m.group(1).strip('[]'), port, (m.group(3) or 'udp').lower()))
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
        self.stop_flag = False
        self.thread = threading.Thread(target=self.run, name='shipper', daemon=True)
        self.configure()
        self.thread.start()

    def configure(self):
        self.targets = syslog_targets(CONFIG.get('isemon_targets')) if CONFIG.get('isemon') \
            else []
        for key, sock in list(self.tcp.items()):
            if (key[0], key[1], 'tcp') not in self.targets:
                try:
                    sock.close()
                except OSError:
                    pass
                self.tcp.pop(key, None)

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
            if file_name and CONFIG.get('ship_files'):
                self._to_file(file_name, line)
            if CONFIG.get('isemon'):
                for target in list(self.targets):
                    self._to_target(target, '<%d>%s' % (pri, line))

    def _to_file(self, name, line):
        path = LOG_DIR / name
        f = self.files.get(name)
        try:
            if f is not None:
                try:
                    if os.fstat(f.fileno()).st_ino != os.stat(path).st_ino:
                        raise OSError('rotated')
                except OSError:
                    f.close()
                    f = None
            if f is None:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                f = open(path, 'a', encoding='utf-8')
                self.files[name] = f
            f.write(line + '\n')
            f.flush()
        except OSError as e:
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
                sock = self.tcp.get((host, port))
                for attempt in (1, 2):
                    if sock is None:
                        sock = socket.create_connection((host, port), timeout=5)
                        sock.settimeout(5)
                        self.tcp[(host, port)] = sock
                    try:
                        sock.sendall(raw + b'\n')
                        break
                    except OSError:
                        try:
                            sock.close()
                        except OSError:
                            pass
                        sock = None
                        self.tcp.pop((host, port), None)
                        if attempt == 2:
                            raise
            self.sent[key] += 1
            self.last_sent = time.time()
            self.trouble.pop(key, None)
            self.down.pop(key, None)
        except OSError as e:
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
