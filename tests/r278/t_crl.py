# t_crl.py VERSION - 1.0.278: the CRLs of the sign-in with a certificate, as the crl-revocation-kit says
# (acme 1.0.104): the kit's test PKI (crl-pki.sh) served on 127.0.0.1, otp.py's own functions run on it.
#   alice OK; bob revoked (base CRL); carol run out (before any CRL); dave's CDP dead (no sign-in);
#   erin revoked in the DELTA only; frank of an authority its root revoked; the cache's rules; Fetch now
#   and Clear on a node; the facts a node publishes (never a CRL); the rows of the card; the guards of
#   where a CRL is fetched from.
import http.server, os, socket, socketserver, subprocess, sys, tempfile, threading, time
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.278'
OTP_PY = os.environ.get('OTP_PY') or '/home/claude/build/out/otp-%s/otp.py' % V
HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


PORT = free_port()
while True:                                 # PORT+1 must be free too (dave's dead CDP)
    t = socket.socket()
    try:
        t.bind(('127.0.0.1', PORT + 1)); t.close(); break
    except OSError:
        t.close(); PORT = free_port()
D = tempfile.mkdtemp(prefix='t-crl-')
subprocess.run(['bash', HERE + '/crl-pki.sh', D, str(PORT)], check=True, capture_output=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=D + '/www', **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == '/redirect.crl':
            self.send_response(302); self.send_header('Location', 'http://169.254.169.254/'); self.end_headers(); return
        if self.path == '/big.crl':
            self.send_response(200); self.send_header('Content-Length', str(9 << 20)); self.end_headers(); return
        return super().do_GET()


srv = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

src = open(OTP_PY).read()
g = {'__name__': 'otp_t', '__file__': OTP_PY}
exec(compile(src, 'otp.py', 'exec'), g)
import pathlib
CAS = {'file': D + '/cas.pem'}


def split(path):
    return g['cert_split_pems'](open(path, 'rb').read()) if 'cert_split_pems' in g else []


g['cert_cas'] = lambda store: [x.strip() + '\n-----END CERTIFICATE-----\n' for x in open(CAS['file']).read().split('-----END CERTIFICATE-----') if 'BEGIN' in x]
C = g['CONFIG']
C['admin_cert_crl'] = 1
os.environ['OTP_CDP_LOCAL'] = '1'


def check(name, cas='cas.pem'):
    CAS['file'] = D + '/' + cas
    g['CERT_CA_FILE'] = pathlib.Path(CAS['file'])
    try:
        g['cert_check'](None, open(D + '/%s.pem' % name).read())
        return 'OK', ''
    except g['CrlRefused'] as e:
        return 'unavailable', str(e)
    except g['CertError'] as e:
        return 'refused', str(e)


k, w = check('alice')
ok('alice (good): taken', k == 'OK', w)
k, w = check('bob-revoked')
ok('bob (revoked in the base CRL): refused, "revoked"', k == 'refused' and 'revoked' in w, w)
k, w = check('carol-old')
ok('carol (run out): refused for it - before any CRL', k == 'refused' and 'expired' in w, w)
k, w = check('dave-nocdp')
ok('dave (his CDP does not answer): no CRL, no sign-in', k == 'unavailable' and 'could not be had' in w, w)
k, w = check('erin-delta')
ok('erin (revoked in the DELTA CRL only): refused, "revoked"', k == 'refused' and 'revoked' in w, w)
k, w = check('frank-sub', 'cas-sub.pem')
ok('frank (his authority revoked by the root): refused, an authority above it', k == 'refused' and 'authority above' in w, w)
k, w = check('alice', 'cas-sub.pem')
ok('alice with the old authority among those put in too: still taken', k == 'OK', w)

# the facts a node publishes: never a CRL
now = g['crls_now']()
urls = {c['url'] for c in now}
base = 'http://127.0.0.1:%d/' % PORT
ok('kept here: the base CRL, its delta, the root\'s CRL (of the issuing authority), the old authority\'s',
   {base + 'issuing.crl', base + 'issuing-delta.crl', base + 'root.crl', base + 'sub.crl'} <= urls, sorted(urls))
ok('...facts and dates only, never a CRL', all('pem' not in c and 'BEGIN' not in str(c) for c in now))
one = next(c for c in now if c['url'] == base + 'issuing.crl')
ok('...its issuer, number, this/next update, size, revoked count, signature checked',
   'Corp Issuing CA' in one.get('issuer', '') and one.get('number') and one.get('this') and one.get('next') > time.time()
   and one.get('size') and one.get('revoked') == 1 and one.get('sig') == 'ok', one)
ok('...the delta CRL said to be one', next(c for c in now if c['url'] == base + 'issuing-delta.crl').get('delta') is True)
dead = next((c for c in now if 'nowhere.crl' in c['url']), {})
ok('...the dead CDP: not had, with its error', dead and not dead['ok'] and dead['err'], dead)

# the rows of the card
g['host_nodes'] = lambda store: ['vm']
g['node_name'] = lambda: 'vm'
g['CERT_NODE']['at'] = time.time()
g['json_obj'] = lambda v, kind=dict: None
CAS['file'] = D + '/cas.pem'
class St:
    def get_meta(self, k):
        return None
rows = g['crl_view_rows'](St())
r = {x['url']: x for x in rows}
ok('the card: a row for each CRL kept', base + 'issuing.crl' in r and r[base + 'issuing.crl']['ok'] and r[base + 'issuing.crl']['fetched'])
ok('...the root\'s CRL named by the issuing authority', r.get(base + 'root.crl', {}).get('named') and
   any('Corp Issuing CA' in x for x in r[base + 'root.crl']['of']))
ok('...each node\'s fetch in it', r[base + 'issuing.crl']['nodes'] and r[base + 'issuing.crl']['nodes'][0]['node'] == 'vm')

# the cache: the last good one kept while the address does not answer
U = base + 'issuing.crl'
os.rename(D + '/www/issuing.crl', D + '/www/issuing.crl.away')
with g['CRL_LOCK']:
    g['CRL_CACHE'][U]['at'] -= 700          # older than ten minutes
k, w = check('alice')
ok('the CDP gone, the CRL older than ten minutes: the last good one kept until its next update - taken', k == 'OK', w)
ok('...its error said', g['CRL_CACHE'][U].get('err'))
with g['CRL_LOCK']:
    g['CRL_CACHE'][U]['next'] = time.time() - 1   # past its next update
    g['CRL_CACHE'][U]['tried'] = 0
k, w = check('alice')
ok('...past its next update: none - no sign-in', k == 'unavailable', w)
os.rename(D + '/www/issuing.crl.away', D + '/www/issuing.crl')

# Fetch now / Clear on this node
said = []
g['cert_tick'] = lambda store, now_too=False: said.append(now_too)
got = g['crl_do'](None, 'fetch', U)
ok('Fetch now (one): fetched, its number said', got and got[0]['ok'] and got[0]['number'], got)
ok('...this node\'s state written at once', said and said[-1] is True)
got = g['crl_do'](None, 'fetch', '')
ok('Fetch now (every one): the dead one said, the others fetched', any(not x['ok'] and 'nowhere' in x['url'] for x in got)
   and any(x['ok'] and x['url'] == U for x in got), got)
got = g['crl_do'](None, 'clear', U)
ok('Clear (one): forgotten', [x['url'] for x in got] == [U] and U not in {c['url'] for c in g['crls_now']()})
got = g['crl_do'](None, 'clear', '')
ok('Clear (all): nothing kept', got and not g['crls_now']())
k, w = check('alice')
ok('...the next sign-in fetches them again', k == 'OK' and U in {c['url'] for c in g['crls_now']()}, w)

# where a CRL is fetched from
os.environ.pop('OTP_CDP_LOCAL')
cdp_ok = g['cdp_ok']
for u in ('https://pki/x.crl', 'ldap://pki/x', 'http://u:p@pki/x.crl', 'http://169.254.169.254/', 'http://[::ffff:169.254.169.254]/',
          'http://metadata.google.internal/', 'http://0.0.0.0/', 'http://224.0.0.1/', 'http://127.0.0.1/', 'http://100.100.100.200/'):
    ok('not fetched from %s' % u, not cdp_ok(u))
for u in ('http://10.1.2.3/x.crl', 'http://192.168.1.1/x.crl', 'http://[fd12::1]/x.crl', 'http://pki.corp.example/x.crl'):
    ok('fetched from %s' % u, cdp_ok(u))
for u in ('http://2852039166/x.crl', 'http://0251.0376.0251.0376/x.crl', 'http://127.1:%d/root.crl' % PORT):
    try:
        g['crl_http_get'](u); refused = False
    except ValueError:
        refused = True
    ok('refused when fetched: %s (as the resolver reads it)' % u, refused)
os.environ['OTP_CDP_LOCAL'] = '1'
for path, word in (('redirect.crl', 'redirect'), ('big.crl', 'larger')):
    try:
        g['crl_http_get'](base + path); why = ''
    except ValueError as e:
        why = str(e)
    ok('%s: refused (%s)' % (path, word), word in why, why)
ok('never through the proxy: the CRL is fetched by http.client to the address checked',
   'url_open' not in g['crl_http_get'].__code__.co_names)
srv.shutdown()
print('ALL %d / %d' % (sum(R), len(R)))
