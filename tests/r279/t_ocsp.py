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


P = free(7)
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
# 1.0.279 (hunt): a forged responder whose name is openssl's own words, and a real "revoked" answer that
# carries one more certificate whose comment is a line "<file>: good"
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', D + '/fake2.key', '-out', D + '/fake2.pem',
                '-days', '2', '-subj', '/CN=Response verify OK'], check=True, capture_output=True)
responder(P + 5, D + '/ocsp-index.txt', D + '/fake2.pem', D + '/fake2.key', D + '/issuing.pem')
open(D + '/evil.cnf', 'w').write('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=x\n[ext]\n'
                                 'nsComment=DER:16:0f:0a:2f:74:6d:70:2f:78:3a:20:67:6f:6f:64:0a\n')
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', D + '/evil.key', '-out', D + '/evil.pem',
                '-days', '2', '-config', D + '/evil.cnf'], check=True, capture_output=True)
log = open(D + '/ocsp-%d.log' % (P + 6), 'w')
procs.append(subprocess.Popen(['openssl', 'ocsp', '-index', D + '/db/index.txt', '-port', str(P + 6), '-rsigner', D + '/ocsp-i.pem',
                               '-rkey', D + '/ocsp-i.key', '-CA', D + '/issuing.pem', '-rother', D + '/evil.pem', '-ndays', '1'],
                              stdout=log, stderr=subprocess.STDOUT))
for _ in range(75):
    if 'waiting for OCSP client connections' in open(D + '/ocsp-%d.log' % (P + 6)).read():
        break
    time.sleep(0.2)

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
        g.get('OCSP_DOWN', {}).clear()
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
    k, why = check('alice', 'only', own='http://127.0.0.1:%d/' % (P + 5))
    ok('a forged answer from a responder named "Response verify OK": no answer - unavailable', k == 'unavailable', why)
    k, why = check('bob', 'only', own='http://127.0.0.1:%d/' % (P + 6))
    ok('bob\'s real "revoked" answer carrying a certificate whose comment says "<file>: good": revoked', k == 'revoked', why)
    k, why = check('alice', 'first', crl=0)
    ok('first with CRLs off, the responder answering: taken', k == 'OK', why)
    k, why = check('dan', 'first', crl=0)
    ok('first with CRLs off, the responder dead: no sign-in', k == 'unavailable', why)

    # 1.0.279 (review): the issuing authority renewed with a new key under the same name (AD CS), put in
    # after the old one: the authority whose key signed the certificate is the one asked
    P7 = free(1)
    sh = lambda *a: subprocess.run(list(a), check=True, capture_output=True, cwd=D, env=dict(os.environ, UPN='zed@corp.example'))
    import shutil
    shutil.copytree(D + '/rootdb', D + '/rootdb2')
    os.makedirs(D + '/db2/new')
    open(D + '/db2/index.txt', 'w').close()
    open(D + '/db2/serial', 'w').write('2000\n'); open(D + '/db2/crlnumber', 'w').write('2000\n')
    cnf = open(D + '/ca.cnf').read().replace(D + '/db\n', D + '/db2\n').replace(D + '/rootdb\n', D + '/rootdb2\n')
    cnf = cnf.replace(D + '/issuing.pem', D + '/issuing2.pem').replace(D + '/issuing.key', D + '/issuing2.key')
    cnf += ('[issuing2_ext]\nbasicConstraints = critical,CA:TRUE,pathlen:0\nkeyUsage = critical,keyCertSign,cRLSign\n'
            'subjectKeyIdentifier = hash\nauthorityKeyIdentifier = keyid\ncrlDistributionPoints = URI:http://127.0.0.1:%d/root2.crl\n'
            '[person2]\nbasicConstraints = CA:FALSE\nkeyUsage = critical,digitalSignature,keyEncipherment\n'
            'extendedKeyUsage = clientAuth,1.3.6.1.4.1.311.20.2.2\n'
            'subjectAltName = otherName:1.3.6.1.4.1.311.20.2.3;UTF8:${ENV::UPN}\nsubjectKeyIdentifier = hash\n'
            'authorityKeyIdentifier = keyid\ncrlDistributionPoints = URI:http://127.0.0.1:%d/issuing.crl\n'
            'authorityInfoAccess = OCSP;URI:http://127.0.0.1:%d/\n') % (P, P, P7)
    open(D + '/ca2.cnf', 'w').write(cnf)
    sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'issuing2.key', '-out', 'issuing2.csr',
       '-subj', '/DC=example/DC=corp/CN=Corp Issuing CA')
    sh('openssl', 'ca', '-batch', '-config', 'ca2.cnf', '-name', 'rootca', '-extensions', 'issuing2_ext',
       '-in', 'issuing2.csr', '-out', 'issuing2.pem', '-notext')
    for who in ('zed', 'zoe'):
        sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', who + '.key', '-out', who + '.csr', '-subj', '/CN=' + who)
        sh('openssl', 'ca', '-batch', '-config', 'ca2.cnf', '-extensions', 'person2', '-in', who + '.csr', '-out', who + '.pem', '-notext')
    sh('openssl', 'ca', '-config', 'ca2.cnf', '-revoke', 'zed.pem', '-crl_reason', 'keyCompromise')
    sh('openssl', 'ca', '-config', 'ca2.cnf', '-name', 'rootca', '-gencrl', '-out', 'root2.crl.pem')
    sh('openssl', 'crl', '-in', 'root2.crl.pem', '-outform', 'DER', '-out', 'www/root2.crl')
    responder(P7, D + '/db2/index.txt', D + '/issuing2.pem', D + '/issuing2.key', D + '/issuing2.pem')
    open(D + '/cas2.pem', 'w').write(open(D + '/cas.pem').read() + open(D + '/issuing2.pem').read())
    CAS = D + '/cas2.pem'
    g['CERT_CA_FILE'] = pathlib.Path(CAS)
    cas = g['cert_ca_facts'](None)
    two = [c for c in cas if 'Corp Issuing CA' in c['subject'] and c['subject'].startswith('CN=')]
    ok('two authorities of one name put in, the old first', len(two) == 2 and two[0]['ski'] and two[0]['ski'] != two[1]['ski'],
       [c['ski'] for c in two])
    zf = g['cert_facts'](open(D + '/zed.pem').read())
    got = g['ocsp_parents'](zf, cas)
    ok('...zed\'s: the new one (the key id it names)', len(got) == 1 and got[0]['ski'] == two[1]['ski'] == zf['aki'])
    af = g['cert_facts'](open(D + '/alice.pem').read())
    got = g['ocsp_parents'](dict(af, aki='', _leafpem=open(D + '/alice.pem').read()), cas)
    ok('...alice\'s with no key id named: the one whose key verifies her (openssl)', len(got) == 1 and got[0]['ski'] == two[0]['ski'])
    k, why = check('zed', 'only')
    ok('zed (revoked, signed by the renewed key): asked with the new key - revoked', k == 'revoked', (k, why))
    k, why = check('zoe', 'only')
    ok('zoe (good, renewed key): taken', k == 'OK', (k, why))
    k, why = check('alice', 'only')
    ok('alice (the old key) beside it: taken', k == 'OK', (k, why))
    ch = g['cert_chain'](af, cas)
    ok('alice\'s chain: her own authority, not the renewed one of its name', [c['ski'] for c in ch if 'Issuing' in c['subject']] == [two[0]['ski']],
       [c['subject'] for c in ch])
    with g['OCSP_LOCK']:
        keys = list(g['OCSP_CACHE'])
    ok('an answer kept by the authority asked too', keys and all(k.count('|') == 3 for k in keys), keys)
    # the renewed authority revoked by the root's CRL, it names no responder: held to that CRL even with
    # CRLs off in "only"
    sh('openssl', 'ca', '-config', 'ca2.cnf', '-name', 'rootca', '-revoke', 'issuing2.pem')
    sh('openssl', 'ca', '-config', 'ca2.cnf', '-name', 'rootca', '-gencrl', '-out', 'root2.crl.pem')
    sh('openssl', 'crl', '-in', 'root2.crl.pem', '-outform', 'DER', '-out', 'www/root2.crl')
    k, why = check('zoe', 'only', crl=0)
    ok('only, CRLs off: an authority above with no responder is held to its CRL - revoked there, no sign-in', k == 'revoked', (k, why))
    k, why = check('zoe', 'first', crl=0)
    ok('...first, CRLs off: the same', k == 'revoked', (k, why))
    CAS = D + '/cas.pem'
    g['CERT_CA_FILE'] = pathlib.Path(CAS)
    k, why = check('alice', 'only', crl=0)
    ok('...alice (her authority has a responder): taken', k == 'OK', (k, why))
    # a responder that does not answer: not asked again for a minute, whoever's certificate
    C.update(admin_cert_crl=1, admin_cert_ocsp='first', admin_cert_ocsp_url='')
    with g['OCSP_LOCK']:
        g['OCSP_CACHE'].clear()
    g['OCSP_DOWN'].clear()
    dead = 'http://127.0.0.1:%d/' % (P + 3)
    try:
        g['ocsp_ask'](dead, g['cert_facts'](open(D + '/dan.pem').read()), open(D + '/dan.pem').read(), open(D + '/issuing.pem').read())
    except g['CrlRefused']:
        pass
    t0 = time.time()
    try:
        g['ocsp_ask'](dead, af, open(D + '/alice.pem').read(), open(D + '/issuing.pem').read()); k = 'asked'
    except g['CrlRefused'] as e:
        k = str(e)
    ok('a dead responder: another person\'s certificate not asked of it within the minute', 'no answer' in k and time.time() - t0 < 0.5 and dead in g['OCSP_DOWN'], k)

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
