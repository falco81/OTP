# t_hisec_sshcode.py VERSION - high security and the code from otp over SSH (1.0.242): keyboard-interactive is otp's
# code, not a password, where otp asks for it with no system password to fall back on - "SSH lets people in with a
# password" and "root may sign in over SSH with a password" not said then; said with the system password allowed.
import os, sys, json, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.242'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-hsc-'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'hs1'}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def bad(ident):
    return [r for r in otp.hisec_rules(st) if r.get('rule') == ident and r.get('bad')]


me = otp.node_name()
def now(**v):
    st.set_meta('host:sshd:now:' + me, json.dumps({'values': dict({'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no',
                                                                  'permitrootlogin': 'prohibit-password', 'maxauthtries': '4'}, **v)}))


def conf(**c):
    st.set_meta('host:sshd:conf', json.dumps(dict({'manage': True, 'password': False, 'permit_root': 'prohibit-password', 'tries': 4,
                                                   'radius': False, 'radius_fallback': False}, **c)))


conf(); now()
ok('keys only: nothing said', not bad('sshd:password') and not bad('sshd:root'))
conf(radius=True, radius_root=True, radius_with_key=True)
now(kbdinteractiveauthentication='yes', permitrootlogin='yes', authenticationmethods='publickey,keyboard-interactive')
ok('a key and then the code from otp, root too (keyboard-interactive, PermitRootLogin yes): no password - not said',
   not bad('sshd:password') and not bad('sshd:root'), [r.get('rule') for r in otp.hisec_rules(st) if r.get('bad')])
conf(radius=True, password=True, radius_fallback=True)
now(kbdinteractiveauthentication='yes', passwordauthentication='yes', permitrootlogin='yes')
ok('the system password when otp does not answer: said - a password lets in', bad('sshd:password') and bad('sshd:root'))
conf(radius=False)
now(kbdinteractiveauthentication='yes', permitrootlogin='yes')
ok('keyboard-interactive without the code from otp: a password - said', bad('sshd:password') and bad('sshd:root'))
conf(); now(passwordauthentication='yes', permitrootlogin='prohibit-password')
ok('passwords, root with a key only: passwords said, root not', bad('sshd:password') and not bad('sshd:root'))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
