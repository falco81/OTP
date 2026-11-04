# t_pwpolicy.py VERSION - Local users -> Password policy (1.0.245), on copies of the system's files (pwquality,
# pwhistory, faillock, login.defs, PAM) and an authselect that only writes down what it is asked.
# The helper: what is in effect read (defaults, the files, the drop-ins after them, which modules PAM uses); the
# policy put in - pwquality's drop-in, otp's lines between marks in pwhistory.conf and faillock.conf (the rest of
# each file as it was), login.defs' aging (the values before kept), authselect's features put in; put in again:
# nothing twice; given back: every file as it was before, only the features otp put in taken out; a link where a
# file is refused; values out of range refused; a user's own aging; the users there now given the aging too.
# End to end: two daemons over one database, the helper played by a loop - the policy saved on node1's pages put in
# by both, a password the policy does not take refused at once, one it takes made; a token admin may not; Events.
# Usage (as root): python3 t_pwpolicy.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, threading, atexit, importlib.util, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.245'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


TOP = tempfile.mkdtemp(prefix='otp-pwp-')
SEC, PAM = TOP + '/security', TOP + '/pam.d'
os.makedirs(SEC); os.makedirs(PAM)
FILES = {
    SEC + '/pwquality.conf': '# Configuration for systemwide password quality limits\n# minlen = 8\nminlen = 9\n',
    SEC + '/pwhistory.conf': '# pam_pwhistory\n# remember = 10\n',
    SEC + '/faillock.conf': '# pam_faillock\n# deny = 3\naudit\n',
    PAM + '/system-auth': 'auth required pam_env.so\nauth required pam_faillock.so preauth\n'
                          'password requisite pam_pwquality.so local_users_only\npassword sufficient pam_unix.so sha512\n',
}
for p, t in FILES.items():
    open(p, 'w').write(t)
DEFS = TOP + '/login.defs'
shutil.copy('/etc/login.defs', DEFS)
ORIG_DEFS = open(DEFS).read()
AS_STATE = TOP + '/authselect.state'
open(AS_STATE, 'w').write('sssd with-mkhomedir\n')
AS = TOP + '/authselect'
open(AS, 'w').write('''#!/bin/bash
S=%s
case "$1" in
  current) cat $S ;;
  enable-feature) grep -qw "$2" $S || sed -i "1s/$/ $2/" $S; echo "enable $2" >> %s/authselect.log ;;
  disable-feature) sed -i "1s/ $2//" $S; echo "disable $2" >> %s/authselect.log ;;
esac
''' % (AS_STATE, TOP, TOP))
os.chmod(AS, 0o755)
ENVX = dict(OTP_SECURITY_DIR=SEC, OTP_PAM_DIR=PAM, OTP_LOGIN_DEFS=DEFS, OTP_AUTHSELECT=AS, OTP_VIP_NO_SERVICES='1',
            OTP_PWP_ORIG=TOP + '/pwpolicy-orig.json')   # both "nodes" are one machine: one record of what was there
os.environ.update(ENVX)
os.environ['OTP_STATE'] = TOP + '/hstate'; os.makedirs(TOP + '/hstate/web')
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
for u in ('otpp_ann', 'otpp_web', 'otpp_bad'):
    sh('userdel', '-r', u)
atexit.register(lambda: [sh('userdel', '-r', u) for u in ('otpp_ann', 'otpp_web', 'otpp_bad')])

# ---- the helper ------------------------------------------------------------------------------------------
r = W.pwp_read()
ok('read: minlen from pwquality.conf (9), the rest the module\'s own', r['pwquality']['minlen'] == 9 and r['pwquality']['dictcheck'] == 1, r['pwquality'])
ok('...PAM uses pwquality and faillock, not pwhistory', r['pam'] == {'pwquality': True, 'pwhistory': False, 'faillock': True, 'read': True}, r['pam'])
ok('...authselect: its profile and features', r['authselect'] == {'profile': 'sssd', 'features': ['with-mkhomedir']}, r['authselect'])
ok('...not managed by otp', not r['managed'])
C = {'managed': True, 'minlen': 14, 'minclass': 3, 'maxrepeat': 2, 'dictcheck': 1, 'usercheck': 1, 'difok': 4,
     'remember': 6, 'max_days': 90, 'min_days': 1, 'warn_days': 10, 'deny': 5, 'unlock_time': 600, 'fail_interval': 900}
said = W.pwp_apply(C)
drop = open(SEC + '/pwquality.conf.d/50-otp.conf').read()
ok('put in: pwquality\'s drop-in', 'minlen = 14' in drop and 'minclass = 3' in drop and 'maxrepeat = 2' in drop, drop)
ok('...pwquality.conf itself not touched', open(SEC + '/pwquality.conf').read() == FILES[SEC + '/pwquality.conf'])
ok('...pwhistory.conf: otp\'s lines, the rest as it was', 'remember = 6' in open(SEC + '/pwhistory.conf').read()
   and open(SEC + '/pwhistory.conf').read().startswith(FILES[SEC + '/pwhistory.conf']))
ok('...faillock.conf: otp\'s lines, the rest as it was', all(x in open(SEC + '/faillock.conf').read() for x in ('deny = 5', 'unlock_time = 600', 'audit')))
d = open(DEFS).read()
ok('...login.defs: the aging', '\nPASS_MAX_DAYS\t90' in d and '\nPASS_MIN_DAYS\t1' in d and '\nPASS_WARN_AGE\t10' in d)
log = open(TOP + '/authselect.log').read()
ok('...authselect: with-pwhistory and with-faillock put in', 'enable with-pwhistory' in log and 'enable with-faillock' in log, log)
r = W.pwp_read()
ok('read again: as put in', r['managed'] and r['pwquality']['minlen'] == 14 and r['remember'] == 6 and r['faillock']['deny'] == 5
   and r['aging']['max_days'] == 90, r)
W.pwp_apply(C)
ok('put in again: nothing twice', open(SEC + '/faillock.conf').read().count('deny = 5') == 1 and open(DEFS).read().count('PASS_MAX_DAYS\t90') == 1)
W.pwp_apply(dict(C, deny=0, remember=6))
ok('the lockout taken off: its lines out, with-faillock out again (otp put it in)', 'deny' not in open(SEC + '/faillock.conf').read().replace('# deny', '')
   and 'disable with-faillock' in open(TOP + '/authselect.log').read())
W.pwp_apply(dict(C, managed=False))
ok('given back: the drop-in gone', not os.path.exists(SEC + '/pwquality.conf.d/50-otp.conf'))
ok('...every file as it was', all(open(p).read() == t for p, t in FILES.items()), [p for p, t in FILES.items() if open(p).read() != t])
ok('...login.defs as it was', open(DEFS).read() == ORIG_DEFS)
ok('...only what otp put in taken out of authselect', open(AS_STATE).read().split() == ['sssd', 'with-mkhomedir'], open(AS_STATE).read())
st = os.stat(SEC + '/faillock.conf').st_mtime
W.pwp_apply(dict(C, managed=False))
ok('given back again: no file written', os.stat(SEC + '/faillock.conf').st_mtime == st)
os.rename(SEC + '/faillock.conf', SEC + '/faillock.real')
os.symlink('/etc/passwd', SEC + '/faillock.conf')
try:
    W.pwp_apply(C); bad = None
except W.Refused as e:
    bad = str(e)
ok('a link where faillock.conf is: refused, the file it points at untouched', bad and 'not a plain file' in bad and 'otp:' not in open('/etc/passwd').read().split('\n')[0], bad)
os.unlink(SEC + '/faillock.conf'); os.rename(SEC + '/faillock.real', SEC + '/faillock.conf')
W.pwp_apply(dict(C, managed=False))
for k, v in (('minlen', 3), ('minclass', 7), ('max_days', -1), ('deny', 1000)):
    try:
        W.pwp_checked(dict(C, **{k: v})); bad = None
    except W.Refused as e:
        bad = str(e)
    ok('%s=%s refused' % (k, v), bad and k in bad, bad)
sh('useradd', '-m', '-s', '/bin/bash', 'otpp_ann')
W.lu_do({'do': 'aging', 'name': 'otpp_ann', 'max_days': 45, 'min_days': 2, 'warn_days': 5})
sp = [ln.split(':') for ln in open('/etc/shadow') if ln.startswith('otpp_ann:')][0]
ok('a user\'s own aging (chage)', sp[3] == '2' and sp[4] == '45' and sp[5] == '5', sp[:6])
u = [x for x in W.lu_list()['users'] if x['name'] == 'otpp_ann'][0]
ok('...listed: 45 days, warned 5 before', u['max_days'] == 45 and u['warn_days'] == 5 and u['min_days'] == 2, u)
W.pwp_apply(dict(C, existing=True, max_days=60))
sp = [ln.split(':') for ln in open('/etc/shadow') if ln.startswith('otpp_ann:')][0]
ok('the policy "also for the users there now": their aging set', sp[4] == '60' and sp[5] == '10', sp[:6])
ok('...root\'s not', [ln.split(':') for ln in open('/etc/shadow') if ln.startswith('root:')][0][4] != '60')
W.pwp_apply(dict(C, managed=False))
ok('given back after all that: login.defs as it was', open(DEFS).read() == ORIG_DEFS)

# ---- end to end: two daemons, the pages ------------------------------------------------------------------
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name)
    os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 33050 + 10 * i,
               'radius_acct_port': 33051 + 10 * i, 'api_port': 30070 + i, 'node_name': name},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 30070 + i,
               'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                           OTP_RUN=d + '/run', OTP_STAY_ROOT='1')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st_ = otp.Storage(otp.open_db()); st_.db.make_tables(); otp.sealing_key(make=True)
st_.add_account('local', 'fulladmin', 'Local-Admin-Pass-245!', must_change=0)
st_.add_account('tok', 'tokenadmin', 'Token-Admin-Pass-245!', must_change=0)
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
STOP = threading.Event()


def helper_loop(name):
    d = N[name]['dir']
    env = dict(os.environ, OTP_STATE=d, **ENVX)
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
        with urllib.request.urlopen(req, timeout=30) as r_:
            return r_.status, json.loads(r_.read())
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


_, a = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-245!'}); S = a['token']
_, a = call('node1', '/api/auth/login', {'name': 'tok', 'password': 'Token-Admin-Pass-245!'}); ST = a['token']
both = ['node1', 'node2']
view = lambda: call('node1', '/api/osusers', None, S)[1]
call('node1', '/api/osusers', {'action': 'refresh', 'nodes': both}, S)
ok('both nodes: not managed, put in as such, what is in effect read', until(lambda: len(view().get('nodes') or []) == 2 and
   all(n.get('policy_applied') and (n.get('policy') or {}).get('pwquality') for n in view()['nodes'])), view().get('nodes'))
ok('...nothing written for it', all(open(p).read() == t for p, t in FILES.items()) and not os.path.exists(SEC + '/pwquality.conf.d/50-otp.conf'))
c, x = call('node1', '/api/osusers', {'action': 'policy', 'policy': dict(C)}, ST)
ok('a token admin may not set it (%s)' % c, c == 403)
c, x = call('node1', '/api/osusers', {'action': 'policy', 'policy': dict(C, minlen=2)}, S)
ok('a value out of range refused (%s)' % c, c == 400, x)
c, x = call('node1', '/api/osusers', {'action': 'policy', 'policy': dict(C, max_days=5, min_days=10)}, S)
ok('the least days more than the days it is good: refused (%s)' % c, c == 400, x)
c, x = call('node1', '/api/osusers', {'action': 'policy', 'policy': dict(C)}, S)
ok('the policy saved (%s)' % c, c == 200, x)
ok('...both nodes put it in', until(lambda: all(n.get('policy_applied') and (n.get('policy') or {}).get('managed') for n in view()['nodes'])),
   [(n.get('policy_applied'), n.get('policy_error')) for n in view()['nodes']])
ok('...in the files', 'minlen = 14' in open(SEC + '/pwquality.conf.d/50-otp.conf').read())
ok('...the view says the policy and the least length for the pages', view()['policy']['managed'] and view()['pw_min'] == 14)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpp_bad', 'password': 'short-but-12', 'nodes': both}, S)
ok('a password shorter than the policy: refused at once (%s)' % c, c == 400 and 'policy' in x.get('error', ''), x)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpp_bad', 'password': 'onlysmallletterslong', 'nodes': both}, S)
ok('...one of too few kinds: refused (%s)' % c, c == 400 and 'kinds' in x.get('error', ''), x)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpp_bad', 'password': 'Aaaa-111-bbbb-2', 'nodes': both}, S)
ok('...one with a character more than twice in a row: refused (%s)' % c, c == 400 and 'row' in x.get('error', ''), x)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpp_web', 'password': 'Otpp_web-Good-245', 'nodes': both}, S)
ok('...one with the user\'s name in it: refused (%s)' % c, c == 400 and 'name' in x.get('error', ''), x)
c, x = call('node1', '/api/osusers', {'action': 'add', 'name': 'otpp_web', 'password': 'Correct-Horse-245', 'nodes': both}, S)
ok('...one it takes: made (%s)' % c, c == 200 and until(lambda: os.path.exists('/home/otpp_web')), x)
ok('no user made for the refused ones', sh('getent', 'passwd', 'otpp_bad').returncode != 0)
until(lambda: all(any(u['name'] == 'otpp_web' for u in n.get('users') or []) for n in view()['nodes']))
c, x = call('node1', '/api/osusers', {'action': 'aging', 'name': 'otpp_web', 'max_days': 30, 'warn_days': 3, 'nodes': both}, S)
ok('a user\'s own aging from the pages (%s %s)' % (c, x.get('error', '')), c == 200 and until(lambda: [ln.split(':') for ln in open('/etc/shadow') if ln.startswith('otpp_web:')][0][4] == '30'))
ev = [dict(e)['words'] for e in st_.db.rows("SELECT words FROM events WHERE words LIKE '%password policy%'")]
ok('in Events: who set the policy, with what', any('local set the password policy of the local users: at least 14 characters' in w for w in ev), ev)
c, x = call('node1', '/api/osusers', {'action': 'policy', 'policy': dict(C, managed=False)}, S)
ok('given back to the system from the pages', c == 200 and until(lambda: not os.path.exists(SEC + '/pwquality.conf.d/50-otp.conf')
   and all(n.get('policy_applied') for n in view()['nodes'])))
ok('...every file as it was', all(open(p).read() == t for p, t in FILES.items()) and open(DEFS).read() == ORIG_DEFS)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
