"""t_fix.py - 1.0.302: SELinux, the root helper (fakebin/ of r300): another program's refusal on otp's files
is never a rule (whatever it calls itself); restorecon only on otp's own real paths (no "..", no link);
otp_local's list written only once the policy took it (a failed take-away keeps the rule listed); a
batch whose module does not load keeps its other fixes; a port of the right type already is done.

    python3 t_fix.py VERSION      (as root)
"""
import os, sys, json, time, shutil, tempfile, atexit, importlib.util
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.302'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
FB = os.path.join(os.path.dirname(HERE), 'r300', 'fakebin')
TOP = tempfile.mkdtemp(prefix='otp-se302-')
atexit.register(lambda: shutil.rmtree(TOP, True))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:500] if not c else ''), flush=True)


FAKE = TOP + '/se'
for d in (FAKE, TOP + '/lib', TOP + '/rootstate', TOP + '/hstate/web'):
    os.makedirs(d)
open(TOP + '/selinux-config', 'w').write('SELINUX=permissive\nSELINUXTYPE=targeted\n')
open(TOP + '/cmdline', 'w').write('ro\n')
shutil.copy(V + '/deploy/otp_server.cil', TOP + '/lib/otp_server.cil')
# otp's own folder for the paths: a real one, a link inside it leading out
W = '/var/www/otp/assets'
LINK = '/var/www/otp/.t302-link'
try:
    os.symlink('/tmp', LINK)
except FileExistsError:
    pass
atexit.register(lambda: os.path.islink(LINK) and os.unlink(LINK))
json.dump({W + '/core.js': 'default_t'}, open(TOP + '/labels.json', 'w'))
json.dump({W + '/core.js': 'httpd_sys_content_t', W + '/../../../srv': 'httpd_sys_content_t',
           LINK: 'httpd_sys_content_t'}, open(TOP + '/match.json', 'w'))
os.environ.update({'SEFAKE': FAKE, 'PATH': FB + ':' + os.environ['PATH'], 'OTP_SELINUX_CONFIG': TOP + '/selinux-config',
                   'OTP_SELINUX_RELABEL': TOP + '/.autorelabel', 'OTP_SELINUX_CMDLINE': TOP + '/cmdline',
                   'OTP_SELINUX_CIL': TOP + '/lib/otp_server.cil', 'OTP_SELINUX_LABELS': TOP + '/labels.json',
                   'OTP_SELINUX_MATCH': TOP + '/match.json', 'OTP_SELINUX_AUDITD': 'active', 'OTP_STATE': TOP + '/hstate',
                   'OTP_ROOT_STATE': TOP + '/rootstate', 'OTP_VIP_NO_SERVICES': '1'})
open(FAKE + '/mode', 'w').write('Permissive\n')
open(FAKE + '/modules', 'w').write('otp_server\n')
open(FAKE + '/ports', 'w').write('ssh_port_t                     tcp      22\n')
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
Wm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Wm)
WANT = {'booleans': [], 'ports': [{'port': 2222, 'proto': 'tcp', 'type': 'ssh_port_t', 'why': 'sshd'}], 'facts': {}}
T0 = int(time.time()) - 3600
N = [0]


def ev(avc, comm, exe, path=None, title=None):
    N[0] += 1
    a = 'msg=audit(%d.%03d:%d):' % (T0 + N[0], N[0], 700 + N[0])
    out = ['type=AVC %s avc:  denied  %s' % (a, avc),
           'type=SYSCALL %s arch=c000003e syscall=257 success=no exit=-13 pid=%d comm="%s" exe="%s" key=(null)' % (a, N[0], comm, exe)]
    if path:
        out.append('type=PATH %s item=0 name="%s" inode=1' % (a, path))
    out.append('type=PROCTITLE %s proctitle=%s' % (a, (title or exe).encode().hex().upper()))
    return '\n'.join(out)


def avc(perms, st, tt, cls, extra=''):
    return '{ %s } for  pid=1 %s scontext=system_u:system_r:%s:s0 tcontext=system_u:object_r:%s:s0 tclass=%s permissive=1' % (
        perms, extra, st, tt, cls)


OTP = '/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'
LOG = [
    ev(avc('read open', 'user_t', 'httpd_var_run_t', 'file', 'name="api-token"'), 'cat', '/usr/bin/cat', '/run/otp/api-token'),
    ev(avc('read', 'named_t', 'httpd_var_run_t', 'file', 'name="api-token"'), 'otp-x', '/usr/sbin/named', '/run/otp/api-token', 'otp.py'),
    ev(avc('getattr', 'unconfined_service_t', 'shadow_t', 'file', 'name="x"'), 'otp-fake', '/usr/bin/python3', '/srv/x', '/srv/otp.py run'),
    ev(avc('read', 'httpd_t', 'default_t', 'file', 'name="core.js"'), 'nginx', '/usr/sbin/nginx', W + '/core.js'),
    ev(avc('read', 'httpd_t', 'default_t', 'dir', 'name="srv"'), 'php-fpm', '/usr/sbin/php-fpm', W + '/../../../srv'),
    ev(avc('read', 'httpd_t', 'default_t', 'lnk_file', 'name=".t302-link"'), 'php-fpm', '/usr/sbin/php-fpm', LINK),
    ev(avc('name_bind', 'sshd_t', 'unreserved_port_t', 'tcp_socket', 'src=2222'), 'sshd', '/usr/sbin/sshd'),
    ev(avc('nnp_transition', 'unconfined_service_t', 'ping_t', 'process2'), 'otp-tick', '/usr/bin/python3.11', None, OTP),
]
open(FAKE + '/avc', 'w').write('\n'.join(LOG) + '\n')


def do(what, **extra):
    try:
        return Wm.se_do(dict(WANT, do=what, **extra)), ''
    except Wm.Refused as e:
        return None, str(e)


c, e = do('check')
F = {(f['source'], f['target'], f['class']): f for f in (c or {}).get('findings') or []}
ok('a look: no error', c is not None, e)
x = F.get(('user_t', 'httpd_var_run_t', 'file')) or {}
ok('user_t reading the API token: another program\'s, never a rule', x.get('kind') == 'other' and not x.get('fix'), x)
x = F.get(('named_t', 'httpd_var_run_t', 'file')) or {}
ok('named_t calling itself "otp-x", "otp.py" on its command line: another program\'s', x.get('kind') == 'other' and not x.get('fix'), x)
x = F.get(('unconfined_service_t', 'shadow_t', 'file')) or {}
ok('a service calling itself otp-fake, "otp.py" not otp\'s own in its command line, off otp\'s paths: not otp\'s',
   x.get('kind') == 'other', x)
x = F.get(('unconfined_service_t', 'ping_t', 'process2')) or {}
ok('otp\'s daemon (its own command line): a rule, as before', x.get('kind') == 'rule', x)
x = F.get(('httpd_t', 'default_t', 'file')) or {}
ok('a page of otp\'s labelled wrong: a label, its own folder', x.get('kind') == 'label' and x['fix']['restorecon'] == W, x)
x = F.get(('httpd_t', 'default_t', 'dir')) or {}
ok('a path with "..": never a label (restorecon -R would go up the tree)', x.get('kind') != 'label' and not (x.get('fix') or {}).get('restorecon'), x)
x = F.get(('httpd_t', 'default_t', 'lnk_file')) or {}
ok('a link inside otp\'s folder: never a label', x.get('kind') != 'label' and not (x.get('fix') or {}).get('restorecon'), x)

# a port of the right type already: done, not "another service's"
open(FAKE + '/ports', 'a').write('ssh_port_t                     tcp      2222\n')
pid = F[('sshd_t', 'unreserved_port_t', 'tcp_socket')]['id']
open(FAKE + '/calls', 'w').write('')
c2, e = do('fix', ids=[pid], by='admin')
ok('a port of the right type already: settled (not listed), semanage not asked, no "another service\'s"', c2 is not None
   and 'semanage port -a' not in open(FAKE + '/calls').read() and not any('another service' in s for s in c2.get('said', []))
   and pid not in {f['id'] for f in c2['findings']}, (e, c2 and c2.get('said')))

# a batch with a label and a rule, the module does not load: the label kept as put right
rid = F[('unconfined_service_t', 'ping_t', 'process2')]['id']
lid = F[('httpd_t', 'default_t', 'file')]['id']
open(FAKE + '/fail_load', 'w').write('1')
c3, e = do('fix', ids=[lid, rid], by='admin')
os.unlink(FAKE + '/fail_load')
c4, _ = do('check')
k4 = {f['id']: f['kind'] for f in c4['findings']}
ok('the module did not load: refused, the rule not kept, the label kept as put right', c3 is None and k4.get(rid) == 'rule'
   and k4.get(lid) == 'fixed' and c4['local_rules'] == [], (e, k4))
ok('...otp_local.cil not left behind with the rule the policy does not have', not os.path.exists(Wm.SE_LOCAL_CIL))

# put in; then a take-away whose semodule fails: the rule still listed, the file as the policy has it
c5, e = do('fix', ids=[rid], by='admin')
ok('the rule put in', c5 is not None and [x['id'] for x in c5['local_rules']] == [rid], e)
before = open(Wm.SE_LOCAL_CIL).read()
open(FAKE + '/fail_remove', 'w').write('1')
real = open(FB + '/semodule').read()
c6, e = do('rule_drop', rule=rid, by='admin') if False else (None, '')
# semodule -r refused: the fake's store locked
os.environ['PATH'] = TOP + '/fb2:' + os.environ['PATH']
os.makedirs(TOP + '/fb2')
open(TOP + '/fb2/semodule', 'w').write('#!/bin/bash\n. "%s/_common"\ncase "$1" in -r) echo "store locked" >&2; exit 1;; *) exec "%s/semodule" "$@";; esac\n' % (FB, FB))
os.chmod(TOP + '/fb2/semodule', 0o755)
c6, e = do('rule_drop', rule=rid, by='admin')
c7, _ = do('check')
ok('a take-away whose semodule fails: refused, the rule still listed, otp_local.cil as before',
   c6 is None and 'store locked' in e and [x['id'] for x in c7['local_rules']] == [rid] and open(Wm.SE_LOCAL_CIL).read() == before, (e, c7['local_rules']))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
