"""t_fix.py - 1.0.329: the database agent's databases and accounts are each one cluster's; ones
there before are taken over only when they are otp's kind. The agent's checks with its client
list in a temp folder; PostgreSQL's on the container's own server (roles and databases named
r329_*, taken away again); MariaDB's with its answers given.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile, threading, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.329'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r329_')
atexit.register(lambda: shutil.rmtree(TOP, True))
os.environ['OTP_STATE'] = TOP + '/hs'
os.makedirs(TOP + '/hs')
sys.path.insert(0, V + '/deploy')
sys.argv = ['otp-db-agent']
spec = importlib.util.spec_from_file_location('otp_db_agent', V + '/deploy/otp_db_agent.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
import otp_pg_ops as O                                  # noqa: E402

# ==== 1 the agent: one cluster's names
cdir, sdir = TOP + '/conf', TOP + '/state'
os.makedirs(cdir); os.makedirs(sdir)
now = time.time()
H1, H2, H3 = 'a' * 64, 'b' * 64, 'c' * 64
cl = [{'name': 'n1', 'fp': 'f1', 'key': 'k', 'at': now, 'seen': now, 'issuers': [H1], 'issuers_seen': [H1], 'ca': ''},
      {'name': 'n2', 'fp': 'f2', 'key': 'k', 'at': now, 'seen': now, 'issuers': [H1], 'issuers_seen': [H1], 'ca': ''},
      {'name': 'x1', 'fp': 'f3', 'key': 'k', 'at': now, 'seen': now, 'issuers': [H2], 'issuers_seen': [H2], 'ca': ''}]
json.dump(cl, open(cdir + '/clients.json', 'w'))
r = A.Root.__new__(A.Root)
r.c = {'dir': cdir, 'state': sdir}
r.lock, r.work, r.busy, r.stopping = threading.Lock(), threading.Lock(), None, False
ran = []


class Ops:
    Refused = O.Refused

    @staticmethod
    def run_op(op, args, c):
        ran.append((op, dict(args)))
        return {'said': 'done'}


r.ops = Ops
mine = {'n1': [H1], 'n2': [H1], 'x1': [H2]}
r.issuers_now = lambda node, der: mine[node]


def ask(node, op, args):
    try:
        r.long_op(op, args, node)
        return 'done'
    except O.Refused as e:
        return str(e)


ok('dbmake by n1: done, recorded', ask('n1', 'dbmake', {'name': 'otp', 'user': 'otp'}) == 'done' and
   json.load(open(sdir + '/names.json'))['db']['otp']['node'] == 'n1')
ok('the other node of its cluster (n2): pg_allow done', ask('n2', 'pg_allow', {'db': 'otp', 'user': 'otp'}) == 'done')
got = ask('x1', 'my_allow', {'db': 'otp', 'user': 'other'})
ok('another cluster (x1): the database refused, named', 'another cluster' in got and 'database otp' in got, got)
got = ask('x1', 'pg_prepare', {'db': 'x1db', 'user': 'otp'})
ok('another cluster: the account refused too', 'account otp' in got, got)
ok('...and nothing run for it', [x for x in ran if x[1].get('db') == 'x1db'] == [])
ok('another cluster, names of its own: done', ask('x1', 'dbmake', {'name': 'x1db', 'user': 'x1user'}) == 'done')
ok('...n1 refused those', 'another cluster' in ask('n1', 'pg_allow', {'db': 'x1db', 'user': 'x1user'}))
ok('names in another case are the same name', 'another cluster' in ask('x1', 'pg_allow', {'db': 'OTP', 'user': 'x1user'}))
ok('an op with no names (pg_restart) as before', ask('x1', 'pg_restart', {}) == 'done')
# the owner's cluster renewed its authority: the node, verified under the new one, still in
mine['n1'] = [H3]
cl[0]['issuers'], cl[0]['issuers_seen'] = [H3], [H1, H3]
json.dump(cl, open(cdir + '/clients.json', 'w'))
ok('the cluster\'s authority renewed (seen before): still its', ask('n2', 'pg_allow', {'db': 'otp', 'user': 'otp'}) == 'done')
# the owner gone for 30 days: taken over
for x in cl:
    if x['name'] in ('n1', 'n2'):
        x['seen'] = x['at'] = now - 40 * 86400
json.dump(cl, open(cdir + '/clients.json', 'w'))
ok('its nodes gone 30 days: another cluster takes it', ask('x1', 'pg_allow', {'db': 'otp', 'user': 'otp'}) == 'done'
   and json.load(open(sdir + '/names.json'))['db']['otp']['node'] == 'x1')
# no record (an agent before 1.0.329): the first asks, the server's checks decide
os.unlink(sdir + '/names.json')
ok('no record: the first cluster asking takes it', ask('n1', 'pg_allow', {'db': 'otp', 'user': 'otp'}) == 'done')
src = open(V + '/deploy/otp_db_agent.py').read()
ok('names checked before the operation, recorded after it',
   src.index('self.names_check(node, mine, names)') < src.index('out = self.ops.run_op(op, args, self.c)', src.index('def long_op'))
   < src.index('self.names_put(node, names, mine)'))

# ==== 2 PostgreSQL: one there before taken only when it is otp's kind
conf = {'pg_port': 5432}


def pg(q, db='postgres'):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-XAtq', '-p', '5432', '-d', db, '-c', q],
                          capture_output=True, text=True)


up = pg('SELECT 1').stdout.strip() == '1'
if not up:
    ok('PostgreSQL on 5432 for the checks', False, 'not running')
else:
    def drop():
        for d in ('r329_app', 'r329_otp', 'r329_other'):
            pg('DROP DATABASE IF EXISTS %s' % d)
        for u in ('r329_app', 'r329_otp'):
            pg('DROP ROLE IF EXISTS %s' % u)
    drop()
    atexit.register(drop)
    pg('CREATE ROLE r329_app LOGIN'); pg('CREATE DATABASE r329_app OWNER r329_app'); pg('CREATE DATABASE r329_other OWNER r329_app')
    pg('CREATE ROLE r329_otp LOGIN'); pg('CREATE DATABASE r329_otp OWNER r329_otp')
    try:
        O.pg_owns_only(conf, 'r329_app', 'r329_app'); e = None
    except O.Refused as x:
        e = x
    ok('pg: an application\'s account owning another database - refused', e is not None and 'r329_other' in str(e), e)
    try:
        O.pg_owns_only(conf, 'r329_otp', 'r329_otp'); e = None
    except O.Refused as x:
        e = x
    ok('pg: otp\'s kind (owns its own database only) - taken', e is None, e)
    try:
        O.pg_owns_only(conf, 'r329_otp', 'r329_app'); e = None
    except O.Refused as x:
        e = x
    ok('pg: a database owned by another - refused', e is not None and 'owned by r329_app' in str(e), e)
    try:
        O.pg_owns_only(conf, 'r329_new', 'r329_newdb'); e = None
    except O.Refused as x:
        e = x
    ok('pg: neither there - free', e is None, e)
    got = None
    try:
        O.op_pg_allow({'db': 'r329_app', 'user': 'r329_app', 'peers': ['192.0.2.9']}, conf)
    except O.Refused as x:
        got = x
    ok('pg_allow: refused before pg_hba is touched', got is not None and 'owns other databases' in str(got), got)
    drop()

# ==== 3 MariaDB: the answers given
said = {}


def fake_my(conf, text, secret=''):
    if text.startswith('SELECT Host FROM mysql.user'):
        return said.get('hosts', '')
    if text.startswith('SHOW GRANTS'):
        return said.get('grants', '')
    if 'FROM mysql.db' in text:
        return said.get('others', '')
    return ''


O.my_sql = fake_my
cases = [
    ('my: an account not there, a database not there - free', {}, True),
    ('my: otp\'s kind (USAGE and its database) - taken',
     {'hosts': 'localhost\n10.0.0.5', 'grants': "GRANT USAGE ON *.* TO `otp`@`localhost` IDENTIFIED BY PASSWORD '*AB'\n"
                                                "GRANT ALL PRIVILEGES ON `otp`.* TO `otp`@`localhost`"}, True),
    ('my: its database written with \\_ - taken',
     {'hosts': 'localhost', 'grants': "GRANT ALL PRIVILEGES ON `otp`.* TO `otp`@`localhost`"}, True),
    ('my: rights on another database - refused',
     {'hosts': 'localhost', 'grants': "GRANT USAGE ON *.* TO `otp`@`localhost`\nGRANT SELECT ON `wordpress`.* TO `otp`@`localhost`"}, False),
    ('my: a global right (RELOAD) - refused', {'hosts': 'localhost', 'grants': "GRANT RELOAD ON *.* TO `otp`@`localhost`"}, False),
    ('my: a role granted - refused', {'hosts': 'localhost', 'grants': "GRANT `admin` TO `otp`@`localhost`"}, False),
    ('my: the database with other accounts on it - refused', {'others': 'wp@localhost'}, False),
]
for n, s, good in cases:
    said = s
    try:
        O.my_owns_only({}, 'otp', 'otp'); e = None
    except O.Refused as x:
        e = x
    ok(n, (e is None) == good, e)
pgsrc = open(V + '/deploy/otp_pg_ops.py').read()
ok('dbmake and my_allow check before anything is changed',
   pgsrc.index('my_owns_only(conf, user, name)') < pgsrc.index("CREATE DATABASE IF NOT EXISTS `%s`")
   and 'my_owns_only(conf, user, db)\n    sqls' in pgsrc)
ok('pg_prepare checks before ALTER ROLE', pgsrc.index('pg_owns_only(conf, user, db, have)') < pgsrc.index("'%s ROLE \"%s\" WITH LOGIN PASSWORD %s'"))
cs = json.load(open(V + '/web/lang/cs.json'))
ok('its words in Czech', any(v['source'].startswith('the {0} {1} on this server is') and v['text']
                             for v in cs['patterns'].values()))
print('ALL %d / %d' % (sum(R), len(R)))
