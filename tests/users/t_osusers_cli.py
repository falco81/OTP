# t_osusers_cli.py - otp --local-users / --local-user (1.0.243) on the installed otp, its root helper played by
# /tmp/claude-0/helperloop.sh: a user made with a password typed at a terminal (twice, never on the command line),
# sudo, locked, unlocked, a new password, taken away with its home; root refused; no terminal, no password.
import os, pty, subprocess, time, grp, sys
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:400] if more and not c else ''), flush=True)


def shadow(name):
    for ln in open('/etc/shadow'):
        p = ln.split(':')
        if p[0] == name:
            return p
    return None


def tty(argv, answers, wait=120):
    """argv run at a terminal, the answers typed when it asks."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(argv[0], argv)
    out, left, end = b'', list(answers), time.time() + wait
    while time.time() < end:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if left and (out.rstrip().endswith(b':') or out.rstrip().endswith(b': ')):
            os.write(fd, (left.pop(0) + '\n').encode())
            out += b'\n'
    _, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st), out.decode('utf-8', 'replace')


subprocess.run(['userdel', '-r', 'otpl_cli'], capture_output=True)
ADMIN = 'wheel' if subprocess.run(['getent', 'group', 'wheel'], capture_output=True).returncode == 0 else 'sudo'
PW = 'Cli-Pass-243-long'
rc, out = tty(['otp', '--local-user', 'add', 'otpl_cli', '--local-full-name', 'Cli Test', '--local-must-change'], [PW, PW])
ok('made from the command line, the password typed twice (%s)' % rc, rc == 0 and shadow('otpl_cli'), out[-400:])
ok('...its password the one typed, to change at the first sign-in', shadow('otpl_cli') and subprocess.run(
    ['openssl', 'passwd', '-6', '-salt', shadow('otpl_cli')[1].split('$')[2], '-stdin'], input=PW + '\n',
    capture_output=True, text=True).stdout.strip() == shadow('otpl_cli')[1] and shadow('otpl_cli')[2] == '0')
ok('...the password not on any command line (ps)', PW not in subprocess.run(['ps', '-eo', 'args'], capture_output=True, text=True).stdout)
r = subprocess.run(['otp', '--local-user', 'password', 'otpl_cli'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
ok('no terminal: no password taken (%s)' % r.returncode, r.returncode == 2 and 'terminal' in r.stdout, r.stdout)
r = subprocess.run(['otp', '--local-user', 'sudo-on', 'otpl_cli'], capture_output=True, text=True)
ok('sudo-on (%s)' % r.returncode, r.returncode == 0 and 'otpl_cli' in grp.getgrnam(ADMIN).gr_mem, r.stdout)
r = subprocess.run(['otp', '--local-users'], capture_output=True, text=True)
ok('--local-users: root view only, otpl_cli with sudo', 'view only' in r.stdout and any('otpl_cli' in ln and 'sudo' in ln for ln in r.stdout.splitlines()), r.stdout)
r = subprocess.run(['otp', '--local-user', 'lock', 'otpl_cli'], capture_output=True, text=True)
ok('lock (%s)' % r.returncode, r.returncode == 0 and shadow('otpl_cli')[1].startswith('!'), r.stdout)
r = subprocess.run(['otp', '--local-user', 'unlock', 'otpl_cli'], capture_output=True, text=True)
ok('unlock (%s)' % r.returncode, r.returncode == 0 and not shadow('otpl_cli')[1].startswith('!'), r.stdout)
r = subprocess.run(['otp', '--local-user', 'lock', 'root'], capture_output=True, text=True)
ok('root refused (%s)' % r.returncode, r.returncode == 1 and 'never changed' in r.stdout, r.stdout)
r = subprocess.run(['otp', '--local-user', 'sudo-off', 'otpl_cli'], capture_output=True, text=True)
ok('sudo-off', r.returncode == 0 and 'otpl_cli' not in grp.getgrnam(ADMIN).gr_mem, r.stdout)
rc, out = tty(['otp', '--local-user', 'drop-home', 'otpl_cli'], ['yes'])
ok('drop-home, asked at the terminal (%s)' % rc, rc == 0 and not shadow('otpl_cli') and not os.path.exists('/home/otpl_cli'), out[-300:])
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
