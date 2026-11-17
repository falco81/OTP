# 1.0.308: an administrator's second step (hunt round 7) - wrong codes counted on the account in the
# database too, across sign-ins and nodes: past 20 in a day no more codes are taken until a full
# administrator resets the second step or the day is over; codes by mail or SMS limited per account and
# per address, as the portal's are.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('90m_mfa.py', [
("""MFA_WRONG_MOST = 5          # wrong second-step codes of one sign-in, then the password again (1.0.252)""",
 """MFA_WRONG_MOST = 5          # wrong second-step codes of one sign-in, then the password again (1.0.252)
MFA_WRONG_DAY_MOST = 20     # wrong codes of one account in a day, every sign-in and node together (1.0.308)
MFA_WRONG_DAY_S = 86400"""),
("""    h.failed(key)
    n = h.store.session_bump(s['id'], 'mfa_wrong')""",
 """    h.failed(key)
    # Counted on the account too, in the database (1.0.308): signing in again with the password
    # gave five more guesses each time - about 1,900 a day on each node.
    try:
        node_key_add(h.store, 'mfawrong', str(s['name']).lower(), MFA_WRONG_DAY_S)
    except Exception:                                   # noqa: BLE001
        pass
    n = h.store.session_bump(s['id'], 'mfa_wrong')"""),
("""        rec = mfa_get(h.store, name) or {}
        key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),""",
 """        rec = mfa_get(h.store, name) or {}
        if mfa_wrong_today(h.store, name) >= MFA_WRONG_DAY_MOST:
            raise ApiError(429, 'too many wrong codes of the second step for this account today - '
                                'another full administrator resets the second step (Accounts), or try '
                                'again tomorrow')
        key = h.throttle('admin', int(CONFIG.get('login_tries') or 5),"""),
("""def _mfa_send(h, s, kind, dest, field):
    data = s.get('data') or {}
    t = time.time()
    st = mfa_send_state(data, field, t)""",
 """def mfa_wrong_today(store, name):
    \"\"\"Wrong second-step codes of `name` in the last day, every node's together (1.0.308).\"\"\"
    try:
        t = time.time()
        return sum(1 for x in node_key_times(store, 'mfawrong', str(name).lower()) if t - x < MFA_WRONG_DAY_S)
    except Exception:                                   # noqa: BLE001
        return 0


def _mfa_send(h, s, kind, dest, field):
    data = s.get('data') or {}
    t = time.time()
    st = mfa_send_state(data, field, t)"""),
("""    code, salt = code_new(), secrets.token_hex(8)
    saved = {'hash': code_hash(salt, code), 'salt': salt,""",
 """    # Limited per account and per address too (1.0.308), as every code of the portal is: five per
    # sign-in only, and signing in again (or setting the step up: any address typed in) sent more
    # without end - a mailbox flooded, SMS paid for to any number.
    dkey = 'to:%s:%s' % (kind, str(dest or '').strip().lower())
    if not code_send_allowed(h.store, 'adm:' + str(s['name']).lower()) or \\
            not code_send_allowed(h.store, dkey):
        try:
            h.store.session_merge(s['id'], was, expect={'mfa_sent_at': t, 'mfa_sent': n + 1})
        except Exception:                               # noqa: BLE001
            pass
        raise ApiError(429, 'too many codes sent lately - try again in %d min'
                       % code_send_wait_min(h.store, 'adm:' + str(s['name']).lower()), extra={'send': st})
    code, salt = code_new(), secrets.token_hex(8)
    saved = {'hash': code_hash(salt, code), 'salt': salt,"""),
("""    had = mfa_get(store, name)
    store.drop_meta(mfa_key(name))""",
 """    had = mfa_get(store, name)
    store.drop_meta(mfa_key(name))
    # The wrong codes of the day forgotten with it (1.0.308): the reset is how the account gets back in.
    try:
        node_key_drop(store, 'mfawrong', str(name).lower())
    except Exception:                                   # noqa: BLE001
        pass"""),
])
print('ok')
