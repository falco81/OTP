# t_ad2025.py VERSION - domain controllers on Windows Server 2025 (1.0.267):
#  - a bind refused with result 8 (strongerAuthRequired, LDAP signing) / 13 is said as what to do;
#  - servers given by address while the certificate is checked are found (ldap_ip_hosts), and said
#    by GET /api/directories (ip_hosts), the security check and otp --directories;
#  - plain LDAP is said there too; a directory by name, or with the check off, says nothing.
# A private state folder (OTP_STATE) - the live installation is never touched.
import os, sys, json, socket, threading, subprocess, tempfile, shutil, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.267'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]))


TOP = tempfile.mkdtemp(prefix='t267-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
os.makedirs(TOP + '/run')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32950,
           'radius_acct_port': 32951, 'api_port': 29951, 'node_name': 't267'}, open(TOP + '/config.json', 'w'))
ENV = {'OTP_STATE': TOP, 'OTP_CONFIG': TOP + '/config.json', 'OTP_LOGDIR': TOP, 'OTP_RUN': TOP + '/run',
       'OTP_STAY_ROOT': '1'}
os.environ.update(ENV)
sys.path.insert(0, V); sys.argv = ['x']
import otp
assert str(otp.STATE_DIR) == TOP, otp.STATE_DIR
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)

# ---- which servers are given by address -------------------------------------------------
f = otp.ldap_ip_hosts
ok('LDAPS, checked, two addresses and a name: the addresses',
   f({'tls': 'ldaps', 'verify': 1, 'hosts': '10.0.0.10, dc2.example.local, 10.0.0.12'}) == ['10.0.0.10', '10.0.0.12'])
ok('STARTTLS, an address with a port and an IPv6 one in brackets',
   f({'tls': 'starttls', 'verify': 1, 'hosts': '10.0.0.10:389, [fd00::10]:389, fd00::11'}) ==
   ['10.0.0.10:389', '[fd00::10]:389', 'fd00::11'])
ok('names only: nothing', f({'tls': 'ldaps', 'verify': 1, 'hosts': 'dc1.example.local,dc2.example.local'}) == [])
ok('plain LDAP: nothing (no certificate to check - said as plain LDAP instead)',
   f({'tls': 'none', 'verify': 1, 'hosts': '10.0.0.10'}) == [])
ok('the certificate not checked: nothing', f({'tls': 'ldaps', 'verify': 0, 'hosts': '10.0.0.10'}) == [])
ok('a name that looks like digits is a name', f({'tls': 'ldaps', 'verify': 1, 'hosts': '10.0.0.10.example.local'}) == [])

# ---- a domain controller asking for LDAP signing ------------------------------------------
def ber(tag, body):
    n = len(body)
    ln = bytes([n]) if n < 128 else (b'\x81' + bytes([n]) if n < 256 else b'\x82' + n.to_bytes(2, 'big'))
    return bytes([tag]) + ln + body


def fake_dc(code, said):
    s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(4)

    def serve():
        while True:
            try:
                c, _ = s.accept()
            except OSError:
                return
            try:
                data = c.recv(65536)
                mid = data[4] if data[:1] == b'\x30' else 1      # the message id (short form)
                res = ber(0x0a, bytes([code])) + ber(0x04, b'') + ber(0x04, said.encode())
                c.sendall(ber(0x30, ber(0x02, bytes([mid])) + ber(0x61, res)))
                c.recv(1024)
            except OSError:
                pass
            finally:
                c.close()
    threading.Thread(target=serve, daemon=True).start()
    return s, s.getsockname()[1]


AD8 = ('00002028: LdapErr: DSID-0C090259, comment: The server requires binds to turn on integrity '
       'checking if SSL\\TLS are not already active on the connection, data 0, v4f7c\x00')
s8, p8 = fake_dc(8, AD8)
try:
    otp.Ldap('127.0.0.1', p8, 'none', timeout=5).open().bind('CN=svc,DC=example,DC=local', 'x')
    ok('result 8: refused', False)
except otp.LdapError as e:
    ok('result 8 (strongerAuthRequired) said as what to do: LDAP signing, LDAPS or STARTTLS',
       e.code == 8 and 'LDAP signing' in str(e) and 'LDAPS or STARTTLS' in str(e), str(e))
    ok('...the directory\'s own words kept for the tooltip, without the NUL', 'integrity checking' in e.whole()
       and '\x00' not in e.whole(), e.whole())
s13, p13 = fake_dc(13, 'confidentiality required')
try:
    otp.Ldap('127.0.0.1', p13, 'none', timeout=5).open().bind('CN=svc,DC=example,DC=local', 'x')
    ok('result 13: refused', False)
except otp.LdapError as e:
    ok('result 13 (confidentialityRequired) said too', e.code == 13 and 'LDAPS or STARTTLS' in str(e), str(e))
ok('8 is not "another server may" - every controller of the domain asks the same',
   8 not in otp.LDAP_TRY_ANOTHER and 13 not in otp.LDAP_TRY_ANOTHER)
# Through Directory too: the reading account's bind refused with 8 says it, not "the directory said 8".
st.directory_save({'name': 'AD-plain', 'hosts': '127.0.0.1', 'port': p8, 'tls': 'none', 'base': 'DC=example,DC=local',
                   'bind_dn': 'CN=svc,DC=example,DC=local', 'bind_pw': 'Reading-Pass-1!', 'verify': 1, 'enabled': 1})
row = st.directory('AD-plain', with_secret=True)
try:
    d = otp.Directory(row)
    d.find_user('alice') if hasattr(d, 'find_user') else d.lookup('alice')
    ok('the reading account refused: said', False, 'nothing raised')
except otp.LdapError as e:
    ok('the reading account refused with 8: said as LDAP signing, not as a number',
       'LDAP signing' in str(e) and 'said 8' not in str(e), str(e))
except Exception as e:                                  # noqa: BLE001
    ok('the reading account refused with 8: said as LDAP signing', 'LDAP signing' in str(e), repr(e)[:300])

# ---- said where it is looked at -----------------------------------------------------------
st.directory_save({'name': 'AD-ip', 'hosts': '10.0.0.10, dc2.example.local', 'port': 636, 'tls': 'ldaps',
                   'base': 'DC=example,DC=local', 'bind_dn': '', 'bind_pw': '', 'verify': 1, 'enabled': 1})
st.directory_save({'name': 'AD-good', 'hosts': 'dc1.example.local, dc2.example.local', 'port': 636, 'tls': 'ldaps',
                   'base': 'DC=example,DC=local', 'bind_dn': '', 'bind_pw': '', 'verify': 1, 'enabled': 1})
warn = otp.hisec_findings(st)['warn']
words = [w['what'] for w in warn]
ok('the security check: the directory given by address, with the address',
   any('AD-ip' in w and '10.0.0.10' in w and 'name' in w for w in words), words)
ok('the security check: the directory over plain LDAP, Windows Server 2025 named',
   any('AD-plain' in w and 'plain LDAP' in w and 'Windows Server 2025' in w for w in words), words)
ok('the security check: nothing of the directory by name', not any('AD-good' in w for w in words), words)


def cli(*a):
    return subprocess.run([sys.executable, V + '/otp.py'] + list(a), capture_output=True, text=True,
                          env=dict(os.environ, **ENV, NO_COLOR='1'), timeout=120)


g = cli('--api', 'GET', '/api/directories')
try:
    dirs = {x['name']: x for x in json.loads(g.stdout)['directories']}
except (ValueError, KeyError):
    dirs = {}
ok('GET /api/directories: ip_hosts of each', dirs.get('AD-ip', {}).get('ip_hosts') == ['10.0.0.10'] and
   dirs.get('AD-good', {}).get('ip_hosts') == [] and dirs.get('AD-plain', {}).get('ip_hosts') == [],
   g.stdout[-400:] + g.stderr[-400:])
ok('...and no reading password in it', 'Reading-Pass-1!' not in g.stdout)
g = cli('--directories')
ok('otp --directories: the address said, with what to do', 'AD-ip: servers given by address (10.0.0.10)' in g.stdout
   and 'FQDN' in g.stdout, g.stdout[-600:] + g.stderr[-300:])
ok('otp --directories: plain LDAP said', 'AD-plain: plain LDAP' in g.stdout, g.stdout[-600:])
ok('otp --directories: nothing of the one by name', 'AD-good:' not in g.stdout, g.stdout[-600:])
g = cli('--directories', '--json')
try:
    j = {x['name']: x for x in json.loads(g.stdout)}
except (ValueError, TypeError, KeyError):
    j = {}
ok('otp --directories --json: ip_hosts', j.get('AD-ip', {}).get('ip_hosts') == ['10.0.0.10'], g.stdout[-300:])
s8.close(); s13.close()
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
