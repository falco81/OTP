

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
