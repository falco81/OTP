#!/usr/bin/env python3
"""agent_client.py - a minimal client of otp-db-agent's protocol (standard library + openssl),
written for the kit: to talk to an agent by hand, and to check an otp port of the agent (or of the
node's client) against otp's - byte for byte the same canonical strings.

    agent_client.py join DIR NODE < code        a throwaway authority in DIR, a client certificate
                                                (clientAuth, CN otp-NODE) from it, a signing key;
                                                GET /v1/enroll/key (checked against the
                                                code's k), /v1/enroll/begin then /finish with
                                                the secret, the signing key and the client
                                                certificate's fingerprint SEALED to the agent's
                                                enroll key (1.0.115) - the agent's certificate
                                                pinned from the code
    agent_client.py op DIR OP ['{"k": "v"}']   one signed /v1/op, the answer's signature checked
    agent_client.py refusals DIR                what the agent must refuse, and how

DIR keeps: code.json (the code's fields but the secret), pins.json, ca.crt/ca.key, client.crt/key,
sign.key (0600), node. The node name must be unique on that agent (a join replaces the entry of the
same name). Test agents only: this is not otp's client (that is reference/engine_db_agent.py).
"""
import base64
import hashlib
import hmac
import http.client
import json
import os
import secrets
import ssl
import subprocess
import sys
import time

PROTO = 'otp-db-agent/1'
SEAL = 'otp-db-agent-seal/1'     # the first line of what is sealed to the agent's enroll key


def pub_fp(pem):
    """sha256 of a public key's DER (SubjectPublicKeyInfo) - the join code's k."""
    body = ''.join(x.strip() for x in pem.splitlines() if x.strip() and not x.startswith('-----'))
    return hashlib.sha256(base64.b64decode(body)).hexdigest()


def seal(pub, fields):
    """The lines sealed to the agent's enroll key: RSA-OAEP, SHA-256 (and MGF1 SHA-256)."""
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.pem') as f:
        f.write(pub)
        f.flush()
        got = subprocess.run(['openssl', 'pkeyutl', '-encrypt', '-pubin', '-inkey', f.name,
                              '-pkeyopt', 'rsa_padding_mode:oaep', '-pkeyopt', 'rsa_oaep_md:sha256',
                              '-pkeyopt', 'rsa_mgf1_md:sha256'],
                             input='\n'.join([SEAL] + list(fields)).encode(), capture_output=True)
    if got.returncode:
        raise SystemExit('openssl pkeyutl: ' + got.stderr.decode(errors='replace').strip())
    return base64.b64encode(got.stdout).decode()


def sh(*args, data=None):
    got = subprocess.run(['openssl'] + list(args), input=data, capture_output=True, text=True)
    if got.returncode:
        raise SystemExit('openssl %s: %s' % (args[0], got.stderr.strip()))
    return got.stdout


def code_read(code):
    code = code.strip()
    assert code.startswith('ODBA1.'), 'a join code starts with ODBA1.'
    raw = code[6:]
    return json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))


def call(host, port, path, body, pins, cert=None, headers=None, method='POST'):
    """One request with the agent's certificate pinned BEFORE anything is sent."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if cert:
        ctx.load_cert_chain(*cert)
    c = http.client.HTTPSConnection(host, int(port), context=ctx, timeout=60)
    try:
        c.connect()
        fp = hashlib.sha256(c.sock.getpeercert(True)).hexdigest()
        if fp not in pins:
            raise SystemExit('the agent answers with %s… - not pinned' % fp[:16])
        c.request(method, path, body=body, headers=dict(headers or {}, **{'Content-Type': 'application/json'}))
        r = c.getresponse()
        return r.status, r.read(), dict(r.getheaders())
    finally:
        c.close()


def signed_headers(key_hex, node, body, ts=None, nonce=None):
    ts = ts or '%.3f' % time.time()
    nonce = nonce or secrets.token_hex(16)
    text = '\n'.join([PROTO, 'POST', '/v1/op', node, ts, nonce, hashlib.sha256(body).hexdigest()]).encode()
    return {'X-Otp-Node': node, 'X-Otp-Time': ts, 'X-Otp-Nonce': nonce,
            'X-Otp-Sign': hmac.new(bytes.fromhex(key_hex), text, 'sha256').hexdigest()}


def reply_ok(key_hex, nonce, body, sig):
    want = hmac.new(bytes.fromhex(key_hex), ('reply\n%s\n' % nonce).encode() + hashlib.sha256(body).digest(),
                    'sha256').hexdigest()
    return hmac.compare_digest(want, sig or '')


def load(d):
    r = lambda n: open(os.path.join(d, n)).read().strip()
    return (json.loads(r('code.json')), json.loads(r('pins.json')), r('node'), r('sign.key'),
            (os.path.join(d, 'client.crt'), os.path.join(d, 'client.key')))


def join(d, node):
    data = code_read(sys.stdin.readline())
    os.makedirs(d, mode=0o700, exist_ok=True)
    p = lambda n: os.path.join(d, n)
    sh('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes', '-keyout', p('ca.key'),
       '-out', p('ca.crt'), '-days', '30', '-subj', '/CN=kit test authority',
       '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    sh('req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes', '-keyout', p('client.key'),
       '-out', p('client.csr'), '-subj', '/CN=otp-%s' % node)
    with open(p('ext.cnf'), 'w') as f:
        f.write('extendedKeyUsage=clientAuth\nkeyUsage=critical,digitalSignature\n')
    sh('x509', '-req', '-in', p('client.csr'), '-CA', p('ca.crt'), '-CAkey', p('ca.key'), '-CAcreateserial',
       '-out', p('client.crt'), '-days', '30', '-extfile', p('ext.cnf'))
    key = secrets.token_hex(32)
    pins = [data['f']]
    # The agent's enroll key, checked against the code's k (1.0.115): what is sealed to it never
    # passes the agent's network side in clear - and that side cannot put another key in.
    if not data.get('k'):
        raise SystemExit('a code of an agent before 1.0.115 (no k): upgrade the agent, then a new code')
    st, got, _ = call(data['h'], data['p'], '/v1/enroll/key', None, pins, method='GET')
    pub = json.loads(got)['pub']
    if st != 200 or pub_fp(pub) != data['k']:
        raise SystemExit('the agent\'s enroll key is not the one in the code')
    cid = str(data.get('i') or '')
    ask = {'code_id': cid, 'node': node, 'seal': seal(pub, ['begin', cid, node, data['s']])}
    st, got, _ = call(data['h'], data['p'], '/v1/enroll/begin', json.dumps(ask).encode(), pins)
    began = json.loads(got)
    print('begin', st, {k: v for k, v in began.items() if k != 'token'})
    if st != 200:
        raise SystemExit(1)
    crt = open(p('client.crt')).read()
    der = base64.b64decode(''.join(x for x in crt.splitlines() if x and not x.startswith('-----')))
    fin = {'code_id': cid, 'node': node, 'token': began['token'], 'client_cert': crt,
           'ca': open(p('ca.crt')).read(),
           'seal': seal(pub, ['finish', cid, node, data['s'], key, hashlib.sha256(der).hexdigest()])}
    st, got, _ = call(data['h'], data['p'], '/v1/enroll/finish', json.dumps(fin).encode(), pins)
    print('finish', st, json.loads(got).get('said'))
    if st != 200:
        raise SystemExit(1)
    fd = os.open(p('sign.key'), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.write(fd, (key + '\n').encode())
    os.close(fd)
    for n, v in (('pins.json', json.dumps(pins)), ('node', node),
                 ('code.json', json.dumps({k: v for k, v in data.items() if k != 's'}))):
        with open(p(n), 'w') as f:
            f.write(v)
    # agent_restart: the agent starts its network side again with this node in - waited for.
    # Until then the old side answers (the first node: it does not even ask for a certificate,
    # 401), or the port is closed for a moment: retried, as otp's join does.
    end = time.time() + 30
    while True:
        try:
            got = op(d, 'status')
            if got['_status'] == 200:
                break
        except OSError:
            pass
        if time.time() > end:
            raise SystemExit('the agent did not come back with this node in')
        time.sleep(0.5)
    print(json.dumps(got, indent=1)[:1500])


def op(d, name, args=None, quiet=False, **kw):
    data, pins, node, key, cert = load(d)
    body = json.dumps({'op': name, 'args': args or {}}).encode()
    hd = signed_headers(key, node, body, kw.get('ts'), kw.get('nonce'))
    if kw.get('bad_key'):
        hd = signed_headers('11' * 32, node, body)
    if kw.get('unsigned'):
        hd['X-Otp-Sign'] = ''
    st, got, rh = call(data['h'], data['p'], '/v1/op', body, pins, None if kw.get('no_cert') else cert, hd)
    out = json.loads(got or b'{}')
    if st == 200 and not reply_ok(key, hd['X-Otp-Nonce'], got, rh.get('X-Otp-Sign')):
        raise SystemExit('the answer is not signed with this node\'s key')
    if st == 200 and name == 'status':
        a = out.get('agent') or {}
        want = [a.get('cert_fp')] + ([a['cert_next_fp']] if a.get('cert_next_fp') else [])
        if a.get('cert_fp') and want != pins:
            with open(os.path.join(d, 'pins.json'), 'w') as f:     # pinned as the signed answer says
                f.write(json.dumps(want))
    return out if quiet else dict(out, _status=st)


def refusals(d):
    nonce = secrets.token_hex(16)
    cases = [
        ('a good status', lambda: op(d, 'status', nonce=nonce), 200),
        ('the same nonce again (replay)', lambda: op(d, 'status', nonce=nonce), 400),
        ('an old time (600 s)', lambda: op(d, 'status', ts='%.3f' % (time.time() - 600)), 400),
        ('signed with another key', lambda: op(d, 'status', bad_key=True), 400),
        ('unsigned', lambda: op(d, 'status', unsigned=True), 400),
        ('no client certificate', lambda: op(d, 'status', no_cert=True), 401),
        ('an op outside the closed set', lambda: op(d, 'shell', {'cmd': 'id'}), 400),
        ('the server\'s own database', lambda: op(d, 'pg_allow', {'db': 'postgres', 'user': 'otp', 'peers': ['192.0.2.9']}), 400),
        ('a newline in an address', lambda: op(d, 'pg_allow', {'db': 'otp', 'user': 'otp', 'peers': ['192.0.2.9\nhost all all']}), 400),
        ('trust with no authority', lambda: op(d, 'trust', {'ca': ''}), 400),
    ]
    bad = 0
    for what, fn, want in cases:
        got = fn()
        # The agent's limiter on refusals (a penalty each, 0.2 a second back) answers 429 after a
        # burst of them - as it must: waited off, the same case asked again.
        waited = 0
        while got['_status'] == 429 and want != 429 and waited < 180:
            time.sleep(5)
            waited += 5
            got = fn()
        if waited:
            print('%-34s     429  the limiter on refusals: waited %d s' % ('', waited))
        ok = got['_status'] == want
        bad += not ok
        print('%-34s %s %3d  %s' % (what, 'ok ' if ok else 'BAD', got['_status'], str(got.get('said') or '')[:90]))
    return bad


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['join'] and len(a) == 3:
        join(a[1], a[2])
    elif a[:1] == ['op'] and len(a) in (3, 4):
        print(json.dumps(op(a[1], a[2], json.loads(a[3]) if len(a) == 4 else None), indent=1))
    elif a[:1] == ['refusals'] and len(a) == 2:
        sys.exit(1 if refusals(a[1]) else 0)
    else:
        print(__doc__)
        sys.exit(2)
