# t_round1.py VERSION - the bugs found by the first round of the bug hunt (1.0.205), each
# shown fixed: run in-process against otp.py of VERSION, on SQLite in a folder of its own.
import os, sys, json, time, tempfile, subprocess, re, threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.205'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r1-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r1'}, open(D + '/config.json', 'w'))
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

# ---- B3: SQLite LOWER() over every letter ----------------------------------------------
otp.CONFIG['names_any_letters'] = True
st.add_account('Žofie', 'readonly', None, source='directory')
ok('an account "Žofie" found again by its name on SQLite', st.account('Žofie') is not None)
ok('... and as "žofie"', st.account('žofie') is not None)

# ---- B2: no new key while tokens are sealed with the lost one --------------------------
otp.import_totp(st, 'alice', 'JBSWY3DPEHPK3PXPJBSWY3DP\n" TOTP_AUTH\n')
p = otp.sealing_key_path()
kept = p.read_text()
p.unlink()
otp._KEY_CACHE.clear()
try:
    st.client_save({'name': 'vpn', 'address': '10.0.0.1', 'secret': 'Sh4red-secret-xyz!'})
    refused = False
except Exception as e:                                  # noqa: BLE001
    refused = 'missing' in str(e) or 'key' in str(e)
ok('the key lost, tokens sealed with it: a client saved makes no new key - refused',
   refused and not p.exists())
p.write_text(kept)
otp._KEY_CACHE.clear()
ok('... the key put back: alice opens again',
   otp.unseal_secret(st.token('alice')['secret'], otp.token_bind('alice')) is not None)

# ---- B1: the other node asked whatever its heartbeat says --------------------------------
otp.CONFIG.update(ha_mode='replicated', ha_slot=1, ha_peer='192.0.2.50')
asked = []


class FakePeer:
    def value(self, sql, args):
        asked.append(args)
        return 1                                    # the other node used it already

    def close(self):
        pass


real_open = otp.db_open
otp.db_open = lambda *a, **k: FakePeer()
otp.once_peer_forget()
st.set_meta('node:r2', json.dumps({'at': time.time() - 600}))      # its heartbeat long stale
ok('replication from the other node stopped: a recovery code it used is refused here',
   otp.once_take(st, 'scratch', 'alice', 'h1') is False and asked)
otp.db_open = real_open
otp.CONFIG.update(ha_mode='standalone', ha_peer='')

# ---- A3: no place known - only the day's limit counts --------------------------------
for _ in range(25):
    otp.scratch_guard_note(st, 'novak@corp.cz', '')
ok('no Calling-Station-Id: 25 wrong tries do not stop the owner\'s recovery codes (the day\'s 100 does)',
   not otp.scratch_guarded(st, 'novak@corp.cz', ''))
for _ in range(20):
    otp.scratch_guard_note(st, 'dvorak@corp.cz', '198.51.100.7')
ok('... from one place known: 20 stop them from it', otp.scratch_guarded(st, 'dvorak@corp.cz', '198.51.100.7'))

# ---- A4: a group's DN with spaces -----------------------------------------------------
have = [('CN=VPN Users,OU=Groups,DC=corp,DC=cz', 'VPN Users')]
ok('a group DN typed with spaces after its commas matches',
   otp.group_matches([{'group': 'CN=VPN Users, OU=Groups, DC=corp, DC=cz'}], have) is not None)
ok('... another group does not', otp.group_matches([{'group': 'CN=Admins, OU=Groups, DC=corp, DC=cz'}], have) is None)


# ---- A1: the directory not answering for a group's name is not "not a member" -------
class SlowAd:
    name = 'corp'

    def group_dns(self, n):
        raise otp.LdapUnreachable('corp is answering slowly')


try:
    otp.group_matches([{'group': 'VPN Users'}], have, SlowAd())
    raised = False
except otp.LdapUnreachable:
    raised = True
ok('a group\'s name not looked up (the directory slow): said so, not "not in the group"', raised)

# ---- A5: totp_window 0 for the second step of the pages -------------------------------
otp.CONFIG['totp_window'] = 0
ok('totp_window 0 is 0 for the administration\'s second step', otp.mfa_window() == 0)
otp.CONFIG['totp_window'] = None
ok('... not set: 1', otp.mfa_window() == 1)

# ---- E4: an alert going between warn and bad mailed once ------------------------------
sent = []
otp.CONFIG.update(alerts=1, alerts_to='a@example.cz', alerts_delay_min=0, alerts_repeat_h=24,
                  mail_from='otp@example.cz')
real_send, real_probs = otp.alert_send, otp.alert_problems
otp.alert_send = lambda store, msg, to, kind, keys: (sent.append(keys), {'ok': True})[1]
lv = ['warn', 'bad', 'warn', 'bad', 'warn', 'bad']
for level in lv:
    otp.alert_problems = lambda store, lang='en', level=level: {
        'disk:/': {'level': level, 'node': 'r1', 'title': 'disk /', 'said': '95 %', 'pane': 'logs'}}
    try:
        otp.alerts_evaluate(st, force=True)
    except Exception as e:                              # noqa: BLE001
        print('    (alerts: %s)' % e)
otp.alert_send, otp.alert_problems = real_send, real_probs
ok('a disk going between warn and bad: mailed twice (said, then worse), not at every turn (%d)' % len(sent),
   1 <= len(sent) <= 2, sent)

# ---- E5: openssl's passphrase on a pipe of its own --------------------------------------
k = subprocess.run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-aes256',
                    '-pass', 'pass:Heslo-123 x'], capture_output=True).stdout.decode()
ok('a locked key opened with its passphrase on a pipe', 'BEGIN PRIVATE KEY' in otp.key_plain(k, 'Heslo-123 x'))
src = open(V + '/otp.py').read()
ok('no passphrase handed to openssl in the environment any more', 'env:OTP_' not in src)

# ---- E9: a name longer than a CN may be -------------------------------------------------
long_ = 'a' * 40 + '.' + 'b' * 30 + '.example.cz'
key, csr = otp.make_csr(long_, [], 'ec')
txt = subprocess.run(['openssl', 'req', '-noout', '-text'], input=csr.encode(), capture_output=True).stdout.decode()
ok('a %d-character name: its request made, the name in the SAN' % len(long_), 'DNS:' + long_ in txt)

# ---- F2: no secret on the command line, @env… or not ------------------------------------
r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--add-client', 'x', '--address', '10.0.0.9',
                    '--secret', '@envMyRealSecret123'], capture_output=True, text=True,
                   env=dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_STAY_ROOT='1'))
ok('--secret @envSomething refused as a secret on the command line', r.returncode != 0 and 'command line' in r.stderr,
   r.stderr[-300:])
# ---- F1: - read from stdin with no terminal --------------------------------------------
r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--add-client', 'pipe', '--address', '10.0.0.8',
                    '--secret', '-'], input='Piped-Secret-123\n', capture_output=True, text=True,
                   env=dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_STAY_ROOT='1'),
                   start_new_session=True)
ok('--secret - with no terminal: one line of stdin, no traceback (%d)' % r.returncode,
   r.returncode == 0 and 'Traceback' not in r.stderr, r.stderr[-300:])

# ---- D2/D3/D4/D1: the root helper ----------------------------------------------------------
H = open(V + '/deploy/otp_web.py').read()
ok('nginx reloaded when only a certificate file changed', 'TLS_FILES_NEW[0] = True' in H and 'if TLS_FILES_NEW[0]:' in H)
ok('modes set on the file itself, never by its name in a folder others write in',
   'os.chmod(tmp, mode)' not in H)
ok('user names for sshd and PAM end at \\Z, not $', '{1,64}$\'' not in H)
# The files and the reload in sshd_apply_files since 1.0.209: the old timer stopped after it.
ok('a change on trial keeps its timer until the next one is in', H.index('if old:\n            sshd_disarm(old)')
   > (H.index('said = sshd_apply_files(') if 'said = sshd_apply_files(' in H
      else H.index('        sshd_reload()\n        if old:')))

# ---- F6: certificate texts escaped in the confirmations -------------------------------------
J = open(V + '/web/assets/admin.js').read()
ok('the issuer of a certificate escaped in the confirmation', "htmlText(t.how)" in J and 'htmlText(words || before.how' in J)
ok('the generated passphrase back to dots once typed over, and forgotten after the file', 'expForget()' in J)
# ---- C2: no firewall map for an account that only reads ---------------------------------
web = {'fw': {'full': 'table inet filter ...'}, 'access': {'admin': ['10.0.0.0/8']}, 'tls': {'x': 1}}
ok('/api/web for an account that reads: no firewall rules, no access lists',
   otp.web_unmapped(web, {'role': 'readonly'}) == {'tls': {'x': 1}})
ok('... a token administrator sees them', otp.web_unmapped(web, {'role': 'tokenadmin'}) == web)
# ---- C4: an IPv6 isemon target written back in brackets ----------------------------------
t = otp.syslog_target_text('fd00::5', 514, 'tcp')
ok('an IPv6 target written as [fd00::5]:514/tcp (%s), taken when saved' % t,
   t == '[fd00::5]:514/tcp' and otp.syslog_targets(t, strict=True))
# ---- C3: the second certificate's key in an export ----------------------------------------
st.set_meta('web:tls:r1', json.dumps({'cert': 'C', 'key': otp.seal_secret('K1', 'web:tls'),
                                      'alt': {'cert': 'C2', 'key': otp.seal_secret('K2', 'web:tls')}}))
whole = otp.config_export(st, True)
half = otp.config_export(st, False)
tw = json.dumps(whole)
ok('an export with the secrets: the second certificate\'s key opened in it', '"K2"' in tw)
ok('... one without them: the second certificate left out', '"C2"' not in json.dumps(half))
print('ALL %d / %d' % (sum(R), len(R)))
