"""1.0.317 (parts): an unsigned EAP request dropped (RFC 3579); the administrator's second step gives its
send-limit places back when nothing went; a mail address the server cannot take (SMTPUTF8) said at once,
not tried for a day; a directory's authorities signed when changed and its removal signed; a PostgreSQL
restore numbers on before anybody else writes."""
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


edit('70_radius_server.py', [
("""        if pkt.code == ACCESS_REQUEST and pkt.all(33):
            self.drop(ip, port, pkt.text(1), 'Proxy-State without a Message-Authenticator '
                      '(the shape of a BlastRADIUS forgery)', pkt=pkt, client=client,
                      sparing=True)
            return False
""",
 """        if pkt.code == ACCESS_REQUEST and pkt.all(33):
            self.drop(ip, port, pkt.text(1), 'Proxy-State without a Message-Authenticator '
                      '(the shape of a BlastRADIUS forgery)', pkt=pkt, client=client,
                      sparing=True)
            return False
        # EAP-Message and no Message-Authenticator (1.0.317): RFC 3579 3.2 - silently discarded,
        # not refused (EAP is not taken here either way).
        if pkt.code == ACCESS_REQUEST and pkt.all(79):
            self.drop(ip, port, pkt.text(1), 'EAP-Message without a Message-Authenticator '
                      '(RFC 3579: discarded)', pkt=pkt, client=client, sparing=True)
            return False
"""),
])

edit('90m_mfa.py', [
("""    dkey = 'to:%s:%s' % (kind, str(dest or '').strip().lower())
    if not code_send_allowed(h.store, 'adm:' + str(s['name']).lower()) or \\
            not code_send_allowed(h.store, dkey):
        try:
""",
 """    dkey = 'to:%s:%s' % (kind, str(dest or '').strip().lower())
    akey = 'adm:' + str(s['name']).lower()
    a_ok = code_send_allowed(h.store, akey)
    d_ok = a_ok and code_send_allowed(h.store, dkey)
    if not d_ok:
        if a_ok:
            # The account's place given back (1.0.317): the address refused it, nothing went.
            portal_sends_back(h.store, akey)
        try:
"""),
("""    except (MailError, SmsError, ValueError) as e:
        # The place given back (1.0.255): nothing went, so nothing is counted - as until now.
        try:
            h.store.session_merge(s['id'], was, expect={'mfa_sent_at': t, 'mfa_sent': n + 1})
        except Exception:                               # noqa: BLE001
            pass
""",
 """    except (MailError, SmsError, ValueError) as e:
        # The place given back (1.0.255): nothing went, so nothing is counted - as until now.
        try:
            h.store.session_merge(s['id'], was, expect={'mfa_sent_at': t, 'mfa_sent': n + 1})
        except Exception:                               # noqa: BLE001
            pass
        # ...the account's and the address's too (1.0.317): five tries in a mail outage had the
        # administrator unable to sign in for the window after it was over.
        portal_sends_back(h.store, akey, dkey)
"""),
])

edit('86_mail.py', [
("""    except (smtplib.SMTPException, OSError) as e:
        if not isinstance(e, MailError):
            step('talking to it', False, e)
            raise MailError('the conversation with %s broke off: %s' % (host, e), steps,
                            permanent=int(getattr(e, 'smtp_code', 0) or 0) >= 500)
        raise
""",
 """    except (smtplib.SMTPException, OSError) as e:
        if not isinstance(e, MailError):
            step('talking to it', False, e)
            if isinstance(e, smtplib.SMTPNotSupportedError) and 'SMTPUTF8' in str(e):
                # An address with letters past ASCII before the @ (1.0.317), a server without
                # SMTPUTF8: it never goes - said at once, not tried again for a day.
                raise MailError('%s does not take an address with letters such as á or ř before '
                                'the @ (no SMTPUTF8): write it in plain letters' % host, steps,
                                permanent=True)
            raise MailError('the conversation with %s broke off: %s' % (host, e), steps,
                            permanent=int(getattr(e, 'smtp_code', 0) or 0) >= 500)
        raise
"""),
])

edit('50_storage.py', [
("""        pem = '\\n'.join(have)
        with self.lock:
            self.db.run('UPDATE directories SET ca = ? WHERE id = ?', (pem, int(ident)))
            self._dirs = None
""",
 """        pem = '\\n'.join(have)
        with self.lock:
            self.db.run('UPDATE directories SET ca = ? WHERE id = ?', (pem, int(ident)))
            self._dirs = None
            # Signed again (1.0.317): its authorities are signed, and a change left the directory
            # of the administrators refused by the guard - nobody of it signed in.
            name = self.db.value('SELECT name FROM directories WHERE id = ?', (int(ident),))
            if name:
                dbguard_directory_sign(self.db, name)
"""),
("""        self.db.run('DELETE FROM directories WHERE id = ?', (int(ident),))
        self._dirs = None
        if one:
            self._dirpw_move(one['name'], None)         # its own cap gone with it (1.0.234)
""",
 """        self.db.run('DELETE FROM directories WHERE id = ?', (int(ident),))
        self._dirs = None
        if one:
            self._dirpw_move(one['name'], None)         # its own cap gone with it (1.0.234)
            # Its removal signed (1.0.317), as an account's: the row put back as it was is refused.
            dbguard_directory_sign(self.db, one['name'])
"""),
])

edit('20_db.py', [
("""        try:
            counts = _load_tables(db, src, keep_logs, say, gzip)
            db.in_tx = False
            db.run('COMMIT')
        except BaseException:
            db.in_tx = False
            try:
                db.run('ROLLBACK')
            except Exception:                           # noqa: BLE001
                pass
            raise
    if db.engine == 'postgres':
        for table in TABLES:
            if table in ('meta', 'settings'):
                continue
            try:
                db.run("SELECT setval(pg_get_serial_sequence('%s', 'id'), "
                       "COALESCE((SELECT MAX(id) FROM %s), 0) + 1, false)" % (table, table))
            except Exception:
                pass
        # Odd or even again at once (1.0.94): MAX+1 can be the other node's
        # parity, and a row written before the caller set it collided there.
        if CONFIG.get('ha_mode') == 'replicated':
            try:
                ha_sequences(db, int(CONFIG.get('ha_slot') or 1))
            except Exception as e:                      # noqa: BLE001
                log('the numbering could not be set after loading: %s' % e, 'warn')
""",
 """        try:
            counts = _load_tables(db, src, keep_logs, say, gzip)
            db.in_tx = False
            db.run('COMMIT')
        except BaseException:
            db.in_tx = False
            try:
                db.run('ROLLBACK')
            except Exception:                           # noqa: BLE001
                pass
            raise
        # Still under the lock (1.0.317): RADIUS, the pages and the events waiting on it wrote
        # with the old numbers first - a duplicate key, the line or the sign-in lost.
        if db.engine == 'postgres':
            for table in TABLES:
                if table in ('meta', 'settings'):
                    continue
                try:
                    db.run("SELECT setval(pg_get_serial_sequence('%s', 'id'), "
                           "COALESCE((SELECT MAX(id) FROM %s), 0) + 1, false)" % (table, table))
                except Exception:
                    pass
            # Odd or even again at once (1.0.94): MAX+1 can be the other node's
            # parity, and a row written before the caller set it collided there.
            if CONFIG.get('ha_mode') == 'replicated':
                try:
                    ha_sequences(db, int(CONFIG.get('ha_slot') or 1))
                except Exception as e:                      # noqa: BLE001
                    log('the numbering could not be set after loading: %s' % e, 'warn')
"""),
])
