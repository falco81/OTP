# SSH with a code from otp (1.0.178): a daemon with a realm of codes alone and a
# token; the root helper's sshd_do puts pam_radius into a copy of sshd's PAM (and
# the drop-in, sshd -t), that copy installed as the PAM service otptest; then
# pamtester signs in as sshd would: the right code, a wrong one, a user left out,
# root, otp not answering (the fallback, or none with passwords off); taken out
# again, and the file as it was. Usage (root): python3 t_pamradius.py VERSION
import os, sys, json, time, base64, shutil, subprocess, tempfile, atexit

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.178'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-pamr-')
os.makedirs(D + '/run')
os.makedirs(D + '/web')
API, RAD = 30991, 36920
SECRET = 'ssh-radius-secret-178-abcdef'
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
st.client_save({'name': 'SSH of the nodes - pam_radius', 'address': '127.0.0.1', 'secret': SECRET, 'enabled': 1})
st.realm_save({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'})
tk = otp.Tokens(st)
K = tk.enroll('jan', 'test')['secret']
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(lambda: d.poll() is None and d.terminate())
time.sleep(6)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (more,)) if more and not c else ''), flush=True)


def code(off=0):
    return otp.totp(base64.b32decode(K + '=' * (-len(K) % 8)), time.time() + off)


# ---- the root helper, on copies of /etc/ssh and /etc/pam.d ----------------------------
E = D + '/etc'
os.makedirs(E + '/ssh/sshd_config.d')
os.makedirs(E + '/pam.d')
shutil.copy('/etc/pam.d/sshd', E + '/pam.d/sshd')
ORIG = open(E + '/pam.d/sshd').read()
open(E + '/ssh/sshd_config', 'w').write('Include %s/ssh/sshd_config.d/*.conf\nHostKey /etc/ssh/ssh_host_ecdsa_key\n' % E)
os.environ.update(OTP_SSH_DIR=E + '/ssh', OTP_ETC=E, OTP_VIP_NO_SERVICES='1', OTP_NO_PKG='1')
sys.path.insert(0, V + '/deploy')
import otp_web  # noqa: E402
CONF = {'manage': True, 'permit_root': 'prohibit-password', 'password': True, 'port': 22, 'allow_users': [],
        'tries': 4, 'notice': '', 'radius': True, 'radius_users': [], 'radius_root': False, 'radius_fallback': True}


def apply(**kw):
    c = dict(CONF, **kw)
    return otp_web.sshd_do({'do': 'apply', 'conf': c, 'trial_min': 0, 'no_keys_ok': True, 'id': 'abc',
                            'radius_secret': SECRET, 'radius_port': RAD})


HERE = os.path.dirname(os.path.abspath(__file__))


def pam(user, secret_word):
    """sshd's PAM as otptest, with the answer on stdin (pamauth.py: pamtester and
    pam_radius 2.0 do not get on)."""
    shutil.copy(E + '/pam.d/sshd', '/etc/pam.d/otptest')
    # A kernel without IPv6 (gVisor): pam_radius 2.0 gives up without an IPv6
    # socket - v6shim.c hands it one that binds to nothing (tests only).
    so = D + '/v6shim.so'
    if not os.path.exists(so):
        subprocess.run(['gcc', '-shared', '-fPIC', '-o', so, HERE + '/v6shim.c', '-ldl'], check=True)
    got = subprocess.run([sys.executable, HERE + '/pamauth.py', 'otptest', user], input=secret_word + '\n',
                         capture_output=True, text=True, timeout=60, env=dict(os.environ, LD_PRELOAD=so))
    return got.returncode == 0, (got.stdout + got.stderr).strip()[-200:]


atexit.register(lambda: os.path.exists('/etc/pam.d/otptest') and os.unlink('/etc/pam.d/otptest'))
got = apply()
text = open(E + '/pam.d/sshd').read()
ok('put in: our block before the first auth line', text.index(otp_web.PAM_BEGIN) < text.index('@include common-auth'), text[:300])
ok('... pam_radius with its own file, the fallback', 'pam_radius_auth.so conf=%s/otp/pam_radius.conf localifdown' % E in text)
ok('... root left out', 'pam_succeed_if.so quiet user = root' in text)
cf = E + '/otp/pam_radius.conf'
ok('... the secret in a file of 0600', oct(os.stat(cf).st_mode & 0o777) == '0o600' and SECRET in open(cf).read())
drop = open(E + '/ssh/sshd_config.d/00-otp.conf').read()
ok('... sshd: keyboard-interactive and PAM', 'KbdInteractiveAuthentication yes' in drop and 'UsePAM yes' in drop, drop)
ok('... said so', got['radius']['pam'] and got['radius']['conf'], got.get('radius'))
apply()
ok('put in twice: one block', open(E + '/pam.d/sshd').read().count(otp_web.PAM_BEGIN) == 1)

good, said = pam('jan', code())
ok('the right code: in (%s)' % said, good)
good, said = pam('jan', '000000')
ok('a wrong code: not in', not good, said)
# Only these users: jan is not among them - his own password (none here) asked, not otp.
apply(radius_users=['petr'])
text = open(E + '/pam.d/sshd').read()
ok('only petr: the others skip it', 'user notin petr' in text)
n0 = len([l for l in open(D + '/otp.log').read().split('\n') if 'jan' in l]) if os.path.exists(D + '/otp.log') else 0
good, said = pam('jan', code())
ok('jan, not among them: otp is not asked, his system password is (none: out)', not good and 'prompt' in said, said)
n_before = st.db.value("SELECT COUNT(*) FROM radius_log")
apply()
# otp not answering: with the fallback, the system's password (none here - so out, but
# by common-auth, after pam_radius said it cannot ask).
d.terminate()
d.wait(10)
good, said = pam('jan', code())
ok('otp down, fallback on: pam_radius steps aside, common-auth asked (no such password: out)', not good, said)
apply(password=False, radius_fallback=True)
text = open(E + '/pam.d/sshd').read()
ok('passwords off: no fallback, and pam_deny after', 'localifdown' not in text and 'auth requisite pam_deny.so' in text)
drop = open(E + '/ssh/sshd_config.d/00-otp.conf').read()
ok('... PasswordAuthentication no, keyboard-interactive for the code', 'PasswordAuthentication no' in drop and
   'KbdInteractiveAuthentication yes' in drop, drop)
apply(radius=False)
ok('switched off: sshd\'s PAM exactly as it was', open(E + '/pam.d/sshd').read() == ORIG)
ok('... the secret\'s file gone', not os.path.exists(cf))
# On trial, not kept: everything back.
otp_web.sshd_do({'do': 'apply', 'conf': CONF, 'trial_min': 5, 'no_keys_ok': True, 'id': 'trial1', 'hash': 'h1',
                 'radius_secret': SECRET, 'radius_port': RAD})
ok('on trial: in', otp_web.PAM_BEGIN in open(E + '/pam.d/sshd').read())
otp_web.sshd_put_back('not kept in time')
ok('... not kept: sshd\'s PAM as it was, the secret gone', open(E + '/pam.d/sshd').read() == ORIG and not os.path.exists(cf))
print('ALL %d / %d' % (sum(R), len(R)))
