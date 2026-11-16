# t_deploy.py VERSION - 1.0.289: install.sh's database server parts, without changing this machine:
# the options checked, --dry-run says what it would do (the password never said), the unit hardened,
# pg_hba.conf written by the agent's own link-safe code (never cp or >), passwords on stdin only.
import os, subprocess, sys, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.289'
OUT = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[-500:]), flush=True)


def inst(*args):
    return subprocess.run(['bash', OUT + '/install.sh'] + list(args), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=300)


ok('install.sh and db-server.sh: bash -n', subprocess.run(['bash', '-n', OUT + '/install.sh']).returncode == 0 and
   subprocess.run(['bash', '-n', OUT + '/deploy/db-server.sh']).returncode == 0)
got = inst('--help')
ok('--help: --db-server, --db-agent, --otp-node, --db-password-file, --new-code', all(x in got.stdout for x in (
    '--db-server ENGINE', '--db-agent ', '--otp-node ADDRESS', '--db-password-file FILE', '--new-code')), got.stdout[-400:])
got = inst('--otp-node', '192.0.2.11')
ok('--otp-node without --db-server: refused', got.returncode != 0 and 'for the database server' in got.stdout + got.stderr, got.stdout + got.stderr)
got = inst('--new-code')
ok('--new-code without --db-agent: refused', got.returncode != 0 and '--new-code is for the database server' in got.stdout + got.stderr)
got = inst('--db-server', 'oracle', '--dry-run')
ok('--db-server oracle: refused', got.returncode != 0 and 'postgres or mariadb' in got.stdout + got.stderr, got.stdout + got.stderr)
got = inst('--db-server', 'postgres', '--otp-node', '192.0.2.11; rm -rf /', '--dry-run')
ok('--otp-node with more than an address: refused', got.returncode != 0 and 'plain addresses' in got.stdout + got.stderr)
pwf = tempfile.NamedTemporaryFile('w', delete=False)
PW = 'Xy7-only-for-this-test-q9'
pwf.write(PW + '\n')
pwf.close()
had = os.path.exists('/usr/local/lib/otp-db-agent') or os.path.exists('/etc/otp-db-agent')
got = inst('--db-server', 'postgres', '--otp-node', '192.0.2.11', '--db-password-file', pwf.name, '--dry-run')
os.unlink(pwf.name)
said = got.stdout + got.stderr
ok('--db-server postgres --dry-run: through to the end', got.returncode == 0 and 'otp-db-agent' in said and '[would' in said, said)
ok('...the password never said', PW not in said)
ok('...nothing installed', had or not (os.path.exists('/usr/local/lib/otp-db-agent') or os.path.exists('/etc/otp-db-agent')))
ok('...nothing of otp itself (no daemon step)', 'Upgrading otp' not in said and 'The daemon' not in said, said[-300:])
unit = open(OUT + '/deploy/otp-db-agent.service').read()
ok('the unit: hardened (ProtectSystem=strict, PrivateDevices, RestrictAddressFamilies, a bounding set), KillMode=mixed',
   all(x in unit for x in ('ProtectSystem=strict', 'PrivateDevices=yes', 'RestrictAddressFamilies=', 'CapabilityBoundingSet=',
                           'KillMode=mixed', 'TimeoutStopSec=360', '/usr/local/lib/otp-db-agent/otp_db_agent.py')))
sh = open(OUT + '/deploy/db-server.sh').read()
ok('db-server.sh: pg_hba.conf by the agent\'s link-safe hba_add, never cp or a redirect', 'O.hba_add(' in sh and not any(
       ('cp ' in l or '>>' in l) and 'hba' in l for l in sh.splitlines()))
ok('...passwords on psql\'s / mariadb\'s standard input, not logged', "SET log_statement = 'none'" in sh and
   'sql_log_off = 1' in sh and 'pg_psql_secret' in sh and 'my_q_secret' in sh)
ok('...a join code only for a new agent or --new-code', 'AGENT_FRESH' in sh and 'DB_AGENT_NEW_CODE' in sh)
ok('...no name of acme left', 'acme' not in sh.lower() and 'acme' not in unit.lower() and
   'acme' not in open(OUT + '/deploy/otp_db_agent.py').read().lower().replace('acme 1.0.113', ''))
print('ALL %d / %d' % (sum(R), len(R)))
