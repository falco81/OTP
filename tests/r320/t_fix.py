"""t_fix.py - 1.0.320: root's keys never from the pages; high security looks at isemon's targets and
takes root with a code; config.json put back as on disk; a full name in the certificate; a network on
trial holds an update back; every SSH port for SELinux; the report given back and tried in 30 min;
both nodes of one database on the alerts' panes. The built otp.py loaded as a module over SQLite.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.320'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r320_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx320', 'api_port': 29950}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 root's keys: refused whoever is named
asked = []
m.sshkeys_ask = lambda *a, **k: asked.append((a, k))
m.rootkey_put = lambda *a, **k: asked.append(('put', a))
m.rootkey_again = lambda *a, **k: asked.append(('again', a))


class H:
    def __init__(self, body):
        self.b = body
        self.store = st

    def me(self, role=None):
        return {'name': 'admin', 'role': 'fulladmin'}

    def body(self):
        return self.b


for act in ('rk_make', 'rk_given', 'rk_again'):
    for user in ('root', 'alice', ''):
        try:
            m._sshkeys_do(H({'action': act, 'user': user, 'key': 'ssh-ed25519 AAAA x'}))
            ok('sshkeys: %s for %r refused' % (act, user), False)
        except m.ApiError as e:
            ok('sshkeys: %s for %r refused' % (act, user), e.status == 403, e.status)
ok('sshkeys: nothing asked', not asked, asked)
try:
    m._sshkeys_do(H({'action': 'add', 'user': 'root', 'line': 'x'}))
    ok('sshkeys: add for root refused', False)
except m.ApiError as e:
    ok('sshkeys: add for root refused', e.status == 403)
try:
    m._sshkeys_do(H({'action': 'refresh', 'user': 'alice'}))
    ok('sshkeys: a normal user\'s list asked', bool(asked), asked)
except Exception as e:                                  # noqa: BLE001
    ok('sshkeys: a normal user\'s list asked', False, repr(e))

# ==== 2 high security: isemon's targets and root with a code
src = inspect.getsource(m.hisec_guard_settings)
ok('hisec: isemon and its targets wake the check', "'isemon', 'isemon_targets'" in src)
m.CONFIG['high_security'] = True
try:
    m.hisec_sshd({'manage': 1, 'permit_root': 'yes', 'radius': 1, 'radius_fallback': 0})
    ok('hisec: root with key and code taken', True)
except ValueError as e:
    ok('hisec: root with key and code taken', False, e)
for c in ({'manage': 1, 'permit_root': 'yes'}, {'manage': 1, 'permit_root': 'yes', 'radius': 1, 'radius_fallback': 1}):
    try:
        m.hisec_sshd(c); ok('hisec: root with a password refused %r' % c, False)
    except ValueError:
        ok('hisec: root with a password refused %r' % c, True)
m.CONFIG['high_security'] = False

# ==== 3 SELinux: every SSH port
st.set_meta('host:sshd:now:fx320', json.dumps({'values': {'port': '22 2222,2200'}}))
w = m.selinux_want(st)
got = sorted(p['port'] for p in w['ports'] if p['type'] == 'ssh_port_t') if isinstance(w, dict) else []
ok('selinux: 2200 and 2222 labelled', got == [2200, 2222], w)

# ==== 4 config.json as on disk
m.write_file_settings({'db_host': '192.0.2.77'})
d = m._net_file_differs({'file': {'db_host': '192.0.2.5'}})
ok('net: config.json differs from what is put back', d == {'db_host': '192.0.2.5'}, d)
m.write_file_settings({'db_host': '192.0.2.5'})
ok('net: nothing when the same', m._net_file_differs({'file': {'db_host': '192.0.2.5'}}) == {})
srcn = inspect.getsource(m.net_undo_put_back)
ok('net: put back reads the disk', '_net_file_differs(undo)' in srcn)

# ==== 5 the certificate's names after a short name became a full one
srcc = inspect.getsource(m.net_cert_again)
ok('net: short names only of full ones, the full name kept',
   "if '.' in w['old_hostname']" in srcc and "new_names.append(w['hostname'])" in srcc)

# ==== 6 a network on trial holds an update back
m.host_nodes = lambda store: ['fx320', 'n2']
st.set_meta('net:job:n2', json.dumps({'state': 'trial', 'trial_until': time.time() + 300, 'at': time.time()}))
b = m.cluster_busy(st, skip=('osup', 'upgrade', 'power'))
ok('busy: a trial holds an update', 'on trial' in b, b)
ok('busy: not for a network of its own', m.cluster_busy(st, skip=('power', 'trial')) == '')
st.set_meta('net:job:n2', json.dumps({'state': 'kept', 'at': time.time()}))
ok('busy: kept - free', m.cluster_busy(st, skip=('osup', 'upgrade', 'power')) == '')

# ==== 7 the report: no sender - given back as not made
m._alerts_to = lambda k: ['a@example.cz']
m.report_build = lambda r, s, u, l: ('s', '<p>p</p>', 't')


def nosender(*a, **k):
    raise m.MailError('no sender address is set')


m._al_msg = nosender
try:
    m.report_send(st, 1, 2); ok('report: no sender is not a MailError', False)
except ValueError:
    ok('report: no sender is not a MailError', True)
except m.MailError:
    ok('report: no sender is not a MailError', False)
srct = inspect.getsource(m.alerts_tick)
ok('report: tried in 30 min after any failure', srct.count("ALERT_WORK['report_fail'] = time.monotonic()") >= 2)

# ==== 8 both nodes of one database on the panes
m.in_cluster = lambda store=None: True
m.ha_nodes = lambda store: [{'name': 'fx320'}, {'name': 'n2'}]
v = m.alerts_view(st)
ok('alerts: both nodes', set(v.get('health') or {}) == {'fx320', 'n2'}, list(v.get('health') or {}))
ok('siem / isemon: in_cluster', 'if in_cluster(h.store)' in inspect.getsource(m._siem_view) and
   'if in_cluster(h.store)' in inspect.getsource(m._isemon))

print('ALL %d / %d' % (sum(R), len(R)))
