# 1.0.288: the card watched - the kit's 4th edition (isemon 1.10.356-1.10.358) - python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('90c_certlogin_api.py', [
    # 5/a: a mode changed - the time out and the last check counted afresh (a session could end at once for
    # time counted under the mode before). Kept with the session, so it holds for a change on either node,
    # from the pages or the command line.
    (
"""def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card')) and not card_unable_now(s)
""",
"""def card_bound(s):
    return card_mode() != 'off' and bool(odict((s or {}).get('data')).get('card')) and not card_unable_now(s)


def card_fresh(h, s):
    \"\"\"The mode a watched sign-in's count was made under (1.0.288): another one now - counted afresh.\"\"\"
    d = s['data']
    m = card_mode()
    if d.get('card_mode') != m:
        h.store.session_merge(s['id'], {'card_mode': m, 'card_out': None, 'card_seen': None})
        d['card_mode'] = m
        d.pop('card_out', None)
        d.pop('card_seen', None)


def card_port_waiting(store):
    \"\"\"Root still putting the watched port into nginx (1.0.288): a check that got nothing then says
    nothing about this browser yet. Only while a request for root waits - and not for ever.\"\"\"
    try:
        f = WEB_DIR / 'request.json'
        return f.exists() and time.time() - f.stat().st_mtime < 300
    except OSError:
        return False
"""),
    # 4: how long the card has been out by the server's clock - a page loaded again (F5) goes on counting.
    (
"""def card_conf(state, token=''):
    \"\"\"What the page is to do: None, or {mode, every, grace, port, out, key}.\"\"\"
    if not state:
        return None
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(), 'key': card_key(token),
            'port': int(CONFIG.get('admin_cert_port') or 8443), 'out': state == 'out', 'stale': state == 'stale'}""",
"""def card_conf(state, token='', s=None):
    \"\"\"What the page is to do: None, or {mode, every, grace, port, out, stale, out_for, key}.\"\"\"
    if not state:
        return None
    out = fnum(odict((s or {}).get('data')).get('card_out')) if state == 'out' else 0
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(), 'key': card_key(token),
            'port': int(CONFIG.get('admin_cert_port') or 8443), 'out': state == 'out', 'stale': state == 'stale',
            'out_for': max(0, int(time.time() - out)) if out else 0}"""),
    (
"""    if not card_bound(s):
        return None
    d = s['data']
    t = time.time()
    seen = fnum(d.get('card_seen'))""",
"""    if not card_bound(s):
        return None
    card_fresh(h, s)
    d = s['data']
    t = time.time()
    seen = fnum(d.get('card_seen'))"""),
    (
"""    if not card_bound(s):
        return {'watched': False, 'alive': True, 'gone': False}
    # The page's own key (1.0.287)""",
"""    if not card_bound(s):
        return {'watched': False, 'alive': True, 'gone': False}
    card_fresh(h, s)
    # The page's own key (1.0.287)"""),
    # 5/d: ended for another card - said as such to the page (a picture 6 wide), not a bare 403.
    (
"""        card_end(h, s, 'another certificate than the one signed in with was offered (the card was changed)')
        return {'watched': True, 'alive': False, 'gone': True}
    if not fp:
        if card_unable(h, s, 'nocert'):""",
"""        card_end(h, s, 'another certificate than the one signed in with was offered (the card was changed)')
        return {'watched': True, 'alive': False, 'gone': True, 'why': 'other'}
    if not fp:
        if not card_proven(s) and card_port_waiting(h.store):
            return {'watched': False, 'alive': True, 'gone': False}
        if card_unable(h, s, 'nocert'):"""),
    # 2: a check waiting on a window of the card's (Windows' "insert the smart card", the browser's chooser)
    # for over 4 s - the card out, but never a word about whether this browser can be checked.
    # 5/b: no "cannot be checked" while root is still putting the port in.
    (
"""    if not card_bound(s):
        return {'watched': False, 'gone': False}
    why = str(h.body().get('why') or '')
    if card_unable(h, s, why if why in CARD_UNABLE_WHY else 'nopicture'):""",
"""    if not card_bound(s):
        return {'watched': False, 'gone': False}
    card_fresh(h, s)
    why = str(h.body().get('why') or '')
    if not card_proven(s) and (why == 'waiting' or card_port_waiting(h.store)):
        return {'watched': False, 'gone': False}
    if why != 'waiting' and card_unable(h, s, why if why in CARD_UNABLE_WHY else 'nopicture'):"""),
])

edit('90_api.py', [
    # 4: whoami - how long the card has been out (5/c not taken: otp's pages take their language from prefs).
    (
"""            'who': {'name': acc['name'], 'role': '' if card in ('out', 'stale') else acc['role'],
                    'card': card_conf(card, h.headers.get('X-Otp-Session')), 'source': acc.get('source'),
                    'display': acc.get('display') or '', 'must_change': bool(
                        acc.get('must_change')), 'prefs': prefs,
                    'cols': h.store.user_cols(acc['name']),""",
"""            'who': {'name': acc['name'], 'role': '' if card in ('out', 'stale') else acc['role'],
                    'card': card_conf(card, h.headers.get('X-Otp-Session'), s), 'source': acc.get('source'),
                    'display': acc.get('display') or '', 'must_change': bool(
                        acc.get('must_change')), 'prefs': prefs,
                    'cols': h.store.user_cols(acc['name']),"""),
])
# The 4th edition: "an iPad's Safari signs nothing in the background" was wrong (it was a policy header of
# isemon's own nginx blocking the check) - a browser that cannot be checked stays as a safety net.
edit('00_head.py', [(
"""                              'be checked at all - an iPad\\'s Safari signs nothing for a page in the background, '
                              'though the card is in. allow""",
"""                              'be checked at all - some browsers sign nothing for a page in the background, '
                              'though the card is in. allow""")])
print('1.0.288 server patched')
