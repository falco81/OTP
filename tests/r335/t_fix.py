"""t_fix.py - 1.0.335: a network change failing half way on the root side put back; firewalld's VRRP
rule added without a reload; a cluster with an IPv6 VIP may change its nodes' networks.

    python3 t_fix.py VERSION
"""
import importlib.util, os, shutil, subprocess, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.335'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r335_')
atexit.register(lambda: shutil.rmtree(TOP, True))
os.environ['OTP_STATE'] = TOP
sys.path.insert(0, V + '/deploy')
sys.argv = ['otp-web']
spec = importlib.util.spec_from_file_location('otp_web_t335', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# ==== 1 net_apply put back
calls = []
hosts = TOP + '/hosts'
open(hosts, 'w').write('127.0.0.1 localhost\n10.0.0.5 otp1.example.cz otp1\n')
W.HOSTS_FILE = hosts
W.shutil = type('S', (), {'which': staticmethod(lambda x: '/usr/bin/' + x)})
before = {'ipv4.method': 'manual', 'ipv4.addresses': '10.0.0.5/24', 'ipv4.gateway': '10.0.0.1',
          'ipv4.dns': '10.0.0.2', 'ipv4.dns-search': '--', 'ipv6.method': 'auto', 'ipv6.addresses': '--',
          'ipv6.gateway': '--', 'ipv6.dns': '--'}
W.nm_fields = lambda con, keys: dict(before)


def run(args, what):
    calls.append(list(args))
    if args[:3] == [W.NMCLI, '-t', '-g']:
        return 'eth0\n'
    if args[:2] == [W.HOSTNAMECTL, '--static']:
        return 'otp1.example.cz\n'
    return ''


W.run = run
written = []


def write_root(path, text, mode):
    written.append(path)
    if path == hosts:
        raise PermissionError(1, 'Operation not permitted')
    with open(path, 'w') as f:
        f.write(text)


W.write_root = write_root
n = {'con': 'eth0', 'addr4': '10.0.0.9/24', 'gw4': '10.0.0.1', 'dns4': ['10.0.0.2'], 'search': [],
     'mode6': 'keep', 'hostname': 'otp9.example.cz', 'old_hostname': 'otp1.example.cz', 'old': ['10.0.0.5'],
     'reboot_in': 60, 'snapshot': ''}
try:
    W.net_apply(dict(n))
    e = None
except Exception as x:
    e = x
mods = [c for c in calls if c[:3] == [W.NMCLI, 'connection', 'modify']]
ok('the failure said', isinstance(e, PermissionError), e)
ok('the profile changed, then put back', len(mods) == 2 and '10.0.0.9/24' in mods[0] and
   mods[1][mods[1].index('ipv4.addresses') + 1] == '10.0.0.5/24' and
   mods[1][mods[1].index('ipv4.dns-search') + 1] == '', mods)
ok('the host name put back', [W.HOSTNAMECTL, 'set-hostname', 'otp1.example.cz'] in calls, calls)
ok('no reboot asked', not any('reboot' in ' '.join(c) for c in calls))
ok('/etc/hosts as it was', '10.0.0.5 otp1' in open(hosts).read())

# all well: no undo
calls.clear()
W.write_root = lambda p, t, m: None
W.power_after = lambda what, secs: 'a reboot in %d s' % secs
got = W.net_apply(dict(n))
mods = [c for c in calls if c[:3] == [W.NMCLI, 'connection', 'modify']]
ok('all well: changed once, a reboot', len(mods) == 1 and any('reboot' in s for s in got['said']), (mods, got))

# ==== 2 firewalld without a reload
fw = []


class P(object):
    def __init__(self, rc=0, err=''):
        self.returncode, self.stderr, self.stdout, self.args = rc, err, "", []


def fake_run(args, **kw):
    fw.append(list(args))
    if '--state' in args:
        return P()
    if '--permanent' not in args:
        return P(1, 'Warning: ALREADY_ENABLED')
    return P()


W.NO_SERVICES = False
W.shutil = type('S', (), {'which': staticmethod(lambda x: '/usr/bin/' + x)})
real_sp = W.subprocess.run
W.subprocess.run = fake_run
try:
    said = W.firewall('10.0.0.6', 4, True)
finally:
    W.subprocess.run = real_sp
ok('no firewall-cmd --reload', not any('--reload' in c for c in fw), fw)
ok('kept and in force both', any('--permanent' in c and any(x.startswith('--add-rich-rule=') for x in c) for c in fw)
   and any('--permanent' not in c and any(x.startswith('--add-rich-rule=') for x in c) for c in fw), fw)
ok('already there: said let in', 'let in' in said and 'NOT' not in said, said)

# ==== 3 net_check: an IPv6 VIP
src = open(V + '/otp.py').read()
ok('an IPv6 VIP not compared with the IPv4 network', 'if vnet and vnet.version == 4 and vnet.ip not in a4.network' in src)
print('ALL %d / %d' % (sum(R), len(R)))
