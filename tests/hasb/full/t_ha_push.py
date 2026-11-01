# t_ha_push.py VERSION [ACME_DIR] - acme push (1.0.216) on the replicated pair: acme (its real target
# acme_push) talks to node a only, as the PHP page hands each request on (POST /api/acme-push/<op>,
# {"body": base64, "headers": {...}}); one certificate for the cluster - both nodes' names and the
# VIP address's - put into every slot. Node b takes its own by replication, and each node's root
# helper puts it in the files nginx reads. A request replayed to node b is refused there too.
import os, sys, json, time, base64, hashlib, subprocess, tempfile, glob, urllib.parse  # noqa: E401
from halib import *  # noqa: F401,F403
import halib

ACME_DIR = sys.argv[2] if len(sys.argv) > 2 else '/home/user/falco81/acme'
T = tempfile.mkdtemp(prefix='acme-ha-push-')
open(T + '/config.json', 'w').write('{"node_name": "acme1", "upgrade_check": 0}')
os.environ.update(ACME_CONFIG=T + '/config.json', ACME_STATE=T, ACME_RUN=T, ACME_LOGDIR=T,
                  ACME_PLUGINS=T + '/plugins')
sys.path.insert(0, ACME_DIR)
_argv = sys.argv
sys.argv = ['x']
import acme  # noqa: E402,F401
import acmelib.engine as A  # noqa: E402
from acmelib.certs import runtime, store as CS  # noqa: E402
from acmelib.plugins import base  # noqa: E402
sys.argv = _argv
AST = A.Storage(A.open_db())
A.sealing_key(make=True)
A.CONFIG['certs_precheck'] = 0
CS.registry()
ok, call, login, in_node, dbq = halib.ok, halib.call, halib.login, halib.in_node, halib.dbq
S = halib.S
SENT = []


class Relay(object):
    """What otp's admin/index.php does: the body as base64 and the five headers, to the daemon."""
    def __init__(self, node):
        self.node = node

    def __call__(self, method, url, body=None, headers=None, **kw):
        op = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)['api'][0][len('acme-push-'):]
        if op == 'hello':
            st, got = call(self.node, '/api/acme-push/hello', None, sess=False)
        else:
            hd = {k[len('X-Acme-Push-'):]: v for k, v in (headers or {}).items()
                  if k.startswith('X-Acme-Push-')}
            payload = {'body': base64.b64encode(body or b'').decode(), 'headers': hd}
            SENT.append((op, payload))
            st, got = call(self.node, '/api/acme-push/' + op, payload, sess=False)
        return st, {'Content-Type': 'application/json'}, json.dumps(got).encode()


for _n in 'ab':
    halib.up(_n)
    login(_n)
# The VIP address with its name, as the sandbox has it (t_ha_auth saves it without one): a VIP
# address with a certificate of its own and no name stops every node's nginx files (an upload's too).
st, got = call('a', '/api/web', {'action': 'vip_save', 'address': halib.VIP + '/24', 'vrid': 61,
                                 'fqdn': 'vip.otp.test'})
ok('the VIP address named vip.otp.test', st == 200, got)
time.sleep(5)
st, got = call('a', '/api/acme-push', {'action': 'on'})
ok('switched on on node a', st == 200, got)
st, got = call('a', '/api/acme-push', {'action': 'pair'})
code = got.get('code') or ''
ok('a pairing code made on node a (%s)' % ('XXXX-' * 3 + 'XXXX' if code else '-'), len(code) == 19, got)

cls = CS.plugin_class('target', 'acme_push')
ctx = runtime.RunContext(AST, None, scope='target:otp-ha')
ctx.http = Relay('a')
t = cls({'url': 'https://otp.example.test/admin/', 'pair_code': code, 'verify_tls': False}, ctx)
t._sleep = lambda s: None
said = t.test()
ok('acme\'s Try against node a: paired (%s)' % said.replace('\n', ' | ')[:160], 'pairing code' in said or
   'paired' in said, said)
inv = t.inventory()
ids = [s['id'] for s in inv['slots']]
names = sorted({n for s in inv['slots'] for n in s['names']})
ok('the inventory says the whole cluster from node a: %s (%s)' % (ids, names),
   {'node:nodea', 'node:nodeb'} <= set(ids) and inv['cluster']['on'], inv)
# A slot with no name (the VIP address without one): nothing put there, said why.
nameless = [s_['id'] for s_ in inv['slots'] if not s_['names']]
ids = [s_['id'] for s_ in inv['slots'] if s_['names']]
time.sleep(2)
# node b: the same app_id and sealing key, by replication
hb = json.loads(dbq('b', "SELECT v FROM meta WHERE k = 'acme_push:box'") or '{}')
ha_ = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'acme_push:box'") or '{}')
ok('node b has the same id and sealing key (replicated)', hb.get('app_id') and hb.get('app_id') == ha_.get('app_id'))

# one certificate for the cluster: every slot's name, signed by a CA of the test's
sub = lambda *a: subprocess.run(list(a), capture_output=True, check=True)  # noqa: E731
sub('openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes',
    '-keyout', T + '/ca.key', '-out', T + '/ca.crt', '-days', '30', '-subj', '/CN=Push HA CA')
sub('openssl', 'req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes',
    '-keyout', T + '/c.key', '-out', T + '/c.csr', '-subj', '/CN=' + names[0])
open(T + '/c.ext', 'w').write('subjectAltName=' + ','.join('DNS:' + n for n in names) + '\n')
sub('openssl', 'x509', '-req', '-in', T + '/c.csr', '-CA', T + '/ca.crt', '-CAkey', T + '/ca.key',
    '-CAcreateserial', '-days', '20', '-out', T + '/c.crt', '-extfile', T + '/c.ext')


class B(base.Bundle):
    pass


b = B()
b.cert_pem, b.key_pem = open(T + '/c.crt').read(), open(T + '/c.key').read()
b.chain_pems = [open(T + '/ca.crt').read()]
b.fullchain_pem = b.cert_pem + b.chain_pems[0]
b.names, b.name = names, names[0]
b.fingerprint = hashlib.sha256(base64.b64decode(''.join(b.cert_pem.strip().splitlines()[1:-1]))).hexdigest()
b.not_after, b.serial, b.key_type, b.alt = time.time() + 20 * 86400, 'ha', 'ec-256', None
got = t.deploy(b, {'slots': ids, 'verify_served': False})
for nm in nameless:
    try:
        t.deploy(b, {'slots': [nm], 'verify_served': False})
        ok('%s has no name: refused' % nm, False)
    except base.PluginError as e:
        ok('%s has no name: refused, and said why (%s)' % (nm, str(e)[:90]), '(names)' in str(e) and 'no name' in str(e), e)
ok('one push to node a for every slot (%s)' % got.replace('\n', ' | ')[:200], all(i in got for i in ids), got)


def fps(n):
    out = {}
    for f in glob.glob('%s/%s/certs/*.pem' % (S, n)):
        if f.endswith('-ca.pem') or 'ecdsa' not in f and 'otp' not in os.path.basename(f):
            continue
        r = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-sha256', '-in', f],
                           capture_output=True, text=True).stdout
        if '=' in r:
            out[os.path.basename(f)] = r.split('=', 1)[1].strip().replace(':', '').lower()
    return out


want_files = {'a': None, 'b': None}
end = time.time() + 240
while time.time() < end:
    fa, fb = fps('a'), fps('b')
    if b.fingerprint in fa.values() and b.fingerprint in fb.values():
        break
    time.sleep(5)
fa, fb = fps('a'), fps('b')
ok('node a\'s root helper put it in the files nginx reads (%s)' % sorted(k for k, v in fa.items() if v == b.fingerprint),
   b.fingerprint in fa.values(), fa)
ok('node b - asked nothing - put it in too, from the replicated database (%s)'
   % sorted(k for k, v in fb.items() if v == b.fingerprint), b.fingerprint in fb.values(), fb)
prof_b = json.loads(dbq('b', "SELECT v FROM meta WHERE k = 'web:tls:nodeb'") or '{}')
ok('node b\'s own card: from acme push, the new certificate',
   str(prof_b.get('how') or '').startswith('acme push') and
   str((prof_b.get('info') or {}).get('fingerprint') or '').replace(':', '').lower() == b.fingerprint,
   {k: prof_b.get(k) for k in ('how',)})

# the last request, replayed to node b: its nonce came over by replication
time.sleep(2)
op, payload = SENT[-1]
st, out = call('b', '/api/acme-push/' + op, payload, sess=False)
ok('the same request replayed to node b: refused (%s %s)' % (st, out.get('code')), st == 401 and
   out.get('code') == 'replay', out)
# acme talking to node b now: the same certificate is already there
ctx.http = Relay('b')
got = t.deploy(b, {'slots': ids, 'verify_served': False})
ok('the same certificate pushed to node b: already there everywhere (%s)' % got.replace('\n', ' | ')[:120],
   'already' in got and 'put in' not in got, got)
if not os.environ.get('PUSH_LEAVE_ON'):
    st, got = call('a', '/api/acme-push', {'action': 'off'})
    ok('switched off again (what was put in stays)', st == 200, got)
halib.done()
