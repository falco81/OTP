# t_ha_tls.py VERSION - certificates running out on a cluster of two, renewed by themselves:
# the link between the databases encrypted (verify-full) and the daemons' own connections to
# their databases encrypted (verify-full, with the link's certificate); then node a's
# certificate near its end, node b's, and the cluster's authority within two years of its end.
# Each time: a new certificate in PostgreSQL, one that ends years from now, replication both
# ways, the daemons' connections still encrypted - and RADIUS (each node and the VIP address)
# answered all the time, a code let in right after each.
# Usage (root, after t_ha_auth.py on the same sandbox): python3 t_ha_tls.py VERSION
import os, sys, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

DATA = {'a': '/var/lib/postgresql/16/main', 'b': '/var/lib/postgresql/16/second'}
PGP = {'a': 5432, 'b': 5433}
helpers_on()
for n in 'ab':
    stop(n)                      # this version's code
    start(n)
    login(n)
ka_on()
T = json.loads(in_node('a', 'tk = otp.Tokens(st); print(json.dumps(tk.enroll("tlsuser", "test")))').strip().split('\n')[-1])
time.sleep(3)


def certfile(n):
    return psql(PGP[n], 'SHOW ssl_cert_file')


def cert(n, what):
    f = certfile(n)
    if not f:
        return ''
    return subprocess.run(['openssl', 'x509', '-noout'] + what.split() + ['-in', f if f.startswith('/') else DATA[n] + '/' + f],
                          capture_output=True, text=True).stdout.strip()


def end_days(n):
    e = cert(n, '-enddate').split('=', 1)[-1]
    if not e:
        return -1
    t = time.mktime(time.strptime(e.replace(' GMT', ''), '%b %d %H:%M:%S %Y'))
    return (t - time.time()) / 86400


def replicates(src, dst, tag):
    mark = 'hatls-%s-%d' % (tag, int(time.time() * 1000))
    dbq(src, "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'x', 'info', 't', '%s')"
        % (time.time(), mark))
    for _ in range(40):
        time.sleep(1)
        if dbq(dst, "SELECT count(*) FROM events WHERE words = '%s'" % mark) == '1':
            return True
    return False


def both_ways(tag):
    return replicates('a', 'b', tag + 'ab') and replicates('b', 'a', tag + 'ba')


def conns_encrypted(n):
    """The daemon's own connections to its database: every one with TLS."""
    got = psql(PGP[n], "SELECT s.ssl, count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) "
               "WHERE a.usename = '%s' AND a.backend_type = 'client backend' AND a.client_addr IS NOT NULL "
               "GROUP BY 1" % CONF[n]['db_name'])
    return got, ('t|' in got and 'f|' not in got)


def link_view():
    return call('a', '/api/ha')[1].get('link_tls') or {}


def fresh():
    s0 = int(time.time()) // 30
    while int(time.time()) // 30 == s0:
        time.sleep(0.5)


def code_in(what):
    fresh()
    for tgt in ('a', 'b'):
        r = rad(tgt, 'tlsuser', totp_of(T['secret']))[0]
        ok('%s: a code on %s: in (%s)' % (what, tgt, r), r == 'accept')
        fresh()


P = Prober()


def settled():
    """No authority near its end left from a run before, both nodes done with it."""
    cas = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:ca'") or '{"cas": []}')['cas']
    w = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:want'") or '{}')
    sts = [json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:node:%s'" % NAME[n]) or '{}') for n in 'ab']
    return cas and float(cas[0]['end']) - time.time() > 730 * 86400 and \
        all(x.get('step') == 'done' and x.get('for') == w.get('at') for x in sts)


# Once a day the authority may be replaced: today's taken by a run before this one, forgotten.
dbq('a', "DELETE FROM meta WHERE k = 'hatls:roll'")
for _ in range(200):
    if settled():
        break
    time.sleep(3)
ok('nothing left from a run before (the authority years from its end, both nodes done)', settled())

# ---- the link encrypted ------------------------------------------------------------------
if not all(json.load(open('%s/%s/config.json' % (S, n))).get('ha_tls') == 'verify-full' for n in 'ab'):
    r = subprocess.run([sys.executable, '-I', V + '/otp.py', '--ha-tls-repair'], env=E['a'], capture_output=True, text=True)
    for _ in range(100):
        time.sleep(3)
        if (call('a', '/api/dbtls')[1] or {}).get('link_done'):
            break
ok('the link between the databases encrypted (verify-full on both)',
   all(json.load(open('%s/%s/config.json' % (S, n))).get('ha_tls') == 'verify-full' for n in 'ab'))
ok('... replication both ways', both_ways('link'))

# ---- the daemons' own connections encrypted -----------------------------------------------


def dbtls(body, of='apply', wait=180):
    st_, got = call('a', '/api/dbtls', dict(body, action='apply' if of == 'apply' else 'probe'))
    if st_ != 200:
        return st_, got
    end = time.time() + wait
    while time.time() < end:
        time.sleep(1)
        _, res = call('a', '/api/dbtls', {'action': 'result', 'id': got['id'], 'of': of})
        nodes = {k: v for k, v in (res.get('nodes') or {}).items() if k in got['nodes']}
        if nodes and all(v for v in nodes.values()):
            return 200, nodes
    return 0, {'timeout': True}


if not all(json.load(open('%s/%s/config.json' % (S, n))).get('db_tls') == 'verify-full' for n in 'ab'):
    s1, g1 = dbtls({'phase': 'server', 'mode': 'verify-full'})
    s2, g2 = dbtls({'phase': 'connect', 'mode': 'verify-full'})
    ok('the daemons\' connections encrypted (%s %s)' % (s1, s2), s1 == 200 and s2 == 200, (g1, g2))
for n in 'ab':
    login(n)
time.sleep(5)
for n in 'ab':
    got, good = conns_encrypted(n)
    ok('%s: every connection of its daemon encrypted (%s)' % (n, got.replace('\n', ' ')), good)
code_in('both encrypted')

# ---- a node's certificate near its end -----------------------------------------------------
for n in 'ab':
    before = cert(n, '-fingerprint')
    days0 = end_days(n)
    t0 = time.time()
    key = 'hatls:node:' + NAME[n]
    row = json.loads(dbq(n, "SELECT v FROM meta WHERE k = '%s'" % key) or '{}')
    ok('%s: its state says its certificate ends in %.0f days' % (n, (float(row.get('cert_end') or 0) - time.time()) / 86400),
       row.get('cert_end'))
    row['cert_end'] = time.time() + 10 * 86400
    dbq(n, "UPDATE meta SET v = '%s' WHERE k = '%s'" % (json.dumps(row).replace("'", "''"), key))
    renewed = False
    for _ in range(120):
        time.sleep(2)
        if cert(n, '-fingerprint') and cert(n, '-fingerprint') != before:
            renewed = True
            break
    ok('%s: ten days left - a new certificate in its PostgreSQL within %.0f s' % (n, time.time() - t0), renewed)
    ok('%s: ... it ends in %.0f days (was %.0f)' % (n, end_days(n), days0), end_days(n) > 300)
    time.sleep(8)
    ok('%s: ... replication both ways' % n, both_ways('renew' + n))
    for m in 'ab':
        got, good = conns_encrypted(m)
        ok('%s: ... the daemon of %s still on TLS (%s)' % (n, m, got.replace('\n', ' ')), good)
    code_in('%s renewed' % n)

# ---- the authority within two years of its end ------------------------------------------
dbq('a', "DELETE FROM meta WHERE k = 'hatls:roll'")       # today's taken by the settling above
t0 = time.time()
ca0 = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:ca'"))
ca0['cas'][0]['end'] = time.time() + 300 * 86400
dbq('a', "UPDATE meta SET v = '%s' WHERE k = 'hatls:ca'" % json.dumps(ca0).replace("'", "''"))
# Only the authority near its end - both nodes' certificates years from theirs: it was
# looked at only when the certificate of the node that may make a new one ended soon.
before = {n: cert(n, '-ext authorityKeyIdentifier') for n in 'ab'}
rolled = False
for _ in range(180):
    time.sleep(2)
    cas = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:ca'") or '{"cas": []}')['cas']
    if cas and float(cas[0].get('at') or 0) >= t0 - 5 and all(cert(n, '-ext authorityKeyIdentifier') != before[n] for n in 'ab'):
        rolled = True
        break
ok('the authority within two years of its end: a new one, both nodes\' certificates from it (%.0f s)' % (time.time() - t0),
   rolled, (len(cas), [cert(n, '-ext authorityKeyIdentifier') for n in 'ab']))
time.sleep(10)
ok('... replication both ways', both_ways('roll'))
for m in 'ab':
    got, good = conns_encrypted(m)
    ok('... the daemon of %s still on TLS (%s)' % (m, got.replace('\n', ' ')), good)
code_in('the authority replaced')
P.stop_flag = True
time.sleep(1)
for t in ('a', 'b', 'vip'):
    ok('the prober: %s answered every time (%d asked, %d not)' % (t, P.asked[t], len(P.lost[t])), not P.lost[t])
done()
