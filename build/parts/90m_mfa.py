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
    if CONFIG.get('admin_2fa_passkey') and (h is None or wa_host_ok(h)):
        out.append('passkey')
    return out or ['app']


def mfa_stage(store, name):
    rec = mfa_get(store, name)
    if rec and rec.get('kind') in MFA_KINDS:
        # A way switched off since is still the account's, and the only one
        # (1.0.136): mail or SMS that can no longer be sent was set up anew
        # - by whoever had the password. Now that waits for a reset (the
        # accounts page, or otp --reset-2fa NAME as root).
        return 'check'
    return 'enrol'


def mfa_pending(s):
    """The sign-in's second step, if it is still to be done."""
    if not CONFIG.get('admin_2fa'):
        return ''
    return str(((s or {}).get('data') or {}).get('mfa') or '')


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


def _mfa_send(h, s, kind, dest, field):
    data = s.get('data') or {}
    t = time.time()
    if t - fnum(data.get('mfa_sent_at')) < MFA_SEND_GAP_S:
        raise ApiError(429, 'a code went a moment ago - wait half a minute for another')
    n = int(data.get('mfa_sent') or 0)
    if n >= MFA_SEND_MOST:
        raise ApiError(429, 'that is %d codes for this sign-in: sign in again for more'
                       % MFA_SEND_MOST)
    code, salt = code_new(), secrets.token_hex(8)
    saved = {'hash': code_hash(salt, code), 'salt': salt,
             't': t, 'exp': t + int(CONFIG.get('code_ttl_s') or 300)}
    try:
        acc = h.store.account(s['name']) or {}
        said = code_send(h.store, kind, dest, code, purpose='admin_verify' if field == 'mfa_new'
                         else 'admin', name=s['name'], display=acc.get('display') or '',
                         lang=mfa_lang(h))
    except (MailError, SmsError, ValueError) as e:
        h.store.add_event('sign-ins', 'the code of the second step for %s could not be sent '
                          '(%s): %s' % (s['name'], kind, e), 'warn', who=s['name'])
        raise ApiError(502, 'the code could not be sent: %s' % e)
    # Kept only once it went: a refused one leaves the last code good.
    new = dict(saved, kind=kind, dest=dest) if field == 'mfa_new' else saved
    h.store.session_merge(s['id'], {field: new, 'mfa_sent_at': t, 'mfa_sent': n + 1})
    log('the second step of %s: a code sent by %s to %s (%s)' % (
        s['name'], kind, dest_masked(kind, dest), said))
    return dest_masked(kind, dest)


def _mfa_done(h, s, how):
    """The second step given: a sign-in of its own from here on (1.0.149) - the
    one the password alone opened is ended, not made whole: whoever had seen
    its cookie had the pages once the code was given."""
    data = {k: v for k, v in odict(s.get('data')).items()
            if k not in ('mfa', 'mfa_new', 'mfa_code', 'mfa_sent_at', 'mfa_sent')}
    hours = max(0.05, (fnum(s.get('expires')) - time.time()) / 3600.0)
    token = h.store.session_new('admin', s['name'], s['role'], h.client_ip(), hours, data=data)
    h.store.session_drop(s['id'])
    h.store.add_event('sign-ins', '%s gave the second step (%s) from %s' % (
        s['name'], how, h.client_ip()), who=s['name'])
    return token


@route('GET', '/api/auth/mfa')
def _mfa(h):
    s, acc = _mfa_session(h)
    stage = mfa_pending(s)
    rec = mfa_get(h.store, s['name']) or {}
    new = odict(s.get('data')).get('mfa_new') or {}
    return {'name': acc['name'], 'display': acc.get('display') or '', 'stage': stage,
            'methods': mfa_methods(h), 'kind': rec.get('kind') if stage == 'check' else '',
            'hosts': sorted(set(k.get('host') for k in rec.get('keys') or [])) if stage == 'check' else [],
            'dest': dest_masked(rec.get('kind'), rec.get('dest')) if stage == 'check' else '',
            'started': {'kind': new.get('kind'),
                        'dest': dest_masked(new.get('kind'), new.get('dest'))} if new else None,
            'digits': 6 if (stage == 'check' and rec.get('kind') == 'app') else
            int(CONFIG.get('code_digits') or 6)}


@route('POST', '/api/auth/mfa')
def _mfa_do(h):
    s, acc = _mfa_session(h)
    stage = mfa_pending(s)
    if not stage:
        raise ApiError(409, 'this sign-in has no second step to give')
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
        return {'kind': kind, 'sent_to': _mfa_send(h, s, kind, dest, 'mfa_new')}
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
        return {'sent_to': _mfa_send(h, s, rec['kind'], rec.get('dest'), 'mfa_code')}
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
