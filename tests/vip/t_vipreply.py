# t_vipreply.py VERSION - RADIUS answered from the address it was asked on (1.0.223). Listening on
# every address, the answer went out from the address the kernel chose for the way back - the node's
# own, not the VIP address the VPN had asked - and most VPNs throw such an answer away. In one process
# (a socket on 0.0.0.0, asked on 10.99.0.3 from 127.0.0.1) and on the sandbox's node a (RADIUS on
# 0.0.0.0, asked on each of its addresses).
import os, sys, socket, time, secrets
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.223'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:300]) if more and not cond else ''), flush=True)


ADDRS = ['127.0.0.1', '10.99.0.1', '10.99.0.2', '10.99.0.3']
# ---- in one process -----------------------------------------------------------------------
srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
srv.bind(('0.0.0.0', 0))
port = srv.getsockname()[1]
otp.radius_pktinfo_on(srv, socket.AF_INET, '0.0.0.0')
srv.settimeout(2)
for a in ADDRS[1:]:
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c.bind(('127.0.0.1', 0))
    c.settimeout(2)
    c.sendto(b'hello', (a, port))
    data, via, peer = otp.radius_recv(srv)
    via.sendto(b'back', peer)
    got, src = c.recvfrom(100)
    ok('asked on %s from 127.0.0.1: answered from %s' % (a, src[0]), src[0] == a)
    c.close()
try:
    socket.socket(socket.AF_INET6, socket.SOCK_DGRAM).close()
    V6 = True
except OSError:
    V6 = False
    print('(no IPv6 on this machine: the dual-stack check skipped)')
if V6:
    srv6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    srv6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    srv6.bind(('::', 0))
    p6 = srv6.getsockname()[1]
    otp.radius_pktinfo_on(srv6, socket.AF_INET6, '::')
    srv6.settimeout(2)
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c.bind(('127.0.0.1', 0)); c.settimeout(2)
    c.sendto(b'hello', ('10.99.0.3', p6))
    data, via, peer = otp.radius_recv(srv6)
    via.sendto(b'back', peer)
    got, src = c.recvfrom(100)
    ok('listening on :: (both families), asked on 10.99.0.3: answered from %s' % src[0], src[0] == '10.99.0.3')
    c.close()
    srv6.close()
srv.close()
plain = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
plain.bind(('127.0.0.1', 0)); plain.settimeout(2)
otp.radius_pktinfo_on(plain, socket.AF_INET, '127.0.0.1')
c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); c.settimeout(2)
c.sendto(b'x', plain.getsockname())
data, via, peer = otp.radius_recv(plain)
ok('listening on one address: as before (the socket itself)', via is plain)
c.close(); plain.close()

# ---- the sandbox's node a: RADIUS on 0.0.0.0 ----------------------------------------------
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
try:
    import halib
    host, nport = halib.where('a')
except Exception as e:                                  # noqa: BLE001
    host = None
    print('no sandbox:', e)
if host:
    secret_b = str(halib.SECRET).encode()
    for a in ADDRS:
        ident = secrets.randbelow(256)
        pairs = [otp.attr_bytes('User-Name', 'nobody-vip'), bytes([4, 6]) + socket.inet_aton('127.0.0.1')]
        data, auth = otp.build_request(otp.ACCESS_REQUEST, ident, pairs, secret_b, password='000000')
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.bind(('127.0.0.1', 0)); c.settimeout(4)
        c.sendto(data, (a, nport))
        try:
            got, src = c.recvfrom(4096)
            fine = otp.reply_ok(got, auth, secret_b)
        except socket.timeout:
            got, src, fine = b'', ('-',), False
        ok('node a asked on %s: a signed answer from %s' % (a, src[0]), fine and src[0] == a)
        c.close()
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
