# t_ha_dbguard.py VERSION - root's actions only from rows otp signed (1.0.231) on the two-node sandbox, the guard
# on on both: rows written straight into PostgreSQL (as anybody who can write the database would) - a sign-in, a
# VIP address, a node's heartbeat, a key for root - are not acted on by either node; what is changed on the pages
# of one node is acted on by both; replication runs on. Switched on and off by the pages of each node.
# Usage (root): python3 t_ha_dbguard.py VERSION [keep]     keep: leave the guard on (for the other HA tests)
import os, sys, time, json, secrets, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402
KEEP = 'keep' in sys.argv[2:]
helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)


def guard_set(on):
    for n in 'ab':
        c, x = call(n, '/api/settings', {'settings': {'db_guard': 1 if on else 0}})
        ok('the guard %s on node %s: %s %s' % ('on' if on else 'off', n, c, str(x.get('message') or x.get('error'))[:120]), c == 200)


guard_set(True)
for n in 'ab':
    ok('node %s: db_guard in its config.json' % n, json.load(open('%s/%s/config.json' % (S, n))).get('db_guard') == 1)
    login(n)

# a sign-in written straight into node b's database
tok = secrets.token_urlsafe(32); t = time.time()
dbq('b', "INSERT INTO sessions (token_hash, kind, name, role, created, last, expires, ip, data) VALUES ('%s', 'admin', 'local', 'fulladmin', %f, %f, %f, '127.0.0.1', '{}')"
    % (hashlib.sha256(tok.encode()).hexdigest(), t, t, t + 3600))
keep_s = SESS['b']; SESS['b'] = tok
c, x = call('b', '/api/status')
SESS['b'] = keep_s
ok('a sign-in written straight into node b\'s database: refused (%s)' % c, c == 401)

# the VIP: what the nodes would hand keepalived, before and after a row written straight
vip_of = lambda n: json.loads(in_node(n, "print(json.dumps(otp.web_desired(st).get('vip')))").strip().split('\n')[-1])
before = {n: vip_of(n) for n in 'ab'}
raw = dbq('a', "SELECT v FROM meta WHERE k = 'web:vip'")
evil = json.dumps(dict(json.loads(raw or '{}'), on=True, address='10.99.0.250/24'))
dbq('a', "UPDATE meta SET v = '%s' WHERE k = 'web:vip'" % evil.replace("'", "''"))
time.sleep(6)
after = {n: vip_of(n) for n in 'ab'}
ok('a VIP address written straight into the database: neither node takes it (%s)' % after['a'].get('address'),
   all((after[n] or {}).get('address') != '10.99.0.250/24' for n in 'ab'))
dbq('a', "UPDATE meta SET v = '%s' WHERE k = 'web:vip'" % (raw or '{}').replace("'", "''"))

# a node's heartbeat written straight: not let through the firewall
dbq('a', "INSERT INTO meta (k, v) VALUES ('node:evil', '%s') ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v"
    % json.dumps({'at': time.time(), 'address': '203.0.113.77', 'version': '1.0.231'}))
time.sleep(5)
for n in 'ab':
    got = in_node(n, "print(sorted(otp.cluster_addresses(st, otp.node_name())))")
    ok('node %s: a heartbeat written straight is not let through the firewall' % n, '203.0.113.77' not in got, got)
dbq('a', "DELETE FROM meta WHERE k = 'node:evil'")

# a key for root, asked by a row written straight
dbq('a', "INSERT INTO meta (k, v) VALUES ('host:sshkeys:want:nodeb@@nodex', '%s')"
    % json.dumps([{'id': 'evil01', 'do': 'add', 'line': 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEvilEvilEvilEvilEvilEvilEvilEvilEvilEvilEv evil', 'fp': '', 'last_ok': False, 'at': time.time()}]))
time.sleep(25)
got = in_node('b', "print(json.dumps(otp.node_key_rows(st, 'host:sshkeys:want', 'nodeb')))")
ok('a key for root asked by a row written straight: not seen by node b', 'evil01' not in got, got[:200])
dbq('a', "DELETE FROM meta WHERE k = 'host:sshkeys:want:nodeb@@nodex'")

# what is changed on the pages of one node is taken by both
c, x = call('a', '/api/settings', {'settings': {'logs_keep': 13}})
ok('a setting that reaches root changed on node a\'s pages: %s' % c, c == 200)
time.sleep(8)
for n in 'ab':
    v = in_node(n, "otp.load_config(saved=otp.dbguard_settings(st.settings_saved(), st)); print(otp.CONFIG.get('logs_keep'))").strip().split('\n')[-1]
    ok('...taken on node %s (%s)' % (n, v), v == '13', v)
call('a', '/api/settings', {'settings': {'logs_keep': 14}})
for n in 'ab':
    c, x = call(n, '/api/hisec')
    g = (x or {}).get('guard') or {}
    ok('node %s: the guard on, what it refused listed (%d)' % (n, len(g.get('refused') or [])), g.get('on'))
ok('RADIUS on both nodes with the guard on', all(rad(n, 'nobody', '000000')[0] in ('reject', 'timeout') for n in 'ab'))
ok('replication still runs both ways', 'running' in in_node('a', "import subprocess; print(subprocess.run([sys.executable, otp.__file__, '--ha-status'], capture_output=True, text=True).stdout)"))
if not KEEP:
    guard_set(False)
done()
