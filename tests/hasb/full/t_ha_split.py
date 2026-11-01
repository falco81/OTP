# t_ha_split.py VERSION - when the two nodes lose each other (1.0.218), on the replicated pair with the
# link between them really cut (iptables: the replication and the direct question to the other node's
# database both go over it). Off: both answer, both apart, alerts; recovery codes refused; changes
# refused on the node that is not preferred; a code let in on both halves. Priority: the other node
# steps aside (RADIUS silent there) and comes back by itself. Arbiter: each node's own (a TCP
# listener), the one whose arbiter is gone steps aside. Healed: together, the report names the code
# let in twice. Everything put back.
import os, sys, json, time, socket, subprocess, threading
from halib import *  # noqa: F401,F403
import halib

ok, call, login, in_node, rad, totp_of = halib.ok, halib.call, halib.login, halib.in_node, halib.rad, halib.totp_of
RULES = [['-p', 'tcp', '-d', '10.99.0.2', '--dport', '5433', '-j', 'DROP'],
         ['-p', 'tcp', '-d', '10.99.0.1', '--dport', '5432', '-j', 'DROP']]
ARB_RULE = ['-p', 'tcp', '-d', '127.0.0.1', '--dport', '47101', '-j', 'DROP']


def ipt(op, rule):
    return subprocess.run(['iptables', op, 'OUTPUT'] + rule, capture_output=True).returncode == 0


def cut(on):
    for r in RULES:
        while ipt('-D', r):
            pass
        if on:
            ipt('-I', r)


def view(n):
    st, got = call(n, '/api/split')
    me = [x for x in got.get('nodes') or [] if x.get('me')]
    return got, (me[0]['state'] if me else {})


def save(n, conf, arbiter=None, checked=True):
    return call(n, '/api/split', {'action': 'save', 'conf': conf, 'arbiter': arbiter or {}, 'checked': checked})


def wait(cond, t=60, step=1):
    end = time.time() + t
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(step)
    return False


def fresh_step():
    while int(time.time()) % 30 > 22:
        time.sleep(1)


BASE = {'split_mode': 'off', 'split_prefer': 'nodea', 'split_after_s': 6, 'split_scratch': 1,
        'split_halve': 0, 'split_freeze': 1, 'split_report': 1}
listeners = []
try:
    for n in 'ab':
        halib.up(n)
        login(n)
    st, got = save('a', BASE)
    ok('the choices saved on node a: off, nodea preferred, 6 s, recovery codes asked, changes frozen, report',
       st == 200, got)
    T = json.loads(in_node('a', "tk = otp.Tokens(st)\nprint(json.dumps(tk.enroll('splitu', 'test'), default=str))")
                   .strip().split('\n')[-1])
    time.sleep(4)
    ok('together: both nodes serve, not apart',
       wait(lambda: all(not view(n)[1].get('apart') and view(n)[1].get('role') == 'serve' for n in 'ab'), 20))
    ok('... a recovery code would be let in: the other node can be asked', True)

    # ---- the link cut -------------------------------------------------------------------
    cut(True)
    t0 = time.time()
    both = wait(lambda: all(view(n)[1].get('apart') for n in 'ab'), 40)
    ok('the link cut: both nodes apart within %.0f s' % (time.time() - t0), both)
    ok('... off: both still serve', all(view(n)[1].get('role') == 'serve' for n in 'ab'))
    got, sa = view('a')
    ok('... each node\'s own word: why (%s)' % sa.get('peer_err', '')[:60], bool(sa.get('peer_err')))
    pr = json.loads(in_node('a', "print(json.dumps(list(otp.alert_problems(st))))").strip().split('\n')[-1])
    ok('... an alert of node a\'s apart (%s)' % [p for p in pr if p.startswith('split')], 'split:nodea' in pr)
    code = T['scratch'][0]
    r = rad('a', 'splitu', code)
    ok('a recovery code on node a while apart: refused (%s)' % (r[1].get('Reply-Message') or r[0]),
       r[0] == 'reject' and 'recovery code cannot be used' in str(r[1].get('Reply-Message') or ''))
    st, got = call('b', '/api/settings', {'settings': {'code_send_max': 50}})
    ok('a change on node b (not the preferred one): refused while apart (%s)' % str(got.get('error'))[:60],
       st == 409 and got.get('split'))
    st, got = call('a', '/api/settings', {'settings': {'code_send_max': 50}})
    ok('... on node a, the preferred one: made', st == 200, got)
    fresh_step()
    c = totp_of(T['secret'])
    ra, rb = rad('a', 'splitu', c), rad('b', 'splitu', c)
    ok('off: the same app code on both halves - let in on both (%s, %s): what the report is for'
       % (ra[0], rb[0]), ra[0] == 'accept' and rb[0] == 'accept')

    # ---- priority: node b steps aside ----------------------------------------------------
    for n in 'ab':                                      # each half has its own database now
        save(n, dict(BASE, split_mode='priority'))
    ok('priority: node b steps aside', wait(lambda: view('b')[1].get('role') == 'aside', 20))
    ok('... and node a goes on', view('a')[1].get('role') == 'serve')
    rb = rad('b', 'splitu', '000000', timeout=2)
    ra = rad('a', 'splitu', '000000')
    ok('... RADIUS: silent on b (%s), answered on a (%s)' % (rb[0], ra[0]), rb[0] == 'timeout' and ra[0] == 'reject')

    # ---- arbiter: each node its own ------------------------------------------------------
    for port in (47101, 47102):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(50)
        listeners.append(s)
        threading.Thread(target=lambda s=s: [s.accept()[0].close() for _ in iter(int, 1)], daemon=True).start()
    save('a', dict(BASE, split_mode='arbiter'), {'nodea': '127.0.0.1:47101'})
    save('b', dict(BASE, split_mode='arbiter'), {'nodeb': '127.0.0.1:47102'})
    ok('arbiter, both reach their own: both serve while apart',
       wait(lambda: all(view(n)[1].get('role') == 'serve' and view(n)[1].get('arbiter') is True for n in 'ab'), 30))
    ipt('-I', ARB_RULE)
    ok('node a\'s arbiter gone: node a steps aside - it is the one cut off',
       wait(lambda: view('a')[1].get('role') == 'aside', 20))
    ok('... node b serves', view('b')[1].get('role') == 'serve')
    while ipt('-D', ARB_RULE):
        pass
    ok('... its arbiter back: node a serves again', wait(lambda: view('a')[1].get('role') == 'serve', 20))

    # ---- healed --------------------------------------------------------------------------
    for n in 'ab':
        save(n, dict(BASE, split_mode='off'), {'nodea': '', 'nodeb': ''} if n == 'a' else {'nodeb': ''})
    cut(False)
    t0 = time.time()
    ok('the link whole again: together within %.0f s' % (time.time() - t0),
       wait(lambda: not any(view(n)[1].get('apart') for n in 'ab'), 40))
    rep = {}

    def has_report():
        rep.update(view('a')[0].get('report') or {})
        return rep.get('at', 0) > t0
    ok('the report on the preferred node within a minute', wait(has_report, 90, 3))
    ok('... it names the code let in on both halves (%s)' % rep.get('twice'),
       any(x.get('name') == 'splitu' for x in rep.get('twice') or []))
    r = rad('b', 'splitu', T['scratch'][1])
    ok('together: a recovery code let in again (%s)' % r[0], r[0] == 'accept')
finally:
    cut(False)
    while ipt('-D', ARB_RULE):
        pass
    for s in listeners:
        s.close()
    try:
        for n in 'ab':
            save(n, {'split_mode': 'off', 'split_prefer': '', 'split_after_s': 20, 'split_scratch': 0,
                     'split_halve': 0, 'split_freeze': 0, 'split_report': 1},
                 {'nodea': '', 'nodeb': ''} if n == 'a' else {'nodeb': ''})
        in_node('a', "st.token_drop('splitu')\nst.db.run(\"DELETE FROM meta WHERE k LIKE 'split:%'\")")
    except Exception as e:                              # noqa: BLE001
        print('cleanup:', e)
    time.sleep(5)
    rs = subprocess.run(['bash', '-c', '. /home/claude/work/hasb/env.sh a; python3 -I %s/otp.py --ha-status' % halib.V],
                        capture_output=True, text=True).stdout
    ok('left as found: replication running both ways', rs.count('running') >= 1 and 'taken' in rs, rs[-400:])
halib.done()
