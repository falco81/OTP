# t_fixes.py VERSION - the fixes of 1.0.271, on otp.py of that version loaded as a module (a private
# state folder - the live installation is never touched):
#  - remote backups: every failure is a line and an event (DbError too), the old ones not taken away
#    said, ~ in an SCP/SFTP folder is the home folder, a wrong password that passes openssl's padding
#    check is the wrong password, a damaged archive is RbError, the token count is "?" when it moved;
#  - HA: no heartbeat in the other node's database is not alive; the link-TLS peer is the live node;
#    a rebuild refuses a missing ha_slot; a failed hba step is asked again an hour later;
#  - CA Issuers: NAT64 and the cloud's IPv6 metadata address refused, private addresses still asked;
#  - the pages' places taken only by somebody signed in.
import atexit, gzip, importlib.util, io, json, os, shutil, subprocess, sys, tarfile, tempfile, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.271'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t271-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx271', 'api_port': 29972}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
SRC = open(V + '/otp.py').read()

# -- CA Issuers
for url, why in (('http://[64:ff9b::a9fe:a9fe]/x', 'NAT64 form of the metadata address'),
                 ('http://[fd00:ec2::254]/latest/meta-data/', 'the IPv6 metadata address')):
    try:
        m.aia_url_ok(url)
        ok('a CA Issuers address at %s refused' % why, False, url)
    except ValueError:
        ok('a CA Issuers address at %s refused' % why, True)
try:
    m.aia_url_ok('http://10.0.0.5/ca.cer')
    ok('a private address (an AD CS on the inside) still asked', True)
except ValueError as e:
    ok('a private address (an AD CS on the inside) still asked', False, e)


# -- pruning that fails
class T(object):
    def __init__(self, names, bad):
        self.names, self.bad, self.gone = names, bad, []

    def list(self):
        return [{'name': n, 'size': 1} for n in self.names]

    def delete(self, n):
        if n in self.bad:
            raise OSError('permission denied')
        self.gone.append(n)


now = time.time()
names = ['otp-backup-otp-fx271-%s.tar.gz.enc' % time.strftime('%Y%m%d-%H%M%S', time.localtime(now - d * 86400))
         for d in range(4)]
t = T(names, {names[3]})
try:
    got = m.rb_retain(t, 2, 0, now=now, just=names[0])
    ok('a backup the server would not take away is said, not told as taken away', False, got)
except m.RbError as e:
    ok('a backup the server would not take away is said, not told as taken away',
       names[3] in str(e) and 'not taken away' in str(e) and names[2] in str(e), e)

# -- ~ in the folder
import re as _re
pat = _re.search(r"self\.dir = re\.sub\(r'(\^~\(/\+\|\$\))', ''", SRC)
ok('~ in an SCP/SFTP folder is the home folder', pat is not None)
if pat:
    for p_, want in (('~/otp', 'otp'), ('~', '.'), ('/srv/b', '/srv/b'), ('~x/b', '~x/b')):
        got = _re.sub(r'^~(/+|$)', '', p_).rstrip('/') or '.'
        ok('...%s is %s' % (p_, want), got == want, got)

# -- opening: a password that "opens" to something that is not a gzip, a damaged archive
W = TOP + '/w'
os.makedirs(W)


def lock(data, pw, out):
    r = subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', str(m.RB_ITER), '-md', 'sha256',
                        '-salt', '-out', out, '-pass', 'env:T271PW'], input=data, capture_output=True,
                       env=dict(os.environ, T271PW=pw))
    return r.returncode == 0


ok('a locked file made', lock(b'this is not a gzip at all, only text', 'pw-one', TOP + '/notgz.enc'))
w1 = tempfile.mkdtemp(dir=W)
try:
    m.rb_open(TOP + '/notgz.enc', 'pw-one', w1)
    ok('what the password opens to is not a backup: "the password does not open it"', False)
except m.RbError as e:
    ok('what the password opens to is not a backup: "the password does not open it"', 'password' in str(e), e)
except Exception as e:                                  # noqa: BLE001
    ok('what the password opens to is not a backup: an RbError', False, repr(e))
bad = gzip.compress(b'x' * 100)[:40] + b'\0' * 30
ok('a locked damaged archive made', lock(bad, 'pw-one', TOP + '/bad.enc'))
w2 = tempfile.mkdtemp(dir=W)
try:
    m.rb_open(TOP + '/bad.enc', 'pw-one', w2)
    ok('a damaged archive: RbError', False)
except m.RbError as e:
    ok('a damaged archive: RbError (not a 500)', 'damaged' in str(e), e)
except Exception as e:                                  # noqa: BLE001
    ok('a damaged archive: RbError (not a 500)', False, repr(e))
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as tf:
    i = tarfile.TarInfo('../evil')
    i.size = 1
    tf.addfile(i, io.BytesIO(b'x'))
ok('a locked archive with ../ made', lock(buf.getvalue(), 'pw-one', TOP + '/evil.enc'))
w3 = tempfile.mkdtemp(dir=W)
try:
    m.rb_open(TOP + '/evil.enc', 'pw-one', w3)
    ok('an archive with ../ still refused', False)
except m.RbError as e:
    ok('an archive with ../ still refused', 'may not have' in str(e), e)

# -- a backup that fails anywhere: a line and an event
store = m.Storage(m.open_db())
m.rb_targets = lambda s: [{'id': 't1', 'name': 'dest', 'kind': 'folder', 'path': TOP + '/dest', 'enabled': True}]
m.rb_password = lambda: 'pw-one'


class DbBroke(Exception):
    pass


def broke(*a, **k):
    raise m.DbError('the database went away during the copy') if hasattr(m, 'DbError') else DbBroke('x')


m.rb_build = broke
try:
    run = m.rb_run(store, 'test')
    ok('the copy failing (DbError): kept as the run\'s error', not run['ok'] and 'went away' in run.get('error', ''), run)
except Exception as e:                                  # noqa: BLE001
    ok('the copy failing (DbError): kept as the run\'s error', False, repr(e))
h = m.rb_history(store)
ok('...a line in the backups sent', h and 'went away' in (h[0].get('error') or ''), h[:1])
ev = store.db.rows("SELECT * FROM events ORDER BY id DESC LIMIT 3") if True else []
ok('...and an event', any('went away' in str(dict(r)) for r in ev), [dict(r) for r in ev][:1])
ok('the token count is "?" when it moved during the copy', "tokens = '?'" in SRC and 'if tokens != before' in SRC)

# -- HA
m.CONFIG.pop('ha_slot', None)
try:
    m.ha_slot_set()
    ok('a rebuild without ha_slot refused', False)
except ValueError as e:
    ok('a rebuild without ha_slot refused', 'ha_slot' in str(e))
m.CONFIG['ha_slot'] = 2
ok('...with it: its value', m.ha_slot_set() == 2)


class Far(object):
    def __init__(self, v):
        self.v = v

    def value(self, *a):
        return self.v

    def close(self):
        pass


for v, want, why in ((None, False, 'no heartbeat there'), ('{}', False, 'a heartbeat without a time'),
                     ('{"at": "x"}', False, 'a time that does not read'),
                     (json.dumps({'at': time.time()}), True, 'a heartbeat just now'),
                     (json.dumps({'at': time.time() - 600}), False, 'an old heartbeat')):
    m.PEER_THERE.clear()
    m.ha_peer_db = lambda v=v: Far(v)
    ok('the other node\'s database, %s: %s' % (why, 'alive' if want else 'not alive'),
       m._peer_alive_there('nodeb') is want)

m.ha_nodes = lambda s: [{'name': 'fx271', 'me': True, 'alive': True, 'at': now},
                        {'name': 'aold', 'me': False, 'alive': False, 'at': now - 86400},
                        {'name': 'znew', 'me': False, 'alive': True, 'at': now}]
ok('the link\'s other node is the live one, not the first by name', m.hatls_peer_name(store) == 'znew')
ok('a failed hba step asked again an hour later', "st.get('failed_step') == 'hba'" in SRC and
   "said='the last step asked again'" in SRC)
ok('the pages\' places only for somebody signed in', 'if self._signed_in():\n                slot = page_slot(' in SRC)

# -- round 2: SSH codes held after many wrong in a row, a token's copy with numbers that are not
now = time.time()
ok('SSH token: 19 wrong in a row not held', m.sshotp_held({'fails': 19, 'failed_at': now}, now) == 0)
ok('...20 wrong: held 15 minutes', 14 * 60 < m.sshotp_held({'fails': 20, 'failed_at': now}, now) <= 15 * 60)
ok('...30 wrong: 30 minutes', 29 * 60 < m.sshotp_held({'fails': 30, 'failed_at': now}, now) <= 30 * 60)
ok('...never more than a day', m.sshotp_held({'fails': 900, 'failed_at': now}, now) <= 86400)
ok('...over once its time passed', m.sshotp_held({'fails': 20, 'failed_at': now - 16 * 60}, now) == 0)
for v, want in ((float('inf'), None), ('yesterday', None), (1e400, None), (-5, None), (True, None),
                ('1700000000', 1700000000.0), (None, None)):
    ok('a copy\'s number %r read as %r' % (v, want), m._when_read(v) == want)
SEC = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
try:
    said = m.token_restore(store, {'name': 'fut271', 'state': 'active', 'kind': 'totp', 'secret': SEC,
                                   'last_step': int(now // 30) + 100000, 'created': 'Infinity',
                                   'activated': 'yesterday', 'last_used': float('inf')}, 'test')
    row = store.db.row('SELECT * FROM tokens WHERE name = ?', ('fut271',))
    ok('a copy with a step from the future: put back, the step not ahead of now',
       row and int(row['last_step']) <= int(now // 30) + 2, dict(row) if row else said)
    ok('...its times that are not times not kept as text', row and isinstance(row['activated'], (int, float)) and
       row['last_used'] is None and isinstance(row['created'], (int, float)), dict(row) if row else None)
except Exception as e:                                  # noqa: BLE001
    ok('a copy with a step from the future: put back', False, repr(e))
try:
    m.token_restore(store, {'name': 'inf271', 'state': 'active', 'kind': 'totp', 'secret': SEC,
                            'window_steps': float('inf')}, 'test')
    ok('window_steps infinite: refused, not a 500', False)
except (ValueError, TypeError, OverflowError):
    ok('window_steps infinite: refused as the page catches it', True)
store.set_meta('fw:trial', json.dumps({'id': 'x1', 'at': now - 900, 'until': now - 5, 'min': 10, 'was': {}}))
try:
    m.fw_trial_answer(store, 'keep', 'test')
    ok('a firewall change past its time is not "kept"', False)
except ValueError as e:
    ok('a firewall change past its time is not "kept"', 'over' in str(e))
store.set_meta('fw:trial', json.dumps({'id': 'x2', 'at': now, 'until': now + 600, 'min': 10, 'was': {}}))
ok('...one within its time still kept', m.fw_trial_answer(store, 'keep', 'test') == 'kept')

# -- round 2: the root helper and the host
spec2 = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W2 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(W2)
saved = '\n'.join(['*filter', ':INPUT ACCEPT [0:0]', ':FORWARD ACCEPT [0:0]', ':OUTPUT ACCEPT [10:900]',
                   '[120:9000] -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT',
                   '[0:0] -A INPUT -p tcp -m tcp --dport 22 -j ACCEPT',
                   '[3:180] -A INPUT -j REJECT --reject-with icmp-host-prohibited', 'COMMIT', ''])
out = W2.fw_into(saved, ['-A %s -p udp --dport 1812 -j ACCEPT' % W2.FW_CHAIN], True).split('\n')
jump = out.index('-A INPUT -j %s' % W2.FW_CHAIN)
rej = next(i for i, l in enumerate(out) if 'REJECT' in l)
ok('a firewall file saved with counters: the jump to otp\'s chain before the REJECT', jump < rej, out)
again = W2.fw_into('\n'.join(out), ['-A %s -p udp --dport 1812 -j ACCEPT' % W2.FW_CHAIN], True)
ok('...the same written again', again == '\n'.join(out))
plain = saved.replace('[120:9000] ', '').replace('[0:0] -A', '-A').replace('[3:180] ', '')
out2 = W2.fw_into(plain, [], True).split('\n')
ok('...and without counters as before', out2.index('-A INPUT -j %s' % W2.FW_CHAIN) <
   next(i for i, l in enumerate(out2) if 'REJECT' in l))
b6 = {'ipv6.method': 'manual', 'ipv6.addresses': '2001:db8::10/64, 2001:db8::20/64'}
ok('a network change keeps the second IPv6 address set by hand',
   W2.net_addrs6_after(b6, '2001:db8::11/64') == ['2001:db8::11/64', '2001:db8::20/64'], W2.net_addrs6_after(b6, '2001:db8::11/64'))
ok('...the first one replaced when it stays', W2.net_addrs6_after(b6, '2001:db8::10/64') == ['2001:db8::10/64', '2001:db8::20/64'])
ok('...from automatic only the new one', W2.net_addrs6_after({'ipv6.method': 'auto'}, '2001:db8::11/64') == ['2001:db8::11/64'])
m.host_nodes = lambda s: ['fx271']
m.sshd_conf = lambda s: {'manage': True, 'port': 2222, 'hash': 'new'}
m.sshd_now = lambda s, n: {'hash': 'old', 'values': {'port': '22 2200'}, 'before_port': '22 2200'}
ok('sshd on two ports, a change not kept: both of them stay open', m.sshd_ports_open(store) == [22, 2200, 2222],
   m.sshd_ports_open(store))
m.CONFIG.update(ha_mode='replicated', ha_peer='localhost')
m.ntp_conf = lambda s: {'manage': True, 'peers': True, 'servers': [], 'allow': []}
ok('the other node by name: chrony is told its address', m.ntp_desired(store)['peers'] in (['127.0.0.1'], ['::1']),
   m.ntp_desired(store))
m.CONFIG.pop('ha_mode', None)

print('ALL %d / %d' % (sum(R), len(R)))
