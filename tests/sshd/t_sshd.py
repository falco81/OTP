# The SSH server and the notices (1.0.163), end to end: two daemons over one
# SQLite database, each with its own /etc/ssh and /etc in a folder (the real
# sshd -t and -T read them), its root helper played by a loop.
# Usage (as root): python3 t_sshd.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.163'
V = '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-sshd-')
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    for sub in ('run', 'web', 'ssh/sshd_config.d', 'etc'):
        os.makedirs(os.path.join(d, sub))
    if name == 'node1':
        os.makedirs(d + '/etc/issue.d'); os.makedirs(d + '/etc/motd.d')
    open(d + '/etc/issue', 'w').write('\\S\nKernel \\r on \\m\n')
    open(d + '/etc/motd', 'w').write('welcome\n')
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', d + '/ssh/host_key'], check=True)
    open(d + '/ssh/sshd_config', 'w').write('Include %s/ssh/sshd_config.d/*.conf\nHostKey %s/ssh/host_key\n'
                                             'PermitRootLogin yes\nPasswordAuthentication yes\n' % (d, d))
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 34810 + 10 * i,
               'radius_acct_port': 34811 + 10 * i, 'api_port': 30090 + i, 'node_name': name},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 30090 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-163!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
STOP = threading.Event()


def henv(name):
    d = N[name]['dir']
    return dict(os.environ, OTP_STATE=d, OTP_ROOT_AUTHKEYS=d + '/authorized_keys', OTP_VIP_NO_SERVICES='1',
                OTP_SSH_DIR=d + '/ssh', OTP_ETC=d + '/etc')


def helper_loop(name):
    d = N[name]['dir']
    while not STOP.is_set():
        if any(os.path.exists(os.path.join(d, 'web', a)) for a in ('sshkeys.ask', 'sshd.ask')):
            subprocess.run([sys.executable, '-I', V + '/deploy/otp_web.py'], env=henv(name),
                           stdout=subprocess.DEVNULL, stderr=open(d + '/helper.err', 'a'))
        time.sleep(0.3)


procs = []
for name in N:
    threading.Thread(target=helper_loop, args=(name,), daemon=True).start()
    procs.append(subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=N[name]['env'],
                                  stdout=open(N[name]['dir'] + '/d.out', 'w'), stderr=subprocess.STDOUT))
atexit.register(lambda: (STOP.set(), [p.terminate() for p in procs]))
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
        with urllib.request.urlopen(req, timeout=60) as r:
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


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-163!'})
S = a['token']
view = lambda: call('node1', '/api/sshd', None, S)[1]
node = lambda n: [x for x in view()['nodes'] if x['name'] == n][0]
call('node1', '/api/sshd', {'action': 'refresh'}, S)
ok('both nodes read: sshd on port 22, root with a password', until(
    lambda: all((x['now'].get('values') or {}).get('port') == '22' and x['now'].get('dropins')
                for x in view()['nodes'])))
WANT = {'manage': True, 'permit_root': 'prohibit-password', 'password': False, 'port': 22,
        'tries': 3, 'trial_min': 5}
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': WANT}, S)
ok('saved: %s' % c, c == 200)
ok('refused on both: root has no key and passwords would be off',
   until(lambda: all(x['state'] == 'failed' and 'no SSH key' in (x['now'].get('error') or '')
                     for x in view()['nodes'])))
ok('... sshd left as it was', not os.path.exists(N['node1']['dir'] + '/ssh/sshd_config.d/00-otp.conf'))
pub = subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', TOP + '/k'], check=True) and \
    open(TOP + '/k.pub').read().strip()
call('node1', '/api/sshkeys', {'action': 'add', 'line': pub, 'nodes': ['node1', 'node2']}, S)
time.sleep(3)
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': dict(WANT, port=2222, notice='Authorised use only.\nEverything is logged.',
                                                                  notice_ssh=True, notice_console=True, notice_motd=True)}, S)
ok('with a key, saved again: %s' % c, c == 200)
ok('put in on both, on trial', until(lambda: all(x['state'] == 'trial' for x in view()['nodes'])))
v1 = node('node1')['now']['values']
ok('sshd -T says: port 2222, no passwords, root by key (%s)' % v1,
   v1.get('port') == '2222' and v1.get('passwordauthentication') == 'no' and
   v1.get('permitrootlogin') in ('prohibit-password', 'without-password') and v1.get('maxauthtries') == '3')
ok('... the banner for SSH', 'otp-banner' in v1.get('banner', '') and
   'Authorised' in open(N['node1']['dir'] + '/ssh/otp-banner').read())
ok('... the console notice: issue.d on node1, /etc/issue kept beside it on node2',
   'Authorised' in open(N['node1']['dir'] + '/etc/issue.d/otp.issue').read() and
   'Authorised' in open(N['node2']['dir'] + '/etc/issue').read() and
   'Kernel' in open(N['node2']['dir'] + '/etc/issue.otp-before').read())
ok('... after sign-in: motd.d on node1, /etc/motd on node2',
   'Everything' in open(N['node1']['dir'] + '/etc/motd.d/otp').read() and
   'Everything' in open(N['node2']['dir'] + '/etc/motd').read())
ok('the drop-in is 0600', oct(os.stat(N['node1']['dir'] + '/ssh/sshd_config.d/00-otp.conf').st_mode & 0o777) == '0o600')
rules = [r for a in otp.fw_auto(st, 'node1') if a['key'] == 'ssh' for r in a['rules']]
ok('the firewall lets 22 and 2222 in while on trial: %s' % sorted({r['port'] for r in rules}),
   {r['port'] for r in rules} == {'22', '2222'})
c, x = call('node1', '/api/sshd', {'action': 'keep'}, S)
ok('kept: %s' % c, c == 200 and until(lambda: all(x['state'] == 'done' for x in view()['nodes'])))
ok('... the trial over on both', not os.path.exists(N['node2']['dir'] + '/ssh/.otp-sshd-trial.json'))
rules = [r for a in otp.fw_auto(st, 'node1') if a['key'] == 'ssh' for r in a['rules']]
ok('the firewall now lets only 2222 in: %s' % sorted({r['port'] for r in rules}), {r['port'] for r in rules} == {'2222'})
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': dict(WANT, allow_users='admin')}, S)
ok('AllowUsers without root refused: %s' % c, c == 400)
# A change not kept, put back by asking.
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': dict(WANT, port=2200, password=True)}, S)
until(lambda: all(x['state'] == 'trial' for x in view()['nodes']))
call('node1', '/api/sshd', {'action': 'back'}, S)
ok('put back by asking: both went back', until(lambda: all(x['state'] == 'back' for x in view()['nodes'])))
ok('... sshd on 2222 again', until(lambda: node('node2')['now'].get('values', {}).get('port') == '2222'))
# A change not kept, put back by its timer (the helper's own: run here by hand).
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': dict(WANT, port=2300)}, S)
until(lambda: node('node2')['state'] == 'trial')
subprocess.run([sys.executable, '-I', V + '/deploy/otp_web.py', '--sshd-back'], env=henv('node2'))
ok('the timer ran out on node2: it went back by itself', until(lambda: node('node2')['state'] == 'back'))
ok('... node2 on 2222, node1 still on trial on 2300', until(
    lambda: node('node2')['now'].get('values', {}).get('port') == '2222' and node('node1')['now'].get('values', {}).get('port') == '2300'))
# Not managed any more.
c, x = call('node1', '/api/sshd', {'action': 'save', 'conf': {'manage': False}}, S)
ok('let go: otp\'s drop-in gone on both', until(lambda: not os.path.exists(N['node1']['dir'] + '/ssh/sshd_config.d/00-otp.conf') and
                                                  not os.path.exists(N['node2']['dir'] + '/ssh/sshd_config.d/00-otp.conf')))
ok('... /etc/issue as it was on node2, the notices gone', until(lambda: open(N['node2']['dir'] + '/etc/issue').read().startswith('\\S') and
                                                               not os.path.exists(N['node1']['dir'] + '/etc/issue.d/otp.issue')))
ev = json.dumps(call('node1', '/api/events?limit=200', None, S)[1])
ok('the changes are in the events', 'set the SSH server' in ev and 'went back on node2' in ev and 'kept the change' in ev)
print('ALL %d / %d' % (sum(R), len(R)))
