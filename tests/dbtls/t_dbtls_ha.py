# C: two nodes replicating (tests/hasb, --ha-setup and --ha-join done): the
# daemons' own connections encrypted and the link between the databases
# encrypted each on and off by itself, in every order (1.0.172) - the
# certificate of each PostgreSQL kept while either uses it, renewed by whichever
# has it, taken away when neither does; replication and RADIUS all the time.
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



S_A, S_B = '/var/lib/postgresql/16/main', '/var/lib/postgresql/16/second'


def certfile(port):
    return psql(port, 'SHOW ssl_cert_file')


def fp(datadir):
    return subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-in', datadir + '/otp-ha.crt'],
                          capture_output=True, text=True).stdout


def replicates(src_port, dst_port, tag):
    mark = 'dbtls-ha-%s-%d' % (tag, int(time.time() * 1000))
    dbq(src_port, "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'x', 'info', 't', '%s')"
        % (time.time(), mark))
    for _ in range(40):
        time.sleep(1)
        if dbq(dst_port, "SELECT count(*) FROM events WHERE words = '%s'" % mark) == '1':
            return True
    return False


def both_ways(tag):
    return replicates(5432, 5433, tag + 'ab') and replicates(5433, 5432, tag + 'ba')


def local_ssl(port):
    sc = psql(port, "SELECT s.ssl, count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) WHERE a.usename = '%s' "
              "AND a.client_addr = '127.0.0.1' GROUP BY 1" % DB)
    return sc


def link_tls(on):
    if on:
        r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--ha-tls-repair'], env=E['a'], capture_output=True, text=True)
        for _ in range(120):
            time.sleep(3)
            if view('a').get('link_done'):
                return True
        print(r.stdout[-300:], r.stderr[-300:])
        return False
    st, got = call('a', '/api/ha', {'action': 'tls_off'})
    if st != 200:
        print('tls_off', st, got)
        return False
    for _ in range(120):
        time.sleep(3)
        ha = call('a', '/api/ha')[1].get('link_tls') or {}
        if ha.get('nodes') and all(x.get('step') == 'off_done' for x in ha['nodes']):
            return True
    return False


def db_on():
    st, got = ask('a', {'phase': 'server', 'mode': 'verify-full'})
    if st != 200 or not all(x.get('ok') for x in got.values()):
        return False, got
    st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
    return st == 200 and all(x.get('ok') for x in got.values()), got


def db_off():
    st, got = ask('a', {'phase': 'connect', 'mode': ''})
    if st != 200 or not all(x.get('ok') for x in got.values()):
        return False, got
    st, got2 = ask('a', {'phase': 'server_off'})
    return st == 200 and all(x.get('ok') for x in got2.values()), got2


def enc_both():
    return all(conf_get(n).get('db_tls') == 'verify-full' for n in 'ab') and \
        all('f|' not in local_ssl(p) and local_ssl(p) for p in (5432, 5433))


print('== C: two nodes replicating - the daemons\' connections and the link, each by itself', flush=True)
start('a')
start('b')
ok('both up', up('a') and up('b') and login('a') and login('b'))
RAD['on'].update({'a', 'b'})
time.sleep(10)
v = view('a')
ok('start: the link not encrypted, the connections not either', not v.get('link_done') and not v.get('mode'), v)
ok('... replication goes both ways', both_ways('c0'))

# C1 - the connections encrypted while the link is not
st, got = ask('a', {'mode': 'verify-full'}, of='probe')
ok('C1 probe: a certificate first on both (no Repair needed)', st == 200 and all(x.get('needs_server') for x in got.values()), got)
good, got = db_on()
ok('C1 the connections encrypted without the link\'s TLS', good and enc_both(), got)
ok('... each PostgreSQL has otp\'s certificate', certfile(5432).endswith('otp-ha.crt') and certfile(5433).endswith('otp-ha.crt'))
ok('... the link is not moved with them (ha_tls empty, no verify)', not conf_get('a').get('ha_tls') and not conf_get('b').get('ha_tls'))
ok('... replication goes both ways', both_ways('c1'))

# C2 - renewed by the database side while the link is off
before = fp(S_A)
row = json.loads(dbq(5432, "SELECT v FROM meta WHERE k = 'dbtls:server:nodea'"))
row.update(cert_end=time.time() + 5 * 86400, tried=0)
dbq(5432, "UPDATE meta SET v = '%s' WHERE k = 'dbtls:server:nodea'" % json.dumps(row))
renewed = False
for _ in range(60):
    time.sleep(2)
    if fp(S_A) and fp(S_A) != before:
        renewed = True
        break
time.sleep(8)
ok('C2 renewed by itself with the link off', renewed)
ok('... the connections still encrypted, replication goes on', enc_both() and both_ways('c2'))

# C3 - the link encrypted while the connections are
ok('C3 the link encrypted (Repair) while the connections are', link_tls(True))
time.sleep(6)
ok('... the connections still encrypted', enc_both())
ok('... the link verify-full on both', conf_get('a').get('ha_tls') == 'verify-full' and conf_get('b').get('ha_tls') == 'verify-full')
ok('... replication goes both ways', both_ways('c3'))
v = view('a')
ok('... the page: the link\'s certificate', all(x.get('server_by') == 'link' for x in v['nodes'] if x.get('me')), v['nodes'])

# C4 - the connections off while the link is on: the certificate stays
good, got = db_off()
ok('C4 the connections back to no TLS', good and not conf_get('a').get('db_tls') and not conf_get('b').get('db_tls'), got)
ok('... the certificates stay - the link uses them', certfile(5432).endswith('otp-ha.crt') and certfile(5433).endswith('otp-ha.crt'))
ok('... the link still verify-full, replication goes both ways', conf_get('a').get('ha_tls') == 'verify-full' and both_ways('c4'))

# C5 - the connections on again while the link is on: its certificate used
st, got = ask('a', {'phase': 'server', 'mode': 'verify-full'})
ok('C5 server: nothing to do, the link\'s certificate is there', st == 200 and all(x.get('skip') for x in got.values()), got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('... connected over it', st == 200 and all(x.get('ok') for x in got.values()) and enc_both(), got)

# C6 - the link off while the connections are on: the certificate stays
ok('C6 the link\'s TLS switched off with the connections on', link_tls(False))
time.sleep(6)
ok('... the certificates stay where the connections use them', certfile(5432).endswith('otp-ha.crt') and certfile(5433).endswith('otp-ha.crt'))
ok('... the connections still encrypted', enc_both())
ok('... the link no longer verify-full, replication goes both ways', not conf_get('a').get('ha_tls') and both_ways('c6'))
ok('... the database side renews them from now on', all(dbq(p, "SELECT count(*) FROM meta WHERE k = 'dbtls:server:%s'" % n) == '1'
                                                       for p, n in ((5432, 'nodea'), (5432, 'nodeb'))))

# C7 - the connections off with the link off: the certificates go
good, got = db_off()
ok('C7 the connections off with the link off', good, got)
time.sleep(3)
ok('... the certificates gone from both PostgreSQLs', not certfile(5432).endswith('otp-ha.crt') and not certfile(5433).endswith('otp-ha.crt'))
ok('... replication goes both ways', both_ways('c7'))

# C8 - the other order: the link first, then the connections, then the link off, then them
ok('C8 the link encrypted first', link_tls(True))
good, got = db_on()
ok('... then the connections', good and enc_both(), got)
ok('... the link off', link_tls(False) and enc_both() and both_ways('c8'))
good, got = db_off()
ok('... the connections off, the certificates gone, replication goes on', good and not certfile(5432).endswith('otp-ha.crt')
   and both_ways('c8b'), got)
ok('C: RADIUS on both nodes answered all the time', RAD['lost'] == 0, RAD['lost_at'][-5:])
print('RADIUS asked %d, lost %d' % (RAD['asked'], RAD['lost']))
stop('a')
stop('b')
helpers.terminate()
subprocess.run(['pkill', '-f', 'hasb/helpers.sh'])
print('ALL %d / %d' % (sum(R), len(R)))
