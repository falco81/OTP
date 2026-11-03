

# ---- certificates by ACME: Let's Encrypt and the like (1.0.169) --------------------------
# Settings → Automatic certificates: the certificate of the VIP address (and,
# where asked, each node's own) ordered from an ACME CA - Let's Encrypt, its
# staging, or one of your own (step-ca, an internal CA) - by HTTP-01, and
# renewed when fewer than acme_days are left. The answer to the challenge is
# kept in the database, so whichever node the CA reaches on port 80 gives it
# (nginx sends /.well-known/acme-challenge/ to acme.php, which asks the
# daemon): in a cluster the VIP address may be on either node. The web
# address's certificate is ordered by the one node that does what one node
# does for both (alerts_lead); a node's own by that node. Signed with openssl;
# done in a thread of its own, never on the way of a sign-in.
ACME_CAS = {'letsencrypt': 'https://acme-v02.api.letsencrypt.org/directory',
            'letsencrypt-staging': 'https://acme-staging-v02.api.letsencrypt.org/directory'}
ACME_WORK = {'busy': False, 'at': 0.0, 'says': '', 'target': '', 'n': 0, 'of': 0, 'done': 0, 'each': {}}
# Several certificates at once (1.0.203): at most this many orders side by side.
ACME_PARALLEL = max(1, int(os.environ.get('OTP_ACME_PARALLEL') or 3))
_ACME_CUR = threading.local()          # the certificate this thread orders
_ACME_LOCK = threading.Lock()


def acme_progress(text):
    """What the order of this thread waits for now - on its own card, and as
    the last word of the whole (1.0.203)."""
    text = str(text)[:300]
    ACME_WORK['says'] = text
    t = getattr(_ACME_CUR, 'target', '')
    if t:
        with _ACME_LOCK:
            one = ACME_WORK['each'].get(t)
            if one is not None:
                one['says'] = text
ACME_EVERY = float(os.environ.get('OTP_ACME_EVERY') or 3600)
ACME_RETRY = float(os.environ.get('OTP_ACME_RETRY') or 6 * 3600)


class AcmeError(Exception):
    pass


def _b64u(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def acme_directory_url():
    ca = CONFIG.get('acme_ca') or 'letsencrypt'
    if ca == 'custom':
        return str(CONFIG.get('acme_url') or '').strip()
    return ACME_CAS.get(ca, ACME_CAS['letsencrypt'])


def _acme_ctx():
    ctx = ssl.create_default_context()
    pem = str(CONFIG.get('acme_ca_pem') or '').strip()
    if pem and CONFIG.get('acme_ca') == 'custom':
        ctx.load_verify_locations(cadata=pem)
    return ctx


def _acme_account_gone(kind, said):
    """The CA's error says the account it was asked with is no more (RFC 8555
    accountDoesNotExist; Boulder's 'unauthorized' for one deactivated or not found)."""
    if kind.endswith(':accountDoesNotExist') or kind == 'accountDoesNotExist':
        return True
    low = str(said or '').lower()
    return kind.endswith('unauthorized') and 'account' in low and \
        any(w in low for w in ('deactivated', 'not valid', 'not found', 'does not exist', 'revoked'))


def _rfc3339(text):
    """2025-01-02T04:00:00Z (fractions and offsets too) as a time, or 0."""
    m = re.match(r'^(\d{4})-(\d\d)-(\d\d)[Tt ](\d\d):(\d\d):(\d\d)(\.\d+)?(Z|z|[+-]\d\d:\d\d)$',
                 str(text or '').strip())
    if not m:
        return 0.0
    t = calendar.timegm(tuple(int(m.group(i)) for i in range(1, 7)) + (0, 0, 0))
    if m.group(8) not in ('Z', 'z'):
        sign = 1 if m.group(8)[0] == '+' else -1
        t -= sign * (int(m.group(8)[1:3]) * 3600 + int(m.group(8)[4:6]) * 60)
    return float(t) + (float(m.group(7)) if m.group(7) else 0.0)


# The keys Let's Encrypt takes (1.0.196): RSA of 2048, 3072, 4096 bits, ECDSA on
# P-256 or P-384 - for the account and for a certificate alike.
ACME_KEY_WORDS = {'ec': 'ECDSA P-256', 'ec384': 'ECDSA P-384', 'rsa2048': 'RSA 2048',
                  'rsa3072': 'RSA 3072', 'rsa4096': 'RSA 4096'}
# A certificate's choice: one key, or two certificates - RSA served by default,
# ECDSA to the clients that take it (what Let's Encrypt advises).
ACME_CERT_KEYS = {'dual': ('rsa2048', 'ec'), 'dual-strong': ('rsa4096', 'ec384'),
                  'ec': ('ec',), 'ec384': ('ec384',), 'rsa2048': ('rsa2048',),
                  'rsa3072': ('rsa3072',), 'rsa4096': ('rsa4096',)}


def ari_cert_id(cert):
    """A certificate's ARI id (RFC 9773): base64url of its Authority Key
    Identifier, ".", base64url of its serial number's DER bytes - '' when it
    has no AKI (not one an ACME CA made)."""
    if not cert:
        return ''
    try:
        out = _openssl(['x509', '-noout', '-serial', '-ext', 'authorityKeyIdentifier'],
                       str(cert).encode(), what='the certificate').decode()
    except ValueError:
        return ''
    serial = re.search(r'serial=([0-9A-Fa-f]+)', out)
    aki = re.search(r'(?:keyid:)?((?:[0-9A-Fa-f]{2}:){7,}[0-9A-Fa-f]{2})', out.split('Authority Key Identifier', 1)[-1])
    if not serial or not aki:
        return ''
    sb = bytes.fromhex(serial.group(1).rjust(len(serial.group(1)) + len(serial.group(1)) % 2, '0'))
    if sb and sb[0] & 0x80:
        sb = b'\x00' + sb                      # DER: a positive integer
    return '%s.%s' % (_b64u(bytes.fromhex(aki.group(1).replace(':', ''))), _b64u(sb))


class Acme(object):
    """One conversation with the CA: the account, its key, the nonces."""
    def __init__(self, store):
        self.store = store
        self.dir_url = acme_directory_url()
        if not re.match(r'^https://[^\s]+\Z', self.dir_url):
            raise AcmeError('the ACME directory is an https:// address')
        self.work = tempfile.mkdtemp(prefix='otp-acme-', dir=str(STATE_DIR))
        os.chmod(self.work, 0o700)
        self.nonce = None
        self.kid = None
        try:
            self.dir = self._get(self.dir_url)[0]
            self._account()
        except BaseException:
            # Its folder gone with it (1.0.205): every CA not answering left one,
            # and after a refused account a key unsealed in it.
            self.close()
            raise

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # -- HTTP ------------------------------------------------------------------------
    def _req(self, url, data=None, method=None, accept='application/json'):
        if not str(url).startswith('https://'):
            raise AcmeError('the CA sent an address that is not https: %s' % url)
        req = urllib.request.Request(url, data=data, method=method or ('POST' if data else 'GET'),
                                     headers={'User-Agent': 'otp/%s (acme)' % __version__,
                                              'Accept': accept})
        if data is not None:
            req.add_header('Content-Type', 'application/jose+json')
        try:
            with url_open(req, timeout=30, context=_acme_ctx(), purpose='acme') as r:
                body, headers, status = r.read(1 << 20), r.headers, r.status
        except urllib.error.HTTPError as e:
            body, headers, status = e.read(1 << 20), e.headers, e.code
        except (OSError, ssl.SSLError) as e:
            raise AcmeError('the CA did not answer (%s): %s' % (
                urllib.parse.urlsplit(url).hostname, getattr(e, 'reason', e)))
        if headers.get('Replay-Nonce'):
            self.nonce = headers['Replay-Nonce']
        return body, headers, status

    def _get(self, url):
        body, headers, status = self._req(url)
        if status >= 400:
            raise AcmeError('the CA said %d: %s' % (status, body[:200]))
        return json.loads(body.decode('utf-8')), headers

    # -- signing ---------------------------------------------------------------------
    def _key_file(self):
        p = os.path.join(self.work, 'account.pem')
        if not os.path.exists(p):
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(self.key_pem)
        return p

    def _alg(self):
        """(JWS alg, digest, bytes of r and s) of the account key (1.0.196)."""
        kind = getattr(self, 'akind', 'ec')
        if kind == 'ec384':
            return 'ES384', '-sha384', 48
        if kind.startswith('rsa'):
            return 'RS256', '-sha256', 0
        return 'ES256', '-sha256', 32

    def _jwk(self):
        if getattr(self, '_jwk_done', None):
            return self._jwk_done
        alg, _, size = self._alg()
        if alg == 'RS256':
            txt = _openssl(['pkey', '-in', self._key_file(), '-noout', '-text_pub'],
                           what='the account key').decode()
            m = re.search(r'(?s)Modulus:\s*\n(.*?)\n\S', txt)
            e = re.search(r'Exponent:\s*(\d+)', txt)
            if not m or not e:
                raise AcmeError('the RSA account key does not read')
            n = bytes.fromhex(re.sub(r'[^0-9a-fA-F]', '', m.group(1))).lstrip(b'\x00')
            ev = int(e.group(1))
            jwk = {'e': _b64u(ev.to_bytes((ev.bit_length() + 7) // 8, 'big')), 'kty': 'RSA',
                   'n': _b64u(n)}
        else:
            der = _openssl(['pkey', '-in', self._key_file(), '-pubout', '-outform', 'DER'],
                           what='the account key')
            point = der[-2 * size:]
            jwk = {'crv': 'P-384' if size == 48 else 'P-256', 'kty': 'EC',
                   'x': _b64u(point[:size]), 'y': _b64u(point[size:])}
        self._jwk_done = jwk
        return jwk

    def thumbprint(self):
        # RFC 7638: the required members only, sorted - the JWK holds just those.
        return _b64u(hashlib.sha256(json.dumps(
            self._jwk(), separators=(',', ':'), sort_keys=True).encode()).digest())

    def _sign(self, data):
        alg, digest, size = self._alg()
        der = _openssl(['dgst', digest, '-sign', self._key_file()], data=data,
                       what='signing for the CA')
        if alg == 'RS256':
            return der                       # PKCS#1 v1.5, as JWS wants it
        # DER SEQUENCE { INTEGER r, INTEGER s } -> r || s, `size` bytes each.
        i = 2 if der[1] < 0x80 else 3

        def integer(at):
            n = der[at + 1]
            v = der[at + 2:at + 2 + n].lstrip(b'\x00')
            return v.rjust(size, b'\x00'), at + 2 + n
        r, i = integer(i)
        s, _ = integer(i)
        return r + s

    def post(self, url, payload, use_jwk=False):
        anew = False
        for attempt in (1, 2, 3):
            if not self.nonce:
                self._req(self.dir['newNonce'], method='HEAD')
            protected = {'alg': self._alg()[0], 'nonce': self.nonce, 'url': url}
            if use_jwk or not self.kid:
                protected['jwk'] = self._jwk()
            else:
                protected['kid'] = self.kid
            p64 = _b64u(json.dumps(protected))
            b64 = '' if payload is None else _b64u(json.dumps(payload))
            sig = _b64u(self._sign(('%s.%s' % (p64, b64)).encode('ascii')))
            self.nonce = None
            body, headers, status = self._req(url, json.dumps(
                {'protected': p64, 'payload': b64, 'signature': sig}).encode('utf-8'),
                accept='application/json' if 'cert' not in url else
                'application/pem-certificate-chain')
            if status == 400 and b'badNonce' in body and attempt == 1:
                continue
            if status >= 400:
                try:
                    err = json.loads(body.decode('utf-8'))
                    said = err.get('detail') or err.get('type')
                    kind = str(err.get('type') or '')
                except (ValueError, AttributeError):
                    said, kind = body[:200].decode('utf-8', 'replace'), ''
                # The account kept here gone from the CA (1.0.187): deleted,
                # deactivated, a CA of the same address started anew. Each
                # renewal was refused for it until the certificates ran out;
                # now a new account is made, and the request asked again.
                if self.kid and not use_jwk and not anew and url != self.dir.get('newAccount') and \
                        _acme_account_gone(kind, said):
                    anew = True
                    log('ACME: the CA does not know the account any more (%s) - a new one is made'
                        % said, 'warn')
                    self._account(fresh=True)
                    continue
                raise AcmeError('the CA refused it: %s' % said)
            return body, headers

    def post_json(self, url, payload):
        body, headers = self.post(url, payload)
        return (json.loads(body.decode('utf-8')) if body else {}), headers

    # -- the account -----------------------------------------------------------------
    def _account(self, fresh=False):
        row = {} if fresh else (_meta_json(self.store, 'acme:account') or {})
        pem = unseal_secret(row.get('key') or '', 'acme') if row.get('key') else ''
        # The kind of key asked for (1.0.196): another one than the account has
        # makes a new account with a key of that kind.
        self.akind = str(CONFIG.get('acme_account_key') or 'ec')
        if self.akind not in ACME_KEY_WORDS:
            self.akind = 'ec'
        if row.get('directory') != self.dir_url or not pem or \
                (row.get('kind') or 'ec') != self.akind:
            pem = ''
        if fresh:
            self.kid = None
            self._jwk_done = None
            try:
                os.unlink(os.path.join(self.work, 'account.pem'))
            except OSError:
                pass
        if not pem:
            pem = new_key(self.akind)
            row = {}
            self.kid = None
            self._jwk_done = None
            try:
                os.unlink(os.path.join(self.work, 'account.pem'))
            except OSError:
                pass
        self.key_pem = pem
        if row.get('kid'):
            self.kid = row['kid']
            return
        mail = str(CONFIG.get('acme_email') or '').strip()
        payload = {'termsOfServiceAgreed': True}
        if mail:
            payload['contact'] = ['mailto:' + mail]
        body, headers = self.post(self.dir['newAccount'], payload, use_jwk=True)
        self.kid = headers.get('Location')
        if not self.kid:
            raise AcmeError('the CA made no account')
        self.store.set_meta('acme:account', json.dumps({
            'key': seal_secret(pem, 'acme'), 'kid': self.kid, 'directory': self.dir_url,
            'email': mail, 'at': time.time(), 'kind': self.akind}))

    # -- an order --------------------------------------------------------------------
    def _poll(self, url, done, what, secs=90):
        end = time.time() + secs
        while True:
            got, hdr = self.post_json(url, None)
            st = got.get('status')
            if st in done:
                return got
            if st == 'invalid':
                errs = [c.get('error', {}).get('detail') for c in got.get('challenges') or []
                        if c.get('error')] or [got.get('error', {}).get('detail')]
                raise AcmeError('%s: %s' % (what, '; '.join(e for e in errs if e) or 'invalid'))
            if time.time() > end:
                raise AcmeError('%s: the CA has not said in %d s (%s)' % (what, secs, st))
            # As long as the CA asks (Retry-After, 1.0.196), within reason.
            try:
                wait = float(hdr.get('Retry-After') or 2)
            except (TypeError, ValueError):
                wait = 2.0
            time.sleep(max(1.0, min(30.0, wait, max(0.0, end - time.time()))))

    def renewal_info(self, cert_id):
        """The CA's window to renew a certificate in (ARI, RFC 9773), or None."""
        base = self.dir.get('renewalInfo')
        if not base or not cert_id:
            return None
        got, _ = self._get(base.rstrip('/') + '/' + cert_id)
        w = got.get('suggestedWindow') or {}
        start, end = _rfc3339(w.get('start')), _rfc3339(w.get('end'))
        if not start or not end or end < start:
            return None
        return {'start': start, 'end': end, 'url': got.get('explanationURL') or ''}

    def order(self, names, say, key_kind=None, replaces=''):
        say('ordered from the CA' + (' (%s)' % ACME_KEY_WORDS.get(key_kind, key_kind) if key_kind else ''))
        ask = {'identifiers': [{'type': 'dns', 'value': n} for n in names]}
        # The profile asked for (1.0.196), where the CA offers it - tlsserver,
        # shortlived at Let's Encrypt; a CA without profiles is asked as before.
        prof = str(CONFIG.get('acme_profile') or '')
        offered = (self.dir.get('meta') or {}).get('profiles') or {}
        if prof and prof in offered:
            ask['profile'] = prof
        elif prof:
            say('this CA offers no profile %s - its own is used' % prof)
        # The certificate it renews (1.0.196, ARI - RFC 9773): the CA counts it as
        # a renewal, its rate limits too.
        if replaces and self.dir.get('renewalInfo'):
            ask['replaces'] = replaces
        try:
            got, headers = self.post_json(self.dir['newOrder'], ask)
        except AcmeError as e:
            # Only the account that ordered a certificate may say it replaces
            # it (1.0.199): an account made since - another kind of its key,
            # one the CA forgot - is refused ("requester account did not
            # request the certificate being replaced"). Ordered again as a new
            # one: a renewal all the same, just not counted as one.
            if 'replaces' not in ask or 'replace' not in str(e).lower():
                raise
            say('the CA does not take it as the renewal of the one before (another account ordered '
                'that one) - ordered as a new certificate')
            ask.pop('replaces', None)
            got, headers = self.post_json(self.dir['newOrder'], ask)
        order_url = headers.get('Location')
        thumb = self.thumbprint()
        for az in got.get('authorizations') or []:
            a, _ = self.post_json(az, None)
            if a.get('status') == 'valid':
                continue
            name = a.get('identifier', {}).get('value')
            kind = 'dns-01' if (CONFIG.get('acme_challenge') or 'http-01') == 'dns-01' else 'http-01'
            ch = [c for c in a.get('challenges') or [] if c.get('type') == kind]
            if not ch:
                raise AcmeError('the CA offers no %s challenge for %s' % (kind.upper(), name))
            token = ch[0]['token']
            if not re.match(r'^[A-Za-z0-9_-]{8,256}\Z', token):
                raise AcmeError('the CA sent a token that is not one')
            auth = token + '.' + thumb
            if kind == 'dns-01':
                # A TXT record in DNS (1.0.169): for a server the CA cannot
                # reach - nothing has to be open to the internet.
                txt = _b64u(hashlib.sha256(auth.encode()).digest())
                undo = acme_dns_put(self.store, name, txt, say)
                try:
                    say('the CA looks up _acme-challenge.%s' % name)
                    self.post_json(ch[0]['url'], {})
                    self._poll(az, ('valid',), 'the CA did not take %s' % name, 180)
                finally:
                    try:
                        undo()
                    except Exception as e:              # noqa: BLE001
                        log('ACME: the TXT record of %s was not taken away: %s' % (name, e), 'warn')
                continue
            # Kept where every node finds it; the other node's copy of the
            # database has it within seconds.
            self.store.set_meta('acme:chal:' + token, json.dumps(
                {'auth': auth, 'at': time.time(), 'name': name}))
            time.sleep(float(os.environ.get('OTP_ACME_SETTLE') or 3))
            say('the CA looks at http://%s/.well-known/acme-challenge/' % name)
            try:
                self.post_json(ch[0]['url'], {})
                self._poll(az, ('valid',), 'the CA did not take %s' % name)
            finally:
                self.store.db.run('DELETE FROM meta WHERE k = ?', ('acme:chal:' + token,))
        key, csr = make_csr(names[0], names[1:], key_kind or (CONFIG.get('acme_key') or 'ec'))
        der = _openssl(['req', '-in', '/dev/stdin', '-outform', 'DER'], data=csr.encode(),
                       what='the request')
        say('the certificate is made')
        o, _ = self.post_json(got['finalize'], {'csr': _b64u(der)})
        if o.get('status') != 'valid':
            o = self._poll(order_url, ('valid',), 'the order', 120)
        body, _ = self.post(o['certificate'], None)
        return key, body.decode('utf-8')


# ---- what is ordered, and when ----------------------------------------------------------
def acme_name_of(store, target):
    """The DNS name a target's certificate is for."""
    if target == 'vip':
        return str(vip_conf(store).get('fqdn') or '').strip()
    k = 'acme_node_name@' + target
    saved = store.settings_saved()
    name = str(saved.get(k) or (CONFIG.get('acme_node_name') if target == node_name() else '')
               or '').strip()
    if not name and target == node_name():
        name = fqdn_cached()
    if not name:
        # The name of the certificate it has now (1.0.170) - what Certificates
        # and TLS shows: otp2's card said "for -" beside otp2.example.cz.
        info = (tls_profile(store, target) or {}).get('info') or {}
        for n in [info.get('cn')] + list(info.get('san') or []):
            n = str(n or '').strip().lower()
            if re.match(r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})\Z', n):
                name = n
                break
    if not name and target == node_name():
        name = fqdn_cached()
    elif not name and target != 'vip':
        # Another node's own name, as that node publishes it (1.0.170): its
        # card said "for -" and Try port 80 asked http://?/.
        name = str((_meta_json(store, 'acme:host:' + target) or {}).get('fqdn') or '').strip()
    return name


FQDN_CACHE = {'name': '', 'at': 0.0, 'asking': False}


def fqdn_cached():
    """This machine's full name, asked of DNS in a thread of its own and kept for
    ten minutes (1.0.207): socket.getfqdn() waits on a DNS that does not answer -
    20 s and more, twice a loop - and the main loop's heartbeat went late until
    the other node took this one for gone. The host name meanwhile."""
    now = time.monotonic()
    if (not FQDN_CACHE['at'] or now - FQDN_CACHE['at'] > 600) and not FQDN_CACHE['asking']:
        FQDN_CACHE['asking'] = True

        def ask():
            try:
                FQDN_CACHE['name'] = socket.getfqdn() or ''
            except Exception:                           # noqa: BLE001
                pass
            finally:
                FQDN_CACHE['at'] = time.monotonic()
                FQDN_CACHE['asking'] = False
        threading.Thread(target=ask, name='otp-fqdn', daemon=True).start()
    return FQDN_CACHE['name'] or socket.gethostname()


def acme_before(store, target):
    """The certificate a target had before ACME replaced it, as the page may
    see it (no key)."""
    got = _meta_json(store, 'acme:before:' + target) or {}
    if not got.get('cert'):
        return None
    info = got.get('info') or {}
    return {'how': got.get('how'), 'subject': info.get('subject'), 'issuer': info.get('issuer'),
            'not_after': info.get('not_after'), 'at': got.get('at'),
            'ran_out': float(info.get('not_after') or 0) < time.time()}


def acme_put_back(store, target, by):
    """The certificate from before ACME back in place, ACME no longer renewing
    it; its TLS settings (protocols, ciphers, DH, HSTS) stay as they are now."""
    got = _meta_json(store, 'acme:before:' + target) or {}
    if not got.get('cert'):
        raise ValueError('there is no certificate from before ACME for this one')
    info = got.get('info') or {}
    if float(info.get('not_after') or 0) < time.time():
        raise ValueError('the certificate from before ACME ran out on %s - put a new one in on '
                         'Certificates and TLS' % stamp(info.get('not_after')))
    prof = tls_profile(store, target) or {}
    prof.update({k: got.get(k) for k in ('cert', 'chain', 'root', 'key', 'info', 'chain_info',
                                         'root_info', 'verify', 'how')})
    prof.pop('pending_key', None)
    prof.pop('csr', None)
    tls_save(store, target, prof, by)
    store.set_meta('acme:care:' + target, json.dumps({'on': False, 'at': time.time(), 'by': by}))
    store.db.run('DELETE FROM meta WHERE k = ?', ('acme:before:' + target,))
    store.add_event('settings', '%s put the certificate of %s from before ACME back (%s, until %s); '
                    'ACME no longer renews it' % (by, 'the VIP address' if target == 'vip' else
                                                  target, info.get('issuer') or '?',
                                                  stamp(info.get('not_after'))), 'warn', who=by)


def acme_care(store, target):
    """Whether ACME looks after this certificate (1.0.170). Said on either page;
    unsaid: yes for one from the CA, a self-signed one and none at all - never
    for one uploaded or answered to a request (a CA of your own): switching ACME
    on does not replace those."""
    got = _meta_json(store, 'acme:care:' + target)
    if got and 'on' in got:
        return bool(got['on'])
    prof = tls_profile(store, target) or {}
    how = str(prof.get('how') or '')
    return not prof.get('cert') or how == 'ACME' or how.startswith('self-signed')


def acme_care_set(store, target, on, by, why=''):
    was = acme_care(store, target)
    store.set_meta('acme:care:' + target, json.dumps({'on': bool(on), 'at': time.time(),
                                                     'by': by}))
    if was != bool(on) and CONFIG.get('acme'):
        store.add_event('settings', '%s: ACME %s the certificate of %s%s' % (
            by, 'looks after' if on else 'no longer renews', 'the VIP address' if target == 'vip'
            else target, (' - ' + why) if why else ''), 'info' if on else 'warn', who=by)


ACME_HOST = {'at': 0.0, 'fqdn': None}


def acme_host_publish(store):
    """This node's full name, for the cards of the other nodes - once in ten
    minutes, written only when it changed."""
    if time.time() - ACME_HOST['at'] < 600:
        return
    ACME_HOST['at'] = time.time()
    fqdn = socket.getfqdn()
    if fqdn == ACME_HOST['fqdn']:
        return
    store.set_meta('acme:host:' + node_name(), json.dumps({'fqdn': fqdn, 'at': time.time()}))
    ACME_HOST['fqdn'] = fqdn


def acme_targets(store):
    """[(target, name)] this node orders: the VIP address's on the lead, and
    its own where asked."""
    if not CONFIG.get('acme'):
        return []
    want = CONFIG.get('acme_for') or 'vip'
    out = []
    if want in ('vip', 'both') and vip_conf(store).get('on') and alerts_lead(store):
        out.append(('vip', acme_name_of(store, 'vip')))
    if want in ('node', 'both') or (want == 'vip' and not vip_conf(store).get('on')):
        out.append((node_name(), acme_name_of(store, node_name())))
    return [(t, n) for t, n in out if n and acme_care(store, t)]


def acme_wanted(store):
    """The certificates asked for at all (For), whichever node renews them."""
    want = CONFIG.get('acme_for') or 'vip'
    out = []
    for t in tls_targets(store):
        if t == 'vip':
            if want in ('vip', 'both') and vip_conf(store).get('on'):
                out.append(t)
        elif want in ('node', 'both') or (want == 'vip' and not vip_conf(store).get('on')):
            out.append(t)
    return out


def acme_state(store, target):
    return _meta_json(store, 'acme:state:' + target) or {}


def acme_due(store, target, name):
    """Why this certificate is to be ordered now, or ''."""
    st = acme_state(store, target)
    if st.get('failed_at') and time.time() - float(st['failed_at']) < ACME_RETRY and \
            st.get('name') == name:
        return ''
    prof = tls_profile(store, target) or {}
    info = prof.get('info') or {}
    if prof.get('how') != 'ACME' or st.get('name') != name:
        return 'not ordered yet for %s' % name
    # The CA's own window (ARI, 1.0.196), looked up every few hours: renewed at
    # a moment picked in it - early too, where the CA says so (a revocation).
    # Earlier only, never later than otp's own measure below: a window gone
    # wrong (a CA's mistake, a clock) does not let a certificate run out.
    ari = _meta_json(store, 'acme:ari:' + target) or {}
    if ari.get('pick') and ari.get('cert') == (info.get('fingerprint') or '') and \
            time.time() - float(ari.get('at') or 0) < 2 * 86400 and time.time() >= float(ari['pick']):
        return 'the CA\'s renewal window (%s - %s)' % (stamp(ari['start']), stamp(ari['end']))
    left = (float(info.get('not_after') or 0) - time.time()) / 86400
    days = float(CONFIG.get('acme_days') or 30)
    # A third of its life at most (1.0.187): a CA giving fewer days than
    # acme_days (short-lived certificates, a test CA) had every new one due
    # at once - ordered again every hour, until its limits refused them all.
    life = (float(info.get('not_after') or 0) - float(info.get('not_before') or 0)) / 86400
    if info.get('not_before') and life > 0:
        days = min(days, life / 3)
    if left < days:
        return '%d days left' % int(left)
    return ''


def acme_order(store, target, name, by, say=None):
    """One certificate ordered and put in; the state kept, an event written -
    and what was done on the way (1.0.175), for the card."""
    tell = say or (lambda t: None)
    steps = []

    def say(t):
        steps.append([round(time.time(), 1), str(t)[:300]])
        tell(t)
    if not re.match(r'^(?=.{1,253}\Z)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'
                    r'(?:[A-Za-z]{2,63}|[Xx][Nn]--[A-Za-z0-9-]{1,59})\Z', name):   # .рф too (1.0.209)
        raise AcmeError('%s is not a name a CA gives a certificate for (a full DNS name)' % name)
    st = {'name': name, 'at': time.time(), 'by': by, 'ca': acme_directory_url(), 'steps': steps}
    a = None
    try:
        a = Acme(store)
        choice = str(CONFIG.get('acme_key') or 'dual')
        kinds = ACME_CERT_KEYS.get(choice) or ('ec',)
        prof = tls_profile(store, target) or {}
        replaces = ari_cert_id(prof.get('cert')) if prof.get('how') == 'ACME' else ''
        # Said only by the account that ordered it (1.0.199); one of before
        # this was kept is tried, and ordered again without it if refused.
        was = acme_state(store, target)
        if replaces and was.get('kid') and was['kid'] != a.kid:
            replaces = ''
        say('the key%s: %s' % ('s' if len(kinds) > 1 else '', ' + '.join(ACME_KEY_WORDS[k] for k in kinds)))
        key, chain = a.order([name], say, kinds[0], replaces)
        got = cert_bundle(chain, key)
        info = got['info']
        alt = None
        made = [kinds[0]]
        if len(kinds) > 1:
            # The second certificate (1.0.196, as Let's Encrypt advises): the name
            # is already proven, so the CA only signs - nginx offers it to the
            # clients that take it, RSA to the rest.
            say('a second certificate, with a %s key' % ACME_KEY_WORDS[kinds[1]])
            try:
                k2, c2 = a.order([name], say, kinds[1])
                g2 = cert_bundle(c2, k2)
                alt = {'cert': g2['cert'], 'chain': g2['chain'],
                       'key': seal_secret(g2['key'], 'web:tls'),
                       'info': g2['info'], 'for': tls_alt_for(got['cert'])}
                made.append(kinds[1])
            except (AcmeError, ValueError) as e:
                # The first one kept all the same (1.0.205): thrown away with it,
                # the CA's weekly limit for the name was spent on nothing, and
                # every retry refused for a week.
                say('the second certificate did not come (%s) - the %s one is put in alone'
                    % (str(e)[:200], ACME_KEY_WORDS[kinds[0]]))
                st['alt_said'] = str(e)[:300]
        # As it is now, not as it was when the order began (1.0.205): an order
        # takes minutes, an hour by hand - what was changed on Certificates and
        # TLS meanwhile is kept, and one no longer looked after is left alone.
        prof = tls_profile(store, target) or {}
        if not acme_care(store, target):
            raise AcmeError('ACME was told to leave this certificate alone while it was being '
                            'ordered - the new one is not put in')
        if prof.get('cert') and prof.get('how') != 'ACME':
            # The certificate it had - uploaded, from your own CA - kept to go
            # back to (1.0.172): ACME switched off or left alone, it is put
            # back with a click, its key as sealed as it was.
            store.set_meta('acme:before:' + target, json.dumps(
                {k: prof.get(k) for k in ('cert', 'chain', 'root', 'key', 'info', 'chain_info',
                                          'root_info', 'verify', 'how')}
                | {'at': time.time()}))
        prof.update(cert=got['cert'], chain=got['chain'], root=got['root'],
                    key=seal_secret(got['key'], 'web:tls'), info=info,
                    chain_info=got['chain_info'], root_info=got['root_info'],
                    verify=got['verify'], how='ACME')
        if alt:
            prof['alt'] = alt
        else:
            prof.pop('alt', None)
        prof.pop('pending_key', None)
        prof.pop('csr', None)
        prof.setdefault('preset', 'standard')
        prof.setdefault('dh', 'none')
        tls_save(store, target, prof, by)
        st['kid'] = a.kid or ''
        st.update(ok=True, not_after=info.get('not_after'), issuer=info.get('issuer'),
                  ordered_at=time.time(), keys=' + '.join(ACME_KEY_WORDS[k] for k in made))
        st['steps'] = steps[-25:]
        store.set_meta('acme:state:' + target, json.dumps(st))
        store.add_event('settings', 'a certificate for %s (%s) came from the CA, good until %s'
                        % (name, 'the VIP address' if target == 'vip' else target,
                           stamp(info.get('not_after')) if info.get('not_after') else '?'),
                        'info', who=by)
        return st
    except Exception as e:                              # noqa: BLE001
        # Every failure written down (1.0.234): an odd answer of the CA (KeyError) or openssl
        # timing out was only logged - the order was due again within the hour, every hour.
        if not isinstance(e, (AcmeError, ValueError, OSError)):
            e = AcmeError('%s: %s' % (type(e).__name__, e))
        if 'NXDOMAIN' in str(e) and (CONFIG.get('acme_challenge') or '') == 'dns-01':
            e = AcmeError('%s - the CA does not find the record: In your DNS → Check DNS, with '
                          'DNS servers for ACME set to public ones (1.1.1.1), shows where the way '
                          'to it stops (the CNAME, or the delegation of its zone)' % e)
        st.update(ok=False, failed_at=time.time(), said=str(e)[:600])
        old = acme_state(store, target)
        for k in ('not_after', 'issuer', 'ordered_at', 'kid'):
            if old.get(k):
                st[k] = old[k]
        st['steps'] = steps[-25:]
        store.set_meta('acme:state:' + target, json.dumps(st))
        store.add_event('settings', 'no certificate for %s came from the CA: %s' % (name, e),
                        'bad', who=by)
        raise AcmeError(str(e))
    finally:
        if a:
            a.close()


ACME_ARI = {'at': 0.0}
ACME_ARI_EVERY = float(os.environ.get('OTP_ACME_ARI_EVERY') or 6 * 3600)


def acme_ari_refresh(store):
    """Each certificate this node orders: the CA's window to renew it in (ARI),
    a moment in it picked once - kept for acme_due."""
    try:
        targets = acme_targets(store)
    except Exception:                                   # noqa: BLE001
        return
    a = None
    try:
        for t, _name in targets:
            prof = tls_profile(store, t) or {}
            if prof.get('how') != 'ACME' or not prof.get('cert'):
                continue
            cid = ari_cert_id(prof['cert'])
            if not cid:
                continue
            if a is None:
                a = Acme(store)
                if not a.dir.get('renewalInfo'):
                    return                              # this CA has no ARI
            w = a.renewal_info(cid)
            if not w:
                continue
            fp = (prof.get('info') or {}).get('fingerprint') or ''
            was = _meta_json(store, 'acme:ari:' + t) or {}
            pick = was.get('pick') if (was.get('start'), was.get('end'), was.get('cert')) == \
                (w['start'], w['end'], fp) else None
            if not pick:
                pick = w['start'] + secrets.randbelow(max(1, int(w['end'] - w['start'])))
            store.set_meta('acme:ari:' + t, json.dumps(dict(w, pick=pick, at=time.time(), cert=fp)))
    except Exception as e:                              # noqa: BLE001
        log_sparing('acme-ari', 'ACME: the renewal window not asked: %s' % e, 'warn', every=6 * 3600)
    finally:
        if a:
            a.close()


def acme_tick(daemon):
    """Once an hour: what is due, ordered - in a thread of its own."""
    # In a thread (1.0.186): socket.getfqdn() waits on a DNS that does not
    # answer, and this is the main loop's.
    if time.time() - ACME_HOST['at'] >= 600:
        def pub():
            try:
                acme_host_publish(daemon.store)
            except Exception:                           # noqa: BLE001
                pass
        threading.Thread(target=pub, name='otp-acme-host', daemon=True).start()
    if CONFIG.get('acme') and time.time() - ACME_ARI['at'] >= ACME_ARI_EVERY and not ACME_WORK['busy']:
        ACME_ARI['at'] = time.time()
        def ari(store=daemon.store):
            with acme_dns_scope():      # the CA looked up as the orders look it up (1.0.205)
                acme_ari_refresh(store)
        threading.Thread(target=ari, name='otp-acme-ari', daemon=True).start()
    if not CONFIG.get('acme') or ACME_WORK['busy'] or \
            time.time() - ACME_WORK['at'] < ACME_EVERY:
        return
    ACME_WORK['at'] = time.time()
    store = daemon.store

    def look():
        # What is due worked out in a thread too (1.0.205): with no name given,
        # a node's own is socket.getfqdn(), which waits on a DNS that does not
        # answer - the main loop with it.
        try:
            due = [(t, n) for t, n in acme_targets(store) if acme_due(store, t, n)]
            if due and not ACME_WORK['busy']:
                acme_start(store, due, 'otp (renewal)')
        except Exception as e:                          # noqa: BLE001
            log_sparing('acme-due', 'ACME: what is due could not be looked at: %s' % e, 'warn',
                        every=3600)
    threading.Thread(target=look, name='otp-acme-due', daemon=True).start()


def acme_parallel_why(which):
    """Why these are ordered one after another, or '' when side by side
    (1.0.203). By hand, the page shows one TXT record at a time; acme-dns keeps
    the last two TXT records of its one subdomain for every name - a third
    order side by side would push one out."""
    if len(which) < 2 or ACME_PARALLEL < 2:
        return 'one'
    if (CONFIG.get('acme_challenge') or 'http-01') == 'dns-01':
        how = CONFIG.get('acme_dns') or 'manual'
        if how == 'manual':
            return 'by hand'
        if how == 'acmedns':
            return 'acme-dns'
    names = [n for _t, n in which]
    if len(set(names)) != len(names):
        return 'the same name twice'
    return ''


def acme_start(store, which, by):
    with _ACME_LOCK:
        if ACME_WORK['busy']:
            raise ValueError('a certificate is being ordered already')
        ACME_WORK.update(busy=True, says='starting', target='', n=0, of=len(which), done=0, each={})

    def one(t, n, i):
        # Each in a thread of its own: its names looked up by ACME's DNS
        # servers, its words on its own card.
        _ACME_DNS.on = True
        _ACME_CUR.target = t
        with _ACME_LOCK:
            ACME_WORK['each'][t] = {'says': 'starting', 'at': time.time(), 'n': i + 1}
            ACME_WORK.update(target=t, n=max(ACME_WORK['n'], i + 1))
        lease = 'acme:busy:%s' % t
        try:
            # One node orders a certificate at a time (1.0.209): ordered from the
            # other node's pages while this one renewed it, both spent the CA's
            # limit and the last one saved won. Held half an hour at most.
            try:
                held = json.loads(store.get_meta(lease) or '{}')
            except ValueError:
                held = {}
            if held.get('node') and held['node'] != node_name() and \
                    float(held.get('until') or 0) > time.time():
                log('ACME: %s is being ordered on %s already - not ordered here too'
                    % (n, held['node']), 'warn')
                return
            store.set_meta(lease, json.dumps({'node': node_name(), 'until': time.time() + 1800}))
            acme_order(store, t, n, by, acme_progress)
        except AcmeError as e:
            log('ACME: %s' % e, 'warn')
        except Exception as e:                          # noqa: BLE001
            # Never the others with it: one order gone wrong is said, the rest go on.
            log('ACME: the order for %s stopped: %s' % (n, e), 'error')
        finally:
            try:
                if json.loads(store.get_meta(lease) or '{}').get('node') == node_name():
                    store.db.run('DELETE FROM meta WHERE k = ?', (lease,))
            except Exception:                           # noqa: BLE001
                pass
            with _ACME_LOCK:
                ACME_WORK['each'].pop(t, None)
                ACME_WORK['done'] += 1
            _ACME_CUR.target = ''

    def go():
        _ACME_DNS.on = True
        try:
            why = acme_parallel_why(which)
            if not why:
                # The account first, once (1.0.203): orders side by side, each
                # finding none (a new kind of its key, one the CA forgot), would
                # make an account each.
                try:
                    a = Acme(store)
                    a.close()
                except Exception as e:                  # noqa: BLE001
                    why = 'the account not ready (%s)' % str(e)[:120]
            if why:
                for i, (t, n) in enumerate(which):
                    one(t, n, i)
                return
            gate = threading.Semaphore(ACME_PARALLEL)
            threads = []

            def gated(t, n, i):
                with gate:
                    one(t, n, i)
            for i, (t, n) in enumerate(which):
                th = threading.Thread(target=gated, args=(t, n, i), name='otp-acme-%s' % t, daemon=True)
                th.start()
                threads.append(th)
            for th in threads:
                th.join()
        finally:
            with _ACME_LOCK:
                ACME_WORK.update(busy=False, says='', target='', n=0, of=0, done=0, each={})
    threading.Thread(target=go, name='otp-acme', daemon=True).start()


def acme_challenge(store, token):
    """The answer for the CA, or None: what acme.php gives on port 80."""
    if not re.match(r'^[A-Za-z0-9_-]{8,256}\Z', str(token or '')):
        return None
    got = _meta_json(store, 'acme:chal:' + token) or {}
    if not got.get('auth') or time.time() - float(got.get('at') or 0) > 3600:
        return None
    return got['auth']


def acme_work_view():
    """What is being ordered, copied under the lock: the orders side by side
    change it while it is read."""
    with _ACME_LOCK:
        out = dict(ACME_WORK)
        out['each'] = {t: dict(v) for t, v in ACME_WORK['each'].items()}
    return out


def acme_view(store):
    out = []
    for t in tls_targets(store):
        if t == 'vip' and not vip_conf(store).get('on'):
            continue
        prof = tls_profile(store, t) or {}
        info = prof.get('info') or {}
        out.append({'target': t, 'name': acme_name_of(store, t), 'state': acme_state(store, t),
                    'how': prof.get('how') or '', 'subject': info.get('subject'),
                    'issuer': info.get('issuer'), 'not_after': info.get('not_after'),
                    'keys': ' + '.join(x for x in [info.get('key') or '',
                                                   ((tls_alt(prof) or {}).get('info') or {}).get('key') or '']
                                       if x),
                    'care': acme_care(store, t), 'wanted': t in acme_wanted(store),
                    'before': acme_before(store, t),
                    'named': bool(str(store.settings_saved().get('acme_node_name@' + t) or '')
                                  .strip()) if t != 'vip' else bool(vip_conf(store).get('fqdn'))})
    mine = [t for t, _ in acme_targets(store)]
    acc = _meta_json(store, 'acme:account') or {}
    return {'on': bool(CONFIG.get('acme')), 'targets': out, 'mine': mine,
            'directory': acme_directory_url(), 'account': {
                'kid': acc.get('kid'), 'email': acc.get('email'), 'at': acc.get('at'),
                'key': ACME_KEY_WORDS.get(acc.get('kind') or 'ec', '') if acc.get('kid') else ''},
            'work': acme_work_view(), 'node': node_name(),
            'challenge': CONFIG.get('acme_challenge') or 'http-01',
            'dns_guide': acme_dns_guide(store),
            'manual': {k: v for k, v in (_meta_json(store, 'acme:manual') or {}).items()
                       if k in ('rr', 'txt', 'at', 'done')} or None}


def acme_probe(store, target):
    """Whether http://NAME/.well-known/acme-challenge/ reaches an otp node that
    answers - asked from here, straight, as the CA will (from outside it may
    still be blocked: a firewall in front sees only what reaches it)."""
    name = acme_name_of(store, target) if target else ''
    if not name:
        raise ValueError('which certificate? its name is not known')
    token = 'otp-probe-' + secrets.token_urlsafe(16)
    want = token + '.' + secrets.token_urlsafe(8)
    store.set_meta('acme:chal:' + token, json.dumps({'auth': want, 'at': time.time(),
                                                    'name': name, 'probe': True}))
    url = 'http://%s/.well-known/acme-challenge/%s' % (name, token)
    began = time.time()
    out = {'name': name, 'url': url, 'ok': False}
    scope = acme_dns_scope()
    scope.__enter__()
    try:
        time.sleep(float(os.environ.get('OTP_ACME_SETTLE') or 3))
        req = urllib.request.Request(url, headers={'User-Agent': 'otp/%s (acme probe)' % __version__})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=10) as r:
            body = r.read(4096).decode('utf-8', 'replace').strip()
        out.update(ok=body == want, status=r.status,
                   said='answered as the CA wants it' if body == want else
                   'something answers on port 80, but not otp\'s answer: %r' % body[:80])
    except urllib.error.HTTPError as e:
        out['said'] = 'port 80 answers %d - nginx does not send /.well-known/acme-challenge/ to otp' % e.code
    except (OSError, ValueError) as e:
        out['said'] = 'port 80 of %s cannot be reached: %s' % (name, getattr(e, 'reason', e))
    finally:
        scope.__exit__()
        store.db.run('DELETE FROM meta WHERE k = ?', ('acme:chal:' + token,))
    out['ms'] = int((time.time() - began) * 1000)
    return out


def acme_http_names(store):
    """The names this node's port 80 answers the CA for."""
    want = CONFIG.get('acme_for') or 'vip'
    vip_on = bool(vip_conf(store).get('on'))
    out = []
    if want in ('vip', 'both') and vip_on:
        out.append(acme_name_of(store, 'vip'))
    if want in ('node', 'both') or (want == 'vip' and not vip_on):
        out.append(acme_name_of(store, node_name()))
    return [n for n in out if n and re.match(r'^[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z', n)]


# ---- DNS-01: the TXT record put in DNS (1.0.169) -------------------------------------
# For a server the CA cannot reach: _acme-challenge.NAME TXT, put in by
#   rfc2136    - nsupdate with a TSIG key (BIND, PowerDNS, Knot...), the key in a
#                file only otp reads for the moment it runs, never on a command line;
#   cloudflare - its API, with a token that may edit the zone's DNS;
#   acmedns    - an acme-dns server (_acme-challenge.NAME a CNAME to its subdomain);
#   manual     - shown on the page; the order waits until it is said to be there.
# Then waited for (acme_dns_wait s) and taken away again once the CA has looked.
NSUPDATE = os.environ.get('OTP_NSUPDATE') or 'nsupdate'


def _dns_wait(say, least=0):
    w = max(int(CONFIG.get('acme_dns_wait') or 0),
            int(os.environ.get('OTP_ACME_DNS_LEAST', least)))
    if w:
        say('waiting %d s for DNS to carry it' % w)
        time.sleep(w)


def acme_dns_where(name):
    """(where the TXT record goes, the CNAME your DNS needs or None) - 1.0.170.
    The record goes to _acme-challenge.NAME itself, or - with a zone of its own
    for them (deSEC, acme_dns_alias) - to _acme-challenge.LABEL.ZONE, and
    _acme-challenge.NAME is a CNAME to it in your DNS, put in once: the CA
    follows it. So a domain whose DNS has no API gets certificates by itself."""
    name = str(name or '').rstrip('.').lower()
    own = '_acme-challenge.' + name
    how = CONFIG.get('acme_dns') or 'manual'
    if how == 'acmedns':
        url = str(CONFIG.get('acme_dns_url') or '').strip()
        host = urllib.parse.urlparse(url).hostname or ''
        sub = str(CONFIG.get('acme_dns_subdomain') or '').strip()
        return own, ('%s.%s' % (sub, host) if sub and host else '')
    zone = str(CONFIG.get('acme_dns_alias') or '').strip().rstrip('.').lower()
    if how == 'desec':
        dom = str(CONFIG.get('acme_desec_domain') or '').strip().rstrip('.').lower()
        if dom and (name == dom or name.endswith('.' + dom)):
            return own, None                            # its DNS is at deSEC itself
        if not zone or not (zone == dom or zone.endswith('.' + dom)):
            zone = dom
    if not zone or name == zone or name.endswith('.' + zone):
        return own, None
    there = '_acme-challenge.%s.%s' % (name.split('.')[0], zone)
    return there, there


def acme_dns_put(store, name, txt, say):
    """The TXT record put in; returns what takes it away again."""
    how = CONFIG.get('acme_dns') or 'manual'
    rr, cname = acme_dns_where(name)
    if cname and how != 'acmedns':
        say('the TXT record %s put in DNS (%s; _acme-challenge.%s is a CNAME to it)'
            % (rr, how, name))
    else:
        say('the TXT record %s put in DNS (%s)' % (rr, how))
    if how == 'rfc2136':
        undo = _dns_rfc2136(rr, txt)
    elif how == 'cloudflare':
        undo = _dns_cloudflare(rr, txt)
    elif how == 'acmedns':
        undo = _dns_acmedns(txt)
    elif how == 'desec':
        undo = _dns_desec(rr, txt)
    else:
        undo = _dns_manual(store, rr, txt, say)
    if how == 'desec':
        _desec_seen(rr, txt, say)
    else:
        _dns_wait(say)
        if how != 'manual':
            acme_txt_seen(name, txt, say)
    return undo


DESEC_NS = ('ns1.desec.io', 'ns2.desec.org')


def _desec_seen(rr, txt, say):
    """deSEC's own name servers asked until both have the record (1.0.175),
    then a while more: they are anycast, and the CA asks from several places
    of the world - "During secondary validation: NXDOMAIN" was a place deSEC
    had not reached yet. Asked straight, never through a resolver, so no
    resolver keeps "not there" for the CA."""
    _dns_wait(say)
    addrs = []
    for ns in DESEC_NS:
        try:
            addrs += [(ns, a) for t, a in dns_ask(ns, 1) if t == 'A'][:1]
        except OSError:
            pass
    if not addrs:
        say('deSEC\'s name servers not found - waited %d s instead' % 120)
        _dns_wait(say, 120)
        return
    began = time.time()
    end = began + float(os.environ.get('OTP_DESEC_PROPAGATION') or 300)
    while True:
        seen = []
        for ns, a in addrs:
            try:
                rc, got = _dns_parse(_dns_ask(a, rr, 16, 3.0))
                if txt in [v for t, v in got if t == 'TXT']:
                    seen.append(ns)
            except OSError:
                pass
        if len(seen) == len(addrs):
            break
        if time.time() > end:
            say('%s TXT not on every deSEC name server yet (%s) - the CA is asked anyway'
                % (rr, ', '.join(seen) or 'none'))
            return
        # What is waited for, said as it goes (1.0.176): the line said "waited
        # 5 s" for minutes while deSEC was being asked.
        acme_progress('waiting for deSEC\'s name servers to have the record - %s so far, %d s' % (
            ', '.join(seen) or 'none', int(time.time() - began)))
        time.sleep(5)
    settle = float(os.environ.get('OTP_DESEC_SETTLE') or 60)
    say('%s TXT is on %s after %d s; %d s more for deSEC\'s other places' % (
        rr, ', '.join(seen), int(time.time() - began), settle))
    left = settle
    while left > 0:
        acme_progress('%d s more for deSEC\'s other places of the world, then the CA is asked' % left)
        time.sleep(min(5, left))
        left -= 5


def _dns_rfc2136(rr, txt):
    server = str(CONFIG.get('acme_dns_server') or '').strip()
    if not server:
        raise AcmeError('the DNS server for the updates is not set')
    keyname = str(CONFIG.get('acme_dns_tsig_name') or '').strip()
    secret = unseal_secret(CONFIG.get('acme_dns_tsig_secret') or '') or ''
    alg = CONFIG.get('acme_dns_tsig_alg') or 'hmac-sha256'
    # [v6]:port, a bare IPv6 address (port 53), or host:port (1.0.206): split on
    # the first colon, an IPv6 server came out as "server 2001 db8::53".
    m = re.match(r'^\[([^\]]+)\](?::(\d+))?\Z', server)
    if m:
        host, port = m.group(1), m.group(2) or ''
    elif server.count(':') > 1:
        host, port = server, ''
    else:
        host, _, port = server.partition(':')
    zone = str(CONFIG.get('acme_dns_zone') or '').strip()

    def run(op):
        work = tempfile.mkdtemp(prefix='otp-dns-', dir=str(STATE_DIR))
        os.chmod(work, 0o700)
        try:
            args = [NSUPDATE]
            if keyname:
                kf = os.path.join(work, 'tsig.key')
                fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as f:
                    f.write('key "%s" {\n  algorithm %s;\n  secret "%s";\n};\n' % (keyname, alg, secret))
                args += ['-k', kf]
            script = 'server %s %s\n' % (host, port or '53')
            if zone:
                script += 'zone %s\n' % zone
            script += 'update %s %s 60 TXT "%s"\nsend\n' % (op, rr, txt) if op == 'add' else \
                'update delete %s TXT "%s"\nsend\n' % (rr, txt)
            try:
                got = subprocess.run(args, input=script, capture_output=True, text=True, timeout=60)
            except FileNotFoundError:
                raise AcmeError('nsupdate is not on this machine (dnf install bind-utils)')
            if got.returncode != 0:
                raise AcmeError('the DNS server did not take the update: %s'
                                % (got.stderr or got.stdout).strip()[-300:])
        finally:
            shutil.rmtree(work, ignore_errors=True)
    run('add')
    return lambda: run('delete')


def _cf(method, path, body=None):
    tok = unseal_secret(CONFIG.get('acme_dns_token') or '') or ''
    if not tok:
        raise AcmeError('the Cloudflare API token is not set')
    base = str(os.environ.get('OTP_CF_API') or 'https://api.cloudflare.com/client/v4').rstrip('/')
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + tok,
                                          'Content-Type': 'application/json',
                                          'User-Agent': 'otp/%s (acme)' % __version__})
    try:
        with url_open(req, purpose='acme_dns', timeout=30, context=ssl.create_default_context()
                      if base.startswith('https') else None) as r:
            got = json.loads(r.read(1 << 20).decode())
    except urllib.error.HTTPError as e:
        try:
            got = json.loads(e.read().decode())
        except ValueError:
            got = {}
        raise AcmeError('Cloudflare said %d: %s' % (e.code, '; '.join(
            x.get('message', '') for x in got.get('errors') or []) or e.reason))
    if not got.get('success'):
        raise AcmeError('Cloudflare said no: %s' % '; '.join(
            x.get('message', '') for x in got.get('errors') or []))
    return got.get('result')


def _dns_cloudflare(rr, txt):
    labels = rr.split('.')
    zone_id = None
    for i in range(1, len(labels) - 1):
        z = '.'.join(labels[i:])
        got = _cf('GET', '/zones?name=' + urllib.parse.quote(z))
        if got:
            zone_id = got[0]['id']
            break
    if not zone_id:
        raise AcmeError('Cloudflare has no zone for %s that the token may see' % rr)
    rec = _cf('POST', '/zones/%s/dns_records' % zone_id,
              {'type': 'TXT', 'name': rr, 'content': txt, 'ttl': 60})
    return lambda: _cf('DELETE', '/zones/%s/dns_records/%s' % (zone_id, rec['id']))


def _dns_acmedns(txt):
    url = str(CONFIG.get('acme_dns_url') or '').strip().rstrip('/')
    if not url:
        raise AcmeError('the acme-dns server is not set')
    req = urllib.request.Request(url + '/update', method='POST', data=json.dumps(
        {'subdomain': str(CONFIG.get('acme_dns_subdomain') or ''), 'txt': txt}).encode(),
        headers={'X-Api-User': str(CONFIG.get('acme_dns_user') or ''),
                 'X-Api-Key': unseal_secret(CONFIG.get('acme_dns_key') or '') or '',
                 'Content-Type': 'application/json'})
    try:
        with url_open(req, purpose='acme_dns', timeout=30, context=ssl.create_default_context()
                      if url.startswith('https') else None) as r:
            r.read(4096)
    except urllib.error.HTTPError as e:
        raise AcmeError('acme-dns said %d: %s' % (e.code, e.read(300).decode('utf-8', 'replace')))
    except OSError as e:
        raise AcmeError('acme-dns did not answer: %s' % getattr(e, 'reason', e))
    return lambda: None             # acme-dns keeps the last two; nothing to take away


def _desec(method, path, body=None):
    """deSEC's API (1.0.170): Authorization: Token; a 429 waited out (it says
    how long) up to twice."""
    tok = unseal_secret(CONFIG.get('acme_desec_token') or '') or ''
    if not tok:
        raise AcmeError('the deSEC API token is not set')
    base = str(os.environ.get('OTP_DESEC_API') or 'https://desec.io/api/v1').rstrip('/')
    for attempt in range(3):
        req = urllib.request.Request(base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': 'Token ' + tok,
                                              'Content-Type': 'application/json',
                                              'User-Agent': 'otp/%s (acme)' % __version__})
        try:
            with url_open(req, purpose='acme_dns', timeout=30, context=ssl.create_default_context()
                          if base.startswith('https') else None) as r:
                raw = r.read(1 << 20)
                return json.loads(raw.decode()) if raw.strip() else None
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == 'GET':
                return None
            if e.code == 429 and attempt < 2:
                try:
                    pause = float(e.headers.get('Retry-After') or 5)
                except ValueError:
                    pause = 5
                time.sleep(min(max(pause, 1), 60))
                continue
            said = e.read(400).decode('utf-8', 'replace')
            raise AcmeError('deSEC said %d: %s' % (e.code, said.strip() or e.reason))
        except OSError as e:
            raise AcmeError('deSEC did not answer: %s' % getattr(e, 'reason', e))
    raise AcmeError('deSEC asked to wait too long (429)')


def _dns_desec(rr, txt):
    dom = str(CONFIG.get('acme_desec_domain') or '').strip().rstrip('.').lower()
    if not dom:
        raise AcmeError('the domain at deSEC is not set')
    if not rr.endswith('.' + dom):
        raise AcmeError('%s is not in %s' % (rr, dom))
    sub = rr[:-len(dom) - 1]
    path = '/domains/%s/rrsets/' % urllib.parse.quote(dom)
    info = _desec('GET', '/domains/%s/' % urllib.parse.quote(dom))
    if info is None:
        raise AcmeError('deSEC has no domain %s that the token may see' % dom)
    ttl = max(int(info.get('minimum_ttl') or 3600), 60)
    one = '"%s"' % txt

    def have():
        got = _desec('GET', '%s%s/TXT/' % (path, urllib.parse.quote(sub))) or {}
        return list(got.get('records') or [])

    recs = have()
    if one not in recs:
        recs.append(one)
    _desec('PATCH', path, [{'subname': sub, 'type': 'TXT', 'ttl': ttl, 'records': recs}])

    def undo():
        left = [x for x in have() if x != one]
        _desec('PATCH', path, [{'subname': sub, 'type': 'TXT', 'ttl': ttl, 'records': left}])
    return undo


ACME_MANUAL_WAIT = float(os.environ.get('OTP_ACME_MANUAL_WAIT') or 3600)


def _dns_manual(store, rr, txt, say):
    """Shown on the page; waited for until somebody says it is in DNS."""
    ident = secrets.token_hex(6)
    end = time.time() + ACME_MANUAL_WAIT
    # One at a time in the cluster (1.0.234): the other node's order, waiting on its own record,
    # was given up the moment this one wrote over the one row the page shows.
    while True:
        cur = _meta_json(store, 'acme:manual') or {}
        mine = cur.get('node') in (None, node_name())
        stale = time.time() - float(cur.get('at') or 0) > ACME_MANUAL_WAIT + 60
        if not cur or mine or cur.get('done') or stale:
            break
        if time.time() > end:
            raise AcmeError('the manual DNS step of %s held the page for an hour' % cur.get('node'))
        say('waiting for %s: its own record is asked for on the page first' % cur.get('node'))
        time.sleep(5)
    store.set_meta('acme:manual', json.dumps({'id': ident, 'rr': rr, 'txt': txt, 'at': time.time(),
                                              'node': node_name()}))
    say('waiting: put %s TXT "%s" in DNS, then say so on the page' % (rr, txt))
    try:
        while time.time() < end:
            got = _meta_json(store, 'acme:manual') or {}
            if got.get('id') != ident:
                raise AcmeError('the manual DNS step was given up')
            if got.get('done'):
                return lambda: None
            time.sleep(2)
        raise AcmeError('nobody said the TXT record was in DNS within an hour')
    finally:
        got = _meta_json(store, 'acme:manual') or {}
        if got.get('id') == ident:
            store.db.run("DELETE FROM meta WHERE k = 'acme:manual'")


# ---- what goes into your DNS, and whether it is there (1.0.170) -------------------------
def acme_resolvers():
    """The DNS servers ACME asks (1.0.172): its own setting, else the
    machine's (/etc/resolv.conf) - never the mail's."""
    out = []
    for w in re.split(r'[\s,;]+', str(CONFIG.get('acme_resolvers') or '')):
        try:
            out.append(str(ipaddress.ip_address(w)))
        except ValueError:
            pass
    return out


def _os_resolvers():
    out = []
    try:
        with open('/etc/resolv.conf') as f:
            for line in f:
                bits = line.split()
                if len(bits) >= 2 and bits[0] == 'nameserver':
                    out.append(bits[1])
    except OSError:
        pass
    return out or ['127.0.0.1']


def dns_ask(name, qtype):
    """One question to ACME's DNS servers (the mail's own DNS client):
    [(type, text)] of the answer - CNAME (5), TXT (16), A (1), AAAA (28), NS (2).
    [] for a name that is not there; OSError when no resolver answers."""
    return dns_ask_rc(name, qtype)[1]


def dns_ask_rc(name, qtype):
    """dns_ask, and whether the name is there at all: (rcode, records) - 3 is
    NXDOMAIN, which a CNAME to a name nobody serves ends in too."""
    last = None
    for srv in (acme_resolvers() or _os_resolvers())[:3]:
        try:
            data = _dns_ask(srv, str(name).rstrip('.'), qtype, 3.0)
        except OSError as e:
            last = e
            continue
        rcode, out = _dns_parse(data)
        if rcode in (0, 3):
            return rcode, out
        last = OSError(DNS_RCODES.get(rcode, 'rcode %d' % rcode))
    raise OSError('no DNS server answered (%s)' % (last or 'none'))


def _dns_parse(data):
    """(rcode, [(type, text)]) of one answer."""
    rcode, recs = _dns_records(data)
    if rcode:
        return rcode, []
    out = []
    for rtype, _n, at, size in recs:
        rd = data[at:at + size]
        if rtype == 5:
            out.append(('CNAME', _dns_name(data, at)[0].lower()))
        elif rtype == 16:
            j, parts = 0, []
            while j < len(rd):
                parts.append(rd[j + 1:j + 1 + rd[j]].decode('utf-8', 'replace'))
                j += 1 + rd[j]
            out.append(('TXT', ''.join(parts)))
        elif rtype == 1 and size == 4:
            out.append(('A', socket.inet_ntop(socket.AF_INET, rd)))
        elif rtype == 28 and size == 16:
            out.append(('AAAA', socket.inet_ntop(socket.AF_INET6, rd)))
        elif rtype == 2:
            out.append(('NS', _dns_name(data, at)[0].lower()))
    return 0, out


# Names looked up by ACME's DNS servers (1.0.172): in the threads of this page
# only - the CA, the DNS API, Try port 80 - every other lookup of the daemon
# as the machine's.
_ACME_DNS = threading.local()
_SYS_GETADDRINFO = socket.getaddrinfo


def _acme_proxy_host():
    """The names looked up as the machine looks names up (1.0.205, 1.0.206): the
    proxy's, the database's, the other node's - inside names ACME's public DNS
    servers do not know; a database connection made again in an order's thread
    asked them."""
    out = set()
    try:
        out.add((urllib.parse.urlsplit(str(CONFIG.get('proxy_url') or '')).hostname or '').lower())
    except ValueError:
        pass
    for k in ('db_host', 'ha_peer', 'ha_address'):
        out.add(str(CONFIG.get(k) or '').strip().strip('[]').lower())
    out.discard('')
    return out


def _acme_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if getattr(_ACME_DNS, 'on', False) and host and acme_resolvers() and \
            (host.decode() if isinstance(host, bytes) else str(host)).lower() not in _acme_proxy_host():
        h = host.decode() if isinstance(host, bytes) else str(host)
        try:
            ipaddress.ip_address(h.strip('[]'))
        except ValueError:
            if h not in ('localhost',):
                addrs = []
                for qtype, kind in ((1, 'A'), (28, 'AAAA')):
                    if family in (0, socket.AF_INET if kind == 'A' else socket.AF_INET6):
                        try:
                            addrs += [a for t, a in dns_ask(h, qtype) if t == kind]
                        except OSError:
                            pass
                if not addrs:
                    raise socket.gaierror(socket.EAI_NONAME, '%s is not known to %s' % (
                        h, ', '.join(acme_resolvers())))
                out = []
                for a in addrs:
                    out += _SYS_GETADDRINFO(a, port, family, type, proto,
                                            flags | socket.AI_NUMERICHOST)
                return out
    return _SYS_GETADDRINFO(host, port, family, type, proto, flags)


socket.getaddrinfo = _acme_getaddrinfo


class acme_dns_scope(object):
    """with acme_dns_scope(): names looked up by ACME's DNS servers."""
    def __enter__(self):
        self.was = getattr(_ACME_DNS, 'on', False)
        _ACME_DNS.on = True

    def __exit__(self, *a):
        _ACME_DNS.on = self.was


def acme_txt_seen(name, txt, say):
    """After the wait: whether ACME's DNS servers see the TXT record (through
    its CNAME) - asked again for up to two minutes; the CA asked either way."""
    rr = '_acme-challenge.' + name.rstrip('.')
    end = time.time() + float(os.environ.get('OTP_ACME_SEEN_WAIT') or 120)
    while True:
        try:
            got = [v for t, v in dns_ask(rr, 16) if t == 'TXT']
        except OSError as e:
            say('DNS could not be asked whether the record is there (%s): the CA is asked anyway'
                % str(e)[:80])
            return False
        if txt in got:
            say('%s TXT is seen by %s' % (rr, ', '.join(acme_resolvers()) or 'this machine\'s DNS'))
            return True
        if time.time() > end:
            say('%s TXT is not seen yet by %s - the CA is asked anyway' % (
                rr, ', '.join(acme_resolvers()) or 'this machine\'s DNS'))
            return False
        time.sleep(5)


def acme_dns_guide(store):
    """What each certificate asked for needs in your DNS, by how the CA
    checks it - for the card In your DNS."""
    rows = []
    http = (CONFIG.get('acme_challenge') or 'http-01') != 'dns-01'
    how = CONFIG.get('acme_dns') or 'manual'
    v = vip_conf(store)
    addr = {n['name']: n.get('address') for n in ha_nodes(store)}
    addr.setdefault(node_name(), node_address())
    for t in acme_wanted(store):
        name = acme_name_of(store, t)
        if not name:
            rows.append({'target': t, 'name': '', 'type': '', 'record': '', 'value': '',
                         'why': 'its name is not known yet'})
            continue
        if http:
            where = str(v.get('address') or '').split('/')[0] if t == 'vip' else addr.get(t) or ''
            rows.append({'target': t, 'name': name, 'type': 'A', 'record': name, 'value': where,
                         'why': 'the name points at an address that reaches port 80 of %s' % (
                             'the VIP address' if t == 'vip' else t), 'check': 'a'})
            continue
        rr, cname = acme_dns_where(name)
        if how == 'desec' and cname:
            dom = str(CONFIG.get('acme_desec_domain') or '').strip().rstrip('.').lower()
            if dom and not dom.endswith('.dedyn.io') and not any(
                    x.get('type') == 'NS' for x in rows):
                # A domain of your own at deSEC (1.0.174): the zone above it
                # must send the internet there - NS records, once.
                rows.append({'target': '', 'name': dom, 'type': 'NS', 'record': dom,
                             'value': 'ns1.desec.io. ns2.desec.org.',
                             'why': 'once, in the zone above it: %s at deSEC' % dom,
                             'check': 'ns'})
        own = '_acme-challenge.' + name
        if how == 'acmedns' or cname:
            rows.append({'target': t, 'name': name, 'type': 'CNAME', 'record': own,
                         'value': (cname or '?') + '.', 'why': 'once, by hand, in your DNS',
                         'check': 'cname'})
        elif how == 'manual':
            rows.append({'target': t, 'name': name, 'type': 'TXT', 'record': rr,
                         'value': 'shown here at every order', 'why': 'by hand, at every order'})
        else:
            rows.append({'target': t, 'name': name, 'type': 'TXT', 'record': rr, 'value': '',
                         'why': 'nothing to do: otp puts it in and takes it away'})
    return {'rows': rows, 'challenge': 'http-01' if http else 'dns-01', 'dns': how}


def acme_dns_check(store):
    """Each row of the guide looked up from this node, as the CA will."""
    g = acme_dns_guide(store)
    for r in g['rows']:
        if not r.get('check'):
            continue
        try:
            if r['check'] == 'cname':
                rc, recs = dns_ask_rc(r['record'], 5)
                got = [x[1] for x in recs if x[0] == 'CNAME']
                want = r['value'].rstrip('.').lower()
                r['found'] = got[0] + '.' if got else ''
                r['ok'] = bool(got) and got[0].rstrip('.') == want
                r['said'] = 'there' if r['ok'] else (
                    'it points elsewhere: %s' % r['found'] if got else 'not there yet')
            elif r['check'] == 'ns':
                rc, recs = dns_ask_rc(r['record'], 2)
                got = sorted(x[1] for x in recs if x[0] == 'NS')
                r['found'] = ' '.join(got)
                r['ok'] = any(x.rstrip('.').endswith(('desec.io', 'desec.org')) for x in got)
                r['said'] = 'there' if r['ok'] else (
                    ('it is served by %s, not deSEC' % r['found']) if got else
                    'not delegated: the internet does not know %s' % r['record'])
            else:
                with acme_dns_scope():
                    got = sorted({a[4][0] for a in socket.getaddrinfo(
                        r['record'], 80, proto=socket.IPPROTO_TCP)})
                r['found'] = ', '.join(got)
                r['ok'] = bool(got)
                r['said'] = 'it points at %s' % r['found'] if got else 'not there'
        except (OSError, socket.gaierror) as e:
            r.update(ok=False, said='could not be looked up: %s' % str(e)[:120])
    g['at'] = time.time()
    g['resolvers'] = acme_resolvers() or ['this machine\'s DNS']
    g['own_resolvers'] = bool(acme_resolvers())
    return g
