"""t_fix.py - 1.0.326: root's helper refuses taking out otp's SELinux rule while semodule does not
answer, a host name over 64 characters before nmcli, and says a restart only when dnf does; the
database agent takes over no member of other roles; the page refuses the long host name too.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, os, sys, types
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.326'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


web = open(V + '/deploy/otp_web.py').read()
pg = open(V + '/deploy/otp_pg_ops.py').read()
otp = open(V + '/otp.py').read()

# ==== 1 SELinux: not known is not "not loaded"
i = web.index('def se_local_load')
blk = web[i:i + 1500]
ok('selinux: semodule -l unanswered refused before anything', 'if loaded is None:' in blk and
   blk.index('if loaded is None:') < blk.index('root_state_write(SE_LOCAL_RULES'))

# ==== 2 the host name: 64 at most, before nmcli
i = web.index("raise Refused('the host name is the whole name, 64 characters at most')")
ok('root: long host name refused in the checks', i < web.index("run(args, 'nmcli connection modify')"))
ok('page: long host name refused', "raise ValueError('the host name is the whole name, 64 characters at most')" in otp)
ok('refused first (nothing changed)', "'the host name is the whole'" in otp)

# ==== 3 reboot_now: only when dnf says so, run with fakes
src = web[web.index('def reboot_now'):web.index('def osup_job')]
g = {'OSUP_PM': '/bin/true', 'os': os}


class R_:
    def __init__(self, rc, out, err=''):
        self.returncode, self.stdout, self.stderr = rc, out, err


for rc, out, err, want in ((1, 'Core libraries have been updated.\nReboot is required to fully utilize these updates.\n', '', True),
                           (0, 'No core libraries or services have been updated since boot-up.\nReboot should not be necessary.\n', '', False),
                           (1, '', 'No such command: needs-restarting.', False)):
    g['subprocess'] = types.SimpleNamespace(run=lambda *a, **k: R_(rc, out, err), DEVNULL=None)
    exec(src, g)
    ok('reboot_now rc=%d %r' % (rc, (out or err)[:30]), g['reboot_now']('dnf', {}) is want)

# ==== 4 the agent: no member of other roles
ok('agent: a member of other roles refused', 'is there as a member of other roles' in pg and
   "g.rolname <> 'pg_create_subscription'" in pg)
for f in ('otp_web.py', 'otp_pg_ops.py'):
    try:
        compile(open(V + '/deploy/' + f).read(), f, 'exec'); ok('compiles: ' + f, True)
    except SyntaxError as e:
        ok('compiles: ' + f, False, e)

print('ALL %d / %d' % (sum(R), len(R)))
