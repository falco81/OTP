# A small ACME CA for the tests (RFC 8555, what otp uses of it): every
# request's JWS (ES256) checked with openssl against the account's key, the
# nonces, HTTP-01 really fetched from port 80 of the name, the certificate
# signed by a CA made here. Names under .example are refused, as Let's
# Encrypt refuses names it may not give.
# Usage: python3 mock_acme.py PORT WORKDIR   (writes WORKDIR/ca.pem: trust it)
import os, sys, json, base64, hashlib, secrets, subprocess, threading, ssl, urllib.request, time
import http.server, socketserver

PORT, W = int(sys.argv[1]), sys.argv[2]
os.makedirs(W, exist_ok=True)
B = 'https://127.0.0.1:%d' % PORT


def run(args, data=None):
    p = subprocess.run(args, input=data, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:300])
    return p.stdout


# The CA, and the certificate of this server (for 127.0.0.1), signed by it.
run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-days', '30',
     '-subj', '/CN=otp test ACME CA', '-addext', 'basicConstraints=critical,CA:TRUE',
     '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', W + '/ca.key', '-out', W + '/ca.pem'])
run(['openssl', 'req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-subj', '/CN=127.0.0.1',
     '-keyout', W + '/srv.key', '-out', W + '/srv.csr'])
open(W + '/ext', 'w').write('subjectAltName=IP:127.0.0.1\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n')
run(['openssl', 'x509', '-req', '-in', W + '/srv.csr', '-CA', W + '/ca.pem', '-CAkey', W + '/ca.key', '-CAcreateserial',
     '-days', '30', '-extfile', W + '/ext', '-out', W + '/srv.pem'])
NONCES, ACCTS, ORDERS, AUTHZ, CERTS = set(), {}, {}, {}, {}
LOCK = threading.Lock()
LOG = []


def b64d(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def jwk_pem(jwk):
    if jwk.get('kty') != 'EC' or jwk.get('crv') != 'P-256':
        raise ValueError('only EC P-256')
    der = bytes.fromhex('3059301306072a8648ce3d020106082a8648ce3d030107034200') + b'\x04' + b64d(jwk['x']) + b64d(jwk['y'])
    return b'-----BEGIN PUBLIC KEY-----\n' + base64.encodebytes(der) + b'-----END PUBLIC KEY-----\n'


def thumb(jwk):
    return b64e(hashlib.sha256(json.dumps({'crv': jwk['crv'], 'kty': jwk['kty'], 'x': jwk['x'], 'y': jwk['y']},
                                          separators=(',', ':'), sort_keys=True).encode()).digest())


def verify(pem, signing_input, sig):
    if len(sig) != 64:
        raise ValueError('the signature is not 64 bytes')

    def integer(b):
        b = b.lstrip(b'\x00') or b'\x00'
        if b[0] & 0x80:
            b = b'\x00' + b
        return b'\x02' + bytes([len(b)]) + b
    body = integer(sig[:32]) + integer(sig[32:])
    der = b'\x30' + bytes([len(body)]) + body
    k = '%s/k%s.pem' % (W, secrets.token_hex(4)); s = k + '.sig'
    open(k, 'wb').write(pem); open(s, 'wb').write(der)
    try:
        p = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', k, '-signature', s], input=signing_input, capture_output=True)
        if p.returncode:
            raise ValueError('the signature does not check')
    finally:
        os.unlink(k); os.unlink(s)


def new_nonce():
    n = secrets.token_urlsafe(16)
    NONCES.add(n)
    return n


class H(http.server.BaseHTTPRequestHandler):
    def send(self, code, body=None, headers=None, ctype='application/json'):
        data = b'' if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.send_response(code)
        self.send_header('Replay-Nonce', new_nonce())
        self.send_header('Content-Type', ctype if body is not None else 'text/plain')
        self.send_header('Content-Length', str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def err(self, code, typ, detail):
        self.send(code, {'type': 'urn:ietf:params:acme:error:' + typ, 'detail': detail}, ctype='application/problem+json')

    def do_HEAD(self):
        self.send(200)

    def do_GET(self):
        if self.path == '/dir':
            return self.send(200, {'newNonce': B + '/nonce', 'newAccount': B + '/acct', 'newOrder': B + '/order'})
        if self.path == '/nonce':
            return self.send(204)
        if self.path == '/log':
            return self.send(200, LOG)
        self.err(405, 'malformed', 'POST-as-GET')

    def do_POST(self):
        raw = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)))
        prot = json.loads(b64d(raw['protected']))
        with LOCK:
            if prot.get('nonce') not in NONCES:
                return self.err(400, 'badNonce', 'unknown nonce')
            NONCES.discard(prot['nonce'])
        if prot.get('url') != B + self.path:
            return self.err(400, 'unauthorized', 'url %s is not %s' % (prot.get('url'), B + self.path))
        if prot.get('alg') != 'ES256':
            return self.err(400, 'badSignatureAlgorithm', prot.get('alg'))
        if 'jwk' in prot:
            jwk = prot['jwk']; kid = None
        else:
            kid = prot.get('kid')
            if kid not in ACCTS:
                return self.err(400, 'accountDoesNotExist', kid)
            jwk = ACCTS[kid]['jwk']
        try:
            verify(jwk_pem(jwk), ('%s.%s' % (raw['protected'], raw['payload'])).encode(), b64d(raw['signature']))
        except ValueError as e:
            return self.err(400, 'unauthorized', str(e))
        payload = json.loads(b64d(raw['payload'])) if raw['payload'] else None
        LOG.append({'path': self.path, 'kid': kid})
        p = self.path
        if p == '/acct':
            for k, a in ACCTS.items():
                if a['jwk'] == jwk:
                    return self.send(200, {'status': 'valid'}, {'Location': k})
            if not payload.get('termsOfServiceAgreed'):
                return self.err(400, 'malformed', 'terms')
            k = B + '/acct/' + secrets.token_hex(4)
            ACCTS[k] = {'jwk': jwk, 'contact': payload.get('contact')}
            return self.send(201, {'status': 'valid'}, {'Location': k})
        if kid is None:
            return self.err(400, 'malformed', 'a kid is needed')
        if p == '/order':
            names = [i['value'] for i in payload['identifiers']]
            if any(n.endswith('.example') for n in names):
                return self.err(400, 'rejectedIdentifier', 'the CA may not give a certificate for %s' % names)
            oid = secrets.token_hex(4)
            azs = []
            for n in names:
                aid = secrets.token_hex(4)
                AUTHZ[aid] = {'name': n, 'status': 'pending', 'token': secrets.token_urlsafe(24), 'kid': kid}
                azs.append(B + '/authz/' + aid)
            ORDERS[oid] = {'status': 'pending', 'names': names, 'authz': azs, 'kid': kid}
            return self.send(201, self.order(oid), {'Location': B + '/order/' + oid})
        if p.startswith('/order/'):
            return self.send(200, self.order(p.split('/')[-1]))
        if p.startswith('/authz/'):
            a = AUTHZ[p.split('/')[-1]]
            return self.send(200, {'status': a['status'], 'identifier': {'type': 'dns', 'value': a['name']},
                                   'challenges': [{'type': t, 'url': B + '/chal/' + p.split('/')[-1] + ('/dns' if t == 'dns-01' else ''),
                                                   'token': a['token'], 'status': a['status'],
                                                   **({'error': a['error']} if a.get('error') else {})}
                                                  for t in ('http-01', 'dns-01')]})
        if p.startswith('/chal/') and p.endswith('/dns'):
            aid = p.split('/')[-2]
            a = AUTHZ[aid]
            want = b64e(hashlib.sha256((a['token'] + '.' + thumb(ACCTS[a['kid']]['jwk'])).encode()).digest())
            try:
                zone = json.load(open(W + '/dns.json'))
                rr = '_acme-challenge.' + a['name']
                for _ in range(5):              # a CNAME followed, as a resolver does
                    if 'CNAME ' + rr not in zone:
                        break
                    rr = zone['CNAME ' + rr].rstrip('.')
                txt = zone.get(rr, [])
            except (OSError, ValueError):
                txt = []
            LOG.append({'dns': a['name'], 'txt': txt})
            a['status'] = 'valid' if want in txt else 'invalid'
            if want not in txt:
                a['error'] = {'detail': 'no TXT record %s at _acme-challenge.%s (found %s)' % (want, a['name'], txt)}
            return self.send(200, {'type': 'dns-01', 'status': 'processing', 'token': a['token']})
        if p.startswith('/chal/'):
            aid = p.split('/')[-1]
            a = AUTHZ[aid]
            want = a['token'] + '.' + thumb(ACCTS[a['kid']]['jwk'])
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                        'http://%s/.well-known/acme-challenge/%s' % (a['name'], a['token']), timeout=10) as r:
                    got = r.read().decode().strip()
                a['status'] = 'valid' if got == want else 'invalid'
                if got != want:
                    a['error'] = {'detail': 'the answer is not the key authorization: %r' % got[:60]}
            except Exception as e:
                a['status'] = 'invalid'
                a['error'] = {'detail': 'port 80 of %s: %s' % (a['name'], e)}
            return self.send(200, {'type': 'http-01', 'status': 'processing', 'token': a['token']})
        if p.startswith('/finalize/'):
            oid = p.split('/')[-1]
            o = ORDERS[oid]
            if not all(AUTHZ[u.split('/')[-1]]['status'] == 'valid' for u in o['authz']):
                return self.err(403, 'orderNotReady', 'not every authorization is valid')
            csr = b64d(payload['csr'])
            open(W + '/c.der', 'wb').write(csr)
            run(['openssl', 'req', '-inform', 'DER', '-in', W + '/c.der', '-out', W + '/c.csr'])
            text = run(['openssl', 'req', '-in', W + '/c.csr', '-noout', '-text']).decode()
            for n in o['names']:
                if 'DNS:' + n not in text:
                    return self.err(400, 'badCSR', 'the request does not name %s' % n)
            open(W + '/e', 'w').write('subjectAltName=' + ','.join('DNS:' + n for n in o['names']) + '\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n')
            pem = run(['openssl', 'x509', '-req', '-in', W + '/c.csr', '-CA', W + '/ca.pem', '-CAkey', W + '/ca.key',
                       '-CAcreateserial', '-days', '90', '-extfile', W + '/e']).decode()
            CERTS[oid] = pem + open(W + '/ca.pem').read()
            o['status'] = 'valid'
            return self.send(200, self.order(oid))
        if p.startswith('/cert/'):
            return self.send(200, CERTS[p.split('/')[-1]].encode(), ctype='application/pem-certificate-chain')
        self.err(404, 'malformed', p)

    def order(self, oid):
        o = ORDERS[oid]
        if o['status'] == 'pending' and all(AUTHZ[u.split('/')[-1]]['status'] == 'valid' for u in o['authz']):
            o['status'] = 'ready'
        if any(AUTHZ[u.split('/')[-1]]['status'] == 'invalid' for u in o['authz']):
            o['status'] = 'invalid'
        out = {'status': o['status'], 'identifiers': [{'type': 'dns', 'value': n} for n in o['names']],
               'authorizations': o['authz'], 'finalize': B + '/finalize/' + oid}
        if o['status'] == 'valid':
            out['certificate'] = B + '/cert/' + oid
        return out

    def log_message(self, *a):
        pass


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


srv = TS(('127.0.0.1', PORT), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(W + '/srv.pem', W + '/srv.key')
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
open(W + '/ready', 'w').write('1')
srv.serve_forever()
