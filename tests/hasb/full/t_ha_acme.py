# t_ha_acme.py VERSION - certificates by ACME on a cluster of two (mock_acme.py, HTTP-01; port 80
# played by a small server that asks the node holding the name, as nginx and acme.php do): each
# node's own and the VIP address's, ordered by themselves; then, the CA giving 20 days, every one
# of them found running out and renewed by itself with 90 - each node's nginx files changed with
# it, the VIP address's on both nodes - while RADIUS (each node, the VIP address) answers all the time.
# Usage (root, after t_ha_auth.py on the same sandbox): python3 t_ha_acme.py VERSION
import os, sys, time, json, subprocess, threading, http.server, socketserver, urllib.request, glob, atexit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

HERE = '/home/claude/ws/tests/acme'
NAMES = {'nodea': 'nodea.otp.test', 'nodeb': 'nodeb.otp.test', 'vip': 'vip.otp.test'}
hosts = open('/etc/hosts').read()
add = ''.join('127.0.0.1 %s\n' % n for n in NAMES.values() if n not in hosts)
if add:
    open('/etc/hosts', 'a').write('\n' + add)
atexit.register(lambda: open('/etc/hosts', 'w').write(hosts))
CAW = S + '/ca'
subprocess.run(['rm', '-rf', CAW])
os.makedirs(CAW)
open(CAW + '/days', 'w').write('20')
CA = []


def ca_start():
    """The CA; started again on the same folder: the same CA, every account it had forgotten."""
    if CA:
        CA[0].terminate()
        CA[0].wait()
        CA.clear()
        os.unlink(CAW + '/ready')
    CA.append(subprocess.Popen([sys.executable, HERE + '/mock_acme.py', '14000', CAW], stdout=open(S + '/ca.out', 'a'),
                               stderr=subprocess.STDOUT, start_new_session=True))
    for _ in range(100):
        if os.path.exists(CAW + '/ready'):
            break
        time.sleep(0.2)


ca_start()
atexit.register(lambda: CA and CA[0].terminate())

SEEN = []  # the CA's questions on port 80


class Port80(http.server.BaseHTTPRequestHandler):
    """nginx and acme.php on port 80: the daemon of the node asked (any of them knows the
    question - it is in the database)."""
    def do_GET(self):
        SEEN.append(self.path)
        tok = self.path.rsplit('/', 1)[-1]
        for n in ('a', 'b'):
            req = urllib.request.Request('http://127.0.0.1:%d/api/acme/challenge?token=%s' % (PORT[n], tok),
                                         headers={'X-Otp-Token': TOK.get(n, '')})
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r:
                    auth = json.loads(r.read())['auth'].encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(auth)))
                self.end_headers()
                self.wfile.write(auth)
                return
            except Exception:                           # noqa: BLE001
                continue
        self.send_response(404)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *a):
        pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
srv = socketserver.ThreadingTCPServer(('0.0.0.0', 80), Port80)
threading.Thread(target=srv.serve_forever, daemon=True).start()

helpers_on()
for n in 'ab':
    stop(n)
    start(n)                     # with OTP_ACME_EVERY from env.sh
    login(n)
ka_on()
P = Prober()
T = json.loads(in_node('a', 'tk = otp.Tokens(st); print(json.dumps(tk.enroll("acmeuser", "test")))').strip().split('\n')[-1])
st_, got = call('a', '/api/settings', {'settings': {
    'acme': 1, 'acme_ca': 'custom', 'acme_url': 'https://127.0.0.1:14000/dir', 'acme_ca_pem': open(CAW + '/ca.pem').read(),
    'acme_email': 'admin@otp.test', 'acme_for': 'both', 'acme_challenge': 'http-01', 'acme_days': 30}})
ok('ACME on, for the nodes and the VIP address (%s)' % st_, st_ == 200, got)
for target, name in NAMES.items():
    st_, got = call('a', '/api/acme', {'action': 'name', 'target': target, 'name': name})
    ok('the name of %s: %s (%s)' % (target, name, st_), st_ == 200, got)


def certs():
    """{target: (its name, days left)} as the database keeps them."""
    out = in_node('a', '''
got = {}
for t in otp.tls_targets(st):
    i = (otp.tls_profile(st, t) or {}).get('info') or {}
    got[t] = [i.get('cn'), (float(i.get('not_after') or 0) - time.time()) / 86400]
print(json.dumps(got))''')
    return json.loads(out.strip().split('\n')[-1])


def files(n):
    """What nginx of node n would read: each certificate file's end."""
    got = {}
    for f in glob.glob('%s/%s/certs/*.crt' % (S, n)) + glob.glob('%s/%s/certs/*.pem' % (S, n)):
        if f.endswith('-ca.pem'):
            continue                # the CA's own, not one renewed
        e = subprocess.run(['openssl', 'x509', '-noout', '-enddate', '-subject', '-in', f], capture_output=True,
                           text=True).stdout
        if 'notAfter' in e:
            end = e.split('notAfter=')[1].split('\n')[0]
            t = time.mktime(time.strptime(end.replace(' GMT', ''), '%b %d %H:%M:%S %Y'))
            got[os.path.basename(f)] = [(t - time.time()) / 86400, e.split('subject=')[-1].strip()]
    return got


def wait_certs(cond, t=600):
    end = time.time() + t
    c = {}
    while time.time() < end:
        try:
            c = certs()
            if cond(c):
                return c
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(5)
    return c


# Left from a run before (from this CA, 90 days): ordered again by hand, from the CA giving 20 now.
for t, v in certs().items():
    if t in NAMES and v[0] == NAMES[t] and v[1] > 25:
        for _ in range(60):            # one order at a time: the one before done first
            if call('a', '/api/acme', {'action': 'order', 'target': t})[0] == 200:
                break
            time.sleep(2)
c = wait_certs(lambda c: all((c.get(t) or [None, 99])[0] == NAMES[t] and c[t][1] < 25 for t in NAMES))
ok('ordered by themselves: each node\'s and the VIP address\'s (%s)' % c,
   all((c.get(t) or [None])[0] == NAMES[t] for t in NAMES), c)
ok('... from the CA giving 20 days', all(0 < (c.get(t) or [0, 0])[1] < 25 for t in NAMES), c)
# Fewer days than acme_days (30), but not yet a third of its life: not ordered again and
# again (it was, every few seconds, until the CA's limits refused them all).
time.sleep(10)                  # the events of the orders above written first
n0 = int(dbq('a', "SELECT count(*) FROM events WHERE words LIKE 'a certificate for %came from the CA%'") or 0)
time.sleep(40)
n1 = int(dbq('a', "SELECT count(*) FROM events WHERE words LIKE 'a certificate for %came from the CA%'") or 0)
ok('a certificate of 20 days, acme_days 30: not ordered again and again (%d more in 40 s)' % (n1 - n0), n1 == n0)
# Eighteen days on: two left of its twenty - renewed by itself; the CA gives 90 now - and it
# has forgotten the account it knew (deleted, deactivated, started anew): a new one by itself.
for t in NAMES:
    prof = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'web:tls:%s'" % t) or '{}')
    prof['info']['not_before'] = time.time() - 18 * 86400
    prof['info']['not_after'] = time.time() + 2 * 86400
    dbq('a', "UPDATE meta SET v = '%s' WHERE k = 'web:tls:%s'" % (json.dumps(prof).replace("'", "''"), t))
ca_start()
open(CAW + '/days', 'w').write('90')
t0 = time.time()
c = wait_certs(lambda c: all((c.get(t) or [0, 0])[1] > 80 for t in NAMES), 900)
ok('running out (2 days left of 20): every one renewed by itself, 90 days now (%.0f s): %s' % (time.time() - t0, c),
   all((c.get(t) or [0, 0])[1] > 80 for t in NAMES), c)
time.sleep(30)
for n in 'ab':
    f = files(n)
    ok('%s: nginx has the renewed certificates (%s)' % (n, {k: round(v[0]) for k, v in f.items()}),
       f and all(v[0] > 80 for v in f.values()), f)
ok('the CA was asked over port 80 (%d)' % len(SEEN), SEEN)
gone = [l for l in open(S + '/a/log/otp.log').read().split('\n')[-3000:] + open(S + '/b/log/otp.log').read().split('\n')[-3000:]
        if 'does not know the account any more' in l]
ok('... the account it forgot: a new one made by itself (%d)' % len(gone), gone)
# ---- 1.0.196: both an RSA and an ECDSA certificate, a profile, the CA's renewal window ----
import ssl as _ssl, urllib.request as _ur


def asked():
    c = _ssl.create_default_context(cafile=CAW + '/ca.pem')
    with _ur.build_opener(_ur.HTTPSHandler(context=c), _ur.ProxyHandler({})).open('https://127.0.0.1:14000/asked', timeout=10) as r:
        return json.loads(r.read())


st_, got = call('a', '/api/settings', {'settings': {'acme_key': 'dual-strong', 'acme_account_key': 'ec384',
                                                    'acme_profile': 'shortlived'}})
ok('both certificates (RSA 4096 + ECDSA P-384), the account on P-384, the shortlived profile (%s)' % st_, st_ == 200, got)
n0 = len(asked()['orders'])
call('a', '/api/acme', {'action': 'order', 'target': 'nodea'})


def alt_of(t):
    out = in_node('a', 'p = otp.tls_profile(st, %r) or {}; a = p.get("alt") or {}; print(json.dumps([(p.get("info") or {}).get("key"), (a.get("info") or {}).get("key"), (float((p.get("info") or {}).get("not_after") or 0) - time.time()) / 86400]))' % t)
    return json.loads(out.strip().split('\n')[-1])


got = None
for _ in range(60):
    time.sleep(2)
    got = alt_of('nodea')
    if got[1] and 'RSA 4096' in str(got[0]).upper():
        break
ok('nodea: an RSA 4096 certificate and an ECDSA P-384 one beside it (%s)' % got,
   got and got[1] and 'RSA 4096' in str(got[0]).upper() and 'EC 384' in str(got[1]).upper(), got)
ok('... the account signs with ES384 (%s)' % asked()['algs'], 'ES384' in asked()['algs'])
acc = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'acme:account'") or '{}')
ok('... a new account for the new kind of key (%s)' % acc.get('kind'), acc.get('kind') == 'ec384')
ok('... from the shortlived profile: 6 days (%.1f)' % (got[2] if got else 0), got and 5 < got[2] < 7, got)
o = asked()['orders'][n0:]
ok('... the CA asked with the profile, and as the renewal of the one before (%s)' % o,
   o and all(x.get('profile') == 'shortlived' for x in o) and o[0].get('replaces'), o)
time.sleep(15)
conf = open('%s/a/nginx/otp.conf' % S).read()
ok('nginx of nodea: both certificates (RSA first)', conf.count('ssl_certificate ') == 2 and
   conf.index('otp.pem') < conf.index('otp-ecdsa.pem'), [l for l in conf.split('\n') if 'ssl_certificate' in l])
ok('... their files: the ECDSA one written', os.path.exists('%s/a/certs/otp-ecdsa.pem' % S) and
   'BEGIN' in open('%s/a/certs/otp-ecdsa.key' % S).read())
# The CA's renewal window (ARI), now: renewed by itself, though 6 days are left.
import datetime as _dt
now_ = _dt.datetime.utcnow()
open(CAW + '/ari', 'w').write(json.dumps({'suggestedWindow': {
    'start': (now_ - _dt.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'end': (now_ - _dt.timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')}}))
before = alt_of('nodea')
n1 = len(asked()['orders'])
renewed = False
for _ in range(60):
    time.sleep(3)
    if len(asked()['orders']) > n1 and asked()['ari']:
        renewed = True
        break
evs = dbq('a', "SELECT words FROM events WHERE words LIKE 'a certificate for nodea%%' ORDER BY id DESC LIMIT 1")
ok('the CA\'s renewal window come (ARI): renewed by itself (%s)' % evs, renewed, asked()['ari'][-2:])
os.unlink(CAW + '/ari')
# The account on RSA (RS256), and one key, ECDSA P-256: a certificate of that alone.
call('a', '/api/settings', {'settings': {'acme_key': 'ec', 'acme_account_key': 'rsa2048', 'acme_profile': ''}})
time.sleep(2)
call('a', '/api/acme', {'action': 'order', 'target': 'nodea'})
for _ in range(60):
    time.sleep(2)
    got = alt_of('nodea')
    if got and not got[1] and 'EC 256' in str(got[0]).upper():
        break
ok('one key, ECDSA P-256: that certificate alone, the second one gone (%s)' % got,
   got and not got[1] and 'EC 256' in str(got[0]).upper(), got)
ok('... the account signs with RS256 (%s)' % asked()['algs'], 'RS256' in asked()['algs'])
time.sleep(15)
conf = open('%s/a/nginx/otp.conf' % S).read()
ok('... nginx: one certificate again', conf.count('ssl_certificate ') == 1,
   [l for l in conf.split('\n') if 'ssl_certificate' in l])
call('a', '/api/settings', {'settings': {'acme_key': 'dual', 'acme_account_key': 'ec', 'acme_profile': ''}})
s0 = int(time.time()) // 30
while int(time.time()) // 30 == s0:
    time.sleep(0.5)
ok('a code through the VIP address: in', rad('vip', 'acmeuser', totp_of(T['secret']))[0] == 'accept')
P.stop_flag = True
time.sleep(1)
for t in ('a', 'b', 'vip'):
    ok('the prober: %s answered every time (%d asked, %d not)' % (t, P.asked[t], len(P.lost[t])), not P.lost[t])
call('a', '/api/settings', {'settings': {'acme': 0}})
srv.shutdown()
done()
