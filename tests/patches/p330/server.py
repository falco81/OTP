"""1.0.330 (parts): the primary group of an AD account counted among its groups."""
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


edit('60_engine.py', [
("""              'objectClass', 'msDS-User-Account-Control-Computed', 'objectSid')
""",
 """              'objectClass', 'msDS-User-Account-Control-Computed', 'objectSid', 'primaryGroupID')
"""),
("""                     'sid': sid_text(bytes.fromhex(first('objectSid'))) if re.match(
                         r'^[0-9a-f]{16,136}\\Z', first('objectSid') or '') else '',
""",
 """                     'sid': sid_text(bytes.fromhex(first('objectSid'))) if re.match(
                         r'^[0-9a-f]{16,136}\\Z', first('objectSid') or '') else '',
                     # Its primary group (1.0.330): on AD in neither memberOf nor the group's member.
                     'primary_sid': primary_group_sid(first('objectSid'), first('primaryGroupID')).hex(),
"""),
("""        if not entry:
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
""",
 """        if not entry:
            return []
        key = ('g' if nested else 'g1', entry['dn'].lower())
        if nested or entry.get('primary_sid'):
            with self.lock:
                got = self.cache.get(key)
                if got and time.time() - got[0] < self.CACHE_S:
                    return got[1]
        # The primary group (1.0.330): AD keeps it in the account's primaryGroupID alone - in
        # neither memberOf nor the group's member, so the in-chain rule never finds it. A realm
        # or a role given to "Domain Users", or to a group made the primary one, refused all.
        prim = self.primary_group(entry)
        if not nested:
            out = [(g, cn_of(g)) for g in entry.get('member_of') or []]
            if prim and prim[0].lower() not in {g.lower() for g, _ in out}:
                out.append(prim)
            if entry.get('primary_sid'):
                self._cache_put(key, out)
            return out
        def do(link):
            link.PAGES_MOST = 20        # a sign-in's groups, not a census (1.0.59)
            # From the root of the domain (1.0.153), as group_dns looks: a base
            # for the people (OU=Users,...) left out every group kept beside
            # it (OU=Groups,...), and nobody was in any group.
            chain = ldap_in_chain('member', entry['dn'])
            if prim:                    # and the groups the primary group is in (1.0.330)
                chain = ldap_or(chain, ldap_in_chain('member', prim[0]))
            return link.search(self.domain_root(), ldap_and(ldap_equal('objectClass', 'group'),
                                                   chain),
                               ('cn',), scope=2, limit=5000, paged=True)
        rows = self.asked(do)
        out = [(r['dn'], (r['attrs'].get('cn') or [cn_of(r['dn'])])[0]) for r in rows]
        if prim and prim[0].lower() not in {g.lower() for g, _ in out}:
            out.append(prim)
        self._cache_put(key, out)                 # as find_user keeps it (1.0.209, 1.0.265)
        return out

    def primary_group(self, entry):
        \"\"\"(dn, cn) of the account's primary group on AD (1.0.330), or None: where it has no
        primaryGroupID (not AD), or the group is not found. Kept as the groups are.\"\"\"
        sid = (entry or {}).get('primary_sid')
        if not sid:
            return None
        key = ('pg', sid)
        with self.lock:
            got = self.cache.get(key)
            if got and time.time() - got[0] < self.CACHE_S:
                return got[1]
        try:
            rows = self.asked(lambda link: link.search(
                self.domain_root(), ldap_and(ldap_equal('objectClass', 'group'),
                                             ldap_equal('objectSid', bytes.fromhex(sid))),
                ('cn',), scope=2, limit=2))
        except LdapUnreachable:
            raise
        except Exception as e:          # the groups as before, not the sign-in refused
            log('the primary group of %s was not found: %s' % (entry.get('dn'), e), 'warn')
            return None
        prim = None
        if len(rows) == 1:
            r = rows[0]
            prim = (r['dn'], (r['attrs'].get('cn') or [cn_of(r['dn'])])[0])
        self._cache_put(key, prim)
        return prim
"""),
])

edit('60_engine.py', [
("""AD_UAC_DISABLED = 0x2
""",
 """AD_UAC_DISABLED = 0x2


def primary_group_sid(sid_hex, rid):
    \"\"\"The binary SID of an AD account's primary group (1.0.330): the account's own SID with its
    last part (its RID) the primaryGroupID - b'' where either is not there or not right.\"\"\"
    try:
        raw = bytes.fromhex(str(sid_hex or ''))
        rid = int(str(rid or '').strip())
    except ValueError:
        return b''
    if not (0 < rid < 2 ** 32) or len(raw) < 12 or raw[0] != 1 or len(raw) != 8 + 4 * raw[1] \\
            or raw[1] < 1:
        return b''
    return raw[:-4] + rid.to_bytes(4, 'little')
"""),
])
