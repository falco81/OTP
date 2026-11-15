

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
    # The certificate's fingerprint kept with the sign-in (1.0.285) - never the certificate: its card is
    # watched by it while admin_cert_card asks.
    return admin_signed_in(h, ok, how='certificate', extra={'card': cert_sha(pem)})


# ---- The card of a sign-in with a certificate (1.0.285) ------------------------------------
# A browser has no event for "the smart card was taken out"; the only sure sign is that the card can no
# longer sign. The open page loads a picture from the certificate's port every admin_cert_card_s seconds:
# a new TCP and TLS connection (no session kept, no keep-alive there while this is on), whose handshake
# only the card can sign. PHP hands the certificate that came ('' for none) and the session's cookie to
# /api/auth/card: the same fingerprint - the card is in; another - the session ends at once; none -
# signout: ends, grace: counted, ended past the grace. A handshake that fails reaches nothing here: the
# page then says so itself (/api/auth/cardgone). The state is kept in the sign-in's row of the database
# - either node of a cluster answers the check, a restart of the daemon forgets nothing - and the
# server holds a watched sign-in whose page stopped checking (card_due, on every question) until a check
# finds the card again.
CARD_ALLOWED = ('/api/auth/logout', '/api/auth/whoami', '/api/auth/card', '/api/auth/cardgone')


def cert_sha(pem):
    """The SHA-256 of a certificate's DER - '' when it is not one."""
    try:
        return hashlib.sha256(cert_der(pem)).hexdigest()
    except Exception:                                   # noqa: BLE001
        return ''


def card_mode():
    m = str(CONFIG.get('admin_cert_card') or 'off')
    return m if m in ('signout', 'grace') and CONFIG.get('admin_cert') else 'off'


def _card_int(key, lo, hi, dflt):
    try:
        return max(lo, min(hi, int(CONFIG.get(key) or dflt)))
    except (TypeError, ValueError):
        return dflt


def card_every():
    return _card_int('admin_cert_card_s', 5, 300, 15)


def card_grace():
    return _card_int('admin_cert_card_grace_s', 5, 600, 30)


def card_late():
    """How late a check may be: a tab in the background is let check about once a minute."""
    return max(3 * card_every(), 150)


def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card'))


def card_conf(state):
    """What the page is to do: None, or {mode, every, grace, port, out}."""
    if not state:
        return None
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(),
            'port': int(CONFIG.get('admin_cert_port') or 8443), 'out': state == 'out', 'stale': state == 'stale'}


def card_end(h, s, why):
    """The watched sign-in `s` ended, said in the events with why."""
    who = s.get('name') or 'somebody'
    h.store.db.run('DELETE FROM sessions WHERE id = ?', (s['id'],))
    h.store.add_event('sign-ins', '%s was signed out: %s' % (who, why), 'warn', who=who)
    return 'gone'


def card_out(h, s, why):
    """No card: signout - the sign-in ends; grace - the time out is counted ('out'), past it 'gone'."""
    d = s['data']
    t = time.time()
    if card_mode() == 'signout':
        return card_end(h, s, why)
    if not d.get('card_out'):
        d['card_out'] = t
        h.store.session_merge(s['id'], {'card_out': t})
        h.store.add_event('sign-ins', '%s: the card they signed in with is out - the session waits %d s for it'
                          % (s.get('name') or '?', card_grace()), who=s.get('name') or '')
    if t - fnum(d['card_out']) >= card_grace():
        return card_end(h, s, 'the card they signed in with was not put back in time')
    return 'out'


def card_due(h, s):
    """The server's half, on every question of a sign-in: None (not watched), 'in', 'out' (grace) or
    'gone' (ended just now) - the card out longer than allowed, or its page no longer checking."""
    if not card_bound(s):
        return None
    d = s['data']
    t = time.time()
    seen = fnum(d.get('card_seen'))
    if not seen:
        # Watched from now (switched on after the sign-in was made, or its first question).
        d['card_seen'] = t
        h.store.session_merge(s['id'], {'card_seen': t})
        return 'in'
    grace = card_grace() if card_mode() == 'grace' else 0
    out = fnum(d.get('card_out'))
    if out and card_mode() == 'signout':
        return card_end(h, s, 'the card they signed in with was taken out')
    if out and t - out >= grace + card_late():
        return card_end(h, s, 'the card they signed in with was not put back in time')
    if out:
        return 'out'
    if t - seen >= card_late() + grace + max(card_every(), 30):
        # No check for long - a page asleep (a tablet's screen locked, the browser in the background
        # stops its pages) is not a card taken out: nothing of the session is answered until a check
        # finds the card again (the page checks the moment it wakes); a card not there then ends it.
        return 'stale'
    return 'in'


def _card_session(h):
    token = str(h.headers.get('X-Otp-Session') or '')
    if not token:
        return None
    # Not touched: a check is not somebody using the pages (the idle time goes on).
    return h.store.session_get(token, 'admin', int(CONFIG.get('session_idle_min') or 120) * 60, touch=False)


@route('POST', '/api/auth/card')
def _auth_card(h):
    """One check, from the certificate's port: {watched, alive, gone, grace_left}."""
    s = _card_session(h)
    if not s:
        return {'watched': False, 'alive': False, 'gone': True}
    if not card_bound(s):
        return {'watched': False, 'alive': True, 'gone': False}
    d = s['data']
    pem = str(h.body().get('cert') or '')
    fp = cert_sha(pem) if pem else ''
    if fp and fp != d.get('card'):
        card_end(h, s, 'another certificate than the one signed in with was offered (the card was changed)')
        return {'watched': True, 'alive': False, 'gone': True}
    if not fp:
        st = card_out(h, s, 'the card they signed in with was taken out')
        if st == 'gone':
            return {'watched': True, 'alive': False, 'gone': True}
        return {'watched': True, 'alive': False, 'gone': False,
                'grace_left': max(0, int(card_grace() - (time.time() - fnum(d.get('card_out')))))}
    st = card_due(h, s)
    if st == 'gone':
        return {'watched': True, 'alive': False, 'gone': True}
    t = time.time()
    ch = {}
    if d.get('card_out'):
        ch['card_out'] = None
        h.store.add_event('sign-ins', '%s: the card they signed in with is back' % s.get('name'), who=s.get('name') or '')
    if t - fnum(d.get('card_seen')) >= 20:
        ch['card_seen'] = t
    if ch:
        h.store.session_merge(s['id'], ch)
    return {'watched': True, 'alive': True, 'gone': False}


@route('POST', '/api/auth/cardgone')
def _auth_cardgone(h):
    """The page's picture got no answer at all, twice, while these pages answer: the handshake failed -
    nothing to sign it with. It only ever ends or holds its own sign-in."""
    s = _card_session(h)
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    if not card_bound(s):
        return {'watched': False, 'gone': False}
    st = card_out(h, s, 'the card they signed in with was taken out')
    return {'watched': True, 'gone': st == 'gone',
            'grace_left': max(0, int(card_grace() - (time.time() - fnum(s['data'].get('card_out')))))
            if st != 'gone' else 0}


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
