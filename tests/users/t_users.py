# t_users.py VERSION - the normal users of the machine (1.0.240): their SSH keys on the pages and the console at
# login for them through sudo. Real users made for it (alice, bob; svcx with nologin; a system one), taken away at
# the end. The root helper: who is listed, a key added as the user (owner, 0700/0600), read, taken away; a link in
# the user's own home never followed (the root's file it points at untouched); names that are not users refused.
# End to end: two daemons over one database, the helper played by a loop - a key for alice asked on node1's pages
# for both nodes, made there (private half once), taken away; root's keys as they were. The console: the flag's
# users line written by the helper and the CLI, kept when root's switch changes; the login script run in a
# terminal as alice (sudo) and bob (no sudo); --console-users; the events say who.
# Usage (as root): python3 t_users.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, shutil, pwd, importlib.util, stat

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.240'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


USERS = ('otpt_alice', 'otpt_bob', 'otpt_svcx', 'otpt_sys')
for u in USERS:
    sh('userdel', '-r', u)
sh('useradd', '-m', '-s', '/bin/bash', '-G', 'wheel' if sh('getent', 'group', 'wheel').returncode == 0 else 'sudo', 'otpt_alice')
sh('useradd', '-m', '-s', '/bin/bash', 'otpt_bob')
sh('useradd', '-m', '-s', '/sbin/nologin', 'otpt_svcx')
sh('useradd', '-r', '-m', '-s', '/bin/bash', 'otpt_sys')
open('/etc/sudoers.d/otpt-alice', 'w').write('otpt_alice ALL=(ALL) NOPASSWD: ALL\n')
os.chmod('/etc/sudoers.d/otpt-alice', 0o440)


def cleanup():
    for u in USERS:
        sh('userdel', '-r', u)
    try:
        os.remove('/etc/sudoers.d/otpt-alice')
    except OSError:
        pass
atexit.register(cleanup)
A = pwd.getpwnam('otpt_alice')
os.environ['OTP_VIP_NO_SERVICES'] = '1'
TOP = tempfile.mkdtemp(prefix='otp-users-')
os.environ['OTP_STATE'] = TOP + '/hstate'; os.makedirs(TOP + '/hstate/web')
os.environ['OTP_CONSOLE_FLAG'] = TOP + '/console-flag'
os.environ['OTP_ROOT_AUTHKEYS'] = TOP + '/root_authorized_keys'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
work = tempfile.mkdtemp(prefix='otp-ukey-')
for n in ('k1', 'k2'):
    sh('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'alice@' + n, '-f', work + '/' + n)
K1 = open(work + '/k1.pub').read().strip(); K2 = open(work + '/k2.pub').read().strip()

# ---- the helper ------------------------------------------------------------------------------------------
names = [u['name'] for u in W.normal_users()]
ok('listed: alice and bob (a login shell, UID 1000 and up)', 'otpt_alice' in names and 'otpt_bob' in names, names)
ok('...not svcx (nologin), not a system user, not root, not nobody', not any(n in names for n in ('otpt_svcx', 'otpt_sys', 'root', 'nobody')), names)
got = W.sshkeys_do({'do': 'add', 'line': K1, 'user': 'otpt_alice'})
ak = A.pw_dir + '/.ssh/authorized_keys'
st_ = os.stat(ak); sd = os.stat(A.pw_dir + '/.ssh')
ok('a key added for alice: in her ~/.ssh/authorized_keys', K1 in open(ak).read() and got['keys'] and got['user'] == 'otpt_alice', got)
ok('...the file hers, 0600; ~/.ssh hers, 0700', st_.st_uid == A.pw_uid and stat.S_IMODE(st_.st_mode) == 0o600
   and sd.st_uid == A.pw_uid and stat.S_IMODE(sd.st_mode) == 0o700, (st_.st_uid, oct(st_.st_mode), sd.st_uid, oct(sd.st_mode)))
ok('...root\'s file not touched', not os.path.exists(TOP + '/root_authorized_keys'))
W.sshkeys_do({'do': 'add', 'line': K1, 'user': 'otpt_alice'})
ok('...added again: still once', open(ak).read().count(K1) == 1)
got = W.sshkeys_do({'do': 'add', 'line': K2, 'user': 'otpt_alice'})
fp1 = [k['fp'] for k in got['keys'] if k['comment'] == 'alice@k1'][0]
got = W.sshkeys_do({'do': 'drop', 'fp': fp1, 'user': 'otpt_alice'})
ok('taken away: the other stays', K1 not in open(ak).read() and K2 in open(ak).read() and len(got['keys']) == 1, got['keys'])
got = W.sshkeys_do({'do': 'drop', 'fp': got['keys'][0]['fp'], 'user': 'otpt_alice'})
ok('...the last one of a normal user taken away too (no "last key" guard - the password stays theirs)', got['keys'] == [])
# a link in her own home: never followed
secret = TOP + '/rootfile'
open(secret, 'w').write('root only\n'); os.chmod(secret, 0o600)
os.remove(ak)
os.symlink(secret, ak)
try:
    W.sshkeys_do({'do': 'add', 'line': K1, 'user': 'otpt_alice'}); e = ''
except W.Refused as x:
    e = str(x)
ok('authorized_keys a link (to a file of root\'s): refused', 'link' in e, e)
ok('...root\'s file as it was', open(secret).read() == 'root only\n' and os.stat(secret).st_uid == 0)
os.remove(ak)
shutil.rmtree(A.pw_dir + '/.ssh')
os.symlink('/root', A.pw_dir + '/.ssh')
try:
    W.sshkeys_do({'do': 'add', 'line': K1, 'user': 'otpt_alice'}); e = ''
except W.Refused as x:
    e = str(x)
ok('~/.ssh a link (to /root): refused, nothing written there', ('link' in e or 'plain folder' in e or 'Permission' in e)
   and K1 not in (open('/root/.ssh/authorized_keys').read() if os.path.exists('/root/.ssh/authorized_keys') else ''), e)
os.remove(A.pw_dir + '/.ssh')
for bad in ('otpt_svcx', 'otpt_sys', 'nobody', '../root', 'otpt_nosuch'):
    try:
        W.sshkeys_do({'do': 'list', 'user': bad}); e = ''
    except W.Refused as x:
        e = str(x)
    ok('user %r refused' % bad, 'not a user who may sign in' in e, e)
got = W.sshkeys_do({'do': 'list'})
ok('root\'s as until now - and the users who may sign in told', got['user'] == 'root' and got['file'] == TOP + '/root_authorized_keys'
   and any(u['name'] == 'otpt_alice' for u in got['users']))
# the console's flag
W.console_flag_set(True, ['otpt_alice', 'otpt_bob'])
ok('the flag: on, then the users', open(TOP + '/console-flag').read() == 'on\nusers: otpt_alice otpt_bob\n', open(TOP + '/console-flag').read())
W.console_flag_set(False)
ok('...root switched off: the users kept', W.console_flag_read() == (False, ['otpt_alice', 'otpt_bob']), W.console_flag_read())
W.console_flag_set(True, '*')
ok('...every normal user: *', W.console_flag_read() == (True, '*'))
W.console_flag_set(True, [])
ok('...nobody: the line gone, as before 1.0.240', open(TOP + '/console-flag').read() == 'on\n')
for bad in (['root'], ['a b'], ['x;rm'], 'all'):
    try:
        W.console_users_checked(bad); e = ''
    except W.Refused as x:
        e = str(x)
    ok('console users %r refused' % (bad,), bool(e), e)

# ---- the login script, in a terminal ---------------------------------------------------------------------
fake = TOP + '/fakeotp'
open(fake, 'w').write('#!/bin/sh\necho "CONSOLE uid=$(id -u) sudo_user=${SUDO_USER:-} oc=${OTP_CONSOLE:-} args=$*"\n'); os.chmod(fake, 0o755)
flag = TOP + '/flag2'
prof = open(V + '/deploy/otp-console-login.sh').read().replace('/usr/local/bin/otp', fake).replace('/etc/otp-console-login', flag)
pf = TOP + '/prof.sh'
open(pf, 'w').write(prof); os.chmod(pf, 0o644)
os.chmod(TOP, 0o755)


def login_as(user, flagtext):
    open(flag, 'w').write(flagtext); os.chmod(flag, 0o644)
    cmd = 'PS1="$ "; . %s; echo SHELL-HERE' % pf
    if user == 'root':
        r = sh('script', '-qec', 'bash --norc --noprofile -c \'%s\'' % cmd, '/dev/null', timeout=30)
    else:
        r = sh('script', '-qec', 'su -s /bin/bash %s -c \'%s\'' % (user, cmd), '/dev/null', timeout=30)
    return r.stdout.replace('\r', '')


o = login_as('otpt_alice', 'off\nusers: otpt_alice\n')
ok('alice named, in wheel with sudo: the console through sudo - as root, her name kept, then her shell', 'CONSOLE uid=0 sudo_user=otpt_alice oc=1 args=--console' in o
   and 'SHELL-HERE' in o, o)
o = login_as('otpt_bob', 'off\nusers: otpt_alice otpt_bob\n')
ok('bob named, no sudo rights: told so, the ordinary shell, no console', 'needs sudo rights' in o and 'CONSOLE' not in o and 'SHELL-HERE' in o, o)
o = login_as('otpt_bob', 'on\nusers: otpt_alice\n')
ok('bob not named: nothing at all', 'CONSOLE' not in o and 'otp:' not in o and 'SHELL-HERE' in o, o)
o = login_as('otpt_alice', 'on\nusers: *\n')
ok('every normal user (*): alice gets it', 'CONSOLE uid=0 sudo_user=otpt_alice' in o, o)
o = login_as('root', 'on\nusers: otpt_bob\n')
ok('root, on: the console as until now', 'CONSOLE uid=0 sudo_user= oc=1' in o, o)
o = login_as('root', 'off\nusers: *\n')
ok('root, off (users on): the ordinary shell', 'CONSOLE' not in o and 'SHELL-HERE' in o, o)
o = login_as('otpt_alice', 'on\n')
ok('a flag of before 1.0.240 (on, no users line): nothing for alice', 'CONSOLE' not in o, o)

# ---- end to end: two daemons, the pages ------------------------------------------------------------------
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32850 + 10 * i,
               'radius_acct_port': 32851 + 10 * i, 'api_port': 29870 + i, 'node_name': name},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 29870 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1', OTP_CONSOLE_FLAG=d + '/console-flag')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-158!', must_change=0)
st.add_account('tok', 'tokenadmin', 'Token-Admin-Pass-158!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
STOP = threading.Event()


def helper_loop(name):
    d = N[name]['dir']
    env = dict(os.environ, OTP_STATE=d, OTP_ROOT_AUTHKEYS=d + '/authorized_keys', OTP_VIP_NO_SERVICES='1',
               OTP_CONSOLE_FLAG=d + '/console-flag')
    while not STOP.is_set():
        if any(os.path.exists(os.path.join(d, 'web', a)) for a in ('sshkeys.ask', 'console.ask')):
            subprocess.run([sys.executable, '-I', V + '/deploy/otp_web.py'], env=env,
                           stdout=subprocess.DEVNULL, stderr=open(d + '/helper.err', 'a'))
        time.sleep(0.3)


procs = []
for name in N:
    open(N[name]['dir'] + '/console-flag', 'w').write('on\n')
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


def until(fn, secs=40):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.7)
    return None


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-158!'}); S = a['token']
_, a = call('node1', '/api/auth/login', {'name': 'tok', 'password': 'Token-Admin-Pass-158!'}); ST = a['token']
both = ['node1', 'node2']


def view():
    return call('node1', '/api/sshkeys', None, S)[1]


call('node1', '/api/sshkeys', {'action': 'refresh', 'nodes': both}, S)
ok('the nodes tell their users', until(lambda: all(any(u['name'] == 'otpt_alice' for u in n.get('users') or []) for n in view().get('nodes') or [{}])
   and len(view()['nodes']) == 2))
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': K1, 'nodes': both, 'user': 'otpt_alice'}, ST)
ok('a token admin may not (%s)' % c, c == 403)
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': K1, 'nodes': both, 'user': 'otpt_alice'}, S)
ok('a key for alice asked for both nodes: %s' % c, c == 200, x)
ok('...written as alice, both nodes say it', until(lambda: all(len(((n.get('keys_of') or {}).get('otpt_alice') or {}).get('keys') or []) == 1 for n in view()['nodes'])),
   view())
ok('...in her file, hers', os.path.exists(ak) and K1 in open(ak).read() and os.stat(ak).st_uid == A.pw_uid)
ok('...root\'s keys of the nodes not touched', all(not n.get('keys') for n in view()['nodes']), [n.get('keys') for n in view()['nodes']])
c, x = call('node1', '/api/sshkeys', {'action': 'uk_make', 'user': 'otpt_alice', 'kind': 'ed25519', 'nodes': both}, S)
ok('a key made for alice: the private half once, the public onto both', c == 200 and 'PRIVATE KEY' in x.get('private', '') and x.get('nodes') == both, x)
ok('...both nodes have two keys of hers', until(lambda: all(len(((n.get('keys_of') or {}).get('otpt_alice') or {}).get('keys') or []) == 2 for n in view()['nodes'])))
ok('...the private half nowhere in the database', x.get('private', 'x')[40:80] not in json.dumps([dict(r) for r in st.db.rows('SELECT * FROM meta')]))
fp = [k['fp'] for k in (view()['nodes'][0]['keys_of']['otpt_alice']['keys']) if 'alice@k1' in k['comment']][0]
c, x = call('node1', '/api/sshkeys', {'action': 'drop', 'fp': fp, 'nodes': both, 'user': 'otpt_alice'}, S)
# (both "nodes" here are one machine - one /home: the second finds it gone already; read again)
time.sleep(3)
call('node1', '/api/sshkeys', {'action': 'refresh', 'nodes': both, 'user': 'otpt_alice'}, S)
ok('taken away for alice: %s' % c, c == 200 and until(lambda: all(len(((n.get('keys_of') or {}).get('otpt_alice') or {}).get('keys') or []) == 1 for n in view()['nodes']))
   and 'alice@k1' not in open(ak).read())
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': K1, 'nodes': ['node1'], 'user': 'otpt_svcx'}, S)
ok('svcx (nologin): asked, refused by the helper - said on the node', c == 200 and until(lambda: 'not a user who may sign in' in
   (((view()['nodes'][0].get('keys_of') or {}).get('otpt_svcx') or {}).get('error') or '')), view()['nodes'][0].get('keys_of'))
c, x = call('node1', '/api/sshkeys', {'action': 'add', 'line': K1, 'nodes': ['node1'], 'user': '../root'}, S)
ok('"../root": refused at once (%s)' % c, c == 400, x)
ev = json.dumps(call('node1', '/api/events?limit=60', None, S)[1])
ok('the events say for whom', 'for otpt_alice on node1, node2' in ev, ev[:300])
# the console's users from the pages
c, x = call('node1', '/api/console-login', {'node': 'node2', 'on': True, 'users': ['otpt_alice']}, S)
ok('the console at login for alice on node2: asked (%s)' % c, c == 200, x)
ok('...written on node2: on, users alice', until(lambda: open(N['node2']['dir'] + '/console-flag').read() == 'on\nusers: otpt_alice\n'),
   open(N['node2']['dir'] + '/console-flag').read())
ok('...node1 as it was', open(N['node1']['dir'] + '/console-flag').read() == 'on\n')
ok('...the page says it', until(lambda: [n for n in call('node1', '/api/console-login', None, S)[1]['nodes'] if n['name'] == 'node2'][0].get('users') == ['otpt_alice']))
c, x = call('node1', '/api/console-login', {'node': 'node2', 'on': False}, S)
ok('...root switched off on node2, users left out: kept', c == 200 and until(lambda: open(N['node2']['dir'] + '/console-flag').read() == 'off\nusers: otpt_alice\n'),
   open(N['node2']['dir'] + '/console-flag').read())
c, x = call('node1', '/api/console-login', {'node': 'node2', 'on': True, 'users': ['root']}, S)
ok('...root as a "normal user": refused (%s)' % c, c == 400, x)
ev = json.dumps(call('node1', '/api/events?limit=60', None, S)[1])
ok('...in the events, with the users', 'for normal users: otpt_alice (through sudo)' in ev, ev[:300])

# ---- the CLI ------------------------------------------------------------------------------------------------
e1 = N['node1']['env']
r = sh(sys.executable, V + '/otp.py', '--console-users', 'otpt_alice,otpt_bob', env=e1, timeout=60)
ok('otp --console-users alice,bob', r.returncode == 0 and open(N['node1']['dir'] + '/console-flag').read() == 'on\nusers: otpt_alice otpt_bob\n', r.stdout + r.stderr)
r = sh(sys.executable, V + '/otp.py', '--console-at-login', 'status', env=e1, timeout=60)
ok('...status says both', 'ON' in r.stdout and 'otpt_alice, otpt_bob' in r.stdout, r.stdout)
r = sh(sys.executable, V + '/otp.py', '--console-at-login', 'off', env=e1, timeout=60)
ok('...--console-at-login off keeps the users', open(N['node1']['dir'] + '/console-flag').read() == 'off\nusers: otpt_alice otpt_bob\n')
r = sh(sys.executable, V + '/otp.py', '--console-users', 'none', env=e1, timeout=60)
ok('...none: the line gone', open(N['node1']['dir'] + '/console-flag').read() == 'off\n', open(N['node1']['dir'] + '/console-flag').read())
r = sh(sys.executable, V + '/otp.py', '--console-users', 'root', env=e1, timeout=60)
ok('...root refused', r.returncode != 0)
r = sh(sys.executable, V + '/otp.py', '--set', 'portal_title=Users test', env=dict(e1, SUDO_USER='otpt_alice'), timeout=60)
ev = json.dumps(call('node1', '/api/events?limit=60', None, S)[1])
ok('run through sudo: the events say whose sudo', r.returncode == 0 and 'command line (sudo otpt_alice)' in ev, (r.stderr, ev[:400]))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
