"""t_fix.py - 1.0.314: the cap of wrong directory passwords counted as the directory counts them - its
counter goes back to 0 only once the time has gone by since the LAST wrong password. The parts loaded as a
module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, atexit
_OUTV = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else '1.0.314'
BUILD = '/home/claude/build'
ASSETS = BUILD + '/out/otp-%s/web/assets/admin.js' % _OUTV
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r314_')
atexit.register(lambda: shutil.rmtree(TOP, True))
cat = [l for l in open(BUILD + '/build.sh').read().splitlines() if l.startswith('cat parts/00_head.py')][0]
parts = re.findall(r'parts/\S+\.py', cat)
with open(TOP + '/otp.py', 'w', encoding='utf-8') as f:
    for p in parts:
        f.write(open(os.path.join(BUILD, p), encoding='utf-8').read())
        f.write('\n')
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx314', 'api_port': 29944}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run',
                  OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', TOP + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db())
st.db.make_tables()
m.sealing_key(make=True)




me = m.node_name()
# ==== 1 the count that went up
m.REPL_ERRS.update(n=None, at=0.0, by='')
inc = lambda a, s: {'incoming': [{'name': 'otp_from_b', 'apply_errors': a, 'sync_errors': s}]}
g = m.repl_errors_seen(inc(4, 0), 1000)
ok('1 the first look: a baseline, nothing said', g['n'] == 4 and g['at'] == 0.0, g)
g = m.repl_errors_seen(inc(4, 0), 1060)
ok('1 the same count: nothing', g['at'] == 0.0, g)
g = m.repl_errors_seen(inc(5, 1), 1120)
ok('1 up: when, and which', g['at'] == 1120 and 'otp_from_b (5 apply, 1 sync)' in g['by'], g)
g = m.repl_errors_seen(inc(0, 0), 1180)
ok('1 down (the statistics reset): a new baseline, the time kept', g['n'] == 0 and g['at'] == 1120, g)
g = m.repl_errors_seen({'incoming': []}, 1240)
ok('1 no subscription: left as it was', g['n'] == 0, g)
# ==== 2 the alert
m.ha_repl_state = lambda store: {'healthy': True, 'outgoing': [], 'incoming': []}
m.in_cluster = lambda store: False
m.CONFIG.update(ha_mode='replicated', alerts_repl_behind_mb=50, alerts_db=1)
now = time.time()


def health(row):
    st.set_meta('host:health:' + me, json.dumps(dict({'at': now, 'disks': [], 'radius': [1]}, **row)))


health({'repl_errors': {'n': 6, 'at': now - 60, 'by': 'otp_from_b (5 apply, 1 sync)'}})
p = m.alert_problems(st, 'en')
k = 'repl:errors:' + me
ok('2 errors a minute ago: warned', k in p and p[k]['level'] == 'warn', sorted(p))
ok('2 which, and where to look', k in p and 'otp_from_b (5 apply, 1 sync)' in p[k]['said'] and 'High availability' in p[k]['said'], p.get(k))
pc = m.alert_problems(st, 'cs')
ok('2 in Czech too', k in pc and 'hlásí chyby' in pc[k]['title'], pc.get(k))
health({'repl_errors': {'n': 6, 'at': now - 3600, 'by': 'x'}})
ok('2 an hour ago: nothing', k not in m.alert_problems(st, 'en'))
health({'repl_errors': {'n': 6, 'at': now - 60, 'by': 'x'}})
m.CONFIG['alerts_repl_behind_mb'] = 0
ok('2 the setting 0: never', k not in m.alert_problems(st, 'en'))
m.CONFIG['alerts_repl_behind_mb'] = 50
m.CONFIG['ha_mode'] = ''
ok('2 not replicated: never', k not in m.alert_problems(st, 'en'))
m.CONFIG['ha_mode'] = 'replicated'
# ==== 3 disks
m.CONFIG['alerts_disk_pct'] = 85
health({'disks': [{'path': '/var', 'pct': 40.0, 'inodes': 97.0, 'free': 10 << 30}]})
p = m.alert_problems(st, 'en')
k = 'disk:%s:/var' % me
ok('3 out of inodes: warned as bad (97 %)', k in p and p[k]['level'] == 'bad', p.get(k))
ok('3 said as inodes', k in p and 'Inodes (files): 97.0 % used' in p[k]['said'] and 'df -i' in p[k]['said'], p.get(k))
health({'disks': [{'path': '/var', 'pct': 90.0, 'inodes': 10.0, 'free': 1 << 30}]})
p = m.alert_problems(st, 'en')
ok('3 full of data: as before, no word of inodes', k in p and p[k]['level'] == 'warn' and 'Inodes' not in p[k]['said'], p.get(k))
health({'disks': [{'path': '/var', 'pct': 50.0, 'inodes': 50.0, 'free': 1 << 30}]})
ok('3 neither: nothing', k not in m.alert_problems(st, 'en'))
print('ALL %d / %d' % (sum(R), len(R)))
