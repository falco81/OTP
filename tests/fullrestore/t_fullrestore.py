# t_fullrestore.py VERSION [guard] - the whole system backed up and put back (1.0.231), with the guard of root's
# actions off (as until now) or on ("guard"): a backup sent to a destination (a folder), the system then damaged -
# a token, an account, a setting, the VIP's row, a client taken away or changed - and the backup put back from
# the destination on the pages: everything back, the codes let in through RADIUS, the administrator signs in,
# nothing refused by the guard. Then the same backup put back on a new machine (an empty state, no key) with
# otp --restore-bundle: the tokens open with the key that came with it, RADIUS lets them in.
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, glob, base64, shutil
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.231'
GUARD = 'guard' in sys.argv[2:]
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-fr-')
D = TOP + '/m1'; D2 = TOP + '/m2'
for x in (D, D2):
    os.makedirs(x + '/run')
os.makedirs(TOP + '/dest')
APORT, RPORT = 30591 + (5 if GUARD else 0), 36210 + (10 if GUARD else 0)


def conf(d, name):
    c = {'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT, 'radius_acct_port': RPORT + 1,
         'api_port': APORT, 'node_name': name}
    if GUARD:
        c['db_guard'] = 1
    json.dump(c, open(d + '/config.json', 'w'))
    return dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d, OTP_RUN=d + '/run', OTP_STAY_ROOT='1')


env = conf(D, 'otp1')
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-231!', must_change=0)
st.add_account('second', 'tokenadmin', 'Second-Admin-Pass-231!', must_change=0)
st.client_save({'name': 'nas', 'address': '127.0.0.1', 'secret': 'nas-secret-231', 'enabled': 1})
st.realm_save({'name': 'local', 'suffix': '*', 'directory': '', 'lookup': 'none', 'auth_mode': 'otp', 'enabled': 1})
tk = otp.Tokens(st)
KEYS = {}
for i in range(6):
    KEYS['user%d' % i] = tk.enroll('user%d' % i, 'test')['secret']
st.set_meta('web:vip', json.dumps({'on': False, 'address': '10.20.30.40/24', 'vrid': 51}))
procs = {}


def start(e, d):
    p = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=e, stdout=open(d + '/d.out', 'a'),
                         stderr=subprocess.STDOUT)
    procs[d] = p
    time.sleep(6)
    return open(d + '/run/api-token').read().strip()


def stop(d):
    p = procs.pop(d, None)
    if p:
        p.terminate(); p.wait(15)


atexit.register(lambda: [stop(d) for d in list(procs)])
TOK = start(env, D)
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def login():
    return call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-231!'})[1].get('token')


def job():
    end = time.time() + 180
    while time.time() < end:
        j = call('/api/rbackup', {'action': 'job'}, S)[1].get('job') or {}
        if not j.get('running'):
            return j
        time.sleep(0.5)
    return {}


def radius(user):
    k = KEYS[user]
    c, _w, _ = otp.radius_ask('127.0.0.1', RPORT, 'nas-secret-231', user,
                              otp.totp(base64.b32decode(k + '=' * (-len(k) % 8))), timeout=8, tries=1)
    return c


tag = '[guard on] ' if GUARD else '[guard off] '
S = login()
if GUARD:
    c, x = call('/api/status', None, S)
    ok(tag + 'the guard is on in config.json of the machine', json.load(open(D + '/config.json')).get('db_guard') == 1 and c == 200, x)
c, x = call('/api/settings', {'settings': {'rbackup_password': 'Backup-Pass-231-xyz', 'radius_reject_reason': 0,
                                           'logs_keep': 21}}, S)
ok(tag + 'settings saved: %s' % c, c == 200, x)
c, x = call('/api/rbackup', {'action': 'save', 'target': {'kind': 'folder', 'name': 'here', 'path': TOP + '/dest', 'enabled': 1}}, S)
ok(tag + 'a folder as the destination: %s' % c, c == 200, x)
c, x = call('/api/rbackup', {'action': 'run'}, S)
j = job()
files = sorted(glob.glob(TOP + '/dest/otp-backup-*.enc'))
ok(tag + 'the backup sent: %s' % (j.get('error') or files[-1:]), not j.get('error') and files, j)

# ---- the system damaged ------------------------------------------------------------------------------
st.token_drop('user0')
st.drop_account('second')
call('/api/settings', {'settings': {'radius_reject_reason': 1, 'logs_keep': 99}}, S)
st.set_meta('web:vip', json.dumps({'on': True, 'address': '192.0.2.99/24', 'vrid': 99}))
st.client_save({'name': 'evil', 'address': '0.0.0.0/0', 'secret': 'evil-secret-1', 'enabled': 1})
ok(tag + 'damaged: a token, an account, settings, the VIP, a client', not st.token('user0') and not st.account('second'))

# ---- put back from the destination, on the pages ------------------------------------------------------------
c, x = call('/api/rbackup', {'action': 'list', 'id': (call('/api/rbackup', None, S)[1].get('targets') or [{}])[0].get('id')}, S)
names = [f.get('name') for f in (x.get('files') or [])]
tid = (call('/api/rbackup', None, S)[1].get('targets') or [{}])[0].get('id')
c, x = call('/api/rbackup', {'action': 'restore', 'id': tid, 'name': names[0] if names else os.path.basename(files[-1]),
                             'password': 'Backup-Pass-231-xyz'}, S)
ok(tag + 'the backup put back from the destination: %s %s' % (c, x.get('error', '')), c == 200, x)
time.sleep(1)
j = call('/api/db', {'action': 'job'}, S)
for _ in range(240):
    j = call('/api/db', {'action': 'job'}, login() or S)[1].get('job') or {}
    if not j.get('running'):
        break
    time.sleep(0.5)
ok(tag + '...done: %s' % (j.get('error') or 'ok'), not j.get('error'), j)
time.sleep(3)
S = login()
ok(tag + 'the administrator signs in after it', bool(S))
ok(tag + 'the token taken away is back', st.token('user0') is not None)
ok(tag + 'the account taken away is back', st.account('second') is not None)
c, x = call('/api/settings', None, S)
got = {s_['key']: s_['value'] for s_ in x.get('settings') or []}
ok(tag + 'the settings as they were (%s, %s)' % (got.get('radius_reject_reason'), got.get('logs_keep')),
   str(got.get('logs_keep')) == '21' and not got.get('radius_reject_reason'), got.get('logs_keep'))
ok(tag + 'the client put in after the backup is gone', not any(c_['name'] == 'evil' for c_ in st.clients()))
otp.CONFIG['db_guard'] = 1 if GUARD else 0
otp.DBGUARD['seen'] = None
vip = st.get_meta('web:vip')
ok(tag + 'the VIP\'s row as it was, read as otp\'s word (%s)' % vip, vip and json.loads(vip)['address'] == '10.20.30.40/24', vip)
time.sleep(1)
ok(tag + 'RADIUS lets in every token\'s code after it', all(radius(u) == 2 for u in ('user0', 'user3')))
c, x = call('/api/hisec', None, S)
ok(tag + 'nothing refused by the guard after it (%s)' % ((x.get('guard') or {}).get('refused')),
   not (x.get('guard') or {}).get('refused'), x.get('guard'))
stop(D)

# ---- the same backup on a new machine ----------------------------------------------------------------------
env2 = conf(D2, 'fresh')
pw = TOP + '/pw'; open(pw, 'w').write('Backup-Pass-231-xyz\n')
r = subprocess.run([sys.executable, V + '/otp.py', '--restore-bundle', files[-1], '--passphrase-file', pw, '--yes'],
                   env=env2, capture_output=True, text=True, timeout=300)
ok(tag + 'a new machine: otp --restore-bundle (%s)' % r.returncode, r.returncode == 0, (r.stdout + r.stderr)[-400:])
ok(tag + '...the key of the tokens came with it', open(D2 + '/secrets.key', 'rb').read() == open(D + '/secrets.key', 'rb').read())
ok(tag + '...the node\'s name came with it', json.load(open(D2 + '/config.json')).get('node_name') == 'otp1')
D = D2
TOK = start(env2, D2)
S = login()
ok(tag + '...the administrator signs in there', bool(S))
ok(tag + '...RADIUS lets the tokens in there', all(radius(u) == 2 for u in ('user1', 'user4')))
c, x = call('/api/hisec', None, S)
ok(tag + '...nothing refused by the guard there', not (x.get('guard') or {}).get('refused'), x.get('guard'))
stop(D2)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
