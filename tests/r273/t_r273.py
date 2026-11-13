# t_r273.py VERSION - 1.0.273 (otp.py loaded as a module, a private state folder):
#  - the SSH server saved with AllowUsers that leaves root out (root by key, by password,
#    or not at all), and the helper's sshd file written with that AllowUsers;
#  - Your account: the new password typed twice (the page, checked in its code).
import atexit, importlib.util, json, os, shutil, sys, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.273'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t273-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx273', 'api_port': 29974}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())

for root in ('prohibit-password', 'yes', 'no'):
    try:
        c = m.sshd_save(st, {'manage': True, 'permit_root': root, 'allow_users': ['falco'], 'port': 22,
                             'max_tries': 4, 'trial_min': 5}, 'admin')
        kept = json.loads(st.get_meta('host:sshd:conf') or '{}')
        ok('AllowUsers falco, root %s: saved' % root, kept.get('allow_users') == ['falco']
           and kept.get('permit_root') == root, kept)
    except ValueError as e:
        ok('AllowUsers falco, root %s: saved' % root, False, e)
c = m.sshd_save(st, {'manage': True, 'permit_root': 'prohibit-password', 'allow_users': ['falco', 'root'],
                     'port': 22}, 'admin')
ok('AllowUsers falco root: saved as before', c['allow_users'] == ['falco', 'root'], c)
c = m.sshd_save(st, {'manage': True, 'permit_root': 'prohibit-password', 'allow_users': [], 'port': 22}, 'admin')
ok('no AllowUsers (everybody): saved as before', c['allow_users'] == [], c)
ev = st.db.rows("SELECT words FROM events WHERE words LIKE '%AllowUsers falco%'") if hasattr(st, 'db') else []
ok('the event says AllowUsers falco', any('AllowUsers falco' in (r.get('words') or '') for r in ev), ev[:2])
ok('the refusal is gone from the code', 'lets nobody in as root' not in open(V + '/otp.py').read())

# the root helper writes the line as it is
WEB = V + '/deploy/otp_web.py'
spec2 = importlib.util.spec_from_file_location('otp_web_t', WEB)
w = importlib.util.module_from_spec(spec2)
try:
    spec2.loader.exec_module(w)
    fn = [n for n in dir(w) if n.startswith('sshd_') and 'conf' in n]
    ok('the helper loaded', True)
except SystemExit:
    ok('the helper loaded', True)
src = open(WEB).read()
ok('the helper writes AllowUsers from the list, root not added', "lines.append('AllowUsers %s' % ' '.join(c['allow_users']))" in src)

JS = open(V + '/web/assets/admin.js').read()
ok('Your account: "The new one again"', "formField('The new one again', nw2)" in JS and "me-pw-new2" in JS)
ok('Your account: the two must be the same before sending',
   "if (nw.value !== nw2.value) { toast('the two new ones are not the same', 'bad'); nw2.focus(); return; }" in JS)
ok('Your account: the one you have now must be typed', "type the password you have now first" in JS)
ok('SSH help says root left out signs in at the console', 'Root left out of the list signs in only at the console.' in JS)
print('ALL %d / %d' % (sum(R), len(R)))
