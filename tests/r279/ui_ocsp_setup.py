# ui_ocsp_setup.py up | down - the installed server set up for ui_ocsp.js: the certificate sign-in of
# tests/cert (ui_cert_setup.py up), and beside its authorities those of the ocsp-ldap-kit's test PKI
# (pki_ocsp.sh on 18990: its CRLs served there, its two responders on 18991/18992), OCSP "first".
import base64, os, signal, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE + '/../cert')
D = '/tmp/claude-0/pki-ocsp'
P = 18990
PIDS = '/tmp/claude-0/ui_ocsp.pids'
what = sys.argv[1]


def stop():
    if os.path.exists(PIDS):
        for pid in open(PIDS).read().split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (OSError, ValueError):
                pass
        os.unlink(PIDS)


if what == 'up':
    subprocess.run([sys.executable, HERE + '/../cert/ui_cert_setup.py', 'up'], check=True)
    subprocess.run(['bash', HERE + '/pki_ocsp.sh', D, str(P)], check=True, capture_output=True)
    stop()
    pids = []
    pids.append(subprocess.Popen([sys.executable, '-m', 'http.server', str(P), '--bind', '127.0.0.1', '--directory', D + '/www'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True).pid)
    for port, index, signer, key, ca in ((P + 2, 'ocsp-index.txt', 'ocsp-i.pem', 'ocsp-i.key', 'issuing.pem'),
                                         (P + 1, 'rootdb/index.txt', 'ocsp-r.pem', 'ocsp-r.key', 'root.pem')):
        log = open('%s/ocsp-%d.log' % (D, port), 'w')
        pids.append(subprocess.Popen(['openssl', 'ocsp', '-index', D + '/' + index, '-port', str(port), '-rsigner', D + '/' + signer,
                                      '-rkey', D + '/' + key, '-CA', D + '/' + ca, '-ndays', '1'], stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True).pid)
    open(PIDS, 'w').write(' '.join(str(p) for p in pids))
    time.sleep(2)
    got = subprocess.run(['otp', '--cert-ca', D + '/cas.pem'], capture_output=True, text=True)
    if got.returncode:
        raise SystemExit('cert-ca: %s' % got.stderr)
    subprocess.run(['otp', '--set', 'admin_cert_ocsp=first'], check=True, capture_output=True)
    time.sleep(4)
    print('up')
else:
    stop()
    subprocess.run(['otp', '--set', 'admin_cert_ocsp=off', '--set', 'admin_cert_ocsp_url=', '--set', 'admin_cert_crl_ldap=0'],
                   capture_output=True)
    subprocess.run([sys.executable, HERE + '/../cert/ui_cert_setup.py', 'down'], capture_output=True)
    print('down')
