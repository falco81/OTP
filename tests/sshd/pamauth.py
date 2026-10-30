# pamauth.py SERVICE USER - a PAM sign-in as sshd makes it: the answers to every
# prompt read from stdin, one a line, given back in memory PAM frees itself
# (pamtester and pam_radius 2.0 freed one twice). Exit 0 when let in; the
# prompts and the result on stdout.
import sys
from ctypes import CDLL, CFUNCTYPE, POINTER, Structure, byref, c_char_p, c_int, c_void_p, cast, sizeof
from ctypes.util import find_library

pam = CDLL(find_library('pam'))
libc = CDLL(find_library('c'))
libc.calloc.restype = c_void_p
libc.strdup.restype = c_void_p
libc.strdup.argtypes = [c_char_p]


class Msg(Structure):
    _fields_ = [('msg_style', c_int), ('msg', c_char_p)]


class Resp(Structure):
    _fields_ = [('resp', c_void_p), ('resp_retcode', c_int)]


CONV = CFUNCTYPE(c_int, c_int, POINTER(POINTER(Msg)), POINTER(POINTER(Resp)), c_void_p)


class Conv(Structure):
    _fields_ = [('conv', CONV), ('appdata_ptr', c_void_p)]


answers = [l.rstrip('\n') for l in sys.stdin]


def conv(n, msgs, resp, _data):
    addr = libc.calloc(n, sizeof(Resp))
    resp[0] = cast(addr, POINTER(Resp))
    for i in range(n):
        m = msgs[i].contents
        print('prompt %d: %s' % (m.msg_style, (m.msg or b'').decode('utf-8', 'replace').strip()), flush=True)
        if m.msg_style in (1, 2):           # PAM_PROMPT_ECHO_OFF / ON
            a = answers.pop(0) if answers else ''
            resp[0][i].resp = libc.strdup(a.encode())
    return 0


h = c_void_p()
cv = Conv(CONV(conv), None)
pam.pam_start.argtypes = [c_char_p, c_char_p, POINTER(Conv), POINTER(c_void_p)]
r = pam.pam_start(sys.argv[1].encode(), sys.argv[2].encode(), byref(cv), byref(h))
if r:
    print('pam_start: %d' % r)
    sys.exit(2)
r = pam.pam_authenticate(h, 0)
pam.pam_strerror.restype = c_char_p
print('result: %d %s' % (r, pam.pam_strerror(h, r).decode()), flush=True)
pam.pam_end(h, r)
sys.exit(0 if r == 0 else 1)
