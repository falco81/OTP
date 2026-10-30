# High security (1.0.168): switched on only with nothing against it, what
# stands against it listed; while on, every less safe value refused wherever
# it is changed; what is only advised stops nothing.
# Usage (as root): python3 t_hisec.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.168'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-hs-'); os.makedirs(D + '/run')
APORT = 30391
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36010, 'radius_acct_port': 36011,
           'api_port': APORT, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-168!', must_change=0)
st.directory_save({'name': 'AD', 'hosts': 'dc1.example.cz', 'tls': 'none', 'port': 389, 'base': 'DC=example,DC=cz',
                   'bind_dn': 'otp@example.cz', 'bind_pw': 'x'})
st.client_save({'name': 'vpn', 'address': '10.0.0.1', 'secret': 'short-secret', 'enabled': 1})
st.set_meta('host:sshd:now:otp1', json.dumps({'values': {'passwordauthentication': 'yes', 'permitrootlogin': 'prohibit-password',
                                                       'maxauthtries': '6'}}))
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-168!'})[1]['token']
SET = lambda dd: call('/api/settings', {'settings': dd}, S)
c, v = call('/api/hisec', None, S)
panes = sorted(set(x['pane'] for x in v.get('block', [])))
ok('what stands against it, listed with where: %s' % panes, c == 200 and {'dir', 'clients', 'guard', 'fw', 'sshd'} <= set(panes))
ok('... every rule listed, the second step of the administration among what stands against it (%d rules)' % len(v.get('rules', [])),
   any(x['key'] == 'admin_2fa' for x in v['block']) and len(v['rules']) > 40 and all(x['kind'] == 'check' for x in v['warn']))
WV = lambda rule, on: call('/api/hisec', {'action': 'waive', 'rule': rule, 'on': on}, S)
c, x = WV('admin_2fa', True)
ok('an exception made: the second step (%s)' % c, c == 200 and any(r['rule'] == 'admin_2fa' for r in x['waived'])
   and not any(r['key'] == 'admin_2fa' for r in x['block']))
c, x = WV('no-such-rule', True)
ok('... not for a rule there is not (%s)' % c, c == 400)
v = call('/api/hisec', None, S)[1]
c, x = SET({'high_security': 1})
ok('switching it on refused, the list with it (%s, %d)' % (c, len(((x.get('detail') or {}).get('hisec') or {}).get('block', []))),
   c == 409 and len(x['detail']['hisec']['block']) == len(v['block']))
ok('... still off', not call('/api/status', None, S)[1].get('high_security'))
# Put right, one by one.
dr = [x for x in call('/api/directories', None, S)[1].get('directories', [])][0]
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='ldaps', port=636, bind_pw='********')}, S)
ok('the directory over LDAPS: %s %s' % (c, x.get('error', '')), c == 200)
cl = call('/api/clients', None, S)[1]['clients'][0]
c, x = call('/api/clients', {'action': 'save', 'client': dict(cl, secret='a-long-shared-secret-168')}, S)
ok('the client\'s secret long enough: %s %s' % (c, x.get('error', '')), c == 200)
c, x = SET({'radius_guard': 1, 'admin_show_key': 0, 'portal_show_secret': 0, 'scratch_digits': 10,
            'session_hours': 8, 'session_idle_min': 30})
st.set_meta('web:access', json.dumps({'admin': {'any': False, 'from': ['10.0.0.0/8']}, 'portal': {'any': True, 'from': []},
                                     'health': {'any': True, 'from': []}}))
st.set_meta('host:sshd:now:otp1', json.dumps({'values': {'passwordauthentication': 'no', 'permitrootlogin': 'prohibit-password',
                                                       'maxauthtries': '3'}}))
c, v = call('/api/hisec', None, S)
ok('put right: nothing against it (%s)' % [x['what'] for x in v['block']], not v['block'])
c, x = SET({'high_security': 1})
ok('switched on now: %s %s' % (c, x.get('error', '')), c == 200)
time.sleep(1.5)
ok('... the page is told', call('/api/status', None, S)[1].get('high_security') is True)
# While it is on.
for what, dd in (('RADIUS without the guard', {'radius_guard': 0}),
                 ('answers without a Message-Authenticator', {'radius_reply_ma': 0}),
                 ('SMTP unencrypted', {'mail_mode': 'smtp', 'smtp_host': 'mail.example.cz', 'smtp_security': 'none'}),
                 ('SMTP without checking the certificate', {'mail_mode': 'smtp', 'smtp_host': 'mail.example.cz', 'smtp_verify': 0}),
                 ('syslog over TCP', {'siem': 1, 'siem_targets': 'tcp://10.0.0.5:514'}),
                 ('isemon plain', {'isemon': 1, 'isemon_targets': '10.0.0.6:514/tcp'}),
                 ('isemon over TLS not checked', {'isemon': 1, 'isemon_targets': 'isemon.example.cz:6514/tls', 'isemon_verify': 0}),
                 ('a wide window of codes', {'totp_window': 3}),
                 ('a code used again', {'totp_disallow_reuse': 0}), ('debug', {'debug': 1})):
    c, x = SET(dd)
    ok('refused: %s (%s: %s)' % (what, c, x.get('error', '')[:90]), c == 400 and 'high security' in x.get('error', ''))
c, x = SET({'siem': 1, 'siem_targets': 'tls://siem.example.cz:6514'})
ok('syslog over TLS: allowed (%s)' % c, c == 200)
c, x = SET({'isemon': 1, 'isemon_targets': 'isemon.example.cz:6514/tls'})
ok('isemon over TLS: allowed (1.0.172) (%s %s)' % (c, x.get('error', '')[:60]), c == 200)
SET({'isemon': 0})
c, x = SET({'session_hours': 12})
ok('a sign-in of 12 hours refused (%s)' % c, c == 400)
c, x = SET({'mail_mode': 'direct', 'mail_direct_tls': 'if-offered', 'mail_codes': 0})
ok('direct mail with TLS only where offered: refused (%s %s)' % (c, x.get('error', '')[:60]), c == 400 and 'Encryption' in x.get('error', '') or 'TLS' in x.get('error', ''))
WV('mail_direct_tls', True)
c, x = SET({'mail_mode': 'direct', 'mail_direct_tls': 'if-offered', 'mail_codes': 0})
ok('... allowed as an exception (%s %s)' % (c, x.get('error', '')), c == 200)
c, x = WV('mail_direct_tls', False)
ok('... the exception not taken back while it is not kept (%s)' % c, c == 400)
SET({'mail_mode': 'off'})
c, x = WV('mail_direct_tls', False)
ok('... and taken back once it is (%s)' % c, c == 200)
c, x = SET({'admin_2fa': 0})
ok('the second step off: allowed, it is an exception (%s)' % c, c == 200)
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='none', port=389, bind_pw='********')}, S)
ok('a directory over plain LDAP refused (%s %s)' % (c, x.get('error', '')[:80]), c == 400)
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='ldaps', port=636, verify=0, bind_pw='********')}, S)
ok('... nor without checking its certificate (%s %s)' % (c, x.get('error','')[:60]), c == 400 and 'high security' in x.get('error',''))
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='starttls', port=389, weak=1, bind_pw='********')}, S)
ok('... nor with weak TLS (%s %s)' % (c, x.get('error','')[:60]), c == 400 and 'high security' in x.get('error',''))
c, x = call('/api/clients', {'action': 'save', 'client': dict(cl, secret='short')}, S)
ok('a short client secret refused (%s %s)' % (c, x.get('error','')[:60]), c == 400 and 'high security' in x.get('error',''))
c, x = call('/api/rbackup', {'action': 'save', 'target': {'kind': 'ftp', 'host': 'ftp.example.cz', 'user': 'b', 'password': 'p', 'path': '/x'}}, S)
ok('a plain FTP destination refused (%s %s)' % (c, x.get('error', '')[:70]), c == 400)
c, x = call('/api/sshd', {'action': 'save', 'conf': {'manage': True, 'password': True, 'permit_root': 'prohibit-password', 'port': 22, 'tries': 3}}, S)
ok('SSH with passwords refused (%s %s)' % (c, x.get('error','')[:60]), c == 400 and 'high security' in x.get('error',''))
c, x = call('/api/sshd', {'action': 'save', 'conf': {'manage': True, 'password': False, 'permit_root': 'prohibit-password', 'port': 22, 'tries': 6}}, S)
ok('... more than 4 SSH tries refused (%s %s)' % (c, x.get('error','')[:60]), c == 400 and 'high security' in x.get('error',''))
c, x = call('/api/tokens/backup', {'lock': False}, S)
ok('a backup not locked refused (%s)' % c, c == 403)
WV('export:unlocked', True)
WV('admin_show_key', True)
SET({'admin_show_key': 1})
c, x = call('/api/tokens/backup', {'lock': False}, S)
ok('... allowed once it is an exception (%s)' % c, c == 200)
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='starttls', port=389, weak=1, bind_pw='********')}, S)
WV('dir:weak', True)
c, x = call('/api/directories', {'action': 'save', 'directory': dict(dr, tls='starttls', port=389, weak=1, bind_pw='********')}, S)
ok('weak TLS to a directory allowed as an exception (%s %s)' % (c, x.get('error', '')), c == 200)
c, x = call('/api/settings', None, S)
hs = {s_['key']: s_.get('hisec') for s_ in x.get('settings', [])}
ok('the pages are told what to grey out: %s' % hs.get('smtp_security'), (hs.get('smtp_security') or {}).get('forbid') == ['none', 'starttls-if']
   and (hs.get('totp_window') or {}).get('most') == 1)
c, x = SET({'high_security': 0})
ok('switched off freely (%s)' % c, c == 200)
c, x = SET({'radius_guard': 0})
ok('... and then the guard may go off again (%s)' % c, c == 200)
ev = json.dumps(call('/api/events?limit=80', None, S)[1])
ok('switching on and off is in the events', 'high_security' in ev)
print('ALL %d / %d' % (sum(R), len(R)))
