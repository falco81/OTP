# t_cli.py VERSION - every option of the command line on one server of its own (SQLite, its
# own folders and ports, the daemon running): each answers without a traceback, with --json
# where it says it can; what it changes is seen changed (by the next command or the API);
# secrets taken only from the environment or a prompt, never shown.
# Usage (root): python3 t_cli.py VERSION
import os, sys, json, time, subprocess, tempfile, atexit, base64, re

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.187'
V = '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-cli-')
for d in ('run', 'web', 'log'):
    os.makedirs(TOP + '/' + d)
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36812, 'radius_acct_port': 36813,
           'api_port': 36880, 'node_name': 'clinode'}, open(TOP + '/config.json', 'w'))
ENV = dict(os.environ, OTP_STATE=TOP, OTP_CONFIG=TOP + '/config.json', OTP_LOGDIR=TOP + '/log', OTP_RUN=TOP + '/run',
           OTP_STAY_ROOT='1', OTP_CONSOLE_FLAG=TOP + '/console-login', OTP_POWER_CMD=TOP + '/power')
R = []
SECRETS = ['Cli-Secret-187-xyz', 'Bind-Pw-187-abc', 'Admin-Pass-187-Cli!', 'Smtp-Pass-187-q']


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % (str(more)[:700],)) if more and not cond else ''),
          flush=True)


def cli(*args, env=None, inp=None, code=None, want=None, name=None, timeout=120):
    """One run of otp: (exit code, output). Never a traceback; never a secret shown."""
    e = dict(ENV, **(env or {}))
    r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--no-color'] + list(args), env=e, input=inp,
                       capture_output=True, text=True, timeout=timeout)
    out = r.stdout + r.stderr
    what = name or ' '.join(args)[:90]
    bad = [s for s in SECRETS if s in out]
    if code is None and 'refused' in what:
        code = 'nonzero'
    good = 'Traceback' not in out and not bad and \
        (code is None or (r.returncode != 0 if code == 'nonzero' else r.returncode == code)) and \
        (want is None or re.search(want, out, re.S))
    ok('%s (%d)' % (what, r.returncode), good, out[-700:])
    return r.returncode, out


cli('--version', code=0, want=VER)
cli('--help', code=0, want='HIGH AVAILABILITY')
# ---- before the daemon: the database made, an account --------------------------------
cli('--add-user', 'cliadmin', '--role', 'fulladmin', env={'OTP_PASSWORD': SECRETS[2]}, code=0)
cli('--users', code=0, want='cliadmin')
cli('--users', '--json', code=0)
d = subprocess.Popen([sys.executable, '-I', V + '/otp.py', '--daemon'], env=ENV, stdout=open(TOP + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
for _ in range(60):
    time.sleep(0.5)
    if os.path.exists(TOP + '/run/api-token'):
        break
time.sleep(3)
# ---- looking ---------------------------------------------------------------------------
for a in (['--status'], ['--status', '--json'], ['--check'], ['--log'], ['--log', '--rejects', '--limit', '5'],
          ['--otp-log'], ['--tokens'], ['--events'], ['--events', '--json', '--hours', '1'], ['--settings'],
          ['--settings', '--json'], ['--clients'], ['--realms'], ['--directories'], ['--ha-status'], ['--web-status'],
          ['--rbackup-status'], ['--upgrade-status'], ['--maintenance', 'status'], ['--admin-2fa', 'status'],
          ['--console-at-login', 'status'], ['--ha-tls'], [], ['--downgrade-check']):
    cli(*a)
# ---- clients, realms, directories ------------------------------------------------------
cli('--add-client', 'vpn', '--address', '127.0.0.0/8', '--secret', '-', env={'OTP_SECRET': SECRETS[0]}, code=0)
cli('--clients', code=0, want='vpn')
c, out = cli('--clients', '--json', code=0)
cli('--add-client', 'bad', '--address', 'not-an-address', '--secret', '-', env={'OTP_SECRET': 'x' * 20},
    name='a client with a wrong address: refused')
ok('... and not made', 'bad' not in cli('--clients')[1].split())
cli('--add-directory', 'corp', '--hosts', '127.0.0.1', '--base', 'DC=corp,DC=cz', '--bind-dn', 'CN=r,DC=corp,DC=cz',
    '--bind-pw', '-', '--tls', 'none', '--port', '3899', env={'OTP_BIND_PW': SECRETS[1]}, code=0)
cli('--directories', code=0, want='corp')
cli('--add-realm', 'local', '--suffix', '', '--mode', 'otp', code=0)
cli('--add-realm', 'corp', '--suffix', 'corp.cz', '--directory', 'corp', '--lookup', 'upn', '--mode', 'password_otp',
    '--aliases', 'corp.local', '--methods', 'totp,mail', code=0)
cli('--realms', code=0, want=r'corp.cz \+corp.local')
# A token made under an alias: under the realm's own suffix, as the pages make it.
cli('--enroll', 'anna@corp.local', '--no-qr', code=0)
cli('--tokens', want='anna@corp.cz')
ok('... not a second one under the alias', 'anna@corp.local' not in cli('--tokens')[1])
# --groups keeps what a group it had replies.
sys.path.insert(0, V)
os.environ.update(ENV)
import otp  # noqa: E402
otp.load_config(saved=None)
_st = otp.Storage(otp.open_db())
_r = next(r for r in _st.realms() if r['name'] == 'corp')
_r['groups'] = [{'group': 'VPN', 'reply': 'Class=vpn-policy'}]
_st.realm_save(_r, 'test')
cli('--add-realm', 'corp', '--groups', 'VPN;Admins', code=0)
_g = {g['group']: g.get('reply') for g in next(r for r in _st.realms() if r['name'] == 'corp')['groups']}
ok('--groups: the reply of a group it had kept (%s)' % _g, _g.get('VPN') == 'Class=vpn-policy' and 'Admins' in _g)
cli('--add-realm', 'ghost', '--suffix', 'g.cz', '--directory', 'nosuch', name='a realm with no such directory: refused')
ok('... and not made', 'ghost' not in cli('--realms')[1])
# ---- tokens ---------------------------------------------------------------------------
c, out = cli('--enroll', 'novak', '--no-qr', '--json', code=0)
try:
    sec = json.loads(out[out.index('{'):])['secret']
except Exception:                                       # noqa: BLE001
    sec = ''
ok('--enroll --json gives the key', sec)


def code_now(off=0):
    sys.path.insert(0, V)
    import otp
    s = sec.replace(' ', '')
    return otp.totp(base64.b32decode(s + '=' * (-len(s) % 8)), time.time() + off)


cli('--tokens', code=0, want='novak')
cli('--token', 'novak', code=0)
cli('--verify', 'novak', code_now(), code=0, want='(?i)right|ok|yes|valid')
cli('--verify', 'novak', '000000' if code_now() != '000000' else '111111', name='--verify a wrong code: no')
cli('--radtest', 'novak', code_now(), env={'OTP_SECRET': SECRETS[0]}, want='(?i)accept')
cli('--log', '--limit', '3', code=0, want='novak')
c, out = cli('--log', '--json', '--limit', '1', code=0)
try:
    rid = str(json.loads(out[out.index('['):])[0].get('id'))
except Exception:                                       # noqa: BLE001
    rid = ''
if rid:
    cli('--request', rid, code=0, want='novak')
cli('--scratch', 'novak', code=0)
cli('--unlock', 'novak', code=0)
cli('--disable-token', 'novak', code=0)
cli('--radtest', 'novak', code_now(), env={'OTP_SECRET': SECRETS[0]}, want='(?i)reject', name='a disabled token: refused')
cli('--enable-token', 'novak', code=0)
cli('--enroll', 'pend', '--pending', '--no-qr', code=0)
time.sleep(31)
cli('--confirm', 'pend', '000000', name='--confirm a wrong code: refused')
cli('--enroll', 'mailer', '--by', 'mail', '--to', 'mailer@corp.cz', '--no-qr', code=0)
cli('--enroll', 'sms1', '--by', 'sms', '--to', '+420601234567', '--no-qr', code=0)
cli('--enroll', 'sms2', '--by', 'sms', '--to', 'not a number', '--no-qr', name='--enroll sms to a wrong number: refused')
cli('--delete-token', 'sms1', '--yes', code=0)
ok('... gone', 'sms1' not in cli('--tokens')[1])
# ---- settings ---------------------------------------------------------------------------
cli('--set', 'lockout_after=7', code=0)
cli('--settings', '--search', 'lockout', want='lockout_after +7')
cli('--set', 'lockout_after=banana', name='--set a number to a word: refused')
cli('--set', 'no_such_setting=1', name='--set an unknown setting: refused')
cli('--set', 'smtp_password=-', env={'OTP_VALUE': SECRETS[3]}, inp=SECRETS[3] + '\n', name='--set a secret from a prompt')
c, out = cli('--settings', '--json')
ok('... a secret shown as nothing more than it is set', SECRETS[3] not in out)
cli('--set', 'smtp_password=Plain-On-The-Line-1', name='--set a secret written out: refused')
cli('--set', 'sms_token=-', inp='Sms-Token-From-Stdin-187\n', code=0, name='--set a secret from one line of stdin')
c, out = cli('--settings', '--search', 'sms_token', '--json')
ok('... saved, and shown as set only', 'Sms-Token-From-Stdin' not in out and 'sms_token' in out)
cli('--add-client', 'x2', '--address', '10.1.1.1', '--secret', 'Plain-Client-Secret', name='--secret written out: refused')
cli('--radtest', 'novak', '123456', '127.0.0.1', '36812', 'Plain-Radtest-Secret', name='--radtest secret written out: refused')
# ---- accounts ---------------------------------------------------------------------------
cli('--add-user', 'reader', env={'OTP_PASSWORD': 'Reader-Pass-187-x!'}, code=0)
cli('--set-role', 'reader', '--role', 'tokenadmin', code=0)
cli('--users', want='reader +token admin')
cli('--disable-user', 'reader', code=0)
cli('--enable-user', 'reader', code=0)
cli('--passwd', 'reader', env={'OTP_PASSWORD': 'Reader-Pass-187-y!'}, code=0)
cli('--passwd', 'reader', env={'OTP_PASSWORD': 'short'}, name='--passwd a weak one: refused')
cli('--reset-2fa', 'reader', code=0)
cli('--del-user', 'reader', '--yes', code=0)
cli('--admin-2fa', 'status', code=0)
cli('--console-at-login', 'on', code=0)
cli('--console-at-login', 'off', code=0)
# ---- maintenance, export, backup --------------------------------------------------------
cli('--maintenance', 'on', '--why', 'cli test', code=0)
cli('--maintenance', 'status', want='(?i)on|maint')
cli('--radtest', 'novak', code_now(), env={'OTP_SECRET': SECRETS[0]}, name='in maintenance: not answered',
    want='(?i)no answer|timeout|did not answer|maintenance')
cli('--maintenance', 'off', code=0)
cli('--export-config', TOP + '/conf.json', code=0)
exp = open(TOP + '/conf.json').read() if os.path.exists(TOP + '/conf.json') else ''
ok('--export-config without secrets: none in the file', exp and not any(s in exp for s in SECRETS))
cli('--import-config', TOP + '/conf.json', name='--import-config without --yes: says what it would do')
cli('--import-config', TOP + '/conf.json', '--yes', code=0)
cli('--clients', want='vpn')
cli('--backup', code=0)
bk = sorted([f for f in os.listdir(TOP) if 'backup' in f or f.endswith('.db.gz') or f.endswith('.sqlite')])
c, out = cli('--backup', '--json', code=0)
cli('--tidy', code=0)
cli('--fill-names', code=0)
cli('--isemon-test')
cli('--rbackup-now')
cli('--upgrade-check')
cli('--change-back', 'fw')
cli('--ha-compare')
cli('--directory-test', 'corp')
# ---- what the pages do, here too --------------------------------------------------------
cli('--acme', code=0, want='off')
cli('--acme', '--json', code=0)
cli('--acme-order', 'all', name='--acme-order with ACME off: refused')
cli('--updates', 'status', code=0, want='clinode')
cli('--updates', 'status', '--json', code=0)
cli('--updates', 'check', code=0)
cli('--updates', 'cancel')
cli('--restarts', code=0, want='clinode')
cli('--restart-nodes', 'nosuch', '--yes', name='--restart-nodes a node there is not: refused')
cli('--restart-nodes', 'clinode', '--yes', code=0)
time.sleep(4)
cli('--restarts', code=0, want='reboot clinode')
cli('--mail-test', 'not-an-address', name='--mail-test to no address: refused')
cli('--mail-test', 'admin@example.cz', name='--mail-test, mail not set up: refused, said why')
cli('--sms-test', '12', name='--sms-test to no number: refused')
cli('--ssh-tokens', code=0)
c, out = cli('--ssh-token-add', 'root', '--no-qr', code=0, want='key:')
cli('--ssh-tokens', code=0, want='root +the app')
cli('--ssh-token-add', 'root', '--no-qr', name='--ssh-token-add again without --yes: refused')
cli('--ssh-token-add', 'ops', '--by', 'sms', '--to', '+420601234567', name='--ssh-token-add by SMS, SMS not set up: refused')
cli('--ssh-token-del', 'root', code=0)
cli('--ssh-token-del', 'root', name='--ssh-token-del one not there: refused')
# a lockout: wrong codes until the token is locked, seen and cleared
cli('--set', 'lockout_after=3', code=0)
for i in range(4):
    cli('--radtest', 'novak', '00000%d' % i, env={'OTP_SECRET': SECRETS[0]})
    time.sleep(1)
time.sleep(6)
cli('--lockouts', code=0, want='token-locked:novak')
cli('--lockouts', '--json', code=0)
cli('--lockouts-clear', 'token-locked:novak', code=0)
ok('... the token not locked any more', 'token-locked:novak' not in cli('--lockouts')[1])
cli('--lockouts-clear', 'all', code=0)
cli('--lockouts-clear', 'nonsense', name='--lockouts-clear without KIND:WHO: refused')
cli('--del-realm', 'corp', '--yes', code=0)
cli('--del-directory', 'corp', '--yes', code=0)
cli('--del-client', 'vpn', '--yes', code=0)
cli('--clients', name='clients after deleting', want='(?s)^((?!vpn ).)*$')
print('    folder:', TOP)
print('ALL %d / %d' % (sum(R), len(R)), flush=True)
