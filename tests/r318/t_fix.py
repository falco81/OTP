"""t_fix.py - 1.0.318: a remote backup cut off on the way leaves nothing and keeps the good copy; names
past UTF-8 read as they come; the other node's old address asked again; a firewall trial claimed by its
end; the lockout limit as in force; the balancer's settings reach nginx alone; a VIP interface as root
takes it. The built otp.py loaded as a module over SQLite, no daemon.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.318'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r318_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx318', 'api_port': 29948}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 SMB: the put alone first; a failed one takes its half file away and renames nothing
smb = object.__new__(m.RbSmb)
smb.t = {'share': 's', 'host': 'h'}; smb.dir = 'otp'
calls = []
FAIL = [True]


def run(cmds, ignore=(), timeout=3600):
    calls.append(list(cmds))
    if FAIL[0] and any(c.startswith('put ') for c in cmds):
        raise m.RbError('smbclient: NT_STATUS_DISK_FULL')
    return ''


smb._run = run
try:
    smb.put('/tmp/x', 'otp-1.tar')
    ok('smb: a failed put raises', False)
except m.RbError:
    ok('smb: a failed put raises', True)
flat = [c for cc in calls for c in cc]
ok('smb: the put was alone', any(cc[1:] == ['put "/tmp/x" ".otp-1.tar.part"'] for cc in calls), calls)
ok('smb: the half file deleted', 'del ".otp-1.tar.part"' in flat, calls)
ok('smb: the old copy kept, nothing renamed', 'del "otp-1.tar"' not in flat and
   not any(c.startswith('rename') for c in flat), calls)
calls[:] = []; FAIL[0] = False
smb.put('/tmp/x', 'otp-1.tar')
flat = [c for cc in calls for c in cc]
ok('smb: a good put replaces and renames', len(calls) == 2 and 'del "otp-1.tar"' in flat and
   'rename ".otp-1.tar.part" "otp-1.tar"' in flat, calls)

# ==== 2 FTP: a broken upload deletes its half file
class F:
    def __init__(self):
        self.deleted = []
        self.renamed = []

    def storbinary(self, cmd, f, blocksize=0):
        raise OSError('connection reset')

    def delete(self, n):
        self.deleted.append(n)

    def rename(self, a, b):
        self.renamed.append((a, b))


ftp = object.__new__(m.RbFtp); ftp.ftp = F()
src = TOP + '/b.tar'; open(src, 'wb').write(b'x' * 10)
try:
    ftp.put(src, 'b.tar'); ok('ftp: raises', False)
except OSError:
    ok('ftp: raises', True)
ok('ftp: half file deleted, nothing renamed', ftp.ftp.deleted == ['.b.tar.part'] and not ftp.ftp.renamed,
   (ftp.ftp.deleted, ftp.ftp.renamed))

# ==== 3 SFTP / SCP: the half file away
for kind in ('sftp', 'scp'):
    s = object.__new__(m.RbSsh)
    s.t = {'kind': kind, 'port': 22}; s.dir = '/b'; s.opts = []; s.rdest = 'u@h'; s.dest = 'u@h'; s.d = TOP
    seen = []

    def sftp(cmds, timeout=3600, seen=seen):
        seen.append(('sftp', list(cmds)))
        if any(c.startswith('put ') for c in cmds):
            raise m.RbError('sftp: no space')
        return ''

    def runx(args, what, stdin=None, timeout=3600, seen=seen):
        seen.append((what, list(args)))
        if what == 'scp':
            raise m.RbError('scp: no space')
        return ''

    def ssh(cmd, seen=seen):
        seen.append(('ssh', cmd))
        return ''
    s._sftp = sftp; s._run = runx; s._ssh = ssh
    try:
        s.put(src, 'b.tar'); ok(kind + ': raises', False)
    except m.RbError:
        ok(kind + ': raises', True)
    txt = json.dumps(seen)
    ok(kind + ': half file removed', ('-rm \\".b.tar.part\\"' in txt) if kind == 'sftp' else
       ('rm -f -- /b/.b.tar.part' in txt), seen)
    if kind == 'scp':                                  # sftp -b stops at the put that failed
        ok(kind + ': never moved to the name', 'mv -f' not in txt, seen)

# ==== 4 SSH / SMB output past UTF-8 read as it comes
s = object.__new__(m.RbSsh); s.env = dict(os.environ)
try:
    out = s._run(['sh', '-c', 'printf "a\\377b\\n"'], 'ssh')
    ok('ssh: bytes past UTF-8 read', 'a�b' in out, repr(out))
except Exception as e:                                  # noqa: BLE001
    ok('ssh: bytes past UTF-8 read', False, e)
smb2 = object.__new__(m.RbSmb); smb2.t = {'share': 's', 'host': 'h'}; smb2.d = TOP
smb2.args = ['sh', '-c', 'printf "a\\377b\\n"', 'x']
try:
    out = m.RbSmb._run(smb2, ['ls'])
    ok('smb: bytes past UTF-8 read', 'a�b' in out, repr(out))
except Exception as e:                                  # noqa: BLE001
    ok('smb: bytes past UTF-8 read', False, e)

# ==== 5 the other node's old address: asked again until it goes
st.set_meta('readdress:dropold:other', json.dumps({'from': 'other', 'id': 'r1', 'old': '192.0.2.1',
                                                   'new': '192.0.2.2'}))
tries = []


def hba_fail(old, new, add, drop_old=False):
    tries.append((old, new)); raise RuntimeError('root helper away')


real = m._readdress_hba
m._readdress_hba = hba_fail
m.readdress_dropold_tick(st)
ok('dropold: not done after a failure', (st.get_meta('readdress:dropold:done:fx318') or '') != 'r1',
   st.get_meta('readdress:dropold:done:fx318'))
m._readdress_hba = lambda old, new, add, drop_old=False: tries.append((old, new)) or 'taken out'
m.readdress_dropold_tick(st)
ok('dropold: asked again and done', len(tries) == 2 and st.get_meta('readdress:dropold:done:fx318') == 'r1',
   (tries, st.get_meta('readdress:dropold:done:fx318')))
m.readdress_dropold_tick(st)
ok('dropold: not asked a third time', len(tries) == 2, tries)
m._readdress_hba = real

# ==== 6 a firewall trial: each end claimed
backs = []
m.fw_put_back = lambda store, trial, why: backs.append(trial.get('until'))
t0 = time.time() - 100
st.set_meta('fw:trial', json.dumps({'id': 't1', 'until': t0, 'min': 5}))
m.fw_trial_tick(st)
st.set_meta('fw:trial', json.dumps({'id': 't1', 'until': t0 + 50, 'min': 5}))
m.fw_trial_tick(st)
m.fw_trial_tick(st)
ok('fw trial: put back at each end, once each', backs == [t0, t0 + 50], backs)

# ==== 7 the lockout limit as in force
m.CONFIG['lockout_after'] = 6; m.CONFIG['split_halve'] = True
m.split_apart = lambda *a, **k: True
st.db.insert('tokens', {'name': 'lk', 'locked_until': time.time() + 600, 'failures': 3, 'fail_times': '[]'})
try:
    rows = [r for r in m.lockouts_shared(st) if r['who'] == 'lk']
    ok('lockouts: halved limit shown while apart', rows and rows[0]['limit'] == 3, rows)
except Exception as e:                                  # noqa: BLE001
    ok('lockouts: halved limit shown while apart', False, repr(e))
m.split_apart = lambda *a, **k: False
rows = [r for r in m.lockouts_shared(st) if r['who'] == 'lk']
ok('lockouts: the whole limit together', rows and rows[0]['limit'] == 6, rows)

# ==== 8 web_tick looks at the balancer's settings
import inspect
src = inspect.getsource(m.web_tick)
ok('web_tick: realip and sso_peer wake it', "'realip' not in desired" in src and "'sso_peer' not in desired" in src)

# ==== 9 a VIP interface name as root takes it
m.ha_nodes = lambda store: []
base = {'address': '192.0.2.50/24', 'vrid': 51}
for bad in ('-x', '.', '..', 'a b', 'x' * 16):
    try:
        m.vip_checked(dict(base, ifaces={'n1': bad}), st); ok('vip: refused %r' % bad, False)
    except ValueError:
        ok('vip: refused %r' % bad, True)
for good in ('eth0', 'ens192', 'bond0.10', 'eth0:1', 'br_lan'):
    try:
        m.vip_checked(dict(base, ifaces={'n1': good}), st); ok('vip: taken %r' % good, True)
    except ValueError as e:
        ok('vip: taken %r' % good, 'network interface' not in str(e), e)

print('ALL %d / %d' % (sum(R), len(R)))
