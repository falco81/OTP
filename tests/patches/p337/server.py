"""1.0.337 (parts): an upgrade started on a node in maintenance no longer waits for good; a realm
renamed with another directory not compared with itself; clients.conf's yes/true/on and netmask;
totpcgi's realms of capital letters imported again; a .totp file with a BOM in a ZIP."""
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


edit('88_upgrade.py', [
("""    order = sorted(n for n in names if n != me) + ([me] if me in names else [])
""",
 """    order = sorted(n for n in names if n != me) + ([me] if me in names else [])
    # One in maintenance first (1.0.337): the node whose turn it was waited for it to be in
    # service again, it waited for its turn - "waiting" for good, no new upgrade taken.
    try:
        order.sort(key=lambda n: not bool(maintenance_row(store, n).get('on')))
    except Exception:                                   # noqa: BLE001
        pass
"""),
])

edit('50_storage.py', [
("""            for r in self.realms():
                if plain_names(r.get('token_name'), r.get('suffix')) and \\
                        str(r.get('name')).lower() != \\
""",
 """            for r in self.realms():
                # Not itself (1.0.337): renamed and given another directory in one save, the row as
                # it was was taken for another realm.
                if data.get('id') and str(r.get('id')) == str(data.get('id')):
                    continue
                if plain_names(r.get('token_name'), r.get('suffix')) and \\
                        str(r.get('name')).lower() != \\
"""),
])

edit('80_daemon.py', [
("""        addr = vals.get('ipaddr') or vals.get('ipv4addr') or vals.get('ipv6addr') or key
        out.append({'name': vals.get('shortname') or key, 'address': addr,
                    'secret': vals.get('secret', ''),
                    'require_ma': 1 if vals.get('require_message_authenticator') == 'yes'
                    else 0})
""",
 """        addr = vals.get('ipaddr') or vals.get('ipv4addr') or vals.get('ipv6addr') or key
        # FreeRADIUS 2's netmask (1.0.337): the network, not its first address alone.
        mask = str(vals.get('netmask') or '').strip()
        if mask.isdigit() and '/' not in addr:
            addr = '%s/%s' % (addr, mask)
        out.append({'name': vals.get('shortname') or key, 'address': addr,
                    'secret': vals.get('secret', ''),
                    # As FreeRADIUS takes it (1.0.337): true, on, Yes - the client lost the rule
                    # that it must sign (BlastRADIUS) on import.
                    'require_ma': 1 if str(vals.get('require_message_authenticator') or '').strip()
                    .lower() in ('yes', 'true', 'on', '1') else 0})
"""),
("""                if any(str(r.get('suffix')) == suffix for r in store.realms()) and not replace:
                    continue
""",
 """                # Of any letters (1.0.337): CORP.CZ in the hints, corp.cz kept - imported again,
                # the realm was made twice, refused, and nothing after it imported.
                if any(str(r.get('suffix')).lower() == suffix.lower() for r in store.realms()) and \\
                        not replace:
                    continue
"""),
("""                old = next((r for r in store.realms() if r.get('suffix') == suffix), None)
""",
 """                old = next((r for r in store.realms()
                            if str(r.get('suffix') or '').lower() == suffix.lower()), None)
"""),
])

edit('90_api.py', [
("""                got.append({'name': base, 'text': data.decode('utf-8', 'replace'),
""",
 """                # Its BOM left out (1.0.337), as the browser leaves it out of one file dropped
                # alone: one saved by Notepad was "not a base32 key" in a ZIP.
                got.append({'name': base, 'text': data.decode('utf-8-sig', 'replace'),
"""),
])
