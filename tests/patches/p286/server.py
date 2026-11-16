# 1.0.286: a browser that cannot be checked (the kit card-removal-watch, 3rd edition - isemon 1.10.355, found on a
# real iPad: Safari signs nothing for a page in the background) - python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('00_head.py', [(
"""    'admin_cert_card_grace_s': 30,
""",
"""    'admin_cert_card_grace_s': 30,
    # A browser whose checks have never once found the card (1.0.286): an iPad's Safari signs nothing
    # in the background - allow: that sign-in is not watched (said in the events); signout: as a card out.
    'admin_cert_card_unable': 'allow',
"""), (
"""    'admin_cert_card_grace_s': (5, 600),
""",
"""    'admin_cert_card_grace_s': (5, 600), 'admin_cert_card_unable': ('allow', 'signout'),
"""), (
"""    'admin_cert_card': {'off': 'off', 'signout': 'signout', 'grace': 'grace'},
""",
"""    'admin_cert_card': {'off': 'off', 'signout': 'signout', 'grace': 'grace'},
    'admin_cert_card_unable': {'allow': 'allow', 'signout': 'signout'},
"""), (
"""    'admin_cert_card_grace_s': '...put back within (seconds)',
""",
"""    'admin_cert_card_grace_s': '...put back within (seconds)',
    'admin_cert_card_unable': 'A browser that cannot be checked',
"""), (
"""                       'in time. Another card than the one signed in with ends it at once. The server ends a '
                       'watched session too when the page stops asking.',""",
"""                       'in time. Another card than the one signed in with ends it at once. The server ends a '
                       'watched session too when the card stays out; a page that stops asking (a tablet '
                       'asleep) is held - nothing answered - until a check finds the card again.',"""), (
"""    'admin_cert_card_grace_s': 'With grace: how long the card may be out before the session ends.',
""",
"""    'admin_cert_card_grace_s': 'With grace: how long the card may be out before the session ends.',
    'admin_cert_card_unable': 'A browser whose very first check in the background does not find the card cannot '
                              'be checked at all - an iPad\\'s Safari signs nothing for a page in the background, '
                              'though the card is in. allow: that sign-in is simply not watched, and Events say so '
                              'and why. signout: it is signed out as if the card were out - such a browser cannot '
                              'stay signed in with this on. Once a check has found the card, a later one that does '
                              'not is a card taken out, whatever this says.',
"""), (
"""                  'admin_cert_card_s', 'admin_cert_card_grace_s'],""",
"""                  'admin_cert_card_s', 'admin_cert_card_grace_s', 'admin_cert_card_unable'],"""), (
"""    'admin_cert_card_grace_s': ['admin_cert_card', 'grace'],""",
"""    'admin_cert_card_grace_s': ['admin_cert_card', 'grace'], 'admin_cert_card_unable': ['admin_cert_card', 'off-not'],""")])

edit('50g_guard.py', [(
"""    'admin_cert_card', 'admin_cert_card_s', 'admin_cert_card_grace_s',
""",
"""    'admin_cert_card', 'admin_cert_card_s', 'admin_cert_card_grace_s', 'admin_cert_card_unable',
""")])

edit('87c_certlogin.py', [(
"""            'watch': card_mode(), 'watch_s': card_every(), 'watch_grace_s': card_grace()}""",
"""            'watch': card_mode(), 'watch_s': card_every(), 'watch_grace_s': card_grace(),
            'watch_unable': card_unable_mode()}""")])

edit('90c_certlogin_api.py', [(
"""def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card'))""",
"""def card_unable_mode():
    return 'signout' if str(CONFIG.get('admin_cert_card_unable') or 'allow') == 'signout' else 'allow'


# A browser that cannot be checked (1.0.286; the kit's 3rd edition, found on a real iPad): Safari on iPadOS
# signs nothing for a page in the background - the card is in, yet no check ever finds it. A session keeps
# whether a check IN THE BACKGROUND has found its card in this browser (data.card_ok: the time of the first;
# -1 - this browser cannot be checked). The sign-in itself does not count (a top-level navigation, which the
# iPad does sign). Until one has, a check without the card means "cannot be checked": allow - that sign-in is
# not watched from then on (an event says why); signout - on as a card taken out. Once found, a check
# without it is a card taken out, as always.
CARD_UNABLE_WHY = {
    'nocert': 'no certificate came with the check (the browser does not sign it in the background)',
    'nocookie': 'the browser sent no cookie with the check',
    'nopicture': 'the check got no answer at all (the browser did not sign the connection)'}


def card_proven(s):
    return fnum(odict((s or {}).get('data')).get('card_ok')) > 0


def card_unable_now(s):
    return fnum(odict((s or {}).get('data')).get('card_ok')) < 0


def card_unable(h, s, why):
    \"\"\"No card at a check of a browser whose checks never found it: True when that sign-in is (now) not
    watched - allow; False - go on as for a card taken out.\"\"\"
    if card_proven(s) or card_unable_mode() != 'allow':
        return False
    if not card_unable_now(s):
        d = s['data']
        d['card_ok'], d['card_out'] = -1, None
        h.store.session_merge(s['id'], {'card_ok': -1, 'card_out': None})
        who = s.get('name') or '?'
        h.store.add_event('sign-ins', 'the card of %s\\'s sign-in cannot be checked in this browser - %s: it is '
                          'not watched (Settings - Accounts - Signing in with a certificate - A browser that '
                          'cannot be checked)' % (who, CARD_UNABLE_WHY.get(why, why)), 'warn', who=who)
    return True


def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card')) and not card_unable_now(s)"""), (
"""    if not fp:
        st = card_out(h, s, 'the card they signed in with was taken out')""",
"""    if not fp:
        if card_unable(h, s, 'nocert'):
            return {'watched': False, 'alive': True, 'gone': False, 'unable': True}
        st = card_out(h, s, 'the card they signed in with was taken out')"""), (
"""    t = time.time()
    ch = {}
    if d.get('card_out'):
        ch['card_out'] = None""",
"""    t = time.time()
    ch = {}
    if not card_proven(s):
        ch['card_ok'] = t               # this browser can be checked: proven (1.0.286)
    if d.get('card_out'):
        ch['card_out'] = None"""), (
"""    \"\"\"The page's picture got no answer at all, twice, while these pages answer: the handshake failed -
    nothing to sign it with. It only ever ends or holds its own sign-in.\"\"\"
    s = _card_session(h)
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    if not card_bound(s):
        return {'watched': False, 'gone': False}""",
"""    \"\"\"The page's picture got no answer at all, twice, while these pages answer: the handshake failed -
    nothing to sign it with; or it came back saying no cookie came with it ({why}). It only ever ends or
    holds its own sign-in - or, never once found in this browser, leaves it unwatched (1.0.286).\"\"\"
    s = _card_session(h)
    if not s:
        raise ApiError(401, 'not signed in, or the sign-in has run out')
    if not card_bound(s):
        return {'watched': False, 'gone': False}
    why = str(h.body().get('why') or '')
    if card_unable(h, s, why if why in CARD_UNABLE_WHY else 'nopicture'):
        return {'watched': False, 'gone': False, 'unable': True}""")])
print('1.0.286 server patched')
