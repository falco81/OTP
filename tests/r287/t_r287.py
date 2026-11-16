# t_r287.py VERSION - 1.0.287: what the three rounds of the bug hunt fixed, where it can be tried here.
# In otp.py itself (a state folder of its own): networks with a mask or a prefix taken, an IPv6 scope id
# refused (the settings that become firewall rules and nginx lines); log_sparing by the monotonic clock (its
# first line written); write_replacing whole; a reply measured with the request's Proxy-State; RADIUS on '::'
# - an IPv4 client by its ::ffff: address in its own line; the card's check key; config.json's signature
# taken from what was read; set_account refusing a row the guard does not know and root's --passwd signing it
# again. On the installed server: the same settings through the pages; the certificate's port refusing a POST
# and a multipart body.
import os, sys, json, time, tempfile, subprocess, ipaddress, urllib.request, ssl, http.cookiejar
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.287'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok   ' if cond else 'FAIL ') + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''), flush=True)


D = tempfile.mkdtemp(prefix='otp-r287-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r287'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)

# networks: a prefix, a mask, no scope id
ok('plain_net: 192.0.2.0/24 and 10.0.0.0/255.0.0.0 taken', str(otp.plain_net('192.0.2.0/24')) == '192.0.2.0/24' and
   str(otp.plain_net('10.0.0.0/255.0.0.0')) == '10.0.0.0/8')
for bad in ('fe80::1%eth0', 'fe80::1%eth0/64', '10.0.0.1\n}', ''):
    try:
        otp.plain_net(bad)
        took = True
    except ValueError:
        took = False
    ok('plain_net: %r refused' % bad, not took)
for key in ('web_proxy_from', 'portal_sso_from', 'snmp_from', 'metrics_from', 'radius_guard_trusted'):
    try:
        otp.check_setting(key, '10.0.0.0/8, fe80::1%ens192')
        took = True
    except otp.BadSetting:
        took = False
    ok('%s: an address with a scope id refused' % key, not took)
    try:
        otp.check_setting(key, '10.0.0.0/255.0.0.0, 192.0.2.7')
        took = True
    except otp.BadSetting as e:
        took = str(e)
    ok('%s: a mask and an address taken' % key, took is True, took)

# log_sparing: the first line written, by the monotonic clock
said = []
real = otp.log
otp.log = lambda words, level='info': said.append(words)
try:
    otp._LOG_SPARING.clear()
    otp.log_sparing('r287-test', 'first one', every=30)
    otp.log_sparing('r287-test', 'second one', every=30)
finally:
    otp.log = real
ok('log_sparing: the first line written, the next one within the time kept back', said[:1] and 'first one' in said[0] and len(said) == 1, said)
ok('...by the monotonic clock', isinstance(otp._LOG_SPARING['r287-test'][0], float) and otp._LOG_SPARING['r287-test'][0] <= time.monotonic())

# write_replacing: whole, its mode
p = os.path.join(D, 'w.json')
otp.write_replacing(p, '{"a": 1}\n', 0o600)
ok('write_replacing: the file whole, mode 0600', open(p).read() == '{"a": 1}\n' and (os.stat(p).st_mode & 0o777) == 0o600)

# config.json's signature: what load_config read
import hashlib
ok('load_config: the signature of the bytes it read', otp.CONFIG_READ_SIG[0] == hashlib.sha256(open(D + '/config.json', 'rb').read()).hexdigest())

# a reply measured with the request's Proxy-State
pairs = [('Reply-Message', 'x' * 240)] * 16
otp.RADIUS_PROXY_STATE.size = 0
base = otp.reply_too_long(pairs)
otp.RADIUS_PROXY_STATE.size = 300
big = otp.reply_too_long(pairs)
otp.RADIUS_PROXY_STATE.size = 0
ok('reply_too_long: the request\'s Proxy-State counted (%s / %s)' % (bool(base), bool(big)), not base and big, (base, big))

# RADIUS on '::': an IPv4 client by its ::ffff: address
class _S(object):
    _clients = [{'_net': ipaddress.ip_network('192.0.2.0/24')}]


class _D(object):
    store = _S()
srv = otp.RadiusServer.__new__(otp.RadiusServer)
srv.d = _D()
ok('fair_known: ::ffff:192.0.2.10 is the client 192.0.2.0/24', srv.fair_known('::ffff:192.0.2.10') and srv.fair_known('192.0.2.10')
   and not srv.fair_known('::ffff:198.51.100.1'))

# the card's check key
k1, k2 = otp.card_key('token-a'), otp.card_key('token-b')
ok('card_key: 32 hex, one for each sign-in', len(k1) == 32 and k1 != k2 and k1 == otp.card_key('token-a'))
print('...the unit checks done')

# ---- on the installed server ----
PW = open('/home/claude/run/adminpw').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(jar))


def call(what, body=None, url=None, headers=None, method=None):
    h = {'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'}
    h.update(headers or {})
    data = None
    if body is not None:
        h.setdefault('Content-Type', 'application/json')
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url or ('https://127.0.0.1/admin/?api=' + what), data=data, headers=h, method=method)
    try:
        with op.open(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, got = call('login', {'name': 'admin', 'password': PW})
ok('the administrator signs in', st == 200, got[:200])
st, got = call('settings', {'settings': {'snmp_from': 'fe80::1%ens192'}})
ok('the pages: SNMP only from with a scope id refused (400)', st == 400, (st, got[:200]))
st, got = call('settings', {'settings': {'snmp_from': '10.0.0.0/255.0.0.0'}})
ok('...a network with its mask taken', st == 200, (st, got[:200]))
call('settings', {'settings': {'snmp_from': ''}})
st, got = call('settings', {'settings': {'web_proxy_from': 'fe80::1%eth0'}})
ok('the pages: the balancers\' addresses with a scope id refused (400)', st == 400, (st, got[:200]))

# the certificate's port: GET only, no multipart
# (without this test's own state folder: root's helper and otp would look there)
CLEAN = {k: v for k, v in os.environ.items() if not k.startswith('OTP_')}
_up = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cert', 'ui_cert_setup.py'), 'up'],
                     capture_output=True, text=True, env=CLEAN)
print(_up.stdout.strip(), _up.stderr.strip()[-300:])
conf = open('/etc/nginx/conf.d/otp_certlogin.conf').read() if os.path.exists('/etc/nginx/conf.d/otp_certlogin.conf') else ''
ok('nginx on the certificate\'s port: GET and HEAD only, no multipart, a small body', 'if ($request_method !~ ^(GET|HEAD)$) { return 405; }' in conf and
   'if ($http_content_type ~* "multipart") { return 403; }' in conf and 'client_max_body_size 16k;' in conf, conf[:300])
st, got = call('', b'x=1', url='https://127.0.0.1:8443/admin/?api=cert-login', headers={'Content-Type': 'application/x-www-form-urlencoded'})
ok('...a POST to it: 405', st == 405, st)
st, got = call('', None, url='https://127.0.0.1:8443/admin/?api=cert-login', headers={'Content-Type': 'multipart/form-data; boundary=x'}, method='GET')
ok('...a multipart body: 403', st == 403, st)
print(subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cert', 'ui_cert_setup.py'), 'down'],
                     capture_output=True, text=True, env=CLEAN).stdout.strip())
print('ALL %d / %d' % (sum(R), len(R)))
