"""1.0.324 (deploy, OUTDIR): the balancers' networks all taken, or refused - never cut at 64 without
a word."""
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
("""    nets = []
    for w in (rp.get('from') or [])[:64]:
""",
 """    nets = []
    # All of them, or refused (1.0.324): the 65th and on were left out without a word - each
    # balancer past them was taken for the client, and its clients passed the lists as it.
    if len(rp.get('from') or []) > 256:
        raise Refused('realip: %d networks of balancers - 256 at most' % len(rp.get('from') or []))
    for w in (rp.get('from') or []):
"""),
])
