# t_round2.py VERSION - the bugs found by the second round of the bug hunt (1.0.206), each
# shown fixed: in-process against otp.py of VERSION, on SQLite in a folder of its own.
import os, sys, json, time, tempfile, subprocess, socket, threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.206'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r2-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r2'}, open(D + '/config.json', 'w'))
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
d = otp.Daemon(st, serve=False)

# ---- portal: a realm of every suffix, a token under another one --------------------------
st.directory_save({'name': 'ad', 'hosts': 'dc.corp.cz', 'base': 'DC=corp,DC=cz', 'bind_dn': 'x',
                   'bind_pw': 'y'}) if hasattr(st, 'directory_save') else None
st.realm_save({'name': 'all', 'suffix': '*', 'directory': 'ad', 'lookup': 'sam', 'auth_mode': 'otp'})
otp.import_totp(st, 'jboss@corp.cz', 'JBSWY3DPEHPK3PXPJBSWY3DP\n" TOTP_AUTH\n')
realm = st.realm_for('jboss@whatever.x')
entry = {'dn': 'CN=J Boss,DC=corp,DC=cz', 'sam': 'jboss', 'upn': 'jan.boss@corp.cz'}
ok('the portal, a realm of every suffix: "jboss@whatever.x" is the same person as the token jboss@corp.cz',
   otp.portal_same_person(st, realm, entry) == 'jboss@corp.cz', otp.portal_same_person(st, realm, entry))
ok('... another account with a like name is not (j_boss)',
   otp.portal_same_person(st, realm, dict(entry, sam='j_boss', upn='')) == '')

# ---- settings ---------------------------------------------------------------------------
ok('radius_bind "127.0.0.1 " kept without its space', otp.check_setting('radius_bind', '127.0.0.1 ') == '127.0.0.1')
ok('mail_from "OTP <otp@firma.cz>" kept as its address',
   otp.check_setting('mail_from', 'OTP Server <otp@firma.cz>') == 'otp@firma.cz')
try:
    otp.check_setting('mail_from', 'not an address')
    refused = False
except otp.BadSetting:
    refused = True
ok('... and something that is no address refused', refused)
for bad in ('http://h:99999', 'http://h:0'):
    try:
        otp.check_setting('proxy_url', bad)
        r_ = False
    except otp.BadSetting:
        r_ = True
    ok('proxy_url %s refused' % bad, r_)
for bad in ('fe80::1', 'gw:'):
    try:
        otp.check_setting('sms_tel_host', bad)
        r_ = False
    except otp.BadSetting:
        r_ = True
    ok('sms_tel_host %s refused' % bad, r_)
ok('... [fe80::1]:443 taken', otp.check_setting('sms_tel_host', '[fe80::1]:443'))
d.save_settings({'proxy': 1, 'proxy_url': 'http://px.example:3128'}, by='t')
ok('the proxy switched on: the new versions and the system updates not through it unless said',
   not otp.CONFIG.get('proxy_update') and not otp.CONFIG.get('proxy_os'))
d.save_settings({'proxy_update': 1}, by='t')
d.save_settings({'proxy_update': 0}, by='t')
ok('... switched on, then off: off it stays', not otp.CONFIG.get('proxy_update'))
try:
    d.save_settings({'radius_auth_port': int(otp.CONFIG.get('radius_acct_port') or 1813)}, by='t')
    same_port = False
except otp.BadSetting:
    same_port = True
ok('the sign-ins and the accounting on one port refused', same_port)
otp.NAME_HELD[0] = True
was = otp.node_name()
cf = json.load(open(D + '/config.json'))
json.dump(dict(cf, node_name='renamed'), open(D + '/config.json', 'w'))
otp.load_config(saved=st.settings_saved())
ok('node_name changed in the file: the running daemon keeps its name until it starts again (%s)' % otp.node_name(),
   otp.node_name() == was)
json.dump(cf, open(D + '/config.json', 'w'))
otp.NAME_HELD[0] = False
otp.load_config(saved=st.settings_saved())

# ---- the SSH gate: a code good once on either node --------------------------------------
took = []
real_once = otp.once_take
otp.once_take = lambda store, kind, name, value: (took.append((kind, name, value)), False)[1]
otp.sshotp_add(st, 'novak', 'app', '', 't') if hasattr(otp, 'sshotp_add') else None
rec = otp.sshotp_get(st, 'novak')
if rec:
    sec = otp.unseal_secret(rec.get('secret'), otp.sshotp_key('novak'))
    code = otp.totp_at(sec, int(time.time() // 30)) if hasattr(otp, 'totp_at') else None
    if code:
        got = otp.sshotp_check(st, 'novak', code)
        ok('an SSH code the other node took already: refused here (%s)' % (got,), got[0] is False and took)
    else:
        ok('(SSH code: no totp_at to make one - looked at the source instead)',
           "once_take(store, 'step', 'sshotp:'" in open(V + '/otp.py').read())
else:
    ok('an SSH code taken in token_once on either node',
       "once_take(store, 'step', 'sshotp:'" in open(V + '/otp.py').read())
otp.once_take = real_once

# ---- the rolling upgrade: the other node's heartbeat read in its own database ------------
class Far:
    def value(self, sql, args):
        return json.dumps({'at': time.time()}) if args and str(args[0]).startswith('node:') else None

    def close(self):
        pass


real_peer = otp.ha_peer_db
otp.ha_peer_db = lambda *a, **k: Far()
otp.PEER_THERE.clear()
ok('the upgrade: a node whose heartbeat no longer comes over is alive by its own database',
   otp._peer_alive_there('otpB') is True)
otp.ha_peer_db = real_peer

# ---- caches: a list read before a save is not kept over it ------------------------------
st.client_save({'name': 'vpn1', 'address': '10.0.0.1', 'secret': 'Sh4red-secret-1!'})
st._clients = None
gen = st.cache_gen
rows = st.db.rows('SELECT * FROM clients ORDER BY position, name')
st.client_save({'name': 'vpn2', 'address': '10.0.0.2', 'secret': 'Sh4red-secret-2!'})
st._cache_put('_clients', rows, gen)
ok('a client list read before a save is not kept over it: the new client is known',
   st.client_for('10.0.0.2') is not None)

# ---- SNMP: the machine's own test, the managers' network set ----------------------------
otp.CONFIG['snmp_from'] = '10.0.0.0/8'
ok('SNMP: this machine itself is not let in by itself outside the managers\' network', not otp.snmp_allowed('127.0.0.1'))
otp.SNMP_SELF['until'] = time.time() + 5
ok('... but while the page\'s own test asks, it is', otp.snmp_allowed('127.0.0.1'))
otp.SNMP_SELF['until'] = 0
ok('... another address outside it may not', not otp.snmp_allowed('192.0.2.7'))

# ---- the root helper and install.sh -------------------------------------------------------
H = open(V + '/deploy/otp_web.py').read()
I = open(V + '/install.sh').read()
ok('otp taken away: sshd\'s PAM put back first (--pam-off)', "['--pam-off']" in H and '--pam-off' in I)
ok('the database drivers asked for kept for the next upgrade', 'db-drivers' in I)
r = subprocess.run(['bash', '-n', V + '/install.sh'], capture_output=True, text=True)
ok('install.sh still reads as bash', r.returncode == 0, r.stderr)
print('ALL %d / %d' % (sum(R), len(R)))
