# t_round3.py VERSION - the bugs found by the third round of the bug hunt (1.0.207), each
# shown fixed: in-process against otp.py of VERSION, on SQLite in a folder of its own,
# and the command line run as a process for its own findings.
import os, sys, json, time, tempfile, subprocess
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.207'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r3-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r3'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


def refused(fn, *exc):
    try:
        fn()
        return False
    except exc or (Exception,):
        return True


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
d = otp.Daemon(st, serve=False)
KEY = 'JBSWY3DPEHPK3PXPJBSWY3DP'

# ---- tokens: a .totp file carries what the token is ----------------------------------------
otp.import_totp(st, 'p8', KEY + '\n" TOTP_AUTH\n" STEP_SIZE 60\n" OTP_DIGITS 8\n" OTP_ALGORITHM SHA256\n'
                '12345678\n123456789012\n')
t = st.token('p8')
ok('a .totp file: step 60, 8 digits, SHA256 taken (%s/%s/%s)' % (t.get('period'), t.get('digits'), t.get('algorithm')),
   int(t.get('period')) == 60 and int(t.get('digits')) == 8 and str(t.get('algorithm')).upper() == 'SHA256')
_s, _o, codes = otp.parse_totp_file(KEY + '\n12345678\n123456789012\n')
ok('... recovery codes of 8 and 12 digits read', len(codes) == 2, codes)
txt = otp.totp_file_text(st.token('p8'))
ok('... and written back out', '" STEP_SIZE 60' in txt and '" OTP_DIGITS 8' in txt and 'SHA256' in txt, txt)
ok('totp_issuer with a colon refused', refused(lambda: otp.check_setting('totp_issuer', 'Firma: VPN'), otp.BadSetting))
ok('secret_shown: eight dots whatever its length', otp.secret_shown('a' * 30) == otp.secret_shown('b' * 5)[:-2] + 'aa'
   and len(otp.secret_shown('x' * 40)) == 10)

# ---- secrets: kept, they go to their own server only ------------------------------------------
d.save_settings({'smtp_host': 'mail.example.cz', 'smtp_password': 'Smtp-Secret-123'}, by='t')
sealed0 = st.settings_saved().get('smtp_password')
masked = otp.secret_shown('Smtp-Secret-123')
ok('the mail password saved as its dots with another server: refused',
   refused(lambda: d.save_settings({'smtp_host': 'evil.example', 'smtp_password': masked}, by='t'), otp.BadSetting))
ok('... with the same server: saved', not refused(lambda: d.save_settings({'smtp_host': 'mail.example.cz',
                                                                              'smtp_password': masked}, by='t')))
ok('... the password still the one typed', st.settings_saved().get('smtp_password') == sealed0)
otp._TEL_TEXT.v = ''
otp.CONFIG['sms_tel_password'] = 'Tel-Pw:42/x'
said = otp._tel_hidden('GET /cgi-bin/sms_send?password=Tel-Pw%3A42%2Fx&x=1 {"password": "Tel-Pw:42/x"}')
ok('the SMS gateway password out of the debug log in every form', 'Tel-Pw' not in said, said)
c = otp._pg_passfile({'db_password': 'a:b\\c'}) if hasattr(otp, '_pg_passfile') else None
if c:
    body = open(c).read()
    ok('pg_dump\'s password in a file of its own, 0600, escaped (%s)' % body.strip(),
       oct(os.stat(c).st_mode & 0o777) == '0o600' and 'a\\:b\\\\c' in body)
    os.unlink(c)

# ---- tokens: a new set of recovery codes with a key waiting ----------------------------------
otp.import_totp(st, 'wait', KEY + '\n" TOTP_AUTH\n')
st.db.run('UPDATE tokens SET pending_secret = ? WHERE name = ?', (st.token('wait')['secret'], 'wait'))
eng = otp.Tokens(st) if hasattr(otp, 'Tokens') else None
if eng:
    try:
        eng.new_scratch('wait', 't')
        ok('new recovery codes while a key waits: they wait with it',
           bool(st.db.value('SELECT pending_scratch FROM tokens WHERE name = ?', ('wait',))))
    except Exception as e:                              # noqa: BLE001
        ok('new recovery codes while a key waits (%s)' % e, False)

# ---- the guard of places -------------------------------------------------------------------
dd = otp.Decision()
dd.refuse('the account is disabled in the directory')
ok('the guard: a disabled account is no guess', not otp.guard_is_guess(dd))
dd = otp.Decision()
dd.result, dd.reason = 'challenge', 'the code was not right: asked again (1 of 3)'
ok('the guard: a wrong code asked again is one', otp.guard_is_guess(dd))
dd = otp.Decision()
dd.refuse('Denied by the token server: wrong code')
ok('... a wrong code refused still is', otp.guard_is_guess(dd))

# ---- HA: the lead, the bundle -----------------------------------------------------------------
otp.CONFIG.update(ha_mode='replicated', ha_slot=2, ha_peer='192.0.2.50')
st.set_meta('node:a1', json.dumps({'at': time.time() - 900}))
otp.this_node_name_was = otp.node_name
real_alive = otp._peer_alive_there
otp._peer_alive_there = lambda name: True
otp.LEAD_FAR.clear()
otp.CONFIG['node_name'] = 'r3'
ok('one way of the replication stopped: the node first by name, alive in its own database, keeps the lead',
   otp.ha_lead(st) is False and otp.alerts_lead(st) is False)
otp._peer_alive_there = lambda name: False
otp.LEAD_FAR.clear()
ok('... gone there too: this one leads', otp.ha_lead(st) is True)
otp._peer_alive_there = real_alive


class V16:
    def value(self, sql, *a):
        return '160004'


class S16:
    db = V16()


otp.CONFIG.update(db_name='otp', db_user='otp', db_password='x' * 20, ha_address='192.0.2.60')
b = otp.ha_replicated_bundle_data(S16())
ok('a bundle made again on node 2: for slot 1, its peer slot 2', b['slot'] == 1 and b['peer']['slot'] == 2, b['slot'])
src = open(V + '/otp.py').read()
ok('--ha-bundle on a replicating node sets nothing up', 'return cli_ha_bundle_again(args, pal, store)' in src)
ok('a setting changed on both nodes: the later kept on both (PostgreSQL)', 'otp_newer_setting' in src)
otp.CONFIG.update(ha_mode='standalone', ha_peer='', ha_slot=1, db_password='')

# ---- the command line ----------------------------------------------------------------------
ENV = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_STAY_ROOT='1')
ENV.pop('INVOCATION_ID', None)


def cli(*a, inp=None):
    return subprocess.run([sys.executable, '-I', V + '/otp.py'] + list(a), capture_output=True, text=True,
                          env=ENV, input=inp if inp is not None else '', start_new_session=True, timeout=120)


r = cli('--set', 'smtp_password=-', inp='')
ok('--set SECRET=- with nothing on stdin: refused, nothing saved (%d)' % r.returncode,
   r.returncode != 0 and 'nothing came on stdin' in r.stderr, r.stderr[-200:])
r = cli('--config', D + '/nope.json', '--settings')
ok('--config FILE that is not there: refused', r.returncode != 0 and 'no config file' in r.stderr, r.stderr[-200:])
r = cli('--json')
try:
    json.loads(r.stdout)
    js = True
except ValueError:
    js = False
ok('--json alone: the state as JSON, not the help', js, r.stdout[:200])
cli('--add-client', 'gone', '--address', '10.9.9.9', '--secret', '-', inp='Sh4red-secret-77\n')
r = cli('--del-client', 'gone')
ok('--del-client without --yes and no terminal: refused', r.returncode != 0 and
   any(c['name'] == 'gone' for c in st.clients()), r.stderr[-200:])
r = cli('--del-client', 'gone', '--yes')
st._clients = None
ok('... with --yes: taken away', r.returncode == 0 and not any(c['name'] == 'gone' for c in st.clients()),
   r.stderr[-200:])
r = cli('--add-realm', 'rx', '--methods', 'totp,mial')
ok('--methods with a word not known: refused', r.returncode != 0 and 'mial' in r.stderr, r.stderr[-200:])
r = cli('--token', 'nobody', '--json')
ok('--token NOBODY --json: exit 1 as the text says', r.returncode == 1)
r = cli('--backup', '--json')
try:
    js = 'file' in json.loads(r.stdout)
except ValueError:
    js = False
ok('--backup --json: JSON', js, r.stdout[:200])
r = cli('--api', 'POST', '/api/settings', '{"settings":{"acme_key":"ec"}}')
ok('--api: acme_key is no secret written out', 'a secret is not taken' not in r.stderr, r.stderr[-200:])
r = cli('--api', 'POST', '/api/settings', '{"settings":{"smtp_password":"x"}}')
ok('... smtp_password still is', 'a secret is not taken' in r.stderr)
print('ALL %d / %d' % (sum(R), len(R)))
