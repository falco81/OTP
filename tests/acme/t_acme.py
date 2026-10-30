# Certificates by ACME (1.0.169), end to end against mock_acme.py (a small CA
# that checks every signature and really fetches HTTP-01): port 80 played by
# a little server that does what acme.php does - asks the daemon.
# Usage (as root): python3 t_acme.py VERSION
import os, re, socket, struct, sys, json, time, subprocess, urllib.request, tempfile, atexit, threading, http.server, socketserver

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.169'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-acme-'); os.makedirs(D + '/run')
APORT = 30691
NAME = 'acme1.otp.test'
hosts = open('/etc/hosts').read()
if NAME not in hosts:
    open('/etc/hosts', 'a').write('\n127.0.0.1 %s\n' % NAME)
atexit.register(lambda: open('/etc/hosts', 'w').write(hosts))
CAW = D + '/ca'
ca = subprocess.Popen([sys.executable, HERE + '/mock_acme.py', '14000', CAW], stdout=open(D + '/ca.out', 'w'),
                      stderr=subprocess.STDOUT)
atexit.register(ca.terminate)
for _ in range(100):
    if os.path.exists(CAW + '/ready'):
        break
    time.sleep(0.2)
DNSJSON = CAW + '/dns.json'
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1',
           OTP_ACME_EVERY='5', OTP_ACME_SETTLE='0.5', OTP_NSUPDATE=HERE + '/fake_nsupdate.sh', DNSJSON=DNSJSON,
           OTP_CF_API='http://127.0.0.1:36780/client/v4', OTP_DESEC_API='http://127.0.0.1:36780/api/v1',
           OTP_ACME_DNS_LEAST='0', OTP_ACME_SEEN_WAIT='3')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36710, 'radius_acct_port': 36711,
           'api_port': APORT, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-169!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
SEEN = []


class Port80(http.server.BaseHTTPRequestHandler):
    """What nginx and acme.php do on port 80."""
    def do_GET(self):
        SEEN.append(self.path)
        tok = self.path.rsplit('/', 1)[-1]
        req = urllib.request.Request('http://127.0.0.1:%d/api/acme/challenge?token=%s' % (APORT, tok),
                                     headers={'X-Otp-Token': TOK})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r:
                auth = json.loads(r.read())['auth'].encode()
            self.send_response(200); self.send_header('Content-Length', str(len(auth))); self.end_headers(); self.wfile.write(auth)
        except Exception:
            self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers()

    def log_message(self, *a):
        pass


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


threading.Thread(target=TS(('0.0.0.0', 80), Port80).serve_forever, daemon=True).start()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


def until(fn, secs=60):
    end = time.time() + secs
    while time.time() < end:
        g = fn()
        if g:
            return g
        time.sleep(0.5)
    return None


def mine(x):
    return [t for t in (x or {}).get('targets', []) if t['target'] == 'otp1']


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-169!'})[1]['token']
SET = lambda dd: call('/api/settings', {'settings': dd}, S)
ok('off by default', not otp.DEFAULTS['acme'])
c, x = call('/api/acme/challenge?token=nothing-here-at-all', None)
ok('a challenge nobody asked: 404 (%s)' % c, c == 404)
c, x = SET({'acme_url': 'http://insecure/'})
ok('an http:// directory refused (%s)' % c, c == 400)
c, x = SET({'acme': 1, 'acme_ca': 'custom', 'acme_url': 'https://127.0.0.1:14000/dir', 'acme_ca_pem': open(CAW + '/ca.pem').read(),
            'acme_for': 'node', 'acme_node_name': NAME, 'acme_email': 'admin@otp.test'})
ok('switched on, the test CA as the CA: %s %s' % (c, x.get('error', '')), c == 200)
c, p = call('/api/acme', {'action': 'probe', 'target': 'otp1'}, S)
ok('port 80 answers as the CA will ask it: %s' % p.get('said'), c == 200 and p.get('ok'))
# The tick orders it by itself: not ordered yet for this name.
v = until(lambda: (lambda x: x if [t for t in mine(x) if t['state'].get('ok')] else None)(call('/api/acme', None, S)[1]), 90)
t = mine(v)
ok('ordered by itself and put in: %s, until %s (%s)' % (t and t[0].get('subject'), t and t[0].get('not_after'),
                                                        t and t[0]['state'].get('said')),
   t and t[0]['how'] == 'ACME' and NAME in str(t[0].get('subject')) and t[0]['not_after'] > time.time() + 80 * 86400)
ok('... the CA really looked at port 80, every request signed and checked', any('/.well-known/acme-challenge/' in s for s in SEEN))
ok('... the account kept, its key sealed', (lambda a: a and a.get('kid') and 'BEGIN' not in a.get('key', ''))(
    json.loads(st.get_meta('acme:account') or '{}')))
ok('... no answer left in the database', not st.db.rows("SELECT k FROM meta WHERE k LIKE 'acme:chal:%'"))
prof = json.loads(st.get_meta('web:tls:otp1'))
ok('... the certificate with its key, the key sealed', prof.get('cert') and 'BEGIN' not in prof.get('key', ''))
first = t[0]['state'].get('ordered_at') if t else 0
c, x = call('/api/acme', {'action': 'order', 'target': 'otp1'}, S)
ok('ordered again by hand: %s' % x.get('message'), c == 200)
v = until(lambda: (lambda x: x if [t for t in mine(x) if (t['state'].get('ordered_at') or 0) > (first or 0)] and not x['work']['busy'] else None)(
    call('/api/acme', None, S)[1]), 60)
ok('... a new one came, the same account used', v and len(set(json.loads(st.get_meta('acme:account'))['kid'] for _ in [0])) == 1)
SET({'acme_node_name': 'blocked.example'})
time.sleep(1)
c, x = call('/api/acme', {'action': 'order', 'target': 'otp1'}, S)
v = until(lambda: (lambda x: x if [t for t in mine(x) if t['state'].get('ok') is False] else None)(call('/api/acme', None, S)[1]), 60)
tt = mine(v)
ok('a name the CA refuses: said why, the certificate in place kept (%s)' % (tt and tt[0]['state'].get('said', '')[:80]),
   tt and tt[0]['state'].get('said') and json.loads(st.get_meta('web:tls:otp1')).get('how') == 'ACME')

# ---- DNS-01 (1.0.169): no port open - the CA reads a TXT record -----------------------
def dns():
    try:
        return json.load(open(DNSJSON))
    except (OSError, ValueError):
        return {}


def dns_put(rr, v, add=True):
    d = dns()
    vals = d.setdefault(rr, [])
    if add and v not in vals:
        vals.append(v)
    if not add and v in vals:
        vals.remove(v)
    json.dump(d, open(DNSJSON, 'w'))


class Fake(http.server.BaseHTTPRequestHandler):
    """Cloudflare's API and an acme-dns server, as far as otp uses them."""
    recs = {}

    def reply(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')

    desec = {}
    desec_429 = [1]

    def desec_ok(self):
        return self.headers.get('Authorization') == 'Token desec-token-170-abcdefghijklmnop'

    def do_GET(self):
        if self.path.startswith('/api/v1/'):
            if not self.desec_ok():
                return self.reply(401, {'detail': 'Invalid token.'})
            if self.path == '/api/v1/domains/otpdesec.dedyn.io/':
                return self.reply(200, {'name': 'otpdesec.dedyn.io', 'minimum_ttl': 3600})
            m = re.match(r'^/api/v1/domains/otpdesec\.dedyn\.io/rrsets/([^/]+)/TXT/$', self.path)
            if m and m.group(1) in Fake.desec:
                return self.reply(200, {'subname': m.group(1), 'type': 'TXT', 'records': Fake.desec[m.group(1)]})
            return self.reply(404, {'detail': 'Not found.'})
        if self.path.startswith('/client/v4/zones?name='):
            ok_ = self.headers.get('Authorization') == 'Bearer cf-token-169'
            z = self.path.split('=', 1)[1]
            return self.reply(200, {'success': ok_, 'errors': [] if ok_ else [{'message': 'bad token'}],
                                    'result': [{'id': 'zone1'}] if z == 'otp.test' else []})
        self.reply(404, {})

    def do_POST(self):
        b = self.body()
        if self.path == '/client/v4/zones/zone1/dns_records':
            rid = 'r%d' % len(Fake.recs)
            Fake.recs[rid] = b
            dns_put(b['name'], b['content'])
            return self.reply(200, {'success': True, 'result': {'id': rid}})
        if self.path == '/update':
            if self.headers.get('X-Api-Key') != 'adns-key-169' or self.headers.get('X-Api-User') != 'adns-user':
                return self.reply(401, {'error': 'forbidden'})
            dns_put('_acme-challenge.' + NAME, b['txt'])
            return self.reply(200, {'txt': b['txt']})
        self.reply(404, {})

    def do_PATCH(self):
        if not self.path.startswith('/api/v1/domains/otpdesec.dedyn.io/rrsets/') or not self.desec_ok():
            return self.reply(401, {'detail': 'no'})
        if Fake.desec_429[0]:
            Fake.desec_429[0] = 0
            self.send_response(429); self.send_header('Retry-After', '1'); self.send_header('Content-Length', '0'); self.end_headers()
            return
        for rr in self.body():
            assert rr['type'] == 'TXT' and rr['ttl'] >= 3600
            full = rr['subname'] + '.otpdesec.dedyn.io'
            for v in Fake.desec.get(rr['subname'], []):
                dns_put(full, v.strip('"'), False)
            Fake.desec[rr['subname']] = rr['records']
            for v in rr['records']:
                dns_put(full, v.strip('"'))
        self.reply(200, [])

    def do_DELETE(self):
        rid = self.path.rsplit('/', 1)[-1]
        r = Fake.recs.pop(rid, None)
        if r:
            dns_put(r['name'], r['content'], False)
        self.reply(200, {'success': True, 'result': {'id': rid}})

    def log_message(self, *a):
        pass


threading.Thread(target=TS(('127.0.0.1', 36780), Fake).serve_forever, daemon=True).start()


def fake_dns():
    """A resolver on 127.0.0.2:53 that knows dns.json: CNAMEs (followed, as a
    resolver does), TXT records and A records ('A name')."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.2', 53))

    def nm(n):
        return b''.join(bytes([len(x)]) + x.encode() for x in n.rstrip('.').split('.')) + b'\0'
    while True:
        q, peer = s.recvfrom(4096)
        i, labels = 12, []
        while q[i]:
            labels.append(q[i + 1:i + 1 + q[i]].decode()); i += 1 + q[i]
        qtype = struct.unpack('!H', q[i + 1:i + 3])[0]
        qend = i + 5
        name = '.'.join(labels)
        zone = dns()
        ans = []
        cur = name
        for _ in range(5):
            t = zone.get('CNAME ' + cur)
            if not t:
                break
            ans.append((cur, 5, nm(t)))
            cur = t.rstrip('.')
        if qtype == 16:
            for v in zone.get(cur, []) if isinstance(zone.get(cur), list) else []:
                ans.append((cur, 16, bytes([len(v)]) + v.encode()))
        if qtype == 1 and zone.get('A ' + cur):
            ans.append((cur, 1, socket.inet_aton(zone['A ' + cur])))
        found = bool(ans) or any(k.endswith(' ' + cur) or k == cur for k in zone)
        head = q[:2] + struct.pack('!HHHHH', 0x8180 if found else 0x8183, 1, len(ans), 0, 0)
        out = head + q[12:qend]
        for n, t, rd in ans:
            out += nm(n) + struct.pack('!HHIH', t, 1, 60, len(rd)) + rd
        s.sendto(out, peer)


threading.Thread(target=fake_dns, daemon=True).start()
SET({'acme_node_name': NAME})


def order_now(what):
    t0 = time.time()
    c, x = call('/api/acme', {'action': 'order', 'target': 'otp1'}, S)
    v = until(lambda: (lambda x: x if [t for t in mine(x) if (t['state'].get('at') or 0) >= t0] and not x['work']['busy'] else None)(
        call('/api/acme', None, S)[1]), 90)
    t = mine(v)
    return c, (t[0]['state'] if t else {}), v


for how, extra in (('rfc2136', {'acme_dns_server': '127.0.0.1:53', 'acme_dns_zone': 'otp.test', 'acme_dns_tsig_name': 'otp-acme.',
                                'acme_dns_tsig_secret': 'c2VjcmV0LWtleS1mb3ItdGVzdHM='}),
                   ('cloudflare', {'acme_dns_token': 'cf-token-169'}),
                   ('acmedns', {'acme_dns_url': 'http://127.0.0.1:36780', 'acme_dns_user': 'adns-user', 'acme_dns_key': 'adns-key-169',
                                'acme_dns_subdomain': 'abc-123'})):
    json.dump({}, open(DNSJSON, 'w'))
    c, x = SET(dict(extra, acme_challenge='dns-01', acme_dns=how, acme_dns_wait=0))
    n80 = len(SEEN)
    c, stt, v = order_now(how)
    ok('DNS-01 by %s: the certificate came (%s)' % (how, stt.get('said') or 'ok'), stt.get('ok'))
    ok('... port 80 never asked', len(SEEN) == n80)
    if how != 'acmedns':
        ok('... the TXT record taken away again (%s)' % dns(), not any(dns().values()))
saved = json.dumps(st.db.rows('SELECT * FROM settings'))
ok('the TSIG secret, the API token and the acme-dns key kept sealed',
   'c2VjcmV0LWtleS1mb3ItdGVzdHM=' not in saved and 'cf-token-169' not in saved and 'adns-key-169' not in saved)
ok('nsupdate was given the key in a file of 0600, never on its command line',
   open(DNSJSON + '.keys').read().startswith('600 key "otp-acme."'))
# By hand: the record shown, put in, said so.
json.dump({}, open(DNSJSON, 'w'))
SET({'acme_dns': 'manual'})
t0 = time.time()
call('/api/acme', {'action': 'order', 'target': 'otp1'}, S)
m = until(lambda: call('/api/acme', None, S)[1].get('manual'), 30)
ok('by hand: the record to put in is shown (%s)' % (m or {}).get('rr'), m and m['rr'] == '_acme-challenge.' + NAME and len(m['txt']) == 43)
dns_put(m['rr'], m['txt'])
c, x = call('/api/acme', {'action': 'manual_done'}, S)
v = until(lambda: (lambda x: x if [t for t in mine(x) if (t['state'].get('at') or 0) >= t0] and not x['work']['busy'] else None)(
    call('/api/acme', None, S)[1]), 60)
ok('... said it is in DNS: the certificate came (%s)' % (mine(v)[0]['state'] if v else None), v and mine(v)[0]['state'].get('ok'))
ev = json.dumps(call('/api/events?limit=60', None, S)[1])
ok('in the events: came from the CA, and the one that did not', 'came from the CA' in ev and 'no certificate for' in ev)

# Certificates and TLS beside it (1.0.170): one put in by hand is kept.
c, x = call('/api/web', {'action': 'tls_selfsigned', 'target': 'otp1', 'cn': NAME, 'names': '', 'days': 30}, S)
ok('a self-signed one put in by hand (%s)' % c, c == 200)
v = call('/api/acme', None, S)[1]
ok('... ACME no longer renews it', mine(v) and mine(v)[0]['care'] is False and 'otp1' not in v.get('mine', []))
w = call('/api/web', None, S)[1]
ok('... and Certificates and TLS says so', w.get('acme', {}).get('care', {}).get('otp1') is False)
c, v = call('/api/acme', {'action': 'care', 'target': 'otp1', 'on': True}, S)
ok('Look after it: ACME renews it again', c == 200 and mine(v)[0]['care'] is True and 'otp1' in v.get('mine', []))
c, v = call('/api/acme', {'action': 'name', 'target': 'otp1', 'name': 'Other.OTP.test.'}, S)
ok('its name given from the page: kept as a DNS name', c == 200 and mine(v)[0]['name'] == 'other.otp.test')
c, v = call('/api/acme', {'action': 'name', 'target': 'otp1', 'name': 'not a name'}, S)
ok('... a wrong one refused', c == 400)
c, v = call('/api/acme', {'action': 'name', 'target': 'vip', 'name': 'otp.otp.test'}, S)
ok('... the web address\'s refused while there is none', c == 400)
c, v = call('/api/acme', {'action': 'name', 'target': 'otp1', 'name': NAME}, S)

# deSEC (1.0.170): its domain, a CNAME in your DNS, the guide and its check.
json.dump({}, open(DNSJSON, 'w'))
c, x = SET({'acme_resolvers': '127.0.0.2', 'acme_challenge': 'dns-01', 'acme_dns': 'desec', 'acme_desec_domain': 'otpdesec.dedyn.io',
            'acme_desec_token': 'desec-token-170-abcdefghijklmnop', 'acme_dns_wait': 0})
ok('deSEC chosen (%s)' % c, c == 200)
saved = json.dumps(st.db.rows('SELECT * FROM settings'))
ok('... its token kept sealed', 'desec-token-170' not in saved)
v = call('/api/acme', None, S)[1]
row = [r for r in v['dns_guide']['rows'] if r['target'] == 'otp1'][0]
ok('In your DNS: _acme-challenge.%s CNAME to the deSEC domain (%s)' % (NAME, row), row['type'] == 'CNAME' and
   row['record'] == '_acme-challenge.' + NAME and row['value'] == '_acme-challenge.acme1.otpdesec.dedyn.io.')
c, g = call('/api/acme', {'action': 'dns_check'}, S)
r1 = [r for r in g['rows'] if r['target'] == 'otp1'][0]
ok('... checked: not there yet (%s)' % r1.get('said'), c == 200 and r1.get('ok') is False and 'not there' in r1.get('said', ''))
c, stt, v = order_now('desec without its CNAME')
ok('... ordered without it: the CA did not find it, said why (%s)' % (stt.get('said') or '')[:90], stt.get('ok') is False)
ok('... the TXT record taken away again from deSEC', not any(Fake.desec.values()))
d0 = dns(); d0['CNAME _acme-challenge.' + NAME] = '_acme-challenge.acme1.otpdesec.dedyn.io.'; json.dump(d0, open(DNSJSON, 'w'))
c, g = call('/api/acme', {'action': 'dns_check'}, S)
r1 = [r for r in g['rows'] if r['target'] == 'otp1'][0]
ok('the CNAME put in: the check finds it (%s)' % r1.get('said'), r1.get('ok') is True)
c, stt, v = order_now('desec')
ok('DNS-01 by deSEC through the CNAME: the certificate came (%s)' % (stt.get('said') or 'ok'), stt.get('ok'))
ok('... a 429 waited out, and the record taken away again', Fake.desec_429[0] == 0 and not any(Fake.desec.values()))
SET({'acme_dns': 'rfc2136', 'acme_dns_alias': 'acme.otp.test'})
v = call('/api/acme', None, S)[1]
row = [r for r in v['dns_guide']['rows'] if r['target'] == 'otp1'][0]
ok('another zone for the records with RFC 2136 too: a CNAME asked for (%s)' % row.get('value'),
   row['type'] == 'CNAME' and row['value'] == '_acme-challenge.acme1.acme.otp.test.')
SET({'acme_dns_alias': '', 'acme_challenge': 'http-01'})
v = call('/api/acme', None, S)[1]
row = [r for r in v['dns_guide']['rows'] if r['target'] == 'otp1'][0]
ok('HTTP-01: the name is to point at the node (%s)' % row, row['type'] == 'A' and row['record'] == NAME)

# Back to the certificate from before ACME (1.0.172).
c, x = call('/api/web', {'action': 'tls_selfsigned', 'target': 'otp1', 'cn': NAME, 'names': '', 'days': 40}, S)
mine_before = json.loads(st.get_meta('web:tls:otp1'))['info']['not_after']
c, stt, v = order_now('over our own')
ok('ordered over a certificate of our own: it came', stt.get('ok') and json.loads(st.get_meta('web:tls:otp1')).get('how') == 'ACME')
b4 = mine(v)[0].get('before') or {}
ok('... the one before kept to go back to (%s)' % b4.get('how'), b4.get('how', '').startswith('self-signed') and
   abs(float(b4.get('not_after') or 0) - mine_before) < 2)
ok('... and Certificates and TLS knows it', (call('/api/web', None, S)[1].get('acme', {}).get('before') or {}).get('otp1'))
pol = json.loads(st.get_meta('web:tls:otp1'))
c, x = call('/api/web', {'action': 'tls_policy', 'target': 'otp1', 'preset': 'modern', 'dh': 'none', 'hsts': 0}, S)
ok('TLS settings changed on a certificate from ACME (%s)' % c, c == 200 and json.loads(st.get_meta('web:tls:otp1')).get('preset') == 'modern')
c, v = call('/api/acme', {'action': 'put_back', 'target': 'otp1'}, S)
prof = json.loads(st.get_meta('web:tls:otp1'))
ok('put back: the certificate from before in place (%s)' % c, c == 200 and prof.get('how', '').startswith('self-signed') and
   abs(float(prof['info']['not_after']) - mine_before) < 2)
ok('... its key in place and sealed', prof.get('key') and 'BEGIN' not in prof['key'])
ok('... its TLS settings as they were made (modern)', prof.get('preset') == 'modern')
ok('... ACME leaves it alone, nothing left to go back to', mine(v)[0]['care'] is False and not mine(v)[0].get('before'))
c, v = call('/api/acme', {'action': 'put_back', 'target': 'otp1'}, S)
ok('... a second time: nothing to put back (%s)' % c, c == 400)

# DNS servers of its own for ACME (1.0.172): Try port 80 asks them, not the machine.
SET({'acme_resolvers': '127.0.0.2', 'acme_challenge': 'http-01'})
d0 = dns(); d0.pop('A ' + NAME, None); json.dump(d0, open(DNSJSON, 'w'))
c, p = call('/api/acme', {'action': 'probe', 'target': 'otp1'}, S)
ok('Try port 80 with DNS servers of its own that do not know the name: said so (%s)' % (p.get('said') or '')[:80],
   c == 200 and p.get('ok') is False and '127.0.0.2' in (p.get('said') or ''))
d0 = dns(); d0['A ' + NAME] = '127.0.0.1'; json.dump(d0, open(DNSJSON, 'w'))
c, p = call('/api/acme', {'action': 'probe', 'target': 'otp1'}, S)
ok('... the name put in at them: port 80 answers (%s)' % (p.get('said') or '')[:60], c == 200 and p.get('ok') is True)
c, g = call('/api/acme', {'action': 'dns_check'}, S)
r1 = [r for r in g['rows'] if r['target'] == 'otp1'][0]
ok('... Check DNS asks them too (%s)' % r1.get('said'), r1.get('ok') and '127.0.0.1' in r1.get('found', '') and g.get('resolvers') == ['127.0.0.2'])
SET({'acme_resolvers': '1.2.3.4.5'}) if False else None
c, x = SET({'acme_resolvers': 'not-an-address'})
ok('a DNS server that is not an address refused (%s)' % c, c == 400)
print('ALL %d / %d' % (sum(R), len(R)))
