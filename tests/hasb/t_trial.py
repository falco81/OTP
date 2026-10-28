"""A network trial on node B of the light sandbox, not kept: it must come back
whole - its NetworkManager profile, host name, /etc/hosts, its settings and
certificate, the other node's pg_hba/subscription/ha_peer, replication and the
link's TLS (1.0.140). Run with the environment of node B (env.sh b).
    python3 -I t_trial.py VERSION [keep] [ADDR/PREFIX HOSTNAME]"""
import json, subprocess, sys, time
V = sys.argv[1]; KEEP = 'keep' in sys.argv[2:]
REST = [x for x in sys.argv[2:] if x != 'keep']
ADDR, HOST = (REST + ['10.99.0.3/24', 'nodeb-new.example.test'][len(REST):])[:2]
S = open('/home/claude/work/hasb/current').read().strip()
sys.argv = ['x']
sys.path.insert(0, '/home/claude/build/out/otp-%s' % V)
import otp
otp.load_config()
store = otp.Storage(otp.open_db()); otp.load_config(saved=store.settings_saved())
otp.HA_STORE['store'] = store

def psql(port, sql, db=None):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-XAtq'] +
                          (['-d', db] if db else []) + ['-c', sql],
                          capture_output=True, text=True).stdout.strip()

def hba(c):
    return [l for l in open('/etc/postgresql/16/%s/pg_hba.conf' % c).read().splitlines()
            if l.split()[:1] in (['host'], ['hostssl']) and otp.CONFIG['db_name'] in l]

def state():
    db = otp.CONFIG['db_name']
    out = {
        'B profile': open(S + '/b/fakenm/profiles/System eth0.nmconnection').read(),
        'B hostname': open(S + '/b/fakenm/hostname').read(),
        'B hosts': open(S + '/b/hosts').read(),
        'B config.json': {k: v for k, v in json.load(open(S + '/b/config.json')).items()
                          if k not in ('node_name',)},
        'B settings': {k: store.settings_saved().get(k) for k in ('radius_bind', 'mail_helo')},
        'B web cert': store.get_meta('web:tls:nodeb') or '',
        'A config.json': json.load(open(S + '/a/config.json')),
        'A pg_hba (otp lines)': hba('main'),
        'B pg_hba (otp lines)': hba('second'),
        'A subscription': psql(5432, "SELECT subconninfo FROM pg_subscription", db).split(' password=')[0],
        'B subscription': psql(5433, "SELECT subconninfo FROM pg_subscription", db).split(' password=')[0],
    }
    return out

def health():
    rep = otp.ha_repl_state(store)
    ok, said = otp.net_hatls_ok(store)
    inc = rep.get('incoming') or []; outg = rep.get('outgoing') or []
    return {'replication in': [(r.get('enabled'), r.get('running')) for r in inc],
            'replication out': [r.get('active') for r in outg], 'tls': (ok, said)}

before = state()
print('before:', json.dumps(health(), default=str))
otp.net_publish(store)
now = otp.net_node_now(store, 'nodeb')
want = {'con': 'System eth0', 'ipv4': {'addr': ADDR, 'gw': '10.99.0.254',
                                       'dns': ['10.99.0.53'], 'search': ['example.test']},
        'ipv6': {'on': False}, 'hostname': HOST, 'vip_elsewhere': True}
ask = otp.net_ask(store, 'nodeb', want, 'test')
print(ask['want']['plan'])
ids = {ask['id']}
power = S + '/b/power'
seen = len(open(power).read().splitlines())
last = None; t0 = time.time(); kept = False
while time.time() - t0 < 1500:
    lines = open(power).read().splitlines()
    if len(lines) > seen:
        seen = len(lines); time.sleep(9)
        print(time.strftime('%H:%M:%S'), '** reboot of nodeb (simulated)', flush=True)
        subprocess.run(['bash', '/home/claude/work/hasb/start.sh', 'b', V, 'reboot'])
    j = otp._meta_json(store, 'net:job:nodeb') or {}
    if j.get('id') not in ids and not (j.get('rollback') and j.get('state') not in (None,)
                                       and any(i in ids for i in [j.get('from_job')])):
        # the job going back has an id of its own: taken once ours is going back
        if j.get('rollback') and last and last[1] == 'going back':
            ids.add(j.get('id'))
        else:
            time.sleep(2)
            continue
    cur = (j.get('id'), j.get('state'), (j.get('steps') or [{}])[-1].get('what', '')[:150])
    if cur != last:
        print(time.strftime('%H:%M:%S'), *cur, flush=True); last = cur
    if j.get('state') == 'trial' and KEEP and not kept:
        print(otp.net_trial_answer(store, 'nodeb', 'keep', 'test')); kept = True
    if j.get('state') == 'done' and (j.get('rollback') or KEEP):
        break
    if j.get('state') == 'failed':
        break
    time.sleep(3)
print()
for st in (otp._meta_json(store, 'net:job:nodeb') or {}).get('steps') or []:
    print('   %s %s' % ('ok ' if st['ok'] else 'BAD', st['what'][:220]))
time.sleep(5)
after = state()
print('\nafter:', json.dumps(health(), default=str))
bad = 0
for k in before:
    same = before[k] == after[k]
    if KEEP:
        print('%-22s %s' % (k, 'same' if same else 'changed'))
        continue
    print('%-22s %s' % (k, 'as before' if same else 'DIFFERENT'))
    if not same:
        bad += 1
        print('     before:', json.dumps(before[k])[:600]); print('     after: ', json.dumps(after[k])[:600])
print('RESULT:', 'everything as before' if not bad and not KEEP else '%d different' % bad)
