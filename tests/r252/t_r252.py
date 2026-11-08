#!/usr/bin/env python3
"""1.0.252: three rounds of bug, security, HA and UI fixes.

Run as root: python3 t_r252.py VERSION"""
import os, sys, json, time, tempfile, atexit, shutil, re, importlib.util

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.252'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


TOP = tempfile.mkdtemp(prefix='otp-r252-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
os.environ['OTP_STATE'] = TOP + '/dstate'; os.makedirs(TOP + '/dstate')
open(TOP + '/dstate/guard.json', 'w').write('{}')
sys.path.insert(0, V); sys.argv = ['otp']
import otp
otp.CONFIG.update({'db_engine': 'sqlite', 'node_name': 'nodea'})
store = otp.Storage(otp.open_db()); store.db.make_tables(); otp.sealing_key(make=True)
import pathlib; otp.WEB_DIR = pathlib.Path(TOP + '/web'); otp.WEB_DIR.mkdir()
SRC = open(V + '/otp.py').read()
HELPER = open(V + '/deploy/otp_web.py').read()
JS = open(V + '/web/assets/admin.js').read()
CORE = open(V + '/web/assets/core.js').read()


def raw(k, v):
    store.db.run('DELETE FROM meta WHERE k = ?', (k,))
    store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, v))


def beat(name, ver, ago=0):
    store.set_meta('node:' + name, json.dumps({'at': time.time() - ago, 'version': ver, 'address': '127.0.0.9'}))


# ---- round 1 ---------------------------------------------------------------------------------------------
# Back up now asked by the other node: done once, whatever its id
otp.CONFIG['ha_mode'] = 'shared'
beat('nodea', otp.__version__); beat('nodeb', otp.__version__)
started = []
real_start = otp.rb_job_start
otp.rb_job_start = lambda s, by, only=None: started.append(by)
store.set_meta('rbackup:nowdone:nodea', json.dumps(['f%011x' % i for i in range(20)]))
raw('rbackup:now:nodea@@nodeb', json.dumps({'id': '000000000001', 'at': time.time(), 'by': 'x', 'from': 'nodeb'}))


class D: pass


d = D(); d.store = store
otp.RB_JOB['running'] = False
otp.rb_now_asked(d); otp.rb_now_asked(d); otp.rb_now_asked(d)
ok('Back up now of the other node started once, an id smaller than the 20 done', len(started) == 1, started)
done = json.loads(store.get_meta('rbackup:nowdone:nodea'))
ok('...the done list in its order, the new one last', done[-1] == '000000000001' and len(done) == 20, done[-3:])
otp.rb_job_start = real_start
store.db.run("DELETE FROM meta WHERE k LIKE 'rbackup:now%'")

# guard.json: there once written
otp.DBGUARD['had_file'] = False
otp._dbguard_load(); otp.DBGUARD['dirty'] = time.time()
otp.dbguard_flush(force=True)
ok('guard.json written: had_file from now on', otp.DBGUARD.get('had_file') is True)

# an older node counted with no ha_mode (a shared database made by hand)
otp.CONFIG['ha_mode'] = ''
otp.CONFIG['db_guard'] = 1
beat('nodeb', '1.0.247')
older = otp._dbguard_older_nodes(store)
ok('an older node counted without ha_mode', older.get('nodeb') == '1.0.247', older)
beat('nodeb', otp.__version__)
otp.CONFIG['db_guard'] = 0

# a node's own settings made its own when the shared cluster is made
store.save_setting('radius_bind', '10.1.1.1', 't')
store.save_setting('mail_helo', 'nodea.example', 't')
moved = otp.ha_own_node_keys(store, 'nodea')
held = store.settings_saved()
ok('a node\'s own settings made key@node', moved == 2 and held.get('radius_bind@nodea') == '10.1.1.1'
   and 'radius_bind' not in held and held.get('mail_helo@nodea') == 'nodea.example', (moved, held))
ok('...not again', otp.ha_own_node_keys(store, 'nodea') == 0)
ok('ha_mark_shared takes the store (pages and CLI)', 'ha_mark_shared(peer, store)' in SRC and
   "ha_mark_shared(args.ha_peer or '', store" in SRC)

# an ask written by a node no longer of the cluster
otp.CONFIG['ha_mode'] = 'shared'
ask = json.dumps([{'id': 'a1', 'do': 'password', 'name': 'novak', 'hash': 'sealed:2:xxx', 'at': time.time()}])
raw('host:users:want:nodea@@nodez', ask)       # nodez renamed or taken out
raw('host:users:want:nodea@@nodeb', ask)       # nodeb is here: its own to take
otp.NODE_ASK_GONE.clear(); otp.NODE_ASK_GONE_S = 0
otp.node_asks_of_gone_tidy(store)
ok('an ask by a node gone taken away; one by a node here left',
   store.get_meta('host:users:want:nodea@@nodez') is None and store.get_meta('host:users:want:nodea@@nodeb'))
otp.NODE_ASK_GONE_S = 3600
store.db.run("DELETE FROM meta WHERE k LIKE 'host:users:want:%'")

# claim_once of a signed key leaves it signed
otp.CONFIG['db_guard'] = 1
otp.CONFIG['ha_mode'] = ''
store.set_meta('fw_trial_back', '')
won = otp.claim_once(store, 'fw_trial_back', 'trial1')
otp.DBGUARD['refused'].clear()
ok('claim_once of fw_trial_back: won, and still signed', won and
   otp.dbguard_ok(store.db, 'm', 'fw_trial_back', store.get_meta('fw_trial_back'), quiet=True))
ok('...not won twice', not otp.claim_once(store, 'fw_trial_back', 'trial1'))
store.db.run("DELETE FROM meta WHERE k = 'fw_trial_back'")
ok('...a key not there yet made signed too', otp.claim_once(store, 'fw_trial_back', 'trial2') and
   otp.dbguard_ok(store.db, 'm', 'fw_trial_back', store.get_meta('fw_trial_back'), quiet=True))
otp.CONFIG['db_guard'] = 0

# the second step switched on ends the other sign-ins
try:
    dm = otp.Daemon(store, serve=False)
    t1 = store.session_new('admin', 'admin', 'fulladmin', '127.0.0.1', 1)
    t2 = store.session_new('admin', 'other', 'fulladmin', '127.0.0.1', 1)
    keep = store.db.value('SELECT id FROM sessions WHERE name = ?', ('admin',))
    otp.CONFIG['admin_2fa'] = 0
    dm.save_settings({'admin_2fa': 1}, by='t', keep_session=keep)
    names = sorted(r['name'] for r in store.db.rows("SELECT name FROM sessions WHERE kind = 'admin'"))
    ok('admin_2fa on: the other sign-ins ended, the one saving kept', names == ['admin'], names)
    dm.save_settings({'admin_2fa': 0}, by='t')
except Exception as e:                              # noqa: BLE001
    ok('admin_2fa on ends the other sign-ins', False, repr(e))

# ids: true is no id
ok('ids read by _int_id (client secret, directory ca, sessions)',
   "c['id'] == _int_id(b.get('id'))), None)" in SRC and "x['id'] == _int_id(b.get('id'))), None)" in SRC
   and "ident = _int_id(h.body().get('id'))" in SRC)
ok('the command line checks an alias clash before enrolling', 'alias_clash(ad, norm_name(args.enroll)' in SRC)
ok('room looked for before a download or an upload', 'rb_room(h.store)\n        if tid and name:' in SRC and
   '2 * want + BACKUP_ROOM_MIN' in SRC)
ok('the first pin over another check drops the saved password',
   "t.get('tls_check') != 'pin' or t.get('pin') != pin" in SRC)
ok('a destination taken away mid-run: the others still tried', "except ValueError:\n                # Taken away" in SRC
   or "except Exception as e:                      # noqa: BLE001\n                # Taken away" in SRC)
ok('the hatls tick spared', "log_sparing('hatls:'" in SRC)

# the admin's second step: five wrong codes end the sign-in
tok = store.session_new('admin', 'mfa1', 'fulladmin', '127.0.0.1', 1, data={'mfa': 'check'})
sid = store.db.value('SELECT id FROM sessions WHERE name = ?', ('mfa1',))
ok('session_bump counts', [store.session_bump(sid, 'w') for _ in range(3)] == [1, 2, 3])
store.session_drop(sid)
ok('...0 once the session is gone', store.session_bump(sid, 'w') == 0)


class H:
    def __init__(self):
        self.store = store
        self.n = 0

    def failed(self, key):
        self.n += 1


store.session_new('admin', 'mfa2', 'fulladmin', '127.0.0.1', 1)
sid = store.db.value('SELECT id FROM sessions WHERE name = ?', ('mfa2',))
h = H(); codes = []
for _ in range(5):
    try:
        otp._mfa_wrong(h, {'id': sid, 'name': 'mfa2'}, 'k', 'that code is not right')
    except otp.ApiError as e:
        codes.append(e.args[0] if e.args else getattr(e, 'status', None))
gone = store.db.value('SELECT id FROM sessions WHERE id = ?', (sid,)) is None
ok('the fifth wrong code of the second step ends the sign-in', gone and h.n == 5, (codes, gone))
ok('PWP words for deny, unlock_time, fail_interval', all(k in otp.PWP_WORDS for k in ('deny', 'unlock_time', 'fail_interval')))

# the root helper
ok('security keys read (ED25519-SK)', r"\(([\w-]+)\)\s*$" in HELPER)
spec = importlib.util.spec_from_file_location('otp_web_t', V + '/deploy/otp_web.py')
ok('pg_hba.conf only a file of postgres', 'def pg_hba_file(port)' in HELPER and HELPER.count('pg_hba_file(r[\'port\'])') == 3)
ok('the keep of authorized_keys capped', 'def keep_lines_short' in HELPER and '256 * 1024' in HELPER)
# the pages
ok('switches named by their words', 'function swNamedBy' in CORE and JS.count('swNamedBy(sw,') >= 6)
ok('the policy\'s labels keep their own name', "x.removeAttribute('aria-label')" in JS)
ok('SSO Look again given back after an error', 'catch(function (e) { busy(chk, false); oops(e); })' in JS)

# ---- round 2 ---------------------------------------------------------------------------------------------
# a node alone again: a save of its own setting not hidden by its row of the cluster before
otp.CONFIG['ha_mode'] = ''
store.db.run("DELETE FROM meta WHERE k LIKE 'node:%'")
try:
    dm = otp.Daemon(store, serve=False)
    ME = otp.node_name()          # the settings read again: the machine's own name
    beat(ME, otp.__version__)
    store.save_setting('radius_auth_port@' + ME, 1912, 't')
    dm.save_settings({'radius_auth_port': 1914}, by='t')
    held = store.settings_saved()
    ok('alone again: its row of the cluster before taken away at a save', 'radius_auth_port@' + ME not in held
       and held.get('radius_auth_port') == 1914, {k: v for k, v in held.items() if 'radius_auth' in k})
    dm.save_settings({'radius_auth_port': 1812}, by='t')
except Exception as e:                              # noqa: BLE001
    ok('alone again: own setting saved', False, repr(e))
store.drop_setting('radius_bind@nodea'); store.drop_setting('mail_helo@nodea')

# a join under the first node's own name refused
try:
    otp.ha_join({'db': {'db_engine': 'postgres', 'db_host': '127.0.0.1'}, 'key': 'a' * 64,
                 'peer': {'name': otp.node_name()}}, name='')
    ok('a join under the first node\'s name refused', False)
except ValueError as e:
    ok('a join under the first node\'s name refused', 'name of its own' in str(e), str(e))

# forgotten: its maintenance and upgrade rows go too
store.set_meta('maint:nodeq', '{"on": true}'); store.set_meta('upgrade:node:nodeq', '{}')
store.set_meta('node:nodeq', json.dumps({'at': time.time() - 99999, 'version': '1.0.250'}))
otp.ha_forget(store, 'nodeq')
ok('forgotten: maint and upgrade rows gone', store.get_meta('maint:nodeq') is None and
   store.get_meta('upgrade:node:nodeq') is None)

# high security not switched on with a change on trial
store.set_meta('fw:trial', json.dumps({'until': time.time() + 300, 'by': 't', 'at': time.time()}))
try:
    otp.hisec_guard_settings(store, {'high_security': 1})
    ok('high security refused while a change is on trial', False)
except otp.BadSetting as e:
    ok('high security refused while a change is on trial', 'on trial' in str(e), str(e))
store.db.run("DELETE FROM meta WHERE k = 'fw:trial'")

# the NTP asks: a value new, not a time set against this clock
ok('NTP asks read as new values', "sync_raw != NTP_WORK.get('sync_raw', None)" in SRC and
   "read_raw != NTP_WORK.get('read_raw', None)" in SRC)
ok('an OS update stopped: a node draining comes back, one updating finishes',
   "plan.get('state') == 'cancelled' and me in (plan.get('order') or [])" in SRC and
   "said='the update was stopped before it began here'" in SRC)
ok('a restart of an update that failed later ends the update', 'def _osup_restart_lost' in SRC and
   "power_id=str((pw or {}).get('id') or '')" in SRC)
ok('a maintenance set by hand kept through an update', "maint=not had" in SRC)
ok('--selinux permissive refused under high security', "if hs or _hs_on():" in SRC)
ok('--ha-renamed refuses a live node', "is another node, answering now" in SRC)
ok('the joining window ends once the node has joined', 'ha_joining_done()\n                joining = []' in SRC)
ok('scheduled work that did not start is alerted', "'on a schedule did not start'" in SRC)
INST = open(V + '/install.sh').read()
ok('install.sh puts acme.php and metrics.php in', '"$SOURCE_DIR/web/acme.php"' in INST and
   '"$SOURCE_DIR/web/metrics.php"' in INST)
ok('uninstall: keyboard-interactive off again with passwords off', 'KbdInteractiveAuthentication no' in HELPER)
ok('the ACME location: the file\'s own socket, no multipart', "sock.group(1)" in HELPER and
   HELPER.split('ACME_LOCATION = ', 1)[1][:900].count('multipart') == 1)

# ---- round 3 ---------------------------------------------------------------------------------------------
JS = open(V + '/web/assets/admin.js').read(); CORE = open(V + '/web/assets/core.js').read()
I18NJS = open(V + '/web/assets/i18n.js').read()
ok('uninstall keeps keyboard-interactive where a key and then the code is asked',
   "AuthenticationMethods\\b.*keyboard-interactive" in HELPER)
ok('no 5 min lock wait at the start; missing columns tried again', "lock_timeout = '5min'" not in SRC and
   'def add_columns_again' in SRC and "self.store.db.add_columns_again()" in SRC)
ok('a quick store writes its mark', "if quick or not getattr(self.db, 'columns_missing', False):" in SRC)
ok('the settings read through the guard at the start and on the command line',
   SRC.count('load_config(saved=dbguard_settings(store.settings_saved(), store))') >= 6)
ok('the guard\'s counts of sign-ins over pruned', ("k.startswith('sig:x:') and k.rsplit(':', 1)[0] not in pre" in SRC or
   "k.startswith(('sig:x:', 'sig:xm:')) and\n                          k.rsplit(':', 1)[0] not in pre" in SRC))
ok('more work left by a restart taken away', "'otp-verify-'" in SRC and "'otp-sql-'" in SRC)
ok('SIGHUP: config.json taken as read only once read', 'self.reload_all(\'SIGHUP\')\n            # Only once read' in SRC)
ok('the code sent to the old token tied to it', "'mark': portal_token_mark(tok)" in SRC and SRC.count('portal_old_same(h, s, old)') == 3)
ok('codes sent on the enrolment pages given back when nothing went', SRC.count('portal_sends_back(h.store') >= 5)
ok('an upgrade not beside an update, a network change or a restart', "busy = cluster_busy(store, skip=('upgrade',))" in SRC)
ok('a maintenance an upgrade left is no hand maintenance', "startswith('upgrade to ')" in SRC)
ok('a failed restart after an update said as an event', 'the restart after the update of the system failed on' in SRC)
ok('a live node forgotten keeps its maintenance', 'if not alive:\n        store.drop_meta(\'maint:\'' in SRC)
store.set_meta('node:nodel', json.dumps({'at': time.time(), 'version': otp.__version__, 'address': '127.0.0.8'}))
store.set_meta('maint:nodel', '{"on": true}')
otp.ha_forget(store, 'nodel')
ok('...as it does', store.get_meta('maint:nodel') is not None)
ok('drafts of SSH and the split taken again while nothing waits', '!SD.draft || !PENDING.sshd' in JS and
   '!SPLITC.draft || !PENDING.split' in JS)
ok('the password policy draft said unsaved, taken again when untouched', 'PWP_BASE' in JS and 'Changed here and not saved yet.' in JS)
ok('Clear puts each time picker to its own default', 'tp._set(tp._start ||' in JS and 'wrap._start' in CORE)
ok('the lockouts timer not stopped by a hidden tab', "if (document.hidden) return;" in JS)
ok('the SELinux report waited for by the nodes\' own clocks', "Number(reps[n].at) > (before[n] || 0)" in JS)
ok('a slot with no space is one word (i18n)', "/\\S\\s+\\S/.test(m[i] || '')" in I18NJS)
ok('the status counts sign-ins only', "packet = 'Access-Request' AND result IN ('reject', 'drop')" in SRC or
   ("packet = 'Access-Request' AND result IN \"" in SRC and "\"('reject', 'drop')" in SRC))   # wrapped in 1.0.265

# ---- Czech -----------------------------------------------------------------------------------------------
cs = V + '/web/lang/cs.json'
if os.path.exists(cs):
    pack = json.load(open(cs))
    srcs = {v['source'] for v in pack['strings'].values()}
    pats = {v['source'] for v in pack['patterns'].values()}
    spec = importlib.util.spec_from_file_location('cs_262', '/home/claude/i18n/cs_262.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    ok('every new text in Czech', all(k in srcs for k in mod.S262), [k[:40] for k in mod.S262 if k not in srcs])
    ok('every new pattern in Czech', all(k in pats for k in mod.P262), [k[:40] for k in mod.P262 if k not in pats])

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
