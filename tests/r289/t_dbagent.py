# t_dbagent.py VERSION - 1.0.289: the database on a server of its own, looked after by otp-db-agent
# (layout A). On this machine, as root, nothing of the installed otp touched:
#   - a PostgreSQL 16 of its own (port 55432, its own folder), an agent for it (port 19443, its own
#     folders, firewalld left alone: OTP_AGENT_NO_FIREWALL) - its network side as otp-db-agent;
#   - an otp node in a state folder of its own (the program of the build, OTP_HA_NO_RESTART);
#   - the join with the code on standard input (never on the command line), sealed;
#   - the protocol's refusals (agent_client.py, the kit's minimal client), audited without secrets;
#   - status, the view, the status line, the server's own settings told by the agent;
#   - Database -> TLS through the agent: a certificate from otp's authority, ssl on, verify-full;
#   - a restart through the agent; renewals; forget = leave; without an agent nothing is asked.
import json, os, pwd, secrets, shutil, signal, socket, subprocess, sys, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.289'
OUT = '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
PY = '/usr/local/lib/otp/python'
PGBIN = '/usr/lib/postgresql/16/bin'
TOP = '/var/tmp/otp-r289'
PGPORT, APORT = 55432, 19443
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:500]), flush=True)


def sh(args, **kw):
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    return subprocess.run(args, **kw)


def psql(sql, db='postgres'):
    got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/psql', '-XAtq', '-p', str(PGPORT), '-d', db,
              '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=sql + ';\n')
    return got.stdout.strip() if got.returncode == 0 else 'ERROR ' + got.stderr.strip()


# ---- the database server: a PostgreSQL 16 of its own -------------------------------------------
PIDS = []


def down():
    for p in PIDS:
        try:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=40)
        except Exception:                               # noqa: BLE001
            try:
                p.kill()
            except Exception:                           # noqa: BLE001
                pass
    if os.path.exists(TOP + '/pg/PG_VERSION'):
        sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-m', 'fast', '-w', 'stop'])


if os.path.exists(TOP + '/pg/postmaster.pid'):
    sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-m', 'fast', '-w', 'stop'])
if os.path.isdir(TOP):
    shutil.rmtree(TOP)
os.makedirs(TOP, mode=0o755)
os.makedirs(TOP + '/pg', mode=0o700)
pg = pwd.getpwnam('postgres')
os.chown(TOP + '/pg', pg.pw_uid, pg.pw_gid)
got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/initdb', '-D', TOP + '/pg', '-E', 'UTF8', '--locale=C.UTF-8',
          '--auth-local=peer', '--auth-host=scram-sha-256'])
ok('a PostgreSQL 16 of its own made', got.returncode == 0, got.stderr[-300:])
with open(TOP + '/pg/postgresql.auto.conf', 'a') as f:
    f.write("port = %d\nlisten_addresses = '127.0.0.1'\nunix_socket_directories = '/var/run/postgresql'\n"
            "logging_collector = on\n" % PGPORT)
os.makedirs('/var/run/postgresql', exist_ok=True)
os.chown('/var/run/postgresql', pg.pw_uid, pg.pw_gid)
RESTART = ['/usr/sbin/runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-w', '-m', 'fast',
           '-l', TOP + '/pg/server.log', 'restart']
got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-w', '-l', TOP + '/pg/server.log', 'start'],
         stdin=subprocess.DEVNULL)
ok('...started on %d' % PGPORT, psql('SELECT 1') == '1', got.stderr[-300:])
PW = secrets.token_urlsafe(18)
psql("SET log_statement = 'none'; CREATE ROLE otp LOGIN PASSWORD '%s'" % PW)
psql("CREATE DATABASE otp OWNER otp ENCODING 'UTF8' TEMPLATE template0")

try:
    # ---- the agent ---------------------------------------------------------------------------
    if sh(['id', 'otp-db-agent']).returncode != 0:
        sh(['useradd', '--system', '--no-create-home', '--home-dir', TOP + '/agent/state', '--shell',
            '/sbin/nologin', 'otp-db-agent'])
    for d, m in (('agent', 0o755), ('agent/lib', 0o755), ('agent/etc', 0o700), ('agent/state', 0o700),
                 ('agent/log', 0o750), ('agent/pki', 0o755)):
        os.makedirs(TOP + '/' + d, mode=m, exist_ok=True)
    for f in ('otp_db_agent.py', 'otp_pg_ops.py', 'otp_web.py'):
        shutil.copy(OUT + '/deploy/' + f, TOP + '/agent/lib/' + f)
    with open(TOP + '/agent/lib/release', 'w') as f:
        f.write(VER + '\n')
    CONF = TOP + '/agent/etc/agent.json'
    with open(CONF, 'w') as f:
        json.dump({'listen': '127.0.0.1', 'port': APORT, 'engine': 'postgres', 'pg_port': PGPORT,
                   'user': 'otp-db-agent', 'state': TOP + '/agent/state', 'log': TOP + '/agent/log/audit.log',
                   'ha_ca': TOP + '/agent/pki/ha-ca.pem', 'pg_restart_cmd': RESTART, 'advertise': '127.0.0.1'}, f)
    os.chmod(CONF, 0o600)
    AENV = dict(os.environ, OTP_AGENT_NO_FIREWALL='1')
    AGENT = [sys.executable, '-I', TOP + '/agent/lib/otp_db_agent.py', '--config', CONF]

    def agent_start():
        p = subprocess.Popen(AGENT, env=AENV, stdout=open(TOP + '/agent/out.log', 'a'), stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
        PIDS.append(p)
        for _ in range(60):
            try:
                socket.create_connection(('127.0.0.1', APORT), timeout=1).close()
                return p
            except OSError:
                time.sleep(0.25)
        return p
    agent = agent_start()

    def new_code():
        got = sh(AGENT + ['--new-code'], env=AENV)
        return got.stdout.strip()
    code = new_code()
    ok('the agent runs and makes a join code (ODBA1., with the key to seal to)', code.startswith('ODBA1.') and
       '"k"' in __import__('base64').urlsafe_b64decode(code[6:] + '=' * (-len(code[6:]) % 4)).decode())
    time.sleep(1)
    side = sh(['pgrep', '-f', '--', '--network-side']).stdout.split()
    users = set(sh(['ps', '-o', 'user=', '-p', ','.join(side)]).stdout.split()) if side else set()
    ok('its network side is a program of its own, as otp-db-agent (never root)', users == {'otp-db-agent'}, users)

    # ---- the otp node --------------------------------------------------------------------------
    N = TOP + '/node'
    for d in ('', '/log', '/run'):
        os.makedirs(N + d, mode=0o700, exist_ok=True)
    with open(N + '/config.json', 'w') as f:
        json.dump({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': PGPORT, 'db_name': 'otp',
                   'db_user': 'otp', 'db_password': PW, 'node_name': 'n1'}, f)
    os.chmod(N + '/config.json', 0o600)
    NENV = {k: v for k, v in os.environ.items() if not k.startswith('OTP_')}
    NENV.update(OTP_STATE=N, OTP_CONFIG=N + '/config.json', OTP_LOGDIR=N + '/log', OTP_RUN=N + '/run',
                OTP_HA_CA=N + '/ha-ca.pem', OTP_HA_NO_RESTART='1', OTP_STAY_ROOT='1', OTP_DBAGENT_EVERY='2')

    def otp(*args, stdin=None, env=None):
        return sh([PY, OUT + '/otp.py'] + list(args), input=stdin, env=dict(NENV, **(env or {})))

    got = otp('--status')
    ok('the node on its PostgreSQL, no agent: --status as ever, no agent line', got.returncode in (0, 1) and
       'database agent' not in got.stdout and 'otp-db-agent' not in got.stdout, got.stdout[-400:] + got.stderr[-300:])
    got = otp('--db-agent-status')
    ok('...--db-agent-status: no agent (db_admin is local)', got.returncode != 0 and 'no database agent' in got.stderr, got.stderr)
    got = otp('--db-agent-join', code)
    ok('the join code on the command line: refused (never on a command line)', got.returncode != 0 and
       'never given on the command line' in got.stderr and not os.path.exists(N + '/db-agent/agent.json'), got.stderr[-300:])
    got = otp('--db-agent-join', '-', stdin=code + '\n')
    ok('the join with the code on standard input', got.returncode == 0, got.stdout[-600:] + got.stderr[-600:])
    print(got.stdout.strip())
    a = json.load(open(N + '/db-agent/agent.json'))
    ok('...agent.json: db_admin agent:127.0.0.1:%d, one pin, its engine and port' % APORT,
       a.get('db_admin') == 'agent:127.0.0.1:%d' % APORT and len(a.get('pins') or []) == 1 and
       a.get('engine') == 'postgres' and a.get('pg_port') == PGPORT, a)
    ok('...sign.key 0600, client.key 0600', oct(os.stat(N + '/db-agent/sign.key').st_mode & 0o777) == '0o600' and
       oct(os.stat(N + '/db-agent/client.key').st_mode & 0o777) == '0o600')
    got = otp('--db-agent-join', '-', stdin=code + '\n')
    ok('...the code used up: a second join with it refused', got.returncode != 0 and 'used up' in got.stderr, got.stderr[-300:])
    audit = open(TOP + '/agent/log/audit.log').read()
    sk = open(N + '/db-agent/sign.key').read().strip()
    ok('...the audit log has the join and the refusal, no key, no code', '"enroll"' in audit and
       'used up' in audit and sk not in audit and code[6:40] not in audit, audit[-300:])

    got = otp('--db-agent-status', '--json')
    v = json.loads(got.stdout or '{}')
    me = [x for x in v.get('servers') or [] if x.get('me')]
    ok('--db-agent-status --json: answers, the server runs, its version', got.returncode == 0 and me and me[0].get('ok') and
       (me[0].get('facts') or {}).get('running') and str((me[0].get('facts') or {}).get('version') or '').startswith('16'),
       got.stdout[-500:] + got.stderr[-300:])
    ok('...where: the agent\'s server', (v.get('where') or {}).get('kind') == 'agent', v.get('where'))
    ok('...no version skew (the program the build ships)', not me[0].get('version_skew'), me[0].get('version_skew'))
    got = otp('--status')
    ok('--status: the database server line', 'database server: 127.0.0.1 through otp-db-agent' in got.stdout and
       'answers' in got.stdout, got.stdout[-600:])
    got = otp('--db-agent-status')
    ok('--db-agent-status: answers, the node listed', got.returncode == 0 and 'answers, otp-db-agent' in got.stdout and
       'node:     n1' in got.stdout, got.stdout)

    # ---- the protocol: the kit's client, another node of its own authority -------------------------
    code2 = new_code()
    W = TOP + '/kitnode'
    got = sh([sys.executable, HERE + '/agent_client.py', 'join', W, 'kitnode'], input=code2 + '\n')
    ok('the kit\'s minimal client joins too (a second node, sealed)', got.returncode == 0, got.stdout[-400:] + got.stderr[-400:])
    got = sh([sys.executable, HERE + '/agent_client.py', 'refusals', W])
    print(got.stdout.rstrip())
    ok('...every refusal as it must be (replay, old time, other key, unsigned, no certificate, outside the set, '
       'the server\'s own database, a newline, empty trust)', got.returncode == 0, got.stdout[-800:] + got.stderr[-300:])
    got = otp('--db-agent-status')
    ok('...the first node goes on (its own pin and key)', got.returncode == 0 and 'node:     kitnode' in got.stdout, got.stdout)
    # the network side holds no key: its memory looked through
    side = sh(['pgrep', '-f', '--', '--network-side']).stdout.split()
    found = False
    keys = [sk, open(W + '/sign.key').read().strip()]
    for pid in side:
        try:
            maps = open('/proc/%s/maps' % pid).read().splitlines()
            with open('/proc/%s/mem' % pid, 'rb', 0) as mem:
                for line in maps:
                    if 'rw' not in line.split()[1]:
                        continue
                    lo, hi = [int(x, 16) for x in line.split()[0].split('-')]
                    try:
                        mem.seek(lo)
                        chunk = mem.read(hi - lo)
                    except (OSError, ValueError, OverflowError):
                        continue
                    for k in keys:
                        if k.encode() in chunk or bytes.fromhex(k) in chunk:
                            found = True
        except OSError:
            pass
    ok('the network side\'s memory holds neither node\'s signing key (hex nor raw)', side and not found, side)

    # ---- the node in-process: the branches -------------------------------------------------------
    probe = r'''
import json, os, sys, time
sys.argv = ['x']
sys.path.insert(0, %r)
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
otp.load_config(saved=st.settings_saved())
otp.HA_STORE['store'] = st
out = {}
out['here'] = otp.db_agent_here()
out['kind'] = otp.dbtls_kind()
m = otp.tune_machine(otp.CONFIG, {})
out['tune_source'] = m.get('source'); out['tune_ram'] = bool(m.get('ram'))
out['restart_ready'] = otp.tune_restart_ready(st)
out['running'] = otp.pg_local_running()
out['names_db'] = '127.0.0.1' in otp.hatls_names()
# Database -> TLS's server certificate, as the daemon asks it (pgtls_send -> the agent)
otp.hatls_ca_ensure(st, 'test')
key, crt = otp.hatls_issue(st, otp.hatls_names())
otp.pgtls_send({'id': 'a1b2c3d4e5f60718', 'do': 'server', 'cert': crt, 'key': key,
                'trust': otp.hatls_trust(otp.hatls_ca(st)), 'db': 'otp', 'user': 'otp'})
got = {}
for _ in range(120):
    try:
        got = json.loads((otp.WEB_DIR / otp.PGTLS_FILE).read_text())
        if got.get('id') == 'a1b2c3d4e5f60718':
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.5)
out['pgtls'] = {k: got.get(k) for k in ('ok', 'said')}
try:
    out['own_cert_end'] = otp.hatls_own_cert(st)[0] > time.time()
except Exception as e:
    out['own_cert_end'] = str(e)
out['ha_ca_local'] = os.path.exists(str(otp.HA_CA_FILE))
out['view'] = sorted(otp.db_agent_view(st).keys())
out['alerts'] = [p['key'] for p in otp._db_agent_alerts(st)]
out['metrics'] = [x[0] for x in otp._db_agent_metrics(st)]
print('JSON' + json.dumps(out, default=str))
''' % OUT
    got = sh([PY, '-c', probe], env=NENV)
    line = [x for x in got.stdout.splitlines() if x.startswith('JSON')]
    p = json.loads(line[0][4:]) if line else {}
    ok('in-process: db_agent_here, dbtls kind "local" (as on this machine)', p.get('here') is True and p.get('kind') == 'local',
       got.stdout[-500:] + got.stderr[-800:])
    # one machine here: 127.0.0.1 is this machine for the settings' page (read here); the agent's own
    # facts are what it says of its machine
    ok('...the server\'s own settings: the machine known', p.get('tune_ram') is True, p)
    ok('...its restart: through the agent', (p.get('restart_ready') or {}).get('unit') == 'otp-db-agent' and
       (p.get('restart_ready') or {}).get('may') is True, p.get('restart_ready'))
    ok('...pg_local_running asks the agent', p.get('running') is True, p)
    ok('...the certificate\'s names have the database server', p.get('names_db') is True, p)
    ok('Database -> TLS through the agent: put in', (p.get('pgtls') or {}).get('ok') is True, p.get('pgtls'))
    ok('...PostgreSQL there answers with it: ssl on, otp-ha.crt', psql('SHOW ssl') == 'on' and
       psql('SHOW ssl_cert_file').endswith('otp-ha.crt'), psql('SHOW ssl_cert_file'))
    ok('...hatls_own_cert checks it at the database server (verify by the cluster\'s authority)', p.get('own_cert_end') is True, p)
    ok('...the authorities written on the node too', p.get('ha_ca_local') is True)
    ok('...the view, the alerts (none), the metrics', 'servers' in (p.get('view') or []) and p.get('alerts') == [] and
       'otp_db_agent_up' in (p.get('metrics') or []), p)
except Exception as e:                                  # noqa: BLE001
    ok('the test ran through', False, repr(e))
    import traceback
    traceback.print_exc()
try:
    vf = sh([PY, '-c', 'import psycopg2,sys; c=psycopg2.connect(host="127.0.0.1", port=%d, dbname="otp", user="otp", '
                       'password=sys.stdin.readline().strip(), sslmode="verify-full", sslrootcert=%r); '
                       'print(c.cursor().connection.info.ssl_in_use)' % (PGPORT, TOP + '/node/ha-ca.pem')],
            input=PW + '\n')
    ok('...the node connects verify-full to it', vf.stdout.strip() == 'True', vf.stderr[-300:])

    # ---- a restart through the agent ------------------------------------------------------------
    t0 = psql("SELECT extract(epoch from pg_postmaster_start_time())::bigint")
    got = otp('--db-agent-restart')
    t1 = psql("SELECT extract(epoch from pg_postmaster_start_time())::bigint")
    ok('--db-agent-restart: PostgreSQL started again by the agent', got.returncode == 0 and t1 != t0 and
       t1.isdigit(), got.stdout + got.stderr)
    # ---- the renewals ----------------------------------------------------------------------------
    got = otp('--db-agent-renew')
    a2 = json.load(open(TOP + '/node/db-agent/agent.json'))
    ok('--db-agent-renew: the agent\'s next certificate announced and pinned, this node\'s client certificate renewed',
       got.returncode == 0 and 'client certificate' in got.stdout and len(a2.get('pins') or []) >= 1, got.stdout + got.stderr)
    got = otp('--db-agent-status')
    ok('...the node goes on with its renewed certificate', got.returncode == 0 and 'answers' in got.stdout, got.stdout + got.stderr)
    # ---- the agent away: said ---------------------------------------------------------------------
    agent.send_signal(signal.SIGTERM)
    agent.wait(timeout=60)
    got = otp('--db-agent-status')
    ok('the agent stopped: --db-agent-status says it does NOT answer', got.returncode != 0 and 'does NOT answer' in
       got.stdout + got.stderr, got.stdout + got.stderr)
    agent = agent_start()
    got = otp('--db-agent-status')
    ok('...started again: it answers (its keys and the nonces kept)', got.returncode == 0, got.stdout + got.stderr)
    # ---- forget = leave ---------------------------------------------------------------------------
    got = otp('--db-agent-forget')
    ok('--db-agent-forget without --yes: asks for it', got.returncode != 0 and '--yes' in got.stderr, got.stderr)
    got = otp('--db-agent-forget', '--yes')
    ok('--db-agent-forget --yes: db_admin local, the agent took this node off its list', got.returncode == 0 and
       'took this node off its list' in got.stdout and not os.path.exists(N + '/db-agent/agent.json') and
       os.path.exists(N + '/db-agent/agent.json.forgotten'), got.stdout + got.stderr)
    st = json.loads(sh(AGENT + ['--status'], env=AENV).stdout or '{}')
    names = list(st.get('clients') or [])
    ok('...the agent lists only the kit\'s node now', names == ['kitnode'], st)
    got = otp('--status')
    ok('...--status: no agent line any more', 'otp-db-agent' not in got.stdout, got.stdout[-300:])
except Exception as e:                                  # noqa: BLE001
    ok('the test ran through', False, repr(e))
    import traceback
    traceback.print_exc()
finally:
    down()
print('ALL %d / %d' % (sum(R), len(R)))
