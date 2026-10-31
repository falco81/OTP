# t_sshreal.py VERSION - SSH with a code as a person signs in: a real sshd (its own port and
# PAM service, otp's block put in by the root helper), a real ssh client with a key, then
# keyboard-interactive - each prompt as PuTTY would show it. Tokens of the app and by mail.
# Usage (root, in a venv with pexpect): python t_sshreal.py VERSION
import os, sys, json, time, base64, shutil, subprocess, tempfile, atexit, re, glob, pwd
import pexpect

PY = '/usr/bin/python3'
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.188'
V = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-sshr-')
os.chmod(D, 0o755)
for x in ('run', 'web', 'mail'):
    os.makedirs(D + '/' + x)
API, RAD, PORT = 30995, 36940, 2222
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
sink = subprocess.Popen([PY, '/home/claude/ws/tests/alerts/mailsink.py', '2527', D + '/mail'])
atexit.register(sink.terminate)
otp.Daemon(st, serve=False).save_settings({'mail_mode': 'smtp', 'smtp_host': '127.0.0.1', 'smtp_port': 2527,
                                            'smtp_security': 'none', 'smtp_auth': 'none',
                                            'mail_from': 'otp@example.cz'}, by='test')
st.set_meta('host:sshd:conf', json.dumps({'manage': True, 'radius': True}))
SECRET = otp.ssh_gate_secret(st, make=True)
USERS = {'sshapp': 'app', 'sshmail': 'mail', 'sshlate': 'mail', 'sshnone': 'mail', 'sshcz': 'mail'}
K = None
for u, kind in USERS.items():
    if subprocess.run(['id', u], capture_output=True).returncode:
        subprocess.run(['useradd', '-m', '-s', '/bin/bash', u], check=True)
    got = otp.sshotp_make(st, u, 'test', kind=kind, dest='%s@example.cz' % u if kind == 'mail' else '',
                          lang='en', replace=True)
    if kind == 'app':
        K = got['secret'].replace(' ', '')
d = subprocess.Popen([PY, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: d.poll() is None and d.terminate())
time.sleep(6)
GATE = int(st.get_meta('sshotp:port:otp1') or 0)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + ((' (%s)' % (str(more)[-700:],)) if more and not c else ''), flush=True)


# ---- the root helper's PAM block, on a copy; sshd run under its own name: its PAM service --
E = D + '/etc'
os.makedirs(E + '/ssh/sshd_config.d')
os.makedirs(E + '/pam.d')
shutil.copy('/etc/pam.d/sshd', E + '/pam.d/sshd')
open(E + '/ssh/sshd_config', 'w').write('Include %s/ssh/sshd_config.d/*.conf\nHostKey /etc/ssh/ssh_host_ecdsa_key\n' % E)
os.environ.update(OTP_SSH_DIR=E + '/ssh', OTP_ETC=E, OTP_VIP_NO_SERVICES='1', OTP_NO_PKG='1')
sys.path.insert(0, V + '/deploy')
import otp_web  # noqa: E402
CONF = {'manage': True, 'permit_root': 'prohibit-password', 'password': False, 'port': PORT, 'allow_users': [],
        'tries': 6, 'notice': '', 'radius': True, 'radius_users': [], 'radius_root': True, 'radius_fallback': False,
        'radius_with_key': True}
got = otp_web.sshd_do({'do': 'apply', 'conf': CONF, 'trial_min': 0, 'no_keys_ok': True, 'id': 'abc',
                       'radius_secret': SECRET, 'radius_port': GATE})
shutil.copy(E + '/pam.d/sshd', '/etc/pam.d/otpsshd')
atexit.register(lambda: os.path.exists('/etc/pam.d/otpsshd') and os.unlink('/etc/pam.d/otpsshd'))
drop = ''.join(open(f).read() for f in glob.glob(E + '/ssh/sshd_config.d/*.conf'))
subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', D + '/hostkey'], check=True)
subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', D + '/userkey'], check=True)
for u in USERS:
    home = pwd.getpwnam(u).pw_dir
    os.makedirs(home + '/.ssh', exist_ok=True)
    shutil.copy(D + '/userkey.pub', home + '/.ssh/authorized_keys')
    subprocess.run(['chown', '-R', '%s:%s' % (u, u), home + '/.ssh'])
    os.chmod(home + '/.ssh/authorized_keys', 0o600)
# What otp's drop-in says, here on a port of its own.
lines = [ln for ln in drop.split('\n') if ln.strip() and not ln.startswith(('Port', 'Include', '#', 'Match', 'ListenAddress'))]
conf = ['Port %d' % PORT, 'ListenAddress 127.0.0.1', 'HostKey %s/hostkey' % D, 'PidFile %s/sshd.pid' % D,
        'AllowUsers %s' % ' '.join(USERS), 'UsePAM yes', 'KbdInteractiveAuthentication yes',
        'PasswordAuthentication no', 'PubkeyAuthentication yes'] + \
    [ln for ln in lines if ln.split()[0] in ('AuthenticationMethods',)]
open(D + '/sshd_config', 'w').write('\n'.join(conf) + '\n')
ok('otp\'s drop-in: a key and then keyboard-interactive', 'publickey,keyboard-interactive' in drop, drop)
os.symlink('/usr/sbin/sshd', D + '/otpsshd')      # its name is its PAM service
so = D + '/v6shim.so'
subprocess.run(['gcc', '-shared', '-fPIC', '-o', so, HERE + '/v6shim.c', '-ldl'], check=True)
os.makedirs('/run/sshd', exist_ok=True)
sd = subprocess.Popen([D + '/otpsshd', '-D', '-e', '-f', D + '/sshd_config'], env=dict(os.environ, LD_PRELOAD=so),
                      stdout=open(D + '/sshd.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(sd.terminate)
time.sleep(2)


def code(off=0):
    return otp.totp(base64.b32decode(K + '=' * (-len(K) % 8)), time.time() + off)


def last_code(before):
    for _ in range(60):
        new = sorted(f for f in glob.glob(D + '/mail/*.eml') if f not in before)
        if new:
            body = open(new[-1]).read()
            try:
                import email
                msg = email.message_from_string(body)
                text = ''.join(p.get_payload(decode=True).decode('utf-8', 'replace') for p in msg.walk()
                               if p.get_content_type() == 'text/plain')
            except Exception:                           # noqa: BLE001
                text = body
            m = re.search(r'\b(\d{6,8})\b', text)
            return m.group(1) if m else None
        time.sleep(0.5)
    return None


def sign_in(user, answers):
    """ssh with the key, then keyboard-interactive; answers: a function (prompt) -> what is typed.
    (in?, every prompt seen, all said)."""
    c = pexpect.spawn('ssh', ['-p', str(PORT), '-i', D + '/userkey', '-o', 'StrictHostKeyChecking=no',
                              '-o', 'UserKnownHostsFile=/dev/null', '-o', 'PreferredAuthentications=publickey,keyboard-interactive',
                              '-o', 'NumberOfPasswordPrompts=3', '%s@127.0.0.1' % user, 'echo SIGNED-IN-$((40+2))'],
                      encoding='utf-8', timeout=40)
    seen, said = [], ''
    while True:
        i = c.expect([r'@127\.0\.0\.1\) ([^\r\n]*[^\r\n ])[ \t]*$', 'SIGNED-IN-42', pexpect.EOF, pexpect.TIMEOUT])
        said += (c.before or '') + (c.after if isinstance(c.after, str) else '')
        if i == 0:
            time.sleep(0.3)
            prompt = c.match.group(1).strip()
            seen.append(prompt)
            if len(seen) > 6:
                c.close(force=True)
                return False, seen, said
            a = answers(prompt)
            if a is None:                       # given up: the window closed
                c.close(force=True)
                return False, seen, said
            c.sendline(a)
        elif i == 1:
            c.expect(pexpect.EOF)
            return True, seen, said
        else:
            return False, seen, said


# ---- a token of the app: one prompt, the code -----------------------------------------
good, seen, said = sign_in('sshapp', lambda p: code())
ok('an app\'s token: in with the code (prompts %s)' % seen, good, said)
ok('... one prompt only, saying it is a code - not "Password:"', len(seen) == 1 and seen[0] == 'Code from the app:', seen)
time.sleep(31)
good, seen, said = sign_in('sshapp', lambda p: '000000')
ok('... a wrong code: not in (prompts %s)' % seen, not good, said)
# ---- by mail: one prompt, the code mailed -----------------------------------------------
time.sleep(21)
before = set(glob.glob(D + '/mail/*.eml'))
CODE = {}


def mail_answer(p):
    if 'mail' in p.lower():
        CODE['c'] = CODE.get('c') or last_code(before)
        return CODE['c'] or 'none'
    return ''


good, seen, said = sign_in('sshmail', mail_answer)
ok('a token by mail: in with the code mailed (prompts %s, code %s)' % (seen, CODE.get('c')), good,
   said + ' | ' + open(D + '/d.out').read()[-600:])
ok('... one prompt only: the code mailed - no "Password:" before it', len(seen) == 1 and 'mail' in seen[0].lower(), seen)
# A mail come late: a second sign-in sends another code; the first one typed - still good.
time.sleep(21)
before = set(glob.glob(D + '/mail/*.eml'))
c1 = {}


def first(p):
    c1['c'] = c1.get('c') or last_code(before)
    return None                                 # this one given up: the window closed


sign_in('sshmail', first)
time.sleep(21)
before2 = set(glob.glob(D + '/mail/*.eml'))
c2 = {}


def late(p):
    if 'mail' in p.lower():
        c2['new'] = c2.get('new') or last_code(before2)
        return c1.get('c') or 'none'
    return ''


good, seen, said = sign_in('sshmail', late)
ok('a mail come late: the code of the sign-in before still let in (%s, a newer %s went too)' % (c1.get('c'), c2.get('new')),
   good and c1.get('c') and c2.get('new') and c1['c'] != c2['new'], said[-400:])
# At once again (within 20 s): no second mail - the one sent asked for again, and it lets in.
time.sleep(21)
before3 = set(glob.glob(D + '/mail/*.eml'))
c3 = {}


def give_up(p):
    c3['c'] = c3.get('c') or last_code(before3)
    return None


sign_in('sshmail', give_up)
n_mail = len(glob.glob(D + '/mail/*.eml'))
good, seen, said = sign_in('sshmail', lambda p: c3.get('c') or 'none')
ok('signed in again at once: the code that went asked for again, no second mail - in (%s)' % seen,
   good and len(glob.glob(D + '/mail/*.eml')) == n_mail, said[-400:])
ok('... the prompt says when the code went (%s)' % seen, seen and re.search(r'\(\d\d:\d\d\):$', seen[0]), seen)
# A code that ran out (a mail come too late): refused, and the event says so.
otp.Daemon(st, serve=False).save_settings({'code_ttl_s': 60}, by='test')
time.sleep(25)
before4 = set(glob.glob(D + '/mail/*.eml'))
c4 = {}


def first4(p):
    c4['c'] = c4.get('c') or last_code(before4)
    return None


sign_in('sshlate', first4)
time.sleep(70)
ONCE = []


def once(answer):
    def f(p):
        if ONCE:
            return None
        ONCE.append(1)
        return answer
    return f


good, seen, said = sign_in('sshlate', once(c4.get('c') or 'none'))
evs = [r['words'] for r in st.db.rows("SELECT words FROM events WHERE kind = 'ssh' ORDER BY id DESC LIMIT 3")]
ok('a code run out: not in, and the event says it ran out (%s)' % (evs[:1],), not good and any('ran out' in e for e in evs), evs)
ONCE.clear()
good, seen, said = sign_in('sshnone', once('000000'))
evs = [r['words'] for r in st.db.rows("SELECT words FROM events WHERE kind = 'ssh' ORDER BY id DESC LIMIT 3")]
ok('a code never sent: the event says none of the codes sent (%s)' % (evs[:1],), any('none of the codes' in e for e in evs), evs)
# Typed on a Czech keyboard without Shift: "794872" comes as "ýíčáýě" - taken as the digits.
CZ = dict(zip('1234567890', '+ěščřžýáíé'))
before5 = set(glob.glob(D + '/mail/*.eml'))
c5 = {}


def czech(p):
    c5['c'] = c5.get('c') or last_code(before5)
    return ''.join(CZ[x] for x in (c5['c'] or '000000'))


good, seen, said = sign_in('sshcz', czech)
ok('the code typed on a Czech keyboard\'s top row (%s): in' % ''.join(CZ[x] for x in (c5.get('c') or '0')), good, said[-300:])
ev = [r['words'] for r in st.db.rows("SELECT words FROM events WHERE kind = 'ssh' ORDER BY id")]
print('    events:', ev[-6:])
print('    sshd:', open(D + '/sshd.out').read()[-800:])
print('ALL %d / %d' % (sum(R), len(R)), flush=True)
