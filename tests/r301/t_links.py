"""t_links.py - 1.0.301: every link to SELinux goes to its own pane (Settings → SELinux): the security
check, the alert, what is to be done by hand; the words say so. Read from the program built.

    python3 t_links.py VERSION
"""
import sys
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.301'
src = open('/home/claude/build/out/otp-%s/otp.py' % V).read()
R = []


def ok(n, c):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n)


ok('the security check: SELinux opens the SELinux pane', "'SELinux on %s: %s' % (n, p), 'SELinux', 'selinux'))" in src)
ok('the alert: SELinux opens the SELinux pane', "'; '.join(probs)[:300], 'selinux')" in src)
ok('to be done by hand: three steps on the SELinux pane', src.count("{'where': 'pages', 'pane': 'selinux',") == 3)
ok('no "High security → SELinux" left in the words', 'High security → SELinux' not in src and 'High security -> SELinux' not in src)
page = open('/home/claude/build/out/otp-%s/web/admin/index.php' % V).read()
ok('the page: the pane and its rail button', 'id="pane-selinux"' in page and 'data-pane="selinux"' in page and page.count('id="se-host"') == 1
   and page.index('id="pane-selinux"') < page.index('id="se-host"'))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
