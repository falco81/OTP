# t_local.py VERSION - 1.0.292: this machine's database shown as a database server (db_local_card),
# in-process on the build's otp.py. On this machine, as root, nothing of the installed otp touched:
#   - a PostgreSQL 16 of its own (port 55435) and an otp node on it (127.0.0.1, no agent);
#   - off (the default): no `local` in GET /api/db-agent, nothing written, the watcher idle;
#   - on: the row written by the watcher (no password in it), the tile's facts, look now, another
#     node's row (stale, too old, not of this cluster), a restart waiting, the certificate's end;
#   - off again: the row taken away; with an agent, a server elsewhere or SQLite: nothing.
import json, os, pwd, shutil, signal, subprocess, sys
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.292'
OUT = '/home/claude/build/out/otp-%s' % VER
PY = '/usr/local/lib/otp/python'
PGBIN = '/usr/lib/postgresql/16/bin'
TOP = '/var/tmp/otp-r292'
PGPORT = 55435
PW = 'r292-Pw-' + os.urandom(6).hex()
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


def pgstop():
    if os.path.exists(TOP + '/pg/postmaster.pid'):
        sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-m', 'fast', '-w', 'stop'])


pgstop()
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
    f.write("port = %d\nlisten_addresses = '127.0.0.1'\nunix_socket_directories = '/var/run/postgresql'\n" % PGPORT)
os.makedirs('/var/run/postgresql', exist_ok=True)
os.chown('/var/run/postgresql', pg.pw_uid, pg.pw_gid)
got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', TOP + '/pg', '-w', '-l', TOP + '/pg/server.log',
          'start'], stdin=subprocess.DEVNULL)
ok('...started on %d' % PGPORT, psql('SELECT 1') == '1', got.stderr[-300:])
psql("CREATE ROLE otp3 LOGIN PASSWORD '%s'" % PW)
psql('CREATE DATABASE otp3 OWNER otp3')

PROBE_HEAD = r'''
import json, os, signal, sys, threading, time
signal.signal(signal.SIGTERM, lambda *a: None)
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


def row():
    v = st.get_meta('dblocal:node:n1')
    return json.loads(v) if v else None


def wait(cond, s=15):
    for _ in range(int(s * 5)):
        if cond():
            return True
        time.sleep(0.2)
    return False


out = {}
''' % OUT

N = TOP + '/node'
for d in ('', '/log', '/run'):
    os.makedirs(N + d, mode=0o700, exist_ok=True)
with open(N + '/config.json', 'w') as f:
    json.dump({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': PGPORT, 'db_name': 'otp3',
               'db_user': 'otp3', 'db_password': PW, 'node_name': 'n1'}, f)
os.chmod(N + '/config.json', 0o600)
NENV = {k: v for k, v in os.environ.items() if not k.startswith('OTP_')}
NENV.update(OTP_STATE=N, OTP_CONFIG=N + '/config.json', OTP_LOGDIR=N + '/log', OTP_RUN=N + '/run',
            OTP_HA_CA=N + '/ha-ca.pem', OTP_HA_NO_RESTART='1', OTP_STAY_ROOT='1', OTP_DBLOCAL_EVERY='2')


def probe(body):
    got = sh([PY, '-c', PROBE_HEAD + body + "\nprint('JSON' + json.dumps(out, default=str))\n"], env=NENV)
    line = [x for x in got.stdout.splitlines() if x.startswith('JSON')]
    if not line:
        print(got.stdout[-1500:], got.stderr[-2500:])
        return {}
    return json.loads(line[-1][4:])


try:
    # ---- off: as before ---------------------------------------------------------------------------
    v = probe(r'''
out['default'] = m.DEFAULTS.get('db_local_card')
out['only_when'] = m.ONLY_WHEN.get('db_local_card')
out['in_pane'] = 'db_local_card' in m.PANES['db']
out['on'] = m.db_local_on(); out['here'] = m.db_local_here()
g, e = call('GET', '/api/db-agent')
out['local_key'] = 'local' in (g or {}); out['get_err'] = e
out['look'] = m.db_local_look(st)
threading.Thread(target=m.db_local_watch, args=(Daemon(st),), daemon=True).start()
time.sleep(5)
out['rows'] = [r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'dblocal:%'")]
r, e = call('POST', '/api/db-agent', {'action': 'look'})
out['look_post_err'] = e
out['rows2'] = [r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'dblocal:%'")]
''')
    ok('the setting: off by default, only for PostgreSQL / MariaDB', v.get('default') is False and
       v.get('only_when') == ['db_engine', 'sqlite-not'], v)
    ok('...in the pane of The database', v.get('in_pane') is True, v.get('in_pane'))
    ok('off: the database is here (no agent), not looked at', v.get('here') is True and v.get('on') is False, v)
    ok('off: GET /api/db-agent has no `local`', v.get('local_key') is False and not v.get('get_err'), v)
    ok('off: nothing looked at, nothing written (the watcher idle for 5 s)', v.get('look') is None and
       v.get('rows') == [], v)
    ok('off: Look now is the agent\'s as before (nothing of this machine\'s written)', v.get('rows2') == [], v)

    # ---- on --------------------------------------------------------------------------------------
    v = probe(r'''
m.CONFIG['db_local_card'] = True
os.environ['DUMMY'] = '1'
st.set_meta('dbtls:server:n1', json.dumps({'cert_end': time.time() + 10 * 86400}))
threading.Thread(target=m.db_local_watch, args=(Daemon(st),), daemon=True).start()
out['written'] = wait(lambda: row() is not None)
raw = st.get_meta('dblocal:node:n1') or ''
out['no_pw'] = %r not in raw and 'password' not in raw
g, e = call('GET', '/api/db-agent')
loc = (g or {}).get('local') or []
out['n'] = len(loc)
out['me'] = loc[0] if loc else {}
a1 = (row() or {}).get('at')
time.sleep(3)
out['again'] = (row() or {}).get('at', 0) > (a1 or 0)
r, e = call('POST', '/api/db-agent', {'action': 'look'})
out['look'] = bool((r or {}).get('row')) and 'local' in ((r or {}).get('view') or {}); out['look_err'] = e
# another node's rows: of this cluster (stale), too old, not of this cluster
m.host_nodes = lambda s: ['n1', 'n2', 'n4']
now = time.time()
st.set_meta('dblocal:node:n2', json.dumps({'at': now - 600, 'host': '127.0.0.1', 'port': 5432, 'engine': 'postgres', 'facts': {'running': True}}))
st.set_meta('dblocal:node:n4', json.dumps({'at': now - 8 * 86400, 'host': '127.0.0.1', 'port': 5432, 'engine': 'postgres', 'facts': {}}))
st.set_meta('dblocal:node:n3', json.dumps({'at': now, 'host': '127.0.0.1', 'port': 5432, 'engine': 'postgres', 'facts': {}}))
g, e = call('GET', '/api/db-agent')
out['nodes'] = [(x['node'], x['me'], x['stale']) for x in (g or {}).get('local') or []]
# the server's own settings waiting for a restart
st.db.run("SELECT 1")
''' % PW + r'''
os.system("runuser -u postgres -- %s/psql -XAtq -p %d -c \"ALTER SYSTEM SET shared_buffers = '136MB'\" -c 'SELECT pg_reload_conf()' >/dev/null")
time.sleep(1.5)
g, e = call('GET', '/api/db-agent')
me = [x for x in (g or {}).get('local') or [] if x['me']]
out['restart'] = me[0].get('restart') if me else None
# with an agent: the card is the agent's
on = m.db_agent_on
m.db_agent_on = lambda: True
out['here_agent'] = m.db_local_here()
out['into_agent'] = 'local' in m.db_local_into(st, {})
m.db_agent_on = on
out['here_far'] = m.db_local_here({'db_engine': 'postgres', 'db_host': '192.0.2.10'})
out['here_sock'] = m.db_local_here({'db_engine': 'mariadb', 'db_host': '/run/mysqld/mysqld.sock'})
out['here_lite'] = m.db_local_here({'db_engine': 'sqlite'})
out['move_rows'] = 'dblocal:node:' in m.DB_SERVER_ROWS
''' % (PGBIN, PGPORT))
    me = v.get('me') or {}
    f = me.get('facts') or {}
    ok('on: the watcher writes this node\'s row', v.get('written') is True, v)
    ok('...no password in it', v.get('no_pw') is True)
    ok('GET /api/db-agent: `local`, one row - this node\'s', v.get('n') == 1 and me.get('me') is True and
       me.get('node') == 'n1' and me.get('kind') == 'db' and me.get('name') == 'db:n1', me)
    ok('...its address, engine', me.get('host') == '127.0.0.1' and me.get('port') == PGPORT and
       me.get('engine') == 'postgres', me)
    ok('...the database: running, version 16, its start, connections', f.get('running') is True and
       str(f.get('version', '')).startswith('16') and (f.get('started') or 0) > 0 and (f.get('connections') or 0) >= 1, f)
    ok('...the machine: processors, memory, load, up for, the data\'s disk', (f.get('cpus') or 0) > 0 and
       (f.get('ram') or 0) > 0 and len(f.get('load') or []) == 3 and (f.get('uptime') or 0) > 0 and
       ((f.get('disk') or {}).get('total') or 0) > 0, f)
    ok('...TLS said (off here)', f.get('ssl') is False, f.get('ssl'))
    ok('...its certificate from Encryption to the database server', me.get('cert_by') == 'dbtls' and
       (me.get('cert_end') or 0) > 0, me)
    ok('...not stale, fresh', me.get('stale') is False and me.get('ok') is True, me)
    ok('looked at again every OTP_DBLOCAL_EVERY', v.get('again') is True)
    ok('Look now: a row and the view with `local`', v.get('look') is True and not v.get('look_err'), v)
    ok('the other nodes: of this cluster (stale), too old and not of this cluster left out',
       v.get('nodes') == [['n1', True, False], ['n2', False, True]], v.get('nodes'))
    rs = v.get('restart') or {}
    ok('settings waiting for a restart: said for this node\'s PostgreSQL', 'shared_buffers' in (rs.get('waiting') or [])
       and 'may' in rs, rs)
    ok('with an agent: the card is the agent\'s (not here, no `local`)', v.get('here_agent') is False and
       v.get('into_agent') is False, v)
    ok('a server elsewhere: not this machine\'s; a socket: this machine\'s; SQLite: none',
       v.get('here_far') is False and v.get('here_sock') is True and v.get('here_lite') is False, v)
    ok('a move to another server leaves the row behind', v.get('move_rows') is True)

    # ---- off again: the row taken away ------------------------------------------------------------
    psql("ALTER SYSTEM RESET shared_buffers")
    psql("SELECT pg_reload_conf()")
    v = probe(r'''
out['before'] = row() is not None
m.CONFIG['db_local_card'] = False
threading.Thread(target=m.db_local_watch, args=(Daemon(st),), daemon=True).start()
out['gone'] = wait(lambda: row() is None, 10)
g, e = call('GET', '/api/db-agent')
out['local_key'] = 'local' in (g or {})
''')
    ok('off again: the row there before, taken away by the watcher', v.get('before') is True and v.get('gone') is True, v)
    ok('...GET /api/db-agent as before (no `local`)', v.get('local_key') is False, v)
    v = probe(r'''
m.CONFIG['db_local_card'] = True
m.CONFIG['db_host'] = '192.0.2.10'
st.set_meta('dblocal:node:n1', json.dumps({'at': time.time()}))
threading.Thread(target=m.db_local_watch, args=(Daemon(st),), daemon=True).start()
out['gone'] = wait(lambda: row() is None, 10)
''')
    ok('on, the database no longer on this machine: the old row taken away', v.get('gone') is True, v)
finally:
    pgstop()

print('ALL %d / %d' % (sum(R), len(R)))
