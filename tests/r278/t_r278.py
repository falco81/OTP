# t_r278.py VERSION - 1.0.278 (hunt round 1): the functions of otp.py itself, on what they are given.
# - a switch is on as save_settings keeps it ("1.0", " 1", 1.0) - the guards read it the same way;
# - nobody left without a way in: no password at all with no way that works, refused on every road;
#   put in effect only from a sign-in made by a way that will still work;
# - pg_hba.conf written as root never through a link, the owner and the mode kept.
import os, sys, tempfile
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.278'
OTP_PY = os.environ.get('OTP_PY') or '/home/claude/build/out/otp-%s/otp.py' % V
src = open(OTP_PY).read()
g = {'__name__': 'otp_t', '__file__': OTP_PY}
exec(compile(src, 'otp.py', 'exec'), g)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


on = g['_setting_on']
ok('"1", "1.0", " 1", 1.0, True are on', all(on(v) for v in ('1', '1.0', ' 1', 1.0, True, 2)))
ok('"0", "", None, 0.0, "0.0", False are off', not any(on(v) for v in ('0', '', None, 0.0, '0.0', False)))
ok('the coerced value of "1.0" is on (what save_settings keeps)', on(g['check_setting']('admin_password_off', '1.0')))

C = g['CONFIG']
have = {'keytab': b'', 'cas': []}
g['krb_keytab_raw'] = lambda store: have['keytab']
g['cert_cas'] = lambda store: have['cas']
P = g['signin_ways_problem']
base = dict(admin_password_off=0, admin_kerberos=0, admin_cert=0, admin_directory='corp')
C.clear(); C.update(base)
ok('nothing about the ways in the batch: nothing asked', P(None, {'radius_port': 1812}) == '')
w = P(None, {'admin_password_off': 1})
ok('no password at all switched on with neither way on: refused, named (it would lie in wait)', w.startswith('admin_password_off:'), w)
ok('...switched off with neither way on: taken', P(None, {'admin_password_off': 0}) == '')
C['admin_password_off'] = 1
ok('...stored on already (an older version, no way on): the same value again is taken (an import, otp --set)', P(None, {'admin_password_off': 1}) == '')
C['admin_password_off'] = 0
w = P(None, {'admin_password_off': 1, 'admin_kerberos': 1})
ok('no password at all with Windows on and no keytab: refused (nobody could sign in)', 'nobody could sign in' in w, w)
have['keytab'] = b'kt'
ok('...with a keytab: taken (the command line, no sign-in to ask about)', P(None, {'admin_password_off': 1, 'admin_kerberos': 1}) == '')
w = P(None, {'admin_password_off': 1, 'admin_kerberos': 1}, how='', session=True)
ok('...from a sign-in made with a password: refused', 'sign in with Windows or a certificate first' in w, w)
ok('...from a sign-in made with Windows: taken', P(None, {'admin_password_off': 1, 'admin_kerberos': 1}, how='Kerberos', session=True) == '')
w = P(None, {'admin_password_off': 1, 'admin_cert': 1, 'admin_kerberos': 0}, how='certificate', session=True)
ok('signed in with a certificate, one batch switching Windows off and the certificate on with no authority: refused', w != '', w)
C.update(admin_password_off=1, admin_kerberos=1)
have['cas'] = []
w = P(None, {'admin_cert': 1, 'admin_kerberos': 0})
ok('in effect with Windows; the certificate on (no authority) and Windows off in one go: refused', 'nobody could sign in' in w, w)
w = P(None, {'admin_kerberos': '0.0', 'admin_cert': '1.0'})
ok('...the same written "0.0" and "1.0": refused too', w != '', w)
ok('...Windows off alone: the password comes back, taken', P(None, {'admin_kerberos': 0}) == '')
have['cas'] = ['ca']
ok('...with an authority: the certificate on and Windows off, taken', P(None, {'admin_cert': 1, 'admin_kerberos': 0}) == '')
C.clear(); C.update(base)

# pg_hba.conf
d = tempfile.mkdtemp(prefix='t-hba-')
hba = os.path.join(d, 'pg_hba.conf')
open(hba, 'w').write('local all all peer\n')
os.chmod(hba, 0o640)
g['pg_hba_write'](hba, 'host otp otp 192.0.2.0/24 scram-sha-256\nlocal all all peer\n', keep=hba + '.before-otp')
ok('written over a plain file, the mode kept', open(hba).read().startswith('host otp') and (os.stat(hba).st_mode & 0o777) == 0o640)
ok('...the old one kept beside it', open(hba + '.before-otp').read() == 'local all all peer\n')
victim = os.path.join(d, 'root-file')
open(victim, 'w').write('root\n')
link = os.path.join(d, 'pg_hba_link.conf')
os.symlink(victim, link)
try:
    g['pg_hba_write'](link, 'evil\n')
    refused = False
except OSError:
    refused = True
ok('a link where pg_hba.conf is: refused, the file it points at untouched', refused and open(victim).read() == 'root\n')
try:
    g['pg_hba_read'](link)
    refused = False
except OSError:
    refused = True
ok('...and not read through either', refused)
ok('no temporary file left behind', not [f for f in os.listdir(d) if f.startswith('.otp-hba-')])

# the CRL of a certificate nobody here issued is never fetched (the chain first)
import subprocess, pathlib
w = tempfile.mkdtemp(prefix='t-crl-')
def osl(*a):
    subprocess.run(['openssl'] + list(a), check=True, capture_output=True, cwd=w)
osl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '2', '-subj', '/CN=Ours')
open(w + '/ext', 'w').write('basicConstraints=CA:FALSE\nextendedKeyUsage=clientAuth\n'
                            'subjectAltName=otherName:1.3.6.1.4.1.311.20.2.3;UTF8:falco@corp.example\n'
                            'crlDistributionPoints=URI:http://10.9.8.7/inside.crl\n')
osl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'x.key', '-out', 'x.pem', '-days', '2', '-subj', '/CN=Anybody',
    '-addext', 'basicConstraints=CA:FALSE', '-addext', 'extendedKeyUsage=clientAuth',
    '-addext', 'subjectAltName=otherName:1.3.6.1.4.1.311.20.2.3;UTF8:falco@corp.example',
    '-addext', 'crlDistributionPoints=URI:http://10.9.8.7/inside.crl')
fetched = []
g['crl_fetch'] = lambda u: fetched.append(u) or (_ for _ in ()).throw(g['CertError']('fetched %s' % u))
g['cert_cas'] = lambda store: ['ca']
g['CERT_CA_FILE'] = pathlib.Path(w + '/ca.pem')
C['admin_cert_crl'] = 1
try:
    g['cert_check'](None, open(w + '/x.pem').read())
    why = 'taken'
except g['CertError'] as e:
    why = str(e)
ok('a certificate of somebody else\'s authority: refused for its chain, its CRL address never fetched',
   not fetched and 'not taken' in why, (why, fetched))

# a fetch from a backup destination held to the size it lists
F = g['RB_FETCH']
F.cap = 10
got = []
w = g['rb_capped_writer'](got.append)
w(b'12345'); w(b'12345')
try:
    w(b'1'); over = False
except ValueError:
    over = True
ok('a fetch held to its size: the byte past it stops it', over and b''.join(got) == b'1234512345', (over, got))
argv = g['rb_capped_argv'](['scp', 'a', 'b'])
import shutil as _sh
ok('the child that fetches gets a file size limit (prlimit)', argv[:2] == ['prlimit', '--fsize=10'] if _sh.which('prlimit') else argv == ['scp', 'a', 'b'], argv)
F.cap = None
ok('...nothing fetched: the command as it was', g['rb_capped_argv'](['scp', 'a']) == ['scp', 'a'])
print('ALL %d / %d' % (sum(R), len(R)))
