# t_certport.py VERSION - 1.0.276: the certificate sign-in's port against every other port, both ways:
# the balancer's own port set to it after (refused, said as the balancer's), the certificate's set to the
# balancer's (refused), 80/443, the API's and RADIUS's, another node's API port, something listening
# already; off: nothing asked. The functions of otp.py itself, run on the configuration given.
import socket, sys, types
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.276'
src = open('/home/claude/build/out/otp-%s/otp.py' % V).read()
g = {'__name__': 'otp_t', '__file__': '/home/claude/build/out/otp-%s/otp.py' % V}
exec(compile(src, 'otp.py', 'exec'), g)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


P = g['cert_port_problem']
base = dict(g['DEFAULTS'])
ok('off: nothing asked, whatever the port', P({'admin_cert_port': 443}, conf=base) == '')
on = dict(base, admin_cert=1)
ok('on, 8443, nothing else there: taken', P({'admin_cert': 1}, conf=base) == '')
w = P({'web_proxy_port': 8443}, conf=on)
ok('the balancer\'s port set to the certificate\'s after: refused, said as the balancer\'s', w.startswith('web_proxy_port: 8443 is the certificate') and '9443' in w, w)
w = P({'admin_cert': 1}, conf=dict(base, web_proxy_port=8443))
ok('switched on over the balancer\'s 8443: refused, another one said (9443)', w.startswith('admin_cert_port: 8443') and 'balancer' in w and '9443' in w, w)
w = P({'admin_cert_port': 9443}, conf=dict(on, web_proxy_port=9443))
ok('the certificate\'s set to the balancer\'s 9443: refused, 8443 said', w.startswith('admin_cert_port: 9443') and '8443, say' in w, w)
ok('both in one save, the same: refused', P({'admin_cert_port': 9000, 'web_proxy_port': 9000}, conf=on) != '')
ok('both in one save, apart: taken', P({'admin_cert_port': 9000, 'web_proxy_port': 9443}, conf=on) == '')
for port in (80, 443):
    ok('%d refused' % port, 'pages' in P({'admin_cert_port': port}, conf=on))
ok('the API\'s port refused', 'API' in P({'admin_cert_port': int(base['api_port'])}, conf=on))
ok('RADIUS\'s port refused', 'RADIUS' in P({'admin_cert_port': 1812}, conf=on))
ok('the API moved onto it refused', P({'api_port': 8443}, conf=on) != '')
w = P({'admin_cert': 1}, conf=base, others={'otp2': {'api_port': 8443}})
ok('another node\'s API port refused, the node named', 'otp2' in w, w)
s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(64); busy = s.getsockname()[1]
w = P({'admin_cert': 1, 'admin_cert_port': busy}, conf=base, probe=True)
ok('something listening there already: refused', 'listens on %d already' % busy in w, w)
ok('...not tried without probe (another node\'s save)', P({'admin_cert': 1, 'admin_cert_port': busy}, conf=base) == '')
ok('...nor when it is on there already (otp\'s own nginx)', P({'admin_cert_map': 'strong', 'admin_cert': 1}, conf=dict(on, admin_cert_port=busy), probe=True) == '')
import os, tempfile
d = tempfile.mkdtemp(prefix='t-certport-')
os.environ['OTP_VIP_NGINX_DIR'] = d
open(d + '/otp_certlogin.conf', 'w').write('server {\n    listen 192.0.2.10:%d ssl;\n    listen [::]:%d ssl;\n}\n' % (busy, busy))
ok('...nor when what listens is otp\'s own certificate server (just switched off, not yet taken away)',
   P({'admin_cert': 1, 'admin_cert_port': busy}, conf=base, probe=True) == '')
open(d + '/otp_certlogin.conf', 'w').write('server {\n    listen %d1 ssl;\n}\n' % busy)
ok('...a server of another port is not ours', 'already' in P({'admin_cert': 1, 'admin_cert_port': busy}, conf=base, probe=True))
os.unlink(d + '/otp_certlogin.conf'); os.rmdir(d)
s.close()
w = g['web_proxy_port_problem']({'web_proxy_port': 9443}, conf=on)
ok('the balancer\'s own check unchanged (9443 with the certificate on 8443: taken)', w == '', w)
print('ALL %d / %d' % (sum(R), len(R)))
