# t_selinux.py VERSION - SELinux (1.0.233). The root helper's steps with SELinux faked (fakebin/:
# getenforce, setenforce, getsebool, setsebool, semodule, semanage, ausearch, restorecon, grubby,
# their state in a folder): absent, disabled, made ready (permissive at the next start), enforcing
# only with nothing missing and nothing refused, permissive again. Then end to end: the daemon,
# its API and the helper - a step asked on the pages done, the security check, a request written
# straight into the database with the guard on not done.
# Usage (as root): python3 t_selinux.py VERSION
import os, sys, json, time, shutil, subprocess, tempfile, threading, atexit, urllib.request, importlib.util

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.233'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
FAKEBIN = HERE + '/fakebin'
TOP = tempfile.mkdtemp(prefix='otp-se-')
atexit.register(lambda: shutil.rmtree(TOP, True))
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:400] if more and not c else ''), flush=True)


FAKE = TOP + '/se'; os.makedirs(FAKE)
CONF = TOP + '/selinux-config'
LABELS = TOP + '/labels.json'
CMDLINE = TOP + '/cmdline'


def fake(mode, labels=None, avc='', cmdline='ro quiet'):
    open(FAKE + '/mode', 'w').write(mode + '\n')
    open(FAKE + '/avc', 'w').write(avc)
    open(CMDLINE, 'w').write(cmdline + '\n')
    json.dump(labels or {}, open(LABELS, 'w'))


open(CONF, 'w').write('# This file controls the state of SELinux on the system.\nSELINUX=disabled\n'
                      '# SELINUXTYPE= can take one of these three values:\nSELINUXTYPE=targeted\n')
ENV = {'SEFAKE': FAKE, 'PATH': FAKEBIN + ':' + os.environ['PATH'], 'OTP_SELINUX_CONFIG': CONF,
       'OTP_SELINUX_RELABEL': TOP + '/.autorelabel', 'OTP_SELINUX_CMDLINE': CMDLINE,
       'OTP_SELINUX_CIL': V + '/deploy/otp_server.cil', 'OTP_SELINUX_LABELS': LABELS,
       'OTP_VIP_NO_SERVICES': '1'}
os.environ.update(ENV)
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
WANT = {'booleans': [{'name': 'httpd_can_network_connect', 'why': 'the pages ask the daemon'},
                     {'name': 'authlogin_radius', 'why': 'SSH asks otp for the code'}],
        'ports': [{'port': 18129, 'proto': 'udp', 'type': 'radius_port_t', 'why': 'the SSH gate'},
                  {'port': 2222, 'proto': 'tcp', 'type': 'ssh_port_t', 'why': 'sshd'}]}
GOOD = {'/run/otp': 'httpd_var_run_t', '/run/otp/api-token': 'httpd_var_run_t',
        '/var/www/otp': 'httpd_sys_content_t',
        '/usr/libexec/keepalived/otp-vip-check': 'keepalived_unconfined_script_exec_t'}
BAD = dict(GOOD, **{'/run/otp': 'var_run_t', '/run/otp/api-token': 'var_run_t'})


def do(what, **extra):
    try:
        return W.se_do(dict(WANT, do=what, **extra)), ''
    except W.Refused as e:
        return None, str(e)


# ---- no SELinux on the machine at all ----
os.environ['PATH'] = '/usr/bin:/bin'
os.makedirs(TOP + '/nobin', exist_ok=True)
for b in ('python3',):
    pass
saved = os.environ['PATH']; os.environ['PATH'] = TOP + '/nobin'
c, _ = do('check')
ok('no getenforce: "absent", nothing to do, nothing missing', c and c['mode'] == 'absent' and not c['problems'], c)
_, e = do('prepare')
ok('...and "prepare" refused: there is no SELinux', 'no SELinux' in e, e)
os.environ['PATH'] = ENV['PATH']

# ---- disabled, as the user's machines are ----
fake('Disabled', cmdline='ro quiet selinux=0')
c, _ = do('check')
ok('disabled: nothing missing (as until now - the security check says nothing)', c['mode'] == 'Disabled' and c['problems'] == [], c)
ok('...the config read: disabled, targeted', c['config'] == 'disabled' and c['policy'] == 'targeted', c)
ok('...selinux=0 on the kernel\'s command line seen', c['cmdline_off'] is True)
_, e = do('enforce')
ok('disabled -> enforcing refused: from permissive only', 'permissive only' in e, e)
_, e = do('permissive')
ok('disabled -> "permissive" refused: "prepare" does it', 'prepare' in e, e)
c, e = do('prepare')
ok('prepare from disabled: done', c is not None, e)
conf = open(CONF).read()
ok('...SELINUX=permissive in the config, the rest of the file as it was',
   'SELINUX=permissive\n' in conf and 'SELINUXTYPE=targeted' in conf and conf.startswith('# This file controls'), conf)
ok('...the files labelled at the next start (/.autorelabel)', os.path.exists(TOP + '/.autorelabel'))
ok('...selinux=0 taken off the kernel\'s command line (grubby)', 'selinux=0' not in open(CMDLINE).read())
ok('...says: restart the machine', any('restart the machine' in x for x in c['said']), c['said'])
ok('...nothing switched now: still disabled', open(FAKE + '/mode').read().strip() == 'Disabled')

# ---- the machine restarted: permissive, otp's files still with the old labels ----
os.remove(TOP + '/.autorelabel')
fake('Permissive', labels=BAD)
c, _ = do('check')
ok('permissive, not ready: the token labelled var_run_t', any('/run/otp/api-token is labelled var_run_t' in p for p in c['problems']), c['problems'])
ok('...booleans off said', any('httpd_can_network_connect is off' in p for p in c['problems']))
ok('...ports not labelled said', any('port 18129/udp is not labelled radius_port_t' in p for p in c['problems']))
ok('...not ready', c['ready'] is False)
_, e = do('enforce')
ok('enforcing refused while a label is wrong ("not yet")', e.startswith('not yet') and 'api-token' in e, e)
calls = open(FAKE + '/calls').read()
ok('...but the booleans, the ports and the module were put in on the way',
   'setsebool -P httpd_can_network_connect on' in calls and 'semanage port -a -t radius_port_t -p udp 18129' in calls
   and 'semodule -i' in calls, calls[-600:])
c, _ = do('check')
ok('...booleans now on, ports labelled, module in', all(b['on'] for b in c['booleans']) and all(p['labelled'] for p in c['ports'])
   and c['module'] is True, c)
AVC = ('type=AVC msg=audit(11/03/2026 02:00:00.123:456) : avc:  denied  { read } for  pid=1234 comm=php-fpm '
       'name=api-token dev="tmpfs" ino=55 scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=system_u:object_r:var_run_t:s0 tclass=file permissive=1\n') * 3 + \
      ('type=AVC msg=audit(11/03/2026 02:00:01.000:457) : avc:  denied  { write } for  pid=99 comm=cupsd '
       'name=x scontext=system_u:system_r:cupsd_t:s0 tcontext=system_u:object_r:etc_t:s0 tclass=file permissive=1\n')
fake('Permissive', labels=GOOD, avc=AVC)
c, _ = do('check')
ok('labels right; what SELinux refused read: 3 for the pages, cupsd\'s not counted',
   c['denials']['total'] == 3 and c['denials']['groups'][0]['source'] == 'httpd_t' and c['denials']['groups'][0]['count'] == 3, c['denials'])
ok('...it says what: php-fpm api-token', 'php-fpm api-token' in c['denials']['groups'][0]['what'], c['denials'])
_, e = do('enforce')
ok('enforcing refused while anything was refused since the start', 'refused 3' in e, e)
fake('Permissive', labels=GOOD, avc='')
c, _ = do('check')
ok('nothing refused, nothing missing: ready for enforcing', c['ready'] is True and c['problems'] == [], c['problems'])
c, e = do('enforce')
ok('enforcing: done', c is not None and c['mode'] == 'Enforcing', e)
ok('...and kept after a restart: SELINUX=enforcing', 'SELINUX=enforcing\n' in open(CONF).read())
_, e = do('prepare')
ok('"prepare" while enforcing refused', 'enforcing already' in e, e)
c, e = do('permissive')
ok('back to permissive: now and in the config', c and c['mode'] == 'Permissive' and 'SELINUX=permissive\n' in open(CONF).read(), e)

# ---- what is asked is checked ----
for bad, why in ((dict(WANT, booleans=[{'name': 'allow_execmem'}]), 'a boolean otp does not set'),
                 (dict(WANT, ports=[{'port': 22, 'proto': 'tcp', 'type': 'unconfined_t'}]), 'port type'),
                 (dict(WANT, ports=[{'port': 70000, 'proto': 'tcp', 'type': 'ssh_port_t'}]), '1 to 65535')):
    try:
        W.se_do(dict(bad, do='enforce')); e = ''
    except W.Refused as x:
        e = str(x)
    ok('refused: %s' % why, why in e, e)

# ---- otp_web.py --selinux-check, as `otp --selinux-check` runs it ----
fake('Permissive', labels=GOOD)
g = subprocess.run(['/usr/bin/python3', '-I', V + '/deploy/otp_web.py', '--selinux-check', '--want-stdin'],
                   input=json.dumps(WANT), capture_output=True, text=True, env=dict(os.environ))
ok('--selinux-check: a report for a person, exit 0 when nothing is missing',
   g.returncode == 0 and 'SELinux: Permissive' in g.stdout and 'ready for enforcing' in g.stdout, g.stdout + g.stderr)
fake('Permissive', labels=BAD)
g = subprocess.run(['/usr/bin/python3', '-I', V + '/deploy/otp_web.py', '--selinux-check', '--want-stdin', '--json'],
                   input=json.dumps(WANT), capture_output=True, text=True, env=dict(os.environ))
try:
    j = json.loads(g.stdout)
except ValueError:
    j = {}
ok('--selinux-check --json: exit 1 with what is missing', g.returncode == 1 and j.get('problems'), g.stdout[-300:] + g.stderr)

# ---- end to end: the daemon, the API, the helper ----
D = TOP + '/node'
os.makedirs(D + '/run'); os.makedirs(D + '/web')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 32910,
           'radius_acct_port': 32911, 'api_port': 29931, 'node_name': 'se1'}, open(D + '/config.json', 'w'))
NENV = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
            OTP_STAY_ROOT='1')
os.environ.update({k: NENV[k] for k in ('OTP_STATE', 'OTP_CONFIG', 'OTP_LOGDIR', 'OTP_RUN', 'OTP_STAY_ROOT')})
sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-233!', must_change=0)
st.add_account('reader', 'readonly', 'Reader-Pass-233!', must_change=0)
STOP = threading.Event()


def helper_loop():
    while not STOP.is_set():
        if os.path.exists(D + '/web/selinux.ask'):
            subprocess.run(['/usr/bin/python3', '-I', V + '/deploy/otp_web.py'], env=NENV,
                           stdout=subprocess.DEVNULL, stderr=open(D + '/helper.err', 'a'))
        time.sleep(0.3)


fake('Disabled')
open(CONF, 'w').write('SELINUX=disabled\nSELINUXTYPE=targeted\n')
threading.Thread(target=helper_loop, daemon=True).start()
proc = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=NENV,
                        stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (STOP.set(), proc.terminate(), proc.wait(10)))
time.sleep(7)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:29931' + path, data=json.dumps(body).encode() if body is not None else None,
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


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-233!'}); S = a.get('token')
_, a = call('/api/auth/login', {'name': 'reader', 'password': 'Reader-Pass-233!'}); SR = a.get('token')


def node():
    c, v = call('/api/selinux', None, S)
    return (v.get('nodes') or [{}])[0] if c == 200 else {}


n = until(lambda: node() if node().get('state', {}).get('mode') else None)
ok('the daemon looked by itself at start: disabled, nothing missing', n and n['state']['mode'] == 'Disabled' and n['state']['problems'] == [], n)
c, _ = call('/api/selinux', None, SR)
ok('a read-only administrator may not see it (%s)' % c, c == 403)
c, _ = call('/api/selinux', {'action': 'enforce', 'node': 'se1'}, SR)
ok('...nor ask a step (%s)' % c, c == 403)
c, x = call('/api/selinux', {'action': 'reboot', 'node': 'se1'}, S)
ok('an unknown step refused (%s)' % c, c == 400, x)
c, x = call('/api/selinux', {'action': 'enforce', 'node': 'nosuch'}, S)
ok('an unknown node refused (%s)' % c, c == 400, x)
c, x = call('/api/selinux', {'action': 'enforce', 'node': 'se1'}, S)
n = until(lambda: node() if node().get('action') == 'enforce' and not node().get('pending') else None)
ok('enforce while disabled: the helper\'s word comes back on the page', n and 'permissive only' in n['error'], n)
c, x = call('/api/selinux', {'action': 'prepare', 'node': 'se1'}, S)
ok('prepare asked (%s)' % c, c == 200, x)
n = until(lambda: node() if node().get('action') == 'prepare' and not node().get('pending') else None)
ok('...done: config permissive, the restart said', n and n['state'].get('config') == 'permissive' and any('restart the machine' in s for s in n['said']), n)
ev = [e['words'] for e in st.db.rows("SELECT words FROM events WHERE kind = 'settings'")]
ok('...in Events: who asked and what was done', any('local asked SELinux on se1: made ready, permissive' in w for w in ev)
   and any(w.startswith('SELinux on se1:') for w in ev), ev[-4:])
# the machine restarted: permissive, a label wrong - the security check says so
fake('Permissive', labels=BAD)
call('/api/selinux', {'action': 'check', 'node': 'se1'}, S)
n = until(lambda: node() if node().get('state', {}).get('mode') == 'Permissive' else None)
c, h = call('/api/hisec', None, S)
items = [w.get('what', '') for w in (h.get('warn') or [])] if isinstance(h, dict) else []
ok('the security check: what SELinux lacks on se1', any(w.startswith('SELinux on se1:') and 'api-token' in w for w in items), items)
fake('Permissive', labels=GOOD)
call('/api/selinux', {'action': 'enforce', 'node': 'se1'}, S)
n = until(lambda: node() if node().get('action') == 'enforce' and node().get('state', {}).get('mode') == 'Enforcing' else None)
ok('enforce from the page, nothing missing: enforcing', bool(n), node())
c, h = call('/api/hisec', None, S)
items = [w.get('what', '') for w in (h.get('warn') or [])] if isinstance(h, dict) else []
ok('...and the security check has nothing of SELinux to say', not any(w.startswith('SELinux on') for w in items), items)
# the guard: a step written straight into the database is not done
r = subprocess.run([sys.executable, V + '/otp.py', '--set', 'db_guard=1'], env=NENV, capture_output=True, text=True, timeout=60)
time.sleep(8)
calls_before = open(FAKE + '/calls').read().count('setenforce')
db = otp.open_db()
db.run('INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT (k) DO UPDATE SET v = excluded.v',
       ('host:selinux:want:se1', json.dumps({'id': 'forged1', 'do': 'permissive', 'by': 'x', 'at': time.time()})))
time.sleep(10)
ok('with the guard on, "permissive" written straight into the database: not done',
   open(FAKE + '/calls').read().count('setenforce') == calls_before and open(FAKE + '/mode').read().strip() == 'Enforcing')
call('/api/selinux', {'action': 'permissive', 'node': 'se1'}, S)
ok('...asked on the page: done', until(lambda: open(FAKE + '/mode').read().strip() == 'Permissive', 30))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
