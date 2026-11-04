# t_r248.py VERSION - the fixes of 1.0.248 (bug hunt, round 1), on this machine as root.
# The root helper by itself: a putback gives no keys to an account of the system that has a kept
# user's name, nor to one of another UID; key lines with options left out; one user that cannot be
# made does not stop the others nor root's keys; an "add" of a user there already changes nothing of
# theirs (password, sudo); "must change" never for a user without a password; unlock takes every '!';
# the full name's other fields kept when the name is saved again; a shell it has kept as it is; the
# authselect features otp switched on read from root's folder, only otp's two.
# The daemon's side: '0' from the command line switches a check off; the UID of "make it on B too" the
# one the user has on A; an add asked and not done keeps its UID; a keep row never sealed is not
# opened; with the guard on, the remote backups' destinations and password unsigned are not taken,
# and rows of a version before signed once at its first start; a putback row dropped with its
# signature cannot be put back; the putback is not tried at every tick when it fails; a restore on a
# machine with tokens marks no putback.
# Usage (as root): python3 t_r248.py VERSION
import os, sys, json, time, subprocess, tempfile, atexit, pwd, grp, importlib.util

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.248'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


USERS = ('otpr_ann', 'otpr_ben', 'otpr_sys', 'otpr_cat', 'otpr_dan', 'otpr_eve')
for u in USERS:
    sh('userdel', '-r', u)
sh('groupdel', 'otpr_cat')
atexit.register(lambda: ([sh('userdel', '-r', u) for u in USERS], sh('groupdel', 'otpr_cat')))
ADMIN = 'wheel' if sh('getent', 'group', 'wheel').returncode == 0 else 'sudo'
KEY1 = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGq0b5tY1y0d8m2m0yJx0fQm4b7r2tC8e1m6Yx2Z3a4B one@r248'
KEY2 = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHf9mXb1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0cD two@r248'
OPTKEY = 'command="/bin/true",no-pty ' + KEY2


def shadow(name):
    for ln in open('/etc/shadow'):
        p = ln.rstrip('\n').split(':')
        if p[0] == name:
            return p
    return None


def hash_of(pw):
    return sh('openssl', 'passwd', '-6', '-stdin', input=pw + '\n').stdout.strip()


def keys_of(name):
    p = pwd.getpwnam(name)
    try:
        return [x for x in open(os.path.join(p.pw_dir, '.ssh', 'authorized_keys')).read().split('\n') if x.strip()]
    except OSError:
        return []


os.environ['OTP_VIP_NO_SERVICES'] = '1'
TOP = tempfile.mkdtemp(prefix='otp-r248-')
os.environ['OTP_STATE'] = TOP + '/hstate'; os.makedirs(TOP + '/hstate/web')
os.environ['OTP_ROOT_AUTHKEYS'] = TOP + '/root_authorized_keys'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# ---- the helper: putback -----------------------------------------------------------------------------------
sh('useradd', '-r', '-m', '-s', '/bin/bash', 'otpr_sys')         # a system account
sh('groupadd', 'otpr_cat')                                      # its group there: useradd -U fails
sysu = pwd.getpwnam('otpr_sys')
lo, hi = W.uid_range()
free = [u for u in range(lo + 3000, hi) if not any(p.pw_uid == u for p in pwd.getpwall())][:5]
k = {'users': [
        {'name': 'otpr_sys', 'uid': free[0], 'gecos': '', 'shell': '/bin/bash', 'hash': '', 'sudo': True},
        {'name': 'otpr_cat', 'uid': free[1], 'gecos': 'Cat', 'shell': '/bin/bash', 'hash': ''},
        {'name': 'otpr_ann', 'uid': free[2], 'gecos': 'Ann\nRoom', 'shell': '/var/lib/otp/evil', 'hash': hash_of('Ann-pw-1234567'),
         'lastchg': '19000', 'max': '99999', 'min': '0', 'warn': '7'},
        {'name': 'otpr_eve', 'uid': free[3], 'gecos': 'Eve', 'shell': '/sbin/nologin', 'hash': ''}],
     'keys': {'otpr_sys': [KEY1], 'otpr_ann': [KEY1, OPTKEY], 'otpr_eve': [KEY1]},
     'root_keys': [KEY2, OPTKEY]}
said = '; '.join(W.keep_putback(k))
ok('putback: the system account of the same name got no key', not keys_of('otpr_sys'), said)
ok('putback: ... and said so', 'otpr_sys is here with UID' in said, said)
ok('putback: the user whose group is there not made - said, the others go on', 'otpr_cat' in said and 'not put back' in said, said)
ann = pwd.getpwnam('otpr_ann') if any(p.pw_name == 'otpr_ann' for p in pwd.getpwall()) else None
ok('putback: ann made with her UID', ann is not None and ann.pw_uid == free[2], said)
ok('putback: ann\'s shell not taken from a file of the service\'s folder', ann is not None and ann.pw_shell == '/bin/bash', ann and ann.pw_shell)
ok('putback: ann\'s full name without the line break', ann is not None and '\n' not in ann.pw_gecos, ann and ann.pw_gecos)
ok('putback: ann\'s plain key put back, the line with options left out', ann is not None and keys_of('otpr_ann') == [KEY1], ann and keys_of('otpr_ann'))
rk = [x for x in open(TOP + '/root_authorized_keys').read().split('\n') if x.strip()] if os.path.exists(TOP + '/root_authorized_keys') else []
ok('putback: root\'s plain key put back after a user that failed, its option line left out', rk == [KEY2], rk)
ok('putback: the lines left out are said', 'with options' in said, said)
eve = pwd.getpwnam('otpr_eve') if any(p.pw_name == 'otpr_eve' for p in pwd.getpwall()) else None
ok('putback: a user who may not sign in made again without a shell to sign in with',
   eve is not None and os.path.basename(eve.pw_shell) in ('nologin', 'false'), eve and eve.pw_shell)
ok('putback: ... and given its keys back (for what it may do)', eve is not None and keys_of('otpr_eve') == [KEY1])

# ---- the helper: add, must_change, unlock, set -----------------------------------------------------------------
W.lu_do({'do': 'add', 'name': 'otpr_ben', 'hash': hash_of('Ben-pw-1234567'), 'sudo': True, 'shell': '/bin/bash', 'gecos': 'Ben,Room 12,555'})
h0 = shadow('otpr_ben')[1]
got = W.lu_do({'do': 'add', 'name': 'otpr_ben', 'hash': hash_of('Other-pw-98765'), 'sudo': False, 'must_change': True,
               'shell': '/bin/bash', 'gecos': 'Ben'})
ok('add of one there: said so', 'here already' in got.get('said', ''), got.get('said'))
ok('add of one there: the password kept', shadow('otpr_ben')[1] == h0)
ok('add of one there: sudo kept', 'otpr_ben' in grp.getgrnam(ADMIN).gr_mem)
ok('add of one there: not asked to change', shadow('otpr_ben')[2] != '0', shadow('otpr_ben')[2])
W.lu_do({'do': 'add', 'name': 'otpr_dan', 'must_change': True, 'shell': '/bin/bash'})
ok('must change with no password: not asked for one (key only)', shadow('otpr_dan')[2] != '0', shadow('otpr_dan')[2])
sh('passwd', '-l', 'otpr_ben'); sh('usermod', '-L', 'otpr_ben')
p = shadow('otpr_ben')[1]
if not p.startswith('!!'):
    sh('usermod', '-p', '!!' + h0, 'otpr_ben')
W.lu_do({'do': 'unlock', 'name': 'otpr_ben'})
ok('unlock: every \'!\' taken away', shadow('otpr_ben')[1] == h0, shadow('otpr_ben')[1][:6])
W.lu_do({'do': 'set', 'name': 'otpr_ben', 'gecos': 'Ben', 'shell': '/bin/bash'})
ok('the name saved again: its other fields kept', pwd.getpwnam('otpr_ben').pw_gecos == 'Ben,Room 12,555', pwd.getpwnam('otpr_ben').pw_gecos)
sh('usermod', '-s', '/bin/false', 'otpr_ben')
try:
    W.lu_do({'do': 'set', 'name': 'otpr_ben', 'gecos': 'Benjamin', 'shell': '/bin/false'})
    ok('a shell it has, not of /etc/shells: kept, the name changed (its other fields kept)',
       pwd.getpwnam('otpr_ben').pw_gecos == 'Benjamin,Room 12,555' and pwd.getpwnam('otpr_ben').pw_shell == '/bin/false',
       pwd.getpwnam('otpr_ben'))
except W.Refused as e:
    ok('a shell it has, not of /etc/shells: kept, the name changed', False, e)

# ---- the helper: authselect's features, from root's folder ---------------------------------------------------
ok('the features otp switched on are kept in a folder of root\'s', W.PWP_ORIG.startswith(W.ROOT_STATE_DIR) and
   not W.PWP_ORIG.startswith(W.STATE_DIR + '/'), W.PWP_ORIG)
with open(os.path.join(W.STATE_DIR, 'pwpolicy-orig.json'), 'w') as f:
    json.dump({'features': ['without-nullok', 'with-pamaccess', 'with-faillock']}, f)
got = W.pwp_orig_read()
ok('a file of the service\'s folder: only otp\'s features taken from it', got.get('features') == ['with-faillock'], got)

# ---- the daemon's side ------------------------------------------------------------------------------------
os.environ['OTP_STATE'] = TOP + '/dstate'; os.makedirs(TOP + '/dstate')
# A node that ran a version before with the guard: its counts there already (an empty file).
open(TOP + '/dstate/guard.json', 'w').write('{}')
sys.path.insert(0, V); sys.argv = ['otp']
import otp
otp.CONFIG.update({'db_engine': 'sqlite', 'node_name': 'nodea'})
store = otp.Storage(otp.open_db()); store.db.make_tables(); otp.sealing_key(make=True)
c = otp.pwp_checked_api({'managed': '1', 'dictcheck': '0', 'usercheck': '0', 'existing': '0'})
ok('policy: \'0\' switches the dictionary and name checks off', c['dictcheck'] == 0 and c['usercheck'] == 0, c)
ok('policy: \'0\' is no yes for existing, \'1\' is for managed', c['existing'] is False and c['managed'] is True, c)
now = lambda users, used: json.dumps({'at': time.time(), 'uid_min': 1000, 'uid_max': 60000, 'used': used, 'users': users})
otp.host_nodes = lambda st: ['nodea', 'nodeb']
store.set_meta('host:users:now:nodea', now([{'name': 'alice', 'uid': 1000}, {'name': 'bob', 'uid': 1001}], [1000, 1001]))
store.set_meta('host:users:now:nodeb', now([], []))
ok('UID: bob made on B too has his UID of A', otp.osu_free_uid(store, ['nodeb'], 'bob') == 1001)
ok('UID: a new user takes none of A\'s', otp.osu_free_uid(store, ['nodeb'], 'carl') == 1002)
store.set_meta('host:users:want:nodeb', json.dumps([{'id': 'x1', 'do': 'add', 'name': 'carl', 'uid': 1002, 'at': time.time()}]))
ok('UID: an add asked and not done keeps its UID from the next', otp.osu_free_uid(store, ['nodeb'], 'dora') == 1003)
ok('keep row never sealed: not opened', otp.keep_open({'sealed': json.dumps({'users': []})}, 'nodea') is None)
sealed = otp.seal_secret(json.dumps({'users': []}), 'hostkeep:nodea')
ok('keep row sealed: opened', otp.keep_open({'sealed': sealed}, 'nodea') == {'users': []})

# The guard: the remote backups' rows.
store.db.run("INSERT INTO meta (k, v) VALUES ('rbackup:targets', ?)", (json.dumps([{'id': 'x', 'kind': 'ftp', 'host': 'evil'}]),))
store.db.run("INSERT INTO settings (k, v, at, by_who) VALUES ('rbackup_password', ?, 0, '')", (json.dumps('known'),))
otp.CONFIG['db_guard'] = 1
otp.DBGUARD.update(seen=None)
ok('guard: an unsigned destination of the backups is not taken', otp.rb_targets(store) == [])
ok('guard: an unsigned password of the backups is not taken',
   'rbackup_password' not in otp.dbguard_settings(store.settings_saved(), store))
got = otp.dbguard_adopt(store)
ok('guard: at the first start of the version, rows written before signed once', sorted(got) == ['rbackup:targets', 'rbackup_password'], got)
ok('guard: ... and taken then', len(otp.rb_targets(store)) == 1)
store.db.run("UPDATE meta SET v = ? WHERE k = 'rbackup:targets'", (json.dumps([{'id': 'y', 'kind': 'ftp', 'host': 'evil2'}]),))
ok('guard: once only - written by somebody after it, not taken', otp.dbguard_adopt(store) == [] and otp.rb_targets(store) == [])
# A node with no counts of its own (installed anew, joining): nothing of the database taken as otp's.
otp.DBGUARD['had_file'] = False
otp.DBGUARD['adopted'] = []
store.db.run("INSERT INTO meta (k, v) VALUES ('rbackup:now:nodea@@x', ?)", (json.dumps({'id': 'z', 'at': time.time()}),))
ok('guard: a node new to the cluster signs nothing it finds', otp.dbguard_adopt(store) == [] and
   store.get_meta('rbackup:now:nodea@@x') is None)
otp.DBGUARD['had_file'] = True
store.set_meta('host:putback:nodea', json.dumps({'at': 1}))
old = store.db.value("SELECT v FROM meta WHERE k = 'host:putback:nodea'")
store.drop_meta('host:putback:nodea')
store.db.run("INSERT INTO meta (k, v) VALUES ('host:putback:nodea', ?)", (old,))
ok('guard: a putback row dropped, put back as it was: not taken', store.get_meta('host:putback:nodea') is None)

# The putback not tried at every tick when it fails.
store.db.run("DELETE FROM meta WHERE k = 'host:putback:nodea'")
store.set_meta('host:keep:nodea', json.dumps({'at': time.time(), 'mark': 'm', 'sealed': sealed}))
store.set_meta('host:putback:nodea', json.dumps({'at': time.time()}))
calls = []
def fail_ask(data, wait=60):
    calls.append(data.get('do')); raise ValueError('the helper says no')
otp.users_ask = fail_ask
class D: pass
d = D(); d.store = store
for _ in range(5):
    otp.keep_tick(d)
    for _ in range(50):
        if not otp.KEEP_WORK['busy']:
            break
        time.sleep(0.05)
ok('putback failed: tried once, not at every tick', calls.count('putback') == 1, calls)
ok('putback failed: the kept row not written over meanwhile', 'keep' not in calls, calls)
otp.KEEP_WORK['putback_at'] = 0
for i in range(3):
    otp.KEEP_WORK['putback_at'] = 0
    otp.keep_tick(d)
    for _ in range(50):
        if not otp.KEEP_WORK['busy']:
            break
        time.sleep(0.05)
ok('putback failed three times: given up, said in Events', store.get_meta('host:putback:nodea') is None and
   'could not be put back' in json.dumps(store.events(limit=20), default=str))

# made by another ask between the check and useradd (1.0.248): "there already", not a failure
sh('userdel', '-r', 'otpr_eve')
sh('useradd', '-m', '-s', '/bin/bash', '-U', '--', 'otpr_eve')
real = W.lu_target
W.lu_target = lambda n: None if n == 'otpr_eve' else real(n)
try:
    got = W.lu_do({'do': 'add', 'name': 'otpr_eve', 'shell': '/bin/bash'}).get('said')
except Exception as e:
    got = 'ERR %s' % e
ok('made in between by another ask: said as there already', got == 'otpr_eve was here already', got)
try:
    got = W.lu_do({'do': 'add', 'name': 'otpr_eve', 'shell': '/bin/bash', 'uid': pwd.getpwnam('otpr_eve').pw_uid + 7}).get('said')
except Exception as e:
    got = 'ERR %s' % e
ok('...but with another UID asked: the failure of useradd said', got.startswith('ERR useradd'), got)
W.lu_target = real

print('ALL %d / %d' % (sum(R), len(R)))
