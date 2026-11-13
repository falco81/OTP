# krbtok.py - a browser's "Authorization: Negotiate" token for HTTP@<host>, made with the system's
# GSS-API (as a browser on Linux does), from the ticket cache of one person of the test realm.
#   python3 krbtok.py KDC_DIR PERSON HOST [krb5]   -> base64 on stdout (SPNEGO; "krb5": bare Kerberos)
import base64, ctypes, ctypes.util, os, sys


class Buf(ctypes.Structure):
    _fields_ = [('length', ctypes.c_size_t), ('value', ctypes.c_void_p)]


class Oid(ctypes.Structure):
    _fields_ = [('length', ctypes.c_uint32), ('elements', ctypes.c_void_p)]


def _oid(raw):
    b = ctypes.create_string_buffer(raw, len(raw))
    o = Oid(len(raw), ctypes.cast(b, ctypes.c_void_p))
    o._keep = b
    return o


def token(kdc, person, host, mech='spnego'):
    os.environ['KRB5_CONFIG'] = kdc + '/krb5.conf'
    os.environ['KRB5CCNAME'] = 'FILE:%s/%s.cc' % (kdc, person)
    lib = ctypes.CDLL(ctypes.util.find_library('gssapi_krb5') or 'libgssapi_krb5.so.2')
    P, U, V = ctypes.POINTER, ctypes.c_uint32, ctypes.c_void_p
    lib.gss_import_name.argtypes = [P(U), P(Buf), P(Oid), P(V)]
    lib.gss_init_sec_context.argtypes = [P(U), V, P(V), V, P(Oid), U, U, V, P(Buf), P(P(Oid)), P(Buf), P(U), P(U)]
    m = U()
    nb = ('HTTP@' + host).encode()
    nbuf = Buf(len(nb), ctypes.cast(ctypes.c_char_p(nb), V))
    name = V()
    hb = _oid(bytes.fromhex('2a864886f71201020104'))
    if lib.gss_import_name(ctypes.byref(m), ctypes.byref(nbuf), ctypes.byref(hb), ctypes.byref(name)):
        raise SystemExit('import_name failed')
    mo = _oid(bytes.fromhex('2b0601050502' if mech == 'spnego' else '2a864886f712010202'))
    ctx, out = V(), Buf()
    r = lib.gss_init_sec_context(ctypes.byref(m), None, ctypes.byref(ctx), name, ctypes.byref(mo), 0, 0,
                                 None, None, None, ctypes.byref(out), None, None)
    if r not in (0, 1):
        raise SystemExit('init_sec_context: %#x/%d' % (r, m.value))
    return base64.b64encode(ctypes.string_at(out.value, out.length)).decode()


if __name__ == '__main__':
    print(token(sys.argv[1], sys.argv[2], sys.argv[3], 'krb5' if len(sys.argv) > 4 and sys.argv[4] == 'krb5' else 'spnego'))
