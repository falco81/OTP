# t_round14.py VERSION - round B of the bug hunt (1.0.235), in-process on SQLite and on the root helper with
# SELinux and sshd faked: the trial of sshd put back after a restart, its timer armed before the change; a port
# of another service refused for SSH and never taken from it in SELinux; a time zone or an interface that is an
# option refused; the VIP address kept on the addresses last known; "quiet" per node; a report not sent on its
# day sent the next; a database carried and changed since refused; an unlocked backup refused; a redirect
# without the credentials; a node rebuilt from the other not signing its rows.
import os, sys, json, time, tempfile, importlib.util, gzip, io, tarfile, urllib.request
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.235'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r14-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run',
                  OTP_VIP_NO_SERVICES='1', OTP_ETC=D + '/etc')
for x in ('log', 'run', 'web', 'etc/ssh/sshd_config.d', 'etc/pam.d'):
    os.makedirs(os.path.join(D, x), exist_ok=True)
json.dump({'db_engine': 'sqlite', 'node_name': 'r14'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:300]) if more and not cond else ''), flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
db.make_tables()
st = otp.Storage(db)
otp.sealing_key(make=True)
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# ---- the root helper: sshd's trial, ports, names ----
st_file = W.SSHD_STATE
W._put_file(st_file, json.dumps({'dropin': None, 'banner': None, 'issue': None, 'motd': None,
                                  'until': time.time() - 600, 'unit': 'otp-sshd-back-x', 'hash': 'h'}), 0o600)
backs = []
real_back = W.sshd_put_back
W.sshd_put_back = lambda why='': backs.append(why)
W.sshd_overdue()
ok('a trial of sshd whose time is up (its timer lost to a restart): put back at the next run of the helper', backs and 'restart' in backs[0], backs)
W._put_file(st_file, json.dumps({'until': time.time() + 600}), 0o600)
backs.clear(); W.sshd_overdue()
ok('...one still within its time: left as it is', not backs)
W.sshd_put_back = real_back
for port, want in ((443, 'web server'), (1812, 'RADIUS'), (5432, 'PostgreSQL'), (2222, None)):
    try:
        W.sshd_checked({'port': port}) if hasattr(W, 'sshd_checked') else None
        e = ''
    except W.Refused as x:
        e = str(x)
    ok('SSH on port %d: %s' % (port, 'refused - %s' % want if want else 'taken'), (want in e) if want else not e or 'port' not in e, e)
ok('a time zone that is an option (-Hhost): refused', not W.TZ_RE.match('-Hhost') and W.TZ_RE.match('Europe/Prague'))
ok('an interface called .. or -x: refused', not W.IFACE_RE.match('..') and not W.IFACE_RE.match('-x') and W.IFACE_RE.match('ens192'))
# semanage never takes a port from another service
SE = os.path.join(D, 'sefake'); os.makedirs(SE)
os.environ.update(SEFAKE=SE, PATH=os.path.dirname(os.path.abspath(__file__)) + '/../selinux/fakebin:' + os.environ['PATH'])
open(SE + '/mode', 'w').write('Permissive\n')
open(SE + '/ports', 'w').write('%-30s %-8s %s\n' % ('http_port_t', 'tcp', '8443'))
calls_before = ''
try:
    W.se_apply([], [{'port': 8443, 'proto': 'tcp', 'type': 'ssh_port_t', 'why': 'test'}], [])
    e = ''
except W.Refused as x:
    e = str(x)
fake_ports = open(SE + '/ports').read()
ok('a port the policy gives another service: refused, not relabelled (semanage -m)', "another service" in e and 'ssh_port_t' not in fake_ports, (e, fake_ports))

# ---- the VIP address on the addresses last known ----
otp.CONFIG.update(ha_mode='replicated', ha_address='10.99.0.1', ha_peer='10.99.0.2')
st.set_meta('web:vip', json.dumps({'on': True, 'address': '10.99.0.200/24'}))
d1 = otp.web_desired(st)
ok('the VIP address with both addresses known: on', d1['vip'].get('on') and d1['vip']['peer'] == '10.99.0.2', d1['vip'])
otp.CONFIG['ha_peer'] = 'no-such-host.invalid'
d2 = otp.web_desired(st)
ok('...the other node\'s name not answered now: still on, on the address last known - keepalived not stopped',
   d2['vip'].get('on') and d2['vip']['peer'] == '10.99.0.2', d2['vip'])
otp.CONFIG.update(ha_mode='', ha_peer='', ha_address='')

# ---- quiet per node; the report on a later day ----
st.set_meta('alerts:quiet:other', json.dumps({'why': 'other in maintenance', 'until': time.time() + 300}))
ok('"quiet" written by another node under its own name: seen here', 'other in maintenance' in otp.alerts_quiet(st, ['r14']))
ok('...and nothing of the one shared row written by this node', st.db.value("SELECT v FROM meta WHERE k = 'alerts:quiet'") is None)
otp.CONFIG.update(report_every='weekly', report_day=1, report_at='07:30')
import datetime
tue = datetime.datetime(2026, 11, 3, 9, 0).timestamp()     # a Tuesday
mon_early = datetime.datetime(2026, 11, 2, 7, 0).timestamp()
ok('the weekly report missed on Monday: due on Tuesday (sent once a week all the same)', otp.report_due(tue))
ok('...not before its hour on its own day', not otp.report_due(mon_early))

# ---- a database carried, then changed here: refused ----
far = otp.Db('sqlite', path=os.path.join(D, 'far.db')); far.make_tables()
ok('nothing changed: the two alike', otp.db_fingerprint_diff(db, db) == [])
st.add_account('nova', 'readonly', 'Nova-Heslo-235!', must_change=0)
ok('an account made here, not in the copy: said (%s)' % otp.db_fingerprint_diff(db, far), 'the accounts' in otp.db_fingerprint_diff(db, far))

# ---- an unlocked backup ----
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as tf:
    data = b'{}'
    ti = tarfile.TarInfo('x/manifest.json'); ti.size = len(data); tf.addfile(ti, io.BytesIO(data))
p = os.path.join(D, 'plain.tar.gz'); open(p, 'wb').write(buf.getvalue())
try:
    otp.rb_open(p, '', tempfile.mkdtemp(dir=D)); e = ''
except otp.RbError as x:
    e = str(x)
ok('an unlocked backup, no password in play: refused - otp\'s are always locked', 'not locked' in e, e)

# ---- a redirect without the credentials ----
h = otp._NoCredsRedirect()
req = urllib.request.Request('https://gw.example/send', headers={'Authorization': 'Bearer secret'})
new = h.redirect_request(req, None, 302, 'Found', {}, 'https://evil.example/x')
ok('a redirect to another host: the Bearer token left behind', new is not None and not any(k.lower() == 'authorization' for k in new.headers), dict(new.headers) if new else None)
new = h.redirect_request(req, None, 302, 'Found', {}, 'https://gw.example/other')
ok('...to the same host: kept', new is not None and any(k.lower() == 'authorization' for k in new.headers))

# ---- rebuilt from the other node: nothing signed here ----
otp.CONFIG['db_guard'] = 1
otp.DBGUARD['seen'] = None
st.set_meta('web:vip', json.dumps({'on': False}))
n_sig = st.db.value("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:%'")
st.db.run("INSERT INTO accounts (name, role, pw, source, disabled) VALUES ('forged', 'fulladmin', 'x', 'local', 0)")
otp.dbguard_forget_seen('test')
ok('after a rebuild: what was seen forgotten, nothing signed - a row written in the other database stays refused',
   st.db.value("SELECT COUNT(*) FROM meta WHERE k LIKE 'sig:%'") == n_sig and st.account('forged', checked=True) is None)
otp.CONFIG['db_guard'] = 0
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
