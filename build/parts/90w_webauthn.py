# ---- a passkey as the administration's second step (1.0.254) ----------------------
# Face ID, Touch ID, Windows Hello or a security key: WebAuthn, after the password -
# never instead of it. The account sets it up as it sets up an app or a mail address
# (the first sign-in, Accounts → Reset the second step, otp --reset-2fa NAME), and the
# server keeps only the public half of the key, in the account's adm2fa:<name> row:
#   {'kind': 'passkey', 'keys': [{'id', 'alg', 'pub', 'count', 'host', 'name', 'at',
#    'used', 'backed_up'}], 'at', 'by'}
# Checked as the WebAuthn rules say: the challenge once (the sign-in's own, and on
# either node), its type, the origin and the name the pages were opened by (the RP ID
# - a name, never an address), the user present AND verified (a face, a finger, the
# device's PIN: without it no second step), the signature, the counter. The
# attestation is not asked for ("none"). The signature checked here, in Python
# (ES256, RS256, EdDSA) - nothing run, nothing written to a file.
WA_TIMEOUT_MS = 300000
WA_CHALLENGE_S = 300
WA_ALGS = (-7, -8, -257)


def wa_b64(raw):
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def wa_unb64(text, most=1 << 16):
    s = str(text or '')
    if len(s) > most * 2 or not re.fullmatch(r'[A-Za-z0-9_-]*', s):
        raise ValueError('not base64url')
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def wa_cbor(data, i=0, depth=0):
    """(value, next index) of the CBOR item at data[i] - the part WebAuthn uses."""
    if depth > 8 or i >= len(data):
        raise ValueError('CBOR too deep or cut short')
    first = data[i]
    major, info = first >> 5, first & 31
    i += 1
    if info < 24:
        n = info
    elif info in (24, 25, 26, 27):
        size = 1 << (info - 24)
        if i + size > len(data):
            raise ValueError('CBOR cut short')
        n = int.from_bytes(data[i:i + size], 'big')
        i += size
    else:
        raise ValueError('CBOR of an indefinite length')
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major in (2, 3):
        if i + n > len(data):
            raise ValueError('CBOR cut short')
        raw = bytes(data[i:i + n])
        return (raw if major == 2 else raw.decode('utf-8')), i + n
    if major == 4:
        if n > 64:
            raise ValueError('CBOR list too long')
        out = []
        for _ in range(n):
            v, i = wa_cbor(data, i, depth + 1)
            out.append(v)
        return out, i
    if major == 5:
        if n > 64:
            raise ValueError('CBOR map too long')
        out = {}
        for _ in range(n):
            k, i = wa_cbor(data, i, depth + 1)
            v, i = wa_cbor(data, i, depth + 1)
            out[k] = v
        return out, i
    if major == 7 and info in (20, 21, 22):
        return {20: False, 21: True, 22: None}[info], i
    raise ValueError('CBOR of a kind not used here')


# P-256 (secp256r1), for ES256.
_P256_P = 2 ** 256 - 2 ** 224 + 2 ** 192 + 2 ** 96 - 1
_P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_P256_G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
           0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)


def _p256_on(pt):
    x, y = pt
    return 0 <= x < _P256_P and 0 <= y < _P256_P and \
        (y * y - (x * x * x - 3 * x + _P256_B)) % _P256_P == 0


def _p256_add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    p = _P256_P
    if a[0] == b[0]:
        if (a[1] + b[1]) % p == 0:
            return None
        lam = (3 * a[0] * a[0] - 3) * pow(2 * a[1], p - 2, p) % p
    else:
        lam = (b[1] - a[1]) * pow(b[0] - a[0], p - 2, p) % p
    x = (lam * lam - a[0] - b[0]) % p
    return x, (lam * (a[0] - x) - a[1]) % p


def _p256_mul(k, pt):
    out = None
    while k:
        if k & 1:
            out = _p256_add(out, pt)
        pt = _p256_add(pt, pt)
        k >>= 1
    return out


def _der_ints(sig):
    """(r, s) of an ECDSA signature as DER."""
    if len(sig) < 8 or sig[0] != 0x30 or sig[1] != len(sig) - 2:
        raise ValueError('not a DER signature')
    out, i = [], 2
    for _ in range(2):
        if sig[i] != 0x02:
            raise ValueError('not a DER signature')
        n = sig[i + 1]
        out.append(int.from_bytes(sig[i + 2:i + 2 + n], 'big'))
        i += 2 + n
    if i != len(sig):
        raise ValueError('not a DER signature')
    return out


def wa_es256_ok(x, y, msg, sig):
    try:
        r, s = _der_ints(sig)
    except (ValueError, IndexError):
        return False
    q = (int.from_bytes(x, 'big'), int.from_bytes(y, 'big'))
    if not (1 <= r < _P256_N and 1 <= s < _P256_N) or not _p256_on(q):
        return False
    e = int.from_bytes(hashlib.sha256(msg).digest(), 'big')
    w = pow(s, _P256_N - 2, _P256_N)
    pt = _p256_add(_p256_mul(e * w % _P256_N, _P256_G), _p256_mul(r * w % _P256_N, q))
    return pt is not None and pt[0] % _P256_N == r


def wa_rs256_ok(n, e, msg, sig):
    k = (n.bit_length() + 7) // 8
    # 1.0.262: bounded both ways - a huge n or e would hold the interpreter for minutes (RADIUS too)
    if n.bit_length() < 2048 or n.bit_length() > 8192 or e < 3 or e.bit_length() > 32 or len(sig) != k:
        return False
    m = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    info = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(msg).digest()
    want = b'\x00\x01' + b'\xff' * (k - 3 - len(info)) + b'\x00' + info
    return hmac.compare_digest(m, want)


def wa_cose(key):
    """The COSE key of a new passkey as (alg, its public half kept here)."""
    if not isinstance(key, dict):
        raise ValueError('the key is not a COSE key')
    kty, alg = key.get(1), key.get(3)
    if alg == -7 and kty == 2 and key.get(-1) == 1:
        x, y = key.get(-2), key.get(-3)
        if not (isinstance(x, bytes) and isinstance(y, bytes) and len(x) == 32 == len(y)) or \
                not _p256_on((int.from_bytes(x, 'big'), int.from_bytes(y, 'big'))):
            raise ValueError('not a key of the curve P-256')
        return alg, wa_b64(x + y)
    if alg == -257 and kty == 3:
        n, e = key.get(-1), key.get(-2)
        if not (isinstance(n, bytes) and isinstance(e, bytes)) or len(n) * 8 < 2048:
            raise ValueError('an RSA key under 2048 bits')
        nb, ev = int.from_bytes(n, 'big').bit_length(), int.from_bytes(e, 'big')
        if nb < 2048 or nb > 8192 or len(e) > 4 or ev < 3 or not ev & 1:
            raise ValueError('an RSA key of 2048 to 8192 bits with a small odd exponent is taken here')
        return alg, wa_b64(e) + '.' + wa_b64(n)
    if alg == -8 and kty == 1 and key.get(-1) == 6:
        x = key.get(-2)
        if not (isinstance(x, bytes) and len(x) == 32):
            raise ValueError('not an Ed25519 key')
        return alg, wa_b64(x)
    raise ValueError('a key of a kind not taken here (ES256, RS256 and EdDSA are)')


def wa_sig_ok(alg, pub, msg, sig):
    try:
        if alg == -7:
            raw = wa_unb64(pub)
            return wa_es256_ok(raw[:32], raw[32:], msg, sig)
        if alg == -257:
            e, n = pub.split('.', 1)
            return wa_rs256_ok(int.from_bytes(wa_unb64(n), 'big'), int.from_bytes(wa_unb64(e), 'big'), msg, sig)
        if alg == -8:
            return bool(ed25519_verify(wa_unb64(pub), msg, sig))
    except (ValueError, TypeError, IndexError):
        return False
    return False


def wa_host(h):
    """(the RP ID, the origin) of the page asking: the name it was opened by - never an
    address (a passkey cannot be bound to one) - over HTTPS."""
    host = str(h.headers.get('X-Otp-Host') or '').strip().lower()
    m = re.fullmatch(r'([a-z0-9.-]{1,253})(?::([0-9]{1,5}))?', host)
    if not m:
        raise ValueError('a passkey works on these pages opened by a name over HTTPS '
                         '(https://name/), not by an address')
    name, port = m.group(1).rstrip('.'), m.group(2)
    try:
        ipaddress.ip_address(name)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip or not name:
        raise ValueError('a passkey works on these pages opened by a name over HTTPS '
                         '(https://name/), not by an address')
    origin = 'https://' + name + ('' if not port or port == '443' else ':' + port)
    return name, origin


def wa_host_ok(h):
    try:
        wa_host(h)
        return True
    except ValueError:
        return False


def wa_client(raw, kind, challenge, origin):
    """clientDataJSON checked: its type, the challenge given, the origin."""
    try:
        c = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ValueError('the browser\'s answer is not JSON')
    if not isinstance(c, dict) or c.get('type') != kind:
        raise ValueError('the browser\'s answer is not of this step')
    if not hmac.compare_digest(str(c.get('challenge') or ''), str(challenge or '')):
        raise ValueError('the answer is to another question - try again')
    if c.get('origin') != origin:
        raise ValueError('the answer came from %s, not from these pages (%s)' % (
            str(c.get('origin'))[:80], origin))
    if c.get('crossOrigin') is True:
        raise ValueError('the answer came from a page inside another')
    return c


def wa_auth_data(ad, rp_id, need_key=False):
    """authenticatorData: the name, the user present and verified, the counter; with
    need_key, the new key's ID and its COSE key."""
    if len(ad) < 37:
        raise ValueError('the authenticator\'s data is cut short')
    if not hmac.compare_digest(ad[:32], hashlib.sha256(rp_id.encode()).digest()):
        raise ValueError('the passkey is for another name than %s' % rp_id)
    flags = ad[32]
    if not flags & 0x01:
        raise ValueError('nobody was there (the authenticator says so)')
    if not flags & 0x04:
        raise ValueError('the device did not check who it was (no face, finger or PIN) - '
                         'that is no second step')
    out = {'count': int.from_bytes(ad[33:37], 'big'), 'backed_up': bool(flags & 0x10)}
    if need_key:
        if not flags & 0x40 or len(ad) < 55:
            raise ValueError('the authenticator gave no key')
        n = int.from_bytes(ad[53:55], 'big')
        if n < 16 or n > 1023 or len(ad) < 55 + n:
            raise ValueError('the authenticator\'s key ID is not right')
        out['id'] = wa_b64(ad[55:55 + n])
        key, _ = wa_cbor(ad, 55 + n)
        out['alg'], out['pub'] = wa_cose(key)
    return out


def wa_user_id(name):
    return wa_b64(hashlib.sha256(('otp-admin:' + str(name).lower()).encode()).digest()[:16])


def wa_register_options(h, name, display, have=()):
    rp_id, origin = wa_host(h)
    ch = wa_b64(secrets.token_bytes(32))
    site = str(CONFIG.get('site_name') or socket.gethostname())
    return {'challenge': ch, 'host': rp_id, 'origin': origin, 't': time.time()}, {'publicKey': {
        'challenge': ch, 'rp': {'id': rp_id, 'name': '%s (administration)' % site[:60]},
        'user': {'id': wa_user_id(name), 'name': name, 'displayName': display or name},
        'pubKeyCredParams': [{'type': 'public-key', 'alg': a} for a in WA_ALGS],
        'authenticatorSelection': {'userVerification': 'required', 'residentKey': 'preferred'},
        'excludeCredentials': [{'type': 'public-key', 'id': k} for k in have],
        'attestation': 'none', 'timeout': WA_TIMEOUT_MS}}


def wa_register_finish(saved, b):
    """The new passkey from the browser's answer, checked against the question asked."""
    if not saved or time.time() - fnum(saved.get('t')) > WA_CHALLENGE_S:
        raise ValueError('that took too long - start again')
    cd = wa_unb64(b.get('clientDataJSON'))
    wa_client(cd, 'webauthn.create', saved.get('challenge'), saved.get('origin'))
    att, _ = wa_cbor(wa_unb64(b.get('attestationObject'), 1 << 17))
    if not isinstance(att, dict) or not isinstance(att.get('authData'), bytes):
        raise ValueError('the authenticator\'s answer is not right')
    got = wa_auth_data(att['authData'], saved['host'], need_key=True)
    return {'id': got['id'], 'alg': got['alg'], 'pub': got['pub'], 'count': got['count'],
            'backed_up': got['backed_up'], 'host': saved['host'], 'at': time.time(), 'used': 0,
            'name': str(b.get('device') or '')[:60]}


def wa_login_options(h, keys):
    rp_id, origin = wa_host(h)
    mine = [k for k in keys if k.get('host') == rp_id]
    if not mine:
        raise ValueError('the passkey of this account is for https://%s/ - open these pages '
                         'there (or a full administrator resets the second step)'
                         % (keys[0].get('host') if keys else '?'))
    ch = wa_b64(secrets.token_bytes(32))
    return {'challenge': ch, 'host': rp_id, 'origin': origin, 't': time.time()}, {'publicKey': {
        'challenge': ch, 'rpId': rp_id, 'userVerification': 'required', 'timeout': WA_TIMEOUT_MS,
        'allowCredentials': [{'type': 'public-key', 'id': k['id']} for k in mine]}}


def wa_login_finish(saved, keys, b):
    """The key of this account that signed, checked; its counter moved on (the key, changed)."""
    if not saved or time.time() - fnum(saved.get('t')) > WA_CHALLENGE_S:
        raise ValueError('that took too long - start again')
    cid = str(b.get('id') or '')
    key = next((k for k in keys if hmac.compare_digest(str(k.get('id')), cid)), None)
    if not key:
        raise ValueError('that passkey is not this account\'s (taken away, or of another server)')
    cd = wa_unb64(b.get('clientDataJSON'))
    wa_client(cd, 'webauthn.get', saved.get('challenge'), saved.get('origin'))
    ad = wa_unb64(b.get('authenticatorData'))
    got = wa_auth_data(ad, saved['host'])
    if not wa_sig_ok(key.get('alg'), key.get('pub'), ad + hashlib.sha256(cd).digest(),
                     wa_unb64(b.get('signature'))):
        raise ValueError('the passkey\'s signature is not right')
    was = int(key.get('count') or 0)
    if (was or got['count']) and got['count'] <= was:
        raise PermissionError('the passkey\'s counter went back - it may have been copied')
    return dict(key, count=got['count'], used=time.time(), backed_up=got['backed_up'])
