"""The HA row of the performance meter (one row a node), two nodes in one process with a dict for meta."""
import os, sys, json, time, threading, types
src = open(sys.argv[1]).read().replace("@route('GET', '/api/load')", "")
R = []


def ok(n, c, m=''):
    R.append(c); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


class DB:
    def __init__(self, meta):
        self.meta, self.reads = meta, 0

    def rows(self, sql, args=()):
        self.reads += 1
        pre = sql.split("LIKE '")[1].split('%')[0]
        return [{'k': k, 'v': v} for k, v in sorted(self.meta.items()) if k.startswith(pre)]

    def run(self, sql, args=()):
        for a in args:
            self.meta.pop(a, None)


class Store:
    def __init__(self, meta):
        self.db, self.writes = DB(meta), 0

    def set_meta(self, k, v):
        self.writes += 1
        self.db.meta[k] = str(v)


META, CLOCK = {}, [1000.0]


def node(name, peers):
    g = {'__name__': 'x' + name, 'CONFIG': {'perf_meter': True, 'ha_mode': 'shared'}, 'node_name': lambda: name,
         'ha_nodes': lambda store: [{'name': n, 'me': n == name} for n in [name] + peers],
         'fnum': float, 'log_sparing': lambda *a, **k: None, 'ApiError': Exception}
    exec('import os, re, json, time, threading\n' + src, g)
    g['time'] = types.SimpleNamespace(time=time.time, monotonic=lambda: CLOCK[0], sleep=time.sleep)
    return g


def readings(g, n=3):
    """the sampler, n readings a second apart (real time: /proc is read)"""
    for _ in range(n):
        g['load_sample']()
        time.sleep(1.05)


a, b = node('nodea', ['nodeb']), node('nodeb', ['nodea'])
sa, sb = Store(META), Store(META)

a['CONFIG']['perf_meter'] = b['CONFIG']['perf_meter'] = False
b['load_ha_tick'](sb)
ok('off: nothing read or written', sb.db.reads == 0 and sb.writes == 0 and not META)
a['CONFIG']['perf_meter'] = b['CONFIG']['perf_meter'] = True
b['CONFIG']['ha_mode'] = ''
b['load_ha_tick'](sb)
ok('standalone: nothing read or written', sb.db.reads == 0 and sb.writes == 0)
b['CONFIG']['ha_mode'] = 'shared'

b['load_ha_tick'](sb)
ok('nobody looking: b writes nothing', sb.writes == 0 and not META, META)
a['load_ha_tick'](sa)
ok('...nor a', sa.writes == 0 and not META)

# a page on a
a['load_ask']()
readings(a)
a['load_ha_tick'](sa)
row = json.loads(META.get('load:nodea', '{}'))
ok('a writes its row: asked, its numbers, its readings of a second each', row.get('asked') is True
   and row.get('now', {}).get('mem_total') and len(row.get('hist') or []) >= 2, row)
ok('one row for the node', [k for k in META if k.startswith('load:')] == ['load:nodea'])
CLOCK[0] += 5
b['load_ha_tick'](sb)
ok('b: the row seen come: b samples now (kept going by the other page)', b['load_looked'](), b['LOAD_LOOK'])
readings(b)
CLOCK[0] += 5
b['load_ha_tick'](sb)
rb = json.loads(META.get('load:nodeb', '{}'))
ok('b writes its row, not asked (its writing keeps nobody going)', 'load:nodeb' in META and rb.get('asked') is False, rb)
CLOCK[0] += 1
a['load_ha_tick'](sa)
o = a['load_others'](sa, {})
ok('a: b heard, its readings', o and o[0]['node'] == 'nodeb' and not o[0]['late'] and len(o[0]['hist']) >= 2, o)
o2 = a['load_others'](sa, {'nodeb': o[0]['hist'][-1]['at']})
ok('a: since b\'s last reading - nothing more', o2[0]['hist'] == [], o2)

# a's page closed: a stops after LOAD_LOOK_S, b after LOAD_WANTED_S
CLOCK[0] += 11
na = META['load:nodea']
a['load_ha_tick'](sa)
ok('a: page closed - its row no longer written', META['load:nodea'] == na)
for _ in range(10):
    CLOCK[0] += 5
    time.sleep(0.01)
    b['load_ha_tick'](sb)
nb = META['load:nodeb']
CLOCK[0] += 5
b['load_ha_tick'](sb)
ok('b stops within 45 s of the page closed (22 s after a\'s last change)', META['load:nodeb'] == nb and not b['load_looked']())
ok('a: b said late', a['load_others'](sa, {})[0]['late'])

# switched off: each node takes its row away
a['CONFIG']['perf_meter'] = b['CONFIG']['perf_meter'] = False
a['load_ha_tick'](sa)
b['load_ha_tick'](sb)
ok('off: the rows taken away', not [k for k in META if k.startswith('load:')], META)
r0 = sb.db.reads
b['load_ha_tick'](sb)
ok('off again: nothing read', sb.db.reads == r0)
print('ALL %d / %d' % (sum(R), len(R)))
