# t_ha_osusers.py VERSION - Settings -> Local users (1.0.243) on the two-node sandbox: a user asked on node a's
# pages for both nodes is made by each node's root helper (one machine here: the second finds it there, the same
# UID - no fault), the password asked on node b's pages for both, locked and unlocked, taken away; root refused;
# the sealed hash taken out of the asking rows once done. With the guard of root's actions on: a change written
# straight into the database (unsigned) is done by neither node.
# Usage (root): python3 t_ha_osusers.py VERSION
import os, sys, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)
for u in ('otpl_ha', 'otpl_evil'):
    subprocess.run(['userdel', '-r', u], capture_output=True)


def shadow(name):
    for ln in open('/etc/shadow'):
        p = ln.split(':')
        if p[0] == name:
            return p
    return None


def view(n='a'):
    return call(n, '/api/osusers')[1]


def user_on(node, name):
    return next((u for u in node.get('users') or [] if u['name'] == name), None)


def until(fn, secs=60):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(1)
    return None


both = [NAME['a'], NAME['b']]
call('a', '/api/osusers', {'action': 'refresh', 'nodes': both})
ok('both nodes tell their users, root first', until(lambda: len(view().get('nodes') or []) == 2 and
                                                   all(user_on(x, 'root') for x in view()['nodes'])), view())
c, x = call('a', '/api/osusers', {'action': 'add', 'name': 'otpl_ha', 'gecos': 'HA Test', 'password': 'Ha-Pass-243-long',
                                  'sudo': True, 'nodes': both})
ok('a user asked on node a for both (%s)' % c, c == 200 and x.get('nodes') == both, x)
ok('...both nodes have it, one UID', until(lambda: all(user_on(n, 'otpl_ha') for n in view()['nodes']) and
                                           len({user_on(n, 'otpl_ha')['uid'] for n in view()['nodes']}) == 1), view())
ok('...node b sees it too, through the replicated rows', until(lambda: all(user_on(n, 'otpl_ha') for n in view('b')['nodes'])))
said = [s for n in view()['nodes'] for s in n.get('said') or [] if s.get('name') == 'otpl_ha']
ok('...each node said done', len(said) >= 2 and all(s['ok'] for s in said), said)


def hashes(node):
    return sum(1 for r in json.loads('[%s]' % ','.join(
        v for v in dbq(node, "SELECT v FROM meta WHERE k LIKE 'host:users:want:%'").split('\n') if v.strip()) or '[]')
        for a in r if isinstance(a, dict) and a.get('hash'))


ok('...the sealed hash taken out of the asking rows once done', until(lambda: hashes('a') == 0 and hashes('b') == 0, 40))
c, x = call('b', '/api/osusers', {'action': 'password', 'name': 'otpl_ha', 'password': 'Ha-Other-243-long', 'nodes': both})
ok('a new password asked on node b for both (%s)' % c, c == 200)
ok('...set', until(lambda: subprocess.run(['openssl', 'passwd', '-6', '-salt', (shadow('otpl_ha') or ['', '$6$x$'])[1].split('$')[2], '-stdin'],
                                          input='Ha-Other-243-long\n', capture_output=True, text=True).stdout.strip() == (shadow('otpl_ha') or ['', ''])[1]))
c, x = call('b', '/api/osusers', {'action': 'password', 'name': 'root', 'password': 'Ha-Other-243-long', 'nodes': both})
ok('root refused on node b too (%s)' % c, c == 400)
c, x = call('a', '/api/osusers', {'action': 'lock', 'name': 'otpl_ha', 'nodes': both})
ok('locked on both', c == 200 and until(lambda: all((user_on(n, 'otpl_ha') or {}).get('locked') for n in view()['nodes'])))
c, x = call('a', '/api/osusers', {'action': 'unlock', 'name': 'otpl_ha', 'nodes': both})
ok('unlocked on both', c == 200 and until(lambda: not any((user_on(n, 'otpl_ha') or {}).get('locked') for n in view()['nodes'])))
guard = all(json.load(open('%s/%s/config.json' % (S, n))).get('db_guard') for n in 'ab')
if guard:
    evil = json.dumps([{'id': 'evil0001', 'do': 'add', 'name': 'otpl_evil', 'sudo': True, 'uid': 45678, 'by': 'x', 'at': time.time()}])
    dbq('a', "INSERT INTO meta (k, v) VALUES ('host:users:want:%s@@%s', '%s') ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v"
        % (NAME['b'], 'evilnode', evil.replace("'", "''")))
    time.sleep(15)
    ok('the guard on: a user asked straight in the database (with sudo) - made by neither node', not shadow('otpl_evil'))
    dbq('a', "DELETE FROM meta WHERE k = 'host:users:want:%s@@evilnode'" % NAME['b'])
else:
    print('   (the guard of root\'s actions is off: the unsigned row is not tried)')
c, x = call('a', '/api/osusers', {'action': 'drop', 'name': 'otpl_ha', 'home': True, 'nodes': both})
ok('taken away on both', c == 200 and until(lambda: not shadow('otpl_ha') and not any(user_on(n, 'otpl_ha') for n in view()['nodes'])))
subprocess.run(['userdel', '-r', 'otpl_evil'], capture_output=True)
done()
