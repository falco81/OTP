# SSH with a code from otp (1.0.178; 1.0.181: SSH tokens of their own and otp's gate
# on 127.0.0.1, no RADIUS client, realm or VPN token): a daemon and an SSH token; the
# root helper's sshd_do puts pam_radius into a copy of sshd's PAM (and
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
os.makedirs(D + '/sms')
import socket
API, RAD, WANT = 30991, 36920, 18157   # in the gate's range, and not the HA sandbox's 18121-18132
# Something else on the port asked for: the gate takes the next free one.
BUSY = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
BUSY.bind(('127.0.0.1', WANT))
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RAD, 'radius_acct_port': RAD + 1,
           'api_port': API, 'node_name': 'otp1', 'ssh_gate_port': WANT,
           'sms_mode': 'spool', 'sms_spool_dir': D + '/sms'}, open(D + '/config.json', 'w'))
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
os.environ.update(env)
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
st.db.make_tables()
otp.sealing_key(make=True)
# What 1.0.178-1.0.180 made: a RADIUS client - taken away when the gate opens.
st.client_save({'name': 'SSH of the nodes - pam_radius', 'address': '127.0.0.1', 'secret': 'old-client-secret-xyz',
                'enabled': 1})
st.set_meta('host:sshd:conf', json.dumps({'manage': True, 'radius': True}))
SECRET = otp.ssh_gate_secret(st, make=True)
K = otp.sshotp_make(st, 'jan', 'test')['secret'].replace(' ', '')
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


GATE = int(st.get_meta('sshotp:port:otp1') or 0)
lo, hi = otp.ssh_gate_ephemeral()
ok('the gate: not the port taken by something else, a free one of 18129-18199 (%d)' % GATE,
   GATE != WANT and 18129 <= GATE <= 18199 and not lo <= GATE <= hi)
ok('no VPN token, no realm: none made', not st.db.value('SELECT COUNT(*) FROM tokens') and not st.realms())
ok('the old RADIUS client for SSH taken away', not [c for c in st.clients() if 'pam_radius' in c['name']],
   [c['name'] for c in st.clients()])


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
                            'radius_secret': SECRET, 'radius_port': GATE})


HERE = os.path.dirname(os.path.abspath(__file__))


def pam(user, secret_word, *more):
    """sshd's PAM as otptest, with the answer on stdin (pamauth.py: pamtester and
    pam_radius 2.0 do not get on)."""
    shutil.copy(E + '/pam.d/sshd', '/etc/pam.d/otptest')
    # A kernel without IPv6 (gVisor): pam_radius 2.0 gives up without an IPv6
    # socket - v6shim.c hands it one that binds to nothing (tests only).
    so = D + '/v6shim.so'
    if not os.path.exists(so):
        subprocess.run(['gcc', '-shared', '-fPIC', '-o', so, HERE + '/v6shim.c', '-ldl'], check=True)
    got = subprocess.run([sys.executable, HERE + '/pamauth.py', 'otptest', user], input='\n'.join((secret_word,) + more) + '\n',
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
good, said = pam('jan', code())
ok('the same code again: not in (used once)', not good, said)
good, said = pam('jan', '000000')
ok('a wrong code: not in', not good, said)
good, said = pam('petr', '123456')
ok('no SSH token for petr: not in', not good, said)
ev = json.dumps(st.db.rows("SELECT words FROM events WHERE kind = 'ssh'"))
ok('each sign-in an event (in, and not)', 'jan signed in to SSH on otp1' in ev and 'was not let into SSH' in ev, ev[:300])
rl = st.db.value('SELECT COUNT(*) FROM radius_log')
ok('nothing in the log of RADIUS', not rl, rl)
# By SMS (1.0.181): Enter at the first prompt, the code sent, asked in a second one.
otp.sshotp_make(st, 'eva', 'test', kind='sms', dest='+420777123456')
good, said = pam('eva', '', '@sms:' + D + '/sms')
ok('an SSH token by SMS: Enter, the code by SMS asked in a second prompt - in (%s)' % said.replace('\n', ' | '),
   good and said.count('prompt') >= 2)
time.sleep(21)
good, said = pam('eva', '', '111111')
ok('... a wrong code sent back: asked again, then not in', not good and said.count('prompt') >= 3, said)
time.sleep(1)
good, said = pam('eva', '')
ok('... asked again at once: no second SMS within 20 s', not good and 'prompt' in said, said)
otp.sshotp_make(st, 'ann', 'test', kind='sms', dest='+420777123457', lang='en')
for f in os.listdir(D + '/sms'):
    os.unlink(os.path.join(D + '/sms', f))
st_, ask_ = otp.sshotp_send(st, 'ann')
sms = ''.join(open(os.path.join(D + '/sms', f)).read() for f in os.listdir(D + '/sms') if not f.startswith('.'))
ok('an SSH token in English: the SMS and the prompt in English', 'SSH sign-in code' in sms and ask_.startswith('Type the code'), (sms, ask_))
ok('... the SMS says it is for SSH', 'SSH' in otp.code_message('sms', '+420777123456', '123456', 'ssh', lang='en'))
ok('the SSH token says when it was used', ([t for t in otp.sshotp_all(st) if t['name'] == 'jan'][0].get('used_at') or 0) > time.time() - 120)
# Only these users: jan is not among them - his own password (none here) asked, not otp.
apply(radius_users=['petr'])
text = open(E + '/pam.d/sshd').read()
ok('only petr: the others skip it', 'user notin petr' in text)
good, said = pam('jan', code())
ok('jan, not among them: otp is not asked, his system password is (none: out)', not good and 'prompt' in said, said)
apply()
# otp not answering: with the fallback, the system's password (none here - so out, but
# by common-auth, after pam_radius said it cannot ask).
d.terminate()
d.wait(10)
good, said = pam('jan', code())
ok('otp down, fallback on: pam_radius steps aside, common-auth asked (no such password: out)', not good, said)
got = otp_web.sshd_do({'do': 'read'})
ok('the helper says the file\'s fingerprint - the daemon\'s own', got['radius']['fp'] == otp.ssh_gate_fp(SECRET, GATE)
   and SECRET not in json.dumps(got))
otp_web.sshd_do({'do': 'pamconf', 'radius_secret': 'another-secret-of-the-gate', 'radius_port': GATE + 1})
ok('pamconf: only the file, the new secret and port', 'another-secret-of-the-gate' in open(cf).read() and
   ':%d ' % (GATE + 1) in open(cf).read())
otp_web.sshd_do({'do': 'pamconf', 'radius_secret': SECRET, 'radius_port': GATE})
apply(password=False, radius_fallback=True)
text = open(E + '/pam.d/sshd').read()
ok('passwords off: no fallback, and pam_deny after', 'localifdown' not in text and 'auth requisite pam_deny.so' in text)
drop = open(E + '/ssh/sshd_config.d/00-otp.conf').read()
ok('... PasswordAuthentication no, keyboard-interactive for the code', 'PasswordAuthentication no' in drop and
   'KbdInteractiveAuthentication yes' in drop, drop)
# A key and then the code (1.0.183).
apply(password=True, radius_with_key=True)
drop = open(E + '/ssh/sshd_config.d/00-otp.conf').read()
ok('a key, then the code: AuthenticationMethods for everybody, root left as it was',
   drop.rstrip().endswith('Match User *,!root\n    AuthenticationMethods publickey,keyboard-interactive'), drop)


def sshT(user):
    got = subprocess.run(['/usr/sbin/sshd', '-T', '-f', E + '/ssh/sshd_config', '-C', 'user=%s,host=x,addr=10.0.0.1' % user],
                         capture_output=True, text=True)
    return [l for l in got.stdout.split('\n') if l.startswith('authenticationmethods')]


ok('... sshd -T: jan a key and the code, root as before', sshT('jan') == ['authenticationmethods publickey,keyboard-interactive']
   and sshT('root') == ['authenticationmethods any'], (sshT('jan'), sshT('root')))
ok('... the Match did not reach the system\'s own settings', otp_web.sshd_match_kept() == '')
apply(radius_with_key=True, radius_users=['petr', 'eva'])
drop = open(E + '/ssh/sshd_config.d/00-otp.conf').read()
ok('... only petr and eva: a Match of theirs', 'Match User petr,eva\n    AuthenticationMethods publickey,keyboard-interactive' in drop
   and sshT('jan') == ['authenticationmethods any'] and sshT('eva') == ['authenticationmethods publickey,keyboard-interactive'], drop)
apply(radius_with_key=False)
ok('... off: no AuthenticationMethods', 'AuthenticationMethods' not in open(E + '/ssh/sshd_config.d/00-otp.conf').read())
apply(radius=False)
ok('switched off: sshd\'s PAM exactly as it was', open(E + '/pam.d/sshd').read() == ORIG)
ok('... the secret\'s file gone', not os.path.exists(cf))
# On trial, not kept: everything back.
otp_web.sshd_do({'do': 'apply', 'conf': CONF, 'trial_min': 5, 'no_keys_ok': True, 'id': 'trial1', 'hash': 'h1',
                 'radius_secret': SECRET, 'radius_port': GATE})
ok('on trial: in', otp_web.PAM_BEGIN in open(E + '/pam.d/sshd').read())
otp_web.sshd_put_back('not kept in time')
ok('... not kept: sshd\'s PAM as it was, the secret gone', open(E + '/pam.d/sshd').read() == ORIG and not os.path.exists(cf))
print('ALL %d / %d' % (sum(R), len(R)))
