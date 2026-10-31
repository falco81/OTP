# t_ha_alerts.py VERSION - the alerts of the database, its replication and the VIP address
# (1.0.194) on a cluster of two: replication paused - an alert; the same while a node is in
# maintenance - none, nor for the quiet time after it, then again; its switch off - none.
# The VIP address on no node (keepalived stopped on both) and keepalived not running on one -
# alerts; the same in maintenance - none; its switch off - none.
# Usage (root, after t_ha_auth.py on the same sandbox): python3 t_ha_alerts.py VERSION
import os, sys, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

helpers_on()
for n in 'ab':
    E[n]['OTP_ALERTS_QUIET_S'] = '20'
    stop(n)
    start(n)
    login(n)
ka_on()
time.sleep(5)


def problems(n='a'):
    out = in_node(n, 'print(json.dumps(sorted(otp.alert_problems(st, "en"))))')
    return json.loads(out.strip().split('\n')[-1])


def wait_for(cond, t=60, step=2):
    end = time.time() + t
    got = None
    while time.time() < end:
        got = problems()
        if cond(got):
            return True, got
        time.sleep(step)
    return False, got


def SET(d):
    return call('a', '/api/settings', {'settings': d})


SET({'alerts': 1, 'alerts_db': 1, 'alerts_vrrp': 1})
dbq('a', "DELETE FROM meta WHERE k = 'alerts:quiet'")
good, got = wait_for(lambda p: not any(k.startswith(('repl', 'vip:')) for k in p), 90)
ok('nothing wrong at the start (%s)' % got, good, got)
# ---- the replication --------------------------------------------------------------------
subprocess.run([sys.executable, '-I', V + '/otp.py', '--ha-pause', 'both'], env=E['a'], capture_output=True)
good, got = wait_for(lambda p: 'repl' in p, 120)
ok('replication paused: an alert (%s)' % got, good, got)
subprocess.run([sys.executable, '-I', V + '/otp.py', '--maintenance', 'on', '--node', 'nodeb', '--why', 'alerts test'],
               env=E['a'], capture_output=True)
good, got = wait_for(lambda p: 'repl' not in p, 30)
ok('... nodeb in maintenance: none (%s)' % got, good, got)
subprocess.run([sys.executable, '-I', V + '/otp.py', '--maintenance', 'off', '--node', 'nodeb'], env=E['a'],
               capture_output=True)
time.sleep(5)
ok('... maintenance over: still quiet a while (%s)' % problems(), 'repl' not in problems())
good, got = wait_for(lambda p: 'repl' in p, 60)
ok('... after the quiet time: the alert again (%s)' % got, good, got)
SET({'alerts_db': 0})
good, got = wait_for(lambda p: 'repl' not in p, 30)
ok('... its switch off: none (%s)' % got, good, got)
SET({'alerts_db': 1})
subprocess.run([sys.executable, '-I', V + '/otp.py', '--ha-resume', 'both'], env=E['a'], capture_output=True)
good, got = wait_for(lambda p: 'repl' not in p, 120)
ok('replication resumed: over (%s)' % got, good, got)
# ---- the VIP address --------------------------------------------------------------------
halib.KA_OFF.add('b')
ka_stop('b')
good, got = wait_for(lambda p: 'vip:ka:nodeb' in p, 90)
ok('keepalived not running on nodeb: an alert (%s)' % got, good, got)
halib.KA_OFF.add('a')
ka_stop('a')
good, got = wait_for(lambda p: 'vip:none' in p, 90)
ok('keepalived on neither: the VIP address on no node (%s)' % got, good, got)
subprocess.run([sys.executable, '-I', V + '/otp.py', '--maintenance', 'on', '--node', 'nodea', '--why', 'alerts test'],
               env=E['a'], capture_output=True)
good, got = wait_for(lambda p: not any(k.startswith('vip:') for k in p), 30)
ok('... nodea in maintenance: none (%s)' % got, good, got)
subprocess.run([sys.executable, '-I', V + '/otp.py', '--maintenance', 'off', '--node', 'nodea'], env=E['a'],
               capture_output=True)
good, got = wait_for(lambda p: 'vip:none' in p, 60)
ok('... after the quiet time: again (%s)' % got, good, got)
SET({'alerts_vrrp': 0})
good, got = wait_for(lambda p: not any(k.startswith('vip:') for k in p), 30)
ok('... its switch off: none (%s)' % got, good, got)
SET({'alerts_vrrp': 1})
halib.KA_OFF.discard('a')
halib.KA_OFF.discard('b')
good, got = wait_for(lambda p: not any(k.startswith('vip:') for k in p), 120)
ok('keepalived back on both: over (%s)' % got, good, got)
# A mail said "over" for something held in maintenance? the state keeps it.
st_ = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'alerts:state'") or '{}')
print('    alerts:state keys:', sorted((st_.get('problems') or {}).keys()))
SET({'alerts': 0})
done()
