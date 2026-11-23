"""1.0.319 (parts): the SSH gate's requests without a Message-Authenticator taken only as pam_radius
sends them; Windows' Kerberos OID taken; an SSH token removed or used under its lock; local users'
asks written under a lock of their own."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('87s_sshotp.py', [
("""        secret = ssh_gate_secret(self.d.store).encode()
        if not secret or p.message_authenticator_ok(secret) is False:
            return None
        user = p.text(1)
        try:
            code = p.password(secret) or ''
        except RadiusError:
            return None
""",
 """        secret = ssh_gate_secret(self.d.store).encode()
        ma = p.message_authenticator_ok(secret) if secret else False
        if not secret or ma is False:
            return None
        user = p.text(1)
        try:
            code = p.password(secret)
        except RadiusError:
            return None
        if ma is None and (code is None or '\\ufffd' in code or not code.isprintable()):
            # Without a Message-Authenticator (an older pam_radius) only a password the secret
            # undid into text (1.0.319): anybody on the host could send names without it - wrong
            # codes counted against them until they were held, codes sent by SMS to them.
            return None
        code = code or ''
"""),
("""    store.drop_meta(sshotp_key(name))
    store.add_event('settings', '%s removed the SSH token of %s' % (by, name), 'warn', who=by)
""",
 """    with SSHOTP_LOCK:       # a sign-in at that moment wrote it back (1.0.319)
        store.drop_meta(sshotp_key(name))
    store.add_event('settings', '%s removed the SSH token of %s' % (by, name), 'warn', who=by)
"""),
("""    \"\"\"The token's own row: when it was last used, or last failed.\"\"\"
    rec = sshotp_get(store, name)
    if rec:
        if ok:
            rec.update(used_at=time.time(), used_on=node_name())
        else:
            rec['failed_at'] = time.time()
        store.set_meta(sshotp_key(name), json.dumps(rec))
""",
 """    \"\"\"The token's own row: when it was last used, or last failed - under the lock (1.0.319):
    a token removed or made again at that moment came back as it was.\"\"\"
    with SSHOTP_LOCK:
        rec = sshotp_get(store, name)
        if rec:
            if ok:
                rec.update(used_at=time.time(), used_on=node_name())
            else:
                rec['failed_at'] = time.time()
            store.set_meta(sshotp_key(name), json.dumps(rec))
"""),
])

edit('87k_kerberos.py', [
("""KRB5_MECH = bytes.fromhex('2a864886f712010202')          # 1.2.840.113554.1.2.2
""",
 """KRB5_MECH = bytes.fromhex('2a864886f712010202')          # 1.2.840.113554.1.2.2
KRB5_MECH_MS = bytes.fromhex('2a864882f712010202')       # 1.2.840.48018.1.2.2 - Windows' (1.0.319)
"""),
("""        if got != KRB5_MECH:
""",
 """        if got not in (KRB5_MECH, KRB5_MECH_MS):
"""),
])

edit('90u_osusers.py', [
("""OSU_WORK = {'busy': False, 'since': 0.0, 'seen': 0.0}
""",
 """OSU_WORK = {'busy': False, 'since': 0.0, 'seen': 0.0}
OSU_ASK_LOCK = threading.Lock()     # this node's asks, read and written back (1.0.319)
"""),
("""    for n in nodes:
        k = node_key('host:users:want', n)
        try:
            had = json.loads(store.get_meta(k) or '[]')
        except ValueError:
            had = []
        had = [x for x in (had if isinstance(had, list) else [had])
               if isinstance(x, dict) and time.time() - fnum(x.get('at')) < 3600]
        had.append(dict(ask, id=secrets.token_hex(6)))
        store.set_meta(k, json.dumps(had[-20:]))
""",
 """    for n in nodes:
        k = node_key('host:users:want', n)
        with OSU_ASK_LOCK:  # two asks at once, or the hashes' clean-up: one was lost (1.0.319)
            try:
                had = json.loads(store.get_meta(k) or '[]')
            except ValueError:
                had = []
            had = [x for x in (had if isinstance(had, list) else [had])
                   if isinstance(x, dict) and time.time() - fnum(x.get('at')) < 3600]
            had.append(dict(ask, id=secrets.token_hex(6)))
            store.set_meta(k, json.dumps(had[-20:]))
"""),
("""        k = node_key('host:users:want', n)
        try:
            had = json.loads(store.get_meta(k) or '[]')
        except ValueError:
            continue
        if not isinstance(had, list) or not any(isinstance(a, dict) and a.get('hash') for a in had):
            continue
        done = set(osu_now(store, n).get('done') or [])
        changed = False
        for a in had:
            if isinstance(a, dict) and a.get('hash') and (
                    a.get('id') in done or time.time() - fnum(a.get('at')) > 900):
                a.pop('hash', None)
                a['hash_gone'] = True
                changed = True
        if changed:
            store.set_meta(k, json.dumps(had))
""",
 """        k = node_key('host:users:want', n)
        done = set(osu_now(store, n).get('done') or [])
        with OSU_ASK_LOCK:
            try:
                had = json.loads(store.get_meta(k) or '[]')
            except ValueError:
                continue
            if not isinstance(had, list) or not any(isinstance(a, dict) and a.get('hash') for a in had):
                continue
            changed = False
            for a in had:
                if isinstance(a, dict) and a.get('hash') and (
                        a.get('id') in done or time.time() - fnum(a.get('at')) > 900):
                    a.pop('hash', None)
                    a['hash_gone'] = True
                    changed = True
            if changed:
                store.set_meta(k, json.dumps(had))
"""),
])

edit('87d_dbtls.py', [
("""        if not mode and kind in ('replicated', 'local'):
            # The wish of none written before the switch (1.0.270): after it, the follow saw the
            # node without TLS and the wish still with it - and encrypted it again at once.
            _dbtls_want_set(store, mode, by)
        try:
            got = dbtls_switch(daemon, mode, ca, by)
        except Exception:
""",
 """        was_want = None
        if not mode and kind in ('replicated', 'local'):
            # The wish of none written before the switch (1.0.270): after it, the follow saw the
            # node without TLS and the wish still with it - and encrypted it again at once.
            # Not when high security refuses it, and put back when the switch did not go
            # (1.0.319): the nodes stayed on TLS and the wish said none for good.
            _dbtls_hisec(mode, store)
            was_want = _dbtls_want(store, derive=False)
            _dbtls_want_set(store, mode, by)
        try:
            got = dbtls_switch(daemon, mode, ca, by)
        except Exception:
            if isinstance(was_want, dict) and str(was_want.get('mode') or ''):
                try:
                    store.set_meta(DBTLS_WANT_KEY, json.dumps(was_want))
                except Exception:                       # noqa: BLE001
                    pass
"""),
("""    if dbtls_kind() not in ('local', 'replicated') or not CONFIG.get('db_tls'):
        DBTLS_WORK['fails'] = 0
        return
    try:
        daemon.store.db.value('SELECT 1')
""",
 """    if dbtls_kind() not in ('local', 'replicated') or not CONFIG.get('db_tls') or db_agent_here():
        # Never for a server of an agent's (1.0.319): it is across a network - anybody between
        # could have the TLS fail and the node then sent all of it in the clear.
        DBTLS_WORK['fails'] = 0
        return
    try:
        daemon.store.db.value('SELECT 1')
"""),
])

edit('90d_dbagent.py', [
("""    for v in db_agent_servers(store) if db_agent_on() else []:
""",
 """    # Every node's (1.0.319): a node without an agent of its own leading the alerts said none
    # of the other node's server.
    for v in db_agent_servers(store):
"""),
])

edit('90s_snmp.py', [
("""class SnmpAgent(object):
""",
 """class SnmpAgent(object):
    salt_lock = threading.Lock()    # answers and traps from two threads (1.0.319)
"""),
("""            self.salt = (self.salt + 1) & 0xFFFFFFFFFFFFFFFF
            priv = self.salt.to_bytes(8, 'big')
""",
 """            with self.salt_lock:                # one IV never twice under one key (1.0.319)
                self.salt = (self.salt + 1) & 0xFFFFFFFFFFFFFFFF
                priv = self.salt.to_bytes(8, 'big')
"""),
])
