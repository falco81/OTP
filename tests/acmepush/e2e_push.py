#!/usr/bin/env python3
"""e2e_push.py CODE [URL] [ACME_DIR] - acme (its real target acme_push, over HTTPS) pushes to
the installed otp: Try (hello + pair + inventory), then a certificate for the node's name,
again (already), and one for another name (refused). Prints what it saw."""
import os, sys, json, subprocess, tempfile, hashlib, base64, time
CODE = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else 'https://127.0.0.1/admin/'
ACME_DIR = sys.argv[3] if len(sys.argv) > 3 else '/home/user/falco81/acme'
T = tempfile.mkdtemp(prefix='acme-e2e-')
open(T + '/config.json', 'w').write('{"node_name": "acme1", "upgrade_check": 0}')
os.environ.update(ACME_CONFIG=T + '/config.json', ACME_STATE=T, ACME_RUN=T, ACME_LOGDIR=T,
                  ACME_PLUGINS=T + '/plugins')
sys.path.insert(0, ACME_DIR)
import acme  # noqa
import acmelib.engine as A  # noqa
from acmelib.certs import runtime, store as S  # noqa
from acmelib.plugins import base  # noqa
st = A.Storage(A.open_db()); A.sealing_key(make=True); A.CONFIG['certs_precheck'] = 0; S.registry()
R = []
def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + ('' if c else ' (%s)' % str(more)[:500]), flush=True)
def sh(*a):
    return subprocess.run(list(a), capture_output=True, check=True).stdout
cls = S.plugin_class('target', 'acme_push')
ctx = runtime.RunContext(st, None, scope='target:otp')
t = cls({'url': URL, 'pair_code': CODE, 'verify_tls': False}, ctx)
t._sleep = lambda s: None
said = t.test()
ok('Try over HTTPS: hello, pair with the code, inventory (%s)' % said.replace('\n', ' | ')[:200], 'node:' in said, said)
inv = t.inventory()
slot = inv['slots'][0]
ok('inventory: app otp, the node\'s slot %s for %s, now %s' % (slot['id'], slot['names'], slot['managed_by']),
   inv.get('app') == 'otp' and slot['id'].startswith('node:') and slot['names'], inv)
name = slot['names'][0]
def make(cn, kind='ec'):
    k = ['-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256'] if kind == 'ec' else ['-newkey', 'rsa:2048']
    sh('openssl', 'req', '-x509', *k, '-nodes', '-keyout', T + '/%s.key' % cn, '-out', T + '/%s.crt' % cn,
       '-days', '20', '-subj', '/CN=' + cn, '-addext', 'subjectAltName=DNS:' + cn)
    class B(base.Bundle):
        pass
    b = B()
    b.cert_pem = open(T + '/%s.crt' % cn).read(); b.key_pem = open(T + '/%s.key' % cn).read()
    b.chain_pems = []; b.fullchain_pem = b.cert_pem; b.names = [cn]; b.name = cn
    b.fingerprint = hashlib.sha256(base64.b64decode(''.join(b.cert_pem.strip().splitlines()[1:-1]))).hexdigest()
    b.not_after = time.time() + 86400 * 20; b.serial = cn; b.key_type = 'ec-256'; b.alt = None
    return b
b = make(name)
got = t.deploy(b, {'verify_served': False})
ok('install: a certificate for %s put in (%s)' % (name, got.replace('\n', ' | ')[:200]), slot['id'] in got, got)
inv2 = t.inventory()
cur = inv2['slots'][0].get('current') or {}
ok('inventory after it: managed_by acme-push, the new fingerprint', inv2['slots'][0]['managed_by'] == 'acme-push'
   and cur.get('fingerprint') == b.fingerprint, inv2['slots'][0])
again = t.deploy(b, {'verify_served': False})
ok('the same again: already there, nothing touched (%s)' % again.replace('\n', ' | ')[:120], 'already' in again, again)
try:
    t.deploy(make('other.example.test'), {'slots': slot['id'], 'verify_served': False})
    ok('a certificate of another name: refused', False)
except base.PluginError as e:
    ok('a certificate of another name: refused (%s)' % str(e)[:100], 'names' in str(e), e)
print(json.dumps({'fingerprint': b.fingerprint, 'name': name}))
print('ALL %d / %d' % (sum(R), len(R)))
