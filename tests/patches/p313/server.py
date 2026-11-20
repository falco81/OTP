"""1.0.313 (parts): what "Wrong passwords before a pause" does, said as it is done."""
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
("""    'portal_tries': 'Wrong passwords from one address on the enrolment pages before it has '
                    'to wait.',""",
 """    # Said as it is counted (1.0.313): since 1.0.265 one address waits after ten times this many
    # (at least 50) and one name after four times - "from one address" was no longer so.
    'portal_tries': 'Wrong passwords on the enrolment pages before a pause: one name waits after '
                    'four times this many, one address after ten times this many and at least 50 '
                    '(a whole office may come from one address).',"""),
("""    'login_tries': 'Wrong passwords from one address before it has to wait.',""",
 """    'login_tries': 'Wrong passwords (and wrong codes of the second step) before a pause: one name '
                   'waits after four times this many, one address after ten times this many and '
                   'at least 50 (a whole office may come from one address). Locked out shows '
                   'each count as it stands.',"""),
])
