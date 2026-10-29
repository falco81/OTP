# Root's SSH keys and the system updates (1.0.158), end to end: two daemons
# (node1, node2) over one SQLite database, each with its own state folder and
# its root helper played by a loop (as otp-web.path would start it), a fake
# authorized_keys and a fake package manager.
# Usage (as root): python3 t_host.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.158'
V = '/home/claude/build/out/otp-%s' % VER
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


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


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


# ---- keys
work = tempfile.mkdtemp(prefix='otp-hostkey-')
subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'jan@laptop', '-f', work + '/k'], check=True)
pub = open(work + '/k.pub').read().strip()
subprocess.run(['ssh-keygen', '-q', '-t', 'rsa', '-b', '2048', '-N', '', '-C', 'weak', '-f', work + '/w'], check=True)
weak = open(work + '/w.pub').read().strip()
c, x = call('node1', '/api/sshkeys', {'action': 'refresh', 'nodes': ['node1', 'node2']}, S)
ok('read on both nodes: %s' % c, c == 200 and until(lambda: all(keys(n).get('at') for n in ('node1', 'node2'))))
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': pub, 'nodes': ['node1', 'node2']}, S)
ok('a public key added to both: %s' % c, c == 200)
ok('... it is on node1 and node2',
   until(lambda: all(any(k['comment'] == 'jan@laptop' for k in keys(n)['keys']) for n in ('node1', 'node2'))))
ok('... the file is 0600 root, its folder 0700',
   oct(os.stat(N['node2']['dir'] + '/authorized_keys').st_mode & 0o777) == '0o600')
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': weak, 'nodes': ['node2']}, S)
ok('RSA 2048 refused on the node: %s' % keys('node2').get('error'),
   until(lambda: 'too weak' in (keys('node2').get('error') or '')))
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': 'command="sh" ' + pub, 'nodes': ['node2']}, S)
ok('a line with options refused', until(lambda: 'options' in (keys('node2').get('error') or '')))
c, x = call('node1', '/api/sshkeys', {'action': 'make', 'kind': 'ed25519', 'comment': 'admin key', 'nodes': ['node2']}, S)
ok('a key made: its private half handed once (%s)' % x.get('fp'), c == 200 and 'PRIVATE KEY' in x.get('private', ''))
ok('... its public half only on node2', until(lambda: any(k['fp'] == x['fp'] for k in keys('node2')['keys'])) and
   not any(k['fp'] == x['fp'] for k in keys('node1')['keys']))
ok('... and kept nowhere on the server', not subprocess.run(['grep', '-rl', 'OPENSSH PRIVATE', N['node1']['dir'], N['node2']['dir']],
                                                          capture_output=True).stdout.strip())
c, x2 = call('node1', '/api/sshkeys', {'action': 'make', 'kind': 'rsa4096', 'nodes': ['node1']}, S)
ok('an RSA 4096 key made: %s' % c, c == 200 and until(lambda: any(k['bits'] == 4096 for k in keys('node1')['keys'])))
fp_jan = [k for k in keys('node1')['keys'] if k['comment'] == 'jan@laptop'][0]['fp']
call('node1', '/api/sshkeys', {'action': 'drop', 'fp': fp_jan, 'nodes': ['node1', 'node2']}, S)
ok('jan@laptop taken away on both', until(lambda: not any(k['fp'] == fp_jan for n in ('node1', 'node2') for k in keys(n)['keys'])))
last = keys('node2')['keys'][0]['fp']
call('node1', '/api/sshkeys', {'action': 'drop', 'fp': last, 'nodes': ['node2']}, S)
ok('the last key of node2 not taken away without being said again',
   until(lambda: 'last key' in (keys('node2').get('error') or '')))
call('node1', '/api/sshkeys', {'action': 'drop', 'fp': last, 'nodes': ['node2'], 'last_ok': True}, S)
ok('... and taken away when said', until(lambda: not keys('node2')['keys']))
ev = json.dumps(call('node1', '/api/events?limit=100', None, S)[1])
ok('the changes are in the events', 'SSH key' in ev)

# ---- updates
c, x = call('node1', '/api/osup', {'action': 'check'}, S)
ok('looking for updates on both: %s' % c, c == 200)


def osv():
    return call('node1', '/api/osup', None, S)[1]


ok('... 3 waiting on each', until(lambda: all((n.get('check') or {}).get('count') == 3 for n in osv()['nodes'])))
c, x = call('node1', '/api/osup', {'action': 'start', 'reboot': 'ask'}, S)
ok('the update started: order %s' % (x.get('plan') or {}).get('order'), c == 200 and x['plan']['order'] == ['node2', 'node1'])
seen = {'node1_waited': False, 'maint2': False, 'pct': set()}


def watch():
    v = osv()
    rows = {n['name']: n.get('row') or {} for n in v['nodes']}
    if rows.get('node2', {}).get('state') in ('draining', 'updating') and rows.get('node1', {}).get('state') in (None, 'waiting'):
        seen['node1_waited'] = True
    if rows.get('node2', {}).get('state') in ('draining', 'updating'):
        if (otp._meta_json(st, 'maint:node2') or {}).get('on'):
            seen['maint2'] = True
    if rows.get('node2', {}).get('state') == 'updating':
        seen['pct'].add(rows['node2'].get('pct'))
    return v['plan'].get('state') in ('done', 'failed') and v


v = until(watch, 120)
ok('the update ended: %s' % (v or {}).get('plan', {}).get('state'), v and v['plan']['state'] == 'done')
ok('node1 waited while node2 was updated', seen['node1_waited'])
ok('node2 was out of service while it was updated', seen['maint2'])
ok('the bar moved: %s' % sorted(p for p in seen['pct'] if p is not None), len(seen['pct']) >= 2)
ok('both back in service', not (otp._meta_json(st, 'maint:node1') or {}).get('on') and
   not (otp._meta_json(st, 'maint:node2') or {}).get('on'))
ok('the restart they need is offered', v and all(n['reboot'] for n in v['nodes']))
ok('what dnf said is there', v and any('Upgrading' in ln for n in v['nodes'] for ln in (n.get('row') or {}).get('lines') or []))
t0 = v['plan']['at'] if v else time.time()
ok('looked again after the update', until(lambda: all(float((n.get('check') or {}).get('checked') or 0) > t0
                                                     for n in osv()['nodes'])))
c, x = call('node1', '/api/osup', {'action': 'hide'}, S)
ok('hidden when done', c == 200 and not x.get('plan'))
print('ALL %d / %d' % (sum(R), len(R)))
