

# ---- Signing in to these pages with a client certificate (a smart card, a YubiKey) (1.0.275) ----
# Off by default (admin_cert). A port of its own (admin_cert_port, 8443) where nginx asks the
# browser for a certificate of the authorities put in here - never on 443, so nobody else is ever
# asked for one (the enrolment pages, the administration's own sign-in). The browser shows the
# certificates it has from those authorities (the one on a YubiKey or a smart card: the system asks
# for its PIN), nginx hands it to the page, and this daemon checks it itself:
#   - the chain to an authority put in on the pages (openssl verify), its dates;
#   - a key usage for signing in: Client Authentication or Smart Card Logon;
#   - not revoked: the CRL at its CRL Distribution Point (fetched over http, kept until its
#     next update) - with admin_cert_crl on, no CRL means no sign-in;
#   - the person: the UPN in its Subject Alternative Name, looked up in the directory the
#     administrators sign in against (on, not locked, not expired; the role of its groups);
#   - admin_cert_map: 'compat' (default) - the SID the AD CS writes into a certificate since
#     KB5014754 (szOID_NTDS_CA_SECURITY_EXT) must be the account's own when it is there; 'strong' -
#     it must be there; 'upn' - not looked at.
# The second step, when it is on, is asked after it - always. A password is never taken here.
# The authorities are kept in the database (signed with the guard on) and written out by every
# node; nginx's server on the port is made by root from this node's HTTPS server and the VIP
# address's, with their certificates.
CERT_DIR = STATE_DIR / 'certlogin'
CERT_CA_FILE = CERT_DIR / 'ca.pem'
CERT_META = 'certlogin:ca'
CERT_MOST = 16384
CERT_CA_MOST = 20
CRL_MOST = 8 << 20
OID_SAN = '2.5.29.17'
OID_EKU = '2.5.29.37'
OID_CDP = '2.5.29.31'
OID_BC = '2.5.29.19'
OID_UPN = '1.3.6.1.4.1.311.20.2.3'
OID_SID_EXT = '1.3.6.1.4.1.311.25.2'
OID_SID = '1.3.6.1.4.1.311.25.2.1'
EKU_SIGN_IN = {'1.3.6.1.5.5.7.3.2': 'Client Authentication', '1.3.6.1.4.1.311.20.2.2': 'Smart Card Logon'}
CERT_NODE = {'said': None, 'at': 0.0, 'v': None, 'err': ''}
CRL_CACHE = {}
CRL_LOCK = threading.Lock()


class CertError(Exception):
    """A certificate not taken; the words say why."""


# -- reading a certificate (DER), only what is needed ---------------------------------------
def _der(b, i=0):
    if i + 2 > len(b):
        raise ValueError('cut short')
    tag = b[i]
    n = b[i + 1]
    i += 2
    if n & 0x80:
        k = n & 0x7f
        if not 0 < k <= 4 or i + k > len(b):
            raise ValueError('a length that cannot be')
        n = int.from_bytes(b[i:i + k], 'big')
        i += k
    if i + n > len(b):
        raise ValueError('cut short')
    return tag, b[i:i + n], i + n


def _der_all(b):
    out, i = [], 0
    while i < len(b):
        t, v, i = _der(b, i)
        out.append((t, v))
    return out


def _oid(v):
    if not v:
        return ''
    parts = [v[0] // 40, v[0] % 40] if v[0] < 80 else [2, v[0] - 80]
    n = 0
    for c in v[1:]:
        n = (n << 7) | (c & 0x7f)
        if not c & 0x80:
            parts.append(n)
            n = 0
    return '.'.join(str(x) for x in parts)


def _der_find(b, want, depth=0):
    """Every value of tag `want` anywhere in b (constructed tags walked into)."""
    out = []
    if depth > 12:
        return out
    try:
        items = _der_all(b)
    except ValueError:
        return out
    for t, v in items:
        if t == want:
            out.append(v)
        if t & 0x20:
            out += _der_find(v, want, depth + 1)
    return out


def cert_der(pem):
    m = re.search(r'-----BEGIN CERTIFICATE-----([A-Za-z0-9+/=\s]+)-----END CERTIFICATE-----', str(pem or ''))
    if not m:
        raise CertError('that is not a certificate (PEM)')
    try:
        return base64.b64decode(re.sub(r'\s+', '', m.group(1)), validate=True)
    except (ValueError, binascii.Error):
        raise CertError('the certificate is not whole')


def cert_facts(pem):
    """What the checks need of a certificate: its extensions read from DER, its names and dates
    from openssl."""
    der = cert_der(pem)
    try:
        t, cert, _ = _der(der)
        tbs_t, tbs, _ = _der(cert)
        items = _der_all(tbs)
    except ValueError as e:
        raise CertError('the certificate cannot be read: %s' % e)
    exts = {}
    for t, v in items:
        if t != 0xa3:
            continue
        try:
            for _t, one in _der_all(_der(v)[1]):
                parts = _der_all(one)
                oid = _oid(parts[0][1])
                crit = len(parts) == 3 and parts[1][0] == 0x01 and parts[1][1] == b'\xff'
                exts[oid] = (crit, parts[-1][1])
        except (ValueError, IndexError):
            raise CertError('the extensions of the certificate cannot be read')
    upns, mails, sid = [], [], ''
    if OID_SAN in exts:
        try:
            for gt, gv in _der_all(_der(exts[OID_SAN][1])[1]):
                if gt == 0xa0:                      # otherName
                    p = _der_all(gv)
                    if p and _oid(p[0][1]) == OID_UPN and len(p) > 1:
                        inner = _der_all(p[1][1])
                        if inner:
                            upns.append(inner[0][1].decode('utf-8', 'replace'))
                    elif p and _oid(p[0][1]) == OID_SID and len(p) > 1:
                        inner = _der_all(p[1][1])
                        if inner:
                            sid = sid or inner[0][1].decode('ascii', 'replace')
                elif gt == 0x81:                    # rfc822Name
                    mails.append(gv.decode('ascii', 'replace'))
        except (ValueError, IndexError):
            raise CertError('the Subject Alternative Name of the certificate cannot be read')
    if OID_SID_EXT in exts:
        try:
            for gt, gv in _der_all(_der(exts[OID_SID_EXT][1])[1]):
                p = _der_all(gv)
                if p and _oid(p[0][1]) == OID_SID and len(p) > 1:
                    inner = _der_all(p[1][1])
                    if inner:
                        sid = inner[0][1].decode('ascii', 'replace')
        except (ValueError, IndexError):
            raise CertError('the SID extension of the certificate cannot be read')
    eku = []
    if OID_EKU in exts:
        try:
            eku = [_oid(v) for t, v in _der_all(_der(exts[OID_EKU][1])[1]) if t == 0x06]
        except ValueError:
            raise CertError('the key usages of the certificate cannot be read')
    is_ca = False
    if OID_BC in exts:
        try:
            body = _der(exts[OID_BC][1])[1]
            p = _der_all(body)
            is_ca = bool(p and p[0][0] == 0x01 and p[0][1] == b'\xff')
        except ValueError:
            is_ca = False
    cdp = []
    if OID_CDP in exts:
        cdp = [u.decode('ascii', 'replace') for u in _der_find(exts[OID_CDP][1], 0x86)][:6]
    ocsp = []
    if OID_AIA in exts:
        # Authority Information Access -> OCSP (1.0.279): where its responder is.
        try:
            for _t, desc in _der_all(_der(exts[OID_AIA][1])[1]):
                parts = _der_all(desc)
                if parts and _oid(parts[0][1]) == OID_OCSP and len(parts) > 1 and parts[1][0] == 0x86:
                    ocsp.append(parts[1][1].decode('ascii', 'replace'))
        except (ValueError, IndexError):
            ocsp = []
        ocsp = ocsp[:4]
    freshest = []
    if OID_FRESHEST in exts:
        # Where its delta CRL is (1.0.278).
        freshest = [u.decode('ascii', 'replace') for u in _der_find(exts[OID_FRESHEST][1], 0x86)][:6]
    try:
        txt = _openssl(['x509', '-noout', '-subject', '-issuer', '-serial', '-startdate', '-enddate',
                        '-fingerprint', '-sha256', '-nameopt', 'RFC2253'], pem.encode(),
                       what='the certificate').decode('utf-8', 'replace')
    except ValueError as e:
        raise CertError(str(e)[:300])
    one = lambda k: (re.search(r'(?m)^%s=\s*(.*)$' % k, txt) or [None, ''])[1].strip()
    fp = (re.search(r'(?mi)^sha256 Fingerprint=([0-9A-F:]+)', txt) or [None, ''])[1]
    return {'subject': one('subject'), 'issuer': one('issuer'), 'serial': one('serial'),
            'not_before': one('notBefore'), 'not_after': one('notAfter'),
            'sha256': fp.replace(':', '').lower(), 'upn': upns, 'mail': mails, 'sid': sid,
            'eku': eku, 'ca': is_ca, 'cdp': cdp, 'freshest': freshest, 'ocsp': ocsp, 'unknown_critical': sorted(
                k for k, (c, _v) in exts.items() if c and k not in (OID_SAN, OID_EKU, OID_BC, '2.5.29.15',
                                                                     OID_CDP, '2.5.29.32', OID_FRESHEST, OID_AIA))}


def sid_text(raw):
    """S-1-5-21-... of a SID in its binary form (objectSid), or ''."""
    try:
        b = bytes(raw)
        if len(b) < 8 or b[0] != 1 or len(b) != 8 + 4 * b[1]:
            return ''
        auth = int.from_bytes(b[2:8], 'big')
        subs = [int.from_bytes(b[8 + 4 * i:12 + 4 * i], 'little') for i in range(b[1])]
        return 'S-%d-%d' % (b[0], auth) + ''.join('-%d' % s for s in subs)
    except (TypeError, ValueError):
        return ''


# -- the authorities ------------------------------------------------------------------------
def cert_split_pems(raw):
    """PEM certificates of an upload: PEM (one or a bundle), DER, or PKCS#7 (.p7b) in DER or PEM."""
    raw = bytes(raw or b'')
    if b'-----BEGIN' in raw:
        text = raw.decode('ascii', 'replace')
        if '-----BEGIN PKCS7-----' in text:
            text = _openssl(['pkcs7', '-print_certs'], raw, what='PKCS#7').decode('ascii', 'replace')
        return [m.group(0) for m in PEM_CERT.finditer(text)]
    for args in (['x509', '-inform', 'DER'], ['pkcs7', '-inform', 'DER', '-print_certs']):
        try:
            text = _openssl(args, raw, what='the authority').decode('ascii', 'replace')
        except ValueError:
            continue
        got = [m.group(0) for m in PEM_CERT.finditer(text)]
        if got:
            return got
    return []


def cert_cas(store):
    """[pem] of the authorities whose certificates sign people in."""
    got = json_obj(store.get_meta(CERT_META)) or {}
    return [p for p in (got.get('certs') or []) if isinstance(p, str) and 'BEGIN CERTIFICATE' in p]


def cert_ca_add(store, raw, by):
    if len(raw or b'') > 1 << 20:
        raise ValueError('that is more than certificates of authorities are')
    try:
        pems = cert_split_pems(raw)
    except ValueError as e:
        raise ValueError('not read: %s' % e)
    if not pems:
        raise ValueError('no certificate in it (PEM, DER or PKCS#7 .p7b)')
    have = cert_cas(store)
    seen = {cert_facts(p)['sha256'] for p in have}
    added = []
    for p in pems:
        f = cert_facts(p)
        if not f['ca']:
            raise ValueError('%s is not the certificate of an authority (no CA:TRUE) - put in the '
                             'authority that issues the people\'s certificates, and the one above it'
                             % (f['subject'] or '?'))
        if f['sha256'] in seen:
            continue
        seen.add(f['sha256'])
        have.append(p.strip() + '\n')
        added.append(f)
    if len(have) > CERT_CA_MOST:
        raise ValueError('%d authorities at most' % CERT_CA_MOST)
    if added:
        store.set_meta(CERT_META, json.dumps({'certs': have, 'at': time.time(), 'by': str(by or '')[:190]}))
        store.add_event('settings', '%s put in an authority for signing in with a certificate: %s' % (
            by, '; '.join(f['subject'] for f in added)[:600]), 'warn', who=by)
    return added


def cert_ca_drop(store, sha, by):
    have = cert_cas(store)
    keep = [p for p in have if cert_facts(p)['sha256'] != str(sha or '').lower()]
    if len(keep) == len(have):
        raise ValueError('there is no such authority')
    if keep:
        store.set_meta(CERT_META, json.dumps({'certs': keep, 'at': time.time(), 'by': str(by or '')[:190]}))
    else:
        store.drop_meta(CERT_META)
    store.add_event('settings', '%s took an authority of signing in with a certificate away' % by,
                    'warn', who=by)


def cert_listening(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', int(port))) == 0
    except (OSError, ValueError):
        return False
    finally:
        s.close()


def cert_port_ours(port):
    """Whether what listens on the port is otp's own certificate server (1.0.276): just switched
    off, root's helper may not have taken it away yet - switching on again is not refused over it."""
    try:
        with open(os.path.join(os.environ.get('OTP_VIP_NGINX_DIR', '/etc/nginx/conf.d'),
                               'otp_certlogin.conf')) as f:
            return re.search(r'(?m)^\s*listen\s+(\S*:)?%d\b' % int(port), f.read(4 << 20)) is not None
    except (OSError, ValueError):
        return False


def _setting_on(v):
    """A switch as save_settings keeps it (1.0.278): "1.0", " 1", 1.0 and True are on, as _coerce
    makes them - a test of the text alone let "1.0" past a check and saved it on."""
    if isinstance(v, bool):
        return v
    try:
        return int(float(str(v).strip() or 0)) != 0
    except (TypeError, ValueError):
        return str(v).strip().lower() in ('true', 'yes', 'on')


def cert_port_problem(checked, conf=None, probe=False, others=None):
    """Why a batch of settings cannot be saved over the certificate's own port (1.0.276), or '':
    with admin_cert on, its port is nobody else's - not 80 or 443, not the balancer's own port
    (web_proxy_port, whichever of the two is changed), not the API's, RADIUS's, the SSH gate's or a
    local database's, on this node or another of the cluster (others: {node: its own values}).
    probe: switched on or moved, the port is tried on 127.0.0.1 - something listening there
    already (not otp's nginx) refuses it. Off, the port is nothing and nothing is asked."""
    keys = ('admin_cert', 'admin_cert_port', 'web_proxy_port') + tuple(k for k, _ in WEB_PROXY_PORT_CLASHES)
    if not any(k in (checked or {}) for k in keys):
        return ''
    before = conf if conf is not None else CONFIG
    after = dict(before)
    after.update(checked or {})
    if not _setting_on(after.get('admin_cert')):
        return ''
    try:
        port = int(after.get('admin_cert_port') or 8443)
        lb = int(after.get('web_proxy_port') or 0)
    except (TypeError, ValueError):
        return ''
    other = '9443' if port == 8443 else '8443'
    clash = web_proxy_port_clash(port, after)
    if not clash and port in (80, 443):
        clash = 'the pages\' own port'
    if not clash and port == lb:
        clash = 'the balancer\'s own port (web_proxy_port)'
    if not clash:
        for n in sorted(others or {}):
            clash = web_proxy_port_clash(port, others[n], keys=NODE_KEYS)
            if clash:
                clash = '%s on %s' % (clash, n)
                break
    if clash:
        if port == lb and 'web_proxy_port' in (checked or {}) and 'admin_cert_port' not in (checked or {}):
            return ('web_proxy_port: %d is the certificate sign-in\'s own port (admin_cert_port) - '
                    'give the balancer another one (%s, say)' % (port, '9443' if port == 8443 else '8443'))
        return ('admin_cert_port: %d is %s - give the certificate sign-in a port of its own '
                '(%s, say)' % (port, clash, other))
    try:
        was_on = _setting_on(before.get('admin_cert'))
        was = int(before.get('admin_cert_port') or 8443)
    except (TypeError, ValueError):
        was_on, was = False, 0
    if probe and (not was_on or port != was) and cert_listening(port) and not cert_port_ours(port):
        return ('admin_cert_port: something on this node listens on %d already - give a free port '
                '(%s, say)' % (port, other))
    return ''


def cert_tick(store, now_too=False):
    """Each node: the authorities written out for the checks, and what this node can do said - with
    the facts of the CRLs it keeps (1.0.278), at once after Fetch now or Clear (now_too)."""
    v = store.get_meta(CERT_META)
    port = int(CONFIG.get('admin_cert_port') or 8443)
    lis = bool(CONFIG.get('admin_cert')) and cert_listening(port)
    crls = crls_now()
    ocsp = ocsp_now()
    if not now_too and v == CERT_NODE.get('v') and lis == CERT_NODE.get('lis') and \
            crls == CERT_NODE.get('crls') and ocsp == CERT_NODE.get('ocsp') and time.time() - CERT_NODE['at'] < 300:
        return
    CERT_NODE['crls'] = crls
    CERT_NODE['ocsp'] = ocsp
    CERT_NODE['v'] = v
    CERT_NODE['lis'] = lis
    err = ''
    pems = cert_cas(store)
    try:
        if pems:
            text = ''.join(p.strip() + '\n' for p in pems)
            have = CERT_CA_FILE.read_text() if CERT_CA_FILE.exists() else ''
            if have != text:
                CERT_DIR.mkdir(mode=0o700, exist_ok=True)
                tmp = CERT_DIR / ('.ca.%d' % os.getpid())
                tmp.write_text(text)
                os.chmod(str(tmp), 0o600)
                os.replace(str(tmp), str(CERT_CA_FILE))
        elif CERT_CA_FILE.exists():
            CERT_CA_FILE.unlink()
    except OSError as e:
        err = 'the authorities could not be written: %s' % e
    said = {'at': int(time.time()), 'cas': len(pems), 'file': CERT_CA_FILE.exists(),
            'listening': lis, 'port': port, 'crls': crls, 'ocsp': ocsp,
            'err': err, 'version': __version__}
    store.set_meta('certlogin:node:' + node_name(), json.dumps(said))
    CERT_NODE.update(said=said, at=time.time(), err=err)


# -- revocation (1.0.278: the crl-revocation-kit, as acme 1.0.104 has it) --------------------------
# The CRL of a person's certificate, its delta CRL (Freshest CRL), and those of every authority above
# it but the root; fetched only for a certificate whose chain is already good; over http only, from
# no loopback, link-local, metadata, multicast or reserved address whatever the name resolves to,
# connected to the address checked (never looked up again), no redirect, 8 MB and 15 s at most, and
# never through the proxy; a CRL seen within ten minutes (sooner at its next update), the last good
# one kept until its next update while its address does not answer, then nothing - no CRL, no
# sign-in. Each node fetches and keeps its own, and says only facts and dates of them.
OID_FRESHEST = '2.5.29.46'          # Freshest CRL: where the delta CRL is
OID_AIA = '1.3.6.1.5.5.7.1.1'       # Authority Information Access (1.0.279)
OID_OCSP = '1.3.6.1.5.5.7.48.1'     # ...its OCSP responder
OCSP_CACHE = {}
OCSP_LOCK = threading.Lock()
OCSP_MOST = 1 << 20
OCSP_MODES = ('off', 'first', 'only', 'both')
CRL_LDAP = {'fetch': None}          # reads a CDP object of the directory (1.0.279): set by the daemon
OID_DELTA = '2.5.29.27'             # Delta CRL Indicator (of a CRL)
CRL_FRESH_S = 600
CRL_FETCH_S = 15
CRL_SAID = 24
CDP_NAMES_NO = ('metadata', 'metadata.google.internal', 'metadata.goog', 'instance-data',
                'instance-data.ec2.internal', 'metadata.azure.com', 'metadata.oraclecloud.com')
CDP_IPS_NO = ('169.254.169.254', '169.254.170.2', 'fd00:ec2::254', '100.100.100.200')
CA_CDPS = {}
CERT_NOENV = {'SSL_CERT_DIR': '/nonexistent', 'SSL_CERT_FILE': '/nonexistent'}


class CrlRefused(CertError):
    """No CRL to be had (1.0.278): the certificate cannot be checked - nobody signs in by it."""


def cdp_addr_no(ip):
    """Why no CRL is fetched from an address ('' when one is): loopback, link-local (a cloud's
    metadata service), multicast, unspecified, reserved, a cloud's metadata address. AD CS's CDPs
    are mostly inside: private addresses (RFC 1918, fc00::/7) are fetched from."""
    if isinstance(ip, str):
        ip = ipaddress.ip_address(ip.split('%', 1)[0])
    if getattr(ip, 'ipv4_mapped', None):
        ip = ip.ipv4_mapped
    if any(ip == ipaddress.ip_address(x) for x in CDP_IPS_NO):
        return 'a cloud\'s metadata service'
    if ip.is_loopback:
        # The tests' CRL is served on this machine (never set by otp itself).
        return '' if os.environ.get('OTP_CDP_LOCAL') == '1' else 'loopback'
    if ip.is_link_local:
        return 'link-local'
    if ip.is_multicast:
        return 'multicast'
    if ip.is_unspecified or (ip.version == 4 and ip in ipaddress.ip_network('0.0.0.0/8')):
        return 'unspecified'
    if ip.is_reserved:
        return 'reserved'
    return ''


def cdp_ok(url):
    """An address a CRL is fetched from: http only, no user or password in it, no name of a cloud's
    metadata service, a number in it none of cdp_addr_no's. Its name's addresses are checked again
    when it is fetched (crl_http_get)."""
    try:
        u = urllib.parse.urlsplit(str(url or ''))
        u.port
    except ValueError:
        return False
    if u.scheme != 'http' or not u.hostname or u.username or u.password:
        return False
    host = u.hostname.lower().rstrip('.')
    if host in CDP_NAMES_NO or any(host.endswith('.' + n) for n in CDP_NAMES_NO if '.' in n):
        return False
    try:
        return not cdp_addr_no(ipaddress.ip_address(host.split('%', 1)[0]))
    except ValueError:
        return True


def crl_http_get(url, body=None, ctype='', most=None):
    """The body at a CRL's http address: every address of its name looked up by this machine's
    resolver and checked, the connection made to the address checked, never looked up again; no
    redirect followed, CRL_MOST at most, CRL_FETCH_S for the whole of it; never through the proxy
    (the CDPs of AD CS are inside). With a body, POSTed (an OCSP request, 1.0.279). ValueError says
    why not."""
    import http.client as _hc
    most = most or CRL_MOST
    if not cdp_ok(url):
        raise ValueError('not an address a CRL is fetched from (http; no loopback, link-local or '
                         'metadata address)')
    u = urllib.parse.urlsplit(url)
    host, port = u.hostname, u.port or 80
    deadline = time.monotonic() + CRL_FETCH_S
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as e:
        raise ValueError('%s cannot be looked up (%s)' % (host, e))
    addrs = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(str(info[4][0]).split('%', 1)[0])
        except ValueError:
            raise ValueError('%s has an address that cannot be read (%s)' % (host, info[4][0]))
        if ip not in addrs:
            addrs.append(ip)
    if not addrs:
        raise ValueError('%s has no address' % host)
    for ip in addrs:
        why = cdp_addr_no(ip)
        if why:
            raise ValueError('%s is %s (%s) - no CRL is fetched from it' % (host, ip, why))
    path = (u.path or '/') + ('?' + u.query if u.query else '')
    last = None
    for ip in addrs[:4]:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        conn = _hc.HTTPConnection(str(ip), port, timeout=min(5.0, left))
        try:
            heads = {'Host': ('[%s]' % host if ':' in host else host) + (':%d' % port if u.port else ''),
                     'User-Agent': 'otp/%s' % __version__, 'Accept': '*/*', 'Connection': 'close'}
            if body is not None:
                heads['Content-Type'] = ctype or 'application/octet-stream'
            conn.request('POST' if body is not None else 'GET', path, body=body, headers=heads)
            r = conn.getresponse()
            if 300 <= r.status < 400:
                raise ValueError('it answers with a redirect (HTTP %d to %s) - not followed'
                                 % (r.status, str(r.getheader('Location') or '?')[:120]))
            if r.status != 200:
                raise ValueError('HTTP %d' % r.status)
            try:
                if int(r.getheader('Content-Length') or 0) > most:
                    raise ValueError('larger than %d kB' % (most >> 10))
            except (TypeError, ValueError) as e:
                if 'larger' in str(e):
                    raise
            raw = b''
            while True:
                if time.monotonic() > deadline:
                    raise ValueError('it took longer than %d s' % CRL_FETCH_S)
                part = r.read1(65536)
                if not part:
                    break
                raw += part
                if len(raw) > most:
                    raise ValueError('larger than %d kB' % (most >> 10))
            return raw
        except (OSError, _hc.HTTPException) as e:
            last = e
        finally:
            conn.close()
    raise ValueError(('%s' % last)[:200] if last else 'it took longer than %d s' % CRL_FETCH_S)


def cdp_ldap(url):
    """(DN, attribute) of a CRL Distribution Point in the directory, as AD CS writes it
    (ldap:///CN=<CA>,CN=<server>,CN=CDP,CN=Public Key Services,CN=Services,CN=Configuration,DC=...
    ?certificateRevocationList?base?objectClass=cRLDistributionPoint) - or None (1.0.279). Only a
    CDP object of the configuration's Public Key Services and only its CRL attributes: the address
    is text in a certificate; the host in it is never used."""
    u = str(url or '')
    if not u.lower().startswith('ldap://'):
        return None
    rest = u[7:]
    if '/' not in rest:
        return None
    parts = rest.split('/', 1)[1].split('?')
    dn = urllib.parse.unquote(parts[0]).strip()
    attr = (parts[1] if len(parts) > 1 else '').strip() or 'certificateRevocationList'
    scope = (parts[2] if len(parts) > 2 else '').strip().lower()
    base_attr = attr.split(';', 1)[0].lower()
    if base_attr not in ('certificaterevocationlist', 'deltarevocationlist'):
        return None
    if scope not in ('', 'base') or not dn or len(dn) > 600 or '\x00' in dn:
        return None
    if not re.search(r'(?i),\s*CN=CDP\s*,\s*CN=Public Key Services\s*,\s*CN=Services\s*,\s*'
                     r'CN=Configuration\s*,\s*DC=', dn):
        return None
    return dn, ('certificateRevocationList' if base_attr == 'certificaterevocationlist'
                else 'deltaRevocationList')


def crl_where_ok(url):
    """An address a CRL is taken from: http by cdp_ok, or the directory's CDP object while reading
    CRLs from the directory is on."""
    if str(url or '').lower().startswith('ldap://'):
        return bool(CRL_LDAP['fetch']) and cdp_ldap(url) is not None
    return cdp_ok(url)


def crl_urls(named):
    """The addresses of a CRL tried in turn: up to three http ones, then the directory's (when on)."""
    named = list(named or [])
    http = [u for u in named if u.lower().startswith('http://') and cdp_ok(u)][:3]
    ldap = [u for u in named if u.lower().startswith('ldap://') and crl_where_ok(u)][:1]
    return http + ldap


def cert_ldap_hook(daemon):
    """The directory's own connection behind CRL_LDAP (1.0.279), while admin_cert_crl_ldap is on and a
    directory is set for administrators; None otherwise."""
    name = str(CONFIG.get('admin_directory') or '').lower()
    ad = (getattr(daemon, 'dirs', None) or {}).get(name) if name else None
    on = bool(_setting_on(CONFIG.get('admin_cert_crl_ldap')) and CONFIG.get('admin_cert_crl', 1) and ad)
    CRL_LDAP['fetch'] = (lambda url: cert_ldap_crl(ad, url)) if on else None
    return on


def cert_ldap_crl(ad, url):
    """A CRL from its CDP object in the directory (DER), read with the directory's connection."""
    got = cdp_ldap(url)
    if not got:
        raise ValueError('not a CDP object of the directory')
    dn, attr = got

    def do(link):
        return link.search(dn, ldap_equal('objectClass', 'cRLDistributionPoint'), (attr,), scope=0, limit=1)
    try:
        found = ad.asked(do)
    except LdapError as e:
        raise ValueError('the directory said: %s' % str(e)[:160])
    if not found:
        raise ValueError('no such CDP object in the directory')
    for k, v in (found[0].get('raw') or {}).items():
        if k.split(';', 1)[0].lower() == attr.lower() and v and v[0]:
            if len(v[0]) > CRL_MOST:
                raise ValueError('larger than %d MB' % (CRL_MOST >> 20))
            return bytes(v[0])
    raise ValueError('the CDP object holds no %s' % attr)


def _der_count(b):
    n, i = 0, 0
    while i < len(b):
        _t, _v, i = _der(b, i)
        n += 1
    return n


def _crl_time(words):
    try:
        return float(calendar.timegm(time.strptime(re.sub(r'\s+', ' ', str(words or '').strip())
                                                   .replace(' GMT', ''), '%b %d %H:%M:%S %Y')))
    except ValueError:
        return 0.0


def crl_info(pem):
    """Of a CRL (PEM): next update, the Freshest CRL it names, whether it is a delta CRL itself,
    its issuer, number, this update and how many certificates it lists as revoked."""
    out = {'next': None, 'freshest': [], 'delta': False, 'issuer': '', 'number': '',
           'this': None, 'revoked': None}
    m = re.search(r'-----BEGIN X509 CRL-----([A-Za-z0-9+/=\s]+)-----END X509 CRL-----', pem)
    try:
        der = base64.b64decode(re.sub(r'\s+', '', m.group(1))) if m else b''
        _t, body, _ = _der(der)
        _t, tbs, _ = _der(body)
        items = _der_all(tbs)
        times = [i for i, (t, _v) in enumerate(items) if t in (0x17, 0x18)]
        if times:
            after = times[-1] + 1
            out['revoked'] = _der_count(items[after][1]) \
                if after < len(items) and items[after][0] == 0x30 else 0
        for t, v in items:
            if t != 0xa0:
                continue
            for _t, one in _der_all(_der(v)[1]):
                parts = _der_all(one)
                oid = _oid(parts[0][1])
                if oid == OID_FRESHEST:
                    out['freshest'] = [u.decode('ascii', 'replace')
                                       for u in _der_find(parts[-1][1], 0x86)][:6]
                elif oid == OID_DELTA:
                    out['delta'] = True
    except (ValueError, IndexError, binascii.Error, AttributeError):
        pass
    try:
        nu = _openssl(['crl', '-noout', '-issuer', '-crlnumber', '-lastupdate', '-nextupdate',
                       '-nameopt', 'RFC2253'], pem.encode(), what='the CRL').decode('utf-8', 'replace')
        m = re.search(r'nextUpdate=(.+)', nu)
        if m and 'NONE' not in m.group(1):
            out['next'] = _crl_time(m.group(1)) or None
        m = re.search(r'lastUpdate=(.+)', nu)
        if m:
            out['this'] = _crl_time(m.group(1)) or None
        m = re.search(r'(?m)^issuer=\s*(.*)$', nu)
        out['issuer'] = m.group(1).strip()[:300] if m else ''
        m = re.search(r'crlNumber=(\S+)', nu)
        out['number'] = m.group(1)[:80] if m and 'NONE' not in m.group(1) else ''
    except (ValueError, CertError):
        pass
    return out


def crl_sig(pem):
    """Whether a CRL's signature is good by the authorities put in, as openssl crl -CAfile says it:
    'ok', 'bad', 'unknown' (its authority is not among them) or '' (no authority written out on
    this node). Only said - openssl verify checks it again at every sign-in."""
    if not CERT_CA_FILE.exists():
        return ''
    try:
        r = subprocess.run(['openssl', 'crl', '-noout', '-CAfile', str(CERT_CA_FILE), '-no-CApath',
                            '-no-CAstore'], input=pem.encode(), capture_output=True, timeout=30,
                           env=dict(os.environ, **CERT_NOENV))
    except (OSError, subprocess.SubprocessError):
        return ''
    words = (r.stdout or b'').decode('utf-8', 'replace') + (r.stderr or b'').decode('utf-8', 'replace')
    if 'verify OK' in words:
        return 'ok'
    if 'verify fail' in words:
        return 'bad'
    return 'unknown'


def crl_fetch(url, force=False):
    """The CRL at url (its facts and PEM): fetched again after CRL_FRESH_S at most - sooner at its
    next update; while the address does not answer, the last good one until its next update, then
    none. CrlRefused when there is none to be had - a CRL already past its next update is none.
    force (Fetch now): fetched whatever is kept - failing, the same as ever."""
    now = time.time()
    with CRL_LOCK:
        got = CRL_CACHE.get(url)
    good = bool(got and got.get('pem') and now < got['next'])
    if good and not force and (now - got['at'] < CRL_FRESH_S or now - float(got.get('tried') or 0) < 60):
        return got
    try:
        if url.lower().startswith('ldap://'):
            fetch = CRL_LDAP['fetch']
            if not fetch:
                raise ValueError('reading CRLs from the directory is off')
            raw = fetch(url)
        else:
            raw = crl_http_get(url)
        form = 'PEM' if b'-----BEGIN X509 CRL' in raw else 'DER'
        pem = _openssl(['crl', '-inform', form, '-outform', 'PEM'], raw,
                       what='the CRL').decode('ascii', 'replace')
        info = crl_info(pem)
        nxt = info['next'] or now + 3600
        if nxt <= now:
            raise ValueError('it has run out (its next update was %s)'
                             % time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(nxt)))
        one = {'at': now, 'pem': pem, 'next': nxt, 'url': url, 'err': '', 'tried': 0,
               'freshest': info['freshest'], 'delta': info['delta'], 'issuer': info['issuer'],
               'number': info['number'], 'this': info['this'], 'revoked': info['revoked'],
               'size': len(raw), 'sig': crl_sig(pem)}
        with CRL_LOCK:
            if len(CRL_CACHE) > 50:
                CRL_CACHE.clear()
            CRL_CACHE[url] = one
        return one
    except Exception as e:                              # noqa: BLE001
        why = str(e)[:200] or e.__class__.__name__
        if good:
            kept = dict(got, err=why, tried=now, err_at=now)    # the last good one, said why
            with CRL_LOCK:
                CRL_CACHE[url] = kept
            return kept
        with CRL_LOCK:
            CRL_CACHE[url] = {'at': now, 'pem': '', 'next': 0, 'url': url, 'err': why, 'err_at': now}
        raise CrlRefused('the CRL at %s could not be had (%s) - nobody signs in while the '
                         'certificate cannot be checked for revocation' % (url, why))


def _crl_any(urls):
    last = None
    for u in urls[:4]:
        try:
            return crl_fetch(u)
        except CrlRefused as e:
            last = e
    raise last


def crls_of(c, what):
    """The CRL of one certificate (a person's, or an authority's above it), and its delta CRL when
    it or the CRL names one: ([PEM], whether a delta is among them). CrlRefused - no CRL, no
    sign-in; a delta named and not to be had neither."""
    urls = crl_urls(c.get('cdp'))
    if not urls:
        if not [u for u in (c.get('cdp') or []) if u.lower().startswith('http://')]:
            raise CrlRefused('%s names no CRL over http (CRL Distribution Points) - it cannot be '
                             'checked for revocation' % what)
        raise CrlRefused('the CRL Distribution Point of %s is not an address a CRL is fetched from '
                         '(http; no loopback, link-local or metadata address)' % what)
    base = _crl_any(urls)
    out = [base['pem']]
    named = list(dict.fromkeys(list(c.get('freshest') or []) + list(base.get('freshest') or [])))
    if not named:
        return out, False
    urls = crl_urls(named)
    if not urls:
        raise CrlRefused('the delta CRL (Freshest CRL) of %s is at no address a CRL is fetched from '
                         '- its revocations of the last days cannot be seen' % what)
    out.append(_crl_any(urls)['pem'])
    return out, True


def cert_verify(leaf, crl_file=None, deltas=False, every=True):
    """openssl verify against the authorities put in and nothing else - never the system's own
    store: CertError, or None. With CRLs: every certificate of the chain checked (-crl_check_all:
    an issuing authority its root revoked too), deltas applied (-use_deltas)."""
    args = ['openssl', 'verify', '-no-CApath', '-no-CAstore', '-CAfile', str(CERT_CA_FILE)]
    if crl_file:
        # -crl_check_all: every certificate of the chain; -crl_check: the person's alone (an authority
        # above it that names no CRL - openssl would want one of it).
        args += ['-crl_check_all' if every else '-crl_check', '-CRLfile', crl_file] + (['-use_deltas'] if deltas else [])
    args.append(leaf)
    try:
        got = subprocess.run(args, capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, **CERT_NOENV))
    except (OSError, subprocess.SubprocessError) as e:
        raise CrlRefused('openssl did not run: %s' % e)
    if got.returncode == 0 and re.search(r':\s*OK\s*$', got.stdout or ''):
        return None
    words = (got.stdout or '') + '\n' + (got.stderr or '')
    m = re.search(r'error (\d+) at (\d+) depth lookup:\s*(.+)', words)
    why = ('%s%s' % (m.group(3).strip(), '' if m.group(2) == '0' else ' (an authority above it)')) \
        if m else re.sub(r'\S*otp-cert-\S*:?\s*', '', words).strip()[:300]
    if m and int(m.group(1)) in (3, 11, 12):
        raise CrlRefused('the certificate cannot be checked for revocation just now: %s' % why)
    raise CertError('the certificate is not taken: %s' % why)


def cert_ca_facts(store):
    """The authorities put in, each with its subject, issuer, CDPs and Freshest CRL (kept by
    their sha256)."""
    out = []
    for pem in cert_cas(store):
        key = hashlib.sha256(pem.encode()).hexdigest()
        f = CA_CDPS.get(key)
        if f is None:
            try:
                got = cert_facts(pem)
                f = {k: got[k] for k in ('subject', 'issuer', 'sha256', 'cdp', 'freshest', 'ocsp', 'serial')}
                f['pem'] = pem
            except CertError:
                f = {'subject': '', 'issuer': '', 'sha256': key, 'cdp': [], 'freshest': [], 'ocsp': [],
                     'serial': '', 'pem': pem}
            if len(CA_CDPS) > 200:
                CA_CDPS.clear()
            CA_CDPS[key] = f
        out.append(f)
    return out


def cert_chain(f, cas):
    """The authorities above a certificate among those put in, the nearest first; a root ends it."""
    out, want, seen = [], f.get('issuer'), set()
    for _ in range(8):
        hit = [c for c in cas if c['subject'] == want and c['sha256'] not in seen]
        if not hit:
            break
        for c in hit:
            seen.add(c['sha256'])
            out.append(c)
        if any(c['subject'] == c['issuer'] for c in hit):
            break
        want = hit[0]['issuer']
    return out


# -- OCSP (1.0.279, the ocsp-ldap-kit) -------------------------------------------------------------
def ocsp_mode():
    m = str(CONFIG.get('admin_cert_ocsp') or 'off')
    return m if m in OCSP_MODES else 'off'


def ocsp_url_set():
    u = str(CONFIG.get('admin_cert_ocsp_url') or '').strip()
    return u if u and cdp_ok(u) else ''


def ocsp_key(url, f):
    return '%s|%s|%s' % (url, f.get('issuer') or '', (f.get('serial') or '').upper())


def _ocsp_run(args):
    env = dict(os.environ, **CERT_NOENV)
    try:
        got = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env)
        if got.returncode and re.search(r'(?i)unknown option|unrecognized', got.stderr or '') \
                and '-no-CAstore' in args:
            args = [a for a in args if a != '-no-CAstore']          # OpenSSL 1.1.1
            got = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        raise ValueError('openssl did not run: %s' % e)
    return got


def ocsp_ask(url, f, pem, issuer_pem, force=False):
    """The responder at url asked about one certificate: {status: good | revoked | unknown, this, next,
    at, revoked_at, reason, responder, ...}; kept ten minutes at most (sooner at its next update), a
    responder that failed less than a minute ago not asked again, its last good answer used until
    its next update while it does not answer. CrlRefused when there is no answer to be had."""
    key = ocsp_key(url, f)
    now = time.time()
    with OCSP_LOCK:
        got = OCSP_CACHE.get(key)
    usable = bool(got and got.get('status') and (not got.get('next') or now < got['next']))
    if usable and not force and (now - got['at'] < CRL_FRESH_S or now - float(got.get('tried') or 0) < 60):
        return got
    base = {'url': url, 'key': key, 'subject': f.get('subject') or '',
            'serial': (f.get('serial') or '').upper(), 'issuer': f.get('issuer') or '',
            '_pem': pem, '_ipem': issuer_pem}
    raw = b''
    try:
        if not cdp_ok(url):
            raise ValueError('not an address otp asks (http; no loopback, link-local or metadata address)')
        with tempfile.TemporaryDirectory(prefix='otp-ocsp-') as work:
            cp, ip = os.path.join(work, 'cert.pem'), os.path.join(work, 'issuer.pem')
            rq, rs = os.path.join(work, 'req.der'), os.path.join(work, 'resp.der')
            with open(cp, 'w') as fh:
                fh.write(pem.strip() + '\n')
            with open(ip, 'w') as fh:
                fh.write(issuer_pem.strip() + '\n')
            made = _ocsp_run(['openssl', 'ocsp', '-issuer', ip, '-cert', cp, '-no_nonce', '-reqout', rq])
            if made.returncode or not os.path.exists(rq):
                raise ValueError('the request could not be made: %s' % (made.stderr or '').strip()[-200:])
            with open(rq, 'rb') as fh:
                body = fh.read()
            raw = crl_http_get(url, body=body, ctype='application/ocsp-request', most=OCSP_MOST)
            with open(rs, 'wb') as fh:
                fh.write(raw)
            said = _ocsp_run(['openssl', 'ocsp', '-respin', rs, '-issuer', ip, '-cert', cp,
                              '-CAfile', str(CERT_CA_FILE), '-no-CApath', '-no-CAstore', '-resp_text'])
        words = (said.stdout or '') + '\n' + (said.stderr or '')
        m = re.search(r'OCSP Response Status:\s*(\w+)', words)
        if not m:
            raise ValueError('not an OCSP answer')
        if m.group(1).lower() != 'successful':
            raise ValueError('the responder said: %s' % m.group(1))
        if 'Response verify OK' not in words:
            why = re.search(r'OCSP_basic_verify:([^:\n]+)', said.stderr or '') or \
                re.search(r'(?m)^.*verify[^\n]*$', said.stderr or '')
            raise ValueError('the answer\'s signature is not good by the authorities put in (%s)' % (
                why.group(1) if why and why.groups() else (why.group(0) if why else 'openssl said no')).strip()[:120])
        if re.search(r'(?i)status times invalid', words):
            raise ValueError('the answer is out of date (its next update has passed)')
        st = re.search(r'(?m)^\S[^\n]*?:\s*(good|revoked|unknown)\s*$', said.stdout or '')
        if not st:
            raise ValueError('the answer says nothing of this certificate')

        def when(label):
            mm = re.search(r'(?m)^\s*%s:\s*(.+)$' % label, said.stdout or '')
            return (_crl_time(mm.group(1)) or None) if mm else None
        rid = re.search(r'(?m)^\s*Responder Id:\s*(.+)$', words)
        reason = re.search(r'(?m)^\s*Reason:\s*(.+)$', said.stdout or '')
        one = dict(base, status=st.group(1), at=now, tried=0, err='', err_at=None,
                   this=when('This Update'), next=when('Next Update'), revoked_at=when('Revocation Time'),
                   reason=reason.group(1).strip()[:60] if reason else '',
                   responder=re.sub(r'\s*=\s*', '=', rid.group(1).strip())[:200] if rid else '', size=len(raw))
        with OCSP_LOCK:
            if len(OCSP_CACHE) > 200:
                OCSP_CACHE.clear()
            OCSP_CACHE[key] = one
        return one
    except Exception as e:                              # noqa: BLE001
        why = str(e)[:200] or e.__class__.__name__
        if usable and got.get('next'):
            kept = dict(got, err=why, tried=now, err_at=now)
            with OCSP_LOCK:
                OCSP_CACHE[key] = kept
            return kept
        with OCSP_LOCK:
            OCSP_CACHE[key] = dict(base, status='', at=now, next=None, err=why, err_at=now, tried=now)
        raise CrlRefused('the OCSP responder at %s gave no answer (%s)' % (url, why))


def ocsp_now():
    """The OCSP answers kept on this node, as the card shows them: never a certificate."""
    with OCSP_LOCK:
        got = list(OCSP_CACHE.values())
    out = []
    for c in sorted(got, key=lambda c: (c['url'], c.get('subject') or ''))[:CRL_SAID * 2]:
        out.append({k: c.get(k) for k in ('key', 'url', 'subject', 'serial', 'issuer', 'status', 'at', 'this',
                                          'next', 'err', 'err_at', 'revoked_at', 'reason', 'responder', 'size')})
    return out


def _crl_file(work, pems):
    cp = os.path.join(work, 'crl-%d.pem' % len(os.listdir(work)))
    with open(cp, 'w') as fh:
        fh.write(''.join(p if p.endswith('\n') else p + '\n' for p in pems))
    return cp


def cert_revocation(store, f, pem, work):
    """Whether a certificate whose chain is good is revoked (1.0.279) - by CRL, by OCSP, or both:
      off   the CRLs (as in 1.0.278, byte for byte);
      first OCSP; a responder that does not answer - its CRL instead;
      only  OCSP; no answer, no sign-in;
      both  OCSP and the CRL, both must say good.
    The certificate and every authority above it but the root, each asked of its own issuer.
    CertError, or [how each was checked]."""
    crl = bool(CONFIG.get('admin_cert_crl', 1))
    mode = ocsp_mode()
    lp = os.path.join(work, 'leaf.pem')
    cas = cert_ca_facts(store)
    chain = cert_chain(f, cas)
    if mode == 'off':
        if not crl:
            return []
        pems, deltas = crls_of(f, 'the certificate')
        every = True
        for c in chain:
            if c['subject'] != c['issuer'] and not c.get('cdp'):
                every = False
            # An authority above that names no CRL at all is not checked (1.0.278): an issuing
            # authority without a CDP signed people in before, and still does; one that names a
            # CRL is held to it - no CRL to be had, no sign-in.
            if c['subject'] != c['issuer'] and c.get('cdp'):
                more, d = crls_of(c, 'the authority %s' % c['subject'])
                pems += more
                deltas = deltas or d
        cert_verify(lp, _crl_file(work, pems), deltas, every)
        return ['crl']
    own = ocsp_url_set()
    items = [(f, pem, 'the certificate', True)]
    items += [(c, c.get('pem') or '', 'the authority %s' % c['subject'], False)
              for c in chain if c['subject'] != c['issuer']]
    how = []
    for c, cpem, what, leaf in items:
        parent = next((p for p in cas if p['subject'] == c['issuer'] and p.get('pem')), None)
        urls = [own] if own else [u for u in c.get('ocsp') or [] if u.lower().startswith('http://')][:2]
        by_crl = mode == 'both'
        if not urls or parent is None:
            if mode == 'only':
                raise CrlRefused('%s names no OCSP responder (Authority Information Access) and none is '
                                 'set - with OCSP only it cannot be checked' % what)
            by_crl = True
        else:
            answer, last = None, None
            for u in urls:
                try:
                    answer = ocsp_ask(u, c, cpem, parent['pem'])
                    break
                except CrlRefused as e:
                    last = e
            if answer is None:
                if mode in ('only', 'both') or not crl:
                    raise last
                by_crl = True
            elif answer['status'] == 'revoked':
                raise CertError('the certificate is not taken: %s is revoked, the OCSP responder says '
                                '(%s%s)' % (what, answer.get('reason') or 'no reason given',
                                            time.strftime(', %Y-%m-%d %H:%M UTC', time.gmtime(answer['revoked_at']))
                                            if answer.get('revoked_at') else ''))
            elif answer['status'] != 'good':
                raise CertError('the certificate is not taken: the OCSP responder does not know %s '
                                '(unknown) - it is not one its authority issued' % what)
            else:
                how.append('ocsp')
        if by_crl:
            if not crl and mode == 'first':
                raise CrlRefused('%s cannot be checked: no OCSP answer, and CRLs are off' % what)
            if not leaf and not c.get('cdp'):
                continue            # an authority above that names no CRL: not checked (1.0.278)
            if crl or mode == 'both':
                pems, deltas = crls_of(c, what)
                cf = lp if leaf else os.path.join(work, 'ca-%s.pem' % c.get('sha256', 'x')[:16])
                if not leaf:
                    with open(cf, 'w') as fh:
                        fh.write(cpem.strip() + '\n')
                cert_verify(cf, _crl_file(work, pems), deltas, every=False)
                how.append('crl')
    return how


# -- the check --------------------------------------------------------------------------------
def cert_check(store, pem):
    """The facts of a client certificate that passed every check, or CertError."""
    pem = str(pem or '').strip()
    if not pem:
        raise CertError('no certificate was sent (none chosen, or the browser has none from the '
                        'authorities put in here)')
    if len(pem) > CERT_MOST:
        raise CertError('larger than any certificate of a person')
    f = cert_facts(pem)
    if f['ca']:
        raise CertError('that is the certificate of an authority, not of a person')
    if f['unknown_critical']:
        raise CertError('the certificate has a critical extension otp does not know (%s)'
                        % ', '.join(f['unknown_critical']))
    if not f['eku'] or not set(f['eku']) & set(EKU_SIGN_IN):
        raise CertError('the certificate is not for signing in (no Client Authentication or Smart '
                        'Card Logon among its key usages)')
    cas = cert_cas(store)
    if not cas or not CERT_CA_FILE.exists():
        raise CertError('no authority is put in on this node yet')
    work = tempfile.mkdtemp(prefix='otp-cert-')
    try:
        lp = os.path.join(work, 'leaf.pem')
        with open(lp, 'w') as fh:
            fh.write(pem + '\n')
        # The chain first (1.0.278): a CRL's address is fetched only for a certificate of an
        # authority put in - nginx takes anybody's on its port.
        cert_verify(lp)
        cert_revocation(store, f, pem, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not f['upn']:
        raise CertError('the certificate names no user (no UPN in its Subject Alternative Name)')
    return f


# -- the CRLs as the card shows them; Fetch now and Clear, asked of every node -----------------
def crls_now():
    """The CRLs kept on this node: facts and dates only, never a CRL - CRL_SAID at most."""
    with CRL_LOCK:
        got = list(CRL_CACHE.values())
    out = []
    for c in sorted(got, key=lambda c: c['url'])[:CRL_SAID]:
        one = {'url': c['url'], 'ok': bool(c.get('pem')), 'at': c.get('at'),
               'next': c.get('next') or None, 'err': c.get('err') or ''}
        for k in ('err_at', 'this', 'size', 'revoked', 'number', 'issuer', 'sig', 'delta'):
            if c.get(k) not in (None, ''):
                one[k] = c[k]
        if c.get('freshest'):
            one['freshest'] = list(c['freshest'])[:3]
        out.append(one)
    return out


def crl_known(store):
    """The CRLs the authorities put in name (their CDPs and Freshest CRL) - those a sign-in fetches
    for the authorities above a person's certificate (a root's own left out)."""
    out = {}
    for c in cert_ca_facts(store):
        if not c.get('subject') or c['subject'] == c['issuer']:
            continue
        for delta, urls in ((False, c['cdp']), (True, c['freshest'])):
            for u in urls:
                if crl_where_ok(u):
                    one = out.setdefault(u, {'url': u, 'of': [], 'delta': delta})
                    if c['subject'] not in one['of']:
                        one['of'].append(c['subject'])
    return [out[u] for u in sorted(out)][:CRL_SAID]


def crl_urls_here(store):
    """Every CRL Fetch now fetches on this node: those kept here (and the delta CRLs they name)
    and those the authorities name."""
    with CRL_LOCK:
        got = list(CRL_CACHE.values())
    urls = [c['url'] for c in got]
    for c in got:
        urls += list(c.get('freshest') or [])
    urls += [k['url'] for k in crl_known(store)]
    return [u for u in dict.fromkeys(urls) if crl_where_ok(u)][:CRL_SAID]


def crl_rows(store, seen):
    """One row for each CRL: as kept on each node (seen: {url: [its state on a node, node=...]}) -
    the facts of the newest good one, else of the newest - and those the authorities name, not
    fetched yet."""
    known = {k['url']: k for k in crl_known(store)}
    out = []
    now = time.time()
    for url in sorted(set(seen) | set(known)):
        each = sorted(seen.get(url) or [], key=lambda c: c['node'])
        good = [c for c in each if c.get('ok') and float(c.get('next') or 0) > now]
        best = max(good or each, key=lambda c: float(c.get('at') or 0)) if each else {}
        k = known.get(url) or {}
        row = {'url': url, 'via': 'ldap' if url.lower().startswith('ldap://') else 'http',
               'fetched': bool(each), 'ok': bool(good), 'of': k.get('of') or [],
               'named': bool(k), 'delta': bool(best.get('delta') if best else k.get('delta')),
               'err': next((c.get('err') for c in sorted(each, key=lambda c: -float(
                   c.get('err_at') or c.get('at') or 0)) if c.get('err')), '') if each else '',
               'nodes': [{x: c.get(x) for x in ('node', 'ok', 'at', 'next', 'err', 'err_at', 'number')}
                         for c in each]}
        for x in ('at', 'next', 'this', 'issuer', 'number', 'size', 'revoked', 'sig', 'err_at'):
            row[x] = best.get(x) if best else None
        out.append(row)
    return out[:CRL_SAID * 2]


def crl_view_rows(store):
    crls = {}
    for n in sorted(set(host_nodes(store)) | {node_name()}):
        got = json_obj(store.get_meta('certlogin:node:' + n)) or {}
        if n == node_name() and CERT_NODE.get('at'):
            # This node's own, in the daemon: what it has now (the command line has none of its own).
            got = dict(got, crls=crls_now())
        for c in got.get('crls') or []:
            if isinstance(c, dict) and c.get('url'):
                crls.setdefault(c['url'], []).append(dict(c, node=n))
    return crl_rows(store, crls)


def crl_do(store, act, url=''):
    """Fetch now ('fetch') or Clear ('clear') on this node - every CRL, or the one at url. A fetch
    that fails changes nothing that lets anybody in. [{url, ok, err}]; this node's state written
    at once."""
    out = []
    if act == 'clear':
        with CRL_LOCK:
            gone = [u for u in CRL_CACHE if not url or u == url]
            for u in gone:
                CRL_CACHE.pop(u, None)
        out = [{'url': u, 'ok': True, 'err': ''} for u in sorted(gone)]
    elif act == 'fetch':
        todo, done = ([url] if url else crl_urls_here(store)), set()
        while todo and len(done) < CRL_SAID:
            u = todo.pop(0)
            if u in done:
                continue
            done.add(u)
            try:
                got = crl_fetch(u, force=True)
                out.append({'url': u, 'ok': not got.get('err'), 'err': got.get('err') or '',
                            'number': got.get('number') or ''})
                if not url:
                    todo += [f for f in got.get('freshest') or []
                             if crl_where_ok(f)]
            except CertError as e:
                with CRL_LOCK:
                    why = (CRL_CACHE.get(u) or {}).get('err') or str(e)
                out.append({'url': u, 'ok': False, 'err': str(why)[:200]})
            except Exception as e:                      # noqa: BLE001
                out.append({'url': u, 'ok': False, 'err': str(e)[:200]})
    try:
        cert_tick(store, now_too=True)
    except Exception as e:                              # noqa: BLE001
        log_sparing('cert-say', 'the state of the sign-in with a certificate: %s' % e, 'warn', 300)
    return out


@node_ask_kind('crl_fetch')
def _ask_crl_fetch(daemon, args):
    got = crl_do(daemon.store, 'fetch', str(args.get('url') or ''))
    return {'ok': all(x['ok'] for x in got), 'crls': got}


@node_ask_kind('crl_clear')
def _ask_crl_clear(daemon, args):
    got = crl_do(daemon.store, 'clear', str(args.get('url') or ''))
    return {'ok': True, 'crls': got}


def crl_ask(d, act, url, by):
    """Fetch now or Clear asked of every node (each does it itself; this one at once from the
    pages): the ask {id, nodes}, the event written. ValueError for an address not known."""
    url = str(url or '').strip()
    if url:
        known = {k['url'] for k in crl_known(d.store)} | {r['url'] for r in crl_view_rows(d.store)} | \
            {c['url'] for c in crls_now()}
        if url not in known:
            raise ValueError('no CRL at that address is known here (otp --cert-crl lists them)')
    if act == 'fetch':
        words = ('%s asked every node to fetch the CRL at %s again' % (by, url) if url else
                 '%s asked every node to fetch every CRL of the sign-in with a certificate again' % by)
    else:
        words = ('%s cleared the CRL at %s on every node - it is fetched again at the next sign-in'
                 % (by, url) if url else '%s cleared the CRLs of the sign-in with a certificate on '
                 'every node - each is fetched again at the next sign-in' % by)
    d.store.add_event('settings', words[:600], 'info', who=by)
    return node_ask(d, 'crl_' + act, {'url': url, 'by': by}, by)


def ocsp_view_rows(store):
    """The OCSP answers kept on each node, one row each (the newest good one's facts, else the
    newest), each node's beside it - never a certificate."""
    seen = {}
    for n in sorted(set(host_nodes(store)) | {node_name()}):
        got = json_obj(store.get_meta('certlogin:node:' + n)) or {}
        if n == node_name() and CERT_NODE.get('at'):
            got = dict(got, ocsp=ocsp_now())
        for c in got.get('ocsp') or []:
            if isinstance(c, dict) and c.get('key'):
                seen.setdefault(c['key'], []).append(dict(c, node=n))
    out = []
    now = time.time()
    for key in sorted(seen):
        each = seen[key]
        good = [c for c in each if c.get('status') and (not c.get('next') or float(c['next']) > now)]
        best = dict(max(good or each, key=lambda c: float(c.get('at') or 0)))
        best['nodes'] = [{x: c.get(x) for x in ('node', 'status', 'at', 'next', 'err', 'err_at')} for c in each]
        best.pop('node', None)
        out.append(best)
    return out[:CRL_SAID * 2]


def ocsp_do(act, key=''):
    """Ask again ('fetch') or forget ('clear') the OCSP answers on this node - all, or the one of key."""
    with OCSP_LOCK:
        todo = [dict(c) for k, c in OCSP_CACHE.items() if not key or k == key]
    if act == 'clear':
        with OCSP_LOCK:
            for c in todo:
                OCSP_CACHE.pop(c['key'], None)
        return [{'url': c['url'], 'key': c['key'], 'ok': True, 'err': ''} for c in todo]
    out = []
    for c in todo[:CRL_SAID * 2]:
        f = {'subject': c.get('subject'), 'issuer': c.get('issuer'), 'serial': c.get('serial')}
        try:
            got = ocsp_ask(c['url'], f, c.get('_pem') or '', c.get('_ipem') or '', force=True)
            out.append({'url': c['url'], 'key': c['key'], 'ok': not got.get('err'),
                        'err': got.get('err') or '', 'status': got.get('status') or ''})
        except CertError:
            with OCSP_LOCK:
                why = (OCSP_CACHE.get(c['key']) or {}).get('err') or 'no answer'
            out.append({'url': c['url'], 'key': c['key'], 'ok': False, 'err': why[:200], 'status': ''})
    return out


@node_ask_kind('ocsp_fetch')
def _ask_ocsp_fetch(daemon, args):
    got = ocsp_do('fetch', str(args.get('url') or ''))
    try:
        cert_tick(daemon.store, now_too=True)
    except Exception:                                   # noqa: BLE001
        pass
    return {'ok': all(x['ok'] for x in got), 'crls': got}


@node_ask_kind('ocsp_clear')
def _ask_ocsp_clear(daemon, args):
    got = ocsp_do('clear', str(args.get('url') or ''))
    try:
        cert_tick(daemon.store, now_too=True)
    except Exception:                                   # noqa: BLE001
        pass
    return {'ok': True, 'crls': got}


def ocsp_ask_all(d, act, key, by):
    """Ask again or forget the OCSP answers, on every node: {id, nodes}; the event written.
    ValueError for a key kept on no node."""
    key = str(key or '').strip()
    if key:
        known = {r['key'] for r in ocsp_view_rows(d.store)} | {c['key'] for c in ocsp_now()}
        if key not in known:
            raise ValueError('no OCSP answer of that is kept here (otp --cert-ocsp lists them)')
    what = key.split('|', 1)[0] if key else ''
    if act == 'fetch':
        words = ('%s asked the OCSP responder at %s again' % (by, what) if key else
                 '%s asked every OCSP responder of the sign-in with a certificate again' % by)
    else:
        words = ('%s cleared an OCSP answer of %s - asked again at the next sign-in' % (by, what) if key
                 else '%s cleared the OCSP answers of the sign-in with a certificate - each is asked again '
                 'at the next sign-in' % by)
    d.store.add_event('settings', words[:600], 'info', who=by)
    return node_ask(d, 'ocsp_' + act, {'url': key, 'by': by}, by)


def admin_password_off_now():
    """No password anywhere (1.0.274, 1.0.275): only while signing in another way can work at all -
    Kerberos or a certificate on, with the directory; switched off, passwords are taken again."""
    return bool(CONFIG.get('admin_password_off') and CONFIG.get('admin_directory')
                and (CONFIG.get('admin_kerberos') or CONFIG.get('admin_cert')))


def cert_view(store):
    meta = json_obj(store.get_meta(CERT_META)) or {}
    cas = []
    for p in cert_cas(store):
        try:
            f = cert_facts(p)
            cas.append({k: f[k] for k in ('subject', 'issuer', 'not_after', 'sha256')})
        except CertError as e:
            cas.append({'subject': '?', 'issuer': '', 'not_after': '', 'sha256': '', 'err': str(e)})
    nodes = []
    alive = host_alive(store)
    for n in host_nodes(store):
        got = json_obj(store.get_meta('certlogin:node:' + n)) or {}
        nodes.append({'name': n, 'alive': alive.get(n, False), 'at': got.get('at'),
                      'cas': got.get('cas', 0), 'file': bool(got.get('file')),
                      'listening': bool(got.get('listening')), 'err': got.get('err') or ''})
    crls = crl_view_rows(store)
    ocsp_rows = ocsp_view_rows(store)
    names = []
    try:
        names = krb_names(store)
    except Exception:                                   # noqa: BLE001
        names = []
    return {'on': bool(CONFIG.get('admin_cert')), 'auto': bool(CONFIG.get('admin_cert_auto')),
            'port': int(CONFIG.get('admin_cert_port') or 8443),
            'map': str(CONFIG.get('admin_cert_map') or 'compat'), 'crl': bool(CONFIG.get('admin_cert_crl', 1)),
            'directory': CONFIG.get('admin_directory') or '', 'mfa': bool(CONFIG.get('admin_2fa')),
            'password_off': admin_password_off_now(), 'cas': cas, 'cas_at': meta.get('at'),
            'cas_by': meta.get('by') or '', 'nodes': nodes, 'crls': crls,
            'names': [{'for': n['for'], 'name': n['name']} for n in names],
            'ocsp': ocsp_mode(), 'ocsp_url': str(CONFIG.get('admin_cert_ocsp_url') or ''),
            'ocsp_url_ok': bool(ocsp_url_set()), 'crl_ldap': bool(_setting_on(CONFIG.get('admin_cert_crl_ldap'))),
            'ocsp_answers': ocsp_rows}


def signin_last_way(store, what):
    """Why taking `what` ('keytab' or the last 'authority') away would leave nobody a way in (1.0.277),
    or '': with no password at all in effect, the keytab while no certificate signs in, the last
    authority while Windows does not."""
    if not admin_password_off_now():
        return ''
    krb = bool(CONFIG.get('admin_kerberos') and CONFIG.get('admin_directory') and krb_keytab_raw(store))
    crt = bool(CONFIG.get('admin_cert') and CONFIG.get('admin_directory') and cert_cas(store))
    if what == 'keytab' and not crt:
        return ('the keytab signs everybody in - with no password at all, nobody could sign in without it: '
                'switch No password at all off first (or a certificate on)')
    if what == 'authority' and not krb and len(cert_cas(store)) <= 1:
        return ('the last authority signs everybody in - with no password at all, nobody could sign in '
                'without it: switch No password at all off first (or Windows on)')
    return ''


def signin_ways_problem(store, checked, how=None, session=False):
    """Why a batch of settings would leave nobody a way in (1.0.278), or '' - the settings as they
    will be after it, on every road to a save (the pages, otp --set, an imported configuration):
    with no password at all in effect, at least one way that is on must work (Windows with a keytab,
    a certificate with an authority). session: the save comes from a sign-in (the pages) - no
    password at all put in effect from it only when it was made by a way that will still work."""
    def after(k):
        return checked[k] if k in (checked or {}) else CONFIG.get(k)
    keys = ('admin_password_off', 'admin_kerberos', 'admin_cert', 'admin_directory')
    if not any(k in (checked or {}) for k in keys):
        return ''
    if _setting_on((checked or {}).get('admin_password_off')) and \
            not _setting_on(CONFIG.get('admin_password_off')) and not (
            _setting_on(after('admin_kerberos')) or _setting_on(after('admin_cert'))):
        # Saved with no way on it did nothing - and lay in wait (1.0.278): the next switch of Windows
        # or a certificate put it in effect, or was refused for a password nobody had asked about.
        return ('admin_password_off: no password at all needs Windows or a certificate on - switch one '
                'on first (nothing saved)')
    if not (_setting_on(after('admin_password_off')) and after('admin_directory')
            and (_setting_on(after('admin_kerberos')) or _setting_on(after('admin_cert')))):
        return ''                               # the password is offered after it: nobody locked out
    krb = _setting_on(after('admin_kerberos')) and bool(krb_keytab_raw(store))
    crt = _setting_on(after('admin_cert')) and bool(cert_cas(store))
    if not (krb or crt):
        return ('with no password at all, nobody could sign in after this: Windows needs its keytab, a '
                'certificate an authority - put one in, or switch No password at all off (nothing saved)')
    if session and not admin_password_off_now():
        # Put in effect now: only from a sign-in made by a way that will still sign its person in.
        if how not in ('Kerberos', 'certificate'):
            return ('no password at all (admin_password_off) would be in effect after this: sign in with '
                    'Windows or a certificate first, so it is known to work for you - or switch it off in '
                    'the same save (nothing saved)')
        if how == 'Kerberos' and not krb:
            return ('you signed in with Windows, which would not sign anybody in after this (switched off, '
                    'or no keytab) - nothing saved')
        if how == 'certificate' and not crt:
            return ('you signed in with a certificate, which would not sign anybody in after this '
                    '(switched off, or no authority) - nothing saved')
    return ''


def cert_problems(store):
    if not CONFIG.get('admin_cert'):
        return []
    out = []
    if not CONFIG.get('admin_directory'):
        out.append('no directory is set for administrators (Sign administrators in against the directory)')
    if not cert_cas(store):
        out.append('no authority is put in')
    if CERT_NODE.get('err'):
        out.append(CERT_NODE['err'])
    return out
