"""t_fix.py - 1.0.303: the upgrade (hunt round 2) - install.sh's EXIT trap says "failed" also when the
rescue's maintenance off fails (set -Eeuo pipefail); root's helper keeps what install.sh said when it
stopped it; a cookie of the right form learns nothing of who asked or why it failed; the sign-in page's
"failed" line one sentence.   python3 t_fix.py VERSION     (as root; the installed pages for the PHP part)
"""
import os, sys, json, re, time, shutil, subprocess, tempfile, atexit, importlib.util
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.303'
OUT = '/home/claude/build/out/otp-%s' % V
TOP = tempfile.mkdtemp(prefix='t_r303_')
atexit.register(lambda: shutil.rmtree(TOP, True))
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


# ==== 1 install.sh: the rescue's maintenance off fails - the file says failed all the same
sh = open(OUT + '/install.sh').read()
a = sh.index('# How far an upgrade is, for the pages (1.0.299)')
funcs = sh[a:sh.index('say()   {', a)]
r0 = sh.index('    upgrade_rescue() {')
r1 = sh.index('\n    }\n', r0) + 7
rescue = sh[r0:r1]
trap = re.search(r"\n(    trap 'upg_rc=\$\?;[^\n]*' EXIT)\n", sh).group(1)
w = TOP + '/www'
os.makedirs(w)
script = ('set -Eeuo pipefail\n'
          "trap 'rc=$?; echo ERRTRAP >&2; exit \"$rc\"' ERR\n"
          'C_HEAD=""; C_OFF=""; DRY_RUN=""; VERSION=9.9.9; WEB_DIR=%s\n' % w + funcs +
          'warn() { echo "warn: $1"; }\nsystemctl() { return 0; }\notp_stays_up() { return 1; }\n'
          'upgrade_put_old_back() { return 1; }\nas_otp() { return 1; }\nsleep() { :; }\n'
          'UPGRADE_STAGE=started; UPGRADE_PROGRAM=new; MAINT_BY_US=yes\n'
          'UPG_ID=k1; UPG_FROM=1.0.1; UPG_BY=root; UPG_NODE=vm; UPG_STARTED=$(date +%s); UPG_PART=3; UPG_PARTS=8\n'
          'UPG_WORDS="The daemon"; UPG_AFTER="x"; UPG_TELL=yes\nupgrade_tell running\n' + rescue + '\n' + trap + '\nfalse\n')
p = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=60)
try:
    got = json.load(open(w + '/.upgrade.json'))
except (OSError, ValueError):
    got = {}
ok('1 an upgrade by hand that failed, the maintenance not going off: the file says failed (it stayed running)',
   got.get('state') == 'failed' and 'exit 1' in got.get('said', ''), (got, p.stdout[-300:], p.stderr[-300:]))

# ==== 2 otp_upgrade.py: install.sh stopped at the deadline - what it said kept
os.environ.update(OTP_STATE=TOP + '/state', OTP_LIB=TOP + '/lib', OTP_PAGES_UPGRADE=TOP + '/pages/.upgrade.json')
os.makedirs(TOP + '/state/upgrade')
os.makedirs(TOP + '/lib')
os.makedirs(TOP + '/pages')
os.chmod(TOP + '/pages', 0o755)
spec = importlib.util.spec_from_file_location('otp_upgrade', OUT + '/deploy/otp_upgrade.py')
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)
U.write_safely = lambda path, data, mode=0o640: open(path, 'w' if isinstance(data, str) else 'wb').write(data)


def put_in(package, ident='', want_sha='', by='', log_to=None, downgrade=False, started=None):
    U.pages_tell('failed', ident, '9.9.9', part=6, parts=9, words='The service restarts',
                 said='install.sh --upgrade stopped (exit 143) - otp 1.0.1 runs again', started=started)
    raise U.Refused('install.sh did not finish in 20 min and was stopped')


U.put_in = put_in
open(TOP + '/state/upgrade/request.json', 'w').write(json.dumps({'id': 'k9', 'file': 'otp-9.9.9.tar.gz', 'version': '9.9.9', 'by': 'admin'}))
U.serve_request()
f = json.load(open(TOP + '/pages/.upgrade.json'))
ok('2 install.sh stopped by root\'s deadline: its step and what runs now kept, not "root checks the package"',
   f.get('state') == 'failed' and f.get('part') == 6 and f.get('words') == 'The service restarts' and 'runs again' in f.get('said', ''), f)
os.unlink(TOP + '/pages/.upgrade.json')
open(TOP + '/state/upgrade/request.json', 'w').write(json.dumps({'id': 'k10', 'file': 'otp-9.9.9.tar.gz', 'version': '9.9.9', 'by': 'admin'}))
U.put_in = lambda *a, **k: (_ for _ in ()).throw(U.Refused('the package is not signed'))
U.serve_request()
f = json.load(open(TOP + '/pages/.upgrade.json'))
ok('2 refused before install.sh began: failed at root\'s check, as before', f.get('state') == 'failed' and f.get('words') == 'root checks the package'
   and 'not signed' in f.get('said', ''), f)

# ==== 3 the pages: a cookie of the right form learns nothing more
F = '/var/www/otp/.upgrade.json'
try:
    open(F + '.t', 'w').write(json.dumps({'state': 'failed', 'id': 'k1', 'version': '9.9.9', 'from': '1.0.1', 'by': 'admin on the pages',
                                          'node': 'vm', 'part': 6, 'parts': 9, 'words': 'x', 'started': int(time.time()) - 60,
                                          'at': int(time.time()), 'said': 'SECRETWHY', 'downgrade': False}))
    os.chmod(F + '.t', 0o644)
    os.replace(F + '.t', F)
    out = subprocess.run(['curl', '-sk', '-m', '10', '-H', 'Cookie: otp_session=AAAAAAAAAAAAAAAAAAAA',
                          'https://127.0.0.1/admin/?api=upgrade-state'], capture_output=True, text=True).stdout
    ok('3 ?api=upgrade-state with a made-up cookie: no "by", no "said", no id', '9.9.9' in out and 'admin on the pages' not in out
       and 'SECRETWHY' not in out and '"id"' not in out, out)
    page = subprocess.run(['curl', '-sk', '-m', '10', '-H', 'Cookie: otp_session=AAAAAAAAAAAAAAAAAAAA', 'https://127.0.0.1/admin/'],
                          capture_output=True, text=True).stdout
    ok('3 the sign-in page: "The upgrade to otp 9.9.9 failed" as one sentence, not why', 'The upgrade to otp 9.9.9 failed' in page
       and 'SECRETWHY' not in page, re.findall(r'.{0,80}9\.9\.9.{0,80}', page)[:2])
finally:
    try:
        os.unlink(F)
    except OSError:
        pass
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
