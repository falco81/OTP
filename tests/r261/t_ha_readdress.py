#!/usr/bin/python3
"""t_ha_readdress.py VERSION [--stack ipv4|dual] [--link on|off] [--db on|off] [--which a|b|both] [--all]

A node of a cluster of two re-addressed through the pages' API (1.0.261): PostgreSQL 16
replicated both ways, the VIP address by keepalived, each case on a fresh full sandbox
(tests/hasb, newsb.sh). As a person does it:

  * the link between the databases encrypted or not (High availability → the link's TLS:
    POST /api/ha tls_link) and the node's own connection to its database encrypted or not
    (Settings → The database → Encryption: POST /api/dbtls phases server, connect);
  * Settings → Network of the node, on the pages of the OTHER node (the node changed restarts):
    Read it again, Check it, Change it and restart - the want as the page builds it - the
    restart simulated as the machine's (the old address leaves lo, the new one comes, keepalived
    and otp start again), then Keep it on the banner (POST /api/trial) once it waits on trial;
  * node a, then node b, or both (a, then b), IPv4 alone or dual stack (the profile with an IPv6
    address beside, the VIP address with an IPv6 one beside).

Meanwhile a prober asks RADIUS all the time on the VIP address (and each node). Afterwards:
both nodes answer, replication both ways (a write on each seen on the other), the link's TLS and
the database's TLS as set (the certificates naming the new addresses), pg_hba.conf and the
subscriptions at the new addresses, ha_peer/ha_address, keepalived's file, the VIP address served
and a code let in through it, RADIUS through the VIP address unanswered for a short while at
most, no maintenance left on, no bad event, no alert left, nothing new in To be done by hand,
the job's steps all good.

  --extra (1.0.262) the extra cases instead of the change, one sandbox: see EXTRA below.
  --all   the 24 cases, each in a process of its own on a fresh sandbox: one line a case, then
          ALL n / m (cases passed). Logs: /tmp/claude-0/f261/logs/.
The kernel of the test machine may have no IPv6 at all: the dual-stack cases then check what the
product writes for IPv6 (NetworkManager, /etc/hosts, the certificates, keepalived) - not IPv6
packets.
"""
import os, sys, json, time, subprocess, re, argparse, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
H = '/home/claude/work/hasb'
LOGS = '/tmp/claude-0/f261/logs'
STOP = '/tmp/claude-0/f261/sbstop.sh'

ap = argparse.ArgumentParser()
ap.add_argument('version')
ap.add_argument('--stack', default='ipv4', choices=('ipv4', 'dual'))
ap.add_argument('--link', default='on', choices=('on', 'off'))
ap.add_argument('--db', default='off', choices=('on', 'off'))
ap.add_argument('--which', default='a', choices=('a', 'b', 'both'))
ap.add_argument('--all', action='store_true')
ap.add_argument('--only', default='', help='with --all: a regex the case name must match')
ap.add_argument('--keep-sandbox', action='store_true', help='leave the daemons running at the end')
ap.add_argument('--extra', action='store_true',
                help='1.0.262 round 3: instead of the change, the extra cases on one sandbox (a gateway '
                     'kept, a trial let go back, refused while the other is in maintenance / allowed '
                     'while its daemon is stopped, both asked at once); not in --all')
A = ap.parse_args()
VER = A.version


def case_name(stack, link, db, which):
    return '%s link=%s db=%s which=%s' % (stack, link, db, which)


def stop_all():
    subprocess.run(['bash', STOP], capture_output=True)


# ---- the whole matrix ----------------------------------------------------------------------
if A.all:
    os.makedirs(LOGS, exist_ok=True)
    cases = list(itertools.product(('ipv4', 'dual'), ('on', 'off'), ('on', 'off'), ('a', 'b', 'both')))
    passed, n_run = 0, 0
    for stack, link, db, which in cases:
        name = case_name(stack, link, db, which)
        if A.only and not re.search(A.only, name):
            continue
        n_run += 1
        log = '%s/%s-%s-%s-%s-%s.log' % (LOGS, time.strftime('%m%d%H%M'), stack, link, db, which)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), VER, '--stack', stack,
                                '--link', link, '--db', db, '--which', which],
                               stdout=open(log, 'w'), stderr=subprocess.STDOUT, timeout=3600)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
        text = open(log).read()
        m = re.findall(r'^ALL (\d+) / (\d+)', text, re.M)
        fails = [l[5:] for l in text.splitlines() if l.startswith('FAIL ')]
        good = bool(m) and m[-1][0] == m[-1][1] and rc == 0
        passed += good
        print('%-4s %-34s %s %4.0f min  %s%s' % ('ok' if good else 'FAIL', name,
                                                 ('%s / %s' % m[-1]) if m else 'no result (%s)' % rc,
                                                 (time.time() - t0) / 60, log,
                                                 ('\n       ' + '\n       '.join(f[:200] for f in fails[:8])) if fails else ''),
              flush=True)
        stop_all()
    print('ALL %d / %d' % (passed, n_run), flush=True)
    sys.exit(0 if passed == n_run else 1)

# ---- one case: a fresh sandbox first (halib reads it when imported) -------------------------
NAME_CASE = case_name(A.stack, A.link, A.db, A.which)
print('CASE', NAME_CASE, flush=True)
stop_all()
DUAL = A.stack == 'dual'
IP4 = {'a': '10.99.0.1', 'b': '10.99.0.2'}
NEW4 = {'a': '10.99.0.3', 'b': '10.99.0.4'}
IP6 = {'a': 'fd99::1', 'b': 'fd99::2'}
NEW6 = {'a': 'fd99::3', 'b': 'fd99::4'}
VIP6 = 'fd99::200/64'
HAS6 = os.path.exists('/proc/net/if_inet6')


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


# lo as the machines have it: each node's addresses alone; the new ones come with the restart.
# Secondaries promoted, so that the first address of 10.99.0.0/24 leaving takes no other with it.
for f in ('/proc/sys/net/ipv4/conf/lo/promote_secondaries', '/proc/sys/net/ipv4/conf/all/promote_secondaries'):
    try:
        open(f, 'w').write('1')
    except OSError:
        pass
for a in ('10.99.0.1', '10.99.0.2'):
    sh('ip addr add %s/24 dev lo' % a)
for a in ('10.99.0.3', '10.99.0.4', '10.99.0.11', '10.99.0.12'):
    sh('ip addr del %s/24 dev lo' % a)
SB = '/tmp/sbr%s' % time.strftime('%m%d%H%M%S')
env = dict(os.environ, OTP_SB_STACK=A.stack)
r = subprocess.run(['bash', H + '/newsb.sh', SB, VER], capture_output=True, text=True, env=env)
print(r.stdout.strip()[-300:], r.stderr.strip()[-300:], flush=True)
if r.returncode:
    print('FAIL the sandbox could not be made')
    print('ALL 0 / 1')
    sys.exit(1)
sys.argv = ['x', VER]
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
import halib  # noqa: E402
from halib import ok, call, login, start, stop, up, rad, totp_of, dbq, psql, in_node, vip_master, vip_role, \
    helpers_on, ka_on, ka_stop, Prober, running, done, S, CONF, NAME, SECRET, ADMIN_PW, VIP, E  # noqa: E402
assert S == SB, (S, SB)
OTHER = {'a': 'b', 'b': 'a'}
PGP = {'a': 5432, 'b': 5433}
CLUSTER = {'a': 'main', 'b': 'second'}
DB = CONF['a']['db_name']
T0 = time.time()


def prof_path(n):
    return '%s/%s/fakenm/profiles/System eth0.nmconnection' % (S, n)


def prof(n):
    out = {}
    for line in open(prof_path(n)):
        if '=' in line and not line.startswith('['):
            k, v = line.rstrip('\n').split('=', 1)
            out[k] = v
    return out


def lo_v4():
    return set(re.findall(r'inet (10\.99\.0\.\d+)/', sh('ip -4 addr show dev lo').stdout))


def machine_addresses(n):
    """The node's addresses on lo as its NetworkManager profile says (what a start gives it)."""
    p = prof(n)
    want = [x.strip() for x in p.get('ipv4.addresses', '').split(',') if x.strip()]
    others = set()
    for m in 'ab':
        if m != n:
            others |= set(x.split('/')[0] for x in prof(m).get('ipv4.addresses', '').split(',') if x.strip())
    have = lo_v4()
    mine_before = MINE.get(n, set())
    for a in mine_before - set(x.split('/')[0] for x in want):
        if a not in others:
            sh('ip addr del %s/24 dev lo' % a)
    for x in want:
        if x.split('/')[0] not in have:
            sh('ip addr add %s dev lo' % x)
    MINE[n] = set(x.split('/')[0] for x in want)
    if HAS6:
        for x in [y.strip() for y in p.get('ipv6.addresses', '').split(',') if y.strip()]:
            sh('ip -6 addr add %s dev lo' % x)


MINE = {}
for n in 'ab':
    machine_addresses(n)
print('lo:', sorted(lo_v4()), 'IPv6 in the kernel:', HAS6, flush=True)

# ---- set up once on node a: an administrator, RADIUS clients, a token --------------------
SETUP = '''
try:
    st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
except Exception: pass
for c in ({'name': 'lo', 'address': '127.0.0.0/8', 'secret': %(sec)r, 'enabled': 1},
          {'name': 'sandbox', 'address': '10.99.0.0/24', 'secret': %(sec)r, 'enabled': 1}):
    if not [x for x in st.clients() if x['name'] == c['name']]:
        st.client_save(c)
have = {r['name'] for r in st.realms()}
if 'local' not in have:
    st.realm_save({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'})
tk = otp.Tokens(st)
print(json.dumps(tk.enroll('rduser', 'test'), default=str))
''' % {'pw': ADMIN_PW, 'sec': SECRET}
T = json.loads(in_node('a', SETUP).strip().split('\n')[-1])
helpers_on()
for n in 'ab':
    start(n)
    ok('%s: up and signed in' % n, login(n))
st_, got = call('a', '/api/settings', {'settings': {'net_confirm_min': 2}})
ok('a new network goes back unless kept within 2 min (%s)' % st_, st_ == 200, got)
body = {'action': 'vip_save', 'address': VIP + '/24', 'vrid': 61}
if DUAL:
    body['address6'] = VIP6
st_, got = call('a', '/api/web', body)
ok('the VIP address kept%s (%s)' % (' with ' + VIP6 if DUAL else '', st_), st_ == 200, got)
st_, got = call('a', '/api/web', {'action': 'vip_on'})
ok('... on (%s)' % st_, st_ == 200, got)
# Each node's own web certificate, self-signed on the pages (Settings → TLS): its address in it -
# made again for the new one by the change.
for n in 'ab':
    names = '%s, %s%s' % (IP4[n], NAME[n], (', ' + IP6[n]) if DUAL else '')
    st_, got = call(n, '/api/web', {'action': 'tls_selfsigned', 'target': NAME[n], 'cn': NAME[n],
                                    'names': names, 'kind': 'rsa2048'})
    ok('%s: its own web certificate made on the pages for %s (%s)' % (n, names, st_), st_ == 200, got)
ka_on()
for _ in range(90):
    if vip_master() and VIP in lo_v4() | set(sh('ip addr show lo').stdout.split()):
        break
    time.sleep(1)
ok('keepalived: one MASTER (%s), the address up' % vip_master(), vip_master())


def hatls_rows():
    return {n: json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'hatls:node:%s'" % NAME[n]) or '{}') for n in 'ab'}


def cfg(n):
    return json.load(open('%s/%s/config.json' % (S, n)))


def link_done():
    rows = hatls_rows()
    return all(rows[n].get('step') == 'done' for n in 'ab') and \
        all(cfg(n).get('ha_tls') == 'verify-full' for n in 'ab')


def dbtls(body, wait=240):
    st_, got = call('a', '/api/dbtls', dict(body, action='apply'))
    if st_ != 200:
        return st_, got
    end = time.time() + wait
    while time.time() < end:
        time.sleep(1)
        _, res = call('a', '/api/dbtls', {'action': 'result', 'id': got['id'], 'of': 'apply'})
        nodes = {k: v for k, v in (res.get('nodes') or {}).items() if k in got['nodes']}
        if nodes and all(v for v in nodes.values()):
            bad = {k: v for k, v in nodes.items() if not (isinstance(v, dict) and v.get('ok'))}
            return (200 if not bad else 409), nodes
    return 0, {'timeout': True}


# ---- the TLS as set on the pages ---------------------------------------------------------
if A.link == 'on':
    st_, got = call('a', '/api/ha', {'action': 'tls_link'})
    ok('the link\'s TLS asked on the pages (%s)' % st_, st_ == 200, got)
    for _ in range(150):
        if link_done():
            break
        time.sleep(2)
    ok('... done on both nodes, verify-full', link_done(), hatls_rows())
else:
    ok('the link\'s TLS off on both (ha_tls %r %r)' % (cfg('a').get('ha_tls'), cfg('b').get('ha_tls')),
       not cfg('a').get('ha_tls') and not cfg('b').get('ha_tls'))
if A.db == 'on':
    s1, g1 = dbtls({'phase': 'server', 'mode': 'verify-full'})
    s2, g2 = dbtls({'phase': 'connect', 'mode': 'verify-full'})
    ok('the daemons\' connections to their databases encrypted on the pages (%s %s)' % (s1, s2),
       s1 == 200 and s2 == 200, (g1, g2))
    for n in 'ab':
        login(n)


def conns_encrypted(n):
    """The node's own daemon's connections (127.0.0.1) - not the other node's, which come over
    the link."""
    got = psql(PGP[n], "SELECT s.ssl, count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) "
               "WHERE a.usename = '%s' AND a.backend_type = 'client backend' AND a.client_addr = '127.0.0.1' "
               "GROUP BY 1" % CONF[n]['db_name'])
    return got.replace('\n', ' '), ('t|' in got and 'f|' not in got)


def replicates(src, dst, tag, wait=60):
    mark = 'rdr-%s-%d' % (tag, int(time.time() * 1000))
    dbq(src, "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'x', 'info', 't', '%s')"
        % (time.time(), mark))
    for _ in range(wait):
        time.sleep(1)
        if dbq(dst, "SELECT count(*) FROM events WHERE words = '%s'" % mark) == '1':
            return True
    return False


ok('before: replication a -> b', replicates('a', 'b', 'pre-ab'))
ok('before: replication b -> a', replicates('b', 'a', 'pre-ba'))
for n in 'ab':
    got, enc = conns_encrypted(n)
    # Off, the daemon's connection is libpq's default (sslmode prefer): encrypted unchecked
    # where its PostgreSQL speaks TLS (the link's certificate), in clear otherwise.
    ok('before: %s: its daemon\'s connections %s (%s; db_tls %r)' % (
        n, 'encrypted, checked' if A.db == 'on' else 'not set to TLS', got, cfg(n).get('db_tls')),
        (enc and cfg(n).get('db_tls') == 'verify-full') if A.db == 'on' else not cfg(n).get('db_tls'))


def after_ids():
    _, v = call('a', '/api/after')
    return set('%s@%s' % (x.get('id'), x.get('node')) for x in (v.get('items') or []))


def alert_keys():
    _, v = call('a', '/api/alerts')
    return {p.get('key'): p for p in (v.get('problems') or [])}


AFTER0 = after_ids()
ALERTS0 = alert_keys()
print('before: to be done by hand %s; alerts %s' % (sorted(AFTER0), sorted(ALERTS0)), flush=True)
EV0 = int(time.time()) - 1

# ---- the re-addressing, as a person presses it ------------------------------------------
P = Prober(every=0.3)
time.sleep(2)
TSTART = time.time()
STEPS_BAD = []


def norm_ip(x):
    import ipaddress
    try:
        return str(ipaddress.ip_address(x))
    except ValueError:
        return x


def page_want(data, n):
    """What the network page of node n sends, filled as the page fills it, the addresses changed."""
    conf = data.get('conf') or {}
    live = data.get('live') or {}
    on6 = conf.get('ipv6_method') not in (None, '', 'disabled', 'ignore')
    want = {'con': data.get('con'), 'hostname': (data.get('hostname') or '').strip(),
            'shared_db_ok': False,
            'ipv4': {'addr': NEW4[n] + '/24', 'gw': conf.get('ipv4_gateway') or live.get('gw4') or '',
                     'dns': ', '.join(x for x in (conf.get('ipv4_dns') or live.get('dns') or []) if ':' not in x),
                     'search': ', '.join(conf.get('ipv4_search') or [])},
            'ipv6': {'on': on6, 'mode': 'auto' if conf.get('ipv6_method') == 'auto' else 'manual',
                     'addr': (NEW6[n] + '/64') if on6 else ((conf.get('ipv6_addresses') or [''])[0]),
                     'gw': conf.get('ipv6_gateway') or '', 'dns': ', '.join(conf.get('ipv6_dns') or [])},
            'vip_elsewhere': False}
    return want


def net_node(via, n):
    _, v = call(via, '/api/net')
    for x in v.get('nodes') or []:
        if x.get('name') == NAME[n]:
            return x
    return {}


def reboot(n):
    """The machine restarts: otp and keepalived go, the addresses of its profile come."""
    print(time.strftime('%H:%M:%S'), '** restart of', NAME[n], '(simulated)', flush=True)
    P.expect_down.add(n)
    halib.KA_OFF.add(n)
    ka_stop(n)
    stop(n)
    machine_addresses(n)
    time.sleep(4)
    halib.start(n, reboot=True)
    halib.KA_OFF.discard(n)
    login(n)
    P.expect_down.discard(n)


def readdress(n):
    via = OTHER[n]
    old4 = IP4[n] if n not in DONE else NEW4[n]
    t_read = time.time()
    st_, got = call(via, '/api/net', {'action': 'read', 'node': NAME[n]})
    now = {}
    for _ in range(60):
        now = net_node(via, n).get('now') or {}
        if float(now.get('at') or 0) > t_read:
            break
        time.sleep(1)
    ok('%s: Read it again on the pages of %s - its network said (%s)' % (n, via, st_),
       float(now.get('at') or 0) > t_read, now)
    data = now.get('data') or {}
    want = page_want(data, n)
    st_, plan = call(via, '/api/net', {'action': 'plan', 'node': NAME[n], 'want': want})
    ok('%s: Check it: the plan (%s)' % (n, st_), st_ == 200, plan)
    for p in (plan.get('plan') or []):
        print('      plan:', p, flush=True)
    st_, got = call(via, '/api/net', {'action': 'apply', 'node': NAME[n], 'want': want})
    ok('%s: Change it and restart (%s)' % (n, st_), st_ == 200, got)
    if st_ != 200:
        return False
    jid = got.get('id')
    power = '%s/%s/power' % (S, n)
    seen = len(open(power).read().splitlines())
    last, kept, t0 = None, False, time.time()
    job = {}
    while time.time() - t0 < 1500:
        lines = open(power).read().splitlines()
        if len(lines) > seen:
            seen = len(lines)
            time.sleep(8)               # reboot_in 8
            reboot(n)
        j = (net_node(via, n).get('job') or {})
        if not j:
            j = json.loads(dbq(via, "SELECT v FROM meta WHERE k = 'net:job:%s'" % NAME[n]) or '{}')
        if j.get('id') != jid:
            time.sleep(2)
            continue
        job = j
        cur = (j.get('state'), (j.get('steps') or [{}])[-1].get('what', '')[:160])
        if cur != last:
            print(time.strftime('%H:%M:%S'), NAME[n], *cur, flush=True)
            last = cur
        if j.get('state') == 'trial' and not kept:
            st_, kg = call(via, '/api/trial', {'kind': 'net', 'node': NAME[n], 'action': 'keep'})
            ok('%s: Keep it on the banner of %s (%s)' % (n, via, st_), st_ == 200, kg)
            kept = True
        if j.get('state') in ('done', 'failed', 'going back'):
            break
        time.sleep(2)
    ok('%s: the change kept and done (%s)' % (n, job.get('state')),
       job.get('state') == 'done' and job.get('kept'), (job.get('error'), job.get('state')))
    for s_ in job.get('steps') or []:
        print('   %s %s' % ('ok ' if s_.get('ok') else 'BAD', s_.get('what', '')[:300]), flush=True)
        if not s_.get('ok'):
            STEPS_BAD.append('%s: %s' % (n, s_.get('what', '')[:200]))
    DONE.add(n)
    return job.get('state') == 'done'


# ---- EXTRA (1.0.262, --extra): the cases the round-3 review found ---------------------------
#  (a) a gateway alone changed on trial, then Keep on node a: b's pg_hba.conf still lets a in,
#      and a's subscription takes b's rows again after ALTER SUBSCRIPTION ... DISABLE; ENABLE;
#  (b) a new address on trial let go back (no Keep): the old address everywhere - the profile,
#      a's ha_address, b's ha_peer, b's pg_hba.conf - the going back done, no maintenance;
#  (c) refused while b is in maintenance; asked once b's daemon is stopped (b not heard from);
#  (d) both: b asked while a is restarting / on trial - refused; asked once a is done.
def ex_job(via, n):
    try:
        j = (net_node(via, n).get('job') or {})
    except Exception:                                   # noqa: BLE001
        j = {}
    try:
        return j or json.loads(dbq(via, "SELECT v FROM meta WHERE k = 'net:job:%s'" % NAME[n]) or '{}')
    except Exception:                                   # noqa: BLE001
        return {}


def ex_ask(via, n, want):
    st_, got = call(via, '/api/net', {'action': 'apply', 'node': NAME[n], 'want': want})
    return st_, got


def ex_read(via, n):
    t_read = time.time()
    call(via, '/api/net', {'action': 'read', 'node': NAME[n]})
    for _ in range(60):
        now = net_node(via, n).get('now') or {}
        if float(now.get('at') or 0) > t_read:
            return now.get('data') or {}
        time.sleep(1)
    return {}


def ex_follow(via, n, jid, keep, power_seen, until=('done', 'failed'), during=None, secs=1500):
    """The job jid of node n followed (restarts done as the machine's); Keep pressed on trial
    when keep. A going back: the job asked by the node itself followed after it. -> its last row."""
    power = '%s/%s/power' % (S, n)
    seen, t0, last, kept, back_id, job = power_seen, time.time(), None, False, None, {}
    while time.time() - t0 < secs:
        lines = open(power).read().splitlines()
        if len(lines) > seen:
            seen = len(lines)
            time.sleep(8)
            reboot(n)
        j = ex_job(via, n)
        if during:
            during(j)
        if j.get('id') not in (jid, back_id):
            if back_id is None and job.get('state') in ('trial', 'going back') and j.get('rollback'):
                back_id = j.get('id')
            else:
                time.sleep(2)
                continue
        job = j
        cur = (j.get('state'), (j.get('steps') or [{}])[-1].get('what', '')[:160])
        if cur != last:
            print(time.strftime('%H:%M:%S'), NAME[n], *cur, flush=True)
            last = cur
        if j.get('state') == 'trial' and keep and not kept:
            st_, kg = call(via, '/api/trial', {'kind': 'net', 'node': NAME[n], 'action': 'keep'})
            ok('%s: Keep it (%s)' % (n, st_), st_ == 200, kg)
            kept = True
        if j.get('state') in until and (keep or j.get('id') == back_id or j.get('state') == 'failed'):
            break
        time.sleep(2)
    return job, seen


def ex_power_seen(n):
    return len(open('%s/%s/power' % (S, n)).read().splitlines())


def ex_hba_has(n, addr):
    return any(a == addr + '/32' for _k, a in hba_lines(n))


def ex_maint(n):
    m = dbq('a', "SELECT v FROM meta WHERE k = 'maint:%s'" % NAME[n])
    return bool(json.loads(m or '{}').get('on'))


if A.extra:
    def wait_for(fn, secs, every=3):
        end = time.time() + secs
        while True:
            try:
                v = fn()
            except Exception:                           # noqa: BLE001
                v = None
            if v or time.time() >= end:
                return v
            time.sleep(every)

    def hba_lines(n):
        out = []
        for l in open('/etc/postgresql/16/%s/pg_hba.conf' % CLUSTER[n]).read().splitlines():
            f = l.split()
            if len(f) >= 5 and f[0] in ('host', 'hostssl') and f[1] == DB:
                out.append((f[0], f[3]))
        return out

    # (a) the gateway alone, kept
    data = ex_read('b', 'a')
    want = page_want(data, 'a')
    want['ipv4']['addr'] = IP4['a'] + '/24'
    if DUAL:
        want['ipv6']['addr'] = IP6['a'] + '/64'
    want['ipv4']['gw'] = '10.99.0.254' if want['ipv4']['gw'] != '10.99.0.254' else '10.99.0.253'
    seen = ex_power_seen('a')
    st_, got = ex_ask('b', 'a', want)
    ok('(a) a: the gateway alone changed, asked on the pages of b (%s)' % st_, st_ == 200, got)
    job, _ = ex_follow('b', 'a', got.get('id'), True, seen)
    ok('(a) a: kept and done (%s)' % job.get('state'), job.get('state') == 'done' and job.get('kept'),
       job.get('error'))
    time.sleep(15)                      # readdress_dropold_tick on b, were it asked
    ok('(a) b: pg_hba.conf still lets a in at %s' % IP4['a'], ex_hba_has('b', IP4['a']), hba_lines('b'))
    sub = psql(PGP['a'], 'SELECT subname FROM pg_subscription', DB).strip().split('\n')[0]
    psql(PGP['a'], 'ALTER SUBSCRIPTION %s DISABLE' % sub, DB)
    time.sleep(2)
    psql(PGP['a'], 'ALTER SUBSCRIPTION %s ENABLE' % sub, DB)
    ok('(a) after DISABLE; ENABLE of %s on a: replication b -> a' % sub, replicates('b', 'a', 'ex-a-ba', 120))
    ok('(a) ... and a -> b', replicates('a', 'b', 'ex-a-ab', 120))

    # (c) refused while b is in maintenance; asked once b's daemon is stopped
    st_, got = call('a', '/api/upgrade', {'action': 'maintenance', 'node': NAME['b'], 'on': True,
                                          'why': 'test'})
    ok('(c) b in maintenance (%s)' % st_, st_ == 200, got)
    data = ex_read('a', 'a')
    want = page_want(data, 'a')
    want['ipv4']['addr'] = IP4['a'] + '/24'
    if DUAL:
        want['ipv6']['addr'] = IP6['a'] + '/64'
    want['ipv4']['gw'] = '10.99.0.253' if want['ipv4']['gw'] != '10.99.0.253' else '10.99.0.252'
    st_, got = ex_ask('a', 'a', want)
    ok('(c) a: a new network refused while b is in maintenance (%s)' % st_,
       st_ != 200 and 'does not answer now' in json.dumps(got), got)
    st_, got = call('a', '/api/upgrade', {'action': 'maintenance', 'node': NAME['b'], 'on': False})
    ok('(c) b out of maintenance (%s)' % st_, st_ == 200, got)
    stop('b')
    time.sleep(60)                      # b's heartbeat old (3 x 15 s)
    seen = ex_power_seen('a')
    st_, got = ex_ask('a', 'a', want)
    ok('(c) a: asked while b\'s daemon is stopped - a dead partner does not block (%s)' % st_,
       st_ == 200, got)
    if st_ == 200:
        job, _ = ex_follow('a', 'a', got.get('id'), True, seen)
        ok('(c) a: kept and done (%s)' % job.get('state'), job.get('state') == 'done', job.get('error'))
    start('b')
    login('b')
    ok('(c) b back', up('b') and login('b'))

    # (b) a new address on trial, let go back
    data = ex_read('b', 'a')
    want = page_want(data, 'a')
    seen = ex_power_seen('a')
    st_, got = ex_ask('b', 'a', want)
    ok('(b) a: a new address asked, not to be kept (%s)' % st_, st_ == 200, got)
    job, _ = ex_follow('b', 'a', got.get('id'), False, seen, secs=2400)
    ok('(b) a: went back, the going back done (%s, rollback %s)' % (job.get('state'), job.get('rollback')),
       job.get('state') == 'done' and job.get('rollback'), job.get('error'))
    ok('(b) a: its profile at %s again (%s)' % (IP4['a'], prof('a').get('ipv4.addresses')),
       prof('a').get('ipv4.addresses', '').split(',')[0].split('/')[0] == IP4['a'])
    ok('(b) a: ha_address %s (%s)' % (IP4['a'], cfg('a').get('ha_address')),
       cfg('a').get('ha_address') in (IP4['a'], '', None))
    good = wait_for(lambda: cfg('b').get('ha_peer') == IP4['a'] and ex_hba_has('b', IP4['a']), 180)
    ok('(b) b: ha_peer and pg_hba.conf at %s (%s, %s)' % (IP4['a'], cfg('b').get('ha_peer'), hba_lines('b')),
       good)
    ok('(b) no maintenance left on', wait_for(lambda: not ex_maint('a') and not ex_maint('b'), 120))
    ok('(b) replication a -> b', replicates('a', 'b', 'ex-b-ab', 120))
    ok('(b) replication b -> a', replicates('b', 'a', 'ex-b-ba', 120))

    # (d) both at once: b refused while a restarts or waits to be kept
    data = ex_read('b', 'a')
    want = page_want(data, 'a')
    dw = page_want(ex_read('a', 'b'), 'b')
    seen = ex_power_seen('a')
    st_, got = ex_ask('b', 'a', want)
    ok('(d) a: a new address asked (%s)' % st_, st_ == 200, got)
    TRIED = {'n': 0, 'bad': []}

    def ask_b_meanwhile(j):
        if j.get('state') in ('rebooting', 'trial') and TRIED['n'] < 3 and up('b', 1):
            s2, g2 = ex_ask('b', 'b', dw)
            TRIED['n'] += 1
            print('   (d) b asked while a is %s: %s %s' % (j.get('state'), s2, str(g2)[:160]), flush=True)
            if s2 == 200:
                TRIED['bad'].append((j.get('state'), g2))
    job, _ = ex_follow('b', 'a', got.get('id'), True, seen, during=ask_b_meanwhile)
    ok('(d) b refused while a was restarting / on trial (%d asked)' % TRIED['n'],
       TRIED['n'] > 0 and not TRIED['bad'], TRIED['bad'])
    ok('(d) a: kept and done (%s)' % job.get('state'), job.get('state') == 'done', job.get('error'))
    seen = ex_power_seen('b')
    st_, got = ex_ask('a', 'b', page_want(ex_read('a', 'b'), 'b'))
    ok('(d) b: asked once a is done (%s)' % st_, st_ == 200, got)
    if st_ == 200:
        job, _ = ex_follow('a', 'b', got.get('id'), True, seen)
        ok('(d) b: kept and done (%s)' % job.get('state'), job.get('state') == 'done', job.get('error'))
    ok('(d) replication a -> b', replicates('a', 'b', 'ex-d-ab', 180))
    ok('(d) replication b -> a', replicates('b', 'a', 'ex-d-ba', 180))
    if not A.keep_sandbox:
        stop_all()
        for a in ('10.99.0.1', '10.99.0.2', '10.99.0.3'):
            sh('ip addr add %s/24 dev lo' % a)
        for a in ('10.99.0.4', '10.99.0.11', '10.99.0.12'):
            sh('ip addr del %s/24 dev lo' % a)
    done()
    sys.exit(0 if all(halib.R) else 1)


DONE = set()
order = ['a', 'b'] if A.which == 'both' else [A.which]
for n in order:
    readdress(n)
    if A.which == 'both' and n == 'a':
        time.sleep(10)
TEND = time.time()
ADDR = {n: (NEW4[n] if n in DONE else IP4[n]) for n in 'ab'}
OLD = {n: IP4[n] for n in DONE}

# ---- afterwards: settled within a few minutes ---------------------------------------------
ok('no job step that went wrong%s' % ((': ' + ' | '.join(STEPS_BAD)) if STEPS_BAD else ''), not STEPS_BAD)


def wait_for(fn, secs, every=3):
    end = time.time() + secs
    while True:
        try:
            v = fn()
        except Exception:                               # noqa: BLE001
            v = None
        if v or time.time() >= end:
            return v
        time.sleep(every)


for n in 'ab':
    ok('%s: answers and signs in' % n, up(n) and login(n))
ok('replication a -> b', replicates('a', 'b', 'post-ab', 120))
ok('replication b -> a', replicates('b', 'a', 'post-ba', 120))


def subinfo(n):
    return psql(PGP[n], "SELECT subconninfo FROM pg_subscription", DB)


def sub_running(n):
    return psql(PGP[n], "SELECT count(*) FROM pg_stat_subscription WHERE pid IS NOT NULL", DB) not in ('', '0')


for n in 'ab':
    c = cfg(n)
    ok('%s: config.json ha_address = %s (%s)' % (n, ADDR[n], c.get('ha_address')), c.get('ha_address') == ADDR[n])
    ok('%s: config.json ha_peer = %s (%s)' % (n, ADDR[OTHER[n]], c.get('ha_peer')), c.get('ha_peer') == ADDR[OTHER[n]])
    si = subinfo(n)
    host = (re.search(r"host='?([^' ]+)", si) or [None, ''])[1]
    ok('%s: its subscription takes the rows from %s (%s)' % (n, ADDR[OTHER[n]], host), host == ADDR[OTHER[n]])
    ok('%s: ... running' % n, wait_for(lambda: sub_running(n), 60))
    sslm = (re.search(r"sslmode='?([^' ]+)", si) or [None, ''])[1]
    if A.link == 'on':
        ok('%s: ... over TLS, checked (sslmode %s)' % (n, sslm), sslm == 'verify-full')
    else:
        ok('%s: ... in clear as set (sslmode %r)' % (n, sslm), sslm in ('', 'prefer', 'disable'))


def hba_lines(n):
    """otp's lines for the database in node n's pg_hba.conf: (kind, address)."""
    out = []
    for l in open('/etc/postgresql/16/%s/pg_hba.conf' % CLUSTER[n]).read().splitlines():
        f = l.split()
        if len(f) >= 5 and f[0] in ('host', 'hostssl') and f[1] == DB:
            out.append((f[0], f[3]))
    return out


def hba_ok(n):
    lines = hba_lines(n)
    peer = ADDR[OTHER[n]] + '/32'
    mine = [k for k, a in lines if a == peer]
    old = [a for k, a in lines if OTHER[n] in OLD and a == OLD[OTHER[n]] + '/32']
    want_kind = 'hostssl' if A.link == 'on' else 'host'
    return bool(mine) and all(k == want_kind for k in mine) and not old, (lines, mine, old)


for n in 'ab':
    good = wait_for(lambda: hba_ok(n)[0], 90)
    ok('%s: pg_hba.conf lets %s in (%s) and no longer the old address' % (
        n, ADDR[OTHER[n]], 'hostssl' if A.link == 'on' else 'host'), good, hba_ok(n)[1])

CERTS = '''
out = {}
try:
    end, sans = otp.hatls_own_cert(st)
    out['end_days'] = (end - time.time()) / 86400
    out['sans'] = [list(x) for x in sans]
except Exception as e:
    out['err'] = str(e)
out['hatls_ok'] = list(otp.net_hatls_ok(st))
out['dbtls_server'] = otp._meta_json(st, 'dbtls:server:' + otp.node_name()) or {}
out['web_tls'] = (otp.tls_profile(st, otp.node_name()) or {}).get('info') or {}
print(json.dumps(out, default=str))
'''


def certs(n):
    return json.loads(in_node(n, CERTS).strip().split('\n')[-1])


def cert_names(n, c=None):
    c = c or certs(n)
    ips = set(v for k, v in c.get('sans') or [] if k == 'IP Address')
    dns = set(v for k, v in c.get('sans') or [] if k == 'DNS')
    return ips, dns


for n in 'ab':
    if A.link == 'on':
        good = wait_for(lambda: certs(n)['hatls_ok'][0], 300, 5)
        c = certs(n)
        ok('%s: the link encrypted and checked: %s' % (n, c['hatls_ok'][1][:200]), good, c['hatls_ok'])
        ips, dns = cert_names(n, c)
        ok('%s: its PostgreSQL\'s certificate names %s (as an address and a name)' % (n, ADDR[n]),
           ADDR[n] in ips and ADDR[n] in dns, (sorted(ips), sorted(dns)))
        ok('%s: ... ends in %.0f days' % (n, c.get('end_days') or 0), (c.get('end_days') or 0) > 300)
        ok('%s: config.json ha_tls verify-full' % n, cfg(n).get('ha_tls') == 'verify-full')
    else:
        ok('%s: the link\'s TLS still off (ha_tls %r)' % (n, cfg(n).get('ha_tls')), not cfg(n).get('ha_tls'))
    if A.db == 'on':
        ok('%s: config.json db_tls verify-full (%s)' % (n, cfg(n).get('db_tls')), cfg(n).get('db_tls') == 'verify-full')
        got, enc = conns_encrypted(n)
        ok('%s: every connection of its daemon encrypted (%s)' % (n, got), enc)
        c = certs(n)
        if A.link == 'off':
            # Its PostgreSQL's certificate is the one Settings → The database gave it: made again
            # for the new address.
            good = wait_for(lambda: ADDR[n] in (certs(n)['dbtls_server'].get('names') or []), 420, 10)
            c = certs(n)
            ips, dns = cert_names(n, c)
            ok('%s: its PostgreSQL\'s certificate (the database\'s) names %s' % (n, ADDR[n]),
               good and ADDR[n] in ips, (c['dbtls_server'].get('names'), sorted(ips)))
    else:
        ok('%s: its daemon\'s connections in clear as set (db_tls %r)' % (n, cfg(n).get('db_tls')), not cfg(n).get('db_tls'))
    if DUAL:
        ok('%s: the IPv6 address in its profile (%s)' % (n, prof(n).get('ipv6.addresses')),
           (NEW6[n] if n in DONE else IP6[n]) in prof(n).get('ipv6.addresses', ''))
    ok('%s: the IPv4 address in its profile (%s)' % (n, prof(n).get('ipv4.addresses')),
       prof(n).get('ipv4.addresses', '').split(',')[0].split('/')[0] == ADDR[n])
    if n in DONE:
        hosts = open('%s/%s/hosts' % (S, n)).read()
        ok('%s: /etc/hosts names the new address%s and not the old' % (n, ' and the IPv6 one' if DUAL else ''),
           ADDR[n] in hosts and IP4[n] not in hosts and (not DUAL or NEW6[n] in hosts), hosts)
    w = certs(n)['web_tls']
    if w:
        names = [str(x) for x in (w.get('san') or [])]
        names = names + [norm_ip(x) for x in names]      # openssl writes FD99:0:0:0:0:0:0:3
        ok('%s: its own web certificate names %s%s' % (n, ADDR[n], ' and ' + NEW6[n] if DUAL and n in DONE else ''),
           ADDR[n] in names and (not DUAL or n not in DONE or NEW6[n] in names) and
           (n not in DONE or (IP4[n] not in names and (not DUAL or IP6[n] not in names))), names)


def ka_text(n):
    try:
        return open('%s/%s/keepalived.conf' % (S, n)).read()
    except OSError:
        return ''


for n in 'ab':
    good = wait_for(lambda: 'unicast_src_ip %s' % ADDR[n] in ka_text(n) and
                    re.search(r'unicast_peer \{\s*%s\s' % re.escape(ADDR[OTHER[n]]), ka_text(n)), 120)
    ok('%s: keepalived from %s to %s' % (n, ADDR[n], ADDR[OTHER[n]]), good,
       re.findall(r'unicast_src_ip \S+|unicast_peer \{\s*\S+', ka_text(n)))
    if DUAL:
        ok('%s: keepalived carries the IPv6 VIP address' % n, VIP6 in ka_text(n))
ok('the VIP address served (%s)' % vip_master(), wait_for(vip_master, 60))
time.sleep(3)
fresh = int(time.time()) // 30
while int(time.time()) // 30 == fresh:
    time.sleep(0.5)
r_ = rad('vip', 'rduser', totp_of(T['secret']))[0]
ok('a code let in through the VIP address (%s)' % r_, r_ == 'accept')
for n in 'ab':
    r_ = rad(n, 'probe-nobody', '000000')[0]
    ok('%s answers RADIUS (%s)' % (n, r_), r_ == 'reject')
P.stop_flag = True
time.sleep(1)
gap = P.gaps('vip', TSTART)
ok('RADIUS through the VIP address: unanswered %.0f s at most (%d asked, %d not)' % (
    gap, P.asked['vip'], len(P.lost['vip'])), gap <= 15)
for n in 'ab':
    m = dbq('a', "SELECT v FROM meta WHERE k = 'maint:%s'" % NAME[n])
    on = bool(json.loads(m or '{}').get('on'))
    ok('%s: not in maintenance' % n, not on, m)
for n in 'ab':
    _, hv = call(n, '/api/ha')
    rv = hv.get('readdress') or {}
    ok('%s: the addresses page: mine %s peer %s, mine here (%s)' % (n, rv.get('mine'), rv.get('peer'), rv.get('mine_here')),
       rv.get('mine') == ADDR[n] and rv.get('peer') == ADDR[OTHER[n]] and rv.get('mine_here'), rv)
    last = rv.get('last') or {}
    ok('%s: ... the last request answered without error' % n, not last.get('error'), last)
bad = dbq('a', "SELECT words FROM events WHERE ts >= %d AND level = 'bad' ORDER BY ts" % EV0)
ok('no bad event since the change began', not bad, bad[:1500])
warns = dbq('a', "SELECT node || ': ' || words FROM events WHERE ts >= %d AND level = 'warn' ORDER BY ts" % EV0)
print('   the warnings meanwhile:\n     ' + '\n     '.join(w[:220] for w in warns.splitlines()), flush=True)
# A warning that something did not go as it should (1.0.261): not a step of the change itself.
trouble = [w for w in warns.splitlines() if re.search(r'could not|cannot|failed|not the one saved|did not|not put in', w)]
ok('no warning of something that went wrong meanwhile', not trouble, trouble[:5])
time.sleep(1)
in_node('a', 'otp.alerts_evaluate(st, force=True) if hasattr(otp, "alerts_evaluate") else None')
AL = wait_for(lambda: (lambda k: k if not (set(k) - set(ALERTS0)) else None)(alert_keys()), 120, 10)
now_al = alert_keys()
ok('no alert left by it (%s)' % sorted(set(now_al) - set(ALERTS0)), not (set(now_al) - set(ALERTS0)),
   {k: v for k, v in now_al.items() if k not in ALERTS0})
for n in 'ab':
    call(n, '/api/after', {'action': 'check', 'node': NAME[n]})
time.sleep(8)
AF = after_ids()
ok('To be done by hand: nothing new (%s)' % sorted(AF - AFTER0), not (AF - AFTER0))
for n in DONE:
    j = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'net:job:%s'" % NAME[n]) or '{}')
    ok('%s: its job done, kept (%s)' % (n, j.get('state')), j.get('state') == 'done' and j.get('kept'))
print('the change took %.0f s; the case %.0f s' % (TEND - TSTART, time.time() - T0))
if not A.keep_sandbox:
    stop_all()
    # lo as setup.sh leaves it, for the other tests: .1 .2 .3.
    for a in ('10.99.0.1', '10.99.0.2', '10.99.0.3'):
        sh('ip addr add %s/24 dev lo' % a)
    for a in ('10.99.0.4', '10.99.0.11', '10.99.0.12'):
        sh('ip addr del %s/24 dev lo' % a)
done()
