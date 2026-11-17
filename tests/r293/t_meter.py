# t_meter.py VERSION - 1.0.293: the database servers in the header's meter (GET /api/load
# `dbservers`), in-process on the build's otp.py. On this machine, as root, nothing of the
# installed otp touched (the setup of r291/t_moves.py: a PostgreSQL 16 of its own on 55436,
# its agent on 19446, an otp node on SQLite):
#   - no agent: /api/load as before (no `dbservers`); the meter off: 404 as before;
#   - joined: a row for this node's server - the machine's numbers, its database's own;
#   - the other node's row from its meta row (late), one older than an hour left out;
#   - the agent stopped: the row down at once, and not asked again for 10 s (no waiting).
import json, os, pwd, secrets, shutil, signal, socket, subprocess, sys, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.293'
OUT = '/home/claude/build/out/otp-%s' % VER
PY = '/usr/local/lib/otp/python'
PGBIN = '/usr/lib/postgresql/16/bin'
TOP = '/var/tmp/otp-r293'
PGPORT, APORT = 55436, 19446
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:600]), flush=True)


def sh(args, **kw):
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    return subprocess.run(args, **kw)


def psql(sql, db='postgres'):
    got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/psql', '-XAtq', '-p', str(PGPORT), '-d', db,
              '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=sql + ';\n')
    return got.stdout.strip() if got.returncode == 0 else 'ERROR ' + got.stderr.strip()


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
got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-w', '-l', TOP + '/pg/server.log',
          'start'], stdin=subprocess.DEVNULL)
ok('...started on %d' % PGPORT, psql('SELECT 1') == '1', got.stderr[-300:])

PROBE_HEAD = r'''
import json, os, signal, sys, time
signal.signal(signal.SIGTERM, lambda *a: None)       # "the daemon starts again": not here
sys.argv = ['x']
sys.path.insert(0, %r)
import otp as m
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.load_config(saved=st.settings_saved())
m.HA_STORE['store'] = st
m.sealing_key(make=True)


class Daemon(object):
    def __init__(self, store):
        self.store = store

    def reader(self):
        return self.store

    def changed(self, *a):
        pass

    def reload_all(self, *a):
        pass

    def cluster_nodes(self):
        return []


class H(object):
    def __init__(self, body=None):
        self.store, self.d, self._body, self.args = st, Daemon(st), body or {}, {}
        self.headers = {}
        self.route_path = ''

    def me(self, *a, **k):
        return {'name': 'tester', 'role': 'fulladmin'}

    def body(self):
        return self._body


def call(method, path, body=None):
    try:
        return m.ROUTES[(method, path)](H(body)), None
    except m.ApiError as e:
        return None, '%%s %%s' %% (getattr(e, 'status', getattr(e, 'code', '')), e)


def job():
    for _ in range(600):
        j = m.job_read() or {}
        if not j.get('running'):
            return j
        time.sleep(0.2)
    return {'error': 'still running'}


out = {}
''' % OUT

try:
    # ---- the agent ---------------------------------------------------------------------------
    if sh(['id', 'otp-db-agent']).returncode != 0:
        sh(['useradd', '--system', '--no-create-home', '--home-dir', TOP + '/agent/state', '--shell',
            '/sbin/nologin', 'otp-db-agent'])
    for d, mo in (('agent', 0o755), ('agent/lib', 0o755), ('agent/etc', 0o700), ('agent/state', 0o700),
                  ('agent/log', 0o750), ('agent/pki', 0o755)):
        os.makedirs(TOP + '/' + d, mode=mo, exist_ok=True)
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
    p = subprocess.Popen(AGENT, env=AENV, stdout=open(TOP + '/agent/out.log', 'a'), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL)
    PIDS.append(p)
    for _ in range(60):
        try:
            socket.create_connection(('127.0.0.1', APORT), timeout=1).close()
            break
        except OSError:
            time.sleep(0.25)
    code = sh(AGENT + ['--new-code'], env=AENV).stdout.strip()
    ok('the agent runs and makes a join code', code.startswith('ODBA1.'))

    # ---- the node on SQLite, joined ------------------------------------------------------------
    N = TOP + '/node'
    for d in ('', '/log', '/run'):
        os.makedirs(N + d, mode=0o700, exist_ok=True)
    with open(N + '/config.json', 'w') as f:
        json.dump({'db_engine': 'sqlite', 'node_name': 'n1'}, f)
    os.chmod(N + '/config.json', 0o600)
    NENV = {k: v for k, v in os.environ.items() if not k.startswith('OTP_')}
    NENV.update(OTP_STATE=N, OTP_CONFIG=N + '/config.json', OTP_LOGDIR=N + '/log', OTP_RUN=N + '/run',
                OTP_HA_CA=N + '/ha-ca.pem', OTP_HA_NO_RESTART='1', OTP_STAY_ROOT='1', OTP_DBAGENT_EVERY='2')

    def otp(*args, stdin=None):
        return sh([PY, OUT + '/otp.py'] + list(args), input=stdin, env=NENV)

    def probe(body):
        got = sh([PY, '-c', PROBE_HEAD + body + "\nprint('JSON' + json.dumps(out, default=str))\n"], env=NENV)
        line = [x for x in got.stdout.splitlines() if x.startswith('JSON')]
        if not line:
            print(got.stdout[-1500:], got.stderr[-2500:])
            return {}
        return json.loads(line[-1][4:])

    LOADP = r'''
H.arg = lambda self, k, d=None: self.args.get(k, d)
m.CONFIG['perf_meter'] = True
def load():
    try:
        return m.ROUTES[('GET', '/api/load')](H()), None
    except m.ApiError as e:
        return None, str(e)
'''
    # ---- no agent: as before ----------------------------------------------------------------------
    v = probe(LOADP + r'''
g, e = load()
out['keys'] = sorted((g or {}).keys()); out['err'] = e
m.CONFIG['perf_meter'] = False
g, e = load()
out['off'] = e
''')
    ok('no agent: /api/load as before (no dbservers)', v.get('keys') and 'dbservers' not in v['keys'] and not v.get('err'), v)
    ok('the meter off: refused as before', 'switched off' in str(v.get('off')), v.get('off'))

    otp('--status')
    got = otp('--db-agent-join', '-', stdin=code + '\n')
    ok('the node on SQLite joins the agent', got.returncode == 0, got.stdout[-400:] + got.stderr[-400:])

    # ---- joined -----------------------------------------------------------------------------------
    v = probe(LOADP + r'''
g, e = load(); time.sleep(1.2); m.DBAGENT_STATE['load_at'] = 0
g, e = load()
out['err'] = e
rows = (g or {}).get('dbservers') or []
out['n'] = len(rows); out['r'] = rows[0] if rows else {}
now = time.time()
st.set_meta('node:n2', json.dumps({'at': now, 'name': 'n2'}))   # a node of the cluster (1.0.295)
st.set_meta('load:db:n2', json.dumps({'at': now - 30, 'kind': 'db', 'node': 'n2', 'host': '192.0.2.7', 'cpu': 5.0, 'mem_used': 1, 'mem_total': 2,
                                      'db': {'running': True}}))
st.set_meta('load:db:n3', json.dumps({'at': now - 7200, 'kind': 'db', 'node': 'n3'}))
g, e = load()
out['nodes'] = [(x.get('node'), x.get('name'), round(x.get('age') or 0)) for x in (g or {}).get('dbservers') or []]
''')
    r = v.get('r') or {}
    db = r.get('db') or {}
    ok('joined: /api/load has dbservers, one row - this node\'s server', v.get('n') == 1 and not v.get('err'), v)
    ok('...its name, node, address, kind', r.get('name') == 'db:n1' and r.get('node') == 'n1' and r.get('kind') == 'db' and
       r.get('host') == '127.0.0.1' and r.get('age') == 0.0, r)
    ok('...the machine: processor, memory, disks, network, cores, load', isinstance(r.get('cpu'), (int, float)) and
       (r.get('mem_total') or 0) > 0 and 'disk_rd' in r and 'net_rx' in r and (r.get('cores') or 0) > 0 and len(r.get('load') or []) == 3, r)
    ok('...its database: PostgreSQL 16 running, since, connections, its disk', db.get('running') is True and
       str(db.get('version', '')).startswith('16') and (db.get('started') or 0) > 0 and (db.get('connections') or 0) >= 1 and
       ((db.get('disk') or {}).get('total') or 0) > 0, db)
    ok('...the server\'s short name (from its agent\'s facts), not down', r.get('down') is not True and 'server' in r, r)
    ok('the other node\'s from its row (its age); older than an hour left out',
       v.get('nodes') == [['n1', 'db:n1', 0], ['n2', 'db:n2', 30]], v.get('nodes'))

    # ---- the agent stopped --------------------------------------------------------------------------
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=40)
    PIDS.remove(p)
    v = probe(LOADP + r'''
t0 = time.time(); g, e = load(); out['t1'] = round(time.time() - t0, 1)
out['r1'] = ((g or {}).get('dbservers') or [{}])[0]
t0 = time.time(); g, e = load(); out['t2'] = round(time.time() - t0, 1)
out['r2'] = ((g or {}).get('dbservers') or [{}])[0]
m.DBAGENT_STATE['ok'] = False
t0 = time.time(); m.DBAGENT_STATE['load_fail_at'] = 0; g, e = load(); out['t3'] = round(time.time() - t0, 1)
out['r3'] = ((g or {}).get('dbservers') or [{}])[0]
''')
    ok('the agent stopped: the row down, said why, the page answered within the short wait',
       (v.get('r1') or {}).get('down') is True and (v.get('r1') or {}).get('said') and v.get('t1', 99) <= 6, v)
    ok('...not asked again for a while: the next answer at once', (v.get('r2') or {}).get('down') is True and v.get('t2', 99) < 1, v)
    ok('...an agent known not to answer: not asked at all', (v.get('r3') or {}).get('down') is True and v.get('t3', 99) < 1 and
       'does not answer' in str((v.get('r3') or {}).get('said')), v)
finally:
    down()

print('ALL %d / %d' % (sum(R), len(R)))
