"""t_find.py - 1.0.300: what SELinux refuses, sorted by what puts it right, put right by id, otp's
own local module - the root helper with SELinux faked (fakebin/ beside this file; the audit log, the
labels and what the policy says they should be given as files). Then the steps of before, unchanged.

    python3 t_find.py VERSION        (as root; OTP_DIR=... to test another folder)
"""
import os, sys, json, time, shutil, tempfile, atexit, importlib.util, hashlib, tarfile, io

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.300'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = tempfile.mkdtemp(prefix='otp-se300-')
atexit.register(lambda: shutil.rmtree(TOP, True))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:500] if not c else ''), flush=True)


FAKE = TOP + '/se'
os.makedirs(FAKE)
os.makedirs(TOP + '/lib')
os.makedirs(TOP + '/hstate/web')
os.makedirs(TOP + '/rootstate')
open(TOP + '/selinux-config', 'w').write('SELINUX=permissive\nSELINUXTYPE=targeted\n')
open(TOP + '/cmdline', 'w').write('ro quiet\n')
shutil.copy(V + '/deploy/otp_server.cil', TOP + '/lib/otp_server.cil')
WWW = '/var/www/otp/assets/core.js'
GOOD = {'/run/otp': 'httpd_var_run_t', '/run/otp/api-token': 'httpd_var_run_t', '/var/www/otp': 'httpd_sys_content_t',
        '/usr/libexec/keepalived/otp-vip-check': 'keepalived_unconfined_script_exec_t', WWW: 'default_t'}
json.dump(GOOD, open(TOP + '/labels.json', 'w'))
json.dump({WWW: 'httpd_sys_content_t', '/var/www/otp/assets': 'httpd_sys_content_t'}, open(TOP + '/match.json', 'w'))
os.environ.update({'SEFAKE': FAKE, 'PATH': HERE + '/fakebin:' + os.environ['PATH'],
                   'OTP_SELINUX_CONFIG': TOP + '/selinux-config', 'OTP_SELINUX_RELABEL': TOP + '/.autorelabel',
                   'OTP_SELINUX_CMDLINE': TOP + '/cmdline', 'OTP_SELINUX_CIL': TOP + '/lib/otp_server.cil',
                   'OTP_SELINUX_LABELS': TOP + '/labels.json', 'OTP_SELINUX_MATCH': TOP + '/match.json',
                   'OTP_VIP_NO_SERVICES': '1', 'OTP_SELINUX_AUDITD': 'active', 'OTP_STATE': TOP + '/hstate',
                   'OTP_ROOT_STATE': TOP + '/rootstate', 'OTP_SELINUX_LIB': '/usr/local/lib/otp'})
open(FAKE + '/mode', 'w').write('Permissive\n')
for b in ('httpd_can_network_connect', 'authlogin_radius'):
    open(FAKE + '/bool_' + b, 'w').write('on\n')
open(FAKE + '/modules', 'w').write('otp_server\n')
open(FAKE + '/ports', 'w').write('radius_port_t                  udp      18129\nssh_port_t                     tcp      22\n'
                                 'http_port_t                    tcp      80, 443, 8443\n')
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
WANT = {'booleans': [{'name': 'httpd_can_network_connect', 'why': 'the pages ask the daemon'}],
        'ports': [{'port': 2222, 'proto': 'tcp', 'type': 'ssh_port_t', 'why': 'sshd'}],
        'facts': {'api_port': 9861, 'db_port': 0, 'radius_ports': [1812, 1813]}}
T0 = int(time.time()) - 3600


def hx(s):
    return s.encode().hex().upper()


def ev(n, at, avc, comm, exe, path=None, title=None):
    a = 'msg=audit(%d.%03d:%d):' % (at, n % 1000, n)
    out = ['type=AVC %s avc:  denied  %s' % (a, avc)]
    out.append('type=SYSCALL %s arch=c000003e syscall=257 success=no exit=-13 pid=%d comm="%s" exe="%s" '
               'subj=system_u:system_r:x_t:s0 key=(null)' % (a, 1000 + n, comm, exe))
    if path:
        out.append('type=PATH %s item=0 name="%s" inode=1 dev=fd:00 mode=0100644' % (a, path))
    out.append('type=PROCTITLE %s proctitle=%s' % (a, hx(title or exe)))
    return '\n'.join(out)


OTP = '/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'
LOG = [
    # a label: nginx reading one of otp's pages labelled default_t
    ev(1, T0, '{ read } for  pid=1001 comm="nginx" name="core.js" dev="vda1" ino=1 scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=unconfined_u:object_r:default_t:s0 tclass=file permissive=1', 'nginx', '/usr/sbin/nginx', WWW),
    ev(2, T0 + 5, '{ read } for  pid=1001 comm="nginx" name="core.js" dev="vda1" ino=1 scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=unconfined_u:object_r:default_t:s0 tclass=file permissive=1', 'nginx', '/usr/sbin/nginx', WWW),
    # a port: sshd on otp's SSH port of no type
    ev(3, T0 + 10, '{ name_bind } for  pid=1003 comm="sshd" src=2222 scontext=system_u:system_r:sshd_t:s0-s0:c0.c1023 '
       'tcontext=system_u:object_r:unreserved_port_t:s0 tclass=tcp_socket permissive=1', 'sshd', '/usr/sbin/sshd'),
    # a rule: otp's daemon starting hostname under NoNewPrivileges
    ev(4, T0 + 20, '{ nnp_transition } for  pid=1004 comm="otp-tick" scontext=system_u:system_r:unconfined_service_t:s0 '
       'tcontext=system_u:system_r:hostname_t:s0 tclass=process2 permissive=1', 'otp-tick', '/usr/bin/python3.11', None, OTP),
    # a boolean: php-fpm asking the daemon's API
    ev(5, T0 + 30, '{ name_connect } for  pid=1005 comm="php-fpm" dest=9861 scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=system_u:object_r:unreserved_port_t:s0 tclass=tcp_socket permissive=1', 'php-fpm', '/usr/sbin/php-fpm'),
    # not for a button: otp's daemon reading /etc/shadow, running a shell
    ev(6, T0 + 40, '{ read } for  pid=1006 comm="python3" name="shadow" scontext=system_u:system_r:unconfined_service_t:s0 '
       'tcontext=system_u:object_r:shadow_t:s0 tclass=file permissive=1', 'python3', '/usr/bin/python3.11', '/etc/shadow', OTP),
    ev(7, T0 + 50, '{ execute } for  pid=1007 comm="php-fpm" name="x.sh" scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=system_u:object_r:shell_exec_t:s0 tclass=file permissive=1', 'php-fpm', '/usr/sbin/php-fpm', '/var/www/otp/x.sh'),
    # a boolean that allows far more: not for a button
    ev(8, T0 + 55, '{ write } for  pid=1008 comm="php-fpm" name="lang" scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=system_u:object_r:httpd_sys_content_t:s0 tclass=dir permissive=1', 'php-fpm', '/usr/sbin/php-fpm', '/var/www/otp/lang'),
    # not otp's: smbd, and nginx on another site's file
    ev(9, T0 + 60, '{ write } for  pid=1009 comm="smbd" name="share" scontext=system_u:system_r:smbd_t:s0 '
       'tcontext=system_u:object_r:home_root_t:s0 tclass=dir permissive=1', 'smbd', '/usr/sbin/smbd', '/home/share'),
    ev(10, T0 + 65, '{ read } for  pid=1010 comm="nginx" name="index.html" scontext=system_u:system_r:httpd_t:s0 '
       'tcontext=system_u:object_r:user_home_t:s0 tclass=file permissive=1', 'nginx', '/usr/sbin/nginx', '/srv/site/index.html'),
    # allowed by the policy now
    ev(11, T0 + 70, '{ getattr } for  pid=1011 comm="chronyd" name="chrony.conf" scontext=system_u:system_r:chronyd_t:s0 '
       'tcontext=system_u:object_r:etc_t:s0 tclass=file permissive=1', 'chronyd', '/usr/sbin/chronyd', '/etc/otp/chrony.conf'),
]
open(FAKE + '/avc', 'w').write('\n'.join(LOG) + '\n')
open(FAKE + '/allowed', 'w').write('chrony.conf\n')
open(FAKE + '/bools', 'w').write('dest=9861\thttpd_can_network_connect\nname="lang"\thttpd_unified\n')


def do(what, **extra):
    try:
        return W.se_do(dict(WANT, do=what, **extra)), ''
    except W.Refused as e:
        return None, str(e)


c, e = do('check')
ok('a look: no error', c is not None, e)
F = {(f['source'], f['target'], f['class'], ' '.join(f['perms'])): f for f in (c or {}).get('findings') or []}


def kind(st, tt, cl, perms):
    return (F.get((st, tt, cl, perms)) or {}).get('kind')


ok('label: nginx on otp\'s page labelled default_t, restorecon of its folder',
   kind('httpd_t', 'default_t', 'file', 'read') == 'label'
   and F[('httpd_t', 'default_t', 'file', 'read')]['fix']['cmd'] == 'restorecon -R -v /var/www/otp/assets'
   and F[('httpd_t', 'default_t', 'file', 'read')]['count'] == 2, F.get(('httpd_t', 'default_t', 'file', 'read')))
ok('port: sshd on otp\'s port 2222 of no type - ssh_port_t', kind('sshd_t', 'unreserved_port_t', 'tcp_socket', 'name_bind') == 'port'
   and F[('sshd_t', 'unreserved_port_t', 'tcp_socket', 'name_bind')]['fix']['cmd'] == 'semanage port -a -t ssh_port_t -p tcp 2222',
   F.get(('sshd_t', 'unreserved_port_t', 'tcp_socket', 'name_bind')))
nnp = F.get(('unconfined_service_t', 'hostname_t', 'process2', 'nnp_transition')) or {}
ok('rule: otp\'s daemon (by its command line, hex in the log) starting hostname - exactly that',
   nnp.get('kind') == 'rule' and nnp['fix']['rule'] == '(allow unconfined_service_t hostname_t (process2 (nnp_transition)))', nnp)
ok('boolean: the API\'s port, audit2why says httpd_can_network_connect', kind('httpd_t', 'unreserved_port_t', 'tcp_socket', 'name_connect') == 'boolean'
   and F[('httpd_t', 'unreserved_port_t', 'tcp_socket', 'name_connect')]['fix']['cmd'] == 'setsebool -P httpd_can_network_connect 1')
sh = F.get(('unconfined_service_t', 'shadow_t', 'file', 'read')) or {}
ok('not for a button: /etc/shadow - security-sensitive, said why', sh.get('kind') == 'nobutton' and 'security-sensitive' in sh.get('why', '') and not sh.get('fix'), sh)
ex = F.get(('httpd_t', 'shell_exec_t', 'file', 'execute')) or {}
ok('not for a button: a shell executed - said why', ex.get('kind') == 'nobutton' and 'never allowed' in ex.get('why', ''), ex)
ub = F.get(('httpd_t', 'httpd_sys_content_t', 'dir', 'write')) or {}
ok('not for a button: only a boolean that allows far more (httpd_unified)', ub.get('kind') == 'nobutton' and 'httpd_unified' in ub.get('why', ''), ub)
sm = F.get(('smbd_t', 'home_root_t', 'dir', 'write')) or {}
ok('not otp\'s: smbd - shown, never put right, not counted', sm.get('kind') == 'other' and sm.get('whose') == 'other' and not sm.get('fix'), sm)
nh = F.get(('httpd_t', 'user_home_t', 'file', 'read')) or {}
ok('nginx on another site\'s file: the web server otp works with - shown apart, counted before enforcing',
   nh.get('kind') == 'other' and nh.get('whose') == 'near', nh)
ok('allowed by the policy now: not listed, said as settled', ('chronyd_t', 'etc_t', 'file', 'getattr') not in F and c['denials']['settled'] == 1)
ok('the count before enforcing: otp\'s and the web server\'s, not smbd\'s (10 of 11, less the one allowed)',
   c['denials']['total'] == 9, c['denials'])
ok('...said as before ("refused 9")', any('refused 9 thing' in p for p in c['problems']), c['problems'])
ok('...and not ready for enforcing', c['ready'] is False)
ids1 = sorted(f['id'] for f in c['findings'])
c2, _ = do('check')
ok('the ids are the same at the next look (12 hex)', ids1 == sorted(f['id'] for f in c2['findings']) and all(len(i) == 12 for i in ids1))
ok('counts by kind', c['counts'] == {'fixed': 0, 'boolean': 1, 'label': 1, 'port': 1, 'rule': 1, 'nobutton': 3, 'other': 2}, c['counts'])

# ---- put right by id ----
open(FAKE + '/calls', 'w').write('')
open(FAKE + '/bool_httpd_can_network_connect', 'w').write('off\n')
pick = [F[k]['id'] for k in (('httpd_t', 'default_t', 'file', 'read'), ('sshd_t', 'unreserved_port_t', 'tcp_socket', 'name_bind'),
                             ('unconfined_service_t', 'hostname_t', 'process2', 'nnp_transition'),
                             ('httpd_t', 'unreserved_port_t', 'tcp_socket', 'name_connect'))]
bad = [sh['id'], sm['id'], 'abcdef012345']
c3, e = do('fix', ids=pick + bad, by='admin')
calls = open(FAKE + '/calls').read()
ok('fix: no error', c3 is not None, e)
said = (c3 or {}).get('said') or []
ok('...restorecon of the folder, as worked out here', 'restorecon -R -v /var/www/otp/assets' in calls, calls)
ok('...the port labelled', 'semanage port -a -t ssh_port_t -p tcp 2222' in calls, calls)
ok('...the boolean on', 'setsebool -P httpd_can_network_connect 1' in calls, calls)
cil = open(W.SE_LOCAL_CIL).read() if os.path.exists(W.SE_LOCAL_CIL) else ''
ok('...the rule in otp\'s local module, in an optional block of its own, loaded', '(optional otp_local_%s' % nnp['id'] in cil
   and '(allow unconfined_service_t hostname_t (process2 (nnp_transition)))' in cil and 'semodule -i ' + W.SE_LOCAL_CIL in calls
   and open(W.SE_LOCAL_CIL + '.in-policy').read() == cil, cil + calls)
ok('...not for a button and not otp\'s: said, not done', any(sh['id'] in x and 'not put right here' in x for x in said)
   and any(sm['id'] in x for x in said), said)
ok('...an id not refused: said, nothing done', any('abcdef012345' in x and 'not refused any more' in x for x in said), said)
F3 = {f['id']: f for f in c3['findings']}
ok('...put right: each "fixed", and the count less them', all(F3[i]['kind'] == 'fixed' for i in pick) and c3['denials']['total'] == 9 - 5, c3['denials'])
ok('...the local rules listed', [x['id'] for x in c3['local_rules']] == [nnp['id']] and c3['local_module'] is True, c3.get('local_rules'))

# a refusal of the same after it was put right comes back
LOG.append(ev(20, int(time.time()) + 5, '{ read } for  pid=1001 comm="nginx" name="core.js" dev="vda1" ino=1 scontext=system_u:system_r:httpd_t:s0 '
              'tcontext=unconfined_u:object_r:default_t:s0 tclass=file permissive=1', 'nginx', '/usr/sbin/nginx', WWW))
open(FAKE + '/avc', 'w').write('\n'.join(LOG) + '\n')
c4, _ = do('check')
F4 = {f['id']: f for f in c4['findings']}
ok('refused again after it was put right: back as a label', F4[pick[0]]['kind'] == 'label', F4.get(pick[0]))
# the file labelled as it should be since: settled
GOOD[WWW] = 'httpd_sys_content_t'
json.dump(GOOD, open(TOP + '/labels.json', 'w'))
c4, _ = do('check')
ok('...labelled as the policy says since: settled, not listed', pick[0] not in {f['id'] for f in c4['findings']})

# ---- the requests: only ids ----
for what, extra, why in (('fix', {'ids': 'abc'}, 'ids'), ('fix', {'ids': ['../x']}, 'ids'), ('fix', {'ids': []}, 'ids'),
                         ('fix', {'ids': ['a' * 12] * 301}, 'ids'), ('rule_drop', {'rule': 'x; rm'}, 'id'),
                         ('rule_drop', {'rule': 'abcdef012345'}, 'no rule')):
    c5, e = do(what, **extra)
    ok('refused: %s %s' % (what, str(extra)[:40]), c5 is None and why in e, e)
c5, e = do('fix', ids=[nnp['id']], rule='(allow unconfined_service_t shadow_t (file (read)))')
ok('a rule sent with a request is never taken: the one worked out here', '(allow unconfined_service_t shadow_t' not in open(W.SE_LOCAL_CIL).read())

# ---- take a rule away ----
open(FAKE + '/calls', 'w').write('')
c6, e = do('rule_drop', rule=nnp['id'], by='admin')
calls = open(FAKE + '/calls').read()
ok('the last rule taken away: semodule -r otp_local, its file gone', c6 is not None and 'semodule -r otp_local' in calls
   and not os.path.exists(W.SE_LOCAL_CIL) and c6['local_rules'] == [], (e, calls))
ok('...its refusal counts again', {f['id']: f for f in c6['findings']}[nnp['id']]['kind'] == 'rule')

# ---- a module that does not load: nothing counted as put right ----
open(FAKE + '/fail_load', 'w').write('1')
c7, e = do('fix', ids=[nnp['id']], by='admin')
os.unlink(FAKE + '/fail_load')
c8, _ = do('check')
ok('the local module not loaded: refused, the rule not kept, still a rule to put in', c7 is None and 'semodule -i' in e
   and c8['local_rules'] == [] and {f['id']: f for f in c8['findings']}[nnp['id']]['kind'] == 'rule', e)

# ---- under enforcing too; never while disabled ----
open(FAKE + '/mode', 'w').write('Enforcing\n')
c9, e = do('fix', ids=[nnp['id']], by='admin')
ok('under enforcing: put right as well', c9 is not None and nnp['id'] in [x['id'] for x in c9['local_rules']], e)
open(FAKE + '/mode', 'w').write('Disabled\n')
c9, e = do('fix', ids=[nnp['id']])
ok('disabled: refused', c9 is None and 'disabled' in e, e)
open(FAKE + '/mode', 'w').write('Permissive\n')

# ---- the report: the machine's side too ----
parts = W.se_report_parts(dict(WANT))
ok('the report: findings.json and os/*', all(k in parts for k in ('findings.json', 'os/processes.txt', 'os/booleans.txt', 'os/ports.txt',
                                                                  'os/modules.txt', 'os/local-changes.txt', 'os/semanage-export.txt',
                                                                  'os/listening.txt')), sorted(parts))
ok('...findings.json has the rules of otp_local', nnp['id'] in parts['findings.json'])
ok('...the text for the command line lists the ids and fixes', nnp['id'] in W.se_report(do('check')[0]))
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
