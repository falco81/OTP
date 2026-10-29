import os, sys, tempfile, shutil
V = sys.argv[1]
base = tempfile.mkdtemp(prefix='dgr-', dir='/tmp/claude-0/dg')
lib = os.path.join(base, 'lib'); os.makedirs(os.path.join(lib, 'release-keys'))
shutil.copy('/home/claude/build/out/otp-%s/otp.py' % V, lib)
shutil.copy('/home/claude/build/out/otp-%s/deploy/release-keys/otp-release-1.pub' % V, os.path.join(lib, 'release-keys'))
os.environ.update(OTP_LIB=lib, OTP_STATE=os.path.join(base, 'state'))
os.makedirs(os.path.join(base, 'state', 'upgrade'))
sys.path.insert(0, '/home/claude/build/out/otp-%s/deploy' % V)
import otp_upgrade as U
R = []
def ok(w, c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
import glob as _g
OLD = sorted((os.path.basename(x)[4:-7] for x in _g.glob('/home/claude/otp/release/otp-1.0.1*.tar.gz')),
             key=lambda v: tuple(int(x) for x in v.split('.')))[0]   # the oldest kept there
ABOVE = '1.0.%d' % (int(OLD.split('.')[2]) + 1)
pkg = '/home/claude/otp/release/otp-%s.tar.gz' % OLD
def run(down):
    try:
        rc, info, lines = U.put_in(pkg, downgrade=down)
        return 'ran install.sh rc=%s: %s' % (rc, ' | '.join(lines[-3:]))
    except U.Refused as e:
        return 'refused: %s' % e
r = run(False); ok('older without asking: refused', r.startswith('refused') and 'going back is asked' in r); print('   ', r)
r = run(True); ok('asked, no floor file: refused', r.startswith('refused') and 'no floor' in r); print('   ', r)
f = os.path.join(lib, 'downgrade-floor')
open(f, 'w').write(OLD + '\n'); os.chmod(f, 0o666)
r = run(True); ok('floor file others may write: no floor', 'no floor' in r)
os.chmod(f, 0o644); open(f, 'w').write(ABOVE + '\n')
r = run(True); ok('below the floor: refused', r.startswith('refused') and 'oldest the versions' in r); print('   ', r)
open(f, 'w').write(OLD + '\n')
r = run(True); ok('asked and allowed: on to install.sh', r.startswith('ran install.sh')); print('   ', r[:400])
print('ALL' if all(R) else 'SOME FAILED', sum(R), '/', len(R))
