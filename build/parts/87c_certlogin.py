

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
        cdp = [u.decode('ascii', 'replace') for u in _der_find(exts[OID_CDP][1], 0x86)]
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
            'eku': eku, 'ca': is_ca, 'cdp': cdp, 'unknown_critical': sorted(
                k for k, (c, _v) in exts.items() if c and k not in (OID_SAN, OID_EKU, OID_BC, '2.5.29.15',
                                                                     OID_CDP, '2.5.29.32'))}


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


def cert_tick(store):
    """Each node: the authorities written out for the checks, and what this node can do said."""
    v = store.get_meta(CERT_META)
    port = int(CONFIG.get('admin_cert_port') or 8443)
    lis = bool(CONFIG.get('admin_cert')) and cert_listening(port)
    if v == CERT_NODE.get('v') and lis == CERT_NODE.get('lis') and time.time() - CERT_NODE['at'] < 300:
        return
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
            'listening': lis, 'port': port,
            'err': err, 'version': __version__}
    store.set_meta('certlogin:node:' + node_name(), json.dumps(said))
    CERT_NODE.update(said=said, at=time.time(), err=err)


# -- revocation -------------------------------------------------------------------------------
def cdp_url_ok(url):
    """A CRL Distribution Point otp asks: http(s) on their own ports, never this machine, a
    link-local or a broadcast address (as a CA Issuers address)."""
    if os.environ.get('OTP_CDP_LOCAL') == '1':
        u = urllib.parse.urlsplit(str(url or ''))
        if u.scheme in ('http', 'https') and u.hostname:
            return
    return aia_url_ok(url)


def crl_fetch(url):
    """The CRL at url as PEM and its next update - kept until then (an hour when it says nothing),
    and used while still good when the address does not answer."""
    now = time.time()
    with CRL_LOCK:
        got = CRL_CACHE.get(url)
    if got and now < got['next'] and now - got['at'] < 86400:
        return got
    try:
        raw = b''
        with url_open(urllib.request.Request(url, headers={'User-Agent': 'otp/%s' % __version__}),
                      timeout=10, purpose='acme', check=cdp_url_ok) as r:
            while len(raw) <= CRL_MOST:
                part = r.read(65536)
                if not part:
                    break
                raw += part
        if len(raw) > CRL_MOST:
            raise ValueError('larger than %d MB' % (CRL_MOST >> 20))
        if b'-----BEGIN X509 CRL' in raw:
            pem = _openssl(['crl', '-outform', 'PEM'], raw, what='the CRL').decode('ascii', 'replace')
        else:
            pem = _openssl(['crl', '-inform', 'DER', '-outform', 'PEM'], raw,
                           what='the CRL').decode('ascii', 'replace')
        nu = _openssl(['crl', '-noout', '-nextupdate'], pem.encode(), what='the CRL').decode()
        m = re.search(r'nextUpdate=(.+)', nu)
        nxt = now + 3600
        if m and 'NONE' not in m.group(1):
            try:
                nxt = calendar.timegm(time.strptime(m.group(1).strip().replace(' GMT', ''),
                                                    '%b %d %H:%M:%S %Y'))
            except ValueError:
                pass
        one = {'at': now, 'pem': pem, 'next': nxt, 'url': url, 'err': ''}
        with CRL_LOCK:
            if len(CRL_CACHE) > 50:
                CRL_CACHE.clear()
            CRL_CACHE[url] = one
        return one
    except Exception as e:                              # noqa: BLE001
        why = str(e)[:200] or e.__class__.__name__
        if got and now < got['next']:
            return got                                  # still good: the last one
        with CRL_LOCK:
            CRL_CACHE[url] = {'at': now, 'pem': '', 'next': 0, 'url': url, 'err': why}
        raise CertError('the CRL at %s could not be had (%s) - nobody signs in while the '
                        'certificate cannot be checked' % (url, why))


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
    args = ['verify', '-CAfile', str(CERT_CA_FILE)]
    work = tempfile.mkdtemp(prefix='otp-cert-')
    try:
        if CONFIG.get('admin_cert_crl', 1):
            urls = [u for u in f['cdp'] if u.lower().startswith(('http://', 'https://'))]
            if not urls:
                raise CertError('the certificate names no CRL over http (CRL Distribution Points) - '
                                'it cannot be checked for revocation')
            crl = None
            last = None
            for u in urls[:3]:
                try:
                    crl = crl_fetch(u)
                    break
                except CertError as e:
                    last = e
            if crl is None:
                raise last
            cp = os.path.join(work, 'crl.pem')
            with open(cp, 'w') as fh:
                fh.write(crl['pem'])
            args += ['-crl_check', '-CRLfile', cp]
        lp = os.path.join(work, 'leaf.pem')
        with open(lp, 'w') as fh:
            fh.write(pem + '\n')
        args.append(lp)
        try:
            got = subprocess.run(['openssl'] + args, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            raise CertError('openssl did not run: %s' % e)
        if got.returncode != 0 or not re.search(r':\s*OK\s*$', got.stdout or ''):
            words = (got.stdout or '') + '\n' + (got.stderr or '')
            m = re.search(r'error \d+ at (\d+) depth lookup:\s*(.+)', words)
            raise CertError('the certificate is not taken: %s' % (
                ('%s%s' % (m.group(2).strip(), '' if m.group(1) == '0' else ' (an authority above it)'))
                if m else re.sub(r'\S*otp-cert-\S*:?\s*', '', words).strip()[:300]))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not f['upn']:
        raise CertError('the certificate names no user (no UPN in its Subject Alternative Name)')
    return f


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
    with CRL_LOCK:
        crls = [{'url': c['url'], 'ok': bool(c['pem']), 'at': c['at'], 'next': c['next'],
                 'err': c.get('err') or ''} for c in CRL_CACHE.values()]
    names = []
    try:
        names = krb_names(store)
    except Exception:                                   # noqa: BLE001
        names = []
    return {'on': bool(CONFIG.get('admin_cert')), 'port': int(CONFIG.get('admin_cert_port') or 8443),
            'map': str(CONFIG.get('admin_cert_map') or 'compat'), 'crl': bool(CONFIG.get('admin_cert_crl', 1)),
            'directory': CONFIG.get('admin_directory') or '', 'mfa': bool(CONFIG.get('admin_2fa')),
            'password_off': admin_password_off_now(), 'cas': cas, 'cas_at': meta.get('at'),
            'cas_by': meta.get('by') or '', 'nodes': nodes, 'crls': crls,
            'names': [{'for': n['for'], 'name': n['name']} for n in names]}


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
