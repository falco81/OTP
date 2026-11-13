"""t_osroots.py [VERSION] - the system's trusted roots (1.0.265): Settings -> Certificates and TLS
-> Trusted roots of the system, `otp --os-roots*`.

Pure Python, nothing started, no port bound, nothing of the machine touched: the root helper
(deploy/otp_web.py, loaded as a module) works on a temporary anchors folder with a fake extract
tool and a fake package query (OTP_OSROOTS_* in the environment); the daemon's parts are put
together as build.sh does into a temporary otp.py and loaded over SQLite - its root_ask() answered
by the helper in-process. The test certificates are made with openssl in a temporary folder.

    python3 t_osroots.py 1.0.265
"""
import atexit
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.265'
BUILD = '/home/claude/build'
V = os.environ.get('OTP_DIR') or BUILD + '/out/otp-%s' % VER
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok   ' if cond else 'FAIL ') + what + ('' if cond else '   <-- %s' % str(more)[:600]), flush=True)
    return bool(cond)


TOP = tempfile.mkdtemp(prefix='t_osroots_')
atexit.register(lambda: shutil.rmtree(TOP, True))
os.chmod(TOP, 0o755)


# ==== the certificates ==========================================================================
C = TOP + '/certs'
os.makedirs(C)


def sh(*a, **kw):
    got = subprocess.run(list(a), capture_output=True, text=True, cwd=C, **kw)
    if got.returncode:
        raise SystemExit('openssl: %s %s' % (' '.join(a), got.stderr))
    return got.stdout


EXT = C + '/ext.cnf'
open(EXT, 'w').write('[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n'
                     'subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n'
                     '[leaf]\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\n'
                     '[noku]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature\n'
                     '[nobc]\nkeyUsage=digitalSignature\n')


def mk_root(name, cn, key='rsa:2048', days=3650, ext='ca'):
    sh('openssl', 'req', '-x509', '-newkey', key, '-nodes', '-keyout', name + '.key', '-out', name + '.pem',
       '-days', str(days), '-subj', '/O=Test/CN=' + cn, '-extensions', ext, '-config',
       _cfg())
    return open(C + '/' + name + '.pem').read()


def _cfg():
    p = C + '/req.cnf'
    if not os.path.exists(p):
        open(p, 'w').write('[req]\ndistinguished_name=dn\n[dn]\n' + open(EXT).read())
    return p


def mk_signed(name, cn, by, ext='ca', md='sha256', key='rsa:2048'):
    sh('openssl', 'req', '-newkey', key, '-nodes', '-keyout', name + '.key', '-out', name + '.csr',
       '-subj', '/O=Test/CN=' + cn, '-config', _cfg())
    sh('openssl', 'x509', '-req', '-in', name + '.csr', '-CA', by + '.pem', '-CAkey', by + '.key',
       '-CAcreateserial', '-out', name + '.pem', '-days', '1000', '-' + md, '-extfile', EXT,
       '-extensions', ext)
    return open(C + '/' + name + '.pem').read()


ROOT = mk_root('root', 'Acme Root CA')
INTER = mk_signed('inter', 'Acme Issuing CA', 'root')
LEAF = mk_signed('leaf', 'www.acme.test', 'inter', ext='leaf')
EC = mk_root('ec', 'Acme EC Root', key='ec:' + C + '/ecp.pem') if not sh(
    'openssl', 'ecparam', '-name', 'prime256v1', '-out', 'ecp.pem') else None
WEAK = mk_root('weak', 'Old Weak Root', key='rsa:1024')
NOKU = mk_root('noku', 'No Sign Root', ext='noku')
NOBC = mk_root('nobc', 'No BC Root', ext='nobc')
SHA1 = mk_signed('sha1', 'SHA1 Issuing CA', 'root', md='sha1')
OTHER = mk_root('other', 'Somebody Elses Root')
EXPIRED = None
try:
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Expired Root')])
    EXPIRED = x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(k.public_key()).serial_number(
        7).not_valid_before(datetime.datetime(2015, 1, 1)).not_valid_after(datetime.datetime(2020, 1, 1)).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(k, hashes.SHA256()).public_bytes(
        serialization.Encoding.PEM).decode()
except ImportError:
    pass
DER = subprocess.run(['openssl', 'x509', '-in', C + '/root.pem', '-outform', 'DER'], capture_output=True).stdout


def fp_of(pem):
    out = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-sha256'], input=pem,
                         capture_output=True, text=True).stdout
    return out.split('=', 1)[1].strip().replace(':', '').lower()


# ==== the fake tools ============================================================================
FB = TOP + '/fakebin'
os.makedirs(FB)
ANCH = TOP + '/anchors'
os.makedirs(ANCH)
os.chmod(ANCH, 0o755)
BUNDLE = TOP + '/extracted/tls-ca-bundle.pem'
os.makedirs(os.path.dirname(BUNDLE))
DISTRO = TOP + '/distro.pem'
open(DISTRO, 'w').write(OTHER)     # the distribution's list: one root
CALLS = TOP + '/extract.calls'
FAILFLAG = TOP + '/extract.fail'
open(FB + '/fake-extract', 'w').write('''#!/bin/sh
# update-ca-trust extract, as it does: the distribution's list and the local additions, merged
echo run >> %s
[ -e %s ] && { echo "p11-kit: could not write" >&2; exit 3; }
cat %s > %s.tmp
for f in %s/*; do [ -f "$f" ] && cat "$f" >> %s.tmp; done
mv %s.tmp %s
''' % (CALLS, FAILFLAG, DISTRO, BUNDLE, ANCH, BUNDLE, BUNDLE, BUNDLE))
open(FB + '/fake-pkg', 'w').write('#!/bin/sh\necho ca-certificates-2025.2.80_v9.0.305-91.el9.noarch\n')
for f in ('fake-extract', 'fake-pkg'):
    os.chmod(FB + '/' + f, 0o755)
HSTATE = TOP + '/hstate'
os.makedirs(HSTATE + '/web')
os.environ.update(OTP_OSROOTS_FLAVOUR='rhel', OTP_OSROOTS_DIR=ANCH, OTP_OSROOTS_BUNDLE=BUNDLE,
                  OTP_OSROOTS_EXTRACT=FB + '/fake-extract', OTP_OSROOTS_PKG=FB + '/fake-pkg',
                  OTP_VIP_NO_SERVICES='1', OTP_STATE=HSTATE)
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)


def calls():
    try:
        return len(open(CALLS).read().split())
    except OSError:
        return 0


def hdo(**r):
    try:
        return W.osroots_do(r), ''
    except W.Refused as e:
        return None, str(e)


# ==== 1. the helper: reading a certificate ======================================================
f = W.osroots_facts(ROOT)
ok('1 a root: an authority, a root, RSA 2048, its SHA-256 as openssl says',
   f['ca'] and f['kind'] == 'root' and f['key'] == 'RSA 2048' and f['fp'] == fp_of(ROOT) and not f['refused']
   and f['cn'] == 'Acme Root CA', f)
f = W.osroots_facts(INTER)
ok('1 an intermediate: an authority, issued by the root', f['kind'] == 'intermediate' and f['ca'] and
   'Acme Root CA' in f['issuer'] and not f['refused'], f)
f = W.osroots_facts(LEAF)
ok('1 a server\'s certificate: refused (CA:FALSE)', f['refused'] and 'CA:FALSE' in f['refused'][0], f)
ok('1 no basicConstraints: refused', W.osroots_facts(NOBC)['refused'])
ok('1 a key usage without keyCertSign: refused', any('keyCertSign' in x for x in W.osroots_facts(NOKU)['refused']))
f = W.osroots_facts(WEAK)
ok('1 RSA 1024: taken, with a warning of the crypto policy', not f['refused'] and any('1024 bits' in w for w in f['warn']), f)
f = W.osroots_facts(SHA1)
ok('1 an intermediate signed with SHA-1: taken, warned', not f['refused'] and any('sha1' in w.lower() for w in f['warn']), f)
if EC:
    f = W.osroots_facts(EC)
    ok('1 an EC root: EC P-256', f['key'] == 'EC P-256', f)
if EXPIRED:
    f = W.osroots_facts(EXPIRED)
    ok('1 a root that ran out: taken, warned', not f['refused'] and any('ran out on 2020' in w for w in f['warn']), f)
for bad, word in ((ROOT + open(C + '/root.key').read(), 'private key'),
                  ('hello', 'no certificate'),
                  ('-----BEGIN CERTIFICATE-----\n!!!!\n-----END CERTIFICATE-----', 'no certificate')):
    try:
        W.osroots_blocks(bad)
        ok('1 refused: %s' % word, False, 'taken')
    except W.Refused as e:
        ok('1 refused: %s' % word, word in str(e) or 'base64' in str(e), e)

# ==== 2. the helper: the folder ===================================================================
open(ANCH + '/corp-by-admin.pem', 'w').write(OTHER)
open(ANCH + '/notes.txt', 'w').write('not a certificate\n')
before_other = open(ANCH + '/corp-by-admin.pem').read()
d, e = hdo(do='list')
ok('2 list: nothing of otp\'s, the admin\'s file shown as somebody else\'s', d and d['ours'] == [] and
   any(o['file'] == 'corp-by-admin.pem' and o['certs'] and o['certs'][0]['cn'] == 'Somebody Elses Root'
       for o in d['others']), d or e)
ok('2 list: a file that is no certificate shown as such', any(o['file'] == 'notes.txt' and o['certs'] == [] for o in d['others']))
ok('2 list: the system\'s list and its package', d['system']['package'].startswith('ca-certificates-2025')
   and d['flavour'] == 'rhel' and d['dir'] == ANCH, d['system'])
d, e = hdo(do='sync', certs=[ROOT, INTER])
name_r = 'otp-%s.pem' % fp_of(ROOT)[:16]
ok('2 sync: written as otp-<sha256 16>.pem, the tool run once', d and os.path.isfile(ANCH + '/' + name_r)
   and calls() == 1 and 'added ' + name_r in d['said'], d or e)
st_ = os.stat(ANCH + '/' + name_r)
ok('2 ...root\'s, 0644', stat.S_IMODE(st_.st_mode) == 0o644 and st_.st_uid == 0, oct(st_.st_mode))
ok('2 ...both in the system\'s list now (in_bundle)', len(d['ours']) == 2 and all(x['in_bundle'] for x in d['ours']), d['ours'])
ok('2 ...the admin\'s file as it was', open(ANCH + '/corp-by-admin.pem').read() == before_other)
ok('2 ...and the distribution\'s list still in the bundle', OTHER.strip() in open(BUNDLE).read())
d, e = hdo(do='sync', certs=[ROOT, INTER])
ok('2 sync again: nothing to do, the tool not run', d and d['said'] == [] and calls() == 1, (d or {}).get('said'))
d, e = hdo(do='sync', certs=[ROOT, INTER, LEAF])
ok('2 a server\'s certificate in the set: refused by name, the others kept', d and len(d['refused']) == 1 and
   d['refused'][0]['cn'] == 'www.acme.test' and len(d['ours']) == 2, d or e)
open(ANCH + '/' + name_r, 'w').write(OTHER)          # somebody changed otp's file
d, e = hdo(do='sync', certs=[ROOT, INTER])
ok('2 otp\'s file changed by somebody: put back as wanted', open(ANCH + '/' + name_r).read().strip() == ROOT.strip()
   or W.osroots_blocks(open(ANCH + '/' + name_r).read())[0][1] == W.osroots_blocks(ROOT)[0][1], d or e)
os.unlink(ANCH + '/' + name_r)
os.symlink('/etc/hostname', ANCH + '/' + name_r)    # a link in otp's name: never followed
d, e = hdo(do='sync', certs=[ROOT, INTER])
ok('2 a link in otp\'s name: replaced by the file, the link\'s target untouched',
   d and not os.path.islink(ANCH + '/' + name_r) and os.path.isfile(ANCH + '/' + name_r), d or e)
n0 = calls()
d, e = hdo(do='sync', certs=[INTER])
ok('2 one taken away: its file removed, the tool run', d and not os.path.exists(ANCH + '/' + name_r) and
   calls() == n0 + 1 and fp_of(ROOT) not in [x.get('fp') for x in d['ours']], d or e)
d, e = hdo(do='sync', certs=[])
ok('2 all taken away: none of otp\'s left, the others\' there', d and not [x for x in os.listdir(ANCH) if x.startswith('otp-')]
   and os.path.isfile(ANCH + '/corp-by-admin.pem') and os.path.isfile(ANCH + '/notes.txt'), os.listdir(ANCH))
open(FAILFLAG, 'w').write('x')
d, e = hdo(do='sync', certs=[ROOT])
ok('2 the tool failing: said, with its words', d is None and 'could not write' in e and 'ended with 3' in e, e)
os.unlink(FAILFLAG)
d, e = hdo(do='sync', certs=[ROOT] * 51)
ok('2 more than 50: refused', d is None and '50' in e, e)
d, e = hdo(do='sync', certs=[ROOT + INTER])
ok('2 two certificates in one entry: refused', d is None and 'one certificate' in e, e)
# the folder a link: nothing written there
LNK = TOP + '/anchors-link'
os.symlink(ANCH, LNK)
os.environ['OTP_OSROOTS_DIR'] = LNK
d, e = hdo(do='sync', certs=[INTER])
ok('2 the anchors folder a link: refused, nothing written', d is None and 'not a folder' in e, e)
os.environ['OTP_OSROOTS_DIR'] = ANCH
os.chmod(ANCH, 0o777)
d, e = hdo(do='sync', certs=[INTER])
ok('2 the anchors folder writable by others: refused', d is None and 'root\'s alone' in e, e)
os.chmod(ANCH, 0o755)
# Debian: .crt
DEB = TOP + '/deb'
os.makedirs(DEB + '/corp')
open(DEB + '/corp/ad-root.crt', 'w').write(OTHER)
os.environ.update(OTP_OSROOTS_FLAVOUR='debian', OTP_OSROOTS_DIR=DEB)
d, e = hdo(do='sync', certs=[ROOT])
ok('2 Debian: otp-<sha256 16>.crt, a subfolder of somebody else\'s listed',
   d and os.path.isfile(DEB + '/otp-%s.crt' % fp_of(ROOT)[:16]) and any(o['file'] == 'corp/ad-root.crt' for o in d['others']), d or e)
os.environ.update(OTP_OSROOTS_FLAVOUR='rhel', OTP_OSROOTS_DIR=ANCH)
# the request file, as systemd starts it
open(HSTATE + '/web/osroots.ask', 'w').write(json.dumps({'id': 'abc123', 'do': 'sync', 'certs': [ROOT, INTER]}))
W.osroots_part()
got = json.load(open(HSTATE + '/web/osroots.json'))
ok('2 osroots.ask: answered in osroots.json under its id, the ask taken away',
   got.get('ok') and got.get('id') == 'abc123' and len(got['data']['ours']) == 2 and
   not os.path.exists(HSTATE + '/web/osroots.ask'), got)
open(HSTATE + '/web/osroots.ask', 'w').write(json.dumps({'id': 'x', 'do': 'rm -rf'}))
W.osroots_part()
got = json.load(open(HSTATE + '/web/osroots.json'))
ok('2 osroots.ask of something else: refused', got.get('ok') is False and 'list, check or sync' in got.get('said', ''), got)
ok('2 otp-web.path starts the helper for osroots.ask',
   'PathExists=/var/lib/otp/web/osroots.ask' in open(V + '/deploy/otp-web.path').read())
ok('2 the helper serves it with the rest', 'osroots_part()' in open(V + '/deploy/otp_web.py').read().split('def serve():')[1])
hdo(do='sync', certs=[])

# ==== 3. the daemon: the set wanted, one row a node ============================================
D = TOP + '/state'
os.makedirs(D + '/run')
os.makedirs(D + '/web')
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
with open(TOP + '/otp.py', 'w', encoding='utf-8') as fo:
    for p in re.findall(r'parts/\S+\.py', cat):
        fo.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        fo.write('\n')
json.dump({'db_engine': 'sqlite', 'node_name': 'n1', 'api_port': 29967}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', TOP + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.sealing_key(make=True)
ok('3 the parts in build.sh: 90k_osroots.py', 'parts/90k_osroots.py' in cat)
ok('3 the guard signs the set wanted', m.dbguard_meta_kept('oscerts:want:n1') and not m.dbguard_meta_kept('oscerts:node:n1'))
ok('3 nothing wanted yet: None (never "take all away")', m.osr_want(st) is None)
CHAIN = ROOT + '\n' + INTER + '\n' + LEAF
got = m.osr_check(st, CHAIN)
ok('3 a chain file read: the root, the intermediate, the leaf refused', [g['kind'] for g in got] == ['root', 'intermediate', 'intermediate']
   and not got[0]['refused'] and not got[1]['refused'] and got[2]['refused'], [(g['cn'], g['refused']) for g in got])
ok('3 the daemon reads as the helper does (fingerprint, key, words)',
   all(g['fp'] == W.osroots_facts(g['pem'])['fp'] and g['key'] == W.osroots_facts(g['pem'])['key'] and
       g['refused'] == W.osroots_facts(g['pem'])['refused'] for g in got))
r = m.osr_add(st, CHAIN, 'alice')
ok('3 add the chain: two added, the leaf said', len(r['added']) == 2 and len(r['refused']) == 1 and
   r['refused'][0]['cn'] == 'www.acme.test', r)
rows = [x['k'] for x in st.db.rows("SELECT k FROM meta WHERE k LIKE 'oscerts:want:%'")]
ok('3 written in this node\'s own row only', rows == ['oscerts:want:n1'], rows)
w1 = m.osr_want(st)
ok('3 the set wanted: the two, by alice', w1 and len(w1['certs']) == 2 and w1['by'] == 'alice', w1)
try:
    m.osr_add(st, ROOT, 'alice')
    ok('3 the same again: nothing added', False)
except ValueError as e:
    ok('3 the same again: nothing added, said', 'there already' in str(e), e)
try:
    m.osr_add(st, LEAF, 'alice')
    ok('3 only a leaf: refused', False)
except ValueError as e:
    ok('3 only a leaf: refused with why', 'CA:FALSE' in str(e), e)
ok('3 DER read as PEM', m.osr_blocks(m.osr_text(DER))[0][1] == DER)
# The other node writes its own row, newer: that is the set.
v_other = w1['v'] + 5
st.db.run("INSERT INTO meta (k, v) VALUES (?, ?)", ('oscerts:want:n2', json.dumps(
    {'v': v_other, 'certs': [{'pem': W.osroots_blocks(INTER)[0][0], 'fp': fp_of(INTER), 'cn': 'Acme Issuing CA'}],
     'by': 'bob', 'at': time.time()})))
w2 = m.osr_want(st)
ok('3 the other node\'s newer row is the set', w2['node'] == 'n2' and len(w2['certs']) == 1, w2)
m.osr_add(st, ROOT, 'carol')
w3 = m.osr_want(st)
ok('3 a change here builds on it and is newer still (above every v seen)', w3['node'] == 'n1' and w3['v'] > v_other and
   sorted(c['cn'] for c in w3['certs']) == ['Acme Issuing CA', 'Acme Root CA'], w3)
try:
    m.osr_remove(st, 'abc', 'carol')
    ok('3 remove: too short a fingerprint refused', False)
except ValueError as e:
    ok('3 remove: too short a fingerprint refused', '12' in str(e), e)
m.osr_remove(st, fp_of(INTER)[:20], 'carol')
ok('3 remove by the start of its fingerprint', [c['cn'] for c in m.osr_want(st)['certs']] == ['Acme Root CA'])
ok('3 every change in the events', any('took away Acme Issuing CA' in str(dict(x)) for x in st.db.rows('SELECT * FROM events')))
# The guard: a row written straight into the database is not taken
m.CONFIG['db_guard'] = True
st.db.run("UPDATE meta SET v = ? WHERE k = 'oscerts:want:n2'", (json.dumps(
    {'v': 10 ** 15, 'certs': [], 'by': 'mallory', 'at': time.time()}),))
w4 = m.osr_want(st)
ok('3 guard on: a row not written by otp is left out', w4 and w4['node'] == 'n1' and w4['by'] == 'carol', w4)
m.osr_add(st, INTER, 'carol')
ok('3 guard on: otp\'s own row is signed and taken', m.osr_want(st)['by'] == 'carol' and len(m.osr_want(st)['certs']) == 2)
m.CONFIG['db_guard'] = False
st.db.run("DELETE FROM meta WHERE k = 'oscerts:want:n2'")

# ==== 4. the tick: each node brings its machine to the set ======================================
def fake_root_ask(ask, answer, data, wait=60):
    assert ask == 'osroots.ask' and answer == 'osroots.json'
    try:
        return W.osroots_do(data)
    except W.Refused as e:
        raise ValueError(str(e))


m.root_ask = fake_root_ask


class Dm(object):
    store = st


def tick_wait():
    m.osroots_tick(Dm())
    for _ in range(200):
        time.sleep(0.05)
        if not m.OSR['busy']:
            break


st.set_meta('node:n2', json.dumps({'at': time.time(), 'version': m.__version__, 'address': '192.0.2.2'}))
tick_wait()
v = m.osr_view(st)
me = [n for n in v['nodes'] if n['name'] == 'n1'][0]
n2 = [n for n in v['nodes'] if n['name'] == 'n2'][0]
ok('4 this node: as wanted, both on it', me['status'] == 'applied' and len(me['ours']) == 2 and
   all(c['on'].get('n1') for c in v['certs']), me)
ok('4 the other node, not heard from: waiting', n2['status'] == 'waiting', n2)
ok('4 the view: the system\'s list and package of this node', me['system'].get('package', '').startswith('ca-certificates')
   and me['system'].get('count', 0) >= 3, me['system'])
ok('4 ...and the others\' additions', any(o['file'] == 'corp-by-admin.pem' for o in me['others']))
n_calls = calls()
tick_wait()
ok('4 a tick with nothing changed: not asked again', calls() == n_calls)
m.osr_remove(st, fp_of(ROOT), 'dave')
tick_wait()
v = m.osr_view(st)
me = [n for n in v['nodes'] if n['name'] == 'n1'][0]
ok('4 taken away: the machine follows within a tick', me['status'] == 'applied' and len(me['ours']) == 1 and
   not os.path.exists(ANCH + '/otp-%s.pem' % fp_of(ROOT)[:16]), me)
# the other node answers: its own row
st.set_meta('oscerts:node:n2', json.dumps({'at': time.time(), 'hash': m.osr_want(st)['hash'], 'ok': False,
                                          'error': 'update-ca-trust ended with 1: p11-kit'}))
n2 = [n for n in m.osr_view(st)['nodes'] if n['name'] == 'n2'][0]
ok('4 the other node failed: failed, with its words', n2['status'] == 'failed' and 'p11-kit' in n2['why'], n2)
st.set_meta('oscerts:node:n2', json.dumps({'at': time.time(), 'hash': 'old', 'ok': True}))
n2 = [n for n in m.osr_view(st)['nodes'] if n['name'] == 'n2'][0]
ok('4 the other node at an older set: waiting', n2['status'] == 'waiting', n2)
open(FAILFLAG, 'w').write('x')
m.osr_add(st, ROOT, 'dave')
tick_wait()
me = [n for n in m.osr_view(st)['nodes'] if n['name'] == 'n1'][0]
ok('4 the tool failing here: failed, with its words', me['status'] == 'failed' and 'could not write' in me['why'], me)
os.unlink(FAILFLAG)
tick_wait()
me = [n for n in m.osr_view(st)['nodes'] if n['name'] == 'n1'][0]
ok('4 ...not tried again at every tick (ten minutes)', me['status'] == 'failed')
m.OSR['fail_at'] = 0
tick_wait()
me = [n for n in m.osr_view(st)['nodes'] if n['name'] == 'n1'][0]
ok('4 ...tried again later: as wanted', me['status'] == 'applied', me)
# A restart: the machine brought to the set again, whatever the rows say
os.unlink(ANCH + '/otp-%s.pem' % fp_of(ROOT)[:16])
m.OSR.update(done_hash=None, done_at=0.0, again_seen=None)
tick_wait()
ok('4 at a start: a file gone is put back', os.path.exists(ANCH + '/otp-%s.pem' % fp_of(ROOT)[:16]))
# Read again, asked from the pages
n_calls = calls()
m.OSR['done_at'] = time.time()
time.sleep(0.01)
m.osr_again(st)
before = m.OSR['done_at']
tick_wait()
ok('4 read again when asked', m.OSR['done_at'] > before)

# ==== 5. the API and the roles ==================================================================
Handler = next(x for x in vars(m).values() if isinstance(x, type) and hasattr(x, 'directory_recheck'))


class H(object):
    def __init__(self, sess, body=None):
        self._s, self._body, self.store, self.headers, self.route_path = sess, body or {}, st, {}, '/api/osroots'


for k in ('me', 'directory_recheck'):
    setattr(H, k, getattr(Handler, k))
H.DIR_CHECKED, H.DIR_CHECK_S = {}, 600
H.body = lambda self: self._body
H.session = lambda self, kind: dict(self._s) if self._s else None
H.client_ip = lambda self: '192.0.2.1'
st.add_account('ro1', 'readonly', 'Read-Only-Pass-265!', must_change=0)
st.add_account('fa1', 'fulladmin', 'Full-Admin-Pass-265!', must_change=0)
GET = m.ROUTES[('GET', '/api/osroots')]
POST = m.ROUTES[('POST', '/api/osroots')]
got = GET(H({'name': 'ro1'}))
ok('5 read-only may see it', isinstance(got, dict) and 'certs' in got and 'nodes' in got)
try:
    POST(H({'name': 'ro1'}, {'action': 'add', 'text': ROOT}))
    ok('5 read-only may not change it', False)
except m.ApiError as e:
    ok('5 read-only may not change it', '403' in str(getattr(e, 'status', '')) or 'full administrator' in str(e), e)
got = POST(H({'name': 'fa1'}, {'action': 'check', 'text': EXPIRED or WEAK}))
ok('5 check: what it is, nothing written, no PEM back', got['certs'] and 'pem' not in got['certs'][0])
try:
    POST(H({'name': 'fa1'}, {'action': 'add', 'text': open(C + '/leaf.key').read()}))
    ok('5 a private key: refused', False)
except m.ApiError as e:
    ok('5 a private key: refused', 'private key' in str(e), e)
got = POST(H({'name': 'fa1'}, {'action': 'refresh'}))
ok('5 refresh: asked', 'asked' in got['message'])

# ==== 6. the command line =======================================================================
os.environ['OTP_STAY_ROOT'] = '1'
def cli(*a):
    import io
    import contextlib
    buf = io.StringIO()
    rc = None
    try:
        with contextlib.redirect_stdout(buf):
            rc = m.cli_main(list(a))
    except SystemExit as e:
        rc = e.code
    return rc, buf.getvalue()


rc, txt = cli('--os-roots', '--json')
try:
    js = json.loads(txt)
except ValueError:
    js = {}
ok('6 otp --os-roots --json: the view', rc in (0, None) and 'certs' in js and 'nodes' in js, (rc, txt[:300]))
rc, txt = cli('--os-roots', '--no-color')
ok('6 otp --os-roots: the table, each node', rc in (0, None) and 'Acme Root CA' in txt and 'n1' in txt and
   'ca-certificates-2025' in txt, (rc, txt[:800]))
open(C + '/ec.der', 'wb').write(subprocess.run(['openssl', 'x509', '-in', C + '/ec.pem', '-outform', 'DER'],
                                               capture_output=True).stdout) if EC else None
rc, txt = cli('--os-roots-add', C + '/ec.der' if EC else C + '/weak.pem')
ok('6 --os-roots-add without --yes: shown, not done', rc not in (0, None) and len(m.osr_want(st)['certs']) == 2, (rc, txt[:400]))
rc, txt = cli('--os-roots-add', C + '/ec.der' if EC else C + '/weak.pem', '--yes')
ok('6 --os-roots-add FILE --yes (DER): added', rc in (0, None) and len(m.osr_want(st)['certs']) == 3, (rc, txt[:400]))
rc, txt = cli('--os-roots-add', C + '/leaf.pem', '--yes')
ok('6 --os-roots-add of a leaf: refused', rc not in (0, None) and 'CA:FALSE' in txt + str(rc), (rc, txt[:400]))
fpw = fp_of(EC if EC else WEAK)
rc, txt = cli('--os-roots-remove', fpw[:16], '--yes')
ok('6 --os-roots-remove FP --yes: taken away', rc in (0, None) and len(m.osr_want(st)['certs']) == 2, (rc, txt[:400]))
ok('6 the console has the list', "self.act('--os-roots')" in open(BUILD + '/parts/96_console.py').read())

# ==== 7. otp's own connections and the system's trust ===========================================
saved = dict(os.environ)
os.environ['SSL_CERT_FILE'] = '/somewhere/else.pem'
m.OSR_PY['fixed'] = ''
m.osr_python_fix()
ok('7 SSL_CERT_FILE given: left as given', os.environ['SSL_CERT_FILE'] == '/somewhere/else.pem' and not m.OSR_PY['fixed'])
os.environ.pop('SSL_CERT_FILE', None)
os.environ.pop('SSL_CERT_DIR', None)
import ssl as _ssl
real = _ssl.get_default_verify_paths
_ssl.get_default_verify_paths = lambda: type('P', (), {'cafile': None, 'capath': '/nonexistent/certs'})()
m.osr_python_fix()
ok('7 a Python whose OpenSSL looks where there is nothing: pointed at the system\'s list',
   m.OSR_PY['fixed'] and os.environ.get('SSL_CERT_FILE') == m.OSR_PY['fixed'], (m.OSR_PY, os.environ.get('SSL_CERT_FILE')))
_ssl.get_default_verify_paths = real
os.environ.clear()
os.environ.update(saved)

# ==== 8. the pages, the words, the docs =========================================================
js_ = open(V + '/web/assets/admin.js').read()
ok('8 admin.js: the card drawn with the certificates', 'function drawOsRoots' in js_ and 'osrLoad();' in js_)
ok('8 index.php: the card after the certificates from acme', open(V + '/web/admin/index.php').read().index('osr-host') >
   open(V + '/web/admin/index.php').read().index('web-push'))
ok('8 node --check admin.js', subprocess.run(['node', '--check', V + '/web/assets/admin.js']).returncode == 0)
ok('8 py_compile otp_web.py and otp.py', subprocess.run([sys.executable, '-m', 'py_compile', V + '/deploy/otp_web.py',
                                                          V + '/otp.py']).returncode == 0)
cs = json.load(open(V + '/web/lang/cs.json'))
srcs = {x['source'] for x in cs['strings'].values()} | {x['source'] for x in cs['patterns'].values()} | \
    {x['source'] for x in cs['rich'].values()}
for s_ in ('Trusted roots of the system', 'Add an authority', 'Read it again on every node', 'nothing added by otp',
           'Added by somebody else - otp leaves them as they are:', 'Add to the system\'s trust',
           'Take it out of the system\'s trust'):
    ok('8 cs.json has "%s"' % s_, s_ in srcs)
ok('8 docs: tls-and-vip.md has the section', 'Trusted roots of the system' in open(V + '/docs/tls-and-vip.md').read())

# The pages reach it (1.0.265): the route was missing from the PHP map, every page asked 404
_php = open(V + '/web/admin/index.php').read()
ok('the admin pages relay osroots (GET and POST maps)', _php.count("'osroots' => '/api/osroots'") == 2)
print('\n%d of %d passed' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
