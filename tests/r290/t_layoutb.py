# t_layoutb.py VERSION - 1.0.290: high availability with each node's database on a server of its own
# (layout B), for real on this machine, as root, nothing of the installed otp touched:
#   - two PostgreSQL 16 of their own (db1 55432, db2 55433), an agent for each (19443, 19444,
#     firewalld left alone), two otp nodes in state folders of their own (n1, n2);
#   - --ha-peer-node refused without an agent and when it is --ha-peer;
#   - n1: --ha-setup --ha-peer DB2 --ha-peer-node OTP2 through db1's agent; n2: --ha-join onto db2
#     through its agent - every row copied, both directions replicating;
#   - what is the nodes' own takes the other otp node, never the other database server;
#   - the link's TLS between db1 and db2 through both agents (the daemons' step, in-process);
#   - --ha-resync through the agents; the agent not forgotten while the replication runs through it.
import json, os, pwd, re, secrets, shutil, signal, socket, subprocess, sys, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.290'
OUT = '/home/claude/build/out/otp-%s' % VER
PY = '/usr/local/lib/otp/python'
PGBIN = '/usr/lib/postgresql/16/bin'
TOP = '/var/tmp/otp-r290'
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:700]), flush=True)


def sh(args, **kw):
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    return subprocess.run(args, **kw)


def psql(port, sql, db='postgres'):
    got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/psql', '-XAtq', '-p', str(port), '-d', db,
              '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=sql + ';\n')
    return got.stdout.strip() if got.returncode == 0 else 'ERROR ' + got.stderr.strip()


PIDS = []
DBS = {'db1': 55432, 'db2': 55433}
AGENTS = {'db1': 19443, 'db2': 19444}


def pg_stop(name):
    if os.path.exists('%s/%s/postmaster.pid' % (TOP, name)):
        sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', '%s/%s' % (TOP, name), '-m', 'fast', '-w', 'stop'])


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
    for n in DBS:
        pg_stop(n)


for n in DBS:
    pg_stop(n)
if os.path.isdir(TOP):
    shutil.rmtree(TOP)
os.makedirs(TOP, mode=0o755)
pg = pwd.getpwnam('postgres')
os.makedirs('/var/run/postgresql', exist_ok=True)
os.chown('/var/run/postgresql', pg.pw_uid, pg.pw_gid)
RESTART = {}
for n, port in DBS.items():
    d = '%s/%s' % (TOP, n)
    os.makedirs(d, mode=0o700)
    os.chown(d, pg.pw_uid, pg.pw_gid)
    got = sh(['runuser', '-u', 'postgres', '--', PGBIN + '/initdb', '-D', d, '-E', 'UTF8', '--locale=C.UTF-8',
              '--auth-local=peer', '--auth-host=scram-sha-256'])
    with open(d + '/postgresql.auto.conf', 'a') as f:
        f.write("port = %d\nlisten_addresses = '127.0.0.1'\nunix_socket_directories = '/var/run/postgresql'\n"
                "logging_collector = on\n" % port)
    RESTART[n] = ['/usr/sbin/runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', d, '-w', '-m', 'fast',
                  '-l', d + '/server.log', 'restart']
    sh(['runuser', '-u', 'postgres', '--', PGBIN + '/pg_ctl', '-D', d, '-w', '-l', d + '/server.log', 'start'],
       stdin=subprocess.DEVNULL)
ok('two PostgreSQL 16 of their own: db1 on 55432, db2 on 55433',
   psql(55432, 'SELECT 1') == '1' and psql(55433, 'SELECT 1') == '1')
PW = {'db1': secrets.token_urlsafe(18), 'db2': secrets.token_urlsafe(18)}
for n, port in DBS.items():
    psql(port, "SET log_statement = 'none'; CREATE ROLE otp LOGIN PASSWORD '%s'" % PW[n])
    psql(port, "CREATE DATABASE otp OWNER otp ENCODING 'UTF8' TEMPLATE template0")

try:
    # ---- an agent on each ----------------------------------------------------------------------
    if sh(['id', 'otp-db-agent']).returncode != 0:
        sh(['useradd', '--system', '--no-create-home', '--home-dir', TOP + '/state', '--shell',
            '/sbin/nologin', 'otp-db-agent'])
    AENV = dict(os.environ, OTP_AGENT_NO_FIREWALL='1')
    CMD = {}

    def agent_start(n):
        p = subprocess.Popen(CMD[n], env=AENV, stdout=open('%s/a%s/out.log' % (TOP, n), 'a'),
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        PIDS.append(p)
        for _ in range(60):
            try:
                socket.create_connection(('127.0.0.1', AGENTS[n]), timeout=1).close()
                break
            except OSError:
                time.sleep(0.25)
        return p
    for n in DBS:
        A = '%s/a%s' % (TOP, n)
        for d, m in (('', 0o755), ('/lib', 0o755), ('/etc', 0o700), ('/state', 0o700), ('/log', 0o750),
                     ('/pki', 0o755)):
            os.makedirs(A + d, mode=m, exist_ok=True)
        for f in ('otp_db_agent.py', 'otp_pg_ops.py', 'otp_web.py'):
            shutil.copy(OUT + '/deploy/' + f, A + '/lib/' + f)
        with open(A + '/lib/release', 'w') as f:
            f.write(VER + '\n')
        with open(A + '/etc/agent.json', 'w') as f:
            json.dump({'listen': '127.0.0.1', 'port': AGENTS[n], 'engine': 'postgres', 'pg_port': DBS[n],
                       'user': 'otp-db-agent', 'state': A + '/state', 'log': A + '/log/audit.log',
                       'ha_ca': A + '/pki/ha-ca.pem', 'pg_restart_cmd': RESTART[n], 'advertise': '127.0.0.1'}, f)
        os.chmod(A + '/etc/agent.json', 0o600)
        CMD[n] = [sys.executable, '-I', A + '/lib/otp_db_agent.py', '--config', A + '/etc/agent.json']
        agent_start(n)

    def new_code(n):
        return sh(CMD[n] + ['--new-code'], env=AENV).stdout.strip()

    # ---- two otp nodes (each node's OTP_HA_CA its database server's ha_ca: one path on both, as
    # /etc/pki/otp/ha-ca.pem is - the subscriptions name it, and run on the database server) -----------------------------------------------------------------------
    NENV = {}
    for i, n in ((1, 'db1'), (2, 'db2')):
        N = '%s/n%d' % (TOP, i)
        for d in ('', '/log', '/run', '/web'):
            os.makedirs(N + d, mode=0o700, exist_ok=True)
        with open(N + '/config.json', 'w') as f:
            json.dump({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': DBS[n], 'db_name': 'otp',
                       'db_user': 'otp', 'db_password': PW[n], 'node_name': 'n%d' % i}, f)
        os.chmod(N + '/config.json', 0o600)
        e = {k: v for k, v in os.environ.items() if not k.startswith('OTP_')}
        e.update(OTP_STATE=N, OTP_CONFIG=N + '/config.json', OTP_LOGDIR=N + '/log', OTP_RUN=N + '/run',
                 OTP_HA_CA='%s/a%s/pki/ha-ca.pem' % (TOP, n), OTP_HA_NO_RESTART='1', OTP_STAY_ROOT='1',
                 OTP_DBAGENT_EVERY='2', NO_COLOR='1')
        NENV[i] = e

    def otp(i, *args, stdin=None, env=None):
        kw = {'input': stdin} if stdin is not None else {'stdin': subprocess.DEVNULL}
        return sh([PY, OUT + '/otp.py'] + list(args), env=dict(NENV[i], **(env or {})), **kw)

    for i in (1, 2):
        otp(i, '--status')
    BUNDLE = TOP + '/otp-join-n1.json'
    got = otp(1, '--ha-setup', '--ha-peer', '127.0.0.1', '--ha-peer-port', '55433', '--ha-peer-node', '127.0.0.2',
              '--node-name', 'n1', '--ha-bundle', BUNDLE, '--yes')
    ok('--ha-peer-node without an agent: refused, nothing made', got.returncode != 0 and
       'server of its own' in got.stderr and not os.path.exists(BUNDLE) and
       'replicated' not in open(TOP + '/n1/config.json').read(), got.stdout[-300:] + got.stderr[-300:])

    for i, n in ((1, 'db1'), (2, 'db2')):
        got = otp(i, '--db-agent-join', '-', stdin=new_code(n) + '\n')
        ok('n%d joins the agent of %s (the code on standard input)' % (i, n), got.returncode == 0,
           got.stdout[-400:] + got.stderr[-400:])
    psql(55432, "INSERT INTO meta (k, v) VALUES ('r290:before', 'made on n1 before the cluster')", 'otp')

    got = otp(1, '--ha-setup', '--ha-peer', '127.0.0.2', '--ha-peer-node', '127.0.0.2', '--node-name', 'n1',
              '--ha-bundle', BUNDLE, '--yes')
    ok('--ha-peer and --ha-peer-node one address: refused', got.returncode != 0 and 'one address' in got.stderr and
       not os.path.exists(BUNDLE), got.stderr[-300:])

    # ---- n1: the first node ------------------------------------------------------------------
    got = otp(1, '--ha-setup', '--ha-peer', '127.0.0.1', '--ha-peer-port', '55433', '--ha-peer-node', '127.0.0.2',
              '--node-name', 'n1', '--ha-bundle', BUNDLE, '--yes')
    said = got.stdout + got.stderr
    print(said[-2500:])
    ok('n1 --ha-setup --ha-peer DB2 --ha-peer-node OTP2: done, the bundle written', got.returncode == 0 and
       os.path.exists(BUNDLE), said[-800:])
    m = re.search(r'its passphrase, shown only now: (\S+)', said)
    PHRASE = m.group(1) if m else ''
    ok('...the steps of layout B said (the other database server, --db-agent-join, --ha-tls-repair)',
       'install.sh --db-server postgres --otp-node 127.0.0.2' in said and 'otp --db-agent-join -' in said and
       'otp --ha-tls-repair' in said and '--with-db postgres' not in said, said[-600:])
    c1 = json.load(open(TOP + '/n1/config.json'))
    a1 = json.load(open(TOP + '/n1/db-agent/agent.json'))
    ok('...config.json: replicated, slot 1, ha_peer db2, ha_address its own database server',
       c1.get('ha_mode') == 'replicated' and c1.get('ha_slot') == 1 and c1.get('ha_peer') == '127.0.0.1' and
       c1.get('ha_peer_port') == 55433 and c1.get('ha_address') == '127.0.0.1', c1)
    ok('...agent.json: peer_node the other otp node, node_address its own', a1.get('peer_node') == '127.0.0.2' and
       a1.get('node_address'), a1)
    ok('...db1 made ready by its agent: wal_level logical, the publication',
       psql(55432, 'SHOW wal_level') == 'logical' and
       psql(55432, "SELECT count(*) FROM pg_publication", 'otp') == '1')
    hba = open(TOP + '/db1/pg_hba.conf').read()
    ok('...db1\'s pg_hba.conf lets in the other otp node (127.0.0.2)', '127.0.0.2' in hba, hba[-400:])
    audit = open(TOP + '/adb1/log/audit.log').read()
    ok('...done by db1\'s agent (pg_prepare, pg_publication, fw_allow in its audit)', all(
        '"%s"' % x in audit for x in ('pg_prepare', 'pg_publication', 'fw_allow')), audit[-400:])

    # ---- n2: the join onto db2 -----------------------------------------------------------------
    got = otp(2, '--ha-join', BUNDLE, '--node-name', 'n2', '--yes', env={'OTP_HA_PASSPHRASE': PHRASE})
    said = got.stdout + got.stderr
    print(said[-2500:])
    ok('n2 --ha-join: its database onto db2 through its agent, done', got.returncode == 0 and
       'goes onto 127.0.0.1 (otp-db-agent)' in said, said[-800:])
    ok('...db2\'s agent told the cluster\'s authorities', 'knows the cluster\'s authorities' in said, said[-400:])
    c2 = json.load(open(TOP + '/n2/config.json'))
    a2 = json.load(open(TOP + '/n2/db-agent/agent.json'))
    ok('...config.json: on db2 (55433), replicated, slot 2, ha_peer db1 (55432)', c2.get('db_port') == 55433 and
       c2.get('ha_mode') == 'replicated' and c2.get('ha_slot') == 2 and c2.get('ha_peer_port') == 55432, c2)
    ok('...agent.json: peer_node from the bundle (n1 itself), node_address', a2.get('peer_node') and
       a2.get('node_address'), a2)
    ok('...every row of n1 on db2', 'made on n1' in psql(55433, "SELECT v FROM meta WHERE k = 'r290:before'", 'otp'))
    psql(55432, "INSERT INTO meta (k, v) VALUES ('r290:one', 'n1 to n2')", 'otp')
    psql(55433, "INSERT INTO meta (k, v) VALUES ('r290:two', 'n2 to n1')", 'otp')
    seen = ('', '')
    for _ in range(60):
        seen = (psql(55433, "SELECT v FROM meta WHERE k = 'r290:one'", 'otp'),
                psql(55432, "SELECT v FROM meta WHERE k = 'r290:two'", 'otp'))
        if seen == ('n1 to n2', 'n2 to n1'):
            break
        time.sleep(1)
    ok('both directions replicate: db1 -> db2 and db2 -> db1', seen == ('n1 to n2', 'n2 to n1'), seen)
    ok('...a subscription on each server', psql(55432, 'SELECT count(*) FROM pg_subscription', 'otp') == '1' and
       psql(55433, 'SELECT count(*) FROM pg_subscription', 'otp') == '1')

    # ---- in-process: what is the nodes' own --------------------------------------------------
    probe = r'''
import json, sys, time
sys.argv = ['x']
sys.path.insert(0, %r)
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
otp.load_config(saved=st.settings_saved())
out = {'here': otp.db_agent_here(), 'b': otp.db_agent_layout_b(), 'peer_node': otp.ha_peer_node(),
       'forget': otp.db_agent_forget_refused()}
real = otp.db_agent()
otp.db_agent = lambda: dict(real, peer_node='192.0.2.12', node_address='192.0.2.11')
otp.local_addresses = lambda: {'127.0.0.1', '192.0.2.11'}
out['own'] = otp.ha_own_node()
out['other'] = otp.ha_peer_node()
out['fw_me'] = otp.cluster_addresses(st, otp.node_name())
out['fw_other'] = otp.cluster_addresses(st, 'n-other')
out['vip_peer'] = otp.vip_peer_want(st)
out['bundle_node'] = otp.ha_replicated_bundle_data(st)['peer'].get('node')
out['bundle_addr'] = otp.ha_replicated_bundle_data(st)['peer'].get('address')
out['links'] = otp.db_agent_link_peers()
try:
    out['clock'] = otp.clock_peer_skew(st)[0]
except Exception as e:
    out['clock'] = 'error: %%s' %% e
print('JSON' + json.dumps(out, default=str))
''' % OUT
    got = sh([PY, '-c', probe], env=NENV[1])
    line = [x for x in got.stdout.splitlines() if x.startswith('JSON')]
    p = json.loads(line[0][4:]) if line else {}
    print(p or got.stderr[-1500:])
    ok('in-process n1: db_agent_here, layout B, ha_peer_node the other otp node',
       p.get('here') is True and p.get('b') is True and p.get('peer_node') == '127.0.0.2', p)
    ok('...this node itself: node_address (not its database server)', p.get('own') == '192.0.2.11', p.get('own'))
    ok('...the firewall\'s always-in: the other otp node, not the other database server',
       '192.0.2.12' in (p.get('fw_me') or []) and '127.0.0.1' not in (p.get('fw_me') or []), p.get('fw_me'))
    ok('...the other node lets this node itself in', '192.0.2.11' in (p.get('fw_other') or []) and
       '127.0.0.1' not in (p.get('fw_other') or []), p.get('fw_other'))
    ok('...keepalived\'s other node: the other otp node', p.get('vip_peer') == '192.0.2.12', p.get('vip_peer'))
    ok('...the bundle made again: peer.node this node, peer.address its database server',
       p.get('bundle_node') == '192.0.2.11' and p.get('bundle_addr') == '127.0.0.1', p)
    ok('...pg_hba of the link: the other database server and the other otp node',
       p.get('links') == ['127.0.0.1', '192.0.2.12'], p.get('links'))
    ok('...the other database server\'s clock said as such (never the node\'s)',
       str(p.get('clock') or '').startswith('the database server of'), p.get('clock'))
    ok('...the agent not let go while the replication runs through it', 'take the cluster apart first' in
       str(p.get('forget')), p.get('forget'))
    got = otp(1, '--db-agent-forget', '--yes')
    ok('--db-agent-forget on n1: refused, still joined', got.returncode != 0 and
       'take the cluster apart first' in got.stderr and os.path.exists(TOP + '/n1/db-agent/agent.json'),
       got.stdout[-300:] + got.stderr[-300:])

    # ---- the link's TLS through both agents --------------------------------------------------
    got = otp(1, '--ha-tls-repair')
    ok('--ha-tls-repair on n1: asked', got.returncode == 0, got.stdout[-300:] + got.stderr[-300:])
    tick = r'''
import sys, time
sys.argv = ['x']
sys.path.insert(0, %r)
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
otp.load_config(saved=st.settings_saved())
otp.HA_STORE['store'] = st
end = time.time() + 300
while time.time() < end:
    try:
        otp.heartbeat(st)       # as the daemon writes it: the other node is known by it
    except Exception as e:
        print('heartbeat:', e)
    otp.hatls_tick(st, ask_wait_s=0)
    v = otp.hatls_view(st)
    if v['nodes'] and all(n.get('step') == 'done' for n in v['nodes']) and len(v['nodes']) >= 2:
        time.sleep(6)
        otp.hatls_tick(st, ask_wait_s=0)
        break
    time.sleep(2)
print('DONE', [(n['name'], n.get('step'), n.get('error') or n.get('said')) for n in otp.hatls_view(st)['nodes']])
''' % OUT
    loops = [subprocess.Popen([PY, '-c', tick], env=NENV[i], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True) for i in (1, 2)]
    outs = [x.communicate(timeout=400)[0] for x in loops]
    print('\n'.join(o[-1200:] for o in outs))
    ok('the link\'s steps done on both nodes', all("'done'" in (o.splitlines() or [''])[-1] and
                                                  o.splitlines()[-1].count("'done'") >= 2 for o in outs if o.strip()),
       [o[-300:] for o in outs])
    conn = (psql(55432, 'SELECT subconninfo FROM pg_subscription', 'otp'),
            psql(55433, 'SELECT subconninfo FROM pg_subscription', 'otp'))
    ok('...both subscriptions verify-full', all(re.search(r"sslmode='?verify-full", c) for c in conn),
       [re.sub(r'password=\S+', 'password=*', c) for c in conn])
    ok('...ssl on, on both servers', psql(55432, 'SHOW ssl') == 'on' and psql(55433, 'SHOW ssl') == 'on')
    ok('...put in by their agents (pgtls in both audits)', '"pgtls"' in open(TOP + '/adb1/log/audit.log').read() and
       '"pgtls"' in open(TOP + '/adb2/log/audit.log').read())
    hba = open(TOP + '/db2/pg_hba.conf').read()
    ok('...hostssl lines on db2', 'hostssl' in hba, hba[-400:])
    psql(55432, "INSERT INTO meta (k, v) VALUES ('r290:tls', 'over TLS')", 'otp')
    v = ''
    for _ in range(60):
        v = psql(55433, "SELECT v FROM meta WHERE k = 'r290:tls'", 'otp')
        if v == 'over TLS':
            break
        time.sleep(1)
    ok('...replication goes on over TLS', v == 'over TLS', v)

    # ---- a rebuild of n2 through its agent ---------------------------------------------------
    got = otp(2, '--ha-resync', '--yes')
    ok('n2 --ha-resync: rebuilt from db1', got.returncode == 0 and 'rebuilt from' in got.stdout,
       got.stdout[-500:] + got.stderr[-500:])
    psql(55433, "INSERT INTO meta (k, v) VALUES ('r290:after', 'n2 after the rebuild')", 'otp')
    v = ''
    for _ in range(60):
        v = psql(55432, "SELECT v FROM meta WHERE k = 'r290:after'", 'otp')
        if v == 'n2 after the rebuild':
            break
        time.sleep(1)
    ok('...and replicates again (db2 -> db1)', v == 'n2 after the rebuild', v)
except Exception as e:                                  # noqa: BLE001
    import traceback
    traceback.print_exc()
    ok('the test ran through', False, repr(e))
finally:
    down()
print('ALL %d / %d' % (sum(R), len(R)))
