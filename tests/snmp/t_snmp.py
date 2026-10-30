# SNMPv3 (1.0.182): one daemon with its agent on 127.0.0.1; a manager that is not
# otp's (pysnmp 7, /tmp/claude-0/snmpvenv) asks it - discovery, GET, GETNEXT walk,
# GETBULK, every authentication with every encryption, a wrong passphrase, a wrong
# user, noAuthNoPriv, a network not let in; the node's own test; a trap received
# by pysnmp with the node's engine ID, and the alerts' traps (raised, cleared).
# Usage (as root): python3 t_snmp.py VERSION
import os, sys, json, time, re, subprocess, urllib.request, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.182'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-snmp-')
os.makedirs(D + '/run')
API, RAD = 30997, 36960
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
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-173!', must_change=0)
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def call(path, body=None, sess=None, extra=None, client='127.0.0.1'):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': client}
    if sess:
        h['X-Otp-Session'] = sess
    h.update(extra or {})
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (API, path), data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


PY = '/tmp/claude-0/snmpvenv/bin/python'
HERE = os.path.dirname(os.path.abspath(__file__))
PORT, TRAP = 16161, 16162
S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-173!'})[1]['token']
AP, PP = 'auth-passphrase-182!', 'priv-passphrase-182?'


def ask(do, oids, auth='SHA-256', priv='AES-128', user='otpmon', ap=AP, pp=PP):
    q = {'port': PORT, 'user': user, 'auth': auth, 'ap': ap, 'priv': priv, 'pp': pp, 'do': do, 'oids': oids}
    got = subprocess.run([PY, HERE + '/pysnmp_ask.py', json.dumps(q)], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(got.stdout.strip().split('\n')[-1])
    except (ValueError, IndexError):
        return {'error': (got.stdout + got.stderr)[-300:], 'vars': []}


def setting(**kw):
    c, x = call('/api/settings', {'settings': kw}, S)
    time.sleep(6.5)                      # the agent reads its settings every 5 s
    return c, x


c, x = call('/api/settings', {'settings': {'snmp': 1, 'snmp_port': PORT, 'snmp_bind': '127.0.0.1', 'snmp_user': 'otpmon',
                                           'snmp_auth_pass': 'short'}}, S)
ok('a passphrase shorter than 12: refused (%s)' % c, c == 400)
c, x = setting(snmp=1, snmp_port=PORT, snmp_bind='127.0.0.1', snmp_user='otpmon', snmp_auth='SHA-256', snmp_priv='AES-128',
               snmp_auth_pass=AP, snmp_priv_pass=PP, snmp_location='Server room 2', snmp_contact='noc@example.cz')
ok('switched on (%s)' % c, c == 200, x)
saved = json.dumps(st.db.rows('SELECT * FROM settings'))
ok('... the passphrases kept sealed', AP not in saved and PP not in saved)
r = ask('get', ['1.3.6.1.2.1.1.1.0', '1.3.6.1.2.1.1.5.0', '1.3.6.1.2.1.1.6.0', '1.3.6.1.2.1.1.3.0'])
v = {a: c for a, b, c in r['vars']}
ok('pysnmp: discovery, then GET authPriv SHA-256/AES-128 (%s)' % r.get('error'), not r['error'] and 'otp %s' % VER in v.get('1.3.6.1.2.1.1.1.0', ''), r)
ok('... sysLocation as set', v.get('1.3.6.1.2.1.1.6.0') == 'Server room 2', v)
ok('... sysUpTime ticks', int(v.get('1.3.6.1.2.1.1.3.0', '0') or 0) > 0, v)
r = ask('walk', ['1.3.6.1.4.1.8072.9999.9999.7'])
names = {a for a, b, c in r['vars']}
ok('GETNEXT walk of otp\'s subtree: %d objects (%s)' % (len(names), r.get('error')), not r['error'] and len(names) > 60, r.get('error'))
vv = {a: (b, c) for a, b, c in r['vars']}
ok('... the version', vv.get('1.3.6.1.4.1.8072.9999.9999.7.1.1.0', ('', ''))[1] == VER, vv.get('1.3.6.1.4.1.8072.9999.9999.7.1.1.0'))
ok('... RADIUS packets a Counter64', vv.get('1.3.6.1.4.1.8072.9999.9999.7.2.3.0', ('',))[0] == 'Counter64', vv.get('1.3.6.1.4.1.8072.9999.9999.7.2.3.0'))
ok('... the database up', vv.get('1.3.6.1.4.1.8072.9999.9999.7.3.1.0', ('', ''))[1] == '1')
ok('... the table of every Prometheus sample', any(a.startswith('1.3.6.1.4.1.8072.9999.9999.7.9.1.1.2.') and c == 'otp_info' for a, b, c in r['vars']))
r2 = ask('bulk', ['1.3.6.1.4.1.8072.9999.9999.7'])
ok('GETBULK walk: the same objects (%d / %d)' % (len(r2['vars']), len(r['vars'])), not r2['error'] and
   [a for a, b, c in r2['vars']] == [a for a, b, c in r['vars']], r2.get('error'))
r = ask('walk', ['1.3.6.1.2.1.1'])
ok('the system group walked: 7 objects', len(r['vars']) == 7, r)
r = ask('get', ['1.3.6.1.2.1.1.1.0'], ap='wrong-passphrase-xx')
ok('a wrong authentication passphrase: no answer (%s)' % (r['error'] or '')[:60], r['error'])
r = ask('get', ['1.3.6.1.2.1.1.1.0'], pp='wrong-privacy-pass-x')
ok('a wrong encryption passphrase: no answer', r['error'] or not r['vars'] or 'otp' not in str(r['vars']), r)
r = ask('get', ['1.3.6.1.2.1.1.1.0'], user='nobody')
ok('an unknown user: no answer (%s)' % (r['error'] or '')[:60], r['error'])
r = ask('get', ['1.3.6.1.2.1.1.1.0'], priv='none')
ok('authNoPriv: not answered - authPriv only (%s)' % (r['error'] or '')[:60], r['error'])
for auth, priv in (('SHA-512', 'AES-256'), ('SHA-1', 'AES-256'), ('SHA-1', 'AES-128'), ('SHA-512', 'AES-128')):
    setting(snmp_auth=auth, snmp_priv=priv)
    r = ask('get', ['1.3.6.1.2.1.1.5.0'], auth=auth, priv=priv)
    ok('pysnmp %s / %s (%s)' % (auth, priv, r.get('error')), not r['error'] and r['vars'], r)
setting(snmp_auth='SHA-256', snmp_priv='AES-128')
# The node's own test, as the page asks it.
c, x = call('/api/snmp', {'action': 'test'}, S)
got = {}
for _ in range(20):
    time.sleep(0.5)
    got = (call('/api/snmp', {'action': 'result', 'id': x.get('id')}, S)[1].get('nodes') or {}).get('otp1')
    if got:
        break
ok('the node\'s own test: asked itself (%s)' % (got or {}).get('error'), (got or {}).get('ok') and 'otp' in json.dumps(got.get('said')), got)
ENG = (got or {}).get('engine') or ''
# A trap, received by pysnmp knowing the user with this node's engine ID.
rx = subprocess.Popen([PY, HERE + '/pysnmp_traps.py', str(TRAP), 'otpmon', 'SHA-256', AP, 'AES-128', PP, ENG, '40'],
                      stdout=open(D + '/rx.out', 'w'), stderr=subprocess.STDOUT, text=True)
for _ in range(50):
    time.sleep(0.2)
    if 'ready' in open(D + '/rx.out').read():
        break
setting(snmp_traps=1, snmp_trap_to='127.0.0.1:%d' % TRAP)
c, x = call('/api/snmp', {'action': 'trap'}, S)
tg = {}
for _ in range(20):
    time.sleep(0.5)
    tg = (call('/api/snmp', {'action': 'result', 'id': x.get('id')}, S)[1].get('nodes') or {}).get('otp1')
    if tg:
        break
ok('the test trap: sent to the receiver (%s)' % (tg or {}).get('error'), (tg or {}).get('ok'), tg)

# Something wrong: RADIUS not listening is not to be made here - an alert of the
# security check is; the alerts' tick gives the trap.
otp.CONFIG['snmp'] = 1
st.set_meta('snmp:trapped', json.dumps({}))
call('/api/settings', {'settings': {'alerts_delay_min': 0}}, S)
c, v = call('/api/snmp', None, S)
ok('the page: on, ready, its port, the receivers', v.get('on') and v.get('ready') and v.get('port') == PORT and v.get('trap_to'), v)
time.sleep(2)
rx.terminate()
rx.wait(20)
out_rx = open(D + '/rx.out').read()
lines = [l for l in out_rx.split('\n') if l.startswith('[')]
traps = [json.loads(l) for l in lines]
ok('pysnmp took the test trap, authPriv, by the engine ID (%d)' % len(traps), any(
   any('1.3.6.1.4.1.8072.9999.9999.7.0.3' in v for o, v in t) for t in traps), out_rx[-600:])
ok('... with the words', any(any('a test trap from otp' in v for o, v in t) for t in traps))
# The alerts' traps: something wrong (a trap), still wrong (none), right again (a trap).
FE = '80001f8805aabbccddeeff001122334455'
open(D + '/rx2.out', 'w').close()
rx = subprocess.Popen([PY, HERE + '/pysnmp_traps.py', str(TRAP + 2), 'otpmon', 'SHA-256', AP, 'AES-128', PP, FE, '30'],
                      stdout=open(D + '/rx2.out', 'w'), stderr=subprocess.STDOUT, text=True)
for _ in range(50):
    time.sleep(0.2)
    if 'ready' in open(D + '/rx2.out').read():
        break
otp.load_config(saved=st.settings_saved())
otp.CONFIG.update(snmp_trap_to='127.0.0.1:%d' % (TRAP + 2), alerts_delay_min=0)
fa = otp.SnmpAgent.__new__(otp.SnmpAgent)
fa.engine, fa.boots, fa.started, fa.keys, fa.salt = bytes.fromhex(FE), 1, time.time() - 50, None, 7


class FD(object):
    pass


fd = FD()
fd.snmp, fd.store = fa, st
st.set_meta('snmp:trapped', '{}')
prob = {'disk:/var': {'level': 'bad', 'title': 'The disk /var is 97 % full', 'said': 'otp1: 97 %'}}
otp.snmp_traps_tick(fd, prob)
otp.snmp_traps_tick(fd, prob)
otp.snmp_traps_tick(fd, {})
time.sleep(2)
rx.terminate()
rx.wait(20)
tr = [json.loads(l) for l in open(D + '/rx2.out').read().split('\n') if l.startswith('[')]
kinds = [dict(t).get('1.3.6.1.6.3.1.1.4.1.0') for t in tr]
ok('the alerts: one trap raised, none for still, one cleared (%s)' % kinds, kinds == [
   '1.3.6.1.4.1.8072.9999.9999.7.0.1', '1.3.6.1.4.1.8072.9999.9999.7.0.2'], tr)
ok('... the raised one says what and how bad', tr and any('97 % full' in v for o, v in tr[0]) and any(v == 'bad' for o, v in tr[0]))
otp.load_config(saved=st.settings_saved())
fw = [i for i in otp.fw_auto(st, 'otp1') if i['key'] == 'snmp']
ok('the firewall: SNMPv3 from everywhere while no network is set', fw and fw[0]['on'] and
   sorted((r['family'], r['proto'], r['port'], r['source']) for r in fw[0]['rules']) == [(4, 'udp', str(PORT), ''), (6, 'udp', str(PORT), '')], fw)
c, x = setting(snmp_from='10.9.9.0/24')
otp.load_config(saved=st.settings_saved())
fw = [i for i in otp.fw_auto(st, 'otp1') if i['key'] == 'snmp']
ok('... from the networks set only', fw and [(r['proto'], r['port'], r['source']) for r in fw[0]['rules']] == [('udp', str(PORT), '10.9.9.0/24')], fw)
r = ask('get', ['1.3.6.1.2.1.1.1.0'])
ok('from a network not let in: no answer', r['error'])
setting(snmp_from='')
c, x = setting(snmp=0)
otp.load_config(saved=st.settings_saved())
ok('off: no rule in the firewall', not [i for i in otp.fw_auto(st, 'otp1') if i['key'] == 'snmp'])
ev = json.dumps(call('/api/events?limit=30', None, S)[1])
print('ALL %d / %d' % (sum(R), len(R)))
