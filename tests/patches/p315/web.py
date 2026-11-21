"""1.0.315 (web, OUTDIR): the docs list the alerts, the outgoing mail and the sign-ins on the command line."""
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
("""otp --lockouts              # who is locked out, on every node;  --lockouts-clear all|KIND:WHO
""",
 """otp --lockouts              # who is locked out, on every node;  --lockouts-clear all|KIND:WHO
otp --alerts                # what is wrong now (exit 1 when anything is bad);  check / test / report / forget
otp --mailq                 # the outgoing mail;  open|failed|...  /  retry-all / drop-sent / drop-failed --yes
otp --mailq-one ID          # one mail and every try of it;  --mailq-retry ID,ID  /  --mailq-drop ID,ID --yes
otp --sessions              # who is signed in to the pages;  --session-end ID --yes
otp --firewall              # otp's firewall and who may reach the pages;  on / off --yes;  --web-access admin=any --yes
"""),
])
