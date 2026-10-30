# C: two nodes replicating (tests/hasb, --ha-setup and --ha-join done): no
# encryption of the daemons' own connections before the link between the
# databases is; after --ha-tls-repair both move over to verify-full with the
# cluster's authority, replication goes on, the link's TLS cannot be switched
# off under them; off again, then the link's TLS off too.
# Usage (root): python3 t_dbtls_ha.py VERSION
# (the rest as in t_dbtls.py:)
# Encryption to the database server (1.0.170) on a live PostgreSQL 16, the
# light HA sandbox's clusters (tests/hasb): A - node a alone, PostgreSQL on the
# same machine (kind local): its certificate, the connection moved over and
# back, a restart, the certificate renewed and made again for new names, the
# connection rescued when the server stops speaking TLS, switched off. B - node
# a and node b sharing node a's database (ha_mode shared): b reaches it at
# 10.99.0.1 (kind remote) with otp's authority, a wrong authority refused with
# nothing changed, off in the right order. RADIUS is asked all the time and
# must always answer.
# Usage (root): bash ../hasb/setup.sh /tmp/sbN; python3 t_dbtls.py VERSION
import os, sys, json, time, subprocess, threading, urllib.request

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.170'
V = '/home/claude/build/out/otp-%s' % VER
H = '/home/claude/work/hasb'
S = open(H + '/current').read().strip()
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % (more,)) if more and not cond else ''),
          flush=True)


def env(n):
    out = subprocess.run(['bash', '-c', '. %s/env.sh %s; env -0' % (H, n)], capture_output=True).stdout
    return dict(x.split('=', 1) for x in out.decode().split('\0') if '=' in x)


E = {n: env(n) for n in 'ab'}
CONF = {n: json.load(open('%s/%s/config.json' % (S, n))) for n in 'ab'}
PORT = {n: CONF[n]['api_port'] for n in 'ab'}
RPORT = {n: CONF[n]['radius_auth_port'] for n in 'ab'}
DB, PW = CONF['a']['db_name'], CONF['a']['db_password']


def psql(port, sql):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-XAtq', '-c', sql],
                          capture_output=True, text=True).stdout.strip()


def conf_put(n, **kw):
    c = json.load(open('%s/%s/config.json' % (S, n)))
    c.update(kw)
    json.dump(c, open('%s/%s/config.json' % (S, n), 'w'), indent=1)


def conf_get(n):
    return json.load(open('%s/%s/config.json' % (S, n)))


# ---- the database made, the first account, a RADIUS client -------------------
code = '''
import sys, os; sys.path.insert(0, %r); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
try:
    st.add_account('local', 'fulladmin', 'Local-Admin-Pass-170!', must_change=0)
except Exception: pass
try:
    st.client_save({'name': 'lo', 'address': '127.0.0.0/8', 'secret': 'radius-secret-170', 'enabled': 1})
except Exception: pass
''' % V
subprocess.run([sys.executable, '-c', code], env=E['a'], check=True)
for n in 'ab':
    os.makedirs('%s/%s/state/web' % (S, n), exist_ok=True)
helpers = subprocess.Popen(['bash', H + '/helpers.sh', VER], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


def start(n):
    subprocess.run(['bash', H + '/start.sh', n, VER])
    if n in RAD.get('was', ()):
        threading.Timer(8, lambda: RAD['on'].add(n)).start()


def stop(n):
    if n in RAD['on']:
        RAD['on'].discard(n)
        RAD.setdefault('was', set()).add(n)
    subprocess.run(['bash', '-c', 'for p in $(pgrep -f "otp.py --daemon"); do tr "\\0" "\\n" < /proc/$p/environ '
                    '2>/dev/null | grep -qx "OTP_CONFIG=%s/%s/config.json" && kill $p; done; sleep 2' % (S, n)])


TOK = {}
SESS = {}
RAD = {'asked': 0, 'lost': 0, 'on': set(), 'lost_at': []}


def up(n):
    for _ in range(60):
        time.sleep(1)
        try:
            TOK[n] = open('%s/%s/run/api-token' % (S, n)).read().strip()
            st, _ = call(n, '/api/health', sess=False)
            if st in (200, 401, 403):
                return True
        except Exception:                               # noqa: BLE001
            pass
    return False


def call(n, path, body=None, sess=True):
    h = {'X-Otp-Token': TOK.get(n, ''), 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess and SESS.get(n):
        h['X-Otp-Session'] = SESS[n]
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (PORT[n], path),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def login(n):
    st, got = call(n, '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-170!'}, sess=False)
    SESS[n] = got.get('token')
    return st == 200


def ask(n, body, of='apply', wait=150):
    """One phase asked of every node; every node's answer."""
    st, got = call(n, '/api/dbtls', dict(body, action='apply' if of == 'apply' else 'probe'))
    if st != 200:
        return st, got
    end = time.time() + wait
    while time.time() < end:
        time.sleep(1)
        _, res = call(n, '/api/dbtls', {'action': 'result', 'id': got['id'], 'of': of})
        nodes = {k: v for k, v in (res.get('nodes') or {}).items() if k in got['nodes']}
        if nodes and all(v for v in nodes.values()):
            return 200, nodes
    return 0, {'timeout': True}


# ---- RADIUS asked all the time ---------------------------------------------
sys.path.insert(0, V)
sys.argv = ['x']
os.environ.update(E['a'])
import otp  # noqa: E402



def radius_loop():
    while True:
        for n in list(RAD['on']):
            RAD['asked'] += 1
            try:
                otp.radius_ask('127.0.0.1', RPORT[n], 'radius-secret-170', 'nobody-%s' % n, 'x', timeout=3, tries=1)
            except Exception as e:                      # noqa: BLE001
                RAD['lost'] += 1
                RAD['lost_at'].append((n, time.strftime('%H:%M:%S'), str(e)[:80]))
        time.sleep(0.2)


threading.Thread(target=radius_loop, daemon=True).start()


def ssl_conns(port, user):
    return psql(port, "SELECT coalesce(s.ssl::text, '?'), count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s "
                "USING (pid) WHERE a.usename = '%s' GROUP BY 1 ORDER BY 1" % user)


def a_cert_file():
    return psql(5432, 'SHOW ssl_cert_file')


def view(n):
    return call(n, '/api/dbtls')[1]



def dbq(port, sql):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-d', DB, '-XAtq', '-c', sql],
                          capture_output=True, text=True).stdout.strip()


print('== C: two nodes replicating', flush=True)
start('a')
start('b')
ok('both up', up('a') and up('b') and login('a') and login('b'))
RAD['on'].update({'a', 'b'})
time.sleep(10)
v = view('a')
kinds = {x['name']: x.get('kind') for x in v['nodes']}
ok('kinds: both replicated', kinds == {'nodea': 'replicated', 'nodeb': 'replicated'}, kinds)
ok('the link between the databases not encrypted yet', v.get('link_done') is False, v)
st, got = ask('a', {'mode': 'verify-full'}, of='probe')
ok('probe: not before the link is encrypted', st == 200 and all(x.get('ok') is False for x in got.values()), got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('connect: refused on both, nothing changed', st == 200 and all(x.get('ok') is False for x in got.values())
   and not conf_get('a').get('db_tls') and not conf_get('b').get('db_tls'), got)
r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--ha-tls-repair'], env=E['a'], capture_output=True, text=True)
done = False
for _ in range(120):
    time.sleep(3)
    v = view('a')
    if v.get('link_done'):
        done = True
        break
ok('the link between the databases encrypted (High availability → Repair)', done, r.stdout[-400:] + r.stderr[-400:])
time.sleep(5)
st, got = ask('a', {'mode': 'verify-full'}, of='probe')
ok('probe: both go with the cluster\'s authority', st == 200 and all(x.get('ok') and x.get('ssl') for x in got.values()), got)
st, got = ask('a', {'phase': 'server', 'mode': 'verify-full'})
ok('server: nothing to do on either (the link gave them their certificates)', st == 200 and
   all(x.get('ok') and x.get('skip') for x in got.values()), got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('connect: both moved over', st == 200 and all(x.get('ok') and x.get('changed') for x in got.values()), got)
for n in 'ab':
    c = conf_get(n)
    ok('... %s: verify-full with its own copy of the cluster\'s authority' % n, c.get('db_tls') == 'verify-full' and
       c.get('db_tls_ca') == '%s/%s/ha-ca.pem' % (S, n), c)
time.sleep(4)
for port, n in ((5432, 'a'), (5433, 'b')):
    sc = psql(port, "SELECT s.ssl, count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) WHERE a.usename = '%s' "
              "AND a.client_addr = '127.0.0.1' GROUP BY 1" % DB)
    ok('... every connection of the daemon of %s to its own PostgreSQL is encrypted (%s)' % (n, sc), sc and 'f|' not in sc, sc)
mark = 'dbtls-ha-%d' % int(time.time())
dbq(5432, "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'nodea', 'info', 't', '%s')"
    % (time.time(), mark))
seen = False
for _ in range(30):
    time.sleep(1)
    if dbq(5433, "SELECT count(*) FROM events WHERE words = '%s'" % mark) == '1':
        seen = True
        break
ok('replication goes on: a row written on a is on b', seen)
st, got = call('a', '/api/ha', {'action': 'tls_off'})
ok('the link\'s TLS cannot be switched off under the daemons\' connections (%s)' % st, st >= 400 and
   'Encryption to the database server' in json.dumps(got), got)
v = view('a')
ok('the page: both encrypted and checked', all(x.get('ssl') and x.get('mode') == 'verify-full' for x in v['nodes']), v['nodes'])
stop('b')
start('b')
ok('b restarted with it on', up('b'))
time.sleep(6)
v = view('a')
ok('... still encrypted', [x for x in v['nodes'] if x['name'] == 'nodeb'][0].get('ssl'), v['nodes'])
st, got = ask('a', {'phase': 'connect', 'mode': ''})
ok('off: both back to no TLS', st == 200 and all(x.get('ok') for x in got.values()) and
   not conf_get('a').get('db_tls') and not conf_get('b').get('db_tls'), got)
st, got = ask('a', {'phase': 'server_off'})
ok('server_off: nothing of the wizard\'s to take away (the link\'s certificates stay)', st == 200 and
   all(x.get('skip') for x in got.values()) and psql(5432, 'SHOW ssl_cert_file').endswith('otp-ha.crt'), got)
time.sleep(6)
st, got = call('a', '/api/ha', {'action': 'tls_off'})
ok('now the link\'s TLS may be switched off (%s)' % st, st == 200, got)
mark2 = mark + '-2'
off = False
for _ in range(120):
    time.sleep(3)
    if not psql(5432, 'SHOW ssl_cert_file').endswith('otp-ha.crt') and not psql(5433, 'SHOW ssl_cert_file').endswith('otp-ha.crt'):
        off = True
        break
ok('... it went off on both', off)
time.sleep(5)
dbq(5433, "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'nodeb', 'info', 't', '%s')"
    % (time.time(), mark2))
seen = False
for _ in range(30):
    time.sleep(1)
    if dbq(5432, "SELECT count(*) FROM events WHERE words = '%s'" % mark2) == '1':
        seen = True
        break
ok('... and replication goes on: a row written on b is on a', seen)
ok('C: RADIUS on both nodes answered all the time', RAD['lost'] == 0, RAD['lost_at'][-5:])
print('RADIUS asked %d, lost %d' % (RAD['asked'], RAD['lost']))
stop('a')
stop('b')
helpers.terminate()
subprocess.run(['pkill', '-f', 'hasb/helpers.sh'])
print('ALL %d / %d' % (sum(R), len(R)))
