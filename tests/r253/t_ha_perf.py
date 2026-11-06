"""t_ha_perf.py - 1.0.253: the performance meter of both nodes (HA sandbox, replicated). Off: no
row, nothing in the API. On: a page asking node a gets node b's readings, a second apart; one
row a node in meta, written every 5 s only while looked at; the page gone, both stop within 45 s;
off again: the rows taken away. RADIUS goes on answering throughout."""
import sys, os, time, json
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
import halib as H

for n in 'ab':
    if not H.running(n):
        H.start(n)
    H.up(n)
# the administrator, as t_ha_auth makes it (this may run on a sandbox of its own)
H.in_node('a', "try:\n    st.add_account('local', 'fulladmin', %r, must_change=0)\nexcept Exception: pass\n" % H.ADMIN_PW)
time.sleep(3)
for n in 'ab':
    if not H.login(n):
        H.stop(n); H.start(n); H.login(n)


def rows(n):
    out = H.dbq(n, "SELECT k, v FROM meta WHERE k LIKE 'load:%' ORDER BY k")
    return dict(ln.split('|', 1) for ln in out.splitlines() if '|' in ln)


def setp(on):
    st, got = H.call('a', '/api/settings', {'settings': {'perf_meter': on}})
    time.sleep(4)
    return st


H.ok('off at the start (the default)', setp(False) == 200)
st, got = H.call('a', '/api/load')
H.ok('off: /api/load 404', st == 404, (st, got))
time.sleep(6)
H.ok('off: no row of the meter on either node', not rows('a') and not rows('b'), (rows('a'), rows('b')))

H.ok('switched on', setp(True) == 200)
# the page on a: asks every 2 s for 40 s
since = {}
last, seen_b = None, []
t_end = time.time() + 40
while time.time() < t_end:
    q = ','.join('%s:%s' % kv for kv in since.items())
    st, d = H.call('a', '/api/load' + ('?since=' + q if q else ''))
    if st == 200:
        last = d
        if d.get('hist'):
            since[d['node']] = d['hist'][-1]['at']
        for o in d.get('others') or []:
            if o.get('hist'):
                seen_b += o['hist']
                since[o['node']] = o['hist'][-1]['at']
    time.sleep(2)
H.ok('a answers with its numbers and readings', last and last.get('now', {}).get('mem_total') and last.get('node') == H.NAME['a'], last)
o = (last or {}).get('others') or []
H.ok('...and the other node, by its name, heard', o and o[0]['node'] == H.NAME['b'] and not o[0]['late'], o)
gaps = [round(b['at'] - a['at'], 1) for a, b in zip(seen_b, seen_b[1:])]
H.ok('...its readings a second apart, none twice', len(seen_b) >= 12 and all(0.7 <= g <= 1.5 for g in gaps[2:]), (len(seen_b), gaps))
ra, rb = rows('a'), rows('b')
H.ok('one row a node in the database', sorted(ra) == ['load:' + H.NAME['a'], 'load:' + H.NAME['b']] and sorted(rb) == sorted(ra), (sorted(ra), sorted(rb)))
va = json.loads(ra.get('load:' + H.NAME['a']) or '{}')
vb = json.loads(ra.get('load:' + H.NAME['b']) or '{}')
H.ok('...a asked (its page), b not', va.get('asked') is True and vb.get('asked') is False, (va.get('asked'), vb.get('asked')))
H.ok('...small (a few seconds of readings)', len(ra.get('load:' + H.NAME['a'], '')) < 3000 and len(va.get('hist') or []) <= 12,
     len(ra.get('load:' + H.NAME['a'], '')))
# written every 5 s, not more
w = []
for _ in range(12):
    w.append(rows('a').get('load:' + H.NAME['b']))
    time.sleep(1)
changes = sum(1 for x, y in zip(w, w[1:]) if x != y)
H.ok('b\'s row changes about every 5 s (looked at a moment ago)', 1 <= changes <= 4, changes)

# the page gone: both stop within 45 s
time.sleep(45)
r1 = rows('a')
time.sleep(12)
r2 = rows('a')
H.ok('the page gone: no row written any more after 45 s', r1 == r2, [k for k in r2 if r1.get(k) != r2.get(k)])
st, d = H.call('b', '/api/load')
# A page that looks again (1.0.257): the other node's last numbers at once, not "does not answer"
# while it wakes up; its rows again within seconds.
o0 = (d.get('others') or [{}])[0]
H.ok('b\'s page looks again: a\'s last numbers at once, not said late while it wakes',
     st == 200 and not o0.get('late') and (o0.get('now') or {}).get('cpu') is not None, d.get('others'))
time.sleep(1)
before = rows('b').get('load:' + H.NAME['a'])
for _ in range(10):
    H.call('b', '/api/load')
    time.sleep(1)
H.ok('...and a writes its row again for b\'s page', rows('b').get('load:' + H.NAME['a']) != before)

H.ok('switched off', setp(False) == 200)
time.sleep(14)
H.ok('off: the rows taken away on both nodes', not rows('a') and not rows('b'), (sorted(rows('a')), sorted(rows('b'))))
ra = H.rad('a', 'nobody', 'x')
H.ok('RADIUS answers all along', ra is not None)
H.done()
