# t_ha_maint.py VERSION - the night's work on a cluster of two, by itself: the updates on a
# schedule (every update, a restart where needed, one node at a time) and the restart of the
# nodes on a schedule. A restart of a machine here: its root helper writes what it would do into
# S/n/power - otp and keepalived of that node are stopped, then started as after a boot.
# All the time: RADIUS asked on each node and on the VIP address, and a code from the app let
# in through the VIP address every few seconds. Never both nodes down at once; the VIP address
# answered all the way; each node back, on the same version, replication healthy.
# Usage (root, after t_ha_auth.py on the same sandbox): python3 t_ha_maint.py VERSION
import os, sys, time, json, subprocess, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

helpers_on()
for n in 'ab':
    stop(n)                      # started again with this env.sh (OTP_VIP_HERE_BY_ROLE)
    start(n)
    login(n)
ka_on()
T = json.loads(in_node('a', 'tk = otp.Tokens(st); print(json.dumps(tk.enroll("nightuser", "test")))').strip().split('\n')[-1])
time.sleep(3)
P = Prober(every=0.25)
DOWN = {'both': 0, 'events': []}
BOOTS = {'a': 0, 'b': 0}


def watch_power():
    """What a helper would have done to the machine, done: otp and keepalived of that node off,
    then on again as after a boot."""
    seen = {n: os.path.getsize('%s/%s/power' % (S, n)) for n in 'ab'}
    while True:
        for n in 'ab':
            f = '%s/%s/power' % (S, n)
            size = os.path.getsize(f)
            if size <= seen[n]:
                continue
            line = open(f).read()[seen[n]:].strip().split('\n')[-1]
            seen[n] = size
            what, secs = line.split()[0], int(line.split()[1])
            DOWN['events'].append((time.strftime('%H:%M:%S'), n, line))

            def boot(n=n, secs=secs, what=what):
                time.sleep(secs)
                P.expect_down.add(n)
                halib.KA_OFF.add(n)
                ka_stop(n)
                stop(n)
                time.sleep(4)
                if what == 'reboot':
                    start(n, reboot=True)
                    halib.KA_OFF.discard(n)
                    BOOTS[n] += 1
                    time.sleep(3)
                    P.expect_down.discard(n)
            threading.Thread(target=boot, daemon=True).start()
        if not running('a') and not running('b'):
            DOWN['both'] += 1
        time.sleep(0.5)


threading.Thread(target=watch_power, daemon=True).start()
IN = {'asked': 0, 'in': 0, 'out': []}


def through_vip():
    last = None
    while True:
        s = int(time.time()) // 30
        if s != last:
            time.sleep(1)
            r = rad('vip', 'nightuser', totp_of(T['secret']))[0]
            if r == 'timeout':
                # Asked again, as a NAS does: here the VIP address is on lo, and the node it
                # is asked on is read from keepalived's role file - a moment late as it moves.
                time.sleep(1)
                r = rad('vip', 'nightuser', totp_of(T['secret']))[0]
            IN['asked'] += 1
            if r == 'accept':
                IN['in'] += 1
            else:
                IN['out'].append((time.strftime('%H:%M:%S'), r, vip_master()))
            last = s
        time.sleep(1)


threading.Thread(target=through_vip, daemon=True).start()


def SET(d):
    return call('a', '/api/settings', {'settings': d})


def osup_plan():
    return call('a', '/api/osup')[1].get('plan') or {}


def wait(cond, t, step=2):
    end = time.time() + t
    while time.time() < end:
        try:
            got = cond()
            if got:
                return got
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(step)
    return None


btime = {n: open('%s/%s/btime' % (S, n)).read().strip() for n in 'ab'}
# Once a day each: today's taken by a run before this one, forgotten.
dbq('a', "DELETE FROM meta WHERE k IN ('power:auto:day', 'osup:auto:day', 'osup:check:day', 'power:plan')")
# ---- 1. the updates on a schedule: every one, restarted where needed -------------------
t0 = time.time()
old = osup_plan().get('id')
st_, got = SET({'osup_auto': 1, 'osup_auto_every': 'daily', 'osup_auto_at': '00:00', 'osup_auto_what': 'all',
                'osup_auto_reboot': 'auto'})
ok('the updates on a schedule switched on (%s)' % st_, st_ == 200, got)
p = wait(lambda: (lambda v: v if v.get('by') == 'otp (on a schedule)' and v.get('id') != old else None)(osup_plan()), 180)
ok('... started by itself (%s)' % (p or {}).get('id'), p)
p = wait(lambda: (lambda v: v if v.get('state') in ('done', 'failed') else None)(osup_plan()), 1500, 5)
ok('... done on both nodes (%s)' % (p or {}).get('state'), p and p.get('state') == 'done',
   json.dumps(osup_plan())[:600])
ok('... both machines restarted, one after the other (%s)' % BOOTS, BOOTS['a'] >= 1 and BOOTS['b'] >= 1, DOWN['events'])
SET({'osup_auto': 0})
time.sleep(20)
ok('... never both nodes down at once', DOWN['both'] == 0, DOWN['both'])
gap = P.gaps('vip', t0)
ok('... the VIP address unanswered for %.0f s at most' % gap, gap <= 10)
for n in 'ab':
    ok('... %s back, the same version' % n, running(n) and (call(n, '/api/health', sess=False)[0] in (200, 401, 403)))
# ---- 2. the restart on a schedule ----------------------------------------------------
for n in 'ab':
    login(n)
b0 = dict(BOOTS)
t0 = time.time()
st_, got = SET({'power_auto': 1, 'power_auto_every': 'weekly', 'power_auto_day': str(time.localtime().tm_wday + 1),
                'power_auto_at': '00:00', 'power_auto_needed': 0})
ok('the restart on a schedule switched on (%s)' % st_, st_ == 200, got)
ok('... both restarted, one after the other', wait(lambda: BOOTS['a'] > b0['a'] and BOOTS['b'] > b0['b'], 900, 5),
   (BOOTS, DOWN['events'][-4:]))
SET({'power_auto': 0})
time.sleep(25)
ok('... never both nodes down at once', DOWN['both'] == 0, DOWN['both'])
gap = P.gaps('vip', t0)
ok('... the VIP address unanswered for %.0f s at most' % gap, gap <= 10)
# ---- all the way ------------------------------------------------------------------------
for n in 'ab':
    login(n)
ok('replication healthy at the end on both nodes', wait(lambda: all(
    (call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab'), 120, 5))
ok('a code through the VIP address let in every time it was tried (%d of %d)' % (IN['in'], IN['asked']),
   IN['asked'] > 5 and not IN['out'], IN['out'])
P.stop_flag = True
print('    restarts:', DOWN['events'])
print('    the VIP address: %d asked, %d not answered' % (P.asked['vip'], len(P.lost['vip'])))
done()
