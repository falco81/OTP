# t_ha_setnodes.py VERSION - Settings in a cluster: in effect on every node? (1.0.246) on the two-node sandbox: both
# nodes say the mark of the settings they read in (heartbeat conf_seen / conf_seen_at); a save on node a - node a
# in effect at once (said as its daemon has it), node b within seconds (it reads the change and says so at once);
# asked again - beat_asked written, node b's heartbeat comes within seconds; node b stopped - not heard from;
# standalone (the API's own words) not a cluster.
# Usage (root): python3 t_ha_setnodes.py VERSION
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)


def sn(n='a', again=False):
    return call(n, '/api/settings/nodes', {'action': 'again'} if again else None)[1]


def until(fn, secs=40):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.5)
    return None


def node(d, name):
    return next((x for x in d.get('nodes') or [] if x['name'] == name), {})


d = sn()
ok('a cluster of two', d.get('cluster') and len(d.get('nodes') or []) == 2, d)
ok('both nodes say what they read in (known), in step', until(lambda: all(x['known'] and x['seen'] for x in sn()['nodes'])), sn())
beat = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'node:%s'" % NAME['b']) or '{}')
ok('the heartbeat carries conf_seen and conf_seen_at', 'conf_seen' in beat and beat.get('conf_seen_at'), list(beat)[:30])
was = call('a', '/api/settings')[1]
keep = next((s['value'] for s in was.get('settings') or [] if s['key'] == 'logs_keep'), 14)
t0 = time.time()
c, x = call('a', '/api/settings', {'settings': {'logs_keep': int(keep) + 1}})
ok('a save on node a (%s)' % c, c == 200, x)
d = sn('a')
ok('...node a in effect at once (as its daemon has it)', node(d, NAME['a']).get('seen'), d)
b_seen = until(lambda: node(sn('a'), NAME['b']).get('seen'), 30)
ok('...node b in effect within seconds (%.1f s)' % (time.time() - t0), b_seen and time.time() - t0 < 20)
ok('...node b\'s own pages say the same (node a says it within its loop of 5 s)', until(lambda: all(x['seen'] for x in sn('b')['nodes']), 15))
before = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'node:%s'" % NAME['b']) or '{}').get('at')
d = sn('a', again=True)
ok('asked again: answered, beat_asked written', d.get('cluster') and dbq('a', "SELECT v FROM meta WHERE k = 'beat_asked'").endswith(NAME['a']))
ok('...node b\'s heartbeat comes within seconds', until(lambda: float(json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'node:%s'" % NAME['b']) or '{}').get('at') or 0) > float(before or 0), 15))
call('a', '/api/settings', {'settings': {'logs_keep': int(keep)}})
until(lambda: all(x['seen'] for x in sn('a')['nodes']), 30)
stop('b')
ok('node b stopped: not heard from (within 50 s)', until(lambda: not node(sn('a'), NAME['b']).get('alive'), 70))
start('b'); up('b'); login('b')
ok('...back: in effect again', until(lambda: all(x['alive'] and x['seen'] for x in sn('a')['nodes']), 60))
done()
