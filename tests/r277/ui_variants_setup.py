# ui_variants_setup.py up | set KEY=VAL ... | down - the installed server for ui_variants.js: Windows (the
# test realm of tests/krb, its keytab) and a certificate (the PKI of tests/cert, nginx on 8443) both put in,
# then the switches set through the pages as the local administrator (root's otp --set where the pages
# would refuse: no password at all from a password's sign-in).
import json, os, subprocess, sys, time
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]] + sys.argv[1:]
what = sys.argv[1:]


def run(*a):
    r = subprocess.run([sys.executable] + list(a), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('%s: %s %s' % (a, r.stdout[-400:], r.stderr[-400:]))
    return r.stdout


if what[0] == 'up':
    run(T + '/cert/ui_cert_setup.py', 'up')
    run(T + '/krb/ui_krb_setup.py', 'up', 'on')
elif what[0] == 'set':
    args = []
    for kv in what[1:]:
        args += ['--set', kv]
    subprocess.run(['otp'] + args, check=True, capture_output=True)
    time.sleep(4)
elif what[0] == 'down':
    subprocess.run(['otp', '--set', 'admin_password_off=0', '--set', 'admin_cert_auto=0', '--set', 'admin_kerberos_auto=0'],
                   capture_output=True)
    time.sleep(3)
    run(T + '/krb/ui_krb_setup.py', 'down')
    run(T + '/cert/ui_cert_setup.py', 'down')
print('done', ' '.join(what))
