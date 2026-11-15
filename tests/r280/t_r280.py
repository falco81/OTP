# t_r280.py VERSION - 1.0.280 (hunt rounds 1-3): the functions of otp.py itself, on what they are given.
# - the RADIUS queue: a lone line may take nine tenths, the line of addresses that are no client half at
#   most, an address no client's never a line of its own (read from the clients in memory only);
# - ACME's answers on port 80 only while ACME is on (the reach probe's own aside), its rows signed;
# - guard.json says which version wrote it: back from a downgrade, a newer version's rows taken in again;
# - the certificate's port looked for on this node's own addresses (not the VIP held by the other node);
# - root's SSH keys only shown: the installed server's API refuses to make, put on or take away one.
import json, os, sys, tempfile, pathlib, ipaddress, time, ssl, urllib.request, http.cookiejar
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.280'
OTP_PY = os.environ.get('OTP_PY') or '/home/claude/build/out/otp-%s/otp.py' % V
src = open(OTP_PY).read()
g = {'__name__': 'otp_t', '__file__': OTP_PY}
exec(compile(src, 'otp.py', 'exec'), g)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


Q = g['RadiusQueue']
Full = g['queue'].Full


def fill(q, key, most=100000):
    n = 0
    try:
        while n < most:
            q.put_nowait(n, key=key)
            n += 1
    except Full:
        pass
    return n


q = Q(1000)
ok('a lone line (one NAS, a burst): nine tenths of the queue', fill(q, 'nas1') == 900, q.qsize())
ok('...the tenth kept for another', fill(q, 'nas2') == 100)
q = Q(1000)
ok('the line of the addresses that are no client: half at most, even alone', fill(q, '*') == 500)
ok('...a client still gets the rest', fill(q, 'nas1') == 500)
q = Q(1000)
fill(q, 'nas2', 10)
ok('a line while another waits: half at most (as before)', fill(q, 'nas1') == 500)


class St(object):
    _clients = None


class D(object):
    store = St()


srv = g['RadiusServer'].__new__(g['RadiusServer'])
srv.d = D()
ok('the clients not read yet: every address a line of its own, as before', srv.fair_known('198.51.100.9'))
D.store._clients = [{'_net': ipaddress.ip_network('10.0.0.0/24'), 'enabled': 1}, {'_net': None}]
ok('an address of a client (from memory): a line of its own', srv.fair_known('10.0.0.7'))
ok('an address of no client: the shared line', not srv.fair_known('198.51.100.9'))
ok('...an IPv6 address of no client', not srv.fair_known('2001:db8::1'))
calls = []
D.store.client_for = lambda ip: calls.append(ip)
srv.fair_known('10.0.0.7')
ok('...the database never asked (the reading thread)', not calls)

# ACME
C = g['CONFIG']
meta = {}


class MS(object):
    def get_meta(self, k):
        return meta.get(k)


ms = MS()
tok = 'A' * 43
meta['acme:chal:' + tok] = json.dumps({'auth': tok + '.x', 'at': time.time()})
C['acme'] = 0
ok('ACME off: a challenge row is not answered (put in by somebody, no certificate asked for)', g['acme_challenge'](ms, tok) is None)
C['acme'] = 1
ok('ACME on: answered', g['acme_challenge'](ms, tok) == tok + '.x')
C['acme'] = 0
pt = 'otp-probe-' + 'b' * 22
meta['acme:chal:' + pt] = json.dumps({'auth': pt + '.y', 'at': time.time(), 'probe': True})
ok('ACME off: the reach probe\'s own row answered', g['acme_challenge'](ms, pt) == pt + '.y')
meta['acme:chal:' + pt] = json.dumps({'auth': pt + '.y', 'at': time.time()})
ok('...a row of a probe\'s name not written by the probe: not', g['acme_challenge'](ms, pt) is None)
ok('the challenge rows are signed rows', 'acme:chal:' in g['DBGUARD_META_PREFIXES'] and 'acme:before:' in g['DBGUARD_META_PREFIXES'])
ok('...rows of a version before taken in once', 'acme:chal:' in g['DBGUARD_SINCE']['1.0.280'].get('meta_prefixes', ()))
ok('...Windows tried by itself signed too', 'admin_kerberos_auto' in g['DBGUARD_SETTINGS'])

# guard.json: which version wrote it
d = tempfile.mkdtemp(prefix='t-r280-')
G = g['DBGUARD']


def load(data):
    p = pathlib.Path(d) / 'guard.json'
    p.write_text(json.dumps(data))
    g['DBGUARD_FILE'] = p
    G['seen'] = None
    g['_dbguard_load']()
    return G['adopted']


got = load({'adopted': ['1.0.248', '1.0.255', '1.0.280', 'tokens']})
ok('written by a version before 1.0.280 (a downgrade): 1.0.280\'s rows taken in again, the rest kept',
   '1.0.280' not in got and '1.0.255' in got and 'tokens' in got, got)
got = load({'adopted': ['1.0.255', '1.0.280'], 'by': g['__version__']})
ok('written by this version: as it was', '1.0.280' in got, got)
G['seen'] = {}; G['good'] = {}; G['seen_h'] = {}; G['dirty'] = 1.0; G['had_file'] = True
g['dbguard_flush'](force=True)
ok('...the version written down at each flush', json.loads(g['DBGUARD_FILE'].read_text()).get('by') == g['__version__'])

# the certificate's port: this node's own addresses
own = g['_cert_own_address']
ok('127.0.0.1 is this node\'s', own('127.0.0.1'))
ok('an address of another machine (the VIP the other node holds) is not', not own('192.0.2.77'))
open(d + '/otp_certlogin.conf', 'w').write('server {\n  listen 192.0.2.77:8443 ssl;\n  listen 127.0.0.1:8443 ssl;\n}\n')
os.environ['OTP_VIP_NGINX_DIR'] = d
h = g['cert_listen_hosts'](8443)
ok('the listen lines: only this node\'s own looked at', h == ['127.0.0.1'], h)
open(d + '/otp_certlogin.conf', 'w').write('server {\n  listen 192.0.2.77:8443 ssl;\n}\n')
ok('...none of its own: 127.0.0.1', g['cert_listen_hosts'](8443) == ['127.0.0.1'])
os.environ.pop('OTP_VIP_NGINX_DIR')

# root's SSH keys only shown - asked of the installed server's API, as the pages ask
for k in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
    os.environ.pop(k, None)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(jar),
                                 urllib.request.ProxyHandler({}))
BASE = 'https://127.0.0.1/admin/'


def api(what, body=None):
    rq = urllib.request.Request(BASE + '?api=' + what, data=json.dumps(body).encode() if body is not None else None,
                                headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'})
    try:
        r = op.open(rq, timeout=30)
        return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


PW = open('/home/claude/run/adminpw').read().strip()
st, _ = api('login', {'name': 'admin', 'password': PW})
ok('signed in as the full administrator', st == 200, st)
line = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl t280@test'
for act, body in (('add', {'line': line}), ('drop', {'fp': 'SHA256:x'}), ('rk_make', {'kind': 'ed25519'}),
                  ('rk_given', {'key': line}), ('rk_again', {})):
    b = dict(body, action=act, user='root')
    st, x = api('sshkeys', b)
    ok('root: %s refused - root\'s keys are only shown' % act, st == 403 and 'only shown' in str(x), (st, x))
st, x = api('sshkeys', {'action': 'add', 'line': line})
ok('...no user named is root: refused too', st == 403, (st, x))
st, x = api('sshkeys', {'action': 'refresh', 'user': 'root'})
ok('...read again: taken', st == 200, (st, x))
st, x = api('sshkeys')
ok('...and shown', st == 200 and 'nodes' in x, st)
print('ALL %d / %d' % (sum(R), len(R)))
