# t_ha_clock.py VERSION - the clocks of the nodes (1.0.222) on the replicated pair. The two sandbox
# nodes share one clock, so a node's wrong clock is played by its reference: each node's own fake
# SNTP server, set to say another time. Off: nothing measured. Watch: both measured, alike, no alert.
# Node b "300 s behind": the alert; guard - b steps aside (RADIUS silent there, a answers); right again
# - b answers. Both off alike: nobody steps aside. Codes by the corrected time: b answers and lets in
# the code of the reference's time. Everything put back.
import os, sys, json, time, subprocess
from halib import *  # noqa: F401,F403
import halib
sys.path.insert(0, '/home/claude/ws/tests/clock')
from fakentp import FakeNtp  # noqa: E402

ok, call, login, in_node, rad = halib.ok, halib.call, halib.login, halib.in_node, halib.rad
fa, fb = FakeNtp(0.0).start(), FakeNtp(0.0).start()
REFS = {'nodea': '127.0.0.1:%d' % fa.port, 'nodeb': '127.0.0.1:%d' % fb.port}


def state(n, of=None):
    st, got = call(n, '/api/clock')
    for x in got.get('nodes') or []:
        if (of and x['name'] == of) or (not of and x.get('me')):
            return x.get('state') or {}
    return {}


def save(conf, refs=None, checked=True):
    return call('a', '/api/clock', {'action': 'save', 'conf': conf, 'refs': refs or {}, 'checked': checked})


def wait(cond, t=90, step=2):
    end = time.time() + t
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(step)
    return False


OFF = {'clock_mode': 'off', 'clock_warn_s': 2, 'clock_aside_s': 20, 'clock_codes': 0, 'clock_beat': 0,
       'clock_locks': 0, 'health_dir': 0}
try:
    for n in 'ab':
        halib.up(n)
        login(n)
    st, got = save(OFF)
    ok('off saved', st == 200, got)
    time.sleep(12)
    in_node('a', "st.db.run(\"DELETE FROM meta WHERE k LIKE 'clock:%'\")")   # left by a run before
    time.sleep(12)
    ok('off: nothing measured on either node', all(not state(n).get('engaged') and state(n).get('ref') is None
                                                   for n in 'ab'), [state(n) for n in 'ab'])
    st, got = save(dict(OFF, clock_mode='watch'), REFS)
    ok('watch saved, each node its own reference', st == 200, got)
    ok('watch: both measured against their reference, right',
       wait(lambda: all(state(n).get('ref') is not None and abs(state(n)['ref']) < 1 for n in 'ab')))
    sb = state('b')
    ok('... b measured a\'s clock through a\'s database: alike (%s %s)' % (sb.get('skew_of'), sb.get('skew')),
       wait(lambda: state('b').get('skew') is not None and abs(state('b')['skew']) < 1 and state('b').get('skew_of') == 'nodea'))
    pr = json.loads(in_node('a', "print(json.dumps(list(otp.alert_problems(st))))").strip().split('\n')[-1])
    ok('... no alert of the clocks (%s)' % [p for p in pr if p.startswith('clock')], not [p for p in pr if p.startswith('clock')])
    fb.offset = 300.0
    ok('b\'s reference says b is 300 s behind - measured within a minute',
       wait(lambda: abs((state('b').get('ref') or 0) - 300) < 2, 75))
    ok('... the alert on b', wait(lambda: 'clock:skew:nodeb' in json.loads(in_node('a', "print(json.dumps(list(otp.alert_problems(st))))").strip().split('\n')[-1]), 30))
    ok('... watch: b still answers', state('b').get('role') == 'serve')
    st, got = save(dict(OFF, clock_mode='guard'), checked=False)
    ok('guard without a try: refused (%s)' % st, st == 409)
    st, got = save(dict(OFF, clock_mode='guard'))
    ok('guard saved', st == 200, got)
    ok('guard: b steps aside', wait(lambda: state('b').get('role') == 'aside', 60))
    ok('... a answers', state('a').get('role') == 'serve')
    rb, ra = rad('b', 'nobody-clk', '000000', timeout=2), rad('a', 'nobody-clk', '000000')
    ok('... RADIUS: silent on b (%s), answered on a (%s)' % (rb[0], ra[0]), rb[0] == 'timeout' and ra[0] == 'reject')
    fb.offset = 0.0
    ok('b\'s clock right again: b answers by itself', wait(lambda: state('b').get('role') == 'serve', 75))
    fa.offset = fb.offset = 300.0
    time.sleep(40)
    ok('both 300 s off alike: neither steps aside', all(state(n).get('role') == 'serve' for n in 'ab'),
       [state(n) for n in 'ab'])
    fa.offset = 0.0
    st, got = save(dict(OFF, clock_mode='guard', clock_codes=1))
    T = json.loads(in_node('a', "tk = otp.Tokens(st)\nprint(json.dumps(tk.enroll('clku', 'test'), default=str))")
                   .strip().split('\n')[-1])
    ok('codes by the corrected time: b (300 s behind) answers', wait(lambda: state('b').get('codes_fixed') is True and state('b').get('role') == 'serve', 90)
       and state('b').get('role') == 'serve', state('b'))
    while int(time.time()) % 30 > 22:
        time.sleep(1)
    c = in_node('a', "print(otp.totp(%r, otp.time.time() + 300))" % T['secret']).strip().split('\n')[-1]
    r = rad('b', 'clku', c)
    ok('... b lets in the code of the reference\'s time (%s)' % r[0], r[0] == 'accept')
finally:
    fa.offset = fb.offset = 0.0
    try:
        save(OFF, {'nodea': '', 'nodeb': ''})
        time.sleep(15)                                  # both have stopped writing their rows
        in_node('a', "st.token_drop('clku')\nst.db.run(\"DELETE FROM meta WHERE k LIKE 'clock:%'\")")
    except Exception as e:                              # noqa: BLE001
        print('cleanup:', e)
    time.sleep(8)
    ok('left as found: both answer', all(state(n).get('role', 'serve') == 'serve' for n in 'ab'))
    rs = subprocess.run(['bash', '-c', '. /home/claude/work/hasb/env.sh a; python3 -I %s/otp.py --ha-status' % halib.V],
                        capture_output=True, text=True).stdout
    ok('left as found: replication running both ways', rs.count('running') >= 1 and 'taken' in rs, rs[-400:])
    fa.close(); fb.close()
halib.done()
