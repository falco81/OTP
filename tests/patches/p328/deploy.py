"""1.0.328 (deploy, OUTDIR): port 80's names for the ACME CA kept as a set of otp's own - replaced
each time, taken away when ACME is off; the database agent does not begin a request the node
has stopped waiting for."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(OUT / 'deploy/otp_web.py', [
("""    where = http_block(main)
    if not where:
        return main
    block = main[where[0]:where[1]]
    new = block
    if 'acme-challenge' not in new:
""",
 """    where = http_block(main)
    if not where:
        return main
    block = main[where[0]:where[1]]
    new = block
    if names and 'acme-challenge' not in new:
"""),
("""    m = re.search(r'(?m)^(\\s*server_name\\s+)([^;#]*);', new)
    if m and names:
        have = m.group(2).split()
        base = [x for x in have if not x.startswith('otp-acme:')]
        want = base + [n for n in names if n not in base]
        if want != have:
            new = new[:m.start()] + m.group(1) + ' '.join(want) + ';' + new[m.end():]
    return main[:where[0]] + new + main[where[1]:] if new != block else main
""",
 """    m = re.search(r'(?m)^(\\s*server_name\\s+)([^;#]*);', new)
    if m:
        have = m.group(2).split()
        # otp's own names, written down beside them (1.0.328): each name ever ordered stayed
        # for good - an old VIP name on port 80 took another site's requests there. Replaced
        # as a set each time, taken away when ACME is off (names empty).
        mk = re.search(r'(?m)^[ \\t]*# otp-acme-names:([^\\n]*)\\n', new)
        if mk:
            mine = mk.group(1).split()
        elif not names:
            mine = None             # never put any here: left as it is
        else:
            # Written before 1.0.328: the first name (install.sh's) and those of the HTTPS
            # server stay; the others are otp's.
            tls = set()
            for t in re.finditer(r'(?m)^\\s*server_name\\s+([^;#]*);', main[:where[0]] + main[where[1]:]):
                tls.update(t.group(1).split())
            mine = [x for x in have[1:] if x not in tls]
        if mine is not None:
            base = [x for x in have if x not in mine and not x.startswith('otp-acme:')]
            add = [n for n in names if n not in base]
            want = base + add
            line = m.group(1) + ' '.join(want) + ';'
            note = ('%s# otp-acme-names: %s\\n' % (re.match(r'\\s*', m.group(1)).group(0).lstrip('\\n'),
                                                   ' '.join(add))) if add else ''
            new2 = new[:m.start()] + line + new[m.end():]
            if mk:
                new2 = re.sub(r'(?m)^[ \\t]*# otp-acme-names:[^\\n]*\\n', lambda _x: '', new2, count=1)
            m2 = re.search(r'(?m)^(\\s*server_name\\s+)([^;#]*);[^\\n]*\\n', new2)
            new2 = new2[:m2.end()] + note + new2[m2.end():]
            new = new2
    return main[:where[0]] + new + main[where[1]:] if new != block else main
"""),
])

edit(OUT / 'deploy/otp_db_agent.py', [
("""            else:
                out = self.long_op(op, args, node, base64.b64decode(msg.get('der') or ''))
""",
 """            else:
                try:
                    wait = float(req.get('wait_s') or 0)
                except (TypeError, ValueError):
                    wait = 0
                out = self.long_op(op, args, node, base64.b64decode(msg.get('der') or ''),
                                   until=(time.monotonic() + wait) if wait > 0 else None)
"""),
("""    def long_op(self, op, args, node, der=b''):
""",
 """    def long_op(self, op, args, node, der=b'', until=None):
"""),
("""        with self.work:
            if self.stopping:
                raise self.ops.Refused('the agent is stopping: again once it is started again')
""",
 """        with self.work:
            if self.stopping:
                raise self.ops.Refused('the agent is stopping: again once it is started again')
            if until is not None and time.monotonic() > until:
                # Waited behind another operation longer than the node waits (1.0.328): it said
                # failed already - done now, it changed pg_hba or the certificate behind its back.
                raise self.ops.Refused('%s waited for another operation longer than the node '
                                       'waits - not done; ask again' % op)
"""),
])
