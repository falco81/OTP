# t_zabbix.py VERSION [TEMPLATE] - 1.0.281: the Zabbix 7.0 template "otp by SNMP" checked without a Zabbix:
# - every tag is one Zabbix 7.0's own import validator knows (C70XmlValidator.php of the 7.0 source, read);
# - UUIDs of 32 hex, each once; item keys and names each once; value maps used are there;
# - every key a trigger, a graph or a widget names is an item (or an item prototype of its rule); every
#   dependency is a trigger there; every graph and graph prototype a widget names is there; every name
#   pattern of a widget finds an item;
# - every OID asked is one of OTP-MIB (deploy/OTP-MIB.txt, net-snmp's snmptranslate); a walk holds every
#   column its rule and prototypes read;
# - each page of the dashboard: 72 columns, no widget over another.
import os, re, subprocess, sys, fnmatch
import yaml
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.281'
OUT = os.environ.get('OTP_OUT') or '/home/claude/build/out/otp-%s' % V
TPL = sys.argv[2] if len(sys.argv) > 2 else OUT + '/deploy/zabbix/otp_by_snmp_zabbix7.yaml'
MIB = OUT + '/deploy/OTP-MIB.txt'
VAL = '/home/claude/zabbix-src/ui/include/classes/import/validators/C70XmlValidator.php'
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]))


d = yaml.safe_load(open(TPL))
z = d['zabbix_export']
ok('version 7.0', z.get('version') == '7.0', z.get('version'))
t = z['templates'][0]
T = t['template']

# the tags Zabbix 7.0 knows
if os.path.exists(VAL):
    known = set(re.findall(r"'([a-z_0-9]+)'\s*=>\s*\[", open(VAL).read()))
    bad = set()

    def walk(o, path=''):
        if isinstance(o, dict):
            for k, v in o.items():
                if k not in known:
                    bad.add('%s/%s' % (path, k))
                walk(v, k)
        elif isinstance(o, list):
            for x in o:
                walk(x, path)
    walk(d['zabbix_export'], 'zabbix_export')
    ok('every tag is one Zabbix 7.0\'s import validator knows', not bad, sorted(bad)[:10])
else:
    ok('the validator of Zabbix 7.0 is there to read (git clone of release/7.0)', False, VAL)

uuids = []


def collect(o):
    if isinstance(o, dict):
        if 'uuid' in o:
            uuids.append(o['uuid'])
        for v in o.values():
            collect(v)
    elif isinstance(o, list):
        for x in o:
            collect(x)


collect(d)
ok('UUIDs: 32 hex, each once (%d)' % len(uuids), all(re.match(r'^[0-9a-f]{32}$', u) for u in uuids) and
   len(set(uuids)) == len(uuids))
items = t.get('items') or []
keys = [i['key'] for i in items]
ok('item keys each once (%d)' % len(keys), len(set(keys)) == len(keys), [k for k in keys if keys.count(k) > 1][:5])
names = [i['name'] for i in items]
ok('item names each once', len(set(names)) == len(names), [n for n in names if names.count(n) > 1][:5])
rules = t.get('discovery_rules') or []
protos = {r['key']: r.get('item_prototypes') or [] for r in rules}
allkeys = set(keys) | {p['key'] for ps in protos.values() for p in ps}
pnames = [p['name'] for ps in protos.values() for p in ps]
ok('prototype names each once', len(set(pnames)) == len(pnames))
vms = {v['name'] for v in t.get('valuemaps') or []}
used_vm = {i['valuemap']['name'] for i in items + [p for ps in protos.values() for p in ps] if i.get('valuemap')}
ok('value maps used are there', used_vm <= vms, used_vm - vms)


def refs(expr):
    return re.findall(r'/%s/([^,)\[]+(?:\[[^\]]*\])?)' % re.escape(T), expr)


trig_all = []
for i in items:
    for tr in i.get('triggers') or []:
        trig_all.append(tr)
trig_all += z.get('triggers') or []
ptrig = [tr for ps in protos.values() for p in ps for tr in p.get('trigger_prototypes') or []]
missing = [k for tr in trig_all + ptrig for k in refs(tr['expression']) if k not in allkeys]
ok('every key a trigger names is an item (%d triggers, %d prototypes)' % (len(trig_all), len(ptrig)), not missing, missing[:5])
byname = {(tr['name'], tr['expression']) for tr in trig_all + ptrig}
dbad = [dp for tr in trig_all + ptrig for dp in tr.get('dependencies') or [] if (dp['name'], dp['expression']) not in byname]
ok('every dependency is a trigger there', not dbad, dbad[:3])
for tr in trig_all:
    for k in refs(tr['expression']):
        if k not in keys:
            ok('a trigger of the template names a prototype: %s' % k, False)
graphs = {g['name'] for g in z.get('graphs') or []}
gproto = {g['name'] for r in rules for g in r.get('graph_prototypes') or []}
gmiss = [gi['item']['key'] for g in (z.get('graphs') or []) + [g for r in rules for g in r.get('graph_prototypes') or []]
         for gi in g['graph_items'] if gi['item']['key'] not in allkeys]
ok('every key a graph names is an item (%d graphs, %d prototypes)' % (len(graphs), len(gproto)), not gmiss, gmiss)
allnames = names + pnames
wbad, pages = [], 0
for db in t.get('dashboards') or []:
    for pg in db['pages']:
        pages += 1
        cells = {}
        for w in pg['widgets']:
            x, y, wd, h = int(w.get('x', 0)), int(w.get('y', 0)), int(w['width']), int(w['height'])
            if x + wd > 72:
                wbad.append('%s: past 72 columns' % w.get('name'))
            for cx in range(x, x + wd):
                for cy in range(y, y + h):
                    if (cx, cy) in cells:
                        wbad.append('%s over %s' % (w.get('name'), cells[(cx, cy)]))
                        break
                    cells[(cx, cy)] = w.get('name')
            for fl in w['fields']:
                v = fl['value']
                if fl['type'] == 'ITEM' and v['key'] not in keys:
                    wbad.append('%s: no item %s' % (w.get('name'), v['key']))
                if fl['type'] == 'GRAPH' and v['name'] not in graphs:
                    wbad.append('%s: no graph %s' % (w.get('name'), v['name']))
                if fl['type'] == 'GRAPH_PROTOTYPE' and v['name'] not in gproto:
                    wbad.append('%s: no graph prototype %s' % (w.get('name'), v['name']))
                if re.match(r'^thresholds\.\d+\.threshold$', fl['name']) and not re.match(r'^-?\d+(\.\d+)?[KMGTsmhdw]?$', str(v)):
                    wbad.append('%s: a threshold is no number (%s) - Zabbix takes no macro there' % (w.get('name'), v))
                if fl['type'] == 'STRING' and re.match(r'^(ds\.\d+\.items\.\d+|items\.\d+)$', fl['name']):
                    if not any(fnmatch.fnmatchcase(n, v) for n in allnames):
                        wbad.append('%s: the pattern %s finds no item' % (w.get('name'), v))
ok('the dashboard: %d pages, 72 columns, nothing over anything, everything named is there' % pages, not wbad, wbad[:6])
refs_ = [fl['value'] for db in t.get('dashboards') or [] for pg in db['pages'] for w in pg['widgets']
         for fl in w['fields'] if fl['name'] == 'reference']
ok('the references of the widgets each once', len(set(refs_)) == len(refs_))

# the OIDs: in OTP-MIB, the walks hold their columns
oids = set()
for i in items:
    m = re.match(r'^get\[(.+)\]$', i.get('snmp_oid') or '')
    if m:
        oids.add(m.group(1))
mibdirs = '+%s:/var/lib/mibs/ietf' % os.path.dirname(MIB)
tmp = '/tmp/claude-0/zbx-mib'
os.makedirs(tmp, exist_ok=True)
open(tmp + '/OTP-MIB', 'w').write(open(MIB).read())
unknown = []
for o in sorted(oids):
    if o.startswith('1.3.6.1.2.1.1.'):
        continue
    got = subprocess.run(['snmptranslate', '-M', '+%s:/var/lib/mibs/ietf' % tmp, '-m', '+OTP-MIB', '-Ov', '-OS',
                          '.' + o.rsplit('.', 1)[0]], capture_output=True, text=True)
    name = subprocess.run(['snmptranslate', '-M', '+%s:/var/lib/mibs/ietf' % tmp, '-m', '+OTP-MIB', '.' + o.rsplit('.', 1)[0]],
                          capture_output=True, text=True).stdout.strip()
    if not name.startswith('OTP-MIB::otp') or '.' in name.split('::')[1]:
        unknown.append((o, name))
ok('every OID asked is an object of OTP-MIB (%d)' % len(oids), not unknown, unknown[:5])
wmiss = []
for r in rules:
    master = next(i for i in items if i['key'] == r['master_item']['key'])
    walked = re.match(r'^walk\[(.+)\]$', master['snmp_oid']).group(1).split(',')
    want = [p for p in r['preprocessing'][0]['parameters'][1::3]]
    for p in protos[r['key']]:
        want.append(p['preprocessing'][0]['parameters'][0].replace('.{#SNMPINDEX}', ''))
    for o in want:
        if o not in walked:
            wmiss.append((r['key'], o))
    for o in walked:
        name = subprocess.run(['snmptranslate', '-M', '+%s:/var/lib/mibs/ietf' % tmp, '-m', '+OTP-MIB', '.' + o],
                              capture_output=True, text=True).stdout.strip()
        if not name.startswith('OTP-MIB::otp'):
            wmiss.append((r['key'], o, name))
ok('each walk holds the columns of its rule and prototypes, each a column of OTP-MIB (%d rules)' % len(rules), not wmiss, wmiss[:4])
print('ALL %d / %d' % (sum(R), len(R)))
