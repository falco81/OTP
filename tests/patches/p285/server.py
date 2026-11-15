# 1.0.285: a sign-in with a certificate watched for its card (admin_cert_card: off | signout | grace) - the
# kit "card-removal-watch" merged: its settings, protocol (a picture of the certificate's port, 1 or 2 px
# wide, or 403) and pages; its state kept in the sign-in's row of the database (either node of a cluster
# answers, a restart forgets nothing) - python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('00_head.py', [(
"""    'admin_cert_ocsp_url': '',
    # --- a second step for the administration (1.0.125) -------------------""",
"""    'admin_cert_ocsp_url': '',
    # The card (or the YubiKey) a sign-in with a certificate was made with, watched while the pages are
    # open (1.0.285): off - nothing changes, nginx is written as before.
    'admin_cert_card': 'off',
    'admin_cert_card_s': 15,
    'admin_cert_card_grace_s': 30,
    # --- a second step for the administration (1.0.125) -------------------"""), (
"""    'admin_cert_ocsp': ('off', 'first', 'only', 'both'),
""",
"""    'admin_cert_ocsp': ('off', 'first', 'only', 'both'),
    'admin_cert_card': ('off', 'signout', 'grace'), 'admin_cert_card_s': (5, 300),
    'admin_cert_card_grace_s': (5, 600),
"""), (
"""                        'only': 'only - OCSP alone, no answer no sign-in', 'both': 'both - OCSP and the CRL'},
""",
"""                        'only': 'only - OCSP alone, no answer no sign-in', 'both': 'both - OCSP and the CRL'},
    'admin_cert_card': {'off': 'off', 'signout': 'signout', 'grace': 'grace'},
"""), (
"""    'admin_cert_ocsp_url': 'OCSP responder of its own',
""",
"""    'admin_cert_ocsp_url': 'OCSP responder of its own',
    'admin_cert_card': 'When the card is taken out',
    'admin_cert_card_s': 'Checked every (seconds)',
    'admin_cert_card_grace_s': '...put back within (seconds)',
"""), (
"""                           'was there. Empty: each certificate\\u2019s own.',
""",
"""                           'was there. Empty: each certificate\\u2019s own.',
    'admin_cert_card': 'Only for a sign-in made with a certificate. off: nothing is watched. signout: the page '
                       'checks the card every few seconds - a new connection to the certificate\\'s port the card '
                       'has to sign - and the first time it is not there the session ends and the sign-in page '
                       'comes. grace: the page says the card is out and waits; the session ends unless it is back '
                       'in time. Another card than the one signed in with ends it at once. The server ends a '
                       'watched session too when the page stops asking.',
    'admin_cert_card_s': 'How often the card is checked. Each check is a signature by the card (no PIN while it '
                         'stays in; a YubiKey with touch or PIN policy "always" asks every time - leave this off '
                         'for one). A tab in the background is checked about once a minute.',
    'admin_cert_card_grace_s': 'With grace: how long the card may be out before the session ends.',
"""), (
"""                  'admin_cert_crl_ldap', 'admin_cert_ocsp', 'admin_cert_ocsp_url'],""",
"""                  'admin_cert_crl_ldap', 'admin_cert_ocsp', 'admin_cert_ocsp_url', 'admin_cert_card',
                  'admin_cert_card_s', 'admin_cert_card_grace_s'],"""), (
"""    'admin_cert_ocsp_url': ['admin_cert_ocsp', 'off-not'], 'admin_cert_auto': ['admin_cert', '1'],""",
"""    'admin_cert_ocsp_url': ['admin_cert_ocsp', 'off-not'], 'admin_cert_auto': ['admin_cert', '1'],
    'admin_cert_card': ['admin_cert', '1'], 'admin_cert_card_s': ['admin_cert_card', 'off-not'],
    'admin_cert_card_grace_s': ['admin_cert_card', 'grace'],""")])

edit('50g_guard.py', [(
"""'admin_cert_ocsp', 'admin_cert_ocsp_url',
""",
"""'admin_cert_ocsp', 'admin_cert_ocsp_url',
    'admin_cert_card', 'admin_cert_card_s', 'admin_cert_card_grace_s',
""")])

edit('90_api.py', [(
"""def admin_signed_in(h, ok, how=''):""",
"""def admin_signed_in(h, ok, how='', extra=None):"""), (
"""    if how:
        data['how'] = how
    token = h.store.session_new('admin', ok['name'], ok['role'], h.client_ip(),""",
"""    if how:
        data['how'] = how
    # The certificate's fingerprint (1.0.285): its card watched while the pages are open (admin_cert_card).
    data.update(extra or {})
    token = h.store.session_new('admin', ok['name'], ok['role'], h.client_ip(),"""), (
"""        if acc.get('must_change') and getattr(self, 'route_path', '') not in MUST_CHANGE_ALLOWED:
            raise ApiError(403, 'change the password first')""",
"""        # The card of a sign-in with a certificate (1.0.285): out too long - signed out; out within
        # the grace - nothing answered but the card's own questions until it is back.
        card = card_due(self, s)
        if card == 'gone':
            raise ApiError(401, 'signed out: the card was taken out', extra={'code': 'card'})
        if card in ('out', 'stale') and getattr(self, 'route_path', '') not in CARD_ALLOWED:
            raise ApiError(423, 'the card is out - put back the card you signed in with',
                           extra={'code': 'card'})
        if acc.get('must_change') and getattr(self, 'route_path', '') not in MUST_CHANGE_ALLOWED:
            raise ApiError(403, 'change the password first')"""), (
"""        return {'who': {'name': acc['name'], 'role': '', 'display': acc.get('display') or '',
                        'mfa': stage}}
    prefs = json_obj(acc.get('prefs')) or {}""",
"""        return {'who': {'name': acc['name'], 'role': '', 'display': acc.get('display') or '',
                        'mfa': stage}}
    # The card of a sign-in with a certificate (1.0.285): ended - nobody; out - no role (the PHP pages'
    # gates refuse it); the page told how to watch it (the PHP page lets the check's picture in by it).
    card = card_due(h, s)
    if card == 'gone':
        return {'who': None}
    prefs = json_obj(acc.get('prefs')) or {}"""), (
"""            'who': {'name': acc['name'], 'role': acc['role'], 'source': acc.get('source'),""",
"""            'who': {'name': acc['name'], 'role': '' if card in ('out', 'stale') else acc['role'],
                    'card': card_conf(card), 'source': acc.get('source'),""")])

edit('88w_web.py', [(
"""        if pems:
            return {'port': int(CONFIG.get('admin_cert_port') or 8443),
                    'ca': ''.join(p.strip() + '\\n' for p in pems)}""",
"""        if pems:
            out = {'port': int(CONFIG.get('admin_cert_port') or 8443),
                   'ca': ''.join(p.strip() + '\\n' for p in pems)}
            # The card watched (1.0.285): the port keeps no TLS session and no connection then. Only
            # while it is on - off, the request (and nginx) stay as they were.
            if card_mode() != 'off':
                out['card'] = 1
            return out""")])

edit('87c_certlogin.py', [(
"""            'ocsp_url_ok': bool(ocsp_url_set()), 'crl_ldap': bool(_setting_on(CONFIG.get('admin_cert_crl_ldap'))),
            'ocsp_answers': ocsp_rows}""",
"""            'ocsp_url_ok': bool(ocsp_url_set()), 'crl_ldap': bool(_setting_on(CONFIG.get('admin_cert_crl_ldap'))),
            'ocsp_answers': ocsp_rows,
            # The card watched (1.0.285): a line of the card's facts.
            'watch': card_mode(), 'watch_s': card_every(), 'watch_grace_s': card_grace()}""")])

edit('90c_certlogin_api.py', [(
"""    h.store.add_event('sign-ins', '%s: the certificate %s%s' % (ok['name'], f['subject'][:160], tail),
                      who=ok['name'])
    return admin_signed_in(h, ok, how='certificate')""",
"""    h.store.add_event('sign-ins', '%s: the certificate %s%s' % (ok['name'], f['subject'][:160], tail),
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
    \"\"\"The SHA-256 of a certificate's DER - '' when it is not one.\"\"\"
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
    \"\"\"How late a check may be: a tab in the background is let check about once a minute.\"\"\"
    return max(3 * card_every(), 150)


def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card'))


def card_conf(state):
    \"\"\"What the page is to do: None, or {mode, every, grace, port, out}.\"\"\"
    if not state:
        return None
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(),
            'port': int(CONFIG.get('admin_cert_port') or 8443), 'out': state == 'out', 'stale': state == 'stale'}


def card_end(h, s, why):
    \"\"\"The watched sign-in `s` ended, said in the events with why.\"\"\"
    who = s.get('name') or 'somebody'
    h.store.db.run('DELETE FROM sessions WHERE id = ?', (s['id'],))
    h.store.add_event('sign-ins', '%s was signed out: %s' % (who, why), 'warn', who=who)
    return 'gone'


def card_out(h, s, why):
    \"\"\"No card: signout - the sign-in ends; grace - the time out is counted ('out'), past it 'gone'.\"\"\"
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
    \"\"\"The server's half, on every question of a sign-in: None (not watched), 'in', 'out' (grace) or
    'gone' (ended just now) - the card out longer than allowed, or its page no longer checking.\"\"\"
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
    \"\"\"One check, from the certificate's port: {watched, alive, gone, grace_left}.\"\"\"
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
    \"\"\"The page's picture got no answer at all, twice, while these pages answer: the handshake failed -
    nothing to sign it with. It only ever ends or holds its own sign-in.\"\"\"
    s = _card_session(h)
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    if not card_bound(s):
        return {'watched': False, 'gone': False}
    st = card_out(h, s, 'the card they signed in with was taken out')
    return {'watched': True, 'gone': st == 'gone',
            'grace_left': max(0, int(card_grace() - (time.time() - fnum(s['data'].get('card_out')))))
            if st != 'gone' else 0}""")])
print('1.0.285 server patched')
