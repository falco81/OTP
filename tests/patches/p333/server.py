"""1.0.333 (parts): a check of an SSH token or of an administrator's second step writes its row
only as it read it - one replaced or removed at that moment on the other node no longer comes
back; a sign-in ended for wrong codes gives no session to a right code waiting behind them."""
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


edit('50_storage.py', [
("""    def session_drop(self, ident):
""",
 """    def meta_json_update(self, k, change, rounds=8):
        \"\"\"A row of meta holding a JSON object changed where it is as it was read (1.0.333): the
        new value written only over the one `change` was given. `change(rec)` returns the new
        object, or None to leave it. The new object; None where the row is not there (never
        made again); False where `change` declined or it kept changing. Not for signed rows.\"\"\"
        for _round in range(rounds):
            raw = self.db.value('SELECT v FROM meta WHERE k = ?', (k,))
            if raw is None:
                return None
            rec = json_obj(raw)
            if rec is None:
                return None
            new = change(dict(rec))
            if new is None:
                return False
            if self.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (json.dumps(new), k, raw)):
                return new
        return False

    def session_drop(self, ident):
"""),
])

edit('87s_sshotp.py', [
("""    with SSHOTP_LOCK:
        rec = sshotp_get(store, name)
        if rec:
            if ok:
                rec.update(used_at=time.time(), used_on=node_name())
            else:
                rec['failed_at'] = time.time()
            store.set_meta(sshotp_key(name), json.dumps(rec))
""",
 """    with SSHOTP_LOCK:
        def change(rec):
            if ok:
                rec.update(used_at=time.time(), used_on=node_name())
            else:
                rec['failed_at'] = time.time()
            return rec
        # As it is in the database (1.0.333): a lock of this process alone did not keep the other
        # node's change out - a token removed there came back.
        store.meta_json_update(sshotp_key(name), change)
"""),
("""        if step is None or step <= int(rec.get('step') or 0):
            fails.append(now)
            rec['failed_at'] = now
            if step is None:
                rec['fails'] = int(rec.get('fails') or 0) + 1
            store.set_meta(sshotp_key(name), json.dumps(rec))
            return False, ('the code is not right' if step is None
                           else 'the code was used already - wait for the next one')
        rec.update(step=step, used_at=now, used_on=node_name())
        rec.pop('fails', None)
        store.set_meta(sshotp_key(name), json.dumps(rec))
        SSHOTP_FAILS.pop(name.lower(), None)
        return True, 'signed in'
""",
 """        same = rec.get('secret')

        # Written over the row as it is now, only while it is the same token (1.0.333): the whole
        # row read before written back put a token removed or made again on the other node meanwhile
        # back as it was - the old phone's codes good again; and wrong codes on both nodes at once
        # were counted as one.
        if step is None or step <= int(rec.get('step') or 0):
            fails.append(now)

            def failed(r):
                if r.get('secret') != same:
                    return None
                r['failed_at'] = now
                if step is None:
                    r['fails'] = int(r.get('fails') or 0) + 1
                return r
            store.meta_json_update(sshotp_key(name), failed)
            return False, ('the code is not right' if step is None
                           else 'the code was used already - wait for the next one')

        def used(r):
            if r.get('secret') != same or step <= int(r.get('step') or 0):
                return None
            r.update(step=step, used_at=now, used_on=node_name())
            r.pop('fails', None)
            return r
        if not store.meta_json_update(sshotp_key(name), used):
            fails.append(now)
            return False, 'the SSH token was changed meanwhile - try again'
        SSHOTP_FAILS.pop(name.lower(), None)
        return True, 'signed in'
"""),
])

edit('90m_mfa.py', [
("""                rec['keys'] = [used if k.get('id') == used['id'] else k for k in rec.get('keys') or []]
                h.store.set_meta(mfa_key(name), json.dumps(rec))
            token = _mfa_done(h, s, 'a passkey (%s)' % (used.get('name') or 'a device'))
""",
 """                def counted(r):
                    # Only while it is the same passkey (1.0.333): one taken away, or the second
                    # step reset, on the other node meanwhile was put back.
                    if r.get('kind') != 'passkey' or not any(k.get('id') == used['id']
                                                             for k in r.get('keys') or []):
                        return None
                    r['keys'] = [used if k.get('id') == used['id'] else k for k in r.get('keys') or []]
                    return r
                if not h.store.meta_json_update(mfa_key(name), counted):
                    raise ApiError(409, 'the second step of this account was changed meanwhile - '
                                        'sign in again')
            token = _mfa_done(h, s, 'a passkey (%s)' % (used.get('name') or 'a device'))
"""),
("""                rec['step'] = step
                h.store.set_meta(mfa_key(name), json.dumps(rec))
        else:
""",
 """                same = rec.get('secret')

                def stepped(r):
                    # Only while it is the same key (1.0.333), as for an SSH token.
                    if r.get('kind') != 'app' or r.get('secret') != same or \\
                            step <= int(r.get('step') or 0):
                        return None
                    r['step'] = step
                    return r
                if not h.store.meta_json_update(mfa_key(name), stepped):
                    raise ApiError(409, 'the second step of this account was changed meanwhile - '
                                        'sign in again')
        else:
"""),
("""    hours = max(0.05, (fnum(s.get('expires')) - time.time()) / 3600.0)
    token = h.store.session_new('admin', s['name'], s['role'], h.client_ip(), hours, data=data)
    h.store.session_drop(s['id'])
""",
 """    hours = max(0.05, (fnum(s.get('expires')) - time.time()) / 3600.0)
    # This sign-in still there, and taken by this request alone (1.0.333): one ended at the fifth
    # wrong code gave a session to a right code that waited behind them - a burst of guesses
    # was not held to five.
    if not h.store.db.run('DELETE FROM sessions WHERE id = ?', (int(s['id']),)):
        raise ApiError(401, 'this sign-in was ended - sign in again')
    token = h.store.session_new('admin', s['name'], s['role'], h.client_ip(), hours, data=data)
"""),
])
