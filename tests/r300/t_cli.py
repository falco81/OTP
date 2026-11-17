"""t_cli.py - 1.0.300: otp --selinux-check lists ids, --selinux-fix ID|all puts right what may be (listing
first what root does), --selinux-rules, --selinux-take-away - the command line of the installed otp
through its root helper, SELinux faked (fakebin/).   python3 t_cli.py VERSION   (as root)
"""
import os, sys, json, time, shutil, subprocess, tempfile, atexit
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = tempfile.mkdtemp(prefix='otp-se300c-')
atexit.register(lambda: shutil.rmtree(TOP, True))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[-600:] if not c else ''), flush=True)


FAKE = TOP + '/se'
for d in (FAKE, TOP + '/lib', TOP + '/rootstate'):
    os.makedirs(d)
open(TOP + '/selinux-config', 'w').write('SELINUX=permissive\nSELINUXTYPE=targeted\n')
open(TOP + '/cmdline', 'w').write('ro\n')
shutil.copy('/usr/local/lib/otp/otp_server.cil', TOP + '/lib/otp_server.cil')
json.dump({'/run/otp': 'httpd_var_run_t', '/run/otp/api-token': 'httpd_var_run_t', '/var/www/otp': 'httpd_sys_content_t'},
          open(TOP + '/labels.json', 'w'))
json.dump({}, open(TOP + '/match.json', 'w'))
open(FAKE + '/mode', 'w').write('Permissive\n')
open(FAKE + '/modules', 'w').write('otp_server\n')
open(FAKE + '/bool_httpd_can_network_connect', 'w').write('on\n')
T = int(time.time()) - 600
title = '/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'.encode().hex().upper()
open(FAKE + '/avc', 'w').write(
    'type=AVC msg=audit(%d.001:901): avc:  denied  { nnp_transition } for  pid=9 comm="otp-tick" scontext=system_u:system_r:unconfined_service_t:s0 '
    'tcontext=system_u:system_r:ssh_keygen_t:s0 tclass=process2 permissive=1\n'
    'type=SYSCALL msg=audit(%d.001:901): arch=c000003e syscall=59 success=yes exit=0 pid=9 comm="otp-tick" exe="/usr/bin/python3.11" key=(null)\n'
    'type=PROCTITLE msg=audit(%d.001:901): proctitle=%s\n'
    'type=AVC msg=audit(%d.002:902): avc:  denied  { read } for  pid=10 comm="python3" name="shadow" scontext=system_u:system_r:unconfined_service_t:s0 '
    'tcontext=system_u:object_r:shadow_t:s0 tclass=file permissive=1\n'
    'type=PROCTITLE msg=audit(%d.002:902): proctitle=%s\n' % (T, T, T, title, T, T, title))
ENV = dict(os.environ, SEFAKE=FAKE, PATH=HERE + '/fakebin:' + os.environ['PATH'], OTP_SELINUX_CONFIG=TOP + '/selinux-config',
           OTP_SELINUX_RELABEL=TOP + '/.autorelabel', OTP_SELINUX_CMDLINE=TOP + '/cmdline', OTP_SELINUX_CIL=TOP + '/lib/otp_server.cil',
           OTP_SELINUX_LABELS=TOP + '/labels.json', OTP_SELINUX_MATCH=TOP + '/match.json', OTP_SELINUX_AUDITD='active',
           OTP_ROOT_STATE=TOP + '/rootstate', OTP_VIP_NO_SERVICES='1')


def otp(*a, stdin=None):
    p = subprocess.run(['otp'] + list(a), env=ENV, capture_output=True, text=True, timeout=300, input=stdin)
    return p.returncode, p.stdout + p.stderr


rc, out = otp('--selinux-check')
ids = [l.split()[0] for l in out.splitlines() if l.startswith('    ') and len(l.split()[0]) == 12]
ok('--selinux-check lists the ids, the fix and why not', len(ids) == 2 and '(allow unconfined_service_t ssh_keygen_t (process2 (nnp_transition)))' in out
   and 'security-sensitive' in out, out)
rc, out = otp('--selinux-fix', 'all')
ok('--selinux-fix without a terminal and without --yes: refused, nothing done', rc != 0 and '--yes' in out and not os.path.exists(TOP + '/lib/otp_local.cil'), out)
rc, out = otp('--selinux-fix', 'all', '--yes')
ok('--selinux-fix all --yes: what root does listed first, the rule put in', rc == 0 and 'root does exactly this' in out
   and 'otp_local' in out and 'nnp_transition' in open(TOP + '/lib/otp_local.cil').read(), out)
ok('...the one not for a button left alone', 'shadow' not in open(TOP + '/lib/otp_local.cil').read())
rc, out = otp('--selinux-rules')
rid = (out.split() or [''])[0]
ok('--selinux-rules lists it', rc == 0 and len(rid) == 12 and 'ssh_keygen_t' in out, out)
rc, out = otp('--selinux-fix', 'zzzzzzzzzzzz', '--yes')
ok('--selinux-fix of an id not refused here: said, nothing done', 'not refused here' in out, out)
rc, out = otp('--selinux-take-away', rid, '--yes')
ok('--selinux-take-away: the module out of the policy', rc == 0 and 'otp_local' not in open(FAKE + '/modules').read()
   and not os.path.exists(TOP + '/lib/otp_local.cil'), out)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
