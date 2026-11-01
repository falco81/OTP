#!/usr/bin/env python3
"""t_acmepush.py VERSION [ACME_DIR] - acme push (docs/acme-push-protocol.md), otp the receiver.

The sender is acme's own (its target acme_push, from a checkout of acme - ACME_DIR, by
default /home/user/falco81/acme); the receiver is otp's daemon part, in-process. The HTTP
between them is handed over the way the PHP page hands it to the daemon. Taken from
acme's test/test_acme_push.py (classes Crypto and Receiver), the receiver being otp:

the cryptography (RFC 8032 / 7748 / 5869, `cryptography` and the pure Python agreeing),
the test vectors of the document, pairing (a wrong code, a code used up), the signature,
the clock, a replay, a key not paired, the names, the slots, a push twice (already), a
dual certificate, the route PHP hands on, a cluster's inventory - and that otp's own QR
codes are still right (otp has a _gf_mul of its own, GF(256)).
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse

VER = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else '1.0.216'
ACME_DIR = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else \
    '/home/user/falco81/acme'
sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a.startswith('-')]

# ---- otp, the receiver -----------------------------------------------------------------------
OTMP = tempfile.mkdtemp(prefix='otp-push-')
os.makedirs(OTMP + '/log')
os.makedirs(OTMP + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'app1', 'acme_node_name': 'app1.example.test'},
          open(OTMP + '/config.json', 'w'))
os.environ.update(OTP_STATE=OTMP, OTP_CONFIG=OTMP + '/config.json', OTP_LOGDIR=OTMP + '/log',
                  OTP_RUN=OTMP + '/run')
sys.path.insert(0, '/home/claude/build/out/otp-%s' % VER)
_argv = sys.argv
sys.argv = ['x']
import otp as O  # noqa: E402
sys.argv = _argv
O.load_config(saved=None)
OSTORE = O.Storage(O.Db('sqlite', path=os.path.join(OTMP, 'otp.db')))
O.sealing_key(make=True)
O.HA_STORE['store'] = OSTORE
NODE = O.node_name()
SLOT = 'node:' + NODE

# ---- acme, the sender ------------------------------------------------------------------------
ATMP = tempfile.mkdtemp(prefix='acme-push-sender-')
with open(os.path.join(ATMP, 'config.json'), 'w') as f:
    f.write('{"node_name": "acme1", "upgrade_check": 0}')
os.environ.update(ACME_CONFIG=os.path.join(ATMP, 'config.json'), ACME_STATE=ATMP, ACME_RUN=ATMP,
                  ACME_LOGDIR=ATMP, ACME_PLUGINS=os.path.join(ATMP, 'plugins'))
sys.path.insert(0, ACME_DIR)
import acme  # noqa: E402,F401
import acmelib.engine as A  # noqa: E402
from acmelib.certs import runtime, store as S  # noqa: E402
from acmelib.plugins import base  # noqa: E402
ASTORE = A.Storage(A.open_db())
A.sealing_key(make=True)
A.CONFIG['certs_precheck'] = 0
S.registry()
CERTS = {}


def openssl(*args, data=None):
    return subprocess.run(['openssl'] + list(args), input=data, capture_output=True,
                          check=True).stdout


def read(p):
    with open(p) as fh:
        return fh.read()


def setUpModule():
    j = lambda n: os.path.join(OTMP, n)  # noqa: E731
    openssl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes',
            '-keyout', j('ca.key'), '-out', j('ca.crt'), '-days', '30', '-subj', '/CN=Push CA')
    for leaf, names, kind in (('a', 'app1.example.test', 'ec'), ('b', 'app1.example.test', 'ec'),
                              ('r', 'app1.example.test', 'rsa'),
                              ('o', 'other.example.test', 'ec'),
                              ('w', '*.example.test', 'ec')):
        key = ['-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256'] if kind == 'ec' else \
            ['-newkey', 'rsa:2048']
        openssl('req', *key, '-nodes', '-keyout', j(leaf + '.key'), '-out', j(leaf + '.csr'),
                '-subj', '/CN=' + names.split(',')[0])
        with open(j(leaf + '.ext'), 'w') as fh:
            fh.write('subjectAltName=' + ','.join('DNS:' + n for n in names.split(',')) + '\n')
        openssl('x509', '-req', '-in', j(leaf + '.csr'), '-CA', j('ca.crt'), '-CAkey', j('ca.key'),
                '-CAcreateserial', '-days', '10', '-out', j(leaf + '.crt'), '-extfile',
                j(leaf + '.ext'))
        CERTS[leaf] = (read(j(leaf + '.crt')), read(j(leaf + '.key')), names.split(','))


def tearDownModule():
    shutil.rmtree(OTMP, ignore_errors=True)
    shutil.rmtree(ATMP, ignore_errors=True)


class Bundle(base.Bundle):
    def __init__(self, leaf='a', alt=None):
        self.cert_pem, self.key_pem, self.names = CERTS[leaf]
        self.chain_pems = [read(os.path.join(OTMP, 'ca.crt'))]
        self.fullchain_pem = self.cert_pem + self.chain_pems[0]
        self.name = self.names[0]
        der = base64.b64decode(''.join(self.cert_pem.strip().splitlines()[1:-1]))
        self.fingerprint = hashlib.sha256(der).hexdigest()
        self.not_after = time.time() + 86400
        self.serial = leaf
        self.key_type = 'rsa-2048' if leaf == 'r' else 'ec-256'
        self.alt = Bundle(alt) if alt else None


class Wire(object):
    """What otp's PHP page and daemon do with a request of acme's: the body as it came, the
    X-Acme-Push-* headers - to otp's push_handle()."""
    def __init__(self):
        self.seen = []
        self.tamper = None

    def __call__(self, method, url, body=None, headers=None, **kw):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        op = q['api'][0][len('acme-push-'):]
        raw = body or b''
        h = {k: v for k, v in (headers or {}).items() if k.startswith('X-Acme-Push-')}
        if self.tamper:
            raw, h = self.tamper(op, raw, h)
        self.seen.append((method, op, raw, dict(h)))
        st, out = O.push_handle(OSTORE, op, raw, h)
        return st, {'Content-Type': 'application/json'}, json.dumps(out).encode()


def target(cfg=None, wire=None, name='app'):
    cls = S.plugin_class('target', 'acme_push')
    ctx = runtime.RunContext(ASTORE, None, scope='target:%s' % name)
    ctx.http = wire or Wire()
    t = cls(dict({'url': 'https://app1.example.test/admin/'}, **(cfg or {})), ctx)
    t._sleep = lambda s: None
    return t, ctx


def receiver_reset(on=True):
    for k in ('acme_push:conf', 'acme_push:nonces', 'web:tls:' + NODE, 'web:tls:vip'):
        OSTORE.db.run('DELETE FROM meta WHERE k = ?', (k,))
    OSTORE.db.run("DELETE FROM meta WHERE k LIKE 'acme:care:%'")
    ASTORE.db.run('DELETE FROM meta WHERE k LIKE ?', ('certs:kv:target:%',))
    ASTORE.db.run("DELETE FROM meta WHERE k LIKE 'acme_push:pin:%'")
    if on:
        O.push_card_do(OSTORE, {'action': 'on'}, 'tester')


def code():
    return O.push_card_do(OSTORE, {'action': 'pair'}, 'tester')['code']


class Crypto(unittest.TestCase):
    def both(self, fn):
        """fn() with `cryptography`, and with otp's pure Python."""
        a = fn()
        real = O._push_crypto
        O._push_crypto = lambda: None
        try:
            b = fn()
        finally:
            O._push_crypto = real
        self.assertEqual(a, b)
        return a

    def test_rfc8032_ed25519(self):
        sk = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
        pk = self.both(lambda: O.ed25519_public(sk))
        self.assertEqual(pk.hex(), 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
        sig = self.both(lambda: O.ed25519_sign(sk, b''))
        self.assertEqual(sig.hex(), 'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155'
                                    '5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
        self.assertTrue(self.both(lambda: O.ed25519_verify(pk, b'', sig)))
        self.assertFalse(self.both(lambda: O.ed25519_verify(pk, b'x', sig)))

    def test_rfc7748_x25519(self):
        k = bytes.fromhex('a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4')
        u = bytes.fromhex('e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c')
        self.assertEqual(self.both(lambda: O.x25519(k, u)).hex(),
                         'c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552')

    def test_rfc5869_hkdf(self):
        got = O.hkdf_sha256(bytes([0x0b] * 22), bytes(range(13)), bytes(range(0xf0, 0xfa)), 42)
        self.assertEqual(got.hex(), '3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf'
                                    '34007208d5b887185865')

    def test_gcm_both_ways(self):
        k, n = bytes(range(32)), bytes(range(12))
        for size in (0, 1, 15, 16, 17, 250):
            data = os.urandom(size)
            ct = self.both(lambda: O.aes256gcm(k, n, data, b'aad'))
            self.assertEqual(self.both(lambda: O.aes256gcm(k, n, ct, b'aad', open_=True)), data)
            with self.assertRaises(ValueError):
                O.aes256gcm(k, n, ct, b'other', open_=True)

    def test_vectors_of_the_document(self):
        seed, app, eph, nonce = bytes(range(32)), bytes(range(32, 64)), bytes(range(64, 96)), \
            bytes(range(96, 108))
        app_id = '00112233445566778899aabbccddeeff'
        pub = O.ed25519_public(seed)
        kid = O.push_key_id(pub)
        self.assertEqual(O.push_b64(pub), 'A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg=')
        self.assertEqual(kid, '56475aa75463474c')
        h = A.push_signed(seed, 'inventory', app_id, b'{"slots": ["auto"]}', ts=1793534400,
                          nonce='n0nce-0123456789ab')
        self.assertEqual(h['X-Acme-Push-Signature'], '7nqJW4/NR3Et6pZx3B8qS3rvQGaQR0UTlNdptpRs4lxa'
                         'Ztc3Cf2zBRkOWPB0tV/rmQNfwbcl2/FKJ3Pu2h/bDg==')
        self.assertEqual(O.push_b64(O.x25519_public(app)), 'NYBy1jZYgNGu6jKa35EhODhR7SGijjt16WXQ0s0WYlQ=')
        fp = 'ab' * 32
        sealed = A.push_seal_key('KEY\n', O.x25519_public(app), app_id, fp, eph=eph, nonce=nonce)
        self.assertEqual(sealed['ct'], '2UbSrj9NwnCBu3qZW4U7MzxzlGw=')
        self.assertEqual(self.both(lambda: O.push_open_key(sealed, app, app_id, fp)), 'KEY\n')
        with self.assertRaises(O.PushError):
            O.push_open_key(sealed, app, app_id, 'cd' * 32)
        self.assertEqual(O.push_proof('ABCD-EFGH-JKMN-PQRS', 'pair', app_id, kid, 'n0nce-0123456789ab'),
                         'e8e1978c03896460ce7f6e1697d5a5220c8f3a1cd8a01d2fc2e838dbd9318b39')

    def test_every_top_level_name_once(self):
        """Every part of otp.py shares one namespace (chapter 0 of the protocol): a name
        defined twice replaces the first - acme 1.0.6's _gf_mul broke the QR codes."""
        import re as _re
        from collections import Counter
        src = open(O.__file__).read()
        names = Counter(_re.findall(r'^(?:def|class) ([A-Za-z_]\w*)', src, _re.M))
        self.assertEqual([n for n, c in names.items() if c > 1], [])

    def test_otps_own_qr_codes_still_right(self):
        """otp's _gf_mul (the QR codes' GF(256)) is not the GCM one."""
        self.assertEqual(O._gf_mul(2, 0x80), 0x1D)          # x^8 = x^4+x^3+x^2+1 (0x11D)
        self.assertLess(O._gf_mul(0xFF, 0xFF), 256)
        self.assertNotEqual(O._gf_mul, O._push_gcm_mul)
        self.assertIn('<svg', O.qr_svg('otpauth://totp/x?secret=JBSWY3DPEHPK3PXP'))


class Receiver(unittest.TestCase):
    def setUp(self):
        receiver_reset()

    def paired(self, **cfg):
        t, ctx = target(dict({'pair_code': code()}, **cfg))
        t.test()
        return t, ctx

    def test_hello_off_says_little(self):
        receiver_reset(on=False)
        st, out = O.push_handle(OSTORE, 'hello', b'', {})
        self.assertEqual((st, out['app'], out['on']), (200, 'otp', False))
        self.assertNotIn('enc_key', out)
        t, _ = target()
        with self.assertRaises(base.PluginError) as e:
            t.test()
        self.assertIn('switch it on', str(e.exception))
        st, out = O.push_handle(OSTORE, 'install', b'{}', {})
        self.assertEqual((st, out['code']), (403, 'off'))

    def test_not_paired_says_how(self):
        t, _ = target()
        with self.assertRaises(base.PluginError) as e:
            t.test()
        self.assertIn('Pairing code', str(e.exception))

    def test_pairing_and_try_change_nothing(self):
        before = O.tls_profile(OSTORE, NODE)
        t, ctx = self.paired()
        self.assertIn(SLOT, t.test())
        self.assertEqual(O.tls_profile(OSTORE, NODE), before)
        self.assertEqual(ctx.push_pin(t.base_url())['how'], 'pairing code')
        conf = O.push_conf(OSTORE)
        self.assertEqual(len(conf['keys']), 1)
        self.assertIsNone(conf['pairing'], 'a code is used once')
        ASTORE.db.run("DELETE FROM meta WHERE k LIKE 'acme_push:pin:%'")
        t2, _ = target({'pair_code': 'AAAA-BBBB-CCCC-DDDD'}, name='other')
        with self.assertRaises(base.PluginError) as e:
            t2.test()
        self.assertIn('pairing_closed', str(e.exception))

    def test_the_route_php_hands_on(self):
        t, ctx = self.paired()
        box, me = O.push_box(OSTORE), A.push_identity(ASTORE)
        raw = b'{}'

        class H(object):
            store = OSTORE
            headers = A.push_signed(me['seed'], 'inventory', box['app_id'], raw)
            got = []

            def body(self):
                return {'body': base64.b64encode(raw).decode(),
                        'headers': {k[len('X-Acme-Push-'):]: v for k, v in self.headers.items()}}

            def send_json(self, data, status=200):
                self.got.append((status, data))
        fn = O.ROUTES[('POST', '/api/acme-push/inventory')]
        h = H()
        fn(h)
        self.assertEqual(h.got[0][0], 200)
        self.assertEqual(h.got[0][1]['slots'][0]['id'], SLOT)
        fn(h)
        self.assertEqual(h.got[1][0], 401)
        O.ROUTES[('GET', '/api/acme-push/hello')](h)
        self.assertEqual(h.got[2][1]['app_id'], box['app_id'])

    def test_wrong_code_burns_it(self):
        right = code()
        for i in range(O.PUSH_CODE_TRIES):
            t, _ = target({'pair_code': 'WRNG-WRNG-WRNG-WRN%d' % i})
            with self.assertRaises(base.PluginError) as e:
                t.test()
            self.assertIn('bad_code', str(e.exception))
        t, _ = target({'pair_code': right})
        with self.assertRaises(base.PluginError) as e:
            t.test()
        self.assertIn('pairing_closed', str(e.exception))
        self.assertEqual(O.push_conf(OSTORE)['keys'], [])

    def test_pasted_key_and_first_seen(self):
        me = A.push_identity(ASTORE)
        O.push_card_do(OSTORE, {'action': 'key_add', 'key': me['text']}, 'tester')
        t, ctx = target()
        t.test()
        self.assertEqual(ctx.push_pin(t.base_url())['how'], 'first seen')
        OSTORE.db.run('DELETE FROM meta WHERE k = ?', ('acme_push:box',))
        with self.assertRaises(base.PluginError) as e:
            t.test()
        self.assertIn('not the one paired', str(e.exception))

    def test_signature_clock_replay_key(self):
        t, ctx = self.paired()
        box, me = O.push_box(OSTORE), A.push_identity(ASTORE)
        raw = b'{}'
        h = A.push_signed(me['seed'], 'inventory', box['app_id'], raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[0], 200)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'replay')
        h = A.push_signed(me['seed'], 'inventory', box['app_id'], raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', b'{ }', h)[1]['code'], 'bad_signature')
        h = A.push_signed(me['seed'], 'install', box['app_id'], raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'bad_signature')
        h = A.push_signed(me['seed'], 'inventory', 'f' * 32, raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'bad_signature')
        for off in (-400, 400):
            h = A.push_signed(me['seed'], 'inventory', box['app_id'], raw, ts=time.time() + off)
            self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'stale')
        h = A.push_signed(os.urandom(32), 'inventory', box['app_id'], raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'unknown_key')
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, {})[1]['code'], 'unsigned')
        O.push_card_do(OSTORE, {'action': 'key_forget', 'id': me['id']}, 'tester')
        h = A.push_signed(me['seed'], 'inventory', box['app_id'], raw)
        self.assertEqual(O.push_handle(OSTORE, 'inventory', raw, h)[1]['code'], 'not_paired')

    def test_deploy_names_already_and_dual(self):
        t, ctx = self.paired()
        b = Bundle('a')
        self.assertIn(SLOT, t.deploy(b, {}))
        prof = O.tls_profile(OSTORE, NODE)
        self.assertEqual(prof['info']['fingerprint'].replace(':', '').lower(), b.fingerprint)
        self.assertTrue(prof['how'].startswith('acme push'))
        self.assertFalse(O.acme_care(OSTORE, NODE), 'otp\'s own Automatic certificates leave it alone')
        self.assertEqual(O.unseal_secret(prof['key'], 'web:tls').strip(), b.key_pem.strip())
        self.assertTrue(any('acme push: %s has the certificate' % NODE in (e.get('words') or '')
                            for e in OSTORE.db.rows("SELECT * FROM events ORDER BY id DESC LIMIT 20")),
                        'an event written')
        self.assertIn('already', t.deploy(b, {}))
        self.assertIn(SLOT, t.deploy(b, {'force': True}))
        with self.assertRaises(base.PluginError) as e:
            t.deploy(Bundle('o'), {'slots': SLOT})
        self.assertIn('(names)', str(e.exception))
        with self.assertRaises(base.PluginError):
            t.deploy(Bundle('o'), {'slots': SLOT, 'check_names': False})
        O.push_card_do(OSTORE, {'action': 'other_names', 'on': True}, 'tester')
        self.assertIn(SLOT, t.deploy(Bundle('o'), {'slots': NODE, 'check_names': False}))
        self.assertIn(SLOT, t.deploy(Bundle('w'), {}))
        dual = Bundle('b', alt='r')
        t.deploy(dual, {})
        prof = O.tls_profile(OSTORE, NODE)
        self.assertEqual(O.tls_alt(prof)['info']['fingerprint'].replace(':', '').lower(),
                         dual.alt.fingerprint)
        # what the card shows: the same certificate an upload would show
        view = O.tls_view(prof)
        self.assertTrue(view, view)
        with self.assertRaises(base.PluginError) as e:
            t.deploy(b, {'slots': 'vip'})
        self.assertIn('no_slot', str(e.exception))

    def test_every_other_way_still_works_and_takes_over(self):
        """Chapter 0: with push on and paired, an upload, a self-signed one and a request on
        Certificates and TLS work as before and replace what acme put in; Automatic
        certificates can take the slot back. Off again: what was pushed stays."""
        t, ctx = self.paired()
        self.assertIn(SLOT, t.deploy(Bundle('a'), {}))

        class H(object):
            store = OSTORE

            def __init__(self, b):
                self.b = b

            def me(self, role=None):
                return {'name': 'tester', 'role': 'fulladmin'}

            def body(self):
                return self.b
        web = O.ROUTES[('POST', '/api/web')]
        managed = lambda: [x for x in O.push_slots(OSTORE) if x['id'] == SLOT][0]['managed_by']  # noqa: E731
        self.assertEqual(managed(), 'acme-push')
        cert, key, _n = CERTS['b']
        got = web(H({'action': 'tls_upload', 'target': NODE, 'cert': cert, 'key': key}))
        self.assertIn('kept', got['message'])
        self.assertEqual(managed(), 'manual', 'an upload replaces the pushed one, as before')
        self.assertEqual(O.tls_profile(OSTORE, NODE)['how'], 'uploaded')
        self.assertIn(SLOT, t.deploy(Bundle('a'), {}))
        got = web(H({'action': 'tls_selfsigned', 'target': NODE, 'cn': 'app1.example.test', 'days': 30,
                     'kind': 'ec256'}))
        self.assertEqual(O.tls_profile(OSTORE, NODE)['how'], 'self-signed, made here')
        self.assertEqual(managed(), 'manual')
        got = web(H({'action': 'tls_csr', 'target': NODE, 'cn': 'app1.example.test'}))
        self.assertIn('BEGIN CERTIFICATE REQUEST', got['csr'])
        O.CONFIG['acme'] = 1
        try:
            O.acme_care_set(OSTORE, NODE, True, 'tester', 'look after it')
            self.assertTrue(O.acme_care(OSTORE, NODE))
            self.assertEqual(managed(), 'own-acme', 'Automatic certificates takes the slot back')
        finally:
            O.CONFIG['acme'] = 0
        self.assertIn(SLOT, t.deploy(Bundle('a'), {}))
        O.push_card_do(OSTORE, {'action': 'off'}, 'tester')
        self.assertTrue(O.tls_profile(OSTORE, NODE)['how'].startswith('acme push'),
                        'switched off: what was pushed stays')
        with self.assertRaises(base.PluginError) as e:
            t.deploy(Bundle('a'), {'force': True})
        self.assertIn('takes no certificates from acme', str(e.exception))

    def test_key_not_of_the_cert_and_tampered(self):
        t, ctx = self.paired()
        b = Bundle('a')
        b.key_pem = CERTS['b'][1]
        with self.assertRaises(base.PluginError) as e:
            t.deploy(b, {})
        self.assertIn('key_mismatch', str(e.exception))
        wire = Wire()
        wire.tamper = lambda op, raw, h: (raw.replace(b'"auto"', b'"this"'), h)
        t2, _ = target(wire=wire)
        with self.assertRaises(base.PluginError) as e:
            t2.deploy(Bundle('a'), {})
        self.assertIn('bad_signature', str(e.exception))

    def test_inventory_in_a_cluster(self):
        t, ctx = self.paired()
        was = dict(O.CONFIG)
        O.CONFIG['ha_mode'] = 'replicated'
        OSTORE.set_meta('web:vip', json.dumps({'on': True, 'fqdn': 'app.example.test',
                                               'address': '192.0.2.10'}))
        OSTORE.set_meta('node:app2', json.dumps({'at': time.time(), 'address': '192.0.2.12'}))
        OSTORE.save_setting('acme_node_name@app2', 'app2.example.test', 't')
        try:
            inv = t.inventory()
            ids = [s['id'] for s in inv['slots']]
            for want in ('vip', SLOT, 'node:app2'):
                self.assertIn(want, ids)
            with self.assertRaises(base.PluginError) as e:
                t.deploy(Bundle('a'), {'slots': 'vip'})
            self.assertIn('app.example.test', str(e.exception))
            got = t.deploy(Bundle('w'), {'slots': 'auto'})
            self.assertIn('vip', got)
            self.assertIn(SLOT, got)
            # The other node's: kept for it here, as an upload for it on these pages is.
            self.assertIn('node:app2', got)
            if True:
                self.assertTrue(str((O.tls_profile(OSTORE, 'app2') or {}).get('how') or '')
                                .startswith('acme push'))
        finally:
            O.CONFIG.clear()
            O.CONFIG.update(was)
            OSTORE.db.run("DELETE FROM meta WHERE k IN ('web:vip', 'node:app2', 'web:tls:app2')")


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=1).result
    n = r.testsRun
    bad = len(r.failures) + len(r.errors)
    print('ALL %d / %d' % (n - bad, n))
    sys.exit(1 if bad else 0)
