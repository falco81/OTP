"""1.0.313 (web, OUTDIR): the docs say how the wrong passwords are counted."""
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


edit(OUT / 'docs/operations.md', [
("""wait are: *Settings → Accounts* (`login_tries`, `login_wait_min`) and *The
enrolment pages* (`portal_tries`, `portal_wait_min`). Behind a load balancer""",
 """wait are: *Settings → Accounts* (`login_tries`, `login_wait_min`) and *The
enrolment pages* (`portal_tries`, `portal_wait_min`). The number set is not
the count of one address: one name waits after four times that many wrong
passwords, one address after ten times that many and at least 50 (with 5:
20 for a name, 50 for an address) - a whole office may come from one address.
Behind a load balancer"""),
])
