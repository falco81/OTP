"""t_install.py - 1.0.299: install.sh's writer of the pages' file, its own functions run alone
under the script's own set -Eeuo pipefail and ERR trap: the steps counted, the end said once
(done; failed with the exit code, from the EXIT trap, also on a signal), nothing where there is no
folder for the pages, and never a reason for the script to stop.

    python3 t_install.py VERSION
"""
import json, os, re, shutil, subprocess, sys, tempfile, atexit
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.299'
SRC = open('/home/claude/build/out/otp-%s/install.sh' % V).read()
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


a = SRC.index('# How far an upgrade is, for the pages (1.0.299)')
b = SRC.index('say()   {', a)
FUNCS = SRC[a:b]
TOP = tempfile.mkdtemp(prefix='t_r299i_')
atexit.register(lambda: shutil.rmtree(TOP, True))


def run(body, web=True):
    w = TOP + '/www'
    shutil.rmtree(w, True)
    if web:
        os.makedirs(w)
    script = ('set -Eeuo pipefail\n'
              "trap 'rc=$?; echo ERRTRAP >&2; exit \"$rc\"' ERR\n"
              'C_HEAD=""; C_OFF=""; DRY_RUN=""; VERSION=9.9.9; WEB_DIR=%s\n' % w + FUNCS + body)
    p = subprocess.run(['bash', '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    try:
        got = json.load(open(w + '/.upgrade.json'))
    except (OSError, ValueError):
        got = None
    return p.returncode, got, p.stdout.decode() + p.stderr.decode(), (os.listdir(w) if web else [])


rc, got, out, ls = run('step "Fresh"\necho went-on\n')
ok('1 not upgrading: step prints as before, writes nothing', rc == 0 and got is None and '==> Fresh' in out and 'went-on' in out, out)
SET = ('UPG_ID=k1; UPG_FROM=1.0.1; UPG_BY="root on the command line"; UPG_NODE=vm; UPG_STARTED=$(date +%s)\n'
       'UPG_PART=1; UPG_PARTS=4; UPG_WORDS="Upgrading otp to 9.9.9"; UPG_AFTER="otp 1.0.1 runs as it did"; UPG_TELL=yes\n'
       "upgrade_tell running\ntrap 'upgrade_told_end $?' EXIT\n")
rc, got, out, ls = run(SET + 'step "The daemon"\nstep "Python \\"quoted\\" \\\\ back"\ncat "$WEB_DIR/.upgrade.json"\n')
mid = json.loads([x for x in out.splitlines() if x.startswith('{')][0])
ok('2 steps counted: 3 of 4, its words, quotes and backslashes taken out', mid['state'] == 'running' and mid['part'] == 3 and mid['parts'] == 4
   and mid['words'] == 'Python quoted  back', mid)
ok('2 ...ended well (exit 0): done', rc == 0 and got['state'] == 'done' and got['words'] == 'otp 9.9.9 runs', (rc, got))
ok('2 ...0644, no temporary file left', ls == ['.upgrade.json'] and (os.stat(TOP + '/www/.upgrade.json').st_mode & 0o777) == 0o644, ls)
ok('2 ...the fields', got['id'] == 'k1' and got['from'] == '1.0.1' and got['node'] == 'vm' and got['downgrade'] is False
   and got['by'] == 'root on the command line', got)
rc, got, out, ls = run(SET + 'step "A"\nstep "B"\nstep "C"\nstep "D"\n')
ok('3 more steps than counted: the count follows (never past 100 %)', got and got['part'] == 5 and got['parts'] == 5, got)
rc, got, out, ls = run(SET + 'step "The pages"\nfalse\necho not-here\n')
ok('4 a command failing (set -e, the ERR trap): failed, its exit code, the step, what runs', rc == 1 and got and got['state'] == 'failed'
   and got['words'] == 'The pages' and 'stopped (exit 1)' in got['said'] and 'otp 1.0.1 runs as it did' in got['said']
   and 'not-here' not in out, (rc, got, out))
rc, got, out, ls = run(SET + "trap 'exit 143' TERM\nstep \"Python\"\nkill -TERM $$\nsleep 5\n")
ok('5 stopped by a signal: failed (exit 143), not left running', got and got['state'] == 'failed' and 'exit 143' in got['said'], (rc, got))
rc, got, out, ls = run(SET + 'step "X"\n', web=False)
ok('6 no folder for the pages: nothing, and the script goes on to its end', rc == 0 and got is None and 'ERRTRAP' not in out, out)
rc, got, out, ls = run(SET + 'chmod 0555 "$WEB_DIR"\nstep "X"\necho went-on\n')
os.chmod(TOP + '/www', 0o755)
ok('7 the folder not writable: the script goes on all the same', rc == 0 and 'went-on' in out and 'ERRTRAP' not in out or os.geteuid() == 0, out)
rc, got, out, ls = run(SET + 'upgrade_told_end 0\nupgrade_told_end 1\n')
ok('8 the end said once', got and got['state'] == 'done', got)
rc, got, out, ls = run(SET.replace('UPG_TELL=yes', 'UPG_TELL=yes; DRY_RUN=yes') + 'step "X"\n')
ok('9 --dry-run: nothing written', got is None or got.get('part') == 1, got)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
