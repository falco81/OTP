"""t_fix.py - 1.0.305: SELinux, the root helper (fakebin/ of r300): two refusals of one event each get
audit2why's word; a rule the same as one in otp_local already is not put in twice; a boolean set once
for a batch of its refusals.   python3 t_fix.py VERSION   (as root; OTP_DIR=... for another folder)
"""
import os, sys, json, time, shutil, tempfile, atexit, importlib.util
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.305'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
FB = os.path.join(os.path.dirname(HERE), 'r300', 'fakebin')
TOP = tempfile.mkdtemp(prefix='otp-se305-')
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
json.dump({}, open(TOP + '/labels.json', 'w'))
json.dump({}, open(TOP + '/match.json', 'w'))
os.environ.update({'SEFAKE': FAKE, 'PATH': FB + ':' + os.environ['PATH'], 'OTP_SELINUX_CONFIG': TOP + '/selinux-config',
                   'OTP_SELINUX_RELABEL': TOP + '/.autorelabel', 'OTP_SELINUX_CMDLINE': TOP + '/cmdline',
                   'OTP_SELINUX_CIL': TOP + '/lib/otp_server.cil', 'OTP_SELINUX_LABELS': TOP + '/labels.json',
                   'OTP_SELINUX_MATCH': TOP + '/match.json', 'OTP_SELINUX_AUDITD': 'active', 'OTP_STATE': TOP + '/hstate',
                   'OTP_ROOT_STATE': TOP + '/rootstate', 'OTP_VIP_NO_SERVICES': '1'})
open(FAKE + '/mode', 'w').write('Permissive\n')
open(FAKE + '/modules', 'w').write('otp_server\n')
open(FAKE + '/ports', 'w').write('')
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
WANT = {'booleans': [], 'ports': [], 'facts': {'api_port': 9861}}
T0 = int(time.time()) - 3600
OTP = '/usr/local/lib/otp/python /usr/local/lib/otp/otp.py --daemon'.encode().hex().upper()


def event(n, avcs, comm='otp-tick', exe='/usr/bin/python3.11', title=OTP):
    a = 'msg=audit(%d.%03d:%d):' % (T0 + n, n, 900 + n)
    return '\n'.join(['type=AVC %s avc:  denied  %s' % (a, x) for x in avcs] +
                     ['type=SYSCALL %s arch=c000003e syscall=257 success=no exit=-13 pid=%d comm="%s" exe="%s" key=(null)' % (a, n, comm, exe),
                      'type=PROCTITLE %s proctitle=%s' % (a, title)])


def avc(perms, st, tt, cls, extra=''):
    return '{ %s } for  pid=1 %s scontext=system_u:system_r:%s:s0 tcontext=system_u:object_r:%s:s0 tclass=%s permissive=1' % (
        perms, extra, st, tt, cls)


LOG = [
    # one event, two refusals: the folder searched (allowed now), the file read (missing)
    event(1, [avc('search', 'unconfined_service_t', 'krb5_conf_t', 'dir', 'name="krb5.conf.d"'),
              avc('read', 'unconfined_service_t', 'krb5_home_x_t', 'file', 'name="x.conf"')]),
    # the same rule, two programs of otp's
    event(2, [avc('nnp_transition', 'unconfined_service_t', 'ping_t', 'process2')], comm='otp-a'),
    event(3, [avc('nnp_transition', 'unconfined_service_t', 'ping_t', 'process2')], comm='otp-b'),
    # php-fpm asking the API on two ports: one boolean
    event(4, [avc('name_connect', 'httpd_t', 'unreserved_port_t', 'tcp_socket', 'dest=9861')], comm='php-fpm', exe='/usr/sbin/php-fpm', title='70'),
    event(5, [avc('name_connect', 'httpd_t', 'unreserved_port_t', 'tcp_socket', 'dest=1812')], comm='php-fpm', exe='/usr/sbin/php-fpm', title='70'),
]
open(FAKE + '/avc', 'w').write('\n'.join(LOG) + '\n')
open(FAKE + '/allowed', 'w').write('krb5_conf_t\n')


def do(what, **extra):
    try:
        return W.se_do(dict(WANT, do=what, **extra)), ''
    except W.Refused as e:
        return None, str(e)


c, e = do('check')
F = {(f['source'], f['target'], f['program']): f for f in (c or {}).get('findings') or []}
ok('two refusals of one event: the one allowed now settled, the other its own word', c is not None
   and ('unconfined_service_t', 'krb5_conf_t', 'otp-tick') not in F and ('unconfined_service_t', 'krb5_home_x_t', 'otp-tick') in F
   and c['denials']['settled'] == 1, (e, sorted(F)))
a, b = F[('unconfined_service_t', 'ping_t', 'otp-a')], F[('unconfined_service_t', 'ping_t', 'otp-b')]
p1, p2 = F[('httpd_t', 'unreserved_port_t', 'php-fpm')], [f for f in c['findings'] if f['source'] == 'httpd_t' and f['id'] != F[('httpd_t', 'unreserved_port_t', 'php-fpm')]['id']]
ok('two programs, the same rule: two findings', a['kind'] == 'rule' and b['kind'] == 'rule' and a['fix']['rule'] == b['fix']['rule'])
ids = [x['id'] for x in c['findings'] if x['kind'] in ('rule', 'boolean')]
open(FAKE + '/calls', 'w').write('')
c2, e = do('fix', ids=ids, by='admin')
calls = open(FAKE + '/calls').read()
cil = open(W.SE_LOCAL_CIL).read() if os.path.exists(W.SE_LOCAL_CIL) else ''
ok('fixed: the same rule once in otp_local, the other said "the same as"', c2 is not None and cil.count('(allow unconfined_service_t ping_t') == 1
   and any('the same as' in s for s in c2.get('said', [])), (e, cil, c2 and c2.get('said')))
ok('...both findings put right', all({f['id']: f for f in c2['findings']}[x]['kind'] == 'fixed' for x in (a['id'], b['id'])))
ok('a boolean for two refusals: setsebool once', calls.count('setsebool -P httpd_can_network_connect') == 1
   and all({f['id']: f for f in c2['findings']}[x['id']]['kind'] == 'fixed' for x in [p1] + p2), calls)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
