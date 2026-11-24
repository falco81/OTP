"""1.0.339 (parts): the link to the enrolment page in a token's mail with the "waiting to be
confirmed" words left empty; isemon's lines not sent while a target is down counted as dropped;
a realm of a totpcgi import that cannot be made said, the rest imported."""
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


edit('86_mail.py', [
("""    rows.append('<div style="height:18px;line-height:18px;font-size:1px">&nbsp;</div>')
    if pending and w['pending'].strip():
""",
 """    rows.append('<div style="height:18px;line-height:18px;font-size:1px">&nbsp;</div>')
    # The link even with its words left empty (1.0.339): without it a token to be confirmed went
    # with nothing saying where - its QR code never started working.
    if pending and (w['pending'].strip() or portal_url):
"""),
("""    if pending and w['pending'].strip():
        text += [plain('pending') + (' ' + portal_url if portal_url else ''), '']
""",
 """    if pending and (w['pending'].strip() or portal_url):
        text += [(plain('pending') + (' ' + portal_url if portal_url else '')).strip(), '']
"""),
])

edit('60_engine.py', [
("""                until, wait = self.down.get(key, (0.0, 0.0))
                if time.time() < until:
                    self.missed[key] += 1
""",
 """                until, wait = self.down.get(key, (0.0, 0.0))
                if time.time() < until:
                    self.missed[key] += 1
                    # Counted as dropped too (1.0.339), as the SIEM counts them (1.0.206): the
                    # metrics, SNMP and the alert said 0 through a whole outage.
                    self.dropped += 1
"""),
("""                self.down[key] = (time.time() + wait, wait)
                self.missed[key] += 1
""",
 """                self.down[key] = (time.time() + wait, wait)
                self.missed[key] += 1
                self.dropped += 1
"""),
])

edit('80_daemon.py', [
("""                store.realm_save({
                    'id': old['id'] if old else None, 'name': suffix if suffix != '*'
                    else 'default', 'suffix': suffix, 'directory': directory,
                    'lookup': lookup, 'auth_mode': 'otp', 'check_disabled': 1, 'nested': 0,
                    'groups': [{'group': g, 'reply': ''} for g in y['groups']],
                    'token_name': 'whole',
                    'note': 'brought over: the code alone, then the user filter and the '
                            'group filter the old handler applied'}, by)
                done['realms'] += 1
""",
 """                # One that cannot be made said, the rest imported (1.0.339), as a client is: it
                # stopped the import, and the clients, settings and tokens never came.
                try:
                    store.realm_save({
                        'id': old['id'] if old else None, 'name': suffix if suffix != '*'
                        else 'default', 'suffix': suffix, 'directory': directory,
                        'lookup': lookup, 'auth_mode': 'otp', 'check_disabled': 1, 'nested': 0,
                        'groups': [{'group': g, 'reply': ''} for g in y['groups']],
                        'token_name': 'whole',
                        'note': 'brought over: the code alone, then the user filter and the '
                                'group filter the old handler applied'}, by)
                except ValueError as e:
                    say('realm %s: not imported - %s' % (suffix, e))
                    continue
                done['realms'] += 1
"""),
])
