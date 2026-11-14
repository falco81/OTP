

# ---- Signing in with Windows (Kerberos) on the pages (1.0.274) ----------------------------
def _krb_token_of(b):
    raw = str(b.get('token') or '').strip()
    if raw.lower().startswith('negotiate '):
        raw = raw[10:].strip()
    if not raw:
        raise KrbError('the browser sent no ticket')
    if len(raw) > KRB_TOKEN_MAX * 2:
        raise KrbError('the ticket is larger than any Kerberos ticket')
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        raise KrbError('the ticket is not base64')


def krb_who(h, token):
    """(principal, user, said of the directory) of a ticket - raises KrbError or ApiError."""
    principal = krb_accept(token)
    user, realm = krb_principal_split(principal)
    want = krb_realm_wanted(h.store)
    if not want:
        raise KrbError('the realm whose people may sign in is not known - set Kerberos realm')
    if realm != want:
        raise KrbError('%s is of the realm %s, and only %s signs in here' % (principal, realm, want))
    bad = name_letters_problem(user)
    if bad:
        raise KrbError('%s: %s' % (principal, bad))
    said = admin_ask_directory(h, user, '', proven=True)
    return principal, user, said


@route('POST', '/api/auth/kerberos')
def _auth_kerberos(h):
    """The pages hand the browser's "Authorization: Negotiate" here (no sign-in yet)."""
    if not CONFIG.get('admin_kerberos'):
        raise ApiError(404, 'signing in with Kerberos is off')
    if not CONFIG.get('admin_directory'):
        raise ApiError(409, 'signing in with Kerberos needs the directory of the administrators')
    tries = int(CONFIG.get('login_tries') or 5)
    key = h.throttle('kerberos', tries * 4, int(CONFIG.get('login_wait_min') or 15),
                     ip_tries=max(50, tries * 10), what='refused tickets')
    b = h.body()
    try:
        token = _krb_token_of(b)
        principal, user, said = krb_who(h, token)
    except KrbError as e:
        h.failed(key)
        h.store.add_event('sign-ins', 'a Kerberos sign-in from %s was refused: %s' % (h.client_ip(), e),
                          'warn')
        raise ApiError(401, str(e), extra={'code': 'kerberos'})
    if said is None:
        raise ApiError(409, 'signing in with Kerberos needs the directory of the administrators')
    # Once in the whole cluster: the library's replay cache is this node's own, and the same
    # ticket handed to the other node (behind the VIP address, after it moved) was taken there.
    if not once_take(h.store, 'krb', principal, hashlib.sha256(token).hexdigest()):
        h.failed(key)
        h.store.add_event('sign-ins', 'a Kerberos ticket of %s from %s was used already' % (
            principal, h.client_ip()), 'warn')
        raise ApiError(401, 'this ticket was used already (a replay?)', extra={'code': 'kerberos'})
    acc = h.store.account(user, checked=True)
    if acc and acc.get('source') != 'directory':
        h.failed(key)
        h.store.add_event('sign-ins', '%s (Kerberos) from %s was refused: %s is an account of '
                          'this server - it signs in with its password' % (principal, h.client_ip(), user),
                          'warn')
        raise ApiError(401, '%s is an account of this server with a password of its own - Kerberos '
                       'signs in only accounts of the directory' % user, extra={'code': 'kerberos'})
    if not said.get('ok'):
        h.failed(key)
        h.store.add_event('sign-ins', '%s (Kerberos) from %s was refused: %s' % (
            principal, h.client_ip(), said.get('said') or '?'), 'warn')
        raise ApiError(401, 'the directory does not let %s in: %s' % (user, said.get('said') or '?'),
                       extra={'code': 'kerberos'})
    if not said.get('role'):
        h.failed(key)
        h.store.add_event('sign-ins', '%s (Kerberos) from %s: none of the groups given a role here '
                          'holds them' % (principal, h.client_ip()), 'warn')
        raise ApiError(401, '%s is known, and none of the groups given a role here holds it' % principal,
                       extra={'code': 'kerberos'})
    try:
        ok = admin_from_directory(h, user, '', proven=True)
    except ApiError:
        h.failed(key)
        raise
    if not ok or ok.get('disabled'):
        h.failed(key)
        h.store.add_event('sign-ins', '%s (Kerberos) from %s was refused: the account is switched off'
                          % (principal, h.client_ip()), 'warn')
        raise ApiError(401, 'the account %s is switched off here' % user, extra={'code': 'kerberos'})
    return admin_signed_in(h, ok, how='Kerberos')


@route('GET', '/api/kerberos')
def _kerberos_view(h):
    h.me()
    out = krb_view(h.store)
    out['problems'] = krb_problems(h.store)
    return out


@route('POST', '/api/kerberos')
def _kerberos_do(h):
    act = str(h.body().get('action') or '')
    if act == 'check':
        # "Try my browser's ticket": who it would sign in, and as what - nothing opened.
        h.me()
        try:
            principal, user, said = krb_who(h, _krb_token_of(h.body()))
        except KrbError as e:
            return {'ok': False, 'said': str(e)}
        if said is None:
            return {'ok': False, 'said': 'no directory is set for administrators'}
        acc = h.store.account(user, checked=True)
        if acc and acc.get('source') != 'directory':
            return {'ok': False, 'principal': principal,
                    'said': '%s is an account of this server - it signs in with its password' % user}
        if not said.get('ok'):
            return {'ok': False, 'principal': principal, 'said': said.get('said') or '?'}
        return {'ok': bool(said.get('role')), 'principal': principal, 'name': user,
                'role': said.get('role') or '', 'groups': said.get('groups') or [],
                'said': '' if said.get('role') else 'none of the groups given a role here holds it',
                'mfa': bool(CONFIG.get('admin_2fa'))}
    s = h.me('fulladmin')
    if act == 'keytab':
        raw = str(h.body().get('data') or '')
        try:
            data = base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error):
            raise ApiError(400, 'the file did not arrive whole (not base64)')
        try:
            ents = krb_keytab_put(h.store, data, s['name'])
        except ValueError as e:
            raise ApiError(400, str(e))
        try:
            krb_tick(h.store)
        except Exception:                               # noqa: BLE001
            pass
        out = krb_view(h.store)
        out['problems'] = krb_problems(h.store)
        out['message'] = 'the keytab is put in: %d key(s)%s' % (
            len(ents), ' - each node writes it out within a few seconds'
            if CONFIG.get('ha_mode') == 'replicated' else '')
        return out
    if act == 'drop':
        krb_keytab_drop(h.store, s['name'])
        try:
            krb_tick(h.store)
        except Exception:                               # noqa: BLE001
            pass
        out = krb_view(h.store)
        out['problems'] = krb_problems(h.store)
        out['message'] = 'the keytab is taken away'
        return out
    raise ApiError(400, 'no such action')
