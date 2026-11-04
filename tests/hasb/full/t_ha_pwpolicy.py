# t_ha_pwpolicy.py VERSION - Local users -> Password policy (1.0.245) on the two-node sandbox: set on node a's pages, put
# in by both nodes (each its own root helper; one machine here, the files shared); node b's pages show it set and in
# effect on both; a password the policy does not take refused on node b too; given back to the system from node b,
# taken out by both - every file as it was. With the guard of root's actions on: a policy written straight into the
# database is put in by neither node.
# Usage (root): python3 t_ha_pwpolicy.py VERSION
import os, sys, time, json, hashlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)
FILES = ['/etc/login.defs', '/etc/security/pwhistory.conf', '/etc/security/faillock.conf', '/etc/security/pwquality.conf']
md5 = lambda f: hashlib.md5(open(f, 'rb').read()).hexdigest() if os.path.exists(f) else None
BEFORE = {f: md5(f) for f in FILES}
DROP = '/etc/security/pwquality.conf.d/50-otp.conf'
both = [NAME['a'], NAME['b']]


def view(n):
    return call(n, '/api/osusers')[1]


def until(fn, secs=90):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(1)
    return None


C = {'managed': True, 'minlen': 15, 'minclass': 3, 'maxrepeat': 3, 'dictcheck': 1, 'usercheck': 1, 'difok': 4,
     'remember': 4, 'max_days': 120, 'min_days': 0, 'warn_days': 14, 'deny': 6, 'unlock_time': 600, 'fail_interval': 900}
call('a', '/api/osusers', {'action': 'refresh', 'nodes': both})
ok('both nodes read: the system\'s own, put in as such', until(lambda: len(view('a').get('nodes') or []) == 2 and
                                                          all(n.get('policy_applied') for n in view('a')['nodes'])), view('a').get('nodes'))
c, x = call('a', '/api/osusers', {'action': 'policy', 'policy': C})
ok('the policy saved on node a (%s)' % c, c == 200, x)
ok('...put in by both nodes', until(lambda: all(n.get('policy_applied') and (n.get('policy') or {}).get('managed')
                                                for n in view('a')['nodes'])),
   [(n['name'], n.get('policy_applied'), n.get('policy_error')) for n in view('a')['nodes']])
vb = view('b')
ok('...node b\'s pages: set, and in effect on both', vb.get('policy', {}).get('managed') and vb['policy'].get('minlen') == 15 and
   all(n.get('policy_applied') and (n.get('policy') or {}).get('pwquality', {}).get('minlen') == 15 for n in vb['nodes']), vb.get('nodes'))
ok('...in the files', os.path.exists(DROP) and 'minlen = 15' in open(DROP).read() and 'PASS_MAX_DAYS\t120' in open('/etc/login.defs').read())
c, x = call('b', '/api/osusers', {'action': 'add', 'name': 'otpl_hapw', 'password': 'Short-1x', 'nodes': both})
ok('a password the policy does not take: refused on node b too (%s)' % c, c == 400 and 'policy' in x.get('error', ''), x)
guard = all(json.load(open('%s/%s/config.json' % (S, n))).get('db_guard') for n in 'ab')
if guard:
    dbq('a', "UPDATE meta SET v = '%s' WHERE k = 'host:pwpolicy:conf'" % json.dumps(dict(C, minlen=6)).replace("'", "''"))
    time.sleep(20)
    ok('the guard on: a policy written straight into the database put in by neither node - nor the policy taken away',
       os.path.exists(DROP) and 'minlen = 15' in open(DROP).read())
    ok('...the pages say its row was refused', view('a').get('policy_refused') and view('b').get('policy_refused'))
    call('a', '/api/osusers', {'action': 'policy', 'policy': C})
    time.sleep(5)
c, x = call('b', '/api/osusers', {'action': 'policy', 'policy': dict(C, managed=False)})
ok('given back to the system on node b (%s)' % c, c == 200)
ok('...taken out by both nodes', until(lambda: all(n.get('policy_applied') and not (n.get('policy') or {}).get('managed')
                                                   for n in view('a')['nodes'])))
ok('...every file as it was', until(lambda: not os.path.exists(DROP) and {f: md5(f) for f in FILES} == BEFORE, 30),
   {f: (BEFORE[f], md5(f)) for f in FILES})
done()
