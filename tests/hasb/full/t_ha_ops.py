# t_ha_ops.py VERSION - the cluster when something happens to a node: otp on the node with the
# VIP address stops (crash), the whole machine goes off (keepalived too), a node goes into
# maintenance (planned: the address handed over at once, RADIUS answered meanwhile), each
# comes back. RADIUS asked all the time on each node and on the VIP address: how long the
# VIP address went unanswered each time; codes from the app let in through the VIP address
# right after each move; replication healthy after each.
# Usage (root, after t_ha_auth.py on the same sandbox): python3 t_ha_ops.py VERSION
import os, sys, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)
ka_on()
for _ in range(60):
    if vip_master():
        break
    time.sleep(1)
ok('the VIP address on %s' % vip_master(), vip_master())
K = {}
out = in_node('a', 'print(json.dumps({r["name"]: 1 for r in st.db.rows("SELECT name FROM tokens")}))')
# A token of its own for this test, its secret known.
T = json.loads(in_node('a', 'tk = otp.Tokens(st); print(json.dumps(tk.enroll("opsuser", "test")))').strip().split('\n')[-1])
time.sleep(3)
P = Prober(every=0.25)


def fresh():
    s0 = int(time.time()) // 30
    while int(time.time()) // 30 == s0:
        time.sleep(0.5)


def wait_master(not_n=None, want=None, t=60):
    for _ in range(t * 4):
        m = vip_master()
        if m and m != not_n and (want is None or m == want):
            return m
        time.sleep(0.25)
    return vip_master()


def in_through_vip(what):
    fresh()
    r = rad('vip', 'opsuser', totp_of(T['secret']))[0]
    ok('%s: a code through the VIP address: in (%s)' % (what, r), r == 'accept')


def repl_ok(what):
    for _ in range(60):
        if all((call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab' if running(n)):
            ok('%s: replication healthy' % what, True)
            return
        time.sleep(2)
    ok('%s: replication healthy' % what, False, [call(n, '/api/ha')[1].get('replication') for n in 'ab'])


# 1. otp on the node with the address stops at once (a crash): the address moves
m = vip_master()
o = 'b' if m == 'a' else 'a'
t0 = time.time()
P.expect_down.add(m)
stop(m)
m2 = wait_master(not_n=m)
took = time.time() - t0
ok('otp of %s gone: the address on %s within %.0f s' % (m, m2, took), m2 == o and took < 20, (vip_role('a'), vip_role('b')))
time.sleep(2)
gap = P.gaps('vip', t0)
ok('... the VIP address unanswered for %.0f s at most' % gap, gap <= 20)
in_through_vip('after the crash')
start(m)
login(m)
P.expect_down.discard(m)
time.sleep(5)
repl_ok('%s back' % m)

# 2. the whole machine of the node with the address goes off (keepalived with it)
m = vip_master()
o = 'b' if m == 'a' else 'a'
t0 = time.time()
P.expect_down.add(m)
halib.KA_OFF.add(m)
ka_stop(m)
stop(m)
m2 = wait_master(not_n=m)
took = time.time() - t0
ok('the machine of %s off: the address on %s within %.0f s' % (m, m2, took), m2 == o and took < 10)
time.sleep(2)
ok('... the VIP address unanswered for %.0f s at most' % P.gaps('vip', t0), P.gaps('vip', t0) <= 10)
in_through_vip('the other machine off')
# a code used now on the node left must not be good on the one coming back
fresh()
c = totp_of(T['secret'])
ok('a code on %s while %s is off: in' % (o, m), rad(o, 'opsuser', c)[0] == 'accept')
start(m, reboot=True)
login(m)
halib.KA_OFF.discard(m)
P.expect_down.discard(m)
time.sleep(4)
r = rad(m, 'opsuser', c)[0]
ok('... the same code on %s once it is back: refused (%s)' % (m, r), r == 'reject')
repl_ok('the machine of %s back' % m)

# 3. maintenance of the node with the address: handed over at once, answered meanwhile
time.sleep(5)
m = vip_master()
o = 'b' if m == 'a' else 'a'
t0 = time.time()
st_, got = call(m, '/api/maintenance', {'action': 'on', 'node': NAME[m], 'why': 'test'})
if st_ != 200:
    st_, got = call(m, '/api/upgrade', {'action': 'maintenance', 'node': NAME[m], 'on': True})
ok('maintenance of %s asked (%s)' % (m, st_), st_ == 200, got)
m2 = wait_master(not_n=m, t=30)
took = time.time() - t0
ok('... the address on %s within %.0f s' % (m2, took), m2 == o and took < 12, (vip_role('a'), vip_role('b')))
ok('... the VIP address never unanswered meanwhile (%d)' % len([t for t in P.lost['vip'] if t >= t0]),
   not [t for t in P.lost['vip'] if t >= t0])
in_through_vip('maintenance')
st_, got = call(m, '/api/maintenance', {'action': 'off', 'node': NAME[m]})
if st_ != 200:
    st_, got = call(m, '/api/upgrade', {'action': 'maintenance', 'node': NAME[m], 'on': False})
ok('maintenance of %s over (%s)' % (m, st_), st_ == 200, got)
time.sleep(15)
repl_ok('after maintenance')
P.stop_flag = True
time.sleep(1)
print('    the VIP address: %d asked, %d not answered' % (P.asked['vip'], len(P.lost['vip'])))
done()
