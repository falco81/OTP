

# ---------------------------------------------------------------------------
# The web side (1.0.47): TLS of each node and of the cluster's VIP address,
# and that address itself (VIP, active/standby, held by keepalived).
#
# Everything is kept in the database, so both nodes know all of it:
#   web:vip          the address, its name, the VRRP id, the node it is meant
#                    to be on, each node's interface
#   web:tls:NODE     a node's own certificate, chain, root and TLS settings
#   web:tls:vip      the same for the VIP address's own name
# Keys are sealed with the tokens' key. Each node then asks root for its own
# part of it (otp_web.py, through /var/lib/otp/web/request.json) and keeps
# /run/otp/vip-state up to date for keepalived: whether this node is healthy
# enough to hold the address - its own pages answering /healthz end to end
# (nginx, PHP, the daemon, the database), RADIUS listening, not in
# maintenance, not being upgraded or rebuilt - and whether it is the one the
# address is meant to be on.
# ---------------------------------------------------------------------------
WEB_DIR = STATE_DIR / 'web'
VIP_STATE = RUN_DIR / 'vip-state'
VIP_ROLE = RUN_DIR / 'vip-role'
WEB_HELPER = Path(__file__).parent / 'otp_web.py'
VIP_FAILS_BEFORE = 2
VIP_HEALTH_URL = os.environ.get('OTP_VIP_HEALTH_URL', 'https://127.0.0.1/healthz')                    # checks in a row before it is said unhealthy
TLS_PRESETS = {
    # The ciphers otp has always used: ECDHE only, AEAD only.
    'standard': {'protocols': ['TLSv1.2', 'TLSv1.3'], 'ciphers': (
        'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:'
        'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:'
        'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305')},
    # Mozilla's "intermediate": the same and the DHE ones (DH parameters).
    'intermediate': {'protocols': ['TLSv1.2', 'TLSv1.3'], 'ciphers': (
        'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:'
        'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:'
        'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:'
        'DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:DHE-RSA-CHACHA20-POLY1305')},
    # Mozilla's "modern": TLS 1.3 alone - its ciphers are not chosen.
    'modern': {'protocols': ['TLSv1.3'], 'ciphers': ''},
}
DH_WORDS = {'none': 'none (ECDHE only needs none)',
            'ffdhe2048': 'RFC 7919 ffdhe2048', 'ffdhe3072': 'RFC 7919 ffdhe3072',
            'ffdhe4096': 'RFC 7919 ffdhe4096', 'gen2048': 'made here, 2048 bits',
            'gen3072': 'made here, 3072 bits (a minute or so)',
            'gen4096': 'made here, 4096 bits (several minutes)'}
WEB_LOCK = threading.Lock()
VIP_HEALTH = {'ok': None, 'why': '', 'fails': 0, 'at': 0.0}


def _json_meta(store, k):
    try:
        got = json.loads(store.get_meta(k) or 'null')
        return got if isinstance(got, dict) else None
    except ValueError:
        return None


def vip_conf(store):
    return _json_meta(store, 'web:vip') or {'on': False}


def tls_profile(store, target):
    return _json_meta(store, 'web:tls:' + target)


def vip_auth():
    """The VRRP password: the same on every node, from the tokens' key."""
    key = sealing_key() or b''
    raw = hmac.new(key, b'otp-vip-vrrp', hashlib.sha256).digest()
    abc = string.ascii_letters + string.digits
    return ''.join(abc[b % len(abc)] for b in raw[:8])


VIP_MOVE_S = 60          # a move asked for by hand, in 'stays' mode, is wanted this long


def vip_moving(conf):
    """The node a move by hand is going to, while it is still under way."""
    to = str(conf.get('move_to') or '')
    if to and time.time() - float(conf.get('move_at') or 0) < VIP_MOVE_S:
        return to
    return ''


def vip_prefer_me(store, conf=None):
    """Is this node the one the address should be on - asked every 3 s.

    'back' (the default): the chosen node, always; the address goes back to it
    as soon as it is healthy. 'stays' (1.0.52): no preference - the node that
    holds it keeps it (keepalived's own state says which: MASTER), until it is
    unhealthy or gone, or until it is moved by hand."""
    conf = conf or vip_conf(store)
    me = node_name()
    if conf.get('mode') != 'stays':
        return vip_prefer(store, conf) == me
    moving = vip_moving(conf)
    if moving:
        return moving == me
    try:
        role = VIP_ROLE.read_text().split()[0]
    except (OSError, IndexError):
        role = ''
    return role == 'MASTER' or (role == '' and vip_here(conf.get('address')))


def vip_prefer(store, conf=None):
    conf = conf or vip_conf(store)
    if conf.get('mode') == 'stays':
        # Whoever holds it now (or is getting it).
        moving = vip_moving(conf)
        if moving:
            return moving
        for n in ha_nodes(store):
            w = web_state(store) if n['me'] else (n.get('web') or {})
            if w.get('vip_here'):
                return n['name']
        return ''
    want = str(conf.get('prefer') or '')
    if want:
        return want
    # Nobody chosen: the first node of the cluster by name - the same answer
    # on both nodes (1.0.59); "this one if it is slot 1" let both pick
    # themselves where the other's name sorted first.
    names = sorted(n['name'] for n in ha_nodes(store))
    return names[0] if names else node_name()


# ---- certificates: read, taken apart, made -----------------------------------
def _openssl(args, data=None, env=None, what='openssl'):
    e = dict(os.environ)
    e.update(env or {})
    got = subprocess.run(['openssl'] + args, input=data, capture_output=True, env=e,
                         timeout=120)
    if got.returncode != 0:
        said = (got.stderr or got.stdout or b'').decode('utf-8', 'replace').strip()
        raise ValueError('%s: %s' % (what, (said.splitlines() or ['openssl said no'])[-1][:200]))
    return got.stdout


PEM_CERT = re.compile(r'-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\s]+?-----END CERTIFICATE-----')
PEM_KEY = re.compile(r'-----BEGIN ((?:RSA |EC |ENCRYPTED )?PRIVATE KEY)-----[A-Za-z0-9+/=\s:,-]+?'
                     r'-----END \1-----')


def cert_info(pem):
    """What a certificate says of itself, for the pages."""
    out = _openssl(['x509', '-noout', '-subject', '-issuer', '-startdate', '-enddate',
                    '-fingerprint', '-sha256', '-ext', 'subjectAltName', '-nameopt',
                    'RFC2253'], pem.encode(), what='the certificate').decode()
    info = {'san': []}
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('subject='):
            info['subject'] = line[8:].strip()
        elif line.startswith('issuer='):
            info['issuer'] = line[7:].strip()
        elif line.startswith('notBefore='):
            info['not_before'] = _cert_time(line[10:])
        elif line.startswith('notAfter='):
            info['not_after'] = _cert_time(line[9:])
        elif 'Fingerprint=' in line:
            info['fingerprint'] = line.split('=', 1)[1].strip()
        elif 'Subject Alternative Name' in line and i + 1 < len(lines):
            info['san'] = [x.strip().split(':', 1)[-1] for x in lines[i + 1].split(',')
                           if x.strip()]
    info['self_signed'] = info.get('subject') == info.get('issuer')
    cn = re.search(r'(?:^|,)CN=([^,]+)', info.get('subject') or '')
    info['cn'] = cn.group(1) if cn else ''
    try:
        pub = _openssl(['x509', '-noout', '-pubkey'], pem.encode()).decode()
        txt = _openssl(['pkey', '-pubin', '-noout', '-text'], pub.encode()).decode()
        m = re.search(r'\((\d+) bit\)', txt)
        info['key'] = ('%s %s bit' % ('EC' if 'ASN1 OID' in txt or 'NIST' in txt else 'RSA',
                                      m.group(1))) if m else ''
    except ValueError:
        info['key'] = ''
    return info


def _cert_time(text):
    try:
        return datetime.strptime(text.strip().replace('  ', ' '),
                                 '%b %d %H:%M:%S %Y %Z').replace(
            tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _pub_of_cert(pem):
    return _openssl(['x509', '-noout', '-pubkey'], pem.encode(), what='the certificate')


def _pub_of_key(pem):
    return _openssl(['pkey', '-pubout'], pem.encode(), what='the key')


def key_plain(pem, password=''):
    """A private key without its passphrase, as PEM."""
    return _openssl(['pkey', '-passin', 'env:OTP_PW'], pem.encode(),
                    {'OTP_PW': password or ''},
                    what='the key (a wrong or missing password?)').decode()


def cert_bundle(cert='', key='', chain='', root='', pfx=b'', password='', pending_key=''):
    """Whatever was sent - one PEM with everything in it, separate parts, or
    a PFX / PKCS#12 with or without a password - as the parts nginx needs:
    the certificate, its key, the chain up from it, the root. The key is the
    certificate's own or nothing is taken."""
    certs, keys = [], []
    if pfx:
        got = None
        for extra in ([], ['-legacy']):
            try:
                got = _openssl(['pkcs12', '-nodes', '-passin', 'env:OTP_PW'] + extra, pfx,
                               {'OTP_PW': password or ''}, what='the PFX / PKCS#12 file')
                break
            except ValueError as e:
                last = e
        if got is None:
            raise ValueError('%s - is the password right?' % last)
        text = got.decode('utf-8', 'replace')
        certs += [m.group(0) for m in PEM_CERT.finditer(text)]
        keys += [m.group(0) for m in PEM_KEY.finditer(text)]
    for part in (cert, chain, root, key):
        part = str(part or '')
        certs += [m.group(0) for m in PEM_CERT.finditer(part)]
        keys += [m.group(0) for m in PEM_KEY.finditer(part)]
    if not certs:
        raise ValueError('no certificate was found in what was sent (PEM, or a PFX / PKCS#12 '
                         'file)')
    if len(keys) > 1:
        raise ValueError('more than one private key was sent')
    if keys:
        key_pem = key_plain(keys[0], password)
    elif pending_key:
        key_pem = pending_key
    else:
        raise ValueError('no private key came with it: send the key too (or the PFX), or make '
                         'the request here first so the key is waiting')
    want = _pub_of_key(key_pem)
    leaf = next((c for c in certs if _pub_of_cert(c) == want), None)
    if not leaf:
        raise ValueError('none of the certificates is the one of this key')
    others = [c for c in certs if c != leaf]
    infos = {c: cert_info(c) for c in others}
    roots = [c for c in others if infos[c]['self_signed']]
    roots += [m.group(0) for m in PEM_CERT.finditer(str(root or '')) if m.group(0) not in roots]
    inter = [c for c in others if c not in roots]
    # The chain in order: each the issuer of the one before it.
    chain_out, at = [], cert_info(leaf)
    while inter:
        nxt = next((c for c in inter if infos[c].get('subject') == at.get('issuer')), None)
        if not nxt:
            chain_out += inter
            break
        chain_out.append(nxt)
        inter.remove(nxt)
        at = infos[nxt]
    info = cert_info(leaf)
    verify = ''
    if roots:
        with tempfile.TemporaryDirectory(prefix='otp-cert-') as t:
            def put(name, text):
                p = os.path.join(t, name)
                with open(p, 'w') as f:
                    f.write(text)
                return p
            args = ['verify', '-CAfile', put('root.pem', '\n'.join(roots) + '\n')]
            if chain_out:
                args += ['-untrusted', put('chain.pem', '\n'.join(chain_out) + '\n')]
            args.append(put('leaf.pem', leaf + '\n'))
            try:
                _openssl(args, what='the chain')
                verify = 'ok'
            except ValueError as e:
                verify = str(e)
    return {'cert': leaf + '\n', 'chain': ''.join(c + '\n' for c in chain_out),
            'root': ''.join(c + '\n' for c in roots), 'key': key_pem, 'info': info,
            'chain_info': [cert_info(c) for c in chain_out],
            'root_info': [cert_info(c) for c in roots], 'verify': verify}


def _san_ext(names):
    out = []
    for n in names:
        n = str(n).strip()
        if not n:
            continue
        try:
            plain_ip(n, 'address')
            out.append('IP:' + n)
        except ValueError:
            if not re.match(r'^(\*\.)?[A-Za-z0-9.-]{1,253}\Z', n):
                raise ValueError('%r is not a name or an address' % n)
            out.append('DNS:' + n)
    return ','.join(out)


def _subject(cn, org='', unit='', country='', city=''):
    def esc(v):
        return re.sub(r'([/\\=+,])', r'\\\1', str(v).strip())
    if not cn or not re.match(r'^[A-Za-z0-9*.-]{1,64}\Z', cn):
        raise ValueError('the common name is a host name')
    s = '/CN=' + esc(cn)
    if org:
        s += '/O=' + esc(org)
    if unit:
        s += '/OU=' + esc(unit)
    if city:
        s += '/L=' + esc(city)
    if country:
        if not re.match(r'^[A-Za-z]{2}\Z', country):
            raise ValueError('the country is two letters (CZ)')
        s += '/C=' + country.upper()
    return s


def new_key(kind):
    if kind == 'ec':
        return _openssl(['genpkey', '-algorithm', 'EC', '-pkeyopt',
                         'ec_paramgen_curve:P-256']).decode()
    bits = {'rsa2048': 2048, 'rsa3072': 3072, 'rsa4096': 4096}.get(kind)
    if not bits:
        raise ValueError('the key is ec, rsa2048, rsa3072 or rsa4096')
    return _openssl(['genpkey', '-algorithm', 'RSA', '-pkeyopt',
                     'rsa_keygen_bits:%d' % bits]).decode()


def make_csr(cn, names, kind='rsa2048', **subject):
    key = new_key(kind)
    with tempfile.TemporaryDirectory(prefix='otp-csr-') as t:
        kf = os.path.join(t, 'k.pem')
        with open(kf, 'w') as f:
            f.write(key)
        csr = _openssl(['req', '-new', '-key', kf, '-subj', _subject(cn, **subject),
                        '-addext', 'subjectAltName=' + _san_ext([cn] + list(names))],
                       what='the request').decode()
    return key, csr


def make_selfsigned(cn, names, days=825, kind='rsa2048', **subject):
    key = new_key(kind)
    with tempfile.TemporaryDirectory(prefix='otp-crt-') as t:
        kf = os.path.join(t, 'k.pem')
        with open(kf, 'w') as f:
            f.write(key)
        crt = _openssl(['req', '-new', '-x509', '-key', kf, '-days', str(int(days)), '-subj',
                        _subject(cn, **subject), '-addext',
                        'subjectAltName=' + _san_ext([cn] + list(names))],
                       what='the certificate').decode()
    return key, crt


# ---- the TLS of a target, kept ---------------------------------------------------------
def tls_targets(store):
    names = sorted(set([node_name()] + [n['name'] for n in ha_nodes(store)]))
    return names + ['vip']


def tls_save(store, target, prof, by):
    prof = dict(prof)
    prof['at'] = time.time()
    prof['by'] = by
    store.set_meta('web:tls:' + target, json.dumps(prof))


def tls_view(prof):
    """A profile as the pages may see it: no key."""
    if not prof:
        return None
    out = {k: v for k, v in prof.items() if k not in ('key', 'pending_key')}
    out['has_key'] = bool(prof.get('key'))
    out['pending'] = bool(prof.get('pending_key'))
    return out


def tls_policy_checked(b):
    preset = str(b.get('preset') or 'standard')
    if preset not in list(TLS_PRESETS) + ['custom']:
        raise ValueError('the TLS settings are standard, intermediate, modern or custom')
    out = {'preset': preset}
    if preset == 'custom':
        prot = b.get('protocols') or []
        if not isinstance(prot, list) or not prot or \
                any(p not in ('TLSv1.2', 'TLSv1.3') for p in prot):
            raise ValueError('the protocols are TLSv1.2 and/or TLSv1.3')
        out['protocols'] = [p for p in ('TLSv1.2', 'TLSv1.3') if p in prot]
        ciphers = str(b.get('ciphers') or '').strip()
        if ciphers:
            if not re.match(r'^[A-Za-z0-9_+!@=:.-]{1,2000}\Z', ciphers):
                raise ValueError('the ciphers are an OpenSSL cipher list')
            _openssl(['ciphers', ciphers], what='OpenSSL does not know that cipher list')
        out['ciphers'] = ciphers
    dh = str(b.get('dh') or 'none')
    if dh not in DH_WORDS:
        raise ValueError('the DH parameters are one of %s' % ', '.join(DH_WORDS))
    out['dh'] = dh
    out['prefer'] = bool(b.get('prefer'))
    try:
        # Not said is the two years nginx is shipped with (1.0.94), not none:
        # the first TLS change on the pages dropped HSTS without a word.
        hv = b.get('hsts')
        out['hsts'] = max(0, min(63072000, int(hv) if hv not in (None, '') else 63072000))
    except (TypeError, ValueError):
        raise ValueError('HSTS is a number of seconds')
    hisec_tls(out)                          # 1.0.168
    return out


def tls_resolved(prof):
    """What root is handed for a profile: the parts and the lines."""
    if not prof:
        return None
    preset = prof.get('preset') or 'standard'
    p = TLS_PRESETS.get(preset) or {'protocols': prof.get('protocols') or ['TLSv1.2', 'TLSv1.3'],
                                    'ciphers': prof.get('ciphers') or ''}
    out = {'protocols': p['protocols'], 'ciphers': p['ciphers'], 'prefer': bool(prof.get('prefer')),
           'dh': prof.get('dh') or 'none',
           'hsts': int(prof['hsts']) if prof.get('hsts') not in (None, '') else 63072000}
    if prof.get('cert') and prof.get('key'):
        out.update(cert=prof['cert'], chain=prof.get('chain') or '', root=prof.get('root') or '',
                   key=unseal_secret(prof['key'], 'web:tls'))
    return out


# ---- what this node asks of root, and how it went -------------------------------------
def web_desired(store):
    me = node_name()
    v = vip_conf(store)
    vip = {'on': False}
    many = bool(CONFIG.get('ha_mode'))
    if v.get('on') and many:
        vip = {'on': True, 'address': v.get('address'), 'fqdn': v.get('fqdn') or '',
               'address6': v.get('address6') or '',
               'vrid': int(v.get('vrid') or 51), 'auth': vip_auth(),
               'own': CONFIG.get('ha_address') or node_address(),
               'peer': CONFIG.get('ha_peer') or '',
               'iface': (v.get('ifaces') or {}).get(me, '')}
    tls = {'node': tls_resolved(tls_profile(store, me)),
           'vip': tls_resolved(tls_profile(store, 'vip')) if vip['on'] else None}
    out = {'node': me, 'vip': vip, 'tls': tls}
    # Asked only once set on the pages (1.0.52): a request from before had
    # neither, and its hash stays what it was.
    fw, access = fw_desired(store), access_desired(store)
    if fw is not None:
        out['fw'] = fw
    if access is not None:
        out['access'] = access
    # ACME (1.0.169): port 80 answers the CA for the names ordered - the web
    # address's on every node, wherever it is now.
    if CONFIG.get('acme'):
        out['acme'] = acme_http_names(store)
    return out


def web_hash(desired):
    return hashlib.sha256(json.dumps(desired, sort_keys=True).encode()).hexdigest()


def web_status():
    try:
        fd = os.open(str(WEB_DIR / 'status.json'), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            got = json.loads(f.read(1 << 20).decode('utf-8'))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def web_tick(store):
    """Asks root for this node's part when what is wanted has changed."""
    if HA_REBUILDING.is_set() or not WEB_DIR.is_dir():
        return
    desired = web_desired(store)
    # Nothing ever asked and nothing to ask: no request at all.
    st = web_status()
    if not st and not desired['vip']['on'] and not desired['tls']['node'] and \
            'fw' not in desired and 'access' not in desired and 'acme' not in desired:
        return
    h = web_hash(desired)
    if st.get('hash') == h:
        if st.get('state') == 'done':
            # Done, by root's last word - and nginx really has it (1.0.104):
            # a machine put back from its own backup, nginx set up again or
            # a file changed by hand is given what the database says again.
            drift = web_drift(desired)
            if not drift or time.time() - WEB_DRIFT['at'] < 1800:
                return
            WEB_DRIFT['at'] = time.time()
            log('the web certificate in place is not the one wanted (%s): asked again' % drift,
                'warn')
            store.add_event('settings', 'the certificate nginx has on %s is not the one saved '
                            '(%s): put in again' % (node_name(), drift), 'warn')
        # Failed with exactly this: asked again only when somebody says so.
        # Or once after a restart (1.0.120): it may have failed on what the
        # machine did not have yet - its new address, say.
        if float(store.get_meta('web:retry:' + node_name()) or 0) <= float(st.get('at') or 0):
            if st.get('state') != 'failed' or WEB_DRIFT.get('boot_retried') or \
                    boot_time() <= float(st.get('at') or 0):
                return
            WEB_DRIFT['boot_retried'] = True
            log('the web part failed before this restart (%s): asked again' % '; '.join(
                st.get('said') or [])[:200], 'warn')
    # Root at work on it (1.0.59): while it holds request.taken the status
    # still has the old hash, and the same request was written again - every
    # change applied twice.
    taken = WEB_DIR / 'request.taken'
    if (taken.exists() and time.time() - taken.stat().st_mtime < 600) or (
            WEB_ASKED.get('hash') == h and time.time() - float(WEB_ASKED.get('at') or 0) < 600
            and float(st.get('at') or 0) < float(WEB_ASKED.get('at') or 0)):
        return
    req = WEB_DIR / 'request.json'
    if req.exists() and time.time() - req.stat().st_mtime < 600:
        # Waiting for root: left as it is when it asks for this very thing,
        # replaced when what is wanted changed meanwhile.
        try:
            if json.loads(req.read_text()).get('hash') == h:
                return
        except (OSError, ValueError):
            return
    body = dict(desired, id=secrets.token_hex(8), hash=h)
    tmp = WEB_DIR / 'request.part'
    try:
        tmp.unlink()
    except OSError:
        pass
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(body, f)
    os.replace(str(tmp), str(req))
    WEB_ASKED['hash'] = h
    WEB_ASKED['at'] = time.time()


WEB_ASKED = {'hash': '', 'at': 0.0}
WEB_DRIFT = {'at': 0.0}
NGINX_CERT_FILES = {'node': '/etc/nginx/certs/otp.pem', 'vip': '/etc/nginx/certs/otp-vip.pem'}


def _first_pem(text):
    m = PEM_CERT.search(text or '')
    return re.sub(r'\s+', '', m.group(0)) if m else ''


def web_drift(desired):
    """Why the certificates nginx has are not the ones wanted - '' when they
    are, or when that cannot be told (a file not readable here)."""
    for target in ('node', 'vip'):
        t = (desired.get('tls') or {}).get(target)
        if not t or not t.get('cert'):
            continue
        path = NGINX_CERT_FILES[target]
        try:
            with open(path) as f:
                have = _first_pem(f.read(200000))
        except FileNotFoundError:
            return '%s is not there' % path
        except OSError:
            continue
        if have and have != _first_pem(t['cert']):
            return '%s holds another certificate' % path
    return ''


def web_progress():
    """What root is doing now, if anything (1.0.50)."""
    try:
        fd = os.open(str(WEB_DIR / 'progress.json'), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            got = json.loads(f.read(65536).decode('utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(got, dict) or time.time() - float(got.get('at') or 0) > 3 * 3600:
        return None
    got['now'] = time.time()
    return got


def web_state(store):
    """This node's web side, for its heartbeat: what root said last, whether
    that is what is wanted now, and the address."""
    st = web_status()
    desired_hash = ''
    try:
        desired_hash = web_hash(web_desired(store))
    except Exception:                                   # noqa: BLE001
        pass
    role = ''
    try:
        role = VIP_ROLE.read_text().split()[0]
    except (OSError, IndexError):
        pass
    v = vip_conf(store)
    return {'cert_now': cert_now('/etc/nginx/certs/otp.pem'),
            'vip_cert_now': cert_now('/etc/nginx/certs/otp-vip.pem'),
            'state': st.get('state') or '', 'said': (st.get('said') or [])[-6:],
            'at': st.get('at'), 'current': bool(st) and st.get('hash') == desired_hash,
            'waiting': (WEB_DIR / 'request.json').exists(),
            'progress': web_progress(),
            'iface': (st.get('applied') or {}).get('iface') or '',
            'vip_here': vip_here(v.get('address')) if v.get('on') else False,
            'role': role, 'health': dict(VIP_HEALTH),
            'fw': dict(st.get('fw') or {}, **fw_now_read()), 'access': st.get('access') or {},
            'ifaces': sorted(os.listdir('/sys/class/net')) if os.path.isdir('/sys/class/net')
            else []}


def fw_now_read():
    """The whole firewall as root last read it (1.0.67): {'full': {4, 6},
    'full_at'}."""
    try:
        fd = os.open(str(WEB_DIR / 'fwnow.json'), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            got = json.loads(f.read(4 << 20).decode('utf-8'))
        full = got.get('full') or {}
        return {'full': {str(k): [str(x)[:400] for x in (v or [])][:1500] for k, v in full.items()},
                'full_at': got.get('at'), 'full_backend': got.get('backend')}
    except (OSError, ValueError, AttributeError):
        return {}


def fw_now_ask(wait=6.0):
    """Root asked to read the firewall again, and waited for (1.0.67)."""
    if not WEB_DIR.is_dir():
        return False
    t0 = time.time()
    try:
        (WEB_DIR / 'fw.ask').write_text(json.dumps({'at': t0}))
    except OSError:
        return False
    while time.time() - t0 < wait:
        if float(fw_now_read().get('full_at') or 0) >= t0:
            return True
        time.sleep(0.3)
    return False


CERT_NOW = {}


def cert_now(path):
    """What the certificate nginx has in `path` says - read again only
    when the file changes."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    had = CERT_NOW.get(path)
    if had and had[0] == (st.st_mtime, st.st_size):
        return had[1]
    try:
        with open(path) as f:
            text = f.read(200000)
        m = PEM_CERT.search(text)
        info = cert_info(m.group(0)) if m else None
        if info:
            info['chain'] = max(0, len(PEM_CERT.findall(text)) - 1)
    except (OSError, ValueError):
        return None             # not kept: read again next time (1.0.57)
    CERT_NOW[path] = ((st.st_mtime, st.st_size), info)
    return info


def local_addresses():
    """Every address on this machine's interfaces, read from the kernel.

    Not by binding to it (1.0.55): with net.ipv4.ip_nonlocal_bind on - which
    the VIP address turns on since 1.0.51, so nginx can listen on it - a bind
    succeeds for an address the machine does not hold, and both nodes said
    they had the VIP address."""
    out = set()
    try:
        # IPv4: the local table of the FIB, "/32 host LOCAL" under each address.
        last = None
        with open('/proc/net/fib_trie') as f:
            for line in f:
                m = re.match(r'^\s*\|--\s+([0-9.]+)\s*\Z', line)
                if m:
                    last = m.group(1)
                elif last and '/32 host LOCAL' in line:
                    out.add(last)
    except OSError:
        pass
    try:
        with open('/proc/net/if_inet6') as f:
            for line in f:
                h = line.split()[0]
                if len(h) == 32:
                    out.add(str(ipaddress.IPv6Address(int(h, 16))))     # ::1 too (1.0.59)
    except (OSError, ValueError, IndexError):
        pass
    if not out and shutil.which('ip'):
        got = subprocess.run(['ip', '-o', 'addr', 'show'], capture_output=True, text=True)
        for m in re.finditer(r'\binet6?\s+([0-9a-fA-F:.]+)/', got.stdout or ''):
            out.add(str(ipaddress.ip_address(m.group(1))))
    return out


def vip_here(address):
    """Does this machine hold the address now? Its interfaces say so."""
    try:
        ip = ipaddress.ip_interface(str(address or '')).ip
    except ValueError:
        return False
    return str(ip) in local_addresses()


# ---- may this node hold the address? ---------------------------------------------------
def vip_health_check(daemon):
    """One look at everything the pages need, from outside the daemon: its
    own /healthz through nginx and PHP to the daemon and the database - and
    RADIUS listening, and no maintenance, upgrade or rebuild. A node that is
    not healthy lets the address go to the other."""
    store = daemon.store
    why = ''
    if HA_REBUILDING.is_set():
        why = 'being rebuilt from the other node'
    elif maintenance_now(store).get('on'):
        why = 'in maintenance'
    elif not getattr(getattr(daemon, 'radius', None), 'bound', None):
        why = 'RADIUS is not listening'
    elif VIP_HEALTH_URL == 'none':
        pass                            # a test bed whose nginx is another node's
    else:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(VIP_HEALTH_URL,
                                         headers={'User-Agent': 'otp-vip-check'})
            with urllib.request.urlopen(req, timeout=4, context=ctx) as r:
                body = r.read(200).decode('utf-8', 'replace')
                if r.status != 200 or not body.startswith('ok'):
                    why = 'its pages say: %s' % body.strip()[:80]
        except urllib.error.HTTPError as e:
            try:
                why = 'its pages say %d: %s' % (e.code, e.read(200).decode('utf-8',
                                                                           'replace').strip()[:80])
            except Exception:                           # noqa: BLE001
                why = 'its pages say %d' % e.code
        except Exception as e:                          # noqa: BLE001
            why = 'its pages do not answer (%s)' % str(e)[:80]
    return why


def vip_watch(daemon):
    """Every three seconds: /run/otp/vip-state for keepalived."""
    while not daemon.stop_flag.wait(3):
        try:
            store = daemon.store
            v = vip_conf(store)
            if not v.get('on') or not CONFIG.get('ha_mode'):
                VIP_HEALTH['here'] = False
                try:
                    VIP_STATE.unlink()
                except OSError:
                    pass
                continue
            why = vip_health_check(daemon)
            if why:
                VIP_HEALTH['fails'] += 1
            else:
                VIP_HEALTH['fails'] = 0
            # Maintenance asked for (1.0.186): said at once, not after two looks -
            # RADIUS of this node stops answering, and the VIP address went
            # silent for seconds before keepalived moved it. Meanwhile, while the
            # address is still here, RADIUS goes on answering (handle()).
            planned = maintenance_now(store).get('on')
            if planned:
                VIP_HEALTH['fails'] = max(VIP_HEALTH['fails'], VIP_FAILS_BEFORE)
                VIP_HEALTH.setdefault('drain_since', time.time())
                why = why or 'in maintenance'
            else:
                VIP_HEALTH.pop('drain_since', None)
            VIP_HEALTH['here'] = vip_here(v.get('address'))
            ok = VIP_HEALTH['fails'] < VIP_FAILS_BEFORE
            if not why or not ok or VIP_HEALTH['ok'] is None:
                VIP_HEALTH.update(ok=ok, why=why if not ok else '')
            VIP_HEALTH['at'] = time.time()
            prefer = vip_prefer_me(store, v)
            line = ('ok prefer' if prefer else 'ok') if ok else 'fail ' + (why or '?')
            tmp = RUN_DIR / '.vip-state'
            tmp.write_text(line + '\n')
            os.chmod(str(tmp), 0o640)
            os.replace(str(tmp), str(VIP_STATE))
        except Exception as e:                          # noqa: BLE001
            log_sparing('vip-watch:' + str(e)[:80], 'the VIP address: %s' % e, 'warn', 600)
            daemon.stop_flag.wait(10)


# ---- what the pages and the command line change ----------------------------------------
def vip_checked(b, store):
    try:
        net = plain_ip(b.get('address'), 'interface')
    except ValueError:
        raise ValueError('the VIP address is an address with its prefix, e.g. 192.0.2.10/24')
    if '/' not in str(b.get('address') or ''):
        raise ValueError('give the prefix with the address, e.g. 192.0.2.10/24')
    if net.ip.is_loopback or net.ip.is_multicast or net.ip.is_unspecified:
        raise ValueError('%s cannot be the VIP address' % net.ip)
    nodes = [n for n in ha_nodes(store)]
    for n in nodes:
        if str(n.get('address') or '') == str(net.ip):
            raise ValueError('%s is the address of %s: the VIP address is a third one'
                             % (net.ip, n['name']))
    fqdn = str(b.get('fqdn') or '').strip().lower().rstrip('.')
    if fqdn and not re.match(r'^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
                             r'(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$', fqdn):
        raise ValueError('%r is not a host name' % fqdn)
    try:
        vrid = int(b.get('vrid') or 51)
    except (TypeError, ValueError):
        raise ValueError('the VRRP id is a number')
    if not 1 <= vrid <= 255:
        raise ValueError('the VRRP id is 1 to 255 - one no other VRRP on that network uses')
    ifaces = {}
    for k, val in (b.get('ifaces') or {}).items():
        val = str(val or '').strip()
        if val and not re.match(r'^[A-Za-z0-9_.:-]{1,15}\Z', val):
            raise ValueError('%r is not the name of a network interface' % val)
        if val:
            ifaces[str(k)] = val
    a6 = str(b.get('address6') or '').strip()
    if a6:
        if '/' not in a6:
            raise ValueError('give the prefix with the IPv6 VIP address, e.g. 2001:db8::10/64')
        try:
            n6 = plain_ip(a6, 'interface')
        except ValueError:
            raise ValueError('the IPv6 VIP address is an address with its prefix, e.g. '
                             '2001:db8::10/64')
        if n6.version != 6 or n6.ip.is_link_local or n6.ip.is_loopback:
            raise ValueError('the IPv6 VIP address is a global IPv6 address')
        a6 = str(n6)
    return {'address': str(net), 'fqdn': fqdn, 'vrid': vrid, 'ifaces': ifaces, 'address6': a6}


def vip_set(store, by, **changes):
    v = vip_conf(store)
    v.update(changes)
    v['at'] = time.time()
    v['by'] = by
    store.set_meta('web:vip', json.dumps(v))
    return v


# ---- a node renamed (1.0.48) ---------------------------------------------------------
NODE_NAME_FILE = STATE_DIR / 'node-name'


def node_carry(store, old, new, by='the daemon'):
    """What belongs to a node by its name, carried to its new name: its own
    settings (key@node), its maintenance, its TLS, its place as the web
    address's preferred node and its interface - and the old name off the
    list of nodes. Nothing the new name has already is overwritten."""
    if not old or old == new:
        return []
    said = []
    for r in store.db.rows('SELECT k, v FROM settings'):
        k = str(r['k'])
        if k.endswith('@' + old):
            want = k[:-len(old)] + new
            if store.db.value('SELECT 1 FROM settings WHERE k = ?', (want,)) is None:
                store.db.run('UPDATE settings SET k = ? WHERE k = ?', (want, k))
                said.append('its own setting %s' % k.split('@')[0])
            else:
                store.db.run('DELETE FROM settings WHERE k = ?', (k,))
    old_maint = _json_meta(store, 'maint:' + old)
    if old_maint and old_maint.get('on') and not (maintenance_row(store, new) or {}).get('on'):
        maintenance_set(store, True, old_maint.get('why') or 'carried over from %s' % old,
                        old_maint.get('by') or '', name=new)
        said.append('its maintenance')
    prof = store.get_meta('web:tls:' + old)
    if prof and store.get_meta('web:tls:' + new) is None:
        store.set_meta('web:tls:' + new, prof)
        said.append('its certificate and TLS settings')
    v = vip_conf(store)
    changed = False
    if v.get('prefer') == old:
        v['prefer'] = new
        changed = True
    ifaces = v.get('ifaces') or {}
    if old in ifaces and new not in ifaces:
        ifaces[new] = ifaces.pop(old)
        v['ifaces'] = ifaces
        changed = True
    if changed:
        store.set_meta('web:vip', json.dumps(v))
        said.append('its place in the VIP address')
    for k in ('node:', 'maint:', 'upgrade:node:', 'web:tls:', 'web:retry:', 'db_job:', 'fw:now:',
              'db_sizes:', 'hatls:node:'):
        store.db.run('DELETE FROM meta WHERE k = ?', (k + old,))
    store.add_event('settings', 'the node %s is called %s now; carried over: %s' % (
        old, new, ', '.join(said) or 'nothing (it had nothing of its own)'), 'warn', who=by)
    return said


def node_name_check(store):
    """At the start: was this node called something else last time?"""
    me = node_name()
    try:
        before = NODE_NAME_FILE.read_text().strip()
    except OSError:
        before = ''
    if before and before != me:
        # The new name is another machine's, answering now (1.0.110): carried
        # over, this node's own settings would land on that one - and with the
        # name put back, that one's on this one. Nothing is carried.
        try:
            taken = [n for n in ha_nodes(store) if n['name'] == me and n.get('alive') and
                     n.get('mid') and n['mid'] != machine_id()]
        except Exception:                               # noqa: BLE001
            taken = []
        if taken:
            log('this node was %s and is called %s now - but %s (%s) is %s and answering: '
                'nothing carried over; give this node its own name (otp --set node_name=%s, '
                'then systemctl restart otp)' % (before, me, taken[0].get('address') or '?',
                                                 taken[0].get('host') or '?', me, before), 'error')
            return
        try:
            said = node_carry(store, before, me)
            log('this node was %s and is %s now; carried over: %s'
                % (before, me, ', '.join(said) or 'nothing'), 'warn')
        except Exception as e:                          # noqa: BLE001
            log('carrying %s over to %s: %s' % (before, me, e), 'warn')
            return
    if before != me:
        try:
            NODE_NAME_FILE.write_text(me + '\n')
        except OSError:
            pass


# ---- the local firewall and who may reach which pages (1.0.52) -------------------------
# Kept for the whole cluster in meta, put in by each node's root helper with
# the rest of the web side (one request, one status). What otp's functions
# need is worked out here from what is set up; the rules somebody adds by
# hand come first, so a DROP or REJECT of theirs wins over what otp opens.
FW_AUTO_OPTIONAL = ('ssh', 'icmp', 'dhcpv6', 'web', 'radius', 'ntp')
ACCESS_WORDS = {'portal': 'the enrolment pages', 'admin': 'the administration pages',
                'health': 'the health check (/healthz)'}


def fw_conf(store):
    c = _json_meta(store, 'fw:conf') or {}
    c.setdefault('on', False)
    c.setdefault('off', [])
    c.setdefault('rules', [])
    return c


def access_conf(store):
    return _json_meta(store, 'web:access') or {}


def cluster_addresses(store, node):
    """The other nodes' addresses, seen from `node`: what must always get in."""
    me = node_name()
    out = set()
    for n in ha_nodes(store):
        if n['name'] != node and n.get('address'):
            out.add(n['address'])
    if CONFIG.get('ha_mode'):
        if node == me and CONFIG.get('ha_peer'):
            out.add(CONFIG['ha_peer'])
        if node != me:
            out.add(CONFIG.get('ha_address') or node_address())
    v = vip_conf(store)
    if v.get('on') and v.get('address'):
        out.add(str(v['address']).split('/')[0])
    good = set()
    for a in out:
        try:
            good.add(str(plain_ip(a, 'address')))
        except ValueError:
            # A host name (ha_peer may be one, 1.0.59): its addresses, not
            # left out of the rules and the lists.
            try:
                for info in socket.getaddrinfo(str(a), None, 0, socket.SOCK_STREAM)[:4]:
                    good.add(str(plain_ip(info[4][0], 'address')))
            except (OSError, ValueError, UnicodeError):
                pass
    return sorted(good)


def _fam(addr):
    try:
        return ipaddress.ip_network(addr, strict=False).version
    except ValueError:
        return 0


def access_desired(store, node=None):
    """The three lists as nginx gets them: what was set, the cluster added."""
    a = access_conf(store)
    if not a:
        return None
    inner = cluster_addresses(store, node or node_name())
    out = {}
    for k in ACCESS_WORDS:
        one = a.get(k) or {'any': True, 'from': []}
        nets = list(one.get('from') or [])
        if not one.get('any'):
            # The cluster first (1.0.59): a list cut at its length cut the
            # other node and the VIP address off, not one of somebody's.
            nets = list(inner) + [x for x in nets if x not in inner]
        out[k] = {'any': bool(one.get('any')), 'from': nets}
    return out


def fw_auto(store, node):
    """What otp's functions need on `node`: [{key, title, why, fixed, rules}]."""
    peers = cluster_addresses(store, node)
    v = vip_conf(store)
    out = [{'key': 'ssh', 'title': 'SSH', 'why': 'to manage the machine - turned off, '
            'take care to keep a rule of your own for it',
            # The port Settings - SSH server says, and while a change is on
            # trial the one before as well (1.0.163).
            'rules': [{'family': f, 'proto': 'tcp', 'port': str(p), 'source': ''}
                      for p in sshd_ports_open(store) for f in (4, 6)]},
           {'key': 'icmp', 'title': 'ICMP / ICMPv6', 'why': 'ping, and IPv6 cannot work without '
            'ICMPv6 (neighbour discovery)',
            'rules': [{'family': f, 'proto': 'icmp', 'port': '', 'source': ''} for f in (4, 6)]},
           {'key': 'dhcpv6', 'title': 'DHCPv6 client', 'why': 'answers of a DHCPv6 server, for '
            'an address given that way', 'rules': [{'family': 6, 'proto': 'udp', 'port': '546',
                                                     'source': 'fe80::/10'}]}]
    # The pages: from everybody when one of the three is for everybody, else
    # from the networks of the three lists (nginx then says who sees which).
    a = access_conf(store)
    srcs = ['']
    if a and not any((a.get(k) or {}).get('any') for k in ACCESS_WORDS):
        srcs = []
        for k in ACCESS_WORDS:
            for n in (a.get(k) or {}).get('from') or []:
                if n not in srcs:
                    srcs.append(n)
    web = []
    for s in srcs:
        for f in ((4, 6) if not s else (_fam(s),)):
            web.append({'family': f, 'proto': 'tcp', 'port': '80,443', 'source': s})
    out.append({'key': 'web', 'title': 'HTTP / HTTPS', 'why': 'the enrolment and '
                'administration pages and the health check; who sees which is under '
                '"Who may reach the pages"', 'rules': web})
    ports = str(int(CONFIG.get('radius_auth_port') or 1812))
    if int(CONFIG.get('radius_acct_port') or 0):
        ports += ',%d' % int(CONFIG.get('radius_acct_port'))
    rad = []
    for c in store.clients():
        if not c.get('enabled'):
            continue
        try:
            net = address_net(c['address'])
        except (ValueError, KeyError):
            continue
        if net is None:
            continue
        rad.append({'family': net.version, 'proto': 'udp', 'port': ports, 'source': str(net),
                    'note': 'RADIUS %s' % c.get('name', '')})
    out.append({'key': 'radius', 'title': 'RADIUS', 'why': 'from each RADIUS client set up '
                '(Clients), and only from them', 'rules': rad})
    # Time served to the networks set in Settings → Time (1.0.120).
    nc = _meta_json(store, 'ntp:conf') or {}
    if nc.get('manage') and nc.get('allow'):
        out.append({'key': 'ntp', 'title': 'NTP (time served)', 'why': 'this node serves the '
                    'time to the networks set under Settings → Time',
                    'rules': [{'family': _fam(a.split('/')[0]), 'proto': 'udp', 'port': '123',
                               'source': a} for a in nc['allow']]})
    # SNMPv3 (1.0.182): from the networks set, or from everywhere.
    if CONFIG.get('snmp'):
        nets = [w for w in re.split(r'[\s,;]+', str(CONFIG.get('snmp_from') or '')) if w]
        port = str(int(CONFIG.get('snmp_port') or 161))
        out.append({'key': 'snmp', 'title': 'SNMPv3', 'why': 'the monitoring asks each node '
                    '(Settings → Monitoring); from the networks set there only',
                    'rules': [{'family': _fam(n.split('/')[0]), 'proto': 'udp', 'port': port,
                               'source': n} for n in nets] or
                    [{'family': f, 'proto': 'udp', 'port': port, 'source': ''} for f in (4, 6)]})
    # Inside the cluster: always, never turned off.
    if CONFIG.get('ha_mode') and peers:
        nodes_only = [p for p in peers if p != str(v.get('address') or '').split('/')[0]]
        out.append({'key': 'cluster', 'title': 'The other node', 'fixed': True,
                    'why': 'replication (PostgreSQL), its pages and the health check - inside '
                    'the cluster everything has to work',
                    # Everything from it (1.0.59): its answers to this node's
                    # own asking came from other ports and were dropped.
                    'rules': [{'family': _fam(p), 'proto': 'any', 'port': '',
                               'source': p} for p in nodes_only]})
        if v.get('on'):
            out.append({'key': 'vrrp', 'title': 'VRRP (the VIP address)', 'fixed': True,
                        'why': 'keepalived of the other node says it is there',
                        'rules': [{'family': _fam(p), 'proto': 'vrrp', 'port': '', 'source': p}
                                  for p in nodes_only]})
    off = set(fw_conf(store).get('off') or [])
    for item in out:
        item['fixed'] = bool(item.get('fixed'))
        item['on'] = item['fixed'] or item['key'] not in off
        for r in item['rules']:
            r.setdefault('note', item['title'])
            r['action'] = 'accept'
    return out


def fw_rules_for(store, node):
    """Everything the chain of `node` holds, in order."""
    c = fw_conf(store)
    auto = fw_auto(store, node)
    # The cluster first (1.0.52): nothing of anybody's can shut the other
    # node out; then the rules of your own; then the rest otp needs.
    rules = [r for item in auto if item['fixed'] for r in item['rules']]
    for r in c.get('rules') or []:
        if r.get('scope', 'all') not in ('all', node) or r.get('disabled'):
            continue
        for f in ((4, 6) if not r.get('family') else (int(r['family']),)):
            if r.get('source') and _fam(r['source']) != f:
                continue
            rules.append({'family': f, 'proto': r.get('proto') or 'any',
                          'port': r.get('port') or '', 'source': r.get('source') or '',
                          'action': r.get('action') or 'accept', 'note': r.get('note') or 'manual'})
    for item in auto:
        if item['on'] and not item['fixed']:
            rules += item['rules']
    return rules


def fw_desired(store):
    c = fw_conf(store)
    if not c.get('set'):
        return None
    return {'on': bool(c.get('on')), 'rules': fw_rules_for(store, node_name()) if c.get('on')
            else []}


FW_PROTOS = ('tcp', 'udp', 'icmp', 'vrrp', 'any')


def fw_rule_checked(b, store):
    """A rule somebody adds by hand, as it is kept."""
    fam = int(b.get('family') or 0)
    if fam not in (0, 4, 6):
        raise ApiError(400, 'IPv4, IPv6 or both')
    proto = str(b.get('proto') or 'any')
    if proto not in FW_PROTOS:
        raise ApiError(400, 'the protocol is one of %s' % ', '.join(FW_PROTOS))
    port = str(b.get('port') or '').replace(' ', '')
    if port:
        if proto not in ('tcp', 'udp'):
            raise ApiError(400, 'a port is for TCP or UDP')
        for p in port.split(','):
            m = re.fullmatch(r'([0-9]{1,5})(?:-([0-9]{1,5}))?', p)    # ASCII only (1.0.61)
            if not m or not 1 <= int(m.group(1)) <= 65535 or \
                    (m.group(2) and not int(m.group(1)) <= int(m.group(2)) <= 65535):
                raise ApiError(400, '%s is not a port or a range (80, 1812-1813, 80,443)' % p)
        if sum(2 if '-' in p else 1 for p in port.split(',')) > 15:
            raise ApiError(400, 'fifteen ports at most in one rule (a range counts as two)')
    src = str(b.get('source') or '').strip()
    if src:
        try:
            net = plain_ip(src, 'network')
        except ValueError:
            raise ApiError(400, '%s is not an address or a network' % src[:60])
        if fam and net.version != fam:
            raise ApiError(400, '%s is not an IPv%d address' % (src, fam))
        src, fam = str(net), net.version
    action = str(b.get('action') or 'accept')
    if action not in ('accept', 'drop', 'reject'):
        raise ApiError(400, 'accept, drop or reject')
    scope = str(b.get('scope') or 'all')
    if scope != 'all' and scope not in {n['name'] for n in ha_nodes(store)} | {node_name()}:
        raise ApiError(400, 'there is no node called %s' % scope)
    note = re.sub(r'[^A-Za-z0-9 ._:/@()+,-]', '', str(b.get('note') or ''))[:80]
    return {'family': fam, 'proto': proto, 'port': port, 'source': src, 'action': action,
            'scope': scope, 'note': note, 'disabled': bool(b.get('disabled'))}


def fw_set(store, by, **changes):
    # On trial (1.0.137): what is there now kept, to come back unless kept.
    try:
        fw_trial_begin(store, by)
    except Exception as e:                              # noqa: BLE001
        log('the firewall change could not be put on trial: %s' % e, 'warn')
    c = fw_conf(store)
    c.update(changes)
    c.update(set=True, at=time.time(), by=by)
    store.set_meta('fw:conf', json.dumps(c))
    return c


def access_checked_api(b):
    out = {}
    for k, words in ACCESS_WORDS.items():
        one = b.get(k) or {}
        nets = []
        raw = one.get('from') or []
        if isinstance(raw, str):
            raw = re.split(r'[\s,;]+', raw)
        for x in raw[:200]:
            x = str(x).strip()
            if not x:
                continue
            try:
                n = str(plain_ip(x, 'network'))
            except ValueError:
                raise ApiError(400, '%s: %s is not an address or a network' % (words, x[:60]))
            if n not in nets:
                nets.append(n)
        if not one.get('any') and not nets:
            raise ApiError(400, '%s would be for nobody: give a network, or let everybody in'
                           % words)
        out[k] = {'any': bool(one.get('any')), 'from': nets}
    try:
        hisec_access(out)                   # 1.0.168
    except ValueError as e:
        raise ApiError(400, str(e))
    return out


# ---- what happened to the cluster, written down (1.0.52) -------------------------------
# Every five seconds this node looks at what it can see - the VIP address
# here or not, its own health, the other node, replication both ways - and
# writes an event (kind 'ha') whenever one of them changes. Settings -
# High availability - History shows them, with what was changed by hand.
HA_SEEN = {}
PGLOG_ASK = 'pglog.ask'
PGLOG_FILE = 'pglog.json'


def _ha_change(store, key, now, words, level='warn'):
    """An event when `key` was something else before; nothing the first time."""
    was = HA_SEEN.get(key, '__first__')
    HA_SEEN[key] = now
    if was == '__first__' or was == now:
        return False
    store.add_event('ha', words, level)
    return True


def ha_watch_tick(store):
    me = node_name()
    if not CONFIG.get('ha_mode'):
        return
    v = vip_conf(store)
    if v.get('on'):
        try:
            role = VIP_ROLE.read_text().split()[0]
        except (OSError, IndexError):
            role = ''
        held = vip_here(v.get('address')) if role else False
        why = VIP_HEALTH.get('why') or ''
        _ha_change(store, 'vip', 'here' if held else 'not',
                   ('the VIP address %s came to %s%s' % (v.get('address'), me,
                                                           ' (%s)' % role if role else '')) if held
                   else ('the VIP address %s left %s%s' % (
                       v.get('address'), me, ' - %s' % why if why else
                       (' (%s)' % role if role else ''))))
        ok = VIP_HEALTH.get('ok')
        if ok is not None:
            _ha_change(store, 'health', 'ok' if ok else 'bad',
                       ('%s is healthy again: the VIP address may come back to it' % me) if ok
                       else ('%s is not healthy - %s: the VIP address leaves it' % (me, why or '?')),
                       'info' if ok else 'bad')
    else:
        HA_SEEN.pop('vip', None)
        HA_SEEN.pop('health', None)
    for n in ha_nodes(store):
        if n['me']:
            continue
        _ha_change(store, 'node:' + n['name'], 'alive' if n.get('alive') else 'gone',
                   ('%s answers again (seen from %s)' % (n['name'], me)) if n.get('alive')
                   else ('%s stopped answering (seen from %s, last heard %d s ago)'
                         % (n['name'], me, int(n.get('age') or 0))),
                   'info' if n.get('alive') else 'bad')
        m = bool((n.get('maintenance')))
        _ha_change(store, 'maint:' + n['name'], 'on' if m else 'off',
                   '%s %s maintenance' % (n['name'], 'went into' if m else 'came out of'), 'info')
    if CONFIG.get('ha_mode') != 'replicated':
        return
    r = ha_repl_state(store)
    if r.get('trouble'):
        return
    for x in r.get('incoming') or []:
        name = x.get('name')
        state = 'running' if x.get('running') else ('paused' if not x.get('enabled') else 'stopped')
        _ha_change(store, 'in:' + name, state,
                   'replication coming in (%s): %s' % (name, {
                       'running': 'running again', 'paused': 'paused',
                       'stopped': 'stopped - the other node or its PostgreSQL is not reached, or '
                                  'an error stops it'}[state]),
                   {'running': 'info', 'paused': 'warn'}.get(state, 'bad'))
        errs = int(x.get('apply_errors') or 0) + int(x.get('sync_errors') or 0)
        was = HA_SEEN.get('err:' + name)
        HA_SEEN['err:' + name] = errs
        if was is not None and errs > was:
            store.add_event('ha', 'replication coming in (%s): %d new error(s), %d in all - '
                                  'Settings - High availability - the errors say what'
                                  % (name, errs - was, errs), 'bad')
    for x in r.get('outgoing') or []:
        _ha_change(store, 'out:' + x['name'], x.get('wal_status') or '',
                   'replication going out (%s): %s' % (x['name'], {
                       'lost': 'LOST - the other node waited too long and has to be rebuilt',
                       'unreserved': 'about to be lost - the other node is far behind',
                       'extended': 'the other node is behind', 'reserved': 'caught up'}.get(
                           x.get('wal_status'), x.get('wal_status') or '?')),
                   'bad' if x.get('wal_status') in ('lost', 'unreserved') else 'info')


def ha_history(store, limit=300, since=0, until=0):
    """The cluster's story: what this watch saw and what was done by hand."""
    span, args = '', []
    cleared = float(store.get_meta('ha:history_cleared') or 0)
    since = max(float(since or 0), cleared)
    if since:
        span += ' AND ts >= ?'
        args.append(float(since))
    if until:
        span += ' AND ts < ?'
        args.append(float(until))
    rows = store.db.rows(
        "SELECT ts, kind, node, level, who, words FROM events WHERE (kind = 'ha' OR "
        "(kind = 'settings' AND (words LIKE '%VIP address%' OR words LIKE '%replication%' OR "
        "words LIKE '%maintenance%' OR words LIKE '%rebuilt%' OR words LIKE '%cluster%' OR "
        "words LIKE '%upgrade%') AND words NOT LIKE '%certificate%' AND "
        "words NOT LIKE '%TLS%'))" + span +
        " ORDER BY ts DESC LIMIT " + str(int(limit)), args)
    for r in rows:
        w = (r.get('words') or '').lower()
        r['what'] = ('vip' if 'VIP address' in w else 'replication' if 'replication' in w
                     or 'rebuilt' in w else 'maintenance' if 'maintenance' in w or 'upgrade' in w
                     else 'node')
    return rows


# ---- replication's errors: counted since cleared, read from PostgreSQL's log -----------
def repl_errors(store, ask_log=True):
    """The errors of each subscription since they were last cleared, and what
    PostgreSQL's log says about them (root reads it: the log is postgres's)."""
    r = ha_repl_state(store)
    base = _json_meta(store, 'ha:errbase:' + node_name()) or {}
    subs = []
    for x in r.get('incoming') or []:
        b = base.get(x['name']) or {}
        subs.append({'name': x['name'], 'running': x.get('running'), 'enabled': x.get('enabled'),
                     'apply': int(x.get('apply_errors') or 0),
                     'sync': int(x.get('sync_errors') or 0),
                     'apply_new': max(0, int(x.get('apply_errors') or 0) - int(b.get('apply') or 0)),
                     'sync_new': max(0, int(x.get('sync_errors') or 0) - int(b.get('sync') or 0)),
                     'cleared': base.get('at'), 'cleared_by': base.get('by')})
    got = {}
    if ask_log and WEB_DIR.is_dir():
        ask = WEB_DIR / PGLOG_ASK
        t0 = time.time()
        try:
            ask.write_text(json.dumps({'at': t0, 'port': int(CONFIG.get('db_port') or 5432)}))
        except OSError:
            pass
        while time.time() - t0 < 8:
            got = _pglog_read()
            if float(got.get('at') or 0) >= t0:
                break
            time.sleep(0.4)
    else:
        got = _pglog_read()
    since = float(base.get('at') or 0)
    lines = [e for e in got.get('entries') or [] if float(e.get('ts') or 0) >= since or
             not e.get('ts')]
    return {'subs': subs, 'log': lines[-60:], 'log_at': got.get('at'),
            'log_file': got.get('file') or '', 'log_said': got.get('said') or '',
            'fresh': float(got.get('at') or 0) >= time.time() - 15}


def _pglog_read():
    try:
        fd = os.open(str(WEB_DIR / PGLOG_FILE), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as f:
            got = json.loads(f.read(1 << 20).decode('utf-8', 'replace'))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def repl_errors_clear(store, by):
    r = ha_repl_state(store)
    base = {'at': time.time(), 'by': by}
    for x in r.get('incoming') or []:
        base[x['name']] = {'apply': int(x.get('apply_errors') or 0),
                           'sync': int(x.get('sync_errors') or 0)}
    store.set_meta('ha:errbase:' + node_name(), json.dumps(base))
    return base
