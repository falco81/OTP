# a 1.0.281 otp daemon with its SNMPv3 agent on 127.0.0.1:16181, for Zabbix to poll (own state, SQLite)
import os, sys, json, time, subprocess, urllib.request
D = '/home/claude/p281/agentstate'
os.makedirs(D + '/run', exist_ok=True)
API = 30977
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36930, 'radius_acct_port': 36931,
           'api_port': API, 'node_name': 'otp1', 'site_name': 'otp test'}, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, '/home/claude/p281/agent'); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
if not st.account('local'):
    st.add_account('local', 'fulladmin', 'Local-Admin-Pass-281!', must_change=0)
p = subprocess.Popen([sys.executable, '/home/claude/p281/agent/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'a'),
                     stderr=subprocess.STDOUT, start_new_session=True)
open(D + '/pid', 'w').write(str(p.pid))
time.sleep(7)
TOK = open(D + '/run/api-token').read().strip()
def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess: h['X-Otp-Session'] = sess
    r = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d%s' % (API, path),
        data=json.dumps(body).encode() if body is not None else None, headers=h, method='POST' if body is not None else 'GET'), timeout=60)
    return json.loads(r.read())
S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-281!'})['token']
print(call('/api/settings', {'settings': {'snmp': 1, 'snmp_port': 16181, 'snmp_bind': '127.0.0.1', 'snmp_user': 'otpmon',
       'snmp_auth': 'SHA-256', 'snmp_priv': 'AES-128', 'snmp_auth_pass': 'auth-passphrase-281!', 'snmp_priv_pass': 'priv-passphrase-281?',
       'snmp_location': 'Server room 2', 'snmp_contact': 'noc@example.cz', 'backup_daily': 1}}, S).get('message'))
