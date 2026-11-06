"""t_webauthn.py - 1.0.254: the passkey checks of the server (90w_webauthn.py) with keys made here:
ES256, RS256 and Ed25519 signed as a device signs; refused: another origin, another name, no user
verification, a wrong signature, the counter back, an old question, an address for a name."""
import os, sys, json, time, hashlib, base64, secrets, random, re, hmac, socket, ipaddress
PARTS = '/home/claude/build/parts'
g = {'__name__': 'wa', 'CONFIG': {'site_name': 'otp'}, 'fnum': lambda x, d=0.0: float(x or d),
     'route': lambda *a, **k: (lambda f: f)}
for f in ('90q_acme_push.py', '90w_webauthn.py'):
    src = open(os.path.join(PARTS, f)).read()
    src = re.sub(r"^@route\(.*$", '', src, flags=re.M)
    exec('import os, re, json, time, hashlib, base64, secrets, hmac, socket, ipaddress, threading\n' + src, g)
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


def b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip('=')


def cbor(v):
    def head(major, n):
        if n < 24:
            return bytes([major << 5 | n])
        for info, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
            if n < 1 << (8 * size):
                return bytes([major << 5 | info]) + n.to_bytes(size, 'big')
    if isinstance(v, bool):
        return bytes([0xf5 if v else 0xf4])
    if isinstance(v, int):
        return head(0, v) if v >= 0 else head(1, -1 - v)
    if isinstance(v, bytes):
        return head(2, len(v)) + v
    if isinstance(v, str):
        e = v.encode(); return head(3, len(e)) + e
    if isinstance(v, list):
        return head(4, len(v)) + b''.join(cbor(x) for x in v)
    if isinstance(v, dict):
        return head(5, len(v)) + b''.join(cbor(k) + cbor(x) for k, x in v.items())
    raise TypeError(v)


class H:
    def __init__(self, host):
        self.headers = {'X-Otp-Host': host}


# ---- the three kinds of key --------------------------------------------------------------
N = g['_P256_N']


def es_key():
    d = secrets.randbelow(N - 1) + 1
    q = g['_p256_mul'](d, g['_P256_G'])
    return d, q


def es_sign(d, msg):
    e = int.from_bytes(hashlib.sha256(msg).digest(), 'big')
    while True:
        k = secrets.randbelow(N - 1) + 1
        r = g['_p256_mul'](k, g['_P256_G'])[0] % N
        s = pow(k, N - 2, N) * (e + r * d) % N
        if r and s:
            break
    def der(i):
        b = i.to_bytes((i.bit_length() + 8) // 8, 'big'); return b'\x02' + bytes([len(b)]) + b
    body = der(r) + der(s)
    return b'\x30' + bytes([len(body)]) + body


def is_prime(n):
    if n < 2 or n % 2 == 0:
        return n == 2
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2; s += 1
    for _ in range(24):
        a = random.randrange(2, n - 1); x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def prime(bits):
    while True:
        p = random.getrandbits(bits) | (1 << (bits - 1)) | 1
        if is_prime(p):
            return p


def rsa_key():
    e = 65537
    while True:
        p, q = prime(1024), prime(1024)
        n, phi = p * q, (p - 1) * (q - 1)
        if n.bit_length() == 2048 and phi % e:
            return n, e, pow(e, -1, phi)


def rsa_sign(n, d, msg):
    k = (n.bit_length() + 7) // 8
    info = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(msg).digest()
    em = b'\x00\x01' + b'\xff' * (k - 3 - len(info)) + b'\x00' + info
    return pow(int.from_bytes(em, 'big'), d, n).to_bytes(k, 'big')


# ---- a device -----------------------------------------------------------------------------
class Device:
    def __init__(self, kind):
        self.kind, self.count, self.cid = kind, 0, secrets.token_bytes(32)
        if kind == 'es':
            self.d, q = es_key()
            self.cose = {1: 2, 3: -7, -1: 1, -2: q[0].to_bytes(32, 'big'), -3: q[1].to_bytes(32, 'big')}
        elif kind == 'rs':
            self.n, e, self.d = rsa_key()
            self.cose = {1: 3, 3: -257, -1: self.n.to_bytes(256, 'big'), -2: e.to_bytes(3, 'big')}
        else:
            self.seed = secrets.token_bytes(32)
            self.cose = {1: 1, 3: -8, -1: 6, -2: g['ed25519_public'](self.seed)}

    def sign(self, msg):
        if self.kind == 'es':
            return es_sign(self.d, msg)
        if self.kind == 'rs':
            return rsa_sign(self.n, self.d, msg)
        return g['ed25519_sign'](self.seed, msg)

    def ad(self, rp, flags=0x05, key=False, count=None):
        self.count = self.count + 1 if count is None and self.kind != 'es' else (count if count is not None else 0)
        out = hashlib.sha256(rp.encode()).digest() + bytes([flags | (0x40 if key else 0)]) + self.count.to_bytes(4, 'big')
        if key:
            out += b'\0' * 16 + len(self.cid).to_bytes(2, 'big') + self.cid + cbor(self.cose)
        return out

    def create(self, opts, origin, flags=0x05, rp=None):
        pk = opts['publicKey']
        cd = json.dumps({'type': 'webauthn.create', 'challenge': pk['challenge'], 'origin': origin}).encode()
        att = cbor({'fmt': 'none', 'attStmt': {}, 'authData': self.ad(rp or pk['rp']['id'], flags, key=True)})
        return {'clientDataJSON': b64(cd), 'attestationObject': b64(att), 'device': 'iPad · test'}

    def get(self, opts, origin, flags=0x05, rp=None, count=None, kind='webauthn.get', bad=False):
        pk = opts['publicKey']
        cd = json.dumps({'type': kind, 'challenge': pk['challenge'], 'origin': origin}).encode()
        ad = self.ad(rp or pk['rpId'], flags, count=count)
        sig = self.sign(ad + hashlib.sha256(cd).digest())
        if bad:
            sig = sig[:-1] + bytes([sig[-1] ^ 1])
        return {'id': b64(self.cid), 'clientDataJSON': b64(cd), 'authenticatorData': b64(ad), 'signature': b64(sig)}


def refused(fn, words=''):
    try:
        fn()
    except (ValueError, PermissionError) as e:
        return (words in str(e)) if words else True
    return False


h = H('otp.firma.cz')
ORIGIN = 'https://otp.firma.cz'
for kind in ('es', 'rs', 'ed'):
    dev = Device(kind)
    saved, opts = g['wa_register_options'](h, 'novak', 'Jan Novák')
    ok(kind + ': the question for the device: the name, verification required, no attestation',
       opts['publicKey']['rp']['id'] == 'otp.firma.cz' and opts['publicKey']['authenticatorSelection']['userVerification'] == 'required'
       and opts['publicKey']['attestation'] == 'none')
    key = g['wa_register_finish'](saved, dev.create(opts, ORIGIN))
    ok(kind + ': the passkey taken, its public half only', key['host'] == 'otp.firma.cz' and key['alg'] == dev.cose[3] and 'pub' in key)
    s2, o2 = g['wa_login_options'](h, [key])
    ok(kind + ': the question names this account\'s passkey', o2['publicKey']['allowCredentials'][0]['id'] == key['id'])
    used = g['wa_login_finish'](s2, [key], dev.get(o2, ORIGIN))
    ok(kind + ': signed by the device - in', used['id'] == key['id'] and used['used'] > 0)
    s3, o3 = g['wa_login_options'](h, [used])
    ok(kind + ': a wrong signature refused', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, ORIGIN, bad=True)), 'signature'))
    s3, o3 = g['wa_login_options'](h, [used])
    ok(kind + ': another origin refused', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, 'https://evil.example')), 'came from'))
    s3, o3 = g['wa_login_options'](h, [used])
    ok(kind + ': another name (RP ID) refused', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, ORIGIN, rp='evil.example')), 'another name'))
    s3, o3 = g['wa_login_options'](h, [used])
    ok(kind + ': present but not verified (no face, finger, PIN) refused', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, ORIGIN, flags=0x01)), 'no second step'))
    s3, o3 = g['wa_login_options'](h, [used])
    ok(kind + ': an answer of the wrong step refused', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, ORIGIN, kind='webauthn.create')), 'not of this step'))
    s3, o3 = g['wa_login_options'](h, [used])
    other = dict(s3, challenge=b64(secrets.token_bytes(32)))
    ok(kind + ': the answer to another question refused', refused(lambda: g['wa_login_finish'](other, [used], dev.get(o3, ORIGIN)), 'another question'))
    s3, o3 = g['wa_login_options'](h, [used])
    old = dict(s3, t=time.time() - 400)
    ok(kind + ': an old question (5 min) refused', refused(lambda: g['wa_login_finish'](old, [used], dev.get(o3, ORIGIN)), 'too long'))
    if kind != 'es':
        s3, o3 = g['wa_login_options'](h, [used])
        ok(kind + ': the counter back - refused as copied', refused(lambda: g['wa_login_finish'](s3, [used], dev.get(o3, ORIGIN, count=used['count'])), 'counter'))
    s3, o3 = g['wa_login_options'](h, [used])
    other_dev = Device('es')
    ans = other_dev.get(o3, ORIGIN)
    ok(kind + ': a passkey not this account\'s refused', refused(lambda: g['wa_login_finish'](s3, [used], ans), 'not this account'))
    saved, opts = g['wa_register_options'](h, 'novak', '')
    ok(kind + ': set up without verification refused', refused(lambda: g['wa_register_finish'](saved, dev.create(opts, ORIGIN, flags=0x01)), 'no second step'))
ok('the pages by an address: no passkey', refused(lambda: g['wa_register_options'](H('192.168.40.10'), 'x', ''), 'not by an address'))
ok('...nor by an IPv6 address', refused(lambda: g['wa_register_options'](H('[::1]'), 'x', ''), 'not by an address'))
ok('a port kept in the origin', g['wa_host'](H('otp.firma.cz:8443'))[1] == 'https://otp.firma.cz:8443' and g['wa_host'](H('otp.firma.cz:443'))[1] == ORIGIN)
ok('a passkey of another name of the pages: said where it works', refused(lambda: g['wa_login_options'](H('otp2.firma.cz'), [{'id': 'x', 'host': 'otp.firma.cz'}]), 'https://otp.firma.cz/'))
ok('CBOR of an indefinite length refused', refused(lambda: g['wa_cbor'](b'\x9f\x01\xff')))
print('ALL %d / %d' % (sum(R), len(R)))
