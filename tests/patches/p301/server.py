# 1.0.301: SELinux on a pane of its own (Settings → SELinux) - every link to it goes there.
#   python3 server.py PARTS OUTDIR
import sys
P = sys.argv[1].rstrip('/') + '/'
O = sys.argv[2].rstrip('/') + '/'


def edit(f, pairs, base=P):
    s = open(base + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(base + f, 'w').write(s)


edit('88h_hisec.py', [("'SELinux on %s: %s' % (n, p), 'SELinux', 'hisec'))", "'SELinux on %s: %s' % (n, p), 'SELinux', 'selinux'))")])
edit('88z_alerts.py', [("""                    '; '.join(probs)[:300], 'hisec')""", """                    '; '.join(probs)[:300], 'selinux')""")])
s = open(P + '88n_after.py').read()
a, b = "{'where': 'pages', 'pane': 'hisec',", "{'where': 'pages', 'pane': 'selinux',"
assert s.count(a) == 3, s.count(a)
s = s.replace(a, b).replace('Settings → High security → SELinux', 'Settings → SELinux')
open(P + '88n_after.py', 'w').write(s)
edit('86b_rbackup.py', [('(Settings -> High security -> SELinux: make it ready', '(Settings -> SELinux: make it ready')])
edit('87e_selinux.py', [("""on the card (Settings → High security → '
                   'SELinux, "Put in what is selected")'""", """on the card (Settings → SELinux, '
                   '"Put in what is selected")'""")])
edit('deploy/otp_web.py', [("put in from Settings → High security → SELinux',", "put in from Settings → SELinux',")], base=O)
edit('docs/selinux.md', [("*Settings → High security → SELinux* (1.0.233), a card for each node;",
                          "*Settings → SELinux* (1.0.233; a pane of its own since 1.0.301), a card for each node;")], base=O)
print('ok')
