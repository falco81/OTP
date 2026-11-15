# t_ocsp.py VERSION - 1.0.279: OCSP and CRLs from the directory for the sign-in with a certificate, as the
# ocsp-ldap-kit says (isemon 1.10.348): the kit's test PKI (pki_ocsp.sh) with two real `openssl ocsp`
# responders on this machine, otp.py's own functions run on it. The matrix of the kit's README (alice, bob,
# dan, eve, hal, ida in off / first / only / both), gina's CRL in the directory, a forged answer, a
# responder of its own, the cache (the last good answer kept), what a node publishes (never a certificate),
# Ask again / Clear on a node, the LDAP address's guards, a CRL read raw from an LDAP entry.
import os, socket, subprocess, sys, tempfile, threading, time, http.server, socketserver, pathlib
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.279'
OTP_PY = os.environ.get('OTP_PY') or '/home/claude/build/out/otp-%s/otp.py' % V
HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


def free(n):
    """A port P with P..P+n-1 all free."""
    while True:
        s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close()
        good = True
        for i in range(n):
            t = socket.socket()
            try:
                t.bind(('0.0.0.0', p + i))
            except OSError:
                good = False
            finally:
                t.close()
        if good and p + n < 65000:
            return p


P = free(6)
D = tempfile.mkdtemp(prefix='t-ocsp-')
subprocess.run(['bash', HERE + '/pki_ocsp.sh', D, str(P)], check=True, capture_output=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=D + '/www', **k)

    def log_message(self, *a):
        pass


srv = socketserver.ThreadingTCPServer(('127.0.0.1', P), Quiet)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
procs = []


def responder(port, index, signer, key, ca):
    log = open(D + '/ocsp-%d.log' % port, 'w')
    pr = subprocess.Popen(['openssl', 'ocsp', '-index', index, '-port', str(port), '-rsigner', signer, '-rkey', key,
                           '-CA', ca, '-ndays', '1'], stdout=log, stderr=subprocess.STDOUT)
    procs.append(pr)
    end = time.time() + 15
    while time.time() < end:
        if 'waiting for OCSP client connections' in open(D + '/ocsp-%d.log' % port).read():
            return
        time.sleep(0.2)


responder(P + 2, D + '/ocsp-index.txt', D + '/ocsp-i.pem', D + '/ocsp-i.key', D + '/issuing.pem')
responder(P + 1, D + '/rootdb/index.txt', D + '/ocsp-r.pem', D + '/ocsp-r.key', D + '/root.pem')
# a forged responder: signs with a key of its own (a self-signed "responder" nobody put in)
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', D + '/fake.key', '-out', D + '/fake.pem',
                '-days', '2', '-subj', '/CN=Fake OCSP'], check=True, capture_output=True)
responder(P + 4, D + '/ocsp-index.txt', D + '/fake.pem', D + '/fake.key', D + '/issuing.pem')

try:
    src = open(OTP_PY).read()
    g = {'__name__': 'otp_t', '__file__': OTP_PY}
    exec(compile(src, 'otp.py', 'exec'), g)
    os.environ['OTP_CDP_LOCAL'] = '1'
    CAS = D + '/cas.pem'
    g['cert_cas'] = lambda store: [x.strip() + '\n-----END CERTIFICATE-----\n' for x in open(CAS).read().split('-----END CERTIFICATE-----') if 'BEGIN' in x]
    g['CERT_CA_FILE'] = pathlib.Path(CAS)
    C = g['CONFIG']

    def check(name, mode='off', crl=1, own=''):
        C.update(admin_cert_crl=crl, admin_cert_ocsp=mode, admin_cert_ocsp_url=own)
        with g['CRL_LOCK']:
            g['CRL_CACHE'].clear()
        with g['OCSP_LOCK']:
            g['OCSP_CACHE'].clear()
        try:
            g['cert_check'](None, open(D + '/%s.pem' % name).read())
            return 'OK', ''
        except g['CrlRefused'] as e:
            return 'unavailable', str(e)
        except g['CertError'] as e:
            return ('revoked' if 'revoked' in str(e) else 'certificate'), str(e)

    want = {
        'alice': {'off': 'OK', 'first': 'OK', 'only': 'OK', 'both': 'OK'},
        'bob': {'off': 'revoked', 'first': 'revoked', 'only': 'revoked', 'both': 'revoked'},
        'dan': {'off': 'OK', 'first': 'OK', 'only': 'unavailable', 'both': 'unavailable'},
        'eve': {'off': 'OK', 'first': 'OK', 'only': 'unavailable', 'both': 'OK'},
        'hal': {'off': 'revoked', 'first': 'OK', 'only': 'OK', 'both': 'revoked'},
        'ida': {'off': 'OK', 'first': 'certificate', 'only': 'certificate', 'both': 'certificate'},
    }
    for who, modes in want.items():
        for mode, w in modes.items():
            k, why = check(who, mode)
            ok('%-5s %-5s -> %s' % (who, mode, w), k == w, '%s: %s' % (k, why))
    k, why = check('alice', 'first')
    with g['OCSP_LOCK']:
        asked = sorted(c['subject'] for c in g['OCSP_CACHE'].values())
    ok('first: the person and the authority above (each of its own issuer\'s responder) asked',
       any('alice' in a for a in asked) and any('Corp Issuing CA' in a for a in asked), asked)

    # gina: her CRL only in the directory
    k, why = check('gina', 'off')
    ok('gina (CDP only in LDAP), LDAP off: refused - names no CRL over http', k == 'unavailable' and 'over http' in why, why)
    read = []
    g['CRL_LDAP']['fetch'] = lambda url: read.append(url) or open(D + '/www/issuing.crl', 'rb').read()
    k, why = check('gina', 'off')
    ok('gina, LDAP on: her CRL read from the directory - taken', k == 'OK', why)
    ok('...the CDP object read, the address as written', read and read[0].startswith('ldap:///CN=Corp%20Issuing%20CA'), read)
    rows = {c['url']: c for c in g['crls_now']()}
    lrow = next((c for u, c in rows.items() if u.startswith('ldap://')), None)
    ok('...kept as a CRL like any other (facts, never the CRL)', lrow and lrow['ok'] and 'pem' not in lrow, lrow)
    g['CRL_LDAP']['fetch'] = None

    # a forged answer, a responder of its own
    k, why = check('alice', 'only', own='http://127.0.0.1:%d/' % (P + 4))
    ok('a forged answer (a responder\'s own key): no answer - unavailable', k == 'unavailable' and 'signature' in why, why)
    k, why = check('eve', 'first', own='http://127.0.0.1:%d/' % (P + 2))
    with g['OCSP_LOCK']:
        eve = [c for c in g['OCSP_CACHE'].values() if 'eve' in c['subject']]
    ok('a responder of its own: eve (no AIA) asked of it - good - and the authority above by its CRL (the '
       'issuing CA\'s responder does not answer for the root\'s) - taken', k == 'OK' and eve and eve[0]['status'] == 'good', (k, why))
    k, why = check('eve', 'only', own='http://127.0.0.1:%d/' % (P + 2))
    ok('...only: the authority above unanswered by that responder - no sign-in', k == 'unavailable', why)
    k, why = check('alice', 'first', crl=0)
    ok('first with CRLs off, the responder answering: taken', k == 'OK', why)
    k, why = check('dan', 'first', crl=0)
    ok('first with CRLs off, the responder dead: no sign-in', k == 'unavailable', why)

    # the cache: the last good answer kept while the responder does not answer
    check('alice', 'only')
    with g['OCSP_LOCK']:
        key = next(k for k, c in g['OCSP_CACHE'].items() if 'alice' in c['subject'])
    procs[0].terminate(); procs[0].wait()
    C.update(admin_cert_ocsp='only')
    with g['OCSP_LOCK']:
        g['OCSP_CACHE'][key]['at'] -= 601
    try:
        g['cert_check'](None, open(D + '/alice.pem').read()); k = 'OK'
    except g['CertError'] as e:
        k = str(e)
    ok('the responder stopped, 601 s on: its last good answer kept until its next update - taken', k == 'OK', k)
    ok('...the error said', g['OCSP_CACHE'][key].get('err'))
    with g['OCSP_LOCK']:
        g['OCSP_CACHE'][key]['next'] = time.time() - 1
        g['OCSP_CACHE'][key]['tried'] = 0
    try:
        g['cert_check'](None, open(D + '/alice.pem').read()); k = 'OK'
    except g['CrlRefused'] as e:
        k = 'unavailable'
    except g['CertError'] as e:
        k = str(e)
    ok('...past its next update: no answer - no sign-in', k == 'unavailable', k)

    # what a node publishes, Ask again / Clear on a node
    now = g['ocsp_now']()
    ok('the answers kept: facts only, never a certificate', now and all('_pem' not in c and 'BEGIN' not in str(c) for c in now))
    got = g['ocsp_do']('fetch', key)
    ok('Ask again (the responder stopped): said not answered', got and not got[0]['ok'], got)
    got = g['ocsp_do']('clear', '')
    ok('Clear: every answer forgotten', got and not g['ocsp_now']())

    # the directory's CDP address: only a CDP object of Public Key Services, only its CRL
    L = g['cdp_ldap']
    good = 'ldap:///CN=Corp%20Issuing%20CA,CN=pki,CN=CDP,CN=Public%20Key%20Services,CN=Services,CN=Configuration,DC=corp,DC=example?certificateRevocationList?base?objectClass=cRLDistributionPoint'
    ok('an AD CS CDP address: read (DN, certificateRevocationList)', L(good) and L(good)[1] == 'certificateRevocationList')
    ok('...its delta: deltaRevocationList', L(good.replace('?certificateRevocationList?', '?deltaRevocationList;binary?'))[1] == 'deltaRevocationList')
    for bad, w in ((good.replace('certificateRevocationList', 'userPassword'), 'another attribute'),
                   (good.replace('?base?', '?sub?'), 'sub scope'),
                   ('ldap:///CN=Administrator,CN=Users,DC=corp,DC=example?certificateRevocationList', 'CN=Users'),
                   ('ldap://evil.example/CN=x?certificateRevocationList', 'not under Public Key Services')):
        ok('not read: %s' % w, L(bad) is None)
    os.environ.pop('OTP_CDP_LOCAL')
    ok('a responder of its own on a metadata address: not asked', not g['cdp_ok']('http://169.254.169.254/'))
    os.environ['OTP_CDP_LOCAL'] = '1'

    # a CRL read raw from an LDAP entry (binary kept beside the text)
    def tl(t, b):
        n = len(b)
        h = bytes([n]) if n < 128 else (bytes([0x81, n]) if n < 256 else bytes([0x82, n >> 8, n & 255]))
        return bytes([t]) + h + b
    crl = open(D + '/www/issuing.crl', 'rb').read()
    body = tl(0x04, b'CN=x') + tl(0x30, tl(0x30, tl(0x04, b'certificateRevocationList;binary') + tl(0x31, tl(0x04, crl))))
    e = g['Ldap']._entry_of(body)
    ok('an LDAP entry: the CRL kept as its bytes', e['raw'].get('certificateRevocationList;binary', [b''])[0] == crl)
finally:
    for pr in procs:
        try:
            pr.terminate(); pr.wait(5)
        except Exception:
            pass
    srv.shutdown()
print('ALL %d / %d' % (sum(R), len(R)))
