# t_moves.py VERSION - 1.0.291: moving the database onto the server of this node's otp-db-agent and
# off it, through the page's requests (POST /api/db), in-process on the build's otp.py. On this
# machine, as root, nothing of the installed otp touched:
#   - a PostgreSQL 16 of its own (port 55434), its agent (port 19445, OTP_AGENT_NO_FIREWALL);
#   - an otp node on SQLite in a state folder of its own, joined to the agent (not moved yet);
#   - GET /api/db: the agent for the wizard; try: agent_server; setup by_agent: made by the agent
#     (the account let in, PostgreSQL started again by its agent), refused for another server;
#   - the TLS of the server in use not carried to another one (with an agent; without, as before);
#   - move: the old server's rows left behind; use: onto it - the agent stays, db_here;
#   - layout B: the move refused with its words; another agent is not joined instead;
#   - back to SQLite: the agent let go (agent.json.forgotten), told (leave), said; no agent then.
import json, os, pwd, secrets, shutil, signal, socket, subprocess, sys, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.291'
OUT = '/home/claude/build/out/otp-%s' % VER
PY = '/usr/local/lib/otp/python'
PGBIN = '/usr/lib/postgresql/16/bin'
TOP = '/var/tmp/otp-r291'
PGPORT, APORT = 55434, 19445
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

    otp('--status')
    got = otp('--db-agent-join', '-', stdin=code + '\n')
    ok('the node on SQLite joins the agent (the database not moved yet)', got.returncode == 0,
       got.stdout[-400:] + got.stderr[-400:])

    # ---- 1. onto the agent's server ------------------------------------------------------------
    v = probe(r'''
g, e = call('GET', '/api/db')
out['agent'] = (g or {}).get('agent'); out['get_err'] = e
# the TLS of the server in use not carried to another one - with an agent; without, as before
m.CONFIG['db_tls'] = 'verify-full'; m.CONFIG['db_tls_ca'] = '/x/ca.pem'
c = m.engine_asked({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': %d, 'db_name': 'otp2',
                    'db_user': 'otp2', 'db_password': 'x'})
out['tls_agent'] = [c.get('db_tls'), c.get('db_tls_ca')]
c = m.engine_asked({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': %d, 'db_name': 'otp2',
                    'db_user': 'otp2', 'db_password': 'x', 'db_tls': 'require'})
out['tls_asked'] = c.get('db_tls')
on = m.db_agent_on
m.db_agent_on = lambda: False
c = m.engine_asked({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': %d, 'db_name': 'otp2',
                    'db_user': 'otp2', 'db_password': 'x'})
out['tls_no_agent'] = c.get('db_tls')
g, e = call('GET', '/api/db')
out['no_agent_key'] = 'agent' in (g or {})
t, e = call('POST', '/api/db', {'action': 'try', 'settings': {'db_engine': 'postgres', 'db_host': '127.0.0.1',
            'db_port': %d, 'db_name': 'otp2', 'db_user': 'otp2'}})
out['no_agent_try'] = 'agent_server' in (t or {})
m.db_agent_on = on
m.CONFIG['db_tls'] = ''; m.CONFIG['db_tls_ca'] = ''
S = {'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': %d, 'db_name': 'otp2', 'db_user': 'otp2'}
t, e = call('POST', '/api/db', {'action': 'try', 'settings': S})
out['try1'] = {k: (t or {}).get(k) for k in ('reached', 'writable', 'agent_server', 'in_use')}; out['try1_err'] = e
t, e = call('POST', '/api/db', {'action': 'try', 'settings': dict(S, db_port=5432)})
out['try_other'] = (t or {}).get('agent_server')
r, e = call('POST', '/api/db', {'action': 'setup', 'settings': dict(S, db_port=5432), 'by_agent': True})
out['setup_other'] = e
r, e = call('POST', '/api/db', {'action': 'setup', 'settings': S, 'by_agent': True})
out['setup'] = {'made': (r or {}).get('made'), 'pw': bool((r or {}).get('password')),
                'try': {k: ((r or {}).get('try') or {}).get(k) for k in ('reached', 'writable')}}
out['setup_err'] = e
S['db_password'] = (r or {}).get('password') or ''
t, e = call('POST', '/api/db', {'action': 'try', 'settings': S})
out['try2'] = {k: (t or {}).get(k) for k in ('reached', 'writable', 'rows', 'agent_server')}
for k in ('dbtls:server:n1', 'dbagent:node:n1', 'load:db:n1', 'r291:keep'):
    st.set_meta(k, '{"x": 1}')
r, e = call('POST', '/api/db', {'action': 'move', 'settings': S})
out['move_err'] = e
j = job()
out['move'] = {k: j.get(k) for k in ('error',)}; out['move_rows'] = (j.get('result') or {}).get('rows')
far = m.db_open(S)
out['far_meta'] = sorted(r['k'] for r in far.rows("SELECT k FROM meta WHERE k IN ('dbtls:server:n1', "
                         "'dbagent:node:n1', 'load:db:n1', 'r291:keep')"))
far.close()
u, e = call('POST', '/api/db', {'action': 'use', 'settings': S})
out['use'] = u; out['use_err'] = e
m.load_config(saved=None)
out['here_after'] = m.db_agent_here()
out['file'] = {k: v for k, v in json.load(open(str(m.CONFIG_FILE))).items() if k != 'db_password'}
''' % ((PGPORT,) * 5))
    a = v.get('agent') or {}
    ok('GET /api/db with an agent: the agent for the wizard (its server, its port, not here yet)',
       a.get('db_host') == '127.0.0.1' and a.get('db_port') == PGPORT and a.get('here') is False and
       a.get('engine') == 'postgres' and a.get('layout_b') is False, v)
    ok('the TLS of the server in use not carried to another server (with an agent)', v.get('tls_agent') == ['', ''], v.get('tls_agent'))
    ok('...asked for, it is what was asked', v.get('tls_asked') == 'require', v.get('tls_asked'))
    ok('...without an agent as before (carried)', v.get('tls_no_agent') == 'verify-full', v.get('tls_no_agent'))
    ok('...without an agent no agent in GET /api/db, no agent_server in try', v.get('no_agent_key') is False and
       v.get('no_agent_try') is False, v)
    ok('try: the agent\'s server, nothing there yet', v.get('try1') == {'reached': False, 'writable': False,
       'agent_server': True, 'in_use': False} or (v.get('try1') or {}).get('agent_server') is True and
       not (v.get('try1') or {}).get('writable'), v.get('try1'))
    ok('...another server: not the agent\'s', v.get('try_other') is False, v.get('try_other'))
    ok('setup by_agent on another server: refused', '400' in str(v.get('setup_err') is None and v.get('setup_other')) and
       'database agent' in str(v.get('setup_other')), v.get('setup_other'))
    s = v.get('setup') or {}
    made = ' | '.join(s.get('made') or [])
    ok('setup by_agent: made by the agent - the database, the account, a password made up', s.get('pw') and
       'otp2' in made and (s.get('try') or {}).get('writable') is True, [v.get('setup_err'), s])
    print('     made: ' + made)
    ok('...PostgreSQL started again by its agent when it had to listen first, or nothing to restart',
       'started again by its agent' in made or 'has to start again' not in made, made)
    ok('...the account is let in by pg_hba.conf from this node', psql("SELECT count(*) FROM pg_hba_file_rules "
       "WHERE 'otp2' = ANY(user_name) AND 'otp2' = ANY(database)") not in ('0', ''), psql(
       "SELECT line_number, database, user_name, address FROM pg_hba_file_rules"))
    ok('...the try afterwards: reached, writable, empty', v.get('try2') == {'reached': True, 'writable': True,
       'rows': 0, 'agent_server': True}, v.get('try2'))
    ok('move: carried', not v.get('move_err') and not (v.get('move') or {}).get('error') and v.get('move_rows'),
       [v.get('move_err'), v.get('move')])
    ok('...the old server\'s rows left behind (dbtls:server, dbagent:node, load:db), otp\'s kept',
       v.get('far_meta') == ['r291:keep'], v.get('far_meta'))
    u = v.get('use') or {}
    ok('use: switched onto the agent\'s server - the agent stays (nothing said of letting it go)',
       u.get('restarting') and 'agent' not in u, [u, v.get('use_err')])
    ok('...config.json names it; db_agent_here() now', (v.get('file') or {}).get('db_name') == 'otp2' and
       (v.get('file') or {}).get('db_engine') == 'postgres' and v.get('here_after') is True,
       [v.get('file'), v.get('here_after')])
    ok('...agent.json still there', os.path.exists(N + '/db-agent/agent.json'))

    # ---- 2. layout B: refused with its words; another agent not joined instead ---------------------
    v = probe(r'''
g, e = call('GET', '/api/db')
out['agent'] = (g or {}).get('agent')
m.in_cluster = lambda s: True
m.CONFIG['ha_mode'] = 'replicated'
g, e = call('GET', '/api/db')
out['agent_b'] = (g or {}).get('agent')
for act in ('move', 'use', 'setup'):
    r, e = call('POST', '/api/db', {'action': act, 'settings': {'db_engine': 'sqlite'}})
    out['refused_' + act] = e
m.CONFIG['ha_mode'] = 'shared'
r, e = call('POST', '/api/db', {'action': 'move', 'settings': {'db_engine': 'sqlite'}})
out['refused_shared'] = e
''')
    ok('on the agent\'s server: GET says here', (v.get('agent') or {}).get('here') is True, v.get('agent'))
    ok('layout B (replicated, the database on the agent\'s server): layout_b in GET', (v.get('agent_b') or {}).get('layout_b') is True,
       v.get('agent_b'))
    ok('...move, use and setup refused with its words and the way out', all(
        '409' in str(v.get('refused_' + a)) and 'server of its own' in str(v.get('refused_' + a)) and
        '--ha-standalone' in str(v.get('refused_' + a)) for a in ('move', 'use', 'setup')),
       [v.get('refused_' + a) for a in ('move', 'use', 'setup')])
    ok('...shared: the refusal as before', '409' in str(v.get('refused_shared')) and
       'server of its own' not in str(v.get('refused_shared')), v.get('refused_shared'))

    # ---- 3. back onto SQLite: the agent let go ---------------------------------------------------
    v = probe(r'''
S = {'db_engine': 'sqlite'}
t, e = call('POST', '/api/db', {'action': 'try', 'settings': S})
out['try'] = {k: (t or {}).get(k) for k in ('reached', 'rows', 'agent_server')}
r, e = call('POST', '/api/db', {'action': 'empty', 'settings': S}); out['empty_err'] = e
r, e = call('POST', '/api/db', {'action': 'move', 'settings': S}); out['move_err'] = e
j = job(); out['move'] = j.get('error')
u, e = call('POST', '/api/db', {'action': 'use', 'settings': S})
out['use'] = u; out['use_err'] = e
out['ev'] = [r['words'] for r in st.db.rows("SELECT words FROM events WHERE words LIKE '%agent%' ORDER BY id DESC LIMIT 5")]
''')
    ok('back to SQLite: the file is not the agent\'s server', (v.get('try') or {}).get('agent_server') is False, v.get('try'))
    ok('...emptied, carried', not v.get('empty_err') and not v.get('move_err') and not v.get('move'),
       [v.get('empty_err'), v.get('move_err'), v.get('move')])
    u = v.get('use') or {}
    ok('...use: the agent let go and said so', u.get('restarting') and 'no longer looks after this node' in
       str(u.get('agent')) and 'db_admin is local again' in str(u.get('agent')), [u, v.get('use_err')])
    ok('...agent.json -> agent.json.forgotten', not os.path.exists(N + '/db-agent/agent.json') and
       os.path.exists(N + '/db-agent/agent.json.forgotten'), os.listdir(N + '/db-agent'))
    audit = open(TOP + '/agent/log/audit.log').read()
    ok('...the agent told this node leaves it (leave in its audit)', '"leave"' in audit, audit[-400:])
    v = probe(r'''
g, e = call('GET', '/api/db')
out['engine'] = (g or {}).get('engine'); out['agent'] = 'agent' in (g or {})
t, e = call('POST', '/api/db', {'action': 'try', 'settings': {'db_engine': 'sqlite'}})
out['try_key'] = 'agent_server' in (t or {})
out['on'] = m.db_agent_on()
''')
    ok('afterwards: on SQLite, no agent - GET without agent, try without agent_server', v.get('engine') == 'sqlite' and
       v.get('agent') is False and v.get('try_key') is False and v.get('on') is False, v)
    got = otp('--status')
    ok('...--status has no database server line', 'otp-db-agent' not in got.stdout, got.stdout[-400:])
finally:
    down()
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
