# 1.0.282: the values of a certificate request for an account of the directory; the SID in the SAN URL
# (KB5014754's strong mapping) read too - python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('87c_certlogin.py', [(
"""                elif gt == 0x81:                    # rfc822Name
                    mails.append(gv.decode('ascii', 'replace'))""",
"""                elif gt == 0x81:                    # rfc822Name
                    mails.append(gv.decode('ascii', 'replace'))
                elif gt == 0x86:                    # uniformResourceIdentifier
                    # The SID as a URL of the SAN (1.0.282, KB5014754's strong mapping, as Microsoft
                    # writes it): tag:microsoft.com,2022-09-14:sid:S-1-5-21-...
                    m = re.match(r'(?i)^tag:microsoft\\.com,2022-09-14:sid:(S-1-[0-9-]{3,180})\\Z',
                                 gv.decode('ascii', 'replace').strip())
                    if m:
                        sid = sid or m.group(1).upper()""")])

edit('90c_certlogin_api.py', [(
"""    if act == 'ca_add':""",
"""    if act == 'request':
        # What a certificate request of an account needs (1.0.282): its subject, the UPN and the SID
        # of the SAN - as AD CS writes them, and certreq's and openssl's words for them.
        return cert_request_values(h, str(b.get('name') or ''))
    if act == 'ca_add':""")])

s = open(P + '90c_certlogin_api.py').read()
s = s.replace("""@route('POST', '/api/auth/cert')""", '''CERT_SID_URL = 'tag:microsoft.com,2022-09-14:sid:'


def cert_request_values(h, name):
    """The values of a certificate request for one account of the directory set for administrators
    (1.0.282): read from the directory, nothing kept, nothing changed - and whether a certificate of
    them would sign in here."""
    name = name.strip()
    if not name or len(name) > 256:
        raise ApiError(400, 'which account? its sAMAccountName, DOMAIN\\\\name or its UPN')
    ad = h.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
    if not ad:
        raise ApiError(409, 'no directory is set for administrators (Settings - Accounts)')
    who, how = admin_name_parts(name)
    bad = name_letters_problem(who.split('@', 1)[0])
    if bad:
        raise ApiError(400, '%s: %s' % (who, bad))
    try:
        entry = ad.find_user(who, how)
        have = ad.groups_of(entry, True) if entry and not entry.get('many') else []
    except LdapUnreachable as e:
        raise ApiError(503, 'the directory cannot be reached', str(e))
    if not entry:
        raise ApiError(404, 'the directory %s has nobody called %s' % (ad.name, who))
    if entry.get('many'):
        raise ApiError(409, 'more than one account answers to %s' % who)
    dn = str(entry.get('dn') or '')
    cn = cn_of(dn) if dn else ''
    upn = str(entry.get('upn') or '')
    sid = str(entry.get('sid') or '')
    mail = str(entry.get('mail') or '')
    role = admin_role_for(have, ad) or ''
    notes = []
    if not upn:
        notes.append(['bad', 'the account has no userPrincipalName - a certificate names its account by it; '
                             'nobody signs in with one of this account'])
    if not sid:
        notes.append(['bad' if str(CONFIG.get('admin_cert_map') or 'compat') == 'strong' else 'warn',
                      'the directory did not say the account\\'s SID (objectSid) - strong mapping needs it'])
    if entry_unusable(entry):
        notes.append(['warn', 'the account may not sign in now: %s' % entry_unusable(entry)])
    if not role:
        notes.append(['warn', 'none of the groups given a role here holds the account - a certificate of it '
                              'is taken, and nobody is signed in'])
    url = CERT_SID_URL + sid if sid else ''
    san = ['otherName: UPN = %s' % upn] if upn else []
    if url:
        san.append('URL = %s' % url)
    if mail:
        san.append('email = %s' % mail)
    inf = ['[Version]', 'Signature="$Windows NT$"', '', '[NewRequest]',
           'Subject = "CN=%s"' % cn.replace('"', '""'), 'KeySpec = 1', 'KeyLength = 2048', 'Exportable = FALSE',
           'MachineKeySet = FALSE', 'RequestType = PKCS10', 'KeyUsage = 0xA0',
           'ProviderName = "Microsoft Smart Card Key Storage Provider"', '', '[EnhancedKeyUsageExtension]',
           'OID = 1.3.6.1.5.5.7.3.2      ; Client Authentication',
           'OID = 1.3.6.1.4.1.311.20.2.2 ; Smart Card Logon', '', '[Extensions]',
           '2.5.29.17 = "{text}"']
    first = True
    for k, v in (('upn', upn), ('url', url), ('email', mail)):
        if v:
            inf.append('_continue_ = "%s=%s&"' % (k, v))
            first = False
    if first:
        inf.pop()
    ossl = ['[req]', 'prompt = no', 'distinguished_name = dn', 'req_extensions = ext', '', '[dn]',
            'CN = %s' % cn, '', '[ext]', 'keyUsage = critical, digitalSignature, keyEncipherment',
            'extendedKeyUsage = clientAuth, 1.3.6.1.4.1.311.20.2.2',
            'subjectAltName = ' + ', '.join(
                ([('otherName:1.3.6.1.4.1.311.20.2.3;UTF8:%s' % upn)] if upn else []) +
                ([('URI:%s' % url)] if url else []) + ([('email:%s' % mail)] if mail else []))]
    return {'directory': ad.name, 'name': entry.get('sam') or who, 'dn': dn, 'cn': cn,
            'display': entry.get('display') or '', 'upn': upn, 'sid': sid, 'mail': mail, 'url': url,
            'subject': 'CN=%s' % cn if cn else '', 'san': san, 'role': role,
            'groups': sorted({c for _, c in have}, key=str.lower)[:20],
            'map': str(CONFIG.get('admin_cert_map') or 'compat'),
            'disabled': bool(entry.get('disabled')), 'locked': bool(entry.get('locked')),
            'notes': notes, 'certreq': '\\r\\n'.join(inf) + '\\r\\n', 'openssl': '\\n'.join(ossl) + '\\n'}


@route('POST', '/api/auth/cert')''', 1)
open(P + '90c_certlogin_api.py', 'w').write(s)
print('1.0.282 server patched')

# Kerberos (1.0.282): the domain's NetBIOS name and DNS name read from AD (its crossRef in the configuration's
# Partitions), and which account holds each SPN - the guide's values are the directory's, never guessed
edit('60_engine.py', [(
"""    def domain_dn(self):""",
"""    def domain_names(self):
        \"\"\"The domain's own names as the forest's configuration says them (1.0.282): its NetBIOS name
        (nETBIOSName of its crossRef - MERIT_NT, not the first part of merit.cz) and its DNS name
        (dnsRoot). Kept ten minutes.\"\"\"
        with self.lock:
            got = self.cache.get(('domnames',))
            if got and time.time() - got[0] < 600:
                return got[1]

        def root(link):
            return link.search('', ldap_present('objectClass'), ('defaultNamingContext',
                                                                  'configurationNamingContext'), scope=0, limit=1)
        got = self.asked(root)
        a = {k.lower(): v for k, v in (got[0]['attrs'] if got else {}).items()}
        dom = self.domain_dn() or (a.get('defaultnamingcontext') or [''])[0]
        cfg = (a.get('configurationnamingcontext') or [''])[0]
        out = {'domain_dn': dom, 'netbios': '', 'dns': ''}
        if dom and cfg:
            rows = self.asked(lambda link: link.search(
                'CN=Partitions,' + cfg, ldap_and(ldap_equal('objectClass', 'crossRef'), ldap_equal('nCName', dom)),
                ('nETBIOSName', 'dnsRoot'), scope=1, limit=5))
            for r in rows:
                b = {k.lower(): v for k, v in r['attrs'].items()}
                out['netbios'] = out['netbios'] or (b.get('netbiosname') or [''])[0]
                out['dns'] = out['dns'] or (b.get('dnsroot') or [''])[0]
        self._cache_put(('domnames',), out)
        return out

    def spn_holders(self, spns):
        \"\"\"{spn: [sAMAccountName, ...]} - the accounts of the domain that hold each SPN (1.0.282).\"\"\"
        dom = self.domain_names().get('domain_dn') or self.base
        out = {}
        for spn in list(spns)[:20]:
            rows = self.asked(lambda link, s=spn: link.search(dom, ldap_equal('servicePrincipalName', s),
                                                              ('sAMAccountName',), scope=2, limit=5))
            out[spn] = [((r['attrs'].get('sAMAccountName') or [cn_of(r['dn'])])[0]) for r in rows]
        return out

    def domain_dn(self):""")])
edit('90g_kerberos_api.py', [(
"""@route('POST', '/api/kerberos')
def _kerberos_do(h):
    act = str(h.body().get('action') or '')""",
"""@route('POST', '/api/kerberos')
def _kerberos_do(h):
    act = str(h.body().get('action') or '')
    if act == 'ad':
        # The guide's values from the directory itself (1.0.282): the domain's NetBIOS name, its DNS
        # name (the realm), and the account holding each SPN - a guess of them was wrong where the
        # NetBIOS name is not the first part of the DNS one (MERIT_NT for merit.cz).
        h.me('fulladmin')
        ad = h.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
        if not ad:
            return {'ok': False, 'said': 'no directory is set for administrators'}
        names = [n['name'] for n in krb_view(h.store).get('names') or [] if n.get('name')]
        try:
            dn = ad.domain_names()
            holders = ad.spn_holders(['HTTP/' + n for n in names])
        except LdapError as e:
            return {'ok': False, 'directory': ad.name, 'said': 'the directory did not say: %s' % str(e)[:200]}
        return {'ok': True, 'directory': ad.name, 'netbios': dn.get('netbios') or '', 'dns': dn.get('dns') or '',
                'realm': (dn.get('dns') or '').upper(), 'spn': holders}""")])
print('kerberos AD names patched')
