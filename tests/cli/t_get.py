# t_get.py VERSION - otp --get KEY... (1.0.244), the counterpart of --set, on a server of its own (SQLite, its own
# folders): one key - the value alone; more - KEY=VALUE a line; --json an object; what --set saved read back; a
# boolean as 0/1, a list as JSON; a key not known: exit 2 and what was meant; a secret never shown - "set" or
# "not set" only, whatever the output.
# Usage (root): python3 t_get.py VERSION
import os, sys, json, subprocess, tempfile

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.244'
V = '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-get-')
for d in ('run', 'web', 'log'):
    os.makedirs(TOP + '/' + d)
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36912, 'radius_acct_port': 36913,
           'api_port': 36980, 'node_name': 'getnode', 'logs_keep': 21}, open(TOP + '/config.json', 'w'))
ENV = dict(os.environ, OTP_STATE=TOP, OTP_CONFIG=TOP + '/config.json', OTP_LOGDIR=TOP + '/log', OTP_RUN=TOP + '/run',
           OTP_STAY_ROOT='1')
SECRET = 'Get-Secret-244-xyz'
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:400] if more and not c else ''), flush=True)


def otp(*a, env=None, inp=None):
    r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--no-color'] + list(a), env=dict(ENV, **(env or {})),
                       input=inp, capture_output=True, text=True, timeout=120)
    ok('  (no traceback, no secret: %s)' % ' '.join(a)[:60], 'Traceback' not in r.stdout + r.stderr and SECRET not in r.stdout + r.stderr,
       r.stdout + r.stderr)
    return r.returncode, r.stdout, r.stderr


rc, out, _ = otp('--get', 'radius_auth_port')
ok('one key: the value alone (%r)' % out, rc == 0 and out == '36912\n')
rc, out, _ = otp('--get', 'logs_keep')
ok('from config.json: as it is (%r)' % out, rc == 0 and out == '21\n')
otp('--set', 'logs_keep=17')
rc, out, _ = otp('--get', 'logs_keep')
ok('what --set saved, read back (%r)' % out, out == '17\n')
rc, out, _ = otp('--get', 'logs_keep', 'radius_auth_port', 'alerts_cert_days')
ok('more keys: KEY=VALUE a line, in the order asked', out.splitlines() == ['logs_keep=17', 'radius_auth_port=36912', 'alerts_cert_days=21'], out)
rc, out, _ = otp('--get', 'logs_keep', 'portal_sso_from', '--json')
ok('--json: an object', rc == 0 and json.loads(out) == {'logs_keep': 17, 'portal_sso_from': ''}, out)
rc, out, _ = otp('--get', 'portal')
ok('a switch as 0 or 1 (%r)' % out, out.strip() in ('0', '1'))
rc, out, err = otp('--get', 'logs_kep')
ok('a key not known: exit 2, what was meant (%s)' % rc, rc == 2 and 'logs_keep' in err and not out, err)
rc, out, _ = otp('--get', 'smtp_password')
ok('a secret not set: "not set"', out == 'not set\n', out)
otp('--set', 'smtp_password=-', inp=SECRET + '\n')
rc, out, _ = otp('--get', 'smtp_password')
ok('a secret set: "set", never the value', out == 'set\n', out)
rc, out, _ = otp('--get', 'smtp_password', 'logs_keep', '--json')
ok('...nor in --json', json.loads(out).get('smtp_password') == 'set', out)
rc, out, _ = otp('--get', 'smtp_password', 'logs_keep')
ok('...nor in KEY=VALUE', 'smtp_password=set' in out, out)
rc, out, _ = otp('--get', 'clock_mode', 'split_mode')
ok('the clock guard\'s and the split\'s own keys too', out.startswith('clock_mode=') and 'split_mode=' in out, out)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
