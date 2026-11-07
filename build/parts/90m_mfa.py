# ---- a second step for the administration (1.0.125) ---------------------------------
# With admin_2fa on, a password right for these pages opens a sign-in that can
# do nothing yet but its second step (MFA_ALLOWED): a code from an app, or one
# sent by mail or SMS. The first time the account chooses how and proves it
# (enrol); after that it gives the code each time (check). The way chosen is
# the account's own - not a VPN token - kept in meta 'adm2fa:<name>':
#   {'kind': 'app'|'mail'|'sms'|'passkey', 'secret': sealed (app), 'dest': (mail/sms),
#    'keys': [the passkeys' public halves] (passkey, 1.0.254: 90w_webauthn.py),
#    'at', 'step': the last app code's step, used once}
# Accounts → Reset the second step and otp --reset-2fa NAME take it away.
MFA_ALLOWED = ('/api/auth/mfa', '/api/auth/logout', '/api/auth/whoami')
MFA_SEND_GAP_S = 30
MFA_SEND_MOST = 5
MFA_WRONG_MOST = 5          # wrong second-step codes of one sign-in, then the password again (1.0.252)
MFA_LOCK = threading.Lock()
# With the guard on (1.0.255): the account's second step in the database not as otp wrote it.
MFA_BLOCKED_WORDS = ('the second step of this account in the database was not written by otp - '
                     'nothing can be set up over it: another full administrator resets it '
                     '(Accounts), or root with  otp --reset-2fa %s')


def mfa_key(name):
    return 'adm2fa:' + str(name or '').strip().lower()


def mfa_get(store, name):
    try:
        got = json.loads(store.get_meta(mfa_key(name)) or 'null')
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


def mfa_all(store):
    out = {}
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'adm2fa:%'"):
        v = json_obj(r['v'])
        if v is None:
            continue
        dest = dest_masked(v.get('kind'), v.get('dest')) if v.get('kind') in ('mail', 'sms') else ''
        if v.get('kind') == 'passkey':
            # which device, for which name of the pages (1.0.254)
            dest = ', '.join('%s · %s' % (k.get('name') or 'a device', k.get('host') or '?')
                             for k in v.get('keys') or [] if isinstance(k, dict))
        out[r['k'][len('adm2fa:'):]] = {'kind': v.get('kind'), 'at': v.get('at'), 'dest': dest}
    return out


def mfa_reset(store, name, by):
    had = mfa_get(store, name)
    store.drop_meta(mfa_key(name))
    store.add_event('accounts', '%s reset the second step of signing in of %s%s' % (
        by, name, ' (it was %s)' % MFA_KIND_WORDS.get(had.get('kind'), had.get('kind'))
        if had else ' (none was set up)'), 'warn', who=by)
    return bool(had)


MFA_KIND_WORDS = {'app': 'an authenticator app', 'mail': 'a code by e-mail',
                  'sms': 'a code by SMS', 'passkey': 'a passkey (Face ID, Touch ID, Windows Hello)'}
MFA_KINDS = ('app', 'mail', 'sms', 'passkey')


def mfa_lang(h):
    """The language of the page the code was asked from - its cookie - or
    the codes' own."""
    got = str(h.headers.get('X-Otp-Lang') or '')
    if not got:
        m = re.search(r'(?:^|;\s*)otp_lang=([a-z]{2})', str(h.headers.get('Cookie') or ''))
        got = m.group(1) if m else ''
    return got if got in CODE_TEXTS else None


def mfa_methods(h=None):
    """The ways offered when an account sets up its second step. A passkey (1.0.254) only
    where it can be: the pages opened by a name (asked from a page: h)."""
    out = []
    ch = code_channels()
    if CONFIG.get('admin_2fa_app', 1):
        out.append('app')
    if CONFIG.get('admin_2fa_mail', 1) and 'mail' in ch:
        out.append('mail')
    if CONFIG.get('admin_2fa_sms', 1) and 'sms' in ch:
        out.append('sms')
    if CONFIG.get('admin_2fa_passkey') and (h is None or wa_host_ok(h)) and \
            not (h is not None and mfa_old_nodes(h.store)):
        out.append('passkey')
    return out or ['app']


def mfa_old_nodes(store):
    """The other nodes of the cluster on a version that does not know a passkey (before
    1.0.254), heard from in the last day: there an account with a passkey reads as one that has
    not set up its second step, and the password alone would set up another. No passkey is set
    up while one is."""
    if not CONFIG.get('ha_mode'):
        return []
    try:
        return [n['name'] for n in ha_nodes(store) if not n.get('me') and fnum(n.get('age')) < 86400
                and _ver_tuple(n.get('version')) < (1, 0, 254)]
    except Exception:                                   # noqa: BLE001
        return []


def mfa_stage(store, name):
    rec = mfa_get(store, name)
    if rec and rec.get('kind') in MFA_KINDS:
        # A way switched off since is still the account's, and the only one
        # (1.0.136): mail or SMS that can no longer be sent was set up anew
        # - by whoever had the password. Now that waits for a reset (the
        # accounts page, or otp --reset-2fa NAME as root).
        return 'check'
    # With the guard on (1.0.255): a way set up and then taken away, or changed, by somebody who
    # could write the database read as none - and the password alone set up one of theirs. Held
    # until it is reset (the accounts page, or otp --reset-2fa NAME), as a way switched off is.
    if dbguard_meta_gone(store.db, mfa_key(name)):
        return 'blocked'
    return 'enrol'


def mfa_pending(s, store=None):
    """The sign-in's second step, if it is still to be done."""
    if not CONFIG.get('admin_2fa'):
        return ''
    data = (s or {}).get('data') or {}
    if data.get('mfa'):
        return str(data['mfa'])
    # Opened with the password alone while the second step was off (1.0.255): when it is on, the
    # step is still to be given - on either node, whenever it learns it is on. The sign-ins ended as
    # it was switched on were only those the database had then: one opened on the other node
    # before it had read the settings again stayed whole.
    if data.get('mfa_off') and not data.get('mfa_ok'):
        try:
            return mfa_stage(store, s['name']) if store is not None else 'check'
        except Exception:                               # noqa: BLE001
            return 'check'
    return ''


def _mfa_session(h):
    s = h.session('admin')
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    acc = h.store.account(s['name'], checked=True)
    if not acc or acc.get('disabled'):
        raise ApiError(401, 'that account may no longer sign in')
    return s, acc


def _mfa_code_ok(saved, code):
    if not saved or time.time() > fnum(saved.get('exp')):
        return False
    return hmac.compare_digest(code_hash(saved.get('salt') or '', str(code or '').strip()),
                               str(saved.get('hash') or ''))


def _mfa_wrong(h, s, key, words):
    """A wrong second-step code (1.0.252): counted on the address and the name as before, and on
    this sign-in - at the fifth its password is asked again. Only the throttle held in memory
    counted: a sign-in with the password could go on guessing, on each node."""
    h.failed(key)
    n = h.store.session_bump(s['id'], 'mfa_wrong')
    if not n or n >= MFA_WRONG_MOST:
        h.store.session_drop(s['id'])
        h.store.add_event('accounts', '%s: %d wrong codes of the second step - the sign-in was '
                          'ended, the password is asked again' % (s['name'], MFA_WRONG_MOST),
                          'warn', who=s['name'])
        raise ApiError(401, 'too many wrong codes - sign in again')
    raise ApiError(400, words)


def mfa_send_state(data, field='mfa_code', now=None):
    """Where the codes of this sign-in stand (1.0.259), for the page's countdown: how many went,
    how many more may, in how many seconds the next one may, how long the last one is good for.
    Seconds from now, not times: the node's clock and the browser's need not agree."""
    data = data or {}
    t = time.time() if now is None else now
    at = fnum(data.get('mfa_sent_at'))
    n = int(data.get('mfa_sent') or 0)
    left = max(0, MFA_SEND_MOST - n)
    # Clamped to the gap: the other node's clock a little ahead is not a longer wait.
    wait = min(MFA_SEND_GAP_S, max(0, int(math.ceil(MFA_SEND_GAP_S - (t - at))))) if at else 0
    saved = data.get(field) or {}
    ttl = int(CONFIG.get('code_ttl_s') or 300)
    code_left = max(0, min(ttl, int(fnum(saved.get('exp')) - t))) if saved.get('exp') else 0
    return {'sent': n, 'most': MFA_SEND_MOST, 'left': left, 'gap_s': MFA_SEND_GAP_S,
            'wait_s': wait if left else 0, 'can': bool(left and not wait),
            'why': 'most' if not left else ('gap' if wait else ''),
            'code_left_s': code_left, 'code_ttl_s': ttl, 'auto': not at}


def mfa_wait_words(wait):
    return 'a code went a moment ago - another in %d s' % max(1, int(wait))


def _mfa_send(h, s, kind, dest, field):
    data = s.get('data') or {}
    t = time.time()
    st = mfa_send_state(data, field, t)
    if st['why'] == 'gap':
        raise ApiError(429, mfa_wait_words(st['wait_s']), extra={'send': st})
    n = int(data.get('mfa_sent') or 0)
    if n >= MFA_SEND_MOST:
        raise ApiError(429, 'that is %d codes for this sign-in: sign in again for more'
                       % MFA_SEND_MOST, extra={'send': st})
    # The place taken before the code goes (1.0.255), only while nobody else took it since this
    # request read the sign-in: requests at once - on one node or both - each sent a code, past
    # the gap and the most.
    was = {'mfa_sent_at': data.get('mfa_sent_at'), 'mfa_sent': data.get('mfa_sent')}
    took = h.store.session_merge(s['id'], {'mfa_sent_at': t, 'mfa_sent': n + 1}, expect=was)
    if took is None:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    if took is False:
        # Another request took the place a moment ago (a second tab, the other node).
        st = mfa_send_state({'mfa_sent_at': t, 'mfa_sent': n + 1}, field, t)
        raise ApiError(429, mfa_wait_words(st['wait_s']), extra={'send': st})
    code, salt = code_new(), secrets.token_hex(8)
    saved = {'hash': code_hash(salt, code), 'salt': salt,
             't': t, 'exp': t + int(CONFIG.get('code_ttl_s') or 300)}
    try:
        acc = h.store.account(s['name']) or {}
        said = code_send(h.store, kind, dest, code, purpose='admin_verify' if field == 'mfa_new'
                         else 'admin', name=s['name'], display=acc.get('display') or '',
                         lang=mfa_lang(h))
    except (MailError, SmsError, ValueError) as e:
        # The place given back (1.0.255): nothing went, so nothing is counted - as until now.
        try:
            h.store.session_merge(s['id'], was, expect={'mfa_sent_at': t, 'mfa_sent': n + 1})
        except Exception:                               # noqa: BLE001
            pass
        h.store.add_event('sign-ins', 'the code of the second step for %s could not be sent '
                          '(%s): %s' % (s['name'], kind, e), 'warn', who=s['name'])
        raise ApiError(502, 'the code could not be sent: %s' % e)
    # Kept only once it went: a refused one leaves the last code good.
    new = dict(saved, kind=kind, dest=dest) if field == 'mfa_new' else saved
    h.store.session_merge(s['id'], {field: new})
    log('the second step of %s: a code sent by %s to %s (%s)' % (
        s['name'], kind, dest_masked(kind, dest), said))
    # Where they stand now (1.0.259): this one counted, its time the gap's start.
    h._mfa_send_st = mfa_send_state(dict(data, mfa_sent_at=t, mfa_sent=n + 1, **{field: saved}),
                                    field, t)
    return dest_masked(kind, dest)


def _mfa_done(h, s, how):
    """The second step given: a sign-in of its own from here on (1.0.149) - the
    one the password alone opened is ended, not made whole: whoever had seen
    its cookie had the pages once the code was given."""
    data = {k: v for k, v in odict(s.get('data')).items()
            if k not in ('mfa', 'mfa_new', 'mfa_code', 'mfa_sent_at', 'mfa_sent', 'mfa_off')}
    # Marked as one past the second step (1.0.255; signed with the guard on): a sign-in without
    # the mark, opened while the step was off, gives it once it is on.
    data['mfa_ok'] = 1
    data['mfa_at'] = int(time.time())       # 1.0.262: a passkey is added only soon after this
    hours = max(0.05, (fnum(s.get('expires')) - time.time()) / 3600.0)
    token = h.store.session_new('admin', s['name'], s['role'], h.client_ip(), hours, data=data)
    h.store.session_drop(s['id'])
    h.store.add_event('sign-ins', '%s gave the second step (%s) from %s' % (
        s['name'], how, h.client_ip()), who=s['name'])
    return token


@route('GET', '/api/auth/mfa')
def _mfa(h):
    s, acc = _mfa_session(h)
    stage = mfa_pending(s, h.store)
    rec = mfa_get(h.store, s['name']) or {}
    new = odict(s.get('data')).get('mfa_new') or {}
    return {'name': acc['name'], 'display': acc.get('display') or '', 'stage': stage,
            'methods': mfa_methods(h), 'kind': rec.get('kind') if stage == 'check' else '',
            'hosts': sorted(set(k.get('host') for k in rec.get('keys') or [])) if stage == 'check' else [],
            'dest': dest_masked(rec.get('kind'), rec.get('dest')) if stage == 'check' else '',
            'started': {'kind': new.get('kind'),
                        'dest': dest_masked(new.get('kind'), new.get('dest'))} if new else None,
            'digits': 6 if (stage == 'check' and rec.get('kind') == 'app') else
            int(CONFIG.get('code_digits') or 6),
            # Why nothing can be set up (1.0.255), with the guard on.
            'blocked': MFA_BLOCKED_WORDS % acc['name'] if stage == 'blocked' else '',
            # The codes sent in this sign-in (1.0.259): the countdown, how many more, the first
            # one sent by itself once.
            'send': mfa_send_state(odict(s.get('data')), 'mfa_code' if stage == 'check' else 'mfa_new')
            if (stage == 'check' and rec.get('kind') in ('mail', 'sms')) or stage == 'enrol' else None}


@route('POST', '/api/auth/mfa')
def _mfa_do(h):
    s, acc = _mfa_session(h)
    stage = mfa_pending(s, h.store)
    if not stage:
        raise ApiError(409, 'this sign-in has no second step to give')
    if stage == 'blocked' or (stage == 'enrol' and mfa_stage(h.store, acc['name']) == 'blocked'):
        # Nothing set up over it (1.0.255): the way kept in the database is not otp's word.
        raise ApiError(409, MFA_BLOCKED_WORDS % acc['name'])
    b = h.body()
    act = b.get('action')
    name = acc['name']
    data = s.get('data') or {}
    # The account as it is now, not as it was at this sign-in (1.0.139): a
    # sign-in kept waiting from before the second step was set up could set
    # up its own, over the one in use.
    if act in ('enrol_start', 'enrol_confirm') and stage == 'enrol' and \
            mfa_stage(h.store, name) != 'enrol':
        raise ApiError(409, 'this account has its second step set up already - sign in again')
    if act == 'enrol_start':
        if stage != 'enrol':
            raise ApiError(409, 'this account has its second step set up already')
        kind = str(b.get('kind') or '')
        if kind == 'passkey' and mfa_old_nodes(h.store):
            raise ApiError(409, 'a passkey waits until every node runs otp 1.0.254 or newer (%s does '
                                'not yet)' % ', '.join(mfa_old_nodes(h.store)))
        if kind not in mfa_methods(h):
            raise ApiError(400, 'that way is not offered here')
        if kind == 'passkey':
            # The question for the device (1.0.254): kept with this sign-in, so either node
            # takes the answer.
            try:
                saved, opts = wa_register_options(h, name, acc.get('display') or '')
            except ValueError as e:
                raise ApiError(400, str(e))
            h.store.session_merge(s['id'], {'mfa_new': dict(saved, kind='passkey')})
            return dict(opts, kind='passkey')
        if kind == 'app':
            secret = b32_new(20)
            h.store.session_merge(s['id'], {'mfa_new': {
                'kind': 'app', 'secret': seal_secret(secret, 'adm2fa-new:' + name.lower())}})
            site = str(CONFIG.get('site_name') or socket.gethostname())
            uri = otpauth_uri(secret, name, '%s (administration)' % site)
            return {'kind': 'app', 'qr': qr_data_uri(uri), 'uri': uri,
                    'secret': ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4))}
        try:
            dest = dest_checked(kind, b.get('dest'))
        except ValueError as e:
            raise ApiError(400, str(e))
        to = _mfa_send(h, s, kind, dest, 'mfa_new')
        return {'kind': kind, 'sent_to': to, 'send': getattr(h, '_mfa_send_st', None)}
    if act == 'enrol_confirm':
        if stage != 'enrol':
            raise ApiError(409, 'this account has its second step set up already')
        new = data.get('mfa_new') or {}
        if not new.get('kind'):
            raise ApiError(400, 'choose a way first')
        key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),
                         int(CONFIG.get('login_wait_min') or 15), name=name,
                         what='wrong codes')
        rec = {'kind': new['kind'], 'at': time.time(), 'by': name}
        code = code_typed(b.get('code') or '') if new['kind'] != 'passkey' else ''
        if new['kind'] == 'passkey':
            try:
                pk = wa_register_finish(new, b)
            except (ValueError, TypeError, KeyError) as e:
                h.failed(key)
                raise ApiError(400, 'the passkey was not taken: %s' % e)
            if not h.store.session_take(s['id'], 'mfa_new'):
                raise ApiError(409, 'that answer was taken already - start again')
            rec['keys'] = [pk]
        elif new['kind'] == 'app':
            secret = unseal_secret(new.get('secret'), 'adm2fa-new:' + name.lower())
            step = totp_match(secret, code, clock_now('codes'), digits=6, window=mfa_window()) \
                if secret else None
            if step is None:
                h.failed(key)
                raise ApiError(400, 'that code is not right - the one the app shows now')
            rec.update(secret=seal_secret(secret, mfa_key(name)), step=step)
        else:
            if not _mfa_code_ok(new, code):
                h.failed(key)
                raise ApiError(400, 'that code is not right, or no longer good - send another')
            rec['dest'] = new['dest']
        with MFA_LOCK:
            if mfa_stage(h.store, name) != 'enrol':
                raise ApiError(409, 'this account has its second step set up already - sign '
                                    'in again')
            h.store.set_meta(mfa_key(name), json.dumps(rec))
        token = _mfa_done(h, s, 'set up now: %s' % MFA_KIND_WORDS.get(rec['kind']))
        h.store.add_event('accounts', '%s set up the second step of signing in: %s%s' % (
            name, MFA_KIND_WORDS.get(rec['kind']),
            ' (%s)' % dest_masked(rec['kind'], rec.get('dest')) if rec.get('dest') else
            ' (%s, for https://%s/)' % (rec['keys'][0].get('name') or 'a device', rec['keys'][0]['host'])
            if rec.get('keys') else ''), who=name)
        return {'message': 'the second step is set up', 'done': True, 'token': token}
    if act == 'send':
        if stage != 'check':
            raise ApiError(409, 'set the second step up first')
        rec = mfa_get(h.store, name) or {}
        if rec.get('kind') not in ('mail', 'sms'):
            raise ApiError(400, 'the second step is %s - nothing is sent'
                           % MFA_KIND_WORDS.get(rec.get('kind'), 'the app'))
        if rec['kind'] not in code_channels():
            raise ApiError(503, 'codes by %s cannot be sent from here now: another full '
                                'administrator resets your second step (Accounts), or root '
                                'with  otp --reset-2fa %s' % ('mail' if rec['kind'] == 'mail'
                                                              else 'SMS', name))
        if b.get('auto') and odict(s.get('data')).get('mfa_sent_at'):
            # The first code by itself (1.0.259) once a sign-in: a code went already - after a
            # reload, in another tab, from the other node - so none goes now.
            return {'sent_to': dest_masked(rec['kind'], rec.get('dest')), 'skipped': True,
                    'send': mfa_send_state(odict(s.get('data')), 'mfa_code')}
        to = _mfa_send(h, s, rec['kind'], rec.get('dest'), 'mfa_code')
        return {'sent_to': to, 'send': getattr(h, '_mfa_send_st', None)}
    if act == 'pk_begin':
        # The question for the account's passkey (1.0.254), kept with this sign-in.
        if stage != 'check':
            raise ApiError(409, 'set the second step up first')
        rec = mfa_get(h.store, name) or {}
        if rec.get('kind') != 'passkey':
            raise ApiError(400, 'the second step of this account is not a passkey')
        try:
            saved, opts = wa_login_options(h, rec.get('keys') or [])
        except ValueError as e:
            raise ApiError(400, str(e))
        h.store.session_merge(s['id'], {'mfa_pk': saved})
        return opts
    if act == 'check':
        if stage != 'check':
            raise ApiError(409, 'set the second step up first')
        rec = mfa_get(h.store, name) or {}
        key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),
                         int(CONFIG.get('login_wait_min') or 15), name=name,
                         what='wrong codes')
        code = code_typed(b.get('code') or '') if rec.get('kind') != 'passkey' else ''
        if rec.get('kind') == 'passkey':
            saved = data.get('mfa_pk') or {}
            # The question once (as a code is), here and on the other node.
            if not saved or not h.store.session_take(s['id'], 'mfa_pk') or \
                    not once_take(h.store, 'chal', 'adm2fa-pk:' + name.lower(),
                                  str(saved.get('challenge') or '')):
                _mfa_wrong(h, s, key, 'that answer is to an old question - try again')
            with MFA_LOCK:
                rec = mfa_get(h.store, name) or {}
                try:
                    used = wa_login_finish(saved, rec.get('keys') or [], b)
                except PermissionError as e:
                    h.store.add_event('sign-ins', '%s: the passkey was refused - %s' % (name, e),
                                      'bad', who=name)
                    _mfa_wrong(h, s, key, str(e))
                except (ValueError, TypeError, KeyError) as e:
                    h.store.add_event('sign-ins', '%s: the passkey was refused - %s' % (name, e),
                                      'warn', who=name)
                    _mfa_wrong(h, s, key, str(e))
                rec['keys'] = [used if k.get('id') == used['id'] else k for k in rec.get('keys') or []]
                h.store.set_meta(mfa_key(name), json.dumps(rec))
            token = _mfa_done(h, s, 'a passkey (%s)' % (used.get('name') or 'a device'))
            return {'message': 'signed in', 'done': True, 'token': token}
        if rec.get('kind') == 'app':
            # Read, checked and written under one lock (1.0.136): two requests
            # with the same code at once both passed the check.
            with MFA_LOCK:
                rec = mfa_get(h.store, name) or {}
                secret = unseal_secret(rec.get('secret'), mfa_key(name))
                step = totp_match(secret, code, clock_now('codes'), digits=6,
                                  window=mfa_window()) if secret else None
                # A code is good once (as a token's is).
                # And on either node (1.0.205): the step taken as a token's is, in
                # token_once - the other node's own lock did not keep a code used
                # here from being used there too.
                if step is not None and step > int(rec.get('step') or 0) and \
                        not once_take(h.store, 'step', 'adm2fa:' + name, step):
                    _mfa_wrong(h, s, key, 'that code was used already - wait for the next one')
                if step is None or step <= int(rec.get('step') or 0):
                    _mfa_wrong(h, s, key, 'that code is not right' if step is None else
                               'that code was used already - wait for the next one')
                rec['step'] = step
                h.store.set_meta(mfa_key(name), json.dumps(rec))
        else:
            saved = data.get('mfa_code') or {}
            if not _mfa_code_ok(saved, code) or \
                    not h.store.session_take(s['id'], 'mfa_code') or \
                    not once_take(h.store, 'chal', 'adm2fa:' + name.lower(),
                                  str(saved.get('hash') or '')):
                # Once across the nodes too (1.0.226), as the app's code is.
                _mfa_wrong(h, s, key, 'that code is not right, or no longer good - send another')
        token = _mfa_done(h, s, MFA_KIND_WORDS.get(rec.get('kind')))
        return {'message': 'signed in', 'done': True, 'token': token}
    raise ApiError(400, 'no such thing to do')


def mfa_window():
    """The steps either side a code is taken from (1.0.205): 0 as it is set -
    `or 1` made the strict window the usual one."""
    v = CONFIG.get('totp_window')
    try:
        return max(0, int(v)) if v is not None and v != '' else 1
    except (TypeError, ValueError):
        return 1


# ---- the passkeys of the account signed in (1.0.257) -------------------------------------
# Your account: the passkeys of this account listed, one added from another device, named,
# taken away - while the second step is on and it is a passkey. The last one is the second
# step itself: taken away only by a reset (another full administrator, or root).
PK_MAX = 10


PK_ADD_FRESH = int(os.environ.get('OTP_PK_ADD_FRESH') or 900)


def _pk_own(h):
    s = h.me('readonly')
    if not CONFIG.get('admin_2fa') or not CONFIG.get('admin_2fa_passkey'):
        raise ApiError(409, 'the second step by a passkey is switched off (Settings - Accounts)')
    rec = mfa_get(h.store, s['name']) or {}
    if rec.get('kind') != 'passkey':
        raise ApiError(409, 'the second step of this account is not a passkey')
    return s, rec


def _pk_row(k):
    return {'id': k.get('id'), 'name': k.get('name') or '', 'host': k.get('host') or '',
            'at': fnum(k.get('at')), 'used': fnum(k.get('used')), 'backed_up': bool(k.get('backed_up'))}


@route('GET', '/api/auth/passkeys')
def _pk_list(h):
    s = h.me('readonly')
    on = bool(CONFIG.get('admin_2fa') and CONFIG.get('admin_2fa_passkey'))
    rec = (mfa_get(h.store, s['name']) or {}) if on else {}
    mine = rec.get('kind') == 'passkey'
    why = ''
    if mine and not wa_host_ok(h):
        why = 'A passkey is added on these pages opened by a name over HTTPS (https://name/), not by an address.'
    elif mine and mfa_old_nodes(h.store):
        why = 'A passkey waits until every node runs otp 1.0.254 or newer (%s does not yet).' \
            % ', '.join(mfa_old_nodes(h.store))
    elif mine and len(rec.get('keys') or []) >= PK_MAX:
        why = 'This account has %d passkeys, as many as it may.' % PK_MAX
    elif mine and time.time() - fnum(odict(s.get('data')).get('mfa_at')) > PK_ADD_FRESH:
        # Said before the button is pressed (1.0.262), not only after.
        why = 'A passkey is added within %d minutes of signing in - sign in again to add one.' % (
            PK_ADD_FRESH // 60)
    return {'on': on, 'mine': mine, 'kind': rec.get('kind') or '',
            'keys': [_pk_row(k) for k in rec.get('keys') or []] if mine else [],
            'can_add': mine and not why, 'why': why, 'max': PK_MAX}


@route('POST', '/api/auth/passkeys')
def _pk_do(h):
    s, rec = _pk_own(h)
    b = h.body()
    act = str(b.get('action') or '')
    name = s['name']
    if act == 'add_begin':
        if mfa_old_nodes(h.store):
            raise ApiError(409, 'a passkey waits until every node runs otp 1.0.254 or newer (%s does '
                                'not yet)' % ', '.join(mfa_old_nodes(h.store)))
        keys = rec.get('keys') or []
        if len(keys) >= PK_MAX:
            raise ApiError(409, 'this account has %d passkeys, as many as it may' % PK_MAX)
        # 1.0.262: not on the cookie alone - a passkey outlives the sign-in, so it is added only
        # within a quarter of an hour of the second step given (sign in again otherwise).
        if time.time() - fnum(odict(s.get('data')).get('mfa_at')) > PK_ADD_FRESH:
            raise ApiError(409, 'a passkey is added within %d minutes of signing in - sign in again '
                                'and add it then' % (PK_ADD_FRESH // 60))
        acc = s.get('account') or {}
        try:
            saved, opts = wa_register_options(h, name, acc.get('display') or '',
                                              have=[k.get('id') for k in keys if k.get('id')])
        except ValueError as e:
            raise ApiError(400, str(e))
        # Kept with this sign-in, so either node takes the answer.
        h.store.session_merge(s['id'], {'pk_add': saved})
        return opts
    if act == 'add_finish':
        saved = odict(odict(s.get('data')).get('pk_add'))
        if not saved:
            raise ApiError(409, 'that answer is to an old question - press the button again')
        try:
            pk = wa_register_finish(saved, b)
        except (ValueError, TypeError, KeyError) as e:
            raise ApiError(400, 'the passkey was not taken: %s' % e)
        if not h.store.session_take(s['id'], 'pk_add'):
            raise ApiError(409, 'that answer was taken already - press the button again')
        with MFA_LOCK:
            rec = mfa_get(h.store, name) or {}
            if rec.get('kind') != 'passkey':
                raise ApiError(409, 'the second step of this account is not a passkey')
            keys = list(rec.get('keys') or [])
            if any(k.get('id') == pk['id'] for k in keys):
                raise ApiError(409, 'this device has a passkey for this account already')
            if len(keys) >= PK_MAX:
                raise ApiError(409, 'this account has %d passkeys, as many as it may' % PK_MAX)
            keys.append(pk)
            rec['keys'] = keys
            h.store.set_meta(mfa_key(name), json.dumps(rec))
        h.store.add_event('accounts', '%s added a passkey (%s, for https://%s/)' % (
            name, pk.get('name') or 'a device', pk['host']), who=name)
        return {'message': 'the passkey is added', 'keys': [_pk_row(k) for k in keys]}
    ident = str(b.get('id') or '')
    if act == 'rename':
        label = ' '.join(str(b.get('name') or '').split())[:60]
        if not label:
            raise ApiError(400, 'a name for the passkey')
        with MFA_LOCK:
            rec = mfa_get(h.store, name) or {}
            keys = list(rec.get('keys') or [])
            hit = next((k for k in keys if k.get('id') == ident), None)
            if hit is None:
                raise ApiError(404, 'no such passkey of this account')
            was = hit.get('name') or 'a device'
            hit['name'] = label
            rec['keys'] = keys
            h.store.set_meta(mfa_key(name), json.dumps(rec))
        h.store.add_event('accounts', '%s named a passkey %s (was %s)' % (name, label, was), who=name)
        return {'message': 'named', 'keys': [_pk_row(k) for k in keys]}
    if act == 'delete':
        with MFA_LOCK:
            rec = mfa_get(h.store, name) or {}
            keys = list(rec.get('keys') or [])
            hit = next((k for k in keys if k.get('id') == ident), None)
            if hit is None:
                raise ApiError(404, 'no such passkey of this account')
            if len(keys) <= 1:
                raise ApiError(409, 'the last passkey is the second step of this account: another '
                                    'full administrator resets it (Accounts), or root with  otp '
                                    '--reset-2fa %s' % name)
            keys = [k for k in keys if k.get('id') != ident]
            rec['keys'] = keys
            h.store.set_meta(mfa_key(name), json.dumps(rec))
        h.store.add_event('accounts', '%s took a passkey away (%s, for https://%s/)' % (
            name, hit.get('name') or 'a device', hit.get('host') or '?'), 'warn', who=name)
        return {'message': 'taken away', 'keys': [_pk_row(k) for k in keys]}
    raise ApiError(400, 'what should be done?')
