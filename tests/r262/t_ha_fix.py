"""t_ha_fix.py - 1.0.262, the HA fixes: in-process with stubs, no PostgreSQL, no ports.
F1 split: the preferred node changing its network / away on purpose is a reason to serve here.
F2 net_ask: a new network refused in a cluster where no other node answers (not going back).
F3 radius_bind for the network asked for (net_bind_after).
F4 ha_readdress: one address against one, not a part of the text.
F5 secondary IPv4 addresses kept (root: net_addrs4_after; daemon: net_kept4, ha_address check).
F6 net_check: going back takes a gateway outside the subnet / any IPv6 gateway.
F7 shared database: keepalived's peer from the fresh heartbeat.
F8 alerts_quiet: quiet while a node changes its network / is away on purpose.
F9 root: net_static_hostname falls back on the kernel's name.
F10 web_state reads NGINX_CERT_FILES.
Round 2: F2 only a partner heard from and out of service (or on trial) refuses; F3 radius_bind
rewritten only for an address the change takes away; F7 the ha_address the other node publishes;
F the VIP pair of the VIP's family; G one node makes the authority; H the rule not changed while
apart; I a failed link step back to the link; J --ha-forget; K the other's clock for the
directory; L one node looks for new versions."""
import os, sys, re, json, time, threading, types
from pathlib import Path
PARTS = '/home/claude/build/parts'
ROOT_HELPER = '/home/claude/build/out/otp-%s/deploy/otp_web.py' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.262')
R = []
HEAD = ('import os, re, json, time, threading, socket, secrets, ipaddress, subprocess, shutil, '
        'hashlib\nfrom pathlib import Path\n')


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]),
                             flush=True)


def src(f):
    return open(os.path.join(PARTS, f)).read()


def load(f, **extra):
    g = {'__name__': 'part', 'STATE_DIR': Path('/nonexistent'), 'log': lambda *a, **k: None,
         'log_sparing': lambda *a, **k: None, 'CONFIG': {}, 'FILE_CONFIG': {},
         'fnum': lambda x, d=0.0: float(x) if isinstance(x, (int, float)) or
         (isinstance(x, str) and re.match(r'^-?[0-9.]+$', x)) else d,
         'odict': lambda x: x if isinstance(x, dict) else {}}
    g.update(extra)
    exec(HEAD + src(f), g)
    return g


def raises(fn, *a, **k):
    try:
        fn(*a, **k)
    except ValueError as e:
        return str(e)
    return None


class Store(object):
    def __init__(self, meta=None):
        self.meta = dict(meta or {})

    def get_meta(self, k):
        return self.meta.get(k)

    def set_meta(self, k, v):
        self.meta[k] = v


def meta_json(store, k, kind=dict):
    v = store.get_meta(k)
    try:
        v = json.loads(v) if v else None
    except ValueError:
        return None
    return v if isinstance(v, kind) else None


N = load('87n_net.py', _meta_json=meta_json)

# ============================== F3 ==========================================================
bind = N['net_bind_after']
w4 = {'ip_changed': True, 'old_ip': '10.0.0.5', 'new_ip': '10.0.0.6', 'ipv6': {'on': False},
      'old_ip6': []}
ok('F3 every address stays (IPv6 off)', bind('0.0.0.0', w4) == '0.0.0.0')
ok('F3 empty is every address', bind('', w4) == '0.0.0.0')
ok('F3 :: with IPv6 off -> 0.0.0.0', bind('::', w4) == '0.0.0.0')
ok('F3 old IPv4 -> new IPv4', bind('10.0.0.5', w4) == '10.0.0.6')
ok('F3 (round 2) another address (second NIC, VIP, kept) left as it is', bind('10.0.0.9', w4) == '10.0.0.9',
   bind('10.0.0.9', w4))
ok('F3 (round 2) the VIP address with ip_nonlocal_bind left', bind('10.0.0.100', w4) == '10.0.0.100')
ok('F3 the new address stays', bind('10.0.0.6', w4) == '10.0.0.6')
w6 = {'ip_changed': False, 'old_ip': '10.0.0.5', 'new_ip': '10.0.0.5',
      'ipv6': {'on': True, 'mode': 'manual', 'addr': '2001:db8::20/64'},
      'old_ip6': ['2001:db8::10']}
ok('F3 0.0.0.0 with IPv6 on -> ::', bind('0.0.0.0', w6) == '::')
ok('F3 :: with IPv6 on stays', bind('::', w6) == '::')
ok('F3 old IPv6 -> new IPv6', bind('2001:DB8:0::10', w6) == '2001:db8::20', bind('2001:DB8:0::10', w6))
ok('F3 IPv4 address kept (not changed) stays', bind('10.0.0.5', w6) == '10.0.0.5')
ok('F3 (round 2) an automatic IPv6 address left as it is', bind('2001:db8::99', w6) == '2001:db8::99')
w6off = dict(w6, ipv6={'on': False})
ok('F3 old IPv6 with IPv6 off -> 0.0.0.0', bind('2001:db8::10', w6off) == '0.0.0.0')
ok('F3 (round 2) another IPv6 address, IPv6 off here: left', bind('2001:db8::99', w6off) == '2001:db8::99')
ok('F3 not an address: left', bind('otp1.example.cz', w4) == 'otp1.example.cz')
w6auto = dict(w6, ipv6={'on': True, 'mode': 'auto', 'addr': ''})
ok('F3 old IPv6, IPv6 automatic -> ::', bind('2001:db8::10', w6auto) == '::')

# ============================== F5 (daemon) =================================================
ok('F3 the job calls net_bind_after(rb, w)', 'nb = net_bind_after(rb, w)' in src('87n_net.py'))
body = src('87n_net.py')
i = body.index('def net_job_run')
j = body.index('\ndef ', i + 10)
jr = body[i:j]
ok('F5 told only with ha_address empty or the old one',
   "ha_on_old = net_ha_on_old(CONFIG.get('ha_address'), w['old_ip'])" in jr and
   "CONFIG.get('ha_mode') == 'replicated' and ha_on_old" in jr)


def ha_on_old(ha_address, old_ip):
    return str(ha_address or '') in ('', old_ip)


ok('F5 matrix case: ha_address == primary -> told', ha_on_old('10.0.0.5', '10.0.0.5'))
ok('F5 ha_address empty -> told', ha_on_old('', '10.0.0.5'))
ok('F5 replication on a second address -> not told', not ha_on_old('10.0.1.5', '10.0.0.5'))

# ============================== F5 (root) ===================================================
rh = open(ROOT_HELPER).read()


def rblock(name):
    i = rh.index('def %s(' % name)
    m = re.compile(r'^(def |class |[A-Z_]+ = )', re.M).search(rh, i + 5)
    return rh[i:m.start()]


RG = {'re': re, 'os': os}
exec(rblock('nm_list') + '\n' + rblock('net_addrs4_after'), RG)
after = RG['net_addrs4_after']
b = {'ipv4.method': 'manual', 'ipv4.addresses': '10.0.0.5/24, 10.0.1.5/24'}
ok('F5 root: the primary replaced, the second kept',
   after(b, '10.0.0.6/24') == ['10.0.0.6/24', '10.0.1.5/24'], after(b, '10.0.0.6/24'))
ok('F5 root: one address as before', after({'ipv4.method': 'manual', 'ipv4.addresses': '10.0.0.5/24'},
                                         '10.0.0.6/24') == ['10.0.0.6/24'])
ok('F5 root: DHCP before - the new one alone',
   after({'ipv4.method': 'auto', 'ipv4.addresses': '10.0.1.5/24'}, '10.0.0.6/24') == ['10.0.0.6/24'])
ok('F5 root: the new one among the others not twice',
   after(b, '10.0.1.5/24') == ['10.0.1.5/24'], after(b, '10.0.1.5/24'))
ok('F5 root: nmcli gets them joined', "','.join(net_addrs4_after(before, n['addr4']))" in rh)

# ============================== F9 ==========================================================


class Refused(Exception):
    pass


for said, exc, want in (('otp1.example.cz\n', None, 'otp1.example.cz'), ('', None, 'kernel-name'),
                        (None, Refused('no'), 'kernel-name'), (None, OSError('x'), 'kernel-name')):
    def run(args, what, _s=said, _e=exc):
        if _e:
            raise _e
        return _s
    fake_os = types.SimpleNamespace(uname=lambda: types.SimpleNamespace(nodename='Kernel-Name.'))
    G9 = {'run': run, 'Refused': Refused, 'HOSTNAMECTL': 'hostnamectl', 'os': fake_os}
    exec(rblock('net_static_hostname'), G9)
    got = G9['net_static_hostname']()
    ok('F9 net_static_hostname %r/%s -> %s' % (said, type(exc).__name__, want), got == want, got)

# ============================== F6 ==========================================================
DATA = {'nm': True, 'con': 'eth0', 'devices': [{'con': 'eth0', 'dev': 'eth0'}], 'hostname': 'otp1',
        'conf': {'ipv4_method': 'manual', 'ipv4_addresses': ['10.0.0.5/24'], 'ipv6_method': 'disabled'}}
N.update(net_node_now=lambda s, n: {'data': DATA}, in_cluster=lambda s=None: False,
         ha_nodes=lambda s: [], vip_conf=lambda s: {}, node_name=lambda: 'otp1')
exec(src('50_storage.py')[src('50_storage.py').index('PLAIN_ADDR_RE'):].split('\ndef address_net')[0], N)
want = {'con': 'eth0', 'ipv4': {'addr': '10.0.0.6/24', 'gw': '192.168.9.1', 'dns': []},
        'ipv6': {'on': True, 'mode': 'manual', 'addr': '2001:db8::20/64', 'gw': 'fe80::1%eth0'},
        'hostname': 'otp1'}
e = raises(N['net_check'], Store(), 'otp1', want)
ok('F6 a change: a gateway outside the subnet refused', e and 'is not another address' in e, e)
try:
    got = N['net_check'](Store(), 'otp1', want, rollback=True)
    ok('F6 going back: the gateways are taken', got['ipv4']['gw'] == '192.168.9.1', got['ipv4'])
except Exception as ex:                                 # noqa: BLE001
    ok('F6 going back: the gateways are taken', False, repr(ex))
ok('F6 going back: an IPv6 gateway root would not take is left out', got['ipv6']['gw'] == '', got['ipv6'])
wg = dict(want, ipv6=dict(want['ipv6'], gw='2001:db8::1'))
ok('F6 going back: a good IPv6 gateway kept',
   N['net_check'](Store(), 'otp1', wg, rollback=True)['ipv6']['gw'] == '2001:db8::1')
wb = dict(want, ipv4=dict(want['ipv4'], gw='not-an-ip'))
ok('F6 going back: no address as gateway left out',
   N['net_check'](Store(), 'otp1', wb, rollback=True)['ipv4']['gw'] == '')
ok('F6 root takes it going back', "(g not in a4.network and not r.get('rollback'))" in rh)
want2 = dict(want, ipv4=dict(want['ipv4'], gw='10.0.0.1'))
e = raises(N['net_check'], Store(), 'otp1', want2)
ok('F6 a change: an IPv6 gateway with a zone id refused', e and 'IPv6 gateway' in e, e)

# ============================== F2 (round 2) ================================================
N.update(in_cluster=lambda s=None: True, power_busy=lambda s: False,
         cluster_busy=lambda s, skip=(): '',
         net_check=lambda s, n, w, rollback=False: {'plan': ['x']})
HN = {'v': []}
MAINT, ASIDE = {}, {}
N.update(node_name=lambda: 'otp1', ha_nodes=lambda s: HN['v'],
         maintenance_row=lambda s, n=None: {'on': MAINT.get(n, False)},
         node_stepped_aside=lambda s, n: ASIDE.get(n, False))
st = Store()
st.add_event = lambda *a, **k: None
ask = N['net_ask']
HN['v'] = [{'name': 'otp1', 'me': True, 'alive': True}]
ok('F2 standalone after --ha-standalone (only this node): asked', raises(ask, st, 'otp1', {}, 'a') is None)
HN['v'] = [{'name': 'otp1', 'me': True, 'alive': True}, {'name': 'otp2', 'me': False, 'alive': False}]
ok('F2 the partner dead: asked (never blocked for good)', raises(ask, st, 'otp1', {}, 'a') is None)
MAINT['otp2'] = True
ok('F2 the partner dead, its old maintenance row on: asked', raises(ask, st, 'otp1', {}, 'a') is None)
HN['v'][1]['alive'] = True
e = raises(ask, st, 'otp1', {}, 'a')
ok('F2 the partner alive in maintenance: refused', e and 'otp2 does not answer now' in e, e)
ok('F2 going back is never refused', raises(ask, st, 'otp1', {}, 'a', rollback=True) is None)
MAINT['otp2'] = False
ASIDE['otp2'] = True
ok('F2 the partner alive, stepped aside: refused', raises(ask, st, 'otp1', {}, 'a') is not None)
ASIDE['otp2'] = False
ok('F2 the partner alive and serving: asked', raises(ask, st, 'otp1', {}, 'a') is None)
st.meta['net:job:otp2'] = json.dumps({'state': 'trial', 'trial_until': time.time() + 600,
                                      'moved': time.time()})
e = raises(ask, st, 'otp1', {}, 'a')
ok('F2 the partner\'s network on trial: refused', e and 'waits to be kept' in e, e)
HN['v'][1]['alive'] = False
ok('F2 on trial counts even when not heard from', raises(ask, st, 'otp1', {}, 'a') is not None)
st.meta.pop('net:job:otp2')
HN['v'][1]['alive'] = True
MAINT['otp1'] = True
e = raises(ask, st, 'otp2', {}, 'a')
ok('F2 otp2 asked from otp1 in maintenance: refused', e and 'otp1 does not answer now' in e, e)
MAINT['otp1'] = False
ok('F2 otp2 asked from otp1 serving: asked', raises(ask, st, 'otp2', {}, 'a') is None)
ok('F2 the job checks the same before maintenance',
   "held = '' if job.get('rollback') else net_others_held(store, me)" in jr)

# ============================== F4 ==========================================================


class Stop(Exception):
    pass


class StopLock(object):
    def __enter__(self):
        raise Stop()

    def __exit__(self, *a):
        return False


U = load('87u_readdress.py', _cert_name_key=N['_cert_name_key'], READDRESS_LOCK=StopLock(),
         node_address=lambda: '', _sub_host=lambda s: '',
         peer_address=lambda t: __import__('ipaddress').ip_address(t))
U['READDRESS_LOCK'] = StopLock()
U['CONFIG'].update(ha_mode='replicated', ha_address='10.0.0.12', ha_peer='10.0.0.5')


def readdress(**k):
    try:
        U['ha_readdress'](Store(), **k)
    except Stop:
        return 'went on'
    except ValueError as e:
        return str(e)


ok('F4 10.0.0.1 is not a part of 10.0.0.12', readdress(peer='10.0.0.1') == 'went on',
   readdress(peer='10.0.0.1'))
ok('F4 the same address refused', 'cannot have one address' in readdress(peer='10.0.0.12'))
ok('F4 mine and peer the same refused', 'cannot have one address' in readdress(mine='10.0.0.7',
                                                                             peer='10.0.0.7'))

# ============================== F8 ==========================================================
AWAY = {'v': {}}
A = load('88z_alerts.py', _meta_json=meta_json, net_job_active=N['net_job_active'],
         maintenance_row=lambda s, n=None: {'on': False}, upgrade_plan=lambda s: {},
         osup_plan=lambda s: {}, power_busy=lambda s: False, node_name=lambda: 'otp1',
         ha_planned_away=lambda s: AWAY['v'], json_obj=lambda v: json.loads(v) if v else None,
         ALERTS_QUIET_AFTER_S=600)
A['NET_JOB_LIVE_S'] = 1800
st = Store()
st.db = types.SimpleNamespace(rows=lambda *a: [])
ok('F8 nothing going on: not quiet', A['alerts_quiet'](st, ['otp1', 'otp2']) == '')
st.meta['net:job:otp2'] = json.dumps({'state': 'rebooting', 'moved': time.time()})
got = A['alerts_quiet'](st, ['otp1', 'otp2'])
ok('F8 a node changing its network: quiet', got == 'otp2 is changing its network', got)
st.meta['net:job:otp2'] = json.dumps({'state': 'done', 'moved': time.time()})
st.meta.pop('alerts:quiet:otp1', None)
AWAY['v'] = {'otp2': 'otp2 is restarting'}
got = A['alerts_quiet'](st, ['otp1', 'otp2'])
ok('F8 away on purpose: quiet', got == 'otp2 is restarting', got)

# ============================== F1 ==========================================================
Y = src('87y_split.py')
i = Y.index('def split_preferred_unable')
spu = Y[i:Y.index('\ndef ', i + 10)]
G1 = {'_meta_json': meta_json, 'net_job_active': N['net_job_active'], 'NET_JOB_LIVE_S': 1800,
      'split_preferred_name': lambda s: 'otp2', 'node_name': lambda: 'otp1',
      'peer_db_restarting': lambda e: '', 'SPLIT': {'peer_err': '', 'apart_since': time.time()},
      'clock_state_of': lambda s, n: {}, 'clock_skew_of': lambda s, n: 0.0,
      'fnum': lambda x, d=0.0: float(x or 0), 'CONFIG': {}, 'time': time,
      'ha_nodes': lambda s: [], 'ha_planned_away': lambda s: AWAY['v']}
exec(spu, G1)
AWAY['v'] = {}
st = Store()
ok('F1 nothing: no reason', G1['split_preferred_unable'](st) == '')
st.meta['net:job:otp2'] = json.dumps({'state': 'running', 'moved': time.time()})
ok('F1 changing its network: a reason', 'changing its network' in G1['split_preferred_unable'](st))
st.meta['net:job:otp2'] = json.dumps({'state': 'running', 'moved': time.time() - 4000})
ok('F1 a job long still: no reason', G1['split_preferred_unable'](st) == '')
AWAY['v'] = {'otp2': 'otp2 is restarting'}
ok('F1 restarting on purpose: a reason', G1['split_preferred_unable'](st) != '')

# ============================== F7 (round 2) ================================================
W = src('88w_web.py')
G7 = {'time': time, 'vip_plain': lambda a, like='': a, '_cert_name_key': N['_cert_name_key'],
      'node_name': lambda: 'otp1', 'STATE_DIR': Path('/nonexistent'), 'dbguard_node_ok': lambda s, n: True,
      'fnum': lambda x, d=0.0: float(x or 0), 'CONFIG': {}, '_meta_json': meta_json}
NODES = {'v': []}
G7['ha_nodes'] = lambda s: NODES['v']
G7['ipaddress'] = __import__('ipaddress')
for name in ('vip_of_family', 'vip_peer_seen', 'vip_peer_published', 'vip_peer_want'):
    i = W.index('def %s(' % name)
    exec(W[i:W.index('\ndef ', i + 10)], G7)
NODES['v'] = [{'name': 'otp1', 'address': '10.0.0.5', 'age': 1},
              {'name': 'otp2', 'address': '192.168.1.7', 'age': 3}]
G7['CONFIG'].update(ha_mode='shared', ha_peer='10.0.0.6')
st7 = Store()
ok('F7 shared, not published (1.0.261): ha_peer', G7['vip_peer_want'](st7) == '10.0.0.6')
st7.meta['net:now:otp2'] = json.dumps({'ha_address': '', 'at': time.time()})
ok('F7 shared, published empty: ha_peer', G7['vip_peer_want'](st7) == '10.0.0.6')
st7.meta['net:now:otp2'] = json.dumps({'ha_address': '10.0.0.7', 'at': time.time()})
ok('F7 shared: the ha_address it publishes, not its heartbeat\'s default-route one',
   G7['vip_peer_want'](st7) == '10.0.0.7', G7['vip_peer_want'](st7))
ok('M shared: of the VIP\'s family', G7['vip_peer_want'](st7, '10.0.0.100/24') == '10.0.0.7')
ok('M shared: of another family than the VIP - ha_peer', G7['vip_peer_want'](st7, 'fd00::100/64') == '10.0.0.6')
st7.meta['net:now:otp2'] = json.dumps({'ha_address': '10.0.0.7', 'at': time.time() - 3600})
ok('M shared: an old row (an hour) - ha_peer', G7['vip_peer_want'](st7, '10.0.0.100/24') == '10.0.0.6')
st7.meta['net:now:otp2'] = json.dumps({'ha_address': '10.0.0.6', 'at': time.time()})
ok('M shared: the same as ha_peer - ha_peer', G7['vip_peer_want'](st7) == '10.0.0.6')
st7.meta['net:now:otp2'] = json.dumps({'ha_address': '10.0.0.7', 'at': time.time()})
G7['CONFIG'].update(ha_mode='replicated')
ok('F7 replicated: ha_peer as before', G7['vip_peer_want'](st7) == '10.0.0.6')
G7['CONFIG'].update(ha_peer='')
ok('F7 replicated, no ha_peer: the heartbeat as before', G7['vip_peer_want'](st7) == '192.168.1.7')

# ============================== F (round 2): VIP family ======================================
import ipaddress
GF = dict(G7, ipaddress=ipaddress, odict=lambda x: x if isinstance(x, dict) else {},
          vip_plain=lambda a, like='': a, node_address=lambda: '10.0.0.5')
LOCAL = {'v': set()}
GF['local_addresses'] = lambda: LOCAL['v']
for name in ('vip_of_family', 'vip_pick', 'vip_family_fix'):
    i = W.index('def %s(' % name)
    exec(W[i:W.index('\ndef ', i + 10)], GF)
NODES['v'] = [{'name': 'otp1', 'address': '10.0.0.5', 'age': 1},
              {'name': 'otp2', 'address': '10.0.0.7', 'age': 3}]
stf = Store()
v = GF['vip_family_fix'](stf, {'address': '10.0.0.100/24', 'own': '10.0.0.5', 'peer': '10.0.0.7'})
ok('F same family: as it was', v['own'] == '10.0.0.5' and v['peer'] == '10.0.0.7', v)
LOCAL['v'] = {'127.0.0.1', '::1', 'fe80::1', '10.0.0.5', '2001:db8::5', '10.0.0.100'}
v = GF['vip_family_fix'](stf, {'address': '10.0.0.100/24', 'own': '2001:db8::5', 'peer': '2001:db8::7'})
ok('F IPv6 nodes, IPv4 VIP: own of IPv4', v['own'] == '10.0.0.5', v)
ok('F IPv6 nodes, IPv4 VIP: peer from its heartbeat', v['peer'] == '10.0.0.7', v)
GF['node_address'] = lambda: '10.0.0.5'
stf.meta['net:now:otp2'] = json.dumps({'data': {'live': {'addrs6': [{'addr': '2001:db8::7/64'}],
                                                          'addrs4': [{'addr': '10.9.0.7/24'}]}}})
v = GF['vip_family_fix'](stf, {'address': '2001:db8::100/64', 'address6': '', 'own': '10.0.0.5',
                               'peer': '10.0.0.7'})
ok('F IPv4 nodes, IPv6 VIP: own IPv6 of this machine', v['own'] == '2001:db8::5', v)
ok('F IPv4 nodes, IPv6 VIP: peer IPv6 from what it says its network is', v['peer'] == '2001:db8::7', v)
stf.meta.pop('net:now:otp2')
LOCAL['v'] = {'10.0.0.5'}
v = GF['vip_family_fix'](stf, {'address': '2001:db8::100/64', 'own': '10.0.0.5', 'peer': '10.0.0.7'})
ok('F none of the family: empty (the VIP waits), never a mismatched pair',
   v['own'] == '' and v['peer'] == '', v)
wd = W[W.index('def web_desired('):]
ok('F web_desired: fixed before kept, a last pair of another family dropped',
   wd.index('vip_family_fix(store, vip)') < wd.index('vip_last_keep(') and 'last = None' in wd)

# ============================== F10 =========================================================
i = W.index('def web_state(')
ws = W[i:W.index('\ndef ', i + 10)]
ok('F10 web_state reads NGINX_CERT_FILES', "cert_now(NGINX_CERT_FILES['node'])" in ws and
   "cert_now(NGINX_CERT_FILES['vip'])" in ws and '/etc/nginx/certs' not in ws)

# ============================== G-L (round 2) ===============================================
D = src('87d_dbtls.py')
i = D.index('def _dbtls_server_cert(')
dsc = D[i:D.index('\ndef ', i + 10)]


class Lock(object):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


CA = {'cas': []}
MADE = []
LEAD = {'v': False}
GG = {'HATLS_LOCK': Lock(), 'hatls_ca': lambda s: CA, 'HATLS_CA_ROLL_DAYS': 30, 'time': time,
      'CONFIG': {'ha_mode': 'replicated'}, 'ha_lead': lambda s: LEAD['v'],
      'hatls_ca_make': lambda s, by: (MADE.append(by), CA.update(cas=[{'end': time.time() + 9e7}])),
      'hatls_names': lambda: ['n'], 'hatls_issue': lambda s, n: ('k', 'c'),
      '_dbtls_helper': lambda *a: {'cert_end': 1}, 'hatls_trust': lambda ca: 'pem',
      'node_name': lambda: 'otp2', 'json': json, '_cert_end': lambda c: 1}
exec(dsc, GG)
T = {'t': 1000.0}
GG['time'] = types.SimpleNamespace(time=lambda: T['t'], sleep=lambda s: T.update(t=T['t'] + s))
st = Store()
e = raises(GG['_dbtls_server_cert'], st, 'x')
ok('G not the lead, no authority: waits, never makes one', MADE == [] and e and 'come over' in e, e)
LEAD['v'] = True
ok('G the lead makes it', raises(GG['_dbtls_server_cert'], st, 'x') is None and MADE == ['x'])
LEAD['v'] = False
CA['cas'] = [{'end': T['t'] + 86400}]
MADE[:] = []
ok('G not the lead, the authority ending soon but good: goes on with it',
   raises(GG['_dbtls_server_cert'], st, 'x') is None and MADE == [])
GG['CONFIG'] = {'ha_mode': ''}
CA['cas'] = []
ok('G standalone: made as before', raises(GG['_dbtls_server_cert'], st, 'x') is None and MADE == ['x'])

Ysrc = src('87y_split.py')
i = Ysrc.index('def split_change_refused(')
GH = {'APART': {'v': False}, 're': re, 'CONFIG': {}}
GH['split_apart'] = lambda: GH['APART']['v']
exec(Ysrc[i:Ysrc.index('\ndef ', i + 10)] if '\ndef ' in Ysrc[i + 10:] else Ysrc[i:], GH)
scr = GH['split_change_refused']
ok('H together: any change taken', scr({'split_mode': 'priority', 'split_prefer': 'otp1'}) == '')
GH['APART']['v'] = True
ok('H apart: the preferred node refused', 'apart' in scr({'split_prefer': 'otp2'}))
ok('H apart: a mode set on each half taken (how they are run while apart)', scr({'split_mode': 'arbiter'}) == '')
ok('H apart: an arbiter taken', scr({}, {'otp1': '10.0.0.1'}) == '')
ok('H apart: switching it off taken', scr({'split_mode': 'off', 'split_prefer': 'otp2'}) == '')
ok('H apart: the report settings taken', scr({'split_report': 1}) == '')
ok('H the API asks it, with the arbiters changed only', 'split_change_refused(want, {n: v for n, v in arb.items()'
   in src('90y_split_api.py'))
GH['CONFIG'].update(split_mode='priority', split_prefer='otp1', split_after_s=20)
ok('O apart: the card sent as kept - taken', scr({'split_mode': 'priority', 'split_prefer': 'otp1',
                                                  'split_report': 1}) == '')
ok('O apart: the same number as text - taken', scr({'split_mode': 'priority', 'split_prefer': 'otp1',
                                                    'split_after_s': '20'}) == '')
ok('O apart: the preferred node changed - refused', scr({'split_mode': 'priority', 'split_prefer': 'otp2'}) != '')

Hs = src('87t_hatls.py')
ok('I a failed link with nothing wrong goes back to the link, its time again',
   "if not wrong and st.get('step') == 'failed' and st.get('failed_step') == 'link':" in Hs and
   "step='link', link_since=now" in Hs)
cli = src('95_cli.py')
i = cli.index('    if args.ha_forget:')
ok('J --ha-forget leaves maint:/upgrade:node: to ha_forget',
   "'maint:' + args.ha_forget" not in cli[i:i + 900])

Z = src('87z_clock.py')
i = Z.index('def clock_decide(')
GK = {}
exec(Z[i:Z.index('\ndef ', i + 10)], GK)
cd = GK['clock_decide']
well = {'fresh': True, 'role': 'serve', 'dir_ok': True, 'ref': 0.5}
ok('K directory: the other well, its clock good - aside', cd('guard', 0, 20, False, False, True, well)[0] == 'aside')
ok('K directory: the other\'s clock off - serve', cd('guard', 0, 20, False, False, True,
                                                    dict(well, ref=60))[0] == 'serve')
ok('K directory: the other\'s clock not measured - aside as before',
   cd('guard', 0, 20, False, False, True, dict(well, ref=None))[0] == 'aside')
ok('K clock_dir_failover checks the clock too', "abs(fnum(pr)) > float(CONFIG.get('clock_aside_s') or 20)" in Z)
O = src('88o_online.py')
i = O.index('def online_tick(')
ot = O[i:O.index('\ndef ', i + 10)] if '\ndef ' in O[i + 10:] else O[i:]
ok('L online_tick: one node of a replicated pair', "CONFIG.get('ha_mode') == 'replicated' and not ha_lead(store)" in ot
   and ot.index('ha_lead(store)') < ot.index('threading.Thread'))

# ============================== round 3 =====================================================
import tempfile
# 1. Keep: readdress:dropold only for a told, changed IPv4 address
X = src('87x_trial.py')
i = X.index('def net_trial_tick(')
GT = {'_meta_json': meta_json, 'node_name': lambda: 'otp1', 'json': json, 'time': time,
      'fnum': lambda x, d=0.0: float(x or 0), '_job_put': lambda st, j, *a, **k: j.update(k),
      'net_go_back': lambda *a: None, 'net_trial_back_wait': lambda s, j: ''}
exec(X[i:X.index('\ndef ', i + 10)], GT)
D3 = types.SimpleNamespace()
for name, job, want_drop in (
        ('gateway only', {'keep_old': True, 'told': False, 'want': {'ip_changed': False, 'old_ip': '10.0.0.5',
                                                                     'new_ip': '10.0.0.5'}}, False),
        ('replication on another address (not told)', {'keep_old': True, 'want': {
            'ip_changed': True, 'old_ip': '10.0.0.5', 'new_ip': '10.0.0.6'}}, False),
        ('told, changed', {'keep_old': True, 'told': True, 'want': {'ip_changed': True, 'old_ip': '10.0.0.5',
                                                                    'new_ip': '10.0.0.6'}}, True)):
    st = Store()
    st.add_event = lambda *a, **k: None
    job = dict(job, id='j1')
    st.meta['net:keep:otp1'] = json.dumps({'id': 'j1', 'by': 'admin'})
    D3.store = st
    GT['net_trial_tick'](D3, job)
    ok('R3-1 Keep, %s: dropold %s' % (name, 'asked' if want_drop else 'not asked'),
       ('readdress:dropold:otp1' in st.meta) == want_drop, st.meta)
pr = open('/tmp/claude-0/h262/r3_otpweb_patch.py').read()
ok('R3-1 root patch: pgtls_peer old == net is no old', "olds = bool(old) and old != net" in pr)

# 2. before kept on this machine; put back after a stalled job / a give-up
tmpd = tempfile.mkdtemp(prefix='t-r3-')
N3 = load('87n_net.py', _meta_json=meta_json, STATE_DIR=Path(tmpd))
N3['NET_BEFORE_FILE'] = Path(tmpd) / 'net-before.json'


def write_replacing(path, text, mode=0o640, owner=None):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, 'w') as f:
        f.write(text)


N3['write_replacing'] = write_replacing
N3['net_before_keep']('j9', {'settings': {'radius_bind': '10.0.0.5'}})
ok('R3-2 kept 0600', oct(os.stat(N3['NET_BEFORE_FILE']).st_mode & 0o777) == '0o600')
ok('R3-2 read back for its job only', N3['net_before_get']('j9') == {'settings': {'radius_bind': '10.0.0.5'}}
   and N3['net_before_get']('other') is None)
PUT = []
N3.update(net_undo_put_back=lambda d, b, by: PUT.append(b) or ['radius_bind = 10.0.0.5'],
          net_job_undo_told=lambda *a: None, maintenance_set=lambda *a, **k: None,
          _job_put=lambda st, j, *a, **k: j.update(k))
D3 = types.SimpleNamespace(store=Store())
N3['net_job_stalled'](D3, {'id': 'j9', 'maint': True}, 'otp')
ok('R3-2 stalled: put back from what was kept, and the file gone',
   PUT == [{'settings': {'radius_bind': '10.0.0.5'}}] and not N3['NET_BEFORE_FILE'].exists(), PUT)
N3['net_before_keep']('j8', {'settings': {}})
D3.store.add_event = lambda *a, **k: None
N3['local_addresses'] = lambda: set()
N3['node_name'] = lambda: 'otp1'
N3['net_job_give_up'](D3, {'id': 'j8', 'want': {'new_ip': '10.0.0.6'}})
ok('R3-2 give-up: put back too', len(PUT) == 2 and not N3['NET_BEFORE_FILE'].exists())
body3 = src('87n_net.py')
i = body3.index('def net_job_run')
jr3 = body3[i:body3.index('\ndef ', i + 10)]
ok('R3-2 the job keeps it at its start', 'net_before_keep(ask[\'id\'], before)' in jr3)

# 3. net_job_after: in_cluster, maintenance ended whenever the job put it on
i = body3.index('def net_job_after')
ja = body3[i:body3.index('\ndef ', i + 10)]
ok('R3-3 net_job_after: many = in_cluster(store)', 'many = in_cluster(store)' in ja)
ok('R3-3 maintenance ended whenever the job put it on', "    if job.get('maint'):\n        maintenance_set(store, False" in ja)

# 4. going back on time-out waits while nobody else answers
i = X.index('def net_trial_back_wait(')
GW = {'in_cluster': lambda s: True, 'NET_TRIAL_BACK_WAIT_S': 1800, 'time': time,
      'fnum': lambda x, d=0.0: float(x or 0), 'node_name': lambda: 'otp1'}
HELD = {'v': ''}
OIS = {'v': ['otp2']}
GW.update(net_others_held=lambda s, n: HELD['v'], others_in_service=lambda s: OIS['v'])
exec(X[i:X.index('\ndef ', i + 10)] if '\ndef ' in X[i + 10:] else X[i:], GW)
bw = GW['net_trial_back_wait']
jt = {'trial_until': time.time() - 60}
ok('R3-4 the other answers: goes back', bw(None, jt) == '')
HELD['v'] = 'otp2 does not answer now (in maintenance or stepped aside): ...'
ok('R3-4 the other in maintenance: waits', bw(None, jt).startswith('otp2 does not answer'))
HELD['v'], OIS['v'] = '', []
ok('R3-4 nobody heard: waits', 'no other node answers' in bw(None, jt))
ok('R3-4 for 30 min at most', bw(None, {'trial_until': time.time() - 1900}) == '')
GW['in_cluster'] = lambda s: False
ok('R3-4 standalone: goes back', bw(None, jt) == '')
ok('R3-4 the tick asks it on time-out only', 'wait = net_trial_back_wait(store, job)' in X)

# 5. the other node told again until it is reached
N5 = load('87n_net.py', _meta_json=meta_json)
THREADS = []
N5.update(node_name=lambda: 'otp1', _net_thread=lambda fn, *a: THREADS.append((fn, a)) or True,
          ha_nodes=lambda s: [{'name': 'otp2', 'alive': True}])
N5['CONFIG'].update(ha_mode='replicated', ha_address='10.0.0.5', ha_peer='10.0.0.7')
st5 = Store()
st5.drop_meta = lambda k: st5.meta.pop(k, None)
st5.add_event = lambda *a, **k: None
N5['net_tell_pending_set'](st5, 'j1', '10.0.0.5', 'otp')
D5 = types.SimpleNamespace(store=st5)
N5['net_tell_pending_tick'](D5)
ok('R3-5 a pending tell tried', len(THREADS) == 1)
N5['net_tell_pending_tick'](D5)
ok('R3-5 not again within the minute', len(THREADS) == 1)
TELL = {'left': ['not reached']}
N5['readdress_tell'] = lambda peer, mine, by, keep_old=False: ([], TELL['left'])
N5['net_tell_pending_try'](st5, meta_json(st5, 'readdress:tell:otp1'))
ok('R3-5 not reached: kept, counted', (meta_json(st5, 'readdress:tell:otp1') or {}).get('tries') == 1)
TELL['left'] = []
N5['net_tell_pending_try'](st5, meta_json(st5, 'readdress:tell:otp1'))
ok('R3-5 reached: done with', 'readdress:tell:otp1' not in st5.meta)
N5['net_tell_pending_set'](st5, 'j1', '10.0.0.5', 'otp')
N5['CONFIG']['ha_address'] = '10.0.0.9'
N5['NET_TELL']['at'] = 0
N5['net_tell_pending_tick'](D5)
ok('R3-5 ha_address moved on since: dropped', 'readdress:tell:otp1' not in st5.meta)
ok('R3-5 net_job_after keeps it when not reached', 'net_tell_pending_set(store, job.get(\'id\')' in ja)
ok('R3-5 net_tick asks it', 'net_tell_pending_tick(daemon)' in body3[body3.index('def net_tick('):])

# 6. maintenance (and the VIP leaving) before the other node is told
ok('R3-6 maintenance before telling the other node',
   jr3.index("maintenance_set(store, True, 'the network is being changed', by)") <
   jr3.index('ha_readdress(store, mine=w[\'new_ip\']'))
ok('R3-6 the held check before telling', jr3.index('net_others_held(store, me)') < jr3.index('job[\'told\'] = True'))

# 7. radius_bind once root took the network
ok('R3-7 radius_bind not saved with the other settings', "bind_later = changes.pop('radius_bind', None)" in jr3)
ok('R3-7 saved after root took it', jr3.index('applied = True') <
   jr3.index("daemon.save_settings({'radius_bind': bind_later}"))
ok('R3-7 net_job_after sets one still pending', "job.get('bind_later') is not None" in ja)

# 8. IPv6 replication address not changed from here
import ipaddress as _ip
N8 = load('87n_net.py', _meta_json=meta_json)
N8['node_name'] = lambda: 'otp1'
h6 = N8['net_ha6_lost']
now8 = {'data': {'conf': {'ipv6_method': 'manual', 'ipv6_addresses': ['fd00::5/64']}}}
N8['CONFIG'].update(ha_address='fd00::5', ha_peer='fd00::7')
ok('R3-8 the IPv6 replication address changed: refused',
   'replicate over IPv6' in h6(None, 'otp1', now8, True, 'manual', _ip.ip_interface('fd00::9/64')))
ok('R3-8 IPv6 off: refused', h6(None, 'otp1', now8, False, 'off', None) != '')
ok('R3-8 kept as it is: taken', h6(None, 'otp1', now8, True, 'manual', _ip.ip_interface('FD00:0::5/64')) == '')
N8['CONFIG'].update(ha_address='10.0.0.5', ha_peer='10.0.0.7')
ok('R3-8 replication over IPv4: any IPv6 change taken', h6(None, 'otp1', now8, False, 'off', None) == '')
N8['CONFIG'].update(ha_peer='fd00::5')
ok('R3-8 the other node asked, reached here over IPv6: refused',
   h6(None, 'otp2', now8, True, 'manual', _ip.ip_interface('fd00::9/64')) != '')
ok('R3-8 never on going back', 'if many and CONFIG.get(\'ha_mode\') == \'replicated\' and not rollback:' in body3)

# N. ha_address a host name resolving to the old address
NN = load('87n_net.py', _meta_json=meta_json)
NN['addresses_cached'] = lambda name: ['10.0.0.5'] if name == 'otp1.example.cz' else ['10.9.9.9']
hoo = NN['net_ha_on_old']
ok('N empty: on the old one', hoo('', '10.0.0.5'))
ok('N the old address: yes', hoo('10.0.0.5', '10.0.0.5'))
ok('N another address: no', not hoo('10.0.1.5', '10.0.0.5'))
ok('N a host name resolving to the old one: yes', hoo('otp1.example.cz', '10.0.0.5'))
ok('N a host name resolving elsewhere: no', not hoo('repl.example.cz', '10.0.0.5'))
ok('N IPv6 written another way: yes', hoo('FD00:0::5', 'fd00::5'))

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
