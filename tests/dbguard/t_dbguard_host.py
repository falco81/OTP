# t_dbguard_host.py VERSION - root's actions only from rows otp signed (1.0.231), end to end with the root
# helper: two daemons over one database (as t_host.py), the guard switched on on both. A key for root's
# authorized_keys asked on the pages of node1 for node2: added there. The same asked by a row written straight
# into the database: not added. A system update and a restart asked by rows written straight: not run.
# Usage (as root): python3 t_dbguard_host.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, shutil, sqlite3, secrets

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.164'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = tempfile.mkdtemp(prefix='otp-host-')
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32810 + 10 * i,
               'radius_acct_port': 32811 + 10 * i, 'api_port': 29890 + i, 'node_name': name},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 29890 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1')}
# One database for both: node2's otp.db and key are node1's.
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-158!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
STOP = threading.Event()


def helper_loop(name):
    d = N[name]['dir']
    env = dict(os.environ, OTP_STATE=d, OTP_ROOT_AUTHKEYS=d + '/authorized_keys',
               OTP_OSUP_PM=HERE + '/fakepm.sh', OTP_VIP_NO_SERVICES='1',
               OTP_OSUP_LOCK=d + '/osup.lock')
    while not STOP.is_set():
        if any(os.path.exists(os.path.join(d, 'web', a)) for a in ('sshkeys.ask', 'osup.ask')):
            subprocess.run([sys.executable, '-I', V + '/deploy/otp_web.py'], env=env,
                           stdout=subprocess.DEVNULL, stderr=open(d + '/helper.err', 'a'))
        time.sleep(0.3)


procs = []
for name in N:
    threading.Thread(target=helper_loop, args=(name,), daemon=True).start()
    procs.append(subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=N[name]['env'],
                                  stdout=open(N[name]['dir'] + '/d.out', 'w'), stderr=subprocess.STDOUT))
atexit.register(lambda: (STOP.set(), [p.terminate() for p in procs], [p.wait(10) for p in procs]))
time.sleep(7)
TOK = {n: open(N[n]['dir'] + '/run/api-token').read().strip() for n in N}


def call(node, path, body=None, sess=None):
    h = {'X-Otp-Token': TOK[node], 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % N[node]['api'] + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def until(fn, secs=40):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.7)
    return None


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-158!'})
S = a['token']
ok('both nodes seen by node1', until(lambda: len(call('node1', '/api/sshkeys', None, S)[1].get('nodes') or []) == 2))


def keys(node):
    v = call('node1', '/api/sshkeys', None, S)[1]
    n = [x for x in v['nodes'] if x['name'] == node][0]
    return n



DBF = N['node1']['dir'] + '/otp.db'


def raw(sql, args=()):
    c = sqlite3.connect(DBF, timeout=30)
    try:
        cur = c.execute(sql, args); c.commit(); return cur.fetchall()
    finally:
        c.close()


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-158!'}); S1 = a['token']
_, a = call('node2', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-158!'}); S2 = a['token']
for n_, s_ in (('node1', S1), ('node2', S2)):
    c, x = call(n_, '/api/settings', {'settings': {'db_guard': 1}}, s_)
    ok('the guard switched on on %s: %s %s' % (n_, c, x.get('message', '')), c == 200)
# the daemons read config.json again
for p_ in procs:
    p_.send_signal(1)
time.sleep(4)
_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-158!'}); S1 = a.get('token') or S1


def keys(node):
    v = call('node1', '/api/sshkeys', None, S1)[1]
    n = [x for x in v.get('nodes') or [] if x['name'] == node]
    return n[0] if n else {}


work = tempfile.mkdtemp(prefix='otp-dgkey-')
subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'admin@laptop', '-f', work + '/k'], check=True)
subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'attacker@evil', '-f', work + '/e'], check=True)
pub = open(work + '/k.pub').read().strip()
evil = open(work + '/e.pub').read().strip()
c, x = call('node1', '/api/sshkeys', {'action': 'refresh', 'nodes': ['node1', 'node2']}, S1)
ok('read on both nodes with the guard on: %s' % c, c == 200 and until(lambda: all(keys(n).get('at') for n in ('node1', 'node2'))))
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': pub, 'nodes': ['node2']}, S1)
ok('a key asked on node1\'s pages for node2: %s' % c, c == 200)
ok('...added to node2\'s authorized_keys', until(lambda: 'admin@laptop' in (open(N['node2']['dir'] + '/authorized_keys').read() if os.path.exists(N['node2']['dir'] + '/authorized_keys') else '')))
raw("INSERT INTO meta (k, v) VALUES (?, ?)", ('host:sshkeys:want:node2@@node9',
    json.dumps([{'id': secrets.token_hex(6), 'do': 'add', 'line': evil, 'fp': '', 'last_ok': False, 'by': 'x', 'at': time.time()}])))
time.sleep(25)
ok('a key asked by a row written straight into the database: NOT added', 'attacker@evil' not in open(N['node2']['dir'] + '/authorized_keys').read())
raw("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", ('host:osup:plan',
    json.dumps({'id': 'evil1', 'order': ['node2'], 'reboot': 'auto', 'security': False, 'state': 'running', 'by': 'x', 'at': time.time()})))
raw("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", ('power:plan',
    json.dumps({'id': 'evil2', 'how': 'reboot', 'targets': ['node2'], 'order': ['node2'], 'at': time.time(), 'by': 'x'})))
time.sleep(20)
log2 = open(N['node2']['dir'] + '/d.out').read()
ok('a system update asked by a row written straight: not run', not os.path.exists(N['node2']['dir'] + '/web/osup.ask') and 'evil1' not in (open(N['node2']['dir'] + '/web/osup.ans').read() if os.path.exists(N['node2']['dir'] + '/web/osup.ans') else ''))
ok('...the refusals in the log', 'not written by otp' in log2 or 'not written by otp' in open(N['node2']['dir'] + '/otp.log').read() if os.path.exists(N['node2']['dir'] + '/otp.log') else 'not written by otp' in log2)
c, x = call('node1', '/api/hisec', None, S1)
ok('the security check lists what was refused', bool(((x or {}).get('guard') or {}).get('refused')) or any('not written by otp' in str(w) for w in (x or {}).get('warn') or []), x.get('guard'))
c, x = call('node1', '/api/sshkeys', {'action': 'drop', 'fp': keys('node2')['keys'][0]['fp'] if keys('node2').get('keys') else '', 'nodes': ['node2'], 'last_ok': True}, S1)
ok('a key dropped from the pages with the guard on: %s' % c, c == 200 and until(lambda: 'admin@laptop' not in open(N['node2']['dir'] + '/authorized_keys').read()))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
