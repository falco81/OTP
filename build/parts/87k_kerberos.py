

# ---- Signing in to these pages with Windows (Kerberos, SPNEGO) (1.0.274) ----------------
# Off by default (admin_kerberos). The browser of somebody signed in to the domain sends a
# Kerberos service ticket for HTTP/<the name it opened> in "Authorization: Negotiate"; the
# pages hand it here, and it is checked against the keytab of that service - with the
# system's own GSS-API library (libgssapi_krb5, part of every RHEL, Rocky, AlmaLinux, Debian
# and Ubuntu), called through ctypes: nothing to install, no Python package. The name it
# proves (novak@CORP.EXAMPLE) is looked up in the directory the administrators sign in
# against (admin_directory) - its groups give the role, as a password would have. The
# second step, when it is on, is asked just the same: Kerberos takes the place of the
# password only.
#
# NTLM is never taken: a token of NTLM (bare, or inside SPNEGO) is refused, and so is any
# mechanism of SPNEGO but Kerberos 5. Nothing of it can be switched on.
#
# The keytab is uploaded on the pages (a full administrator), kept in the database sealed
# with this installation's key (so the other node of a cluster has it too), and written by
# each node to STATE_DIR/kerberos/http.keytab (0600, otp's own). It is never shown again:
# only its principals, key versions and kinds of key.
import ctypes
import ctypes.util

KRB_DIR = STATE_DIR / 'kerberos'
KRB_KEYTAB = KRB_DIR / 'http.keytab'
KRB_RCACHE = KRB_DIR / 'rcache'
KRB_META = 'kerberos:keytab'
KRB_KEYTAB_MAX = 65536
KRB_TOKEN_MAX = 65536
KRB5_MECH = bytes.fromhex('2a864886f712010202')          # 1.2.840.113554.1.2.2
KRB_LIB = {'lib': None, 'tried': False, 'err': '', 'lock': threading.Lock()}
KRB_NODE = {'sha': None, 'said': None, 'at': 0.0, 'err': '', 'v': None}
KRB_ENCTYPES = {1: 'des-cbc-crc', 3: 'des-cbc-md5', 16: 'des3-cbc-sha1', 17: 'aes128-cts-hmac-sha1-96',
                18: 'aes256-cts-hmac-sha1-96', 19: 'aes128-cts-hmac-sha256-128',
                20: 'aes256-cts-hmac-sha384-192', 23: 'rc4-hmac', 24: 'rc4-hmac-exp',
                25: 'camellia128-cts-cmac', 26: 'camellia256-cts-cmac'}
KRB_WEAK = (1, 3, 16, 23, 24)
GSS_S_COMPLETE = 0
GSS_S_CONTINUE_NEEDED = 1


class KrbError(Exception):
    """A ticket not taken: the words say why (never anything secret)."""


class _GssBuf(ctypes.Structure):
    _fields_ = [('length', ctypes.c_size_t), ('value', ctypes.c_void_p)]


class _GssOid(ctypes.Structure):
    _fields_ = [('length', ctypes.c_uint32), ('elements', ctypes.c_void_p)]


def krb_env():
    """Where the library finds the keytab and keeps its replay cache: set once for the
    process (the library reads them on each call)."""
    os.environ['KRB5_KTNAME'] = 'FILE:%s' % KRB_KEYTAB
    os.environ['KRB5RCACHEDIR'] = str(KRB_RCACHE)


def krb_lib():
    """The system's GSS-API library, or None (KRB_LIB['err'] says why)."""
    with KRB_LIB['lock']:
        if KRB_LIB['tried']:
            return KRB_LIB['lib']
        KRB_LIB['tried'] = True
        try:
            path = ctypes.util.find_library('gssapi_krb5') or 'libgssapi_krb5.so.2'
            lib = ctypes.CDLL(path)
            P, U, V = ctypes.POINTER, ctypes.c_uint32, ctypes.c_void_p
            lib.gss_accept_sec_context.argtypes = [P(U), P(V), V, P(_GssBuf), V, P(V), P(P(_GssOid)),
                                                   P(_GssBuf), P(U), P(U), P(V)]
            lib.gss_accept_sec_context.restype = U
            lib.gss_display_name.argtypes = [P(U), V, P(_GssBuf), P(P(_GssOid))]
            lib.gss_display_name.restype = U
            lib.gss_display_status.argtypes = [P(U), U, ctypes.c_int, V, P(U), P(_GssBuf)]
            lib.gss_display_status.restype = U
            lib.gss_release_buffer.argtypes = [P(U), P(_GssBuf)]
            lib.gss_release_name.argtypes = [P(U), P(V)]
            lib.gss_delete_sec_context.argtypes = [P(U), P(V), V]
            krb_env()
            KRB_LIB['lib'] = lib
        except (OSError, AttributeError) as e:
            KRB_LIB['err'] = 'the GSS-API library of Kerberos (libgssapi_krb5) is not there: %s' % e
            KRB_LIB['lib'] = None
        return KRB_LIB['lib']


def _gss_words(lib, major, minor):
    out = []
    for code, kind in ((major, 1), (minor, 2)):
        if not code:
            continue
        ctx = ctypes.c_uint32(0)
        for _ in range(8):
            m = ctypes.c_uint32()
            buf = _GssBuf()
            if lib.gss_display_status(ctypes.byref(m), code, kind, None, ctypes.byref(ctx),
                                      ctypes.byref(buf)) != 0:
                break
            try:
                words = ctypes.string_at(buf.value, buf.length).decode('utf-8', 'replace').strip()
            finally:
                lib.gss_release_buffer(ctypes.byref(m), ctypes.byref(buf))
            if words and words not in out:
                out.append(words)
            if not ctx.value:
                break
    return '; '.join(out)[:400] or 'GSS-API status %#x/%d' % (major, minor)


def krb_is_ntlm(token):
    """A token of NTLM, bare or carried by SPNEGO."""
    return b'NTLMSSP\x00' in bytes(token or b'')


def krb_accept(token):
    """The principal a Kerberos ticket (SPNEGO or bare) proves: 'novak@CORP.EXAMPLE'. Refuses
    NTLM, any other mechanism, a ticket for a service not in the keytab, an old or replayed one."""
    token = bytes(token or b'')
    if not token:
        raise KrbError('the browser sent no ticket')
    if len(token) > KRB_TOKEN_MAX:
        raise KrbError('the ticket is larger than any Kerberos ticket')
    if krb_is_ntlm(token):
        raise KrbError('the browser offered NTLM, which is never taken here - only Kerberos '
                       '(is the name it opened in the keytab, and is the computer in the domain?)')
    lib = krb_lib()
    if lib is None:
        raise KrbError(KRB_LIB['err'] or 'no GSS-API library')
    if not KRB_KEYTAB.exists():
        raise KrbError('this node has no keytab yet')
    minor = ctypes.c_uint32()
    ctx = ctypes.c_void_p()
    raw = ctypes.create_string_buffer(token, len(token))
    inb = _GssBuf(len(token), ctypes.cast(raw, ctypes.c_void_p))
    src = ctypes.c_void_p()
    mech = ctypes.POINTER(_GssOid)()
    out = _GssBuf()
    flags = ctypes.c_uint32()
    try:
        major = lib.gss_accept_sec_context(ctypes.byref(minor), ctypes.byref(ctx), None,
                                           ctypes.byref(inb), None, ctypes.byref(src),
                                           ctypes.byref(mech), ctypes.byref(out),
                                           ctypes.byref(flags), None, None)
        if major == GSS_S_CONTINUE_NEEDED:
            raise KrbError('the browser wants more than one round - that is not Kerberos (NTLM?)')
        if major != GSS_S_COMPLETE:
            raise KrbError('the ticket was not taken: %s' % _gss_words(lib, major, minor.value))
        got = ctypes.string_at(mech.contents.elements, mech.contents.length) if mech else b''
        if got != KRB5_MECH:
            raise KrbError('the browser used a mechanism that is not Kerberos 5')
        name = _GssBuf()
        m2 = ctypes.c_uint32()
        if lib.gss_display_name(ctypes.byref(m2), src, ctypes.byref(name), None) != 0:
            raise KrbError('the ticket has no name that can be read')
        try:
            who = ctypes.string_at(name.value, name.length).decode('utf-8', 'replace')
        finally:
            lib.gss_release_buffer(ctypes.byref(m2), ctypes.byref(name))
        return who
    finally:
        m3 = ctypes.c_uint32()
        if out.value:
            lib.gss_release_buffer(ctypes.byref(m3), ctypes.byref(out))
        if src.value:
            lib.gss_release_name(ctypes.byref(m3), ctypes.byref(src))
        if ctx.value:
            lib.gss_delete_sec_context(ctypes.byref(m3), ctypes.byref(ctx), None)


def krb_principal_split(principal):
    """('novak', 'CORP.EXAMPLE') of a person's principal; a service's (HTTP/x@R), one with a
    second @ or none, or letters a name never has: refused."""
    p = str(principal or '')
    if p.count('@') != 1 or '/' in p or '\\' in p:
        raise KrbError('%s is not the name of a person' % p[:200])
    user, realm = p.split('@', 1)
    if not user or not realm or not re.match(r'^[A-Za-z0-9._-]{1,253}\Z', realm):
        raise KrbError('%s is not the name of a person' % p[:200])
    return user, realm.upper()


def krb_realm_wanted(store=None):
    """The realm whose people may sign in: as set, or from the base DN of the directory the
    administrators sign in against (DC=corp,DC=example -> CORP.EXAMPLE)."""
    set_ = str(CONFIG.get('admin_kerberos_realm') or '').strip().upper()
    if set_:
        return set_
    name = str(CONFIG.get('admin_directory') or '').lower()
    if not name or store is None:
        return ''
    try:
        row = store.db.row('SELECT * FROM directories WHERE LOWER(name) = ?', (name,))
    except Exception:                                   # noqa: BLE001
        row = None
    base = str(odict(row).get('base') or '')
    dcs = [x.split('=', 1)[1] for x in re.split(r'\s*,\s*', base) if x.lower().startswith('dc=')]
    return '.'.join(dcs).upper()


def keytab_entries(raw):
    """What a keytab holds, without its keys: [{principal, kvno, enctype, kind, weak}]."""
    raw = bytes(raw or b'')
    if len(raw) < 2 or raw[0] != 5 or raw[1] not in (1, 2):
        raise ValueError('that is not a keytab (it starts 0x05 0x02)')
    if raw[1] == 1:
        raise ValueError('a keytab of the first format is not read - make it again with ktpass or ktutil')
    out, i = [], 2

    def take(n):
        nonlocal i
        if i + n > end:
            raise ValueError('the keytab ends in the middle of an entry')
        b = raw[i:i + n]
        i += n
        return b
    while i + 4 <= len(raw):
        size = struct.unpack('>i', raw[i:i + 4])[0]
        i += 4
        if size == 0:
            break
        if size < 0:
            i += -size                      # a hole left by a key taken away
            continue
        end = i + size
        if end > len(raw):
            raise ValueError('the keytab ends in the middle of an entry')
        count = struct.unpack('>H', take(2))[0]
        rl = struct.unpack('>H', take(2))[0]
        realm = take(rl).decode('utf-8', 'replace')
        comps = []
        for _ in range(count):
            cl = struct.unpack('>H', take(2))[0]
            comps.append(take(cl).decode('utf-8', 'replace'))
        take(4)                             # name type
        stamp = struct.unpack('>I', take(4))[0]
        kvno = take(1)[0]
        enc = struct.unpack('>H', take(2))[0]
        kl = struct.unpack('>H', take(2))[0]
        take(kl)                            # the key itself: never kept, never shown
        if end - i >= 4:
            kv32 = struct.unpack('>I', raw[i:i + 4])[0]
            if kv32:
                kvno = kv32
        i = end
        out.append({'principal': '%s@%s' % ('/'.join(comps), realm), 'kvno': kvno, 'enctype': enc,
                    'kind': KRB_ENCTYPES.get(enc, 'type %d' % enc), 'weak': enc in KRB_WEAK,
                    'at': stamp})
    if not out:
        raise ValueError('the keytab holds no key')
    return out


def krb_keytab_raw(store):
    """The keytab as kept in the database, or None."""
    v = store.get_meta(KRB_META)
    if not v:
        return None
    try:
        got = json_obj(v) or {}
        data = unseal_secret(got.get('data') or '', bind=KRB_META)
        return base64.b64decode(data) if data else None
    except (ValueError, TypeError):
        return None


def krb_keytab_put(store, raw, by):
    """A keytab uploaded: checked, sealed into the database; each node writes it out."""
    raw = bytes(raw or b'')
    if not raw:
        raise ValueError('the file is empty')
    if len(raw) > KRB_KEYTAB_MAX:
        raise ValueError('that is larger than any keytab of a web service (64 kB)')
    ents = keytab_entries(raw)
    good = [e for e in ents if not e['weak']]
    if not good:
        raise ValueError('every key in it is of a weak kind (DES, RC4) - make it with '
                         '-crypto AES256-SHA1 (ktpass) and allow AES for the account')
    http = [e for e in ents if e['principal'].upper().startswith('HTTP/')]
    if not http:
        raise ValueError('it holds no key of a web service (HTTP/name@REALM) - the browser asks '
                         'for HTTP/<the name it opened>')
    sha = hashlib.sha256(raw).hexdigest()
    store.set_meta(KRB_META, json.dumps({
        'data': seal_secret(base64.b64encode(raw).decode('ascii'), bind=KRB_META),
        'sha': sha, 'at': time.time(), 'by': str(by or '')[:190],
        'principals': sorted({e['principal'] for e in ents})}))
    store.add_event('settings', '%s put in a keytab for signing in with Kerberos: %s' % (
        by, ', '.join(sorted({e['principal'] for e in http}))[:600]), 'warn', who=by)
    return ents


def krb_keytab_drop(store, by):
    store.drop_meta(KRB_META)
    store.add_event('settings', '%s took the keytab of Kerberos away' % by, 'warn', who=by)


def _krb_write(raw):
    KRB_DIR.mkdir(mode=0o700, exist_ok=True)
    KRB_RCACHE.mkdir(mode=0o700, exist_ok=True)
    tmp = KRB_DIR / ('.http.keytab.%d' % os.getpid())
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(KRB_KEYTAB))


def krb_tick(store):
    """Each node: the keytab in the database written out (or taken away), and what this node
    can do said in meta kerberos:node:NAME."""
    v = store.get_meta(KRB_META)
    if v is not None and v == KRB_NODE.get('v') and KRB_KEYTAB.exists() and not KRB_NODE.get('err') \
            and time.time() - KRB_NODE['at'] < 600:
        return                              # nothing new since the last look
    if v is None and KRB_NODE.get('v') is None and not KRB_KEYTAB.exists() and KRB_NODE['said'] \
            and time.time() - KRB_NODE['at'] < 600:
        return
    KRB_NODE['v'] = v
    raw = krb_keytab_raw(store)
    sha = hashlib.sha256(raw).hexdigest() if raw else ''
    err = ''
    try:
        if raw:
            have = KRB_KEYTAB.read_bytes() if KRB_KEYTAB.exists() else b''
            if hashlib.sha256(have).hexdigest() != sha:
                _krb_write(raw)
                log('the keytab of Kerberos was written (%d key(s))' % len(keytab_entries(raw)))
        elif KRB_KEYTAB.exists():
            KRB_KEYTAB.unlink()
            log('the keytab of Kerberos was taken away')
    except (OSError, ValueError) as e:
        err = 'the keytab could not be written: %s' % e
    if v and not raw and not err:
        err = 'the keytab in the database does not open with this node\'s key (secrets.key)'
    lib = krb_lib()
    said = {'at': int(time.time()), 'sha': sha[:16], 'file': KRB_KEYTAB.exists(),
            'lib': lib is not None, 'lib_err': KRB_LIB['err'] if lib is None else '',
            'err': err, 'version': __version__}
    same = {k: v for k, v in said.items() if k != 'at'}
    if KRB_NODE['said'] != same or time.time() - KRB_NODE['at'] > 600:
        store.set_meta('kerberos:node:' + node_name(), json.dumps(said))
        KRB_NODE.update(said=same, at=time.time())
    KRB_NODE['err'] = err


def krb_names(store):
    """The names the browser may open the pages by - each needs HTTP/<name> in the keytab."""
    names = []
    try:
        if CONFIG.get('ha_mode') == 'replicated':
            v = acme_name_of(store, 'vip')
            if v:
                names.append(('vip', v.lower()))
    except Exception:                                   # noqa: BLE001
        pass
    for n in host_nodes(store):
        try:
            f = acme_name_of(store, n)
        except Exception:                               # noqa: BLE001
            f = ''
        if f:
            names.append((n, f.lower()))
    seen, out = set(), []
    for who, f in names:
        if f not in seen:
            seen.add(f)
            out.append({'for': who, 'name': f})
    return out


def krb_view(store):
    raw = krb_keytab_raw(store)
    meta = json_obj(store.get_meta(KRB_META)) or {}
    ents = []
    if raw:
        try:
            ents = keytab_entries(raw)
        except ValueError:
            ents = []
    have = {e['principal'].split('@', 1)[0].lower() for e in ents}
    names = krb_names(store)
    for n in names:
        n['in_keytab'] = ('http/' + n['name']) in have
    nodes = []
    alive = host_alive(store)
    for n in host_nodes(store):
        got = json_obj(store.get_meta('kerberos:node:' + n)) or {}
        nodes.append({'name': n, 'alive': alive.get(n, False), 'at': got.get('at'),
                      'file': bool(got.get('file')), 'lib': got.get('lib'),
                      'lib_err': got.get('lib_err') or '', 'err': got.get('err') or '',
                      'same': bool(meta.get('sha')) and str(meta.get('sha', ''))[:16] == got.get('sha'),
                      'version': got.get('version') or ''})
    return {'on': bool(CONFIG.get('admin_kerberos')), 'auto': bool(CONFIG.get('admin_kerberos_auto')),
            'directory': CONFIG.get('admin_directory') or '',
            'realm': krb_realm_wanted(store), 'realm_set': str(CONFIG.get('admin_kerberos_realm') or ''),
            'mfa': bool(CONFIG.get('admin_2fa')), 'password_off': admin_password_off_now(),
            'keytab': {'there': bool(raw), 'at': meta.get('at'), 'by': meta.get('by') or '',
                       'sha': str(meta.get('sha') or '')[:16],
                       'entries': [{k: e[k] for k in ('principal', 'kvno', 'kind', 'weak')} for e in ents]},
            'names': names, 'nodes': nodes, 'ntlm': False}


def krb_problems(store):
    """What stands in the way, for the card and for alerts: [] when it is ready."""
    if not CONFIG.get('admin_kerberos'):
        return []
    out = []
    if not CONFIG.get('admin_directory'):
        out.append('no directory is set for administrators (Sign administrators in against the directory)')
    if krb_lib() is None:
        out.append(KRB_LIB['err'])
    if not krb_keytab_raw(store):
        out.append('no keytab is put in')
    if KRB_NODE.get('err'):
        out.append(KRB_NODE['err'])
    if not krb_realm_wanted(store):
        out.append('the realm is not known - set it (Kerberos realm)')
    return out
