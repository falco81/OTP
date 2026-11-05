#!/usr/bin/env python3
"""1.0.249: the fixes of the first round of a review - the root helper's and the daemon's side.

Run as root: python3 t_r249.py VERSION"""
import os, sys, json, time, subprocess, tempfile, atexit, pwd, importlib.util, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.249'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


TOP = tempfile.mkdtemp(prefix='otp-r249-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
os.environ['OTP_VIP_NO_SERVICES'] = '1'
os.environ['OTP_STATE'] = TOP + '/hstate'; os.makedirs(TOP + '/hstate/web')
os.environ['OTP_ROOT_AUTHKEYS'] = TOP + '/root_authorized_keys'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# ---- the helper --------------------------------------------------------------------------------------------
# authselect's old note: a FIFO there is not waited on
os.mkfifo(os.path.join(W.STATE_DIR, 'pwpolicy-orig.json'))
t0 = time.time()
got = W.pwp_orig_read()
ok('a FIFO in place of the old note of the policy: not waited on', time.time() - t0 < 5 and isinstance(got, dict), got)
os.unlink(os.path.join(W.STATE_DIR, 'pwpolicy-orig.json'))

# a kept user's shell: only the known no-login paths outside /etc/shells
ok('the no-login paths are exact', '/usr/sbin/nologin' in W.NOLOGIN_PATHS and '/tmp/nologin' not in W.NOLOGIN_PATHS)
src = open(V + '/deploy/otp_web.py').read()
ok('putback: a shell outside /etc/shells only by its exact path', 'shell in NOLOGIN_PATHS and os.path.isfile(shell)' in src)

# the console notice put back after a trial: escaped once only
paths = {'issue': TOP + '/issue.d/otp.issue', 'motd': TOP + '/motd.d/otp', 'banner': TOP + '/banner'}
os.makedirs(TOP + '/issue.d'); os.makedirs(TOP + '/motd.d')
W.notice_paths = lambda: paths
W.notice_set('issue', 'C:\\path and \\\\share')
first = open(paths['issue']).read()
st = {'dropin': None, 'banner': None, 'issue': first, 'motd': None}
W.SSH_DIR = TOP; W.sshd_reload = lambda: None
try:
    W.sshd_put_back(st)
except Exception as e:      # noqa: BLE001 - what it does after the notices is not tested here
    pass
ok('a notice put back after a trial not kept: its backslashes as they were', open(paths['issue']).read() == first,
   (first, open(paths['issue']).read()))

# SELinux: since_lost only within the machine's start of the upgrade
os.environ.get('OTP_ROOT_STATE')
W.ROOT_STATE_DIR = TOP + '/rootstate'
boot = open('/proc/sys/kernel/random/boot_id').read().strip()
ok('SELinux note: no note of the upgrade yet - noted, and lost now', W.se_upgrade_boot_same() is True and
   open(os.path.join(W.ROOT_STATE_DIR, W.SE_UPGRADE_BOOT)).read().strip() == boot)
open(os.path.join(W.ROOT_STATE_DIR, W.SE_UPGRADE_BOOT), 'w').write('another-boot\n')
ok('SELinux note: after a restart of the machine no more', W.se_upgrade_boot_same() is False)

# pgtls: the files before read never through a link
ok('pgtls: the files before read by pg_file_read, a plain file of postgres only',
   "was_files[name] = pg_file_read(p) if (stat.S_ISREG(st.st_mode) and" in src)

# ---- the daemon's side ---------------------------------------------------------------------------------------
os.environ['OTP_STATE'] = TOP + '/dstate'; os.makedirs(TOP + '/dstate')
open(TOP + '/dstate/guard.json', 'w').write('{}')
sys.path.insert(0, V); sys.argv = ['otp']
import otp
otp.CONFIG.update({'db_engine': 'sqlite', 'node_name': 'nodea'})
store = otp.Storage(otp.open_db()); store.db.make_tables(); otp.sealing_key(make=True)
otp.CONFIG['db_guard'] = 1

# a signed row deleted with its signature: the last value put back is refused
store.set_meta('sshotp:u:novak', json.dumps({'secret': 'x', 'at': 1}))
had = store.db.row("SELECT v FROM meta WHERE k = 'sshotp:u:novak'")['v']
try:
    otp.sshotp_remove(store, "novak", "test")
except Exception as e:      # noqa: BLE001
    store.drop_meta('sshotp:u:novak')
store.db.run("INSERT INTO meta (k, v) VALUES ('sshotp:u:novak', ?)", (had,))
signed = otp.dbguard_meta_signed('sshotp:u:novak')
ok('a signed row taken away and put back as it was: not taken (%s)' % ('signed' if signed else 'not signed'),
   not signed or not otp.dbguard_ok(store.db, 'm', 'sshotp:u:novak', had, quiet=True))
ok('drop_meta says how many it took', store.drop_meta('sshotp:u:novak') == 1 and store.drop_meta('sshotp:u:novak') == 0)

# switched on: every version taken as adopted, nothing left for the next start
otp.DBGUARD['adopted'] = []
otp.dbguard_resign(store, 'test')
ok('guard switched on (resigned): adopted every version and the tokens',
   set(otp.DBGUARD_SINCE) | {'tokens'} <= set(otp.DBGUARD['adopted']), otp.DBGUARD['adopted'])
ok('...written to guard.json', set(otp.DBGUARD_SINCE) <= set(json.load(open(TOP + '/dstate/guard.json')).get('adopted') or []))
otp.DBGUARD['good'] = {'x': 1}
otp.dbguard_forget_seen('test')
ok('counts forgotten: the values last found good too', otp.DBGUARD['good'] == {})

# the putback hold kept in a file
otp.keep_hold_set(time.time() + 3600)
ok('putback hold: in a file, read back', otp.keep_hold_until() > time.time() + 3000 and otp.KEEP_HOLD_FILE.exists())
otp.keep_hold_set(0)
ok('putback hold: taken away', otp.keep_hold_until() == 0 and not otp.KEEP_HOLD_FILE.exists())
ok('a copy\'s putback row is not put back', any('host:putback:'.startswith(p) for p in otp.META_TRANSIENT))

# config.json through a link: refused
real = TOP + '/secret.json'; open(real, 'w').write(json.dumps({'root_only': 'x'}))
link = TOP + '/config.json'; os.symlink(real, link)
try:
    otp.write_file_settings({'db_guard': 1}, link)
    ok('config.json a link: refused', False, open(real).read())
except OSError as e:
    ok('config.json a link: refused, nothing written', 'link' in str(e) and json.load(open(real)) == {'root_only': 'x'}, e)
os.unlink(link)
otp.write_file_settings({'db_guard': 1}, link)
ok('config.json a plain file: written as before', json.load(open(link)).get('db_guard') == 1)

# names: as the directory reads them
ok('admin name: after the last backslash', otp.admin_name_parts('x1\\CORP\\novak') == ('novak', 'sam'))
ok('admin name: DOMAIN\\name as before', otp.admin_name_parts('CORP\\novak') == ('novak', 'sam'))

# alias: more than one account answering - refused
class FakeAd(object):
    def __init__(self, ans):
        self.ans = ans

    def find_user(self, name, how):
        return self.ans
got = otp.Authenticator.alias_clash(FakeAd({'many': True}), 'xavier@corp.local', 'xavier@corp.cz', {'dn': 'cn=y'})
ok('alias: more than one account answers to the token\'s name - refused', 'more than one' in got, got)
got = otp.Authenticator.alias_clash(FakeAd({'dn': 'cn=x'}), 'xavier@corp.local', 'xavier@corp.cz', {})
ok('alias: a name the directory does not know, the main one another\'s - refused', 'another account' in got, got)
got = otp.Authenticator.alias_clash(FakeAd({'dn': 'cn=y'}), 'xavier@corp.local', 'xavier@corp.cz', {'dn': 'CN=y'})
ok('alias: the same account - let in', got == '', got)

# the local users: sudo needs a password
otp.host_nodes = lambda st: ['nodea']
store.set_meta('host:users:now:nodea', json.dumps({'at': time.time(), 'uid_min': 1000, 'uid_max': 60000, 'used': [], 'users': []}))
try:
    otp.osu_ask(store, ['nodea'], 'add', 'test', name='otpq_x', sudo=True)
    ok('a local user with sudo and no password: refused', False)
except ValueError as e:
    ok('a local user with sudo and no password: refused', 'sudo asks' in str(e), e)
except Exception as e:      # noqa: BLE001
    ok('a local user with sudo and no password: refused', 'sudo asks' in str(e), e)

# FTPS: how the server is checked is part of which server it is
otp.CONFIG['db_guard'] = 0
t = {'kind': 'ftps', 'name': 'x', 'host': 'h.example', 'port': 21, 'user': 'u', 'path': '/b', 'password': 'Pw-123456789',
     'tls_check': 'system'}
try:
    otp.rb_save(store, t, "test")
    saved = otp.rb_targets(store)[0]
    ok('FTPS saved', True)
    try:
        otp.rb_save(store, dict({k: v for k, v in saved.items() if k != 'password'}, tls_check='none'), "test")
        ok('FTPS: the check switched off without the password typed again: refused', False)
    except ValueError as e:
        ok('FTPS: the check switched off without the password typed again: refused', 'type the password again' in str(e), e)
    otp.rb_save(store, dict({k: v for k, v in saved.items() if k != 'password'}, user='u2'), "test")
    ok('FTPS: another change keeps the password as before', otp.rb_targets(store)[0].get('user') == 'u2')
except AttributeError as e:
    ok('FTPS save functions found', False, e)

# download tickets: which node holds it
otp.held_note(store, 'abc')
store.db.run("UPDATE meta SET v = ? WHERE k LIKE 'held:%'", (json.dumps({'node': 'nodeb', 'at': time.time()}),))
ok('a download waiting on the other node: said which', 'nodeb' in otp.held_words(store, 'abc', 'gone'))
ok('...one nobody holds: the words as before', otp.held_words(store, 'zzz', 'gone') == 'gone')

# --enroll: DOMAIN\name refused
r = sh(sys.executable, V + '/otp.py', '--enroll', 'CORP\\novak', env=dict(os.environ, OTP_STATE=TOP + '/dstate', OTP_STAY_ROOT='1'))
ok('--enroll CORP\\novak: refused', r.returncode != 0 and 'looked up as the name alone' in (r.stderr + r.stdout),
   (r.returncode, (r.stderr + r.stdout)[-300:]))


# ---- rounds 2-5 ----------------------------------------------------------------------------------------------
# backups into a folder: never through a link planted at a known name
fold = TOP + '/fold'; os.makedirs(fold)
victim = TOP + '/victim'; open(victim, 'w').write('keep me')
src = TOP + '/bk.enc'; open(src, 'wb').write(b'Salted__' + os.urandom(64))
nm = 'otp-backup-otp-nodea-20261105-030000.tar.gz.enc'
os.symlink(victim, os.path.join(fold, '.%s.part' % nm))
try:
    tr = otp.rb_transport({'kind': 'folder', 'path': fold, 'id': 'x', 'name': 'f'})
    tr.open(); tr.put(src, nm)
    ok('folder: a link planted at the known part name - the file it leads to untouched',
       open(victim).read() == 'keep me' and open(os.path.join(fold, nm), 'rb').read() == open(src, 'rb').read())
except Exception as e:      # noqa: BLE001
    ok('folder: a link planted at the known part name - the file it leads to untouched', False, e)

# retention: never the one just sent, never counting one stamped ahead
class FakeTr(object):
    def __init__(self, names):
        self.names = list(names); self.gone = []
    def list(self):
        return [{'name': n, 'size': 1} for n in self.names]
    def delete(self, n):
        self.gone.append(n)
site = otp.rb_slug(otp.CONFIG.get('site_name') or 'otp'); me = otp.rb_slug(otp.node_name())
mk = lambda st: 'otp-backup-%s-%s-%s.tar.gz.enc' % (site, me, st)
future = mk('20991231-000000'); just = mk(time.strftime('%Y%m%d-%H%M%S'))
ft = FakeTr([future, just, mk('20200101-000000')])
gone = otp.rb_retain(ft, 1, 0, just=just)
ok('retention keep 1: the one just sent stays, a future-stamped one is not counted', just not in gone and future not in gone, gone)

# token names: a dot at the end of the realm refused, a plain name with one not
ok('a name ending in a dot after its realm: refused', 'dot' in otp.token_name_problem('novak@corp.cz.'))
ok('a plain name ending in a dot: as before', otp.token_name_problem('jan.') == '')

# the database names root lets in: never PostgreSQL's own
for db, us in (('postgres', 'otp'), ('otp', 'postgres'), ('all', 'otp'), ('otp', 'replication')):
    try:
        otp.pg_names_otps(None, db, us)
        ok('pg names %s/%s refused' % (db, us), False)
    except ValueError:
        ok('pg names %s/%s refused' % (db, us), True)
try:
    otp.pg_names_otps(None, 'otp_x', 'otp_x')
    ok('pg names otp_x/otp_x taken', True)
except ValueError as e:
    ok('pg names otp_x/otp_x taken', False, e)

# settings checked without spaces are kept so
ok('a metrics token pasted with a space: kept without', otp.check_setting('metrics_token', ' ' + 'a' * 32 + ' ') == 'a' * 32)

# the password policy: 0 days refused, a stored 0 read as never
try:
    otp.pwp_checked_api({'managed': 1, 'max_days': 0})
    ok('policy: a password good for 0 days refused', False)
except ValueError as e:
    ok('policy: a password good for 0 days refused, the box named', 'days a password is good' in str(e), e)
store.set_meta('host:pwpolicy:conf', json.dumps({'managed': True, 'max_days': 0}))
ok('policy: a stored 0 read as never running out', otp.pwp_conf(store)['max_days'] == 99999)
store.drop_meta('host:pwpolicy:conf')

# the network on trial: put back by root when the database cannot be read and its time ran out
asked = []
otp.net_root = lambda r, t=0: asked.append(r) or {'said': []}
otp.NET_LOCAL_TRIAL.write_text(json.dumps({'id': 'j1', 'snap': 's1', 'until': time.time() - 5}))
otp.net_local_trial_lost()
ok('network trial: root asked to put it back, the note gone after', asked and asked[0].get('do') == 'restore' and
   asked[0].get('snapshot') == 's1' and not otp.NET_LOCAL_TRIAL.exists(), asked)
asked[:] = []
otp.NET_LOCAL_TRIAL.write_text(json.dumps({'id': 'j1', 'snap': 's1', 'until': time.time() + 600}))
otp.net_local_trial_lost()
ok('network trial: not before its time', not asked)
otp.NET_LOCAL_TRIAL.unlink()

# SELinux permissive refused under high security
otp.CONFIG['high_security'] = 1
try:
    otp.selinux_ask(store, otp.node_name(), 'permissive', 'test')
    ok('SELinux permissive under high security: refused', False)
except ValueError as e:
    ok('SELinux permissive under high security: refused', 'high security' in str(e), e)
otp.CONFIG['high_security'] = 0

# a .totp of 10 s steps imported: its last step kept in its own steps
now10 = int(time.time()) // 10
txt = 'JBSWY3DPEHPK3PXP\n" STEP_SIZE 10\n" OTP_LAST_STEP %d\n' % now10
try:
    otp.import_totp(store, 'zz-r249-ten', txt, by='test', replace=True)
    t = store.token('zz-r249-ten') or {}
    ok('a 10 s token imported: its last step as the file had it', int(t.get('last_step') or 0) == now10, t.get('last_step'))
except Exception as e:      # noqa: BLE001
    ok('a 10 s token imported: its last step as the file had it', False, e)

print('ALL %d / %d' % (sum(R), len(R)))
