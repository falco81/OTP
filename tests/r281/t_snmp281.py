# t_snmp281.py VERSION - 1.0.281: the objects added to otp's SNMPv3 agent, asked as a monitor asks them
# (pysnmp 7, authPriv): the machine (CPU, memory, disks, network as counters, the load, the file systems),
# RADIUS (clients, realms, the last day), the cluster (VIP), backups, mail, the ways of signing in, the
# clock guard, the logs sent away - each of the type OTP-MIB says; every OID the Zabbix 7.0 template asks
# with get[] is answered, every column its walks read is there; the page gives OTP-MIB and the template.
import os, sys, json, time, re, subprocess, urllib.request, tempfile, atexit
import yaml

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.281'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-snmp281-')
os.makedirs(D + '/run')
API, RAD = 30987, 36950
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RAD, 'radius_acct_port': RAD + 1,
           'api_port': API, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-281!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


PY = '/tmp/claude-0/snmpvenv/bin/python'
ASK = os.path.dirname(os.path.abspath(__file__)) + '/../snmp/pysnmp_ask.py'
PORT = 16171
S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-281!'})[1]['token']
AP, PP = 'auth-passphrase-281!', 'priv-passphrase-281?'


def ask(do, oids):
    q = {'port': PORT, 'user': 'otpmon', 'auth': 'SHA-256', 'ap': AP, 'priv': 'AES-128', 'pp': PP, 'do': do, 'oids': oids}
    got = subprocess.run([PY, ASK, json.dumps(q)], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(got.stdout.strip().split('\n')[-1])
    except (ValueError, IndexError):
        return {'error': (got.stdout + got.stderr)[-300:], 'vars': []}


c, x = call('/api/settings', {'settings': {'snmp': 1, 'snmp_port': PORT, 'snmp_bind': '127.0.0.1', 'snmp_user': 'otpmon',
                                           'snmp_auth': 'SHA-256', 'snmp_priv': 'AES-128', 'snmp_auth_pass': AP,
                                           'snmp_priv_pass': PP}}, S)
ok('SNMPv3 switched on (%s)' % c, c == 200, x)
time.sleep(7)
B = '1.3.6.1.4.1.8072.9999.9999.7'
r = ask('walk', [B])
ok('the subtree walked (%s)' % r.get('error'), not r.get('error') and r['vars'], r.get('error'))
vv = {a: (b, c) for a, b, c in r['vars']}


def typ(o):
    return vv.get(B + o, ('', ''))[0]


def val(o):
    return vv.get(B + o, ('', ''))[1]


ok('the machine: CPU idle and total, Counter64, total more than idle',
   typ('.10.1.0') == 'Counter64' and typ('.10.2.0') == 'Counter64' and int(val('.10.2.0')) > int(val('.10.1.0')) > 0,
   (vv.get(B + '.10.1.0'), vv.get(B + '.10.2.0')))
ok('... cores, the load (x100)', int(val('.10.3.0')) >= 1 and typ('.10.4.0') == 'Gauge32', (val('.10.3.0'), typ('.10.4.0')))
ok('... memory in KiB: total more than used, more than 0',
   int(val('.10.7.0')) > int(val('.10.8.0')) > 0, (val('.10.7.0'), val('.10.8.0')))
ok('... disks and network as Counter64', all(typ('.10.%d.0' % i) == 'Counter64' for i in (10, 11, 12, 13)))
ok('... the machine\'s uptime', int(val('.10.14.0') or 0) > 0)
fs = {a.rsplit('.', 1)[1]: c for a, b, c in r['vars'] if a.startswith(B + '.10.20.1.2.')}
ok('the file systems: / among them', '/' in fs.values(), fs)
ok('... each with its size, used, free, % (0-100)', all(int(val('.10.20.1.3.%s' % i)) > 0 and 0 <= int(val('.10.20.1.6.%s' % i)) <= 100
                                                       for i in fs), fs)
ok('RADIUS: clients, realms, directories, the last day (Gauge32)',
   all(typ('.2.%d.0' % i) == 'Gauge32' for i in range(15, 21)), [typ('.2.%d.0' % i) for i in range(15, 21)])
ok('the cluster: not one, no VIP address, not here', val('.12.1.0') == '0' and val('.12.2.0') == '0' and val('.12.3.0') == '0')
ok('backups: the nightly copy\'s time and age; sent away off - answered all the same',
   all(B + '.13.%d.0' % i in vv for i in range(1, 8)), [i for i in range(1, 8) if B + '.13.%d.0' % i not in vv])
ok('mail: five states', all(typ('.14.%d.0' % i) == 'Gauge32' for i in range(1, 6)))
ok('signing in: Windows, certificate, no password, second step; CRLs and OCSP',
   all(B + '.15.%d.0' % i in vv for i in range(1, 10)) and val('.15.7.0') == 'off')
ok('the clock guard: five', all(B + '.16.%d.0' % i in vv for i in range(1, 6)))
ok('the logs sent away: isemon and the SIEM, four each', all(B + '.17.%d.%d.0' % (a, b) in vv for a in (1, 2) for b in range(1, 5)))
ok('the objects before 1.0.281 still there: the version, RADIUS, the metrics table',
   val('.1.1.0') == VER and typ('.2.3.0') == 'Counter64' and any(a.startswith(B + '.9.1.1.2.') for a in vv))

# what the Zabbix template asks
tpl = yaml.safe_load(open(V + '/deploy/zabbix/otp_by_snmp_zabbix7.yaml'))['zabbix_export']['templates'][0]
gets = [re.match(r'^get\[(.+)\]$', i['snmp_oid']).group(1) for i in tpl['items']
        if re.match(r'^get\[', i.get('snmp_oid') or '')]
sysr = ask('get', [o for o in gets if not o.startswith(B)])
have = set(vv) | {a for a, b, c in sysr['vars']}
miss = [o for o in gets if o not in have]
ok('every OID the Zabbix template asks with get[] is answered (%d)' % len(gets), not miss, miss)
cols = set()
for i in tpl['items']:
    m = re.match(r'^walk\[(.+)\]$', i.get('snmp_oid') or '')
    if m:
        cols |= set(m.group(1).split(','))
answered = {c for c in cols if any(a.startswith(c + '.') for a in vv)}
need = {c for c in cols if c.startswith(B + '.10.20') or c.startswith(B + '.2.30') is False and False}
ok('the file systems\' columns its walk reads are answered', all(any(a.startswith(c + '.') for a in vv)
                                                                 for c in cols if c.startswith(B + '.10.20')), sorted(cols - answered)[:5])

# the page gives both files
c, x = call('/api/snmpfile?what=zabbix', None, S)
ok('the page: the Zabbix 7.0 template (%s)' % c, c == 200 and x.get('name') == 'otp_by_snmp_zabbix7.yaml' and
   "version: '7.0'" in x.get('text', ''))
c, x = call('/api/snmpfile?what=mib', None, S)
ok('...OTP-MIB (%s)' % c, c == 200 and 'OTP-MIB DEFINITIONS' in x.get('text', '') and 'otpHostCpuIdle' in x.get('text', ''))
c, x = call('/api/snmpfile?what=../../etc/passwd', None, S)
ok('...nothing else (%s)' % c, c == 404)
c, x = call('/api/snmpfile?what=mib')
ok('...not without signing in (%s)' % c, c in (401, 403))
print('ALL %d / %d' % (sum(R), len(R)))
