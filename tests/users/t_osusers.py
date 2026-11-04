# t_osusers.py VERSION - Settings -> Local users (1.0.243): the users of the machine made and looked after from the
# pages, on every node or on one, by each node's root helper; root shown, never changed.
# The helper by itself: who is listed (root and the normal range - no system user, no service), a user made with a
# password's hash (chpasswd -e from standard input), sudo, to change at the first sign-in; made again with the same
# UID is no fault, another UID refused; locked (the password and the account) and unlocked; a new password; sudo
# taken away; the full name and the shell; taken away with the home folder. Refused: root, a system user, a hash
# that is no hash, a shell not of /etc/shells, a colon in the full name.
# End to end: two daemons over one database, the helper played by a loop (both "nodes" are this one machine): a
# user asked on node1's pages for both, the same UID on both, the password never in the database as itself and its
# hash taken out of the asking row once done; a token admin may not; root refused; locked, unlocked, taken away;
# the events say who and never the password.
# Usage (as root): python3 t_osusers.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, pwd, grp, importlib.util

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.243'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


USERS = ('otpl_ann', 'otpl_ben', 'otpl_sys', 'otpl_web')
for u in USERS:
    sh('userdel', '-r', u)
sh('useradd', '-r', '-m', '-s', '/bin/bash', 'otpl_sys')
atexit.register(lambda: [sh('userdel', '-r', u) for u in USERS])
ADMIN = 'wheel' if sh('getent', 'group', 'wheel').returncode == 0 else 'sudo'


def shadow(name):
    for ln in open('/etc/shadow'):
        p = ln.rstrip('\n').split(':')
        if p[0] == name:
            return p
    return None


def in_admin(name):
    return name in grp.getgrnam(ADMIN).gr_mem


def hash_of(pw):
    return sh('openssl', 'passwd', '-6', '-stdin', input=pw + '\n').stdout.strip()


os.environ['OTP_VIP_NO_SERVICES'] = '1'
TOP = tempfile.mkdtemp(prefix='otp-osu-')
os.environ['OTP_STATE'] = TOP + '/hstate'; os.makedirs(TOP + '/hstate/web')
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# ---- the helper ------------------------------------------------------------------------------------------
L = W.lu_do({'do': 'list'})
names = [u['name'] for u in L['users']]
ok('listed: root first, shown as root', names[:1] == ['root'] and L['users'][0]['root'])
ok('...no system user, no service (otpl_sys, nobody, otp)', not any(n in names for n in ('otpl_sys', 'nobody', 'otp', 'daemon')), names)
ok('...the admin group named (%s), the shells, the normal range' % L['admin_group'], L['admin_group'] == ADMIN and L['shells'] and L['uid_min'] >= 500)


def refused(r, words):
    try:
        W.lu_do(r)
    except W.Refused as e:
        return words in str(e) or str(e)
    return False


H1 = hash_of('First-Pass-243!')
ok('root refused', refused({'do': 'password', 'name': 'root', 'hash': H1}, 'not a local user this may change') is True)
ok('a system user refused', refused({'do': 'lock', 'name': 'otpl_sys'}, 'account of the system') is True)
ok('a service (otp) refused', refused({'do': 'drop', 'name': 'otp'}, 'not a local user') is True)
ok('a hash that is no hash refused', refused({'do': 'add', 'name': 'otpl_ann', 'hash': 'plaintext'}, 'hash') is True and not shadow('otpl_ann'))
ok('a shell not of /etc/shells refused', refused({'do': 'add', 'name': 'otpl_ann', 'shell': '/tmp/evil'}, 'not a shell') is True)
ok('a colon in the full name refused', refused({'do': 'add', 'name': 'otpl_ann', 'gecos': 'a:b'}, 'cannot be in it') is True)
got = W.lu_do({'do': 'add', 'name': 'otpl_ann', 'gecos': 'Ann Test', 'shell': '/bin/bash', 'hash': H1, 'sudo': True,
               'must_change': True})
p = pwd.getpwnam('otpl_ann'); s = shadow('otpl_ann')
ok('made: home, shell, full name', os.path.isdir(p.pw_dir) and p.pw_shell == '/bin/bash' and p.pw_gecos.startswith('Ann Test'), got.get('said'))
ok('...its password the hash given', s and s[1] == H1)
ok('...to change at the first sign-in', s and s[2] == '0')
ok('...sudo (%s)' % ADMIN, in_admin('otpl_ann'))
u = [x for x in got['users'] if x['name'] == 'otpl_ann'][0]
ok('...listed as such', u['sudo'] and u['password'] and u['must_change'] and not u['locked'] and not u['root'], u)
ok('made again with its UID: no fault', 'was here already' in W.lu_do({'do': 'add', 'name': 'otpl_ann', 'uid': p.pw_uid})['said'])
ok('...with another UID: refused', refused({'do': 'add', 'name': 'otpl_ann', 'uid': p.pw_uid + 7}, 'is here already') is True)
free = max(L['used'] + [L['uid_min']]) + 50
W.lu_do({'do': 'add', 'name': 'otpl_ben', 'uid': free})
ok('a UID asked is the one it gets, no password', pwd.getpwnam('otpl_ben').pw_uid == free and not [x for x in W.lu_list()['users'] if x['name'] == 'otpl_ben'][0]['password'])
ok('a UID of another user refused', refused({'do': 'add', 'name': 'otpl_web', 'uid': free}, "otpl_ben's here") is True)
W.lu_do({'do': 'lock', 'name': 'otpl_ann'})
s = shadow('otpl_ann')
ok('locked: the password (!) and the account (expired)', s[1].startswith('!') and s[7] == '0', s)
ok('...listed locked', [x for x in W.lu_list()['users'] if x['name'] == 'otpl_ann'][0]['locked'])
W.lu_do({'do': 'unlock', 'name': 'otpl_ann'})
s = shadow('otpl_ann')
ok('unlocked: the password as it was, no end', s[1] == H1 and s[7] == '', s)
W.lu_do({'do': 'lock', 'name': 'otpl_ben'}); W.lu_do({'do': 'unlock', 'name': 'otpl_ben'})
ok('locked and unlocked with no password: no fault, not locked', not [x for x in W.lu_list()['users'] if x['name'] == 'otpl_ben'][0]['locked'])
H2 = hash_of('Second-Pass-243!')
W.lu_do({'do': 'password', 'name': 'otpl_ann', 'hash': H2})
s = shadow('otpl_ann')
ok('a new password: its hash, no longer to change', s[1] == H2 and s[2] not in ('0', ''), s[2])
W.lu_do({'do': 'sudo', 'name': 'otpl_ann', 'on': False})
ok('sudo taken away', not in_admin('otpl_ann'))
W.lu_do({'do': 'set', 'name': 'otpl_ann', 'gecos': 'Ann Other', 'shell': '/bin/sh'})
p = pwd.getpwnam('otpl_ann')
ok('the full name and the shell changed', p.pw_gecos.startswith('Ann Other') and p.pw_shell == '/bin/sh', (p.pw_gecos, p.pw_shell))
home = p.pw_dir
W.lu_do({'do': 'drop', 'name': 'otpl_ann', 'home': True})
ok('taken away with the home folder', not shadow('otpl_ann') and not os.path.exists(home))
ok('taken away again: no fault', 'was not here' in W.lu_do({'do': 'drop', 'name': 'otpl_ann'})['said'])
W.lu_do({'do': 'drop', 'name': 'otpl_ben', 'home': True})

# ---- end to end: two daemons, the pages ------------------------------------------------------------------
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32950 + 10 * i,
               'radius_acct_port': 32951 + 10 * i, 'api_port': 29970 + i, 'node_name': name},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 29970 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-243!', must_change=0)
st.add_account('tok', 'tokenadmin', 'Token-Admin-Pass-243!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
STOP = threading.Event()


def helper_loop(name):
    d = N[name]['dir']
    env = dict(os.environ, OTP_STATE=d, OTP_VIP_NO_SERVICES='1')
    while not STOP.is_set():
        if os.path.exists(os.path.join(d, 'web', 'users.ask')):
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


def until(fn, secs=45):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.7)
    return None


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-243!'}); S = a['token']
_, a = call('node1', '/api/auth/login', {'name': 'tok', 'password': 'Token-Admin-Pass-243!'}); ST = a['token']
both = ['node1', 'node2']


def view():
    return call('node1', '/api/osusers', None, S)[1]


def user_on(n, name):
    for x in n.get('users') or []:
        if x['name'] == name:
            return x
    return None


ok('a token admin may not look (%s)' % call('node1', '/api/osusers', None, ST)[0], call('node1', '/api/osusers', None, ST)[0] == 403)
call('node1', '/api/osusers', {'action': 'refresh', 'nodes': both}, S)
ok('both nodes tell their users, root among them', until(lambda: len(view().get('nodes') or []) == 2 and
                                                       all(user_on(n, 'root') for n in view()['nodes'])), view())
PW = 'Pages-Pass-243-xyz!'
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpl_web', 'gecos': 'Web Test', 'shell': '/bin/bash',
                                       'password': PW, 'sudo': True, 'must_change': True, 'nodes': both}, ST)
ok('a token admin may not make one (%s)' % c, c == 403)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpl_web', 'gecos': 'Web Test', 'shell': '/bin/bash',
                                       'password': 'short', 'nodes': both}, S)
ok('a password too short refused (%s)' % c, c == 400 and 'characters at least' in x.get('error', ''), x)
for bad in ('root', 'otp', 'Ann', '9x', 'a b'):
    c, x = call('node1', '/api/osusers', {'action': 'add', 'name': bad, 'password': PW, 'nodes': both}, S)
    ok('the name %r refused (%s)' % (bad, c), c == 400, x)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpl_web', 'gecos': 'Web Test', 'shell': '/bin/bash',
                                       'password': PW, 'sudo': True, 'must_change': True, 'nodes': both}, S)
ok('a user asked for both nodes (%s)' % c, c == 200 and x.get('nodes') == both, x)
ok('...both nodes have it, the same UID', until(lambda: all(user_on(n, 'otpl_web') for n in view()['nodes']) and
                                               len({user_on(n, 'otpl_web')['uid'] for n in view()['nodes']}) == 1), view())
ok('...made on the machine, sudo, to change at the first sign-in', shadow('otpl_web') and in_admin('otpl_web') and shadow('otpl_web')[2] == '0')
ok('...its password the one typed', sh('openssl', 'passwd', '-6', '-salt', shadow('otpl_web')[1].split('$')[2], '-stdin',
                                        input=PW + '\n').stdout.strip() == shadow('otpl_web')[1])
dump = json.dumps([dict(r) for r in st.db.rows('SELECT * FROM meta')]) + json.dumps([dict(r) for r in st.db.rows('SELECT * FROM events')])
ok('...the password never in the database as itself', PW not in dump)
ok('...nor its hash in the clear', shadow('otpl_web')[1] not in dump)


def hashes_left():
    n = 0
    for r in st.db.rows("SELECT v FROM meta WHERE k LIKE 'host:users:want:%'"):
        n += sum(1 for a in json.loads(r['v']) if a.get('hash'))
    return n


ok('...its sealed hash taken out of the asking rows once done', until(lambda: hashes_left() == 0, 30), hashes_left())
ev = [dict(r) for r in st.db.rows("SELECT * FROM events WHERE words LIKE '%otpl_web%'")]
ok('...in Events: who, on which nodes, UID and sudo', any('local made the local user otpl_web' in e['words'] and 'node1, node2' in e['words']
                                                          and 'sudo' in e['words'] for e in ev), ev)
said = [s for n in view()['nodes'] for s in n.get('said') or [] if s.get('name') == 'otpl_web']
ok('...each node said it was done (the second: there already - one machine)', len(said) >= 2 and all(s['ok'] for s in said), said)
c, x = call('node1', '/api/osusers', {'action': 'password', 'name': 'root', 'password': PW, 'nodes': both}, S)
ok('root: never changed from the pages (%s)' % c, c == 400 and 'never changed' in x.get('error', ''), x)
c, x = call('node1', '/api/osusers', {'action': 'lock', 'name': 'otpl_sys', 'nodes': both}, S)
ok('a system user not of the list refused (%s)' % c, c == 400, x)
c, x = call('node1', '/api/osusers', {'action': 'lock', 'name': 'otpl_web', 'nodes': both}, S)
ok('locked from the pages (%s)' % c, c == 200 and until(lambda: all((user_on(n, 'otpl_web') or {}).get('locked') for n in view()['nodes'])))
c, x = call('node1', '/api/osusers', {'action': 'unlock', 'name': 'otpl_web', 'nodes': ['node2']}, S)
ok('unlocked on one node (one machine: both read it so)', c == 200 and x.get('nodes') == ['node2'] and
   until(lambda: not (user_on(view()['nodes'][1], 'otpl_web') or {}).get('locked')))
PW2 = 'Another-Pass-243-abc'
c, x = call('node1', '/api/osusers', {'action': 'password', 'name': 'otpl_web', 'password': PW2, 'nodes': ['node1']}, S)
ok('a new password from the pages', c == 200 and until(lambda: sh('openssl', 'passwd', '-6', '-salt', shadow('otpl_web')[1].split('$')[2], '-stdin',
                                                                   input=PW2 + '\n').stdout.strip() == shadow('otpl_web')[1]))
c, x = call('node1', '/api/osusers', {'action': 'sudo', 'name': 'otpl_web', 'on': False, 'nodes': both}, S)
ok('sudo taken away from the pages', c == 200 and until(lambda: not in_admin('otpl_web') and
                                                        not any((user_on(n, 'otpl_web') or {}).get('sudo') for n in view()['nodes'])))
c, x = call('node1', '/api/osusers', {'action': 'drop', 'name': 'otpl_web', 'home': True, 'nodes': both}, S)
ok('taken away from the pages, on both', c == 200 and until(lambda: not shadow('otpl_web') and
                                                            not any(user_on(n, 'otpl_web') for n in view()['nodes'])))
ok('...no change of root on the way', shadow('root')[1] == open('/etc/shadow').read().split('root:', 1)[1].split(':')[0])
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
