
# ---- signed in by the load balancer or WAF in front (1.0.239) ----------------------------------
# A NetScaler (nFactor / LDAP), an F5 APM or another balancer signs people in against the
# directory before the enrolment pages are shown; who it signed in comes in a header of its own,
# with a key only the balancer has (X-Otp-Sso-Key), on a connection from the balancer's own
# address - nginx's $realip_remote_addr, which the page passes on as X-Otp-Peer, never the
# client's address from X-Forwarded-For. Everything after the password is as it was: the
# directory is asked who it is, the realm's groups and who may enrol decide, the one-time code
# before the first token is sent. Off by default; the administration pages are not concerned.

SSO_KEY_HEADER = 'X-Otp-Sso-Key'
SSO_NOTED = {'at': 0.0, 'what': None}


def sso_nets(conf=None):
    out = []
    for w in re.split(r'[\s,;]+', str((conf or CONFIG).get('portal_sso_from') or '')):
        if not w:
            continue
        try:
            out.append(ipaddress.ip_network(w, strict=False))
        except ValueError:
            continue
    return out


def sso_peer_ok(peer):
    try:
        a = ipaddress.ip_address(str(peer or '').strip().split('%')[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return any(a in n for n in sso_nets() if n.version == a.version)


def sso_note(h, ok, why, peer, name):
    """The last sign-in by the balancer this node saw - for "Check it" on the administration
    pages. A refusal always; one that went well at most once a minute (a write on every page)."""
    what = (bool(ok), str(why)[:200], str(peer)[:64], str(name)[:120])
    t = time.time()
    if ok and SSO_NOTED['what'] == what and t - SSO_NOTED['at'] < 60:
        return
    SSO_NOTED.update(at=t, what=what)
    rec = {'at': t, 'ok': bool(ok), 'why': what[1], 'peer': what[2], 'name': what[3],
           'client': h.client_ip(), 'node': node_name()}
    try:
        # The last that went well and the last refused, each its own (a refusal hid the sign-ins).
        h.store.set_meta('portal_sso:last:%s:%s' % (node_name(), 'ok' if ok else 'refused'),
                         json.dumps(rec))
    except Exception as e:                                  # noqa: BLE001
        log('the last sign-in by the load balancer could not be noted: %s' % e, 'warn')


def sso_refuse(h, peer, name, why, code=401, said=None):
    """Refused - in the events with the reason, to the page in general words."""
    sso_note(h, False, why, peer, name)
    log_sparing('sso-refused:' + why[:40], 'the enrolment pages refused a sign-in by the load '
                'balancer from %s (%s): %s' % (peer or '?', name or '?', why), 'warn', every=300)
    h.store.add_event('enrolment', 'a sign-in by the load balancer was refused (from %s, for %s): '
                      '%s' % (peer or '?', name or '?', why), 'warn', who=name or None)
    raise ApiError(code, said or 'the sign-in through the load balancer was not taken here - '
                                 'sign in with your password, or ask the administrator')


@route('POST', '/api/portal/sso')
def _portal_sso(h):
    if not CONFIG.get('portal'):
        raise ApiError(403, 'enrolling a token here is switched off')
    if not CONFIG.get('portal_sso'):
        raise ApiError(404, 'signing in through the load balancer is switched off')
    b = h.body()
    name = str(b.get('name') or '').strip()
    given = str(b.get('key') or '')
    peer = str(h.headers.get('X-Otp-Peer') or '').strip()
    # Counted per address and per name as the sign-in is - more loosely per address: without
    # "Behind a load balancer" every client is the balancer's address.
    tries = int(CONFIG.get('portal_tries') or 5)
    key = h.throttle('portal-sso', tries, int(CONFIG.get('portal_wait_min') or 15), name=name,
                     ip_tries=max(50, tries * 10), what='refused sign-ins by the load balancer')
    if not peer:
        h.failed(key)
        sso_refuse(h, peer, name, 'nginx does not say which machine the request came from '
                   '(OTP_PEER) - the node\'s nginx has not been set up for it yet', 503)
    if not sso_peer_ok(peer):
        h.failed(key)
        sso_refuse(h, peer, name, 'not from the balancers named (%s)'
                   % (CONFIG.get('portal_sso_from') or 'none'))
    want = unseal_secret(str(CONFIG.get('portal_sso_key') or '')) or ''
    if not want:
        sso_refuse(h, peer, name, 'no key is set (Make a key)', 503)
    if not hmac.compare_digest(given.encode('utf-8', 'replace'), want.encode('utf-8', 'replace')):
        h.failed(key)
        sso_refuse(h, peer, name, 'the key in %s is %s' % (SSO_KEY_HEADER,
                                                           'not the one set' if given else 'not there'))
    if not name or len(name) > 256 or re.search(r'[\x00-\x1f\x7f]', name):
        h.failed(key)
        sso_refuse(h, peer, name[:60], 'no name in %s' % (CONFIG.get('portal_sso_header') or
                                                         'X-Otp-User'))
    full = Authenticator.full_name(name, CONFIG.get('portal_realm') or
                                   CONFIG.get('default_realm') or '')
    # Signed in already, as the same person by the balancer: the same session goes on.
    s = h.session('portal')
    if s:
        data = s.get('data') or {}
        if data.get('sso') and str(data.get('login') or '').lower() == str(full or '').lower():
            return {'same': True, 'name': s['name']}
        # Somebody else now (a shared machine), or signed in with a password before: that one ends.
        h.store.session_end(h.headers.get('X-Otp-Session'))
    if full and name_letters_problem(full):
        h.failed(key)
        sso_refuse(h, peer, full, 'the name has letters this server does not take', 400,
                   'that name has letters this server does not take (accents or another '
                   'language) - ask the administrator')
    realm = h.store.realm_for(full) if full else None
    if not realm or not realm.get('directory'):
        h.failed(key)
        sso_refuse(h, peer, full, 'no realm with a directory for that name')
    ad = h.d.auth.directory(realm['directory'])
    if not ad:
        raise ApiError(503, 'the directory of this realm is not set up')
    how = realm.get('lookup') if realm.get('lookup') in ('upn', 'sam') else (
        'upn' if '@' in full else 'sam')
    try:
        entry = Authenticator.find_person(ad, full, how, realm)
        if not entry:
            raise LdapError('there is no such account')
        if entry.get('many'):
            raise LdapError('more than one account answers to that name')
        if entry_unusable(entry):
            raise LdapError('the account may not sign in: %s' % entry_unusable(entry))
    except LdapUnreachable as e:
        log('the enrolment pages could not reach the directory: %s' % e, 'warn')
        raise ApiError(503, 'the directory cannot be reached just now')
    except LdapError as e:
        h.failed(key)
        sso_refuse(h, peer, full, 'the directory: %s' % e)
    try:
        got = portal_open(h, full, realm, ad, entry, key, str(b.get('lang') or ''), sso=True)
    except ApiError as e:
        sso_note(h, False, str(e), peer, full)
        raise
    sso_note(h, True, '', peer, full)
    return got


def sso_view(store):
    """What the card on the administration pages shows: set or not, and the last sign-in by the
    balancer each node saw."""
    last = []
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'portal_sso:last:%'"):
        try:
            rec = json.loads(r['v'])
        except (TypeError, ValueError):
            continue
        if isinstance(rec, dict):
            last.append({k: rec.get(k) for k in ('at', 'ok', 'why', 'peer', 'name', 'client',
                                                 'node')})
    last.sort(key=lambda x: -float(x.get('at') or 0))
    return {'on': bool(CONFIG.get('portal_sso')), 'portal': bool(CONFIG.get('portal')),
            'key_set': bool(unseal_secret(str(CONFIG.get('portal_sso_key') or ''))),
            'from': [str(n) for n in sso_nets()],
            'header': CONFIG.get('portal_sso_header') or 'X-Otp-User',
            'key_header': SSO_KEY_HEADER, 'logout': CONFIG.get('portal_sso_logout') or '',
            'web_proxy': bool(CONFIG.get('web_proxy')),
            'web_proxy_from': str(CONFIG.get('web_proxy_from') or ''),
            'web_proxy_header': CONFIG.get('web_proxy_header') or 'X-Forwarded-For',
            'site': CONFIG.get('site_name') or short_host(), 'last': last[:8]}


@route('GET', '/api/portal-sso')
def _portal_sso_view(h):
    h.me('readonly')
    return sso_view(h.store)


@route('POST', '/api/portal-sso')
def _portal_sso_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    if act == 'key':
        tok = secrets.token_urlsafe(32)
        h.d.save_settings({'portal_sso_key': tok}, by=s['name'])
        h.store.add_event('settings', '%s made a new key for the sign-in by the load balancer - '
                          'the one before is no longer taken' % s['name'], 'warn', who=s['name'])
        return {'key': tok, 'view': sso_view(h.store)}
    if act == 'forget':
        h.store.db.run("DELETE FROM meta WHERE k LIKE 'portal_sso:last:%'")
        return {'view': sso_view(h.store)}
    raise ApiError(400, 'no such thing to do')
