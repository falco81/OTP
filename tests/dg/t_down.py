import os, sys, json, tempfile, shutil
V = sys.argv[1]
base = tempfile.mkdtemp(prefix='dg-', dir='/tmp/claude-0/dg')
lib = os.path.join(base, 'lib'); os.makedirs(lib)
shutil.copy('/home/claude/build/out/otp-%s/deploy/otp_upgrade.py' % V, lib)
os.makedirs(os.path.join(lib, 'release-keys'))
shutil.copy('/home/claude/build/out/otp-%s/deploy/release-keys/otp-release-1.pub' % V, os.path.join(lib, 'release-keys'))
shutil.copy('/home/claude/build/out/otp-%s/otp.py' % V, lib)
os.environ.update(OTP_STATE=os.path.join(base, 'state'), OTP_UPGRADE_HELPER=os.path.join(lib, 'otp_upgrade.py'),
                  OTP_LIB=lib, OTP_RELEASE_KEYS=os.path.join(lib, 'release-keys'))
os.makedirs(os.environ['OTP_STATE'])
sys.path.insert(0, '/home/claude/build/out/otp-%s' % V); sys.argv = ['x']
import otp
otp.CONFIG['db_engine'] = 'sqlite'
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
otp.UPGRADE_DIR.mkdir(exist_ok=True)
R = []
def ok(w, c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
# The floor of this version checked as it is, then the old releases used as
# packages to go back to with a floor of 1.0.139 as they had it (1.0.149
# raised it: nothing released before may be gone back to from it).
ok('this version does not go back below itself: %s' % otp.DOWNGRADE_FLOOR,
   otp.DOWNGRADE_FLOOR == V or otp._ver_tuple(otp.DOWNGRADE_FLOOR) >= (1, 0, 149))
otp.DOWNGRADE_FLOOR = '1.0.139'
otp.downgrade_floor_note(st)
print('  db floor', otp.downgrade_db_floor(st), 'root floor', otp.downgrade_root_floor())
w = otp.downgrade_why_not(st, '1.0.142')
ok('without the root floor file: refused', any('never upgraded' in x for x in w))
open(os.path.join(lib, 'downgrade-floor'), 'w').write('1.0.139\n')
ok('1.0.142 allowed', otp.downgrade_why_not(st, '1.0.142') == [])
ok('1.0.139 allowed', otp.downgrade_why_not(st, '1.0.139') == [])
ok('1.0.138 refused (floor)', otp.downgrade_why_not(st, '1.0.138') != [])
ok('%s itself refused (not older)' % V, otp.downgrade_why_not(st, V) != [])
# a later version that raised the floor ran here
st.set_meta('downgrade:floor:othernode', json.dumps({'floor': '1.0.141', 'version': '1.0.150'}))
w = otp.downgrade_why_not(st, '1.0.140')
ok('a floor another node wrote counts: 1.0.140 refused', w and '1.0.141' in w[0]); print('   ', w)
st.db.run("DELETE FROM meta WHERE k = 'downgrade:floor:othernode'")
open(os.path.join(lib, 'downgrade-floor'), 'w').write('1.0.141\n')
ok('root floor 1.0.141: 1.0.140 refused', otp.downgrade_why_not(st, '1.0.140') != [])
open(os.path.join(lib, 'downgrade-floor'), 'w').write('1.0.139\n')
# the package and the tables
pkg = '/home/claude/otp/release/otp-1.0.142.tar.gz'
ok('the tables of 1.0.142 read off its otp.py', 'tokens' in otp.downgrade_package_schema(pkg)['tables'])
ok('this database can take 1.0.142', otp.downgrade_schema_why(st, pkg) == [])
st.db.run("ALTER TABLE tokens ADD COLUMN must_have TEXT NOT NULL DEFAULT 'x'")
ok('a NOT NULL column with a default is fine', otp.downgrade_schema_why(st, pkg) == [])
# sqlite cannot drop a default: a table of its own the old version knows, made strict
st.db.run('DROP TABLE token_once'); st.db.run('CREATE TABLE token_once (k TEXT PRIMARY KEY, node TEXT, ts REAL, newer_col TEXT NOT NULL)')
w = otp.downgrade_schema_why(st, pkg)
ok('a NOT NULL column without a default it does not know: refused', w and 'newer_col' in w[0]); print('   ', w)
st.db.run('DROP TABLE token_once'); st.db.make_tables()
# fetch from a file: the whole road, kept as a package to go back to
meta = otp.downgrade_file(st, pkg, 'test')
ok('kept as a package to go back to', meta['version'] == '1.0.142' and json.loads(st.get_meta('upgrade:pkg'))['downgrade'])
okk, why = otp.upgrade_checks(st, json.loads(st.get_meta('upgrade:pkg')))
ok('upgrade_checks lets it start: %s' % why, okk)
plan = otp.upgrade_start(st, 'test')
ok('the plan says downgrade', json.loads(st.get_meta('upgrade:plan'))['downgrade'] is True)
try:
    otp.downgrade_file(st, '/home/claude/otp/release/otp-1.0.138.tar.gz', 'test'); ok('1.0.138 file refused', False)
except ValueError as e:
    ok('1.0.138 file refused', True); print('   ', e)
print('ALL' if all(R) else 'SOME FAILED', sum(R), '/', len(R))
