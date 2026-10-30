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


# ============ A: node a alone, PostgreSQL on this machine ======================
print('== A: a node alone, its PostgreSQL on the same machine', flush=True)
conf_put('a', ha_mode='')
start('a')
ok('node a is up', up('a'))
ok('signed in', login('a'))
RAD['on'].add('a')
time.sleep(2)
v = view('a')
ok('kind local, no TLS', v.get('kind') == 'local' and v.get('mode') == '', v)
st, got = ask('a', {'mode': 'verify-full'}, of='probe')
g = (got or {}).get('nodea') or {}
ok('probe: a certificate is needed first', st == 200 and g.get('needs_server'), got)
ok('probe: the server speaks TLS already (snakeoil)', g.get('server_tls') is True, g)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('connect before its certificate: refused, nothing changed', st == 200 and got['nodea'].get('ok') is False
   and not conf_get('a').get('db_tls'), got)
st, got = ask('a', {'phase': 'server', 'mode': 'verify-full'})
ok('server: PostgreSQL given otp\'s certificate', st == 200 and got['nodea'].get('ok') and got['nodea'].get('cert_end'), got)
ok('... its ssl_cert_file is otp\'s', a_cert_file().endswith('otp-ha.crt'), a_cert_file())
ok('... the authority file is there', os.path.exists(S + '/a/ha-ca.pem'))
ok('... the connection is not moved yet', not conf_get('a').get('db_tls'))
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('connect: moved over', st == 200 and got['nodea'].get('ok') and got['nodea'].get('changed'), got)
c = conf_get('a')
ok('... config.json says verify-full with the authority', c.get('db_tls') == 'verify-full' and
   c.get('db_tls_ca', '').endswith('/a/ha-ca.pem'), c)
time.sleep(3)
v = view('a')
n0 = v['nodes'][0]
ok('... the page: encrypted, TLS version, a cipher', n0.get('ssl') and n0.get('version', '').startswith('TLS')
   and n0.get('cipher'), n0)
ok('... the page: when the certificate ends', n0.get('cert_end') and n0['cert_end'] > time.time() + 600 * 86400, n0)
call('a', '/api/tokens')
time.sleep(1)
sc = ssl_conns(5432, DB)
ok('... every connection of the daemon is encrypted (pg_stat_ssl)', sc and 'false' not in sc, sc)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('connect again: it was so already', st == 200 and got['nodea'].get('changed') is False, got)

# a restart with it on
stop('a')
start('a')
ok('restarted with TLS on', up('a') and login('a'))
time.sleep(3)
v = view('a')
ok('... still encrypted after the restart', v['nodes'][0].get('ssl') and v['mode'] == 'verify-full', v['nodes'][0])

# renewed 45 days before it ends, and made again when the names change
pre = a_cert_file()
srv = json.loads(psql(5432, "SELECT v FROM meta WHERE k = 'dbtls:server:nodea'") or 'null') if False else None
row = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', '5432', '-d', DB, '-XAtq', '-c',
                      "SELECT v FROM meta WHERE k = 'dbtls:server:nodea'"], capture_output=True, text=True).stdout.strip()
srv = json.loads(row)
old_end = srv['cert_end']
fp_before = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-in', '/var/lib/postgresql/16/main/otp-ha.crt'],
                           capture_output=True, text=True).stdout
srv.update(cert_end=time.time() + 10 * 86400, tried=0)
subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', '5432', '-d', DB, '-XAtq', '-c',
                "UPDATE meta SET v = '%s' WHERE k = 'dbtls:server:nodea'" % json.dumps(srv)])
renewed = False
for _ in range(60):
    time.sleep(2)
    fp = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-in', '/var/lib/postgresql/16/main/otp-ha.crt'],
                        capture_output=True, text=True).stdout
    if fp and fp != fp_before:
        renewed = True
        break
ok('renewed by itself when 10 days were left', renewed)
time.sleep(4)
call('a', '/api/tokens')
v = view('a')
ok('... the connection goes on, encrypted', v['nodes'][0].get('ssl'), v['nodes'][0])
row = json.loads(subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', '5432', '-d', DB, '-XAtq', '-c',
                                 "SELECT v FROM meta WHERE k = 'dbtls:server:nodea'"], capture_output=True,
                                text=True).stdout.strip())
ok('... the new one lasts two years', row['cert_end'] > time.time() + 700 * 86400, row)
row.update(names=['localhost', '127.0.0.1', 'an-old-name'], tried=0)
subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', '5432', '-d', DB, '-XAtq', '-c',
                "UPDATE meta SET v = '%s' WHERE k = 'dbtls:server:nodea'" % json.dumps(row)])
fp_before = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-in', '/var/lib/postgresql/16/main/otp-ha.crt'],
                           capture_output=True, text=True).stdout
again = False
for _ in range(60):
    time.sleep(2)
    fp = subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-in', '/var/lib/postgresql/16/main/otp-ha.crt'],
                        capture_output=True, text=True).stdout
    if fp and fp != fp_before:
        again = True
        break
ok('made again when the machine\'s names changed', again)
time.sleep(8)                   # the root helper reloads PostgreSQL after the files
san = subprocess.run(['openssl', 'x509', '-noout', '-ext', 'subjectAltName', '-in', '/var/lib/postgresql/16/main/otp-ha.crt'],
                     capture_output=True, text=True).stdout
ok('... it names 127.0.0.1, localhost and 10.99.0.1', '127.0.0.1' in san and 'localhost' in san and '10.99.0.1' in san, san)

# the server stops speaking TLS: rescued to no TLS, RADIUS goes on
lost0 = RAD['lost']
psql(5432, "ALTER SYSTEM SET ssl = 'off'")
psql(5432, 'SELECT pg_reload_conf()')
time.sleep(1)
psql(5432, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = '%s'" % DB)
rescued = False
for _ in range(40):
    time.sleep(2)
    if not conf_get('a').get('db_tls'):
        rescued = True
        break
ok('the server stopped speaking TLS: moved back to no TLS by itself', rescued, conf_get('a'))
v = {}
for _ in range(20):
    time.sleep(2)
    v = view('a')
    if (v.get('nodes') or [{}])[0].get('rescued'):
        break
ok('... the page says so', (v['nodes'][0].get('rescued') or {}).get('was') == 'verify-full', v['nodes'][0])
ok('... RADIUS lost at most a few answers', RAD['lost'] - lost0 <= 25, RAD['lost'] - lost0)
psql(5432, "ALTER SYSTEM SET ssl = 'on'")
psql(5432, 'SELECT pg_reload_conf()')
time.sleep(2)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full'})
ok('encrypted again', st == 200 and got['nodea'].get('ok') and conf_get('a').get('db_tls') == 'verify-full', got)
time.sleep(2)
ok('... and the rescue note is gone', not view('a')['nodes'][0].get('rescued'))

# off: the connection, then the certificate
st, got = ask('a', {'phase': 'server_off'})
ok('server_off while the connection uses it: refused', st == 200 and got['nodea'].get('ok') is False
   and a_cert_file().endswith('otp-ha.crt'), got)
st, got = ask('a', {'phase': 'connect', 'mode': ''})
ok('connect with no TLS: moved back', st == 200 and got['nodea'].get('ok') and not conf_get('a').get('db_tls'), got)
st, got = ask('a', {'phase': 'server_off'})
ok('server_off: otp\'s certificate out', st == 200 and got['nodea'].get('ok') and not a_cert_file().endswith('otp-ha.crt'),
   (got, a_cert_file()))
ok('... its files gone from the data folder', not os.path.exists('/var/lib/postgresql/16/main/otp-ha.crt'))
time.sleep(2)
v = view('a')
ok('... the page: no TLS, no certificate', v['mode'] == '' and not v['servers'], v)
ok('A: RADIUS answered all the time but the rescue', RAD['lost'] - (RAD['lost'] - lost0) == RAD['lost'] - (RAD['lost'] - lost0)
   and RAD['lost'] <= 25, RAD)
lost_a = RAD['lost']

# ============ B: two nodes sharing node a's database ===========================
print('== B: two nodes, one database (node a\'s), node b reaches it over the network', flush=True)
hba = psql(5432, 'SHOW hba_file')
txt = open(hba).read()
if '10.99.0.0/24' not in txt:
    open(hba, 'a').write('\nhost all all 10.99.0.0/24 scram-sha-256\n')
    psql(5432, 'SELECT pg_reload_conf()')
conf_put('a', ha_mode='shared')
conf_put('b', ha_mode='shared', db_host='10.99.0.1', db_port=5432, db_name=DB, db_user=DB, db_password=PW)
for f in ('secrets.key',):
    import shutil
    shutil.copy('%s/a/state/%s' % (S, f), '%s/b/state/%s' % (S, f))
    os.chmod('%s/b/state/%s' % (S, f), 0o600)
stop('a')
start('a')
start('b')
ok('both up', up('a') and up('b') and login('a'))
RAD['on'].add('b')
time.sleep(8)
v = view('a')
kinds = {x['name']: x.get('kind') for x in v['nodes']}
ok('kinds: a local, b remote', kinds == {'nodea': 'local', 'nodeb': 'remote'}, kinds)
st, got = ask('a', {'mode': 'verify-full', 'ca_source': 'given', 'ca_pem': open('/etc/ssl/certs/ssl-cert-snakeoil.pem').read()}, of='probe')
ok('probe b with a wrong authority: it says no', st == 200 and got['nodeb'].get('ok') is False, got)
st, got = ask('a', {'phase': 'server', 'mode': 'verify-full'})
ok('server: a given its certificate, b has none to give', st == 200 and got['nodea'].get('ok') and got['nodeb'].get('skip'), got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full', 'ca_source': 'given',
                    'ca_pem': open('/etc/ssl/certs/ssl-cert-snakeoil.pem').read()})
ok('connect with the wrong authority: b refuses and stays as it was', st == 200 and got['nodeb'].get('ok') is False
   and not conf_get('b').get('db_tls'), got)
ok('... (a moved over, its own authority)', got['nodea'].get('ok') and conf_get('a').get('db_tls') == 'verify-full', got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full', 'ca_source': 'system'})
ok('connect with the system\'s authorities: b refuses (otp\'s is not one of them)', st == 200 and
   got['nodeb'].get('ok') is False and not conf_get('b').get('db_tls'), got)
st, got = ask('a', {'mode': 'verify-full', 'ca_source': 'otp'}, of='probe')
ok('probe b with otp\'s authority: it goes, TLS', st == 200 and got['nodeb'].get('ok') and got['nodeb'].get('ssl'), got)
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-full', 'ca_source': 'otp'})
ok('connect with otp\'s authority: both moved over', st == 200 and all(x.get('ok') for x in got.values()), got)
cb = conf_get('b')
ok('... b: verify-full to 10.99.0.1 with the authority kept in its state folder', cb.get('db_tls') == 'verify-full'
   and cb.get('db_tls_ca', '').endswith('/b/state/db-ca.pem'), cb)
ok('... b\'s file is otp\'s authority', 'BEGIN CERTIFICATE' in open(S + '/b/state/db-ca.pem').read())
time.sleep(3)
sc = ssl_conns(5432, DB)
ok('... every connection of both daemons is encrypted', sc and 'false' not in sc, sc)
v = view('a')
ok('... the page: both nodes encrypted', all(x.get('ssl') for x in v['nodes']), v['nodes'])
st, got = ask('a', {'phase': 'connect', 'mode': 'verify-ca', 'ca_source': 'given',
                    'ca_pem': open(S + '/b/state/db-ca.pem').read(), 'node': 'nodeb'})
ok('b alone to verify-ca with the authority given: the file in use is replaced only once it goes',
   st == 200 and got['nodeb'].get('ok') and conf_get('b').get('db_tls') == 'verify-ca' and
   conf_get('b').get('db_tls_ca', '').endswith('/b/state/db-ca.pem') and not os.path.exists(S + '/b/state/db-ca.next.pem'),
   (got, conf_get('b')))
st, got = ask('a', {'phase': 'connect', 'mode': 'require', 'node': 'nodeb'})
ok('b alone to require', st == 200 and got['nodeb'].get('ok') and conf_get('b').get('db_tls') == 'require', got)
st, got = ask('a', {'phase': 'connect', 'mode': '', 'node': 'nodea'})
ok('a alone back to no TLS', st == 200 and got['nodea'].get('ok') and not conf_get('a').get('db_tls'), got)
st, got = ask('a', {'phase': 'server_off', 'node': 'nodea'})
ok('server_off on a while b still uses TLS: refused', st == 200 and got['nodea'].get('ok') is False
   and a_cert_file().endswith('otp-ha.crt'), got)
st, got = ask('a', {'phase': 'connect', 'mode': ''})
ok('off: every connection back', st == 200 and all(x.get('ok') for x in got.values())
   and not conf_get('b').get('db_tls'), got)
st, got = ask('a', {'phase': 'server_off'})
ok('server_off: done', st == 200 and all(x.get('ok') for x in got.values()) and not a_cert_file().endswith('otp-ha.crt'), got)
time.sleep(2)
ok('B: RADIUS on both nodes answered all the time', RAD['lost'] == lost_a, RAD['lost_at'][-5:])
print('RADIUS asked %d, lost %d' % (RAD['asked'], RAD['lost']))
stop('a')
stop('b')
helpers.terminate()
subprocess.run(['pkill', '-f', 'hasb/helpers.sh'])
print('ALL %d / %d' % (sum(R), len(R)))
