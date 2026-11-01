# t_round5.py VERSION - the bugs found by the fifth round of the bug hunt (1.0.209), each
# shown fixed: in-process against otp.py of VERSION on SQLite, and the root helper and the
# upgrader read as modules (nothing of this machine changed).
import os, sys, json, time, tempfile, subprocess, tarfile, io, importlib.util
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.209'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r5-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r5'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st

# ---- a firewall trial not kept: never "everybody" ---------------------------------------------
otp.web_status = lambda: {}
trial = otp.fw_trial_begin(st, 'admin') or {'was': {}, 'access': {}}
otp.fw_put_back(st, dict(trial, access={}), 'not kept in time')
a = json.loads(st.get_meta('web:access') or '{}')
ok('a firewall trial put back with the lists never set here: the administration not open to all (%s)'
   % a.get('admin'), a.get('admin', {}).get('any') is False and a.get('portal', {}).get('any') is False)
otp.web_status = lambda: {'access': {'admin': {'any': False, 'from': ['10.1.0.0/16'], 'marked': True},
                                     'portal': {'any': True, 'from': [], 'marked': True},
                                     'health': {'any': True, 'from': [], 'marked': False}}}
ok('... the lists nginx has kept for the put-back', otp.access_in_nginx()['admin']['from'] == ['10.1.0.0/16'])

# ---- the VIP: a host name or no other node ----------------------------------------------------
ok('the VIP: an address is itself', otp.vip_plain('192.0.2.12', '192.0.2.100') == '192.0.2.12')
otp.ADDR_CACHE['peer.example.test'] = (time.monotonic(), ['2001:db8::5', '192.0.2.77'], False)
ok('... a host name its address of the VIP\'s family', otp.vip_plain('peer.example.test', '192.0.2.100') == '192.0.2.77')
ok('... nothing: nothing', otp.vip_plain('', '192.0.2.100') == '')
otp.CONFIG.update(ha_mode='shared', ha_peer='')
st.set_meta('web:vip', json.dumps({'on': True, 'address': '192.0.2.100', 'vrid': 51}))
d = otp.web_desired(st)
ok('the VIP on with no other node known: the VIP waits, the rest of the request goes (%s)' % d['vip'],
   d['vip'] == {'on': False} and 'tls' in d)
otp.CONFIG.update(ha_mode='', ha_peer='')
st.db.run("DELETE FROM meta WHERE k = 'web:vip'")

# ---- ACME http-01 with the pages kept to some networks: port 80 for the CA ---------------------
st.set_meta('web:access', json.dumps({'admin': {'any': False, 'from': ['10.0.0.0/8']},
                                      'portal': {'any': False, 'from': ['10.0.0.0/8']},
                                      'health': {'any': False, 'from': ['10.0.0.0/8']}}))
otp.CONFIG.update(acme=True, acme_challenge='http-01')
web = [x for x in otp.fw_auto(st, 'r5') if x['key'] == 'web'][0]['rules']
ok('ACME by HTTP-01, the pages kept to 10/8: port 80 open to the CA, from anywhere',
   any(r['port'] == '80' and r['source'] == '' for r in web) and
   any(r['port'] == '80,443' and r['source'] == '10.0.0.0/8' for r in web))
otp.CONFIG.update(acme=False)
web = [x for x in otp.fw_auto(st, 'r5') if x['key'] == 'web'][0]['rules']
ok('... ACME off: no port 80 from anywhere', not any(r['source'] == '' for r in web))

# ---- moving the other node's address: written once the subscription moved ---------------------
otp.CONFIG.update(ha_mode='replicated', ha_peer='192.0.2.12', ha_address='192.0.2.11', ha_slot=1)
otp.write_file_settings({'ha_peer': '192.0.2.12'})
real = (otp._readdress_hba, st.db.value, otp.sub_connection_set, otp.readdress_tell, otp.hatls_check_soon)
otp._readdress_hba = lambda *a, **k: 'pg_hba.conf changed'
rv = st.db.value
st.db.value = lambda sql, args=(): True if 'subscription' in sql.lower() else rv(sql, args)
calls = []


def sub_set(store, sub, conninfo):
    calls.append(conninfo)
    raise ValueError('x: could not connect to the publisher')


otp.sub_connection_set = sub_set
otp.readdress_tell = lambda *a, **k: ([], [])
otp.hatls_check_soon = lambda: None
try:
    otp.ha_readdress(st, peer='192.0.2.22', by='t', tell=False)
except ValueError:
    pass
ok('the other node\'s address: the subscription not moved - ha_peer kept as it was',
   otp.CONFIG['ha_peer'] == '192.0.2.12' and json.load(open(otp.CONFIG_FILE)).get('ha_peer') == '192.0.2.12')
try:
    otp.ha_readdress(st, peer='192.0.2.22', by='t', tell=False)
except ValueError:
    pass
ok('... asked again, tried again (%d tries)' % len(calls), len(calls) == 2)
otp._readdress_hba, st.db.value, otp.sub_connection_set, otp.readdress_tell, otp.hatls_check_soon = real
otp.CONFIG.update(ha_mode='', ha_peer='', ha_address='')

# ---- names, networks, the long run --------------------------------------------------------------
src = open(V + '/otp.py').read()
ok('ACME: a name under a punycode TLD (.рф = xn--p1ai) taken', '[Xx][Nn]--[A-Za-z0-9-]{1,59}' in src)
otp.net_node_now = lambda store, node: {'data': {'nm': True, 'devices': [{'con': 'eth0', 'dev': 'eth0'}]}}
for addr, gw in (('192.0.2.10/32', ''), ('192.0.2.10/31', '192.0.2.11')):
    try:
        otp.net_check(st, 'r5', {'con': 'eth0', 'ipv4': {'addr': addr, 'gw': gw, 'dns': '192.0.2.53'}})
        took = True
    except ValueError as e:
        took = 'cannot be the address' not in str(e)
        if not took:
            print('    (%s)' % e)
    ok('a network: %s taken as an address of a machine' % addr, took)
try:
    otp.net_check(st, 'r5', {'con': 'eth0', 'ipv4': {'addr': '192.0.2.10/24', 'dns': '2001:db8::53'}})
    v6 = False
except ValueError as e:
    v6 = 'IPv6' in str(e)
ok('... an IPv6 DNS server among the IPv4 ones refused here, not by root later', v6)
otp.NODE_ASK['done'].update('proxy:%d' % i for i in range(2500))
otp.NODE_ASK['do'].setdefault('x-test', lambda *a: None)
try:
    otp._node_ask_run(type('Dm', (), {'store': st})(), 'x-test', {'id': 'new', 'args': {'only': 'elsewhere'}})
except Exception as e:                                   # noqa: BLE001
    print('    (%s)' % e)
ok('the tests asked of the nodes kept to a size (%d)' % len(otp.NODE_ASK['done']), len(otp.NODE_ASK['done']) < 2500)
ok('the SSH gate answers 32 requests at once at most', 'SSHGATE_AT_ONCE = threading.BoundedSemaphore(32)' in src)
ok('ACME: a certificate ordered on one node at a time', "'acme:busy:%s' % t" in src)


# ---- the root helper and the upgrader -----------------------------------------------------------
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


W = load('otp_web_r5', V + '/deploy/otp_web.py')
for words in (('all', 'otp'), ('otp', 'replication'), ('sameuser', 'otp')):
    try:
        W.pgtls_checked({'id': 'abcdef0123', 'do': 'peer', 'port': 5432, 'db': words[0], 'user': words[1], 'peer': '192.0.2.5'})
        refused = False
    except W.Refused as e:
        refused = 'word of pg_hba' in str(e)
    ok('root: pg_hba for "%s %s" refused' % words, refused)
try:
    W.pgtls_checked({'id': 'abcdef0123', 'do': 'peer', 'port': 5432, 'db': 'otp', 'user': 'otp', 'peer': '192.0.2.5'})
    fine = True
except W.Refused as e:
    fine = 'word of pg_hba' not in str(e)
ok('... otp\'s own database and account taken', fine)
H = open(V + '/deploy/otp_web.py').read()
ok('root: a change of sshd that fails half way put back whole', 'said = sshd_apply_files(c, r, drop, now_dropin, paths, before)'
   in H and 'except BaseException:' in H)
ok('root: /etc/hosts lines taken out only for the addresses this machine has', "n['old'] = [o for o in n['old'] if o in have]" in H)
ok('root: a certificate PostgreSQL does not take - ssl and its files as they were', "it is as it was')" in H
   and 'was_conf' in H)
U = load('otp_upgrade_r5', V + '/deploy/otp_upgrade.py')
pkg = '/home/claude/build/out/otp-%s.tar.gz' % VER
if not os.path.exists(pkg):
    pkg = sorted(p for p in (os.path.join('/home/claude/build/out', f) for f in os.listdir('/home/claude/build/out'))
                 if p.endswith('.tar.gz'))[-1]
bad = os.path.join(D, 'extra.tar.gz')
with tarfile.open(pkg) as src_t, tarfile.open(bad, 'w:gz') as out_t:
    top = None
    for m in src_t.getmembers():
        top = top or m.name.split('/')[0]
        out_t.addfile(m, src_t.extractfile(m) if m.isreg() else None)
    extra = tarfile.TarInfo(top + '/deploy/release-keys/extra.pub')
    extra.type = tarfile.DIRTYPE
    extra.mode = 0o755
    out_t.addfile(extra)
r = subprocess.run([sys.executable, '-I', V + '/deploy/otp_upgrade.py', '--inspect', bad], capture_output=True, text=True)
ok('the upgrader: a signed package with a folder added refused', 'no file of it is in' in r.stdout + r.stderr,
   (r.stdout + r.stderr)[-300:])
r = subprocess.run([sys.executable, '-I', V + '/deploy/otp_upgrade.py', '--inspect', pkg], capture_output=True, text=True)
ok('... the package itself taken', '"ok": true' in r.stdout, (r.stdout + r.stderr)[-300:])
print('ALL %d / %d' % (sum(R), len(R)))
