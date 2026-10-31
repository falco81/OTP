# t_console.py VERSION - the console (otp --console) on one server of its own: every menu
# opened and left again, each read-only screen of each, and the new ones of 1.0.187
# (certificates, updates, restarts, tests, SSH tokens, lockouts) - none ending in a
# traceback or a dead screen; a token made through it seen by the command line.
# Usage (root): python3 t_console.py VERSION
import os, sys, json, time, subprocess, tempfile, atexit, re
PY = '/usr/bin/python3'          # otp's own Python; this test may run in a venv with pexpect, pyte
import pexpect, pyte

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.187'
V = '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-con-')
for d in ('run', 'web', 'log'):
    os.makedirs(TOP + '/' + d)
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36912, 'radius_acct_port': 36913,
           'api_port': 36980, 'node_name': 'connode'}, open(TOP + '/config.json', 'w'))
ENV = dict(os.environ, OTP_STATE=TOP, OTP_CONFIG=TOP + '/config.json', OTP_LOGDIR=TOP + '/log', OTP_RUN=TOP + '/run',
           OTP_STAY_ROOT='1', OTP_CONSOLE_FLAG=TOP + '/console-login', OTP_POWER_CMD=TOP + '/power',
           TERM='xterm', LANG='C.UTF-8', OTP_CONSOLE_START='menu')   # not the live log it opens with
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % (str(more)[:900],)) if more and not cond else ''),
          flush=True)


def cli(*a, env=None):
    return subprocess.run([PY, '-I', V + '/otp.py', '--no-color'] + list(a), env=dict(ENV, **(env or {})),
                          capture_output=True, text=True, timeout=120)


cli('--add-user', 'conadmin', '--role', 'fulladmin', env={'OTP_PASSWORD': 'Con-Admin-Pass-187!'})
d = subprocess.Popen([PY, '-I', V + '/otp.py', '--daemon'], env=ENV, stdout=open(TOP + '/d.out', 'w'),
                     stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
cli('--enroll', 'novak', '--no-qr')
scr = pyte.Screen(120, 40)
st = pyte.ByteStream(scr)
c = pexpect.spawn(PY, ['-I', V + '/otp.py', '--console'], env=ENV, timeout=30, dimensions=(40, 120))
SEEN = []


def pump(t=1.0):
    end = time.time() + t
    while time.time() < end:
        try:
            st.feed(c.read_nonblocking(65536, timeout=0.2))
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            break


def text():
    return '\n'.join(line.rstrip() for line in scr.display)


def screen_ok(what, want=None, t=2.0):
    """The screen after a key: no traceback, something drawn, what is wanted on it."""
    end = time.time() + t + 25
    pump(t)
    while want and not re.search(want, text(), re.S) and time.time() < end:
        pump(1)
    s = text()
    SEEN.append((what, s))
    good = 'Traceback' not in s and s.strip() and (not want or re.search(want, s, re.S))
    ok(what, good, s[-900:])
    return s


def key(k, t=1.0):
    c.send(k)
    pump(t)


screen_ok('the main menu', 'Certificates, updates, restarts, tests', 3)
MAIN = ['Status and checks', 'Tokens', 'Accounts of the administration', 'Settings',
        'RADIUS clients, realms and directories', 'Cluster, VIP address and maintenance', 'Backups', 'Upgrades',
        'The service', 'Certificates, updates, restarts, tests',
        'Encryption, sending out, time, network, high security']
NUM = {'Status and checks': '1', 'Tokens': '4', 'Accounts of the administration': '5', 'Settings': '6',
       'RADIUS clients, realms and directories': '7', 'Cluster, VIP address and maintenance': '8', 'Backups': '9',
       'Upgrades': '10', 'The service': '11', 'Certificates, updates, restarts, tests': '12',
       'Encryption, sending out, time, network, high security': '13'}


def pick(num, many):
    """A number typed as one does: chosen at once when no longer one can grow from it,
    else with Enter (1 of a menu with a 10)."""
    for ch in num:
        key(ch, 0.25)
    if any(str(n).startswith(num) and str(n) != num for n in range(many + 1)):
        key('\r', 1.5)
    else:
        pump(1.5)


SIZE = {'Status and checks': 5, 'RADIUS clients, realms and directories': 6,
        'Cluster, VIP address and maintenance': 7, 'Upgrades': 7, 'Certificates, updates, restarts, tests': 15,
        'Encryption, sending out, time, network, high security': 15}


def open_menu(name):
    pick(NUM[name], 13)
    return screen_ok('menu: %s' % name, re.escape(name))


def at_main():
    return re.search(r'(?m)^\s*Main menu\s*$', text()) and '12  Certificates' in text()


def back_main():
    for _ in range(5):
        if at_main():
            return
        key('\x1b', 1.0)


for m in MAIN:
    open_menu(m)
    back_main()
    screen_ok('... back in the main menu from %s' % m, r'(?m)^\s*Main menu\s*$')


def item(menu, num, want, what):
    open_menu(menu)
    pick(num, SIZE[menu])
    s = screen_ok('%s → %s' % (menu, what), want, 3)
    key('\r', 1)
    key('\x1b', 1)
    back_main()
    return s


item('Status and checks', '1', 'connode', 'Status')
item('Status and checks', '2', '(?i)database', 'Checks')
item('RADIUS clients, realms and directories', '3', '(?i)realm|nothing', 'Realms')
item('Cluster, VIP address and maintenance', '1', '(?i)node|cluster', 'The cluster')
item('Upgrades', '1', '(?i)upgrade|package|nothing', 'How it stands')
OPS = 'Certificates, updates, restarts, tests'
item(OPS, '1', '(?i)ACME|off', 'ACME status')
item(OPS, '3', 'connode', 'updates status')
item(OPS, '7', 'connode', 'restarts')
item(OPS, '11', '(?i)account|none', 'SSH tokens')
item(OPS, '14', '(?i)kind|none', 'lockouts')
MORE = 'Encryption, sending out, time, network, high security'
item(MORE, '1', '(?i)sqlite|kind|mode', 'DB TLS status')
item(MORE, '11', 'connode', 'the time')
item(MORE, '13', '(?i)node|connode', 'the network')
item(MORE, '14', '(?i)high security', 'high security')
# An SSH token made through the console: seen by the command line.
open_menu(OPS)
pick('12', 15)
screen_ok('make an SSH token: its form', '(?i)account')
c.send('opsuser')
pump(0.5)
key('\r', 1)
for _ in range(4):
    if 'opsuser' in cli('--ssh-tokens').stdout:
        break
    key('\r', 2)
s = screen_ok('... made, its key shown', '(?i)key|scan it now', 3)
ok('... the command line sees it', 'opsuser' in cli('--ssh-tokens').stdout, cli('--ssh-tokens').stdout)
key('\r', 1)
key('\x1b', 1)
back_main()
key('q', 1.5)
pump(2)
ok('the console closed by q', not c.isalive() or 'closed' in text(), text()[-400:])
print('    folder:', TOP)
print('ALL %d / %d' % (sum(R), len(R)), flush=True)
