

# ---- Signing in with a client certificate on the pages (1.0.275) ----------------------------
def cert_who(h, pem):
    """(facts, said of the directory) of a client certificate - CertError when not taken."""
    f = cert_check(h.store, pem)
    upn = f['upn'][0]
    bad = name_letters_problem(upn.split('@', 1)[0])
    if bad:
        raise CertError('%s: %s' % (upn, bad))
    said = admin_ask_directory(h, upn, '', proven=True)
    if said is None:
        raise CertError('no directory is set for administrators')
    if said.get('ok'):
        mode = str(CONFIG.get('admin_cert_map') or 'compat')
        have = str(odict(said.get('entry')).get('sid') or '')
        if mode == 'strong' and not f['sid']:
            raise CertError('the certificate names no SID of its account (strong mapping, KB5014754) - '
                            'issued by an AD CS before May 2022, or from an offline template')
        if mode in ('strong', 'compat') and f['sid']:
            if not have:
                raise CertError('the directory did not say the SID of %s, and the certificate names one' % upn)
            if f['sid'].upper() != have.upper():
                raise CertError('the certificate is of another account: its SID is %s, %s\'s is %s'
                                % (f['sid'], upn, have))
    return f, said


CERT_SID_URL = 'tag:microsoft.com,2022-09-14:sid:'


def cert_request_values(h, name):
    """The values of a certificate request for one account of the directory set for administrators
    (1.0.282): read from the directory, nothing kept, nothing changed - and whether a certificate of
    them would sign in here."""
    name = name.strip()
    if not name or len(name) > 256:
        raise ApiError(400, 'which account? its sAMAccountName, DOMAIN\\name or its UPN')
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
                      'the directory did not say the account\'s SID (objectSid) - strong mapping needs it'])
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
            'notes': notes, 'certreq': '\r\n'.join(inf) + '\r\n', 'openssl': '\n'.join(ossl) + '\n'}


@route('POST', '/api/auth/cert')
def _auth_cert(h):
    """The page of the certificate's own port hands the browser's certificate here (nginx's
    $ssl_client_escaped_cert) - no sign-in yet."""
    if not CONFIG.get('admin_cert'):
        raise ApiError(404, 'signing in with a certificate is off')
    if not CONFIG.get('admin_directory'):
        raise ApiError(409, 'signing in with a certificate needs the directory of the administrators')
    tries = int(CONFIG.get('login_tries') or 5)
    key = h.throttle('certificate', tries * 4, int(CONFIG.get('login_wait_min') or 15),
                     ip_tries=max(50, tries * 10), what='refused certificates')
    pem = str(h.body().get('cert') or '')
    try:
        f, said = cert_who(h, pem)
    except CertError as e:
        h.failed(key)
        h.store.add_event('sign-ins', 'a sign-in with a certificate from %s was refused: %s'
                          % (h.client_ip(), e), 'warn')
        if isinstance(e, CrlRefused):
            # The person told little (1.0.280): which responder or CRL address of the inside network did
            # not answer, and openssl's words, are for the administrator - in the events.
            raise ApiError(401, 'the certificate cannot be checked for revocation (CRL, OCSP) just now - nobody '
                                'signs in with it until it can; an administrator sees why in the events',
                           extra={'code': 'certificate'})
        raise ApiError(401, str(e), extra={'code': 'certificate'})
    upn = f['upn'][0]
    tail = ' (serial %s, %s)' % (f['serial'], f['issuer'][:120])
    if not said.get('ok'):
        h.failed(key)
        h.store.add_event('sign-ins', '%s (a certificate) from %s was refused: %s%s' % (
            upn, h.client_ip(), said.get('said') or '?', tail), 'warn')
        raise ApiError(401, 'the directory does not let %s in: %s' % (upn, said.get('said') or '?'),
                       extra={'code': 'certificate'})
    if not said.get('role'):
        h.failed(key)
        h.store.add_event('sign-ins', '%s (a certificate) from %s: none of the groups given a role '
                          'here holds them%s' % (upn, h.client_ip(), tail), 'warn')
        raise ApiError(401, '%s is known, and none of the groups given a role here holds it' % upn,
                       extra={'code': 'certificate'})
    # The account by its sAMAccountName (as with a password or Kerberos): one person, one account,
    # whichever way they signed in first.
    entry = odict(said.get('entry'))
    name = str(entry.get('sam') or '') or upn
    local = h.store.account(name, checked=True)
    if local and local.get('source') != 'directory':
        h.failed(key)
        raise ApiError(401, '%s is an account of this server with a password of its own - a '
                       'certificate signs in only accounts of the directory' % name,
                       extra={'code': 'certificate'})
    try:
        ok = admin_from_directory(h, name, '', proven=True)
    except ApiError:
        h.failed(key)
        raise
    if ok and str(ok.get('dn') or '').lower() != str(entry.get('dn') or '').lower():
        h.failed(key)
        raise ApiError(401, '%s is not the same entry of the directory as %s' % (name, upn),
                       extra={'code': 'certificate'})
    if not ok or ok.get('disabled'):
        h.failed(key)
        raise ApiError(401, 'the account %s is switched off here' % upn, extra={'code': 'certificate'})
    h.store.add_event('sign-ins', '%s: the certificate %s%s' % (ok['name'], f['subject'][:160], tail),
                      who=ok['name'])
    return admin_signed_in(h, ok, how='certificate')


@route('GET', '/api/certlogin')
def _certlogin_view(h):
    h.me()
    out = cert_view(h.store)
    out['problems'] = cert_problems(h.store)
    return out


@route('POST', '/api/certlogin')
def _certlogin_do(h):
    b = h.body()
    act = str(b.get('action') or '')
    if act == 'check':
        # "Try my certificate": who it would sign in, and as what - nothing opened.
        h.me()
        try:
            f, said = cert_who(h, str(b.get('cert') or ''))
        except CertError as e:
            return {'ok': False, 'said': str(e)}
        upn = f['upn'][0]
        if not said.get('ok'):
            return {'ok': False, 'upn': upn, 'said': said.get('said') or '?'}
        return {'ok': bool(said.get('role')), 'upn': upn, 'name': said.get('name'),
                'role': said.get('role') or '', 'subject': f['subject'], 'issuer': f['issuer'],
                'serial': f['serial'], 'not_after': f['not_after'], 'sid': f['sid'],
                'said': '' if said.get('role') else 'none of the groups given a role here holds it',
                'mfa': bool(CONFIG.get('admin_2fa'))}
    s = h.me('fulladmin')
    if act in ('crl_fetch', 'crl_clear'):
        # Fetch now / Clear (1.0.278): asked of every node, each does it itself.
        try:
            asked = crl_ask(h.d, act[4:], b.get('url'), s['name'])
        except ValueError as e:
            raise ApiError(404, str(e))
        return dict(asked, message=('every node fetches the CRLs again' if act == 'crl_fetch'
                                    else 'the CRLs are cleared on every node'))
    if act in ('ocsp_fetch', 'ocsp_clear'):
        # Ask again / Clear of the OCSP answers (1.0.279): asked of every node, each does it itself.
        try:
            asked = ocsp_ask_all(h.d, act[5:], b.get('url'), s['name'])
        except ValueError as e:
            raise ApiError(404, str(e))
        return dict(asked, message=('every responder is asked again' if act == 'ocsp_fetch'
                                    else 'the OCSP answers are cleared on every node'))
    if act == 'result':
        ident = str(b.get('id') or '')
        got = {}
        for kind in ('crl_fetch', 'crl_clear', 'ocsp_fetch', 'ocsp_clear'):
            for n, v in node_ask_results(h.store, kind, ident).items():
                got[n] = got.get(n) or v
        return {'nodes': got}
    if act == 'request':
        # What a certificate request of an account needs (1.0.282): its subject, the UPN and the SID
        # of the SAN - as AD CS writes them, and certreq's and openssl's words for them.
        return cert_request_values(h, str(b.get('name') or ''))
    if act == 'ca_add':
        try:
            raw = base64.b64decode(str(b.get('data') or ''), validate=True)
        except (ValueError, binascii.Error):
            raise ApiError(400, 'the file did not arrive whole (not base64)')
        try:
            added = cert_ca_add(h.store, raw, s['name'])
        except (ValueError, CertError) as e:
            raise ApiError(400, str(e))
        try:
            cert_tick(h.store)
        except Exception:                               # noqa: BLE001
            pass
        out = cert_view(h.store)
        out['problems'] = cert_problems(h.store)
        out['message'] = ('%d authority(ies) put in' % len(added)) if added else 'every one of them was in already'
        return out
    if act == 'ca_drop':
        why = signin_last_way(h.store, 'authority')
        if why:
            raise ApiError(400, why)
        try:
            cert_ca_drop(h.store, b.get('sha256'), s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
        try:
            cert_tick(h.store)
        except Exception:                               # noqa: BLE001
            pass
        out = cert_view(h.store)
        out['problems'] = cert_problems(h.store)
        out['message'] = 'the authority is taken away'
        return out
    raise ApiError(400, 'no such action')
