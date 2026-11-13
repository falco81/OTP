"""t_krb_ha.py VERSION - 1.0.274: signing in to the pages with Windows (Kerberos) on the cluster of two
(tests/hasb sandbox: PostgreSQL replicated both ways, the VIP address by keepalived/VRRP), the
ticket handed to each node's daemon as its pages do:
  - the keytab put in on node a: node b has it too (sealed in the database), each node writes it
    out itself, the same bytes, and says so (meta kerberos:node:NAME);
  - signing in on node a, on node b and on the node holding the VIP address, with the role of the
    directory's groups; a sign-in made on one node is good on the other (one database);
  - a ticket used on one node refused on the other (the replay cache of the library is a node's
    own: the cluster's is in the database);
  - the node holding the VIP address taken away (keepalived and the daemon stopped): the VIP
    moves, a new ticket signs in there, the one used before the move is still refused;
  - the second step on, switched on node b: asked after Kerberos on node a too;
  - the keytab taken away on node b: gone from both nodes, nobody signs in with Kerberos.

Usage (root, the sandbox made and joined): python3 t_krb_ha.py VERSION
"""
import base64, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

HERE = '/home/claude/ws/tests/krb'
KDC = os.environ.get('KDC_DIR', '/tmp/claude-0/kdc2')
subprocess.run(['bash', HERE + '/kdc.sh', KDC], check=True, capture_output=True)
if not subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).stdout:
    subprocess.Popen([sys.executable, V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1.5)


def tok(person, host='otp.corpnet.loc'):
    r = subprocess.run([sys.executable, HERE + '/krbtok.py', KDC, person, host], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('no token: %s' % r.stderr)
    return r.stdout.strip()


def krb(n, token):
    return call(n, '/api/auth/kerberos', {'token': token}, sess=False)


SETUP = '''
try:
    st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
except Exception:
    pass
if not [d for d in st.directories() if d['name'] == 'MOCK']:
    st.directory_save({'name': 'MOCK', 'hosts': '127.0.0.1:3899', 'port': 389, 'tls': 'none',
                       'base': 'DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                       'bind_pw': 'the-otp-service-password', 'user_attr': 'sAMAccountName'})
print('ok')
''' % {'pw': ADMIN_PW}
ok('set up on node a: an administrator, the directory', in_node('a', SETUP).strip().endswith('ok'))
helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
for n in 'ab':
    up(n)
    login(n)
st_, got = call('a', '/api/settings', {'settings': {
    'admin_directory': 'MOCK', 'admin_group_full': 'CN=VPN_SUPPLIER_X,OU=Groups,DC=corpnet,DC=loc',
    'admin_group_readonly': 'CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc', 'admin_kerberos': 1,
    'login_tries': 100}})
ok('Kerberos switched on, on node a (%s)' % st_, st_ == 200, got)
raw = open(KDC + '/http.keytab', 'rb').read()
st_, got = call('a', '/api/kerberos', {'action': 'keytab', 'data': base64.b64encode(raw).decode()})
ok('the keytab put in on node a', st_ == 200 and got.get('keytab', {}).get('there'), got)
want = hashlib.sha256(raw).hexdigest()
KT = {n: in_node(n, 'print(otp.KRB_KEYTAB)').strip() for n in 'ab'}
ok('each node its own file (%s, %s)' % (KT['a'], KT['b']), KT['a'] != KT['b'])


def written(n):
    try:
        return hashlib.sha256(open(KT[n], 'rb').read()).hexdigest() == want
    except OSError:
        return False


for _ in range(60):
    if written('a') and written('b'):
        break
    time.sleep(1)
ok('the keytab written out by node a', written('a'))
ok('... and by node b, from the database (replicated, sealed)', written('b'))
ok('... 0600 on both', all(os.path.exists(KT[n]) and (os.stat(KT[n]).st_mode & 0o777) == 0o600 for n in 'ab'))
for _ in range(30):
    st_, v = call('b', '/api/kerberos')
    nodes = {x['name']: x for x in v.get('nodes') or []}
    if len(nodes) == 2 and all(x['file'] and x['same'] for x in nodes.values()):
        break
    time.sleep(1)
ok('node b\'s card: both nodes have it written, the library there (%s)' % sorted(nodes),
   len(nodes) == 2 and all(x['file'] and x['same'] and x['lib'] for x in nodes.values()), v.get('nodes'))
for _ in range(30):
    if call('b', '/api/health', sess=False)[1].get('kerberos'):
        break
    time.sleep(1)
ok('node b offers it on its sign-in page (health: kerberos)', call('b', '/api/health', sess=False)[1].get('kerberos'))

# -- each node
for n in 'ab':
    st_, got = krb(n, tok('falco'))
    ok('node %s: falco signs in with Kerberos, read only' % n, st_ == 200 and got.get('who', {}).get('role') == 'readonly', (st_, got))
st_, got = krb('b', tok('nested'))
ok('node b: nested signs in, full admin (a group within a group)', st_ == 200 and got.get('who', {}).get('role') == 'fulladmin', (st_, got))
token_b = got.get('token')
h = {'X-Otp-Token': halib.TOK.get('a', '')}
saved = dict(halib.SESS)
halib.SESS['a'] = token_b
st_, me = call('a', '/api/auth/whoami')
halib.SESS.update(saved)
ok('the sign-in made on node b is good on node a (one database)', st_ == 200 and (me.get('who') or {}).get('name') == 'nested', (st_, me))
t = tok('falco')
st_, got = krb('a', t)
ok('a ticket used on node a', st_ == 200, got)
st_, got = krb('b', t)
ok('... the same ticket on node b: refused (the cluster\'s replay cache)', st_ == 401 and 'used already' in (got.get('error') or ''), (st_, got))
st_, got = krb('b', tok('outsider'))
ok('node b: outsider (no group of a role): refused', st_ == 401, (st_, got))

# -- the VIP address
st_, got = call('a', '/api/web', {'action': 'vip_save', 'address': VIP + '/24', 'vrid': 62})
st_, got = call('a', '/api/web', {'action': 'vip_on'})
ka_on()
for _ in range(90):
    if vip_master():
        break
    time.sleep(1)
m = vip_master()
ok('the VIP address up (VRRP), held by node %s' % m, m is not None)
if m:
    st_, got = krb(m, tok('falco'))
    ok('on the node holding the VIP address (%s): signed in' % m, st_ == 200, (st_, got))
    before = tok('falco')
    st_, got = krb(m, before)
    ok('a ticket used there before the VIP moves', st_ == 200, got)
    other = 'b' if m == 'a' else 'a'
    ka_stop(m)
    stop(m)
    for _ in range(60):
        if vip_master() == other:
            break
        time.sleep(1)
    ok('the VIP address moved to node %s' % other, vip_master() == other, (vip_role('a'), vip_role('b')))
    st_, got = krb(other, tok('falco'))
    ok('a new ticket on the VIP address, now node %s: signed in' % other, st_ == 200, (st_, got))
    st_, got = krb(other, before)
    ok('the ticket used before the move, sent again after it: refused', st_ == 401 and 'used already' in (got.get('error') or ''), (st_, got))
    start(m)
    up(m)
    login(m)
    halib.KA_OFF.discard(m)
    for _ in range(60):
        if vip_master():
            break
        time.sleep(1)
    st_, got = krb(m, tok('falco'))
    ok('node %s back: signs in with Kerberos again' % m, st_ == 200, (st_, got))
else:
    ok('the VIP address could not be raised here - the rest of the VIP checks skipped', False)

# -- the second step, switched on on node b
st_, got = call('b', '/api/settings', {'settings': {'admin_2fa': 1}})
ok('the second step switched on, on node b', st_ == 200, got)
for _ in range(30):
    st_, got = krb('a', tok('falco'))
    if got.get('mfa'):
        break
    time.sleep(1)
ok('node a: after Kerberos the second step is asked (%s)' % got.get('mfa'), st_ == 200 and got.get('mfa') in ('enrol', 'check')
   and not got.get('who', {}).get('role'), (st_, got))
call('b', '/api/settings', {'settings': {'admin_2fa': 0}})

# -- taken away on node b
st_, got = call('b', '/api/kerberos', {'action': 'drop'})
ok('the keytab taken away on node b', st_ == 200 and not got.get('keytab', {}).get('there'), got)
for _ in range(60):
    if not os.path.exists(KT['a']) and not os.path.exists(KT['b']):
        break
    time.sleep(1)
ok('... gone from both nodes\' files', not os.path.exists(KT['a']) and not os.path.exists(KT['b']))
st_, got = krb('a', tok('falco'))
ok('... nobody signs in with Kerberos on node a', st_ == 401 and 'keytab' in (got.get('error') or ''), (st_, got))
for n in 'ab':                  # the API's token is new after a restart
    up(n)
    login(n)
st_, got = call('a', '/api/settings', {'settings': {'admin_kerberos': 0, 'admin_directory': '', 'admin_group_full': '',
                                                   'admin_group_readonly': ''}})
ok('off again (%s)' % st_, st_ == 200, got)
ok('replication healthy at the end on both nodes',
   all((call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab'))
done()
