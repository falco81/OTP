"""1.0.324 (parts): the balancers' networks 256 at most, said when saved."""
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


edit('00_head.py', [
("""    if key == 'web_proxy_from':
        for one in [w for w in re.split(r'[\\s,;]+', str(got)) if w]:
""",
 """    if key == 'web_proxy_from':
        if len([w for w in re.split(r'[\\s,;]+', str(got)) if w]) > 256:
            # As root's helper takes them (1.0.324): it cut them at 64 without a word.
            raise BadSetting('web_proxy_from: 256 networks at most')
        for one in [w for w in re.split(r'[\\s,;]+', str(got)) if w]:
"""),
])

edit('50_storage.py', [
("""        suffix = user.rsplit('@', 1)[1].lower() if '@' in user else ''
        realms = [r for r in self.realms() if r.get('enabled')]
        for r in realms:
            if str(r.get('suffix') or '').lower() == suffix and r.get('suffix') != '*':
                return r
        if suffix:
            # Taken as one of a realm's other suffixes (1.0.117).
            for r in realms:
                if suffix in (r.get('aliases') or []):
                    return r
""",
 """        suffix = user.rsplit('@', 1)[1].lower() if '@' in user else ''
        every = self.realms()
        realms = [r for r in every if r.get('enabled')]
        # A realm of its own switched off is none (1.0.324), as a client's narrowest range is:
        # its people were taken by the realm of everything else - a code alone, no password.
        for r in every:
            if str(r.get('suffix') or '').lower() == suffix and r.get('suffix') != '*':
                return r if r.get('enabled') else None
        if suffix:
            # Taken as one of a realm's other suffixes (1.0.117).
            for r in every:
                if suffix in (r.get('aliases') or []):
                    return r if r.get('enabled') else None
"""),
])

edit('80_daemon.py', [
("""        if names is None:
            rows = self.store.db.rows("SELECT name FROM tokens WHERE COALESCE(display, '') = '' "
                                      "ORDER BY id LIMIT %d" % int(limit))
            names = [r['name'] for r in rows]
""",
 """        if names is None:
            # On from where the last look stopped (1.0.324): the first hundred that no directory
            # knows were looked at every hour, and the tokens after them never.
            after = int(getattr(self, '_fill_after', 0) or 0)
            rows = self.store.db.rows("SELECT id, name FROM tokens WHERE COALESCE(display, '') = '' "
                                      "AND id > ? ORDER BY id LIMIT %d" % int(limit), (after,))
            self._fill_after = rows[-1]['id'] if len(rows) >= int(limit) else 0
            names = [r['name'] for r in rows]
"""),
])


# 256 networks need more than 500 letters.
edit('00_head.py', [
("        most = 64 if key in ('totp_issuer', 'totp_label') else (20000 if tall else 500)\n",
 "        most = 64 if key in ('totp_issuer', 'totp_label') else (20000 if tall else 500)\n        # 256 networks of balancers (1.0.324) take more than 500 letters: some 40 went in.\n        if key == 'web_proxy_from':\n            most = 256 * 50\n"),
])
