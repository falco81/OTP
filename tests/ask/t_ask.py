# Tests asked of every node (1.0.169): two daemons over one SQLite database;
# isemon, syslog, the proxy and a directory tried from each node, asked on
# node1. Usage (as root): python3 t_ask.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, socket, threading

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.169'
V = '/home/claude/build/out/otp-%s' % VER
TOP = tempfile.mkdtemp(prefix='otp-ask-')
UPORT = 36514
N = {}
for i, name in ((1, 'node1'), (2, 'node2')):
    d = os.path.join(TOP, name); os.makedirs(d + '/run'); os.makedirs(d + '/web')
    json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 36610 + 10 * i,
               'radius_acct_port': 36611 + 10 * i, 'api_port': 30590 + i, 'node_name': name, 'ha_mode': 'shared'},
              open(d + '/config.json', 'w'))
    N[name] = {'dir': d, 'api': 30590 + i, 'env': dict(os.environ, OTP_STATE=d, OTP_CONFIG=d + '/config.json', OTP_LOGDIR=d,
                                                       OTP_RUN=d + '/run', OTP_STAY_ROOT='1', OTP_ALERTS_EVERY='3')}
os.environ.update(N['node1']['env']); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-169!', must_change=0)
st.directory_save({'name': 'AD', 'hosts': '127.0.0.1:1', 'tls': 'ldaps', 'port': 1, 'base': 'DC=example,DC=cz',
                   'bind_dn': 'otp@example.cz', 'bind_pw': 'x', 'timeout_s': 2})
for f in ('otp.db', 'secrets.key'):
    os.symlink(os.path.join(N['node1']['dir'], f), os.path.join(N['node2']['dir'], f))
GOT = []


def rx():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.1', UPORT))
    while True:
        GOT.append(s.recv(65535).decode('utf-8', 'replace'))


threading.Thread(target=rx, daemon=True).start()
procs = [subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=N[n]['env'], stdout=open(N[n]['dir'] + '/d.out', 'w'),
                          stderr=subprocess.STDOUT) for n in N]
atexit.register(lambda: [p.terminate() for p in procs])
time.sleep(8)
TOK = {n: open(N[n]['dir'] + '/run/api-token').read().strip() for n in N}


def call(node, path, body=None, sess=None):
    h = {'X-Otp-Token': TOK[node], 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % N[node]['api'] + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


def until(fn, secs=40):
    end = time.time() + secs
    while time.time() < end:
        g = fn()
        if g:
            return g
        time.sleep(0.5)
    return None


S = call('node1', '/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-169!'})[1]['token']


def ask(path, body):
    c, x = call('node1', path, body, S)
    if c != 200:
        return c, x, {}
    res = until(lambda: (lambda r: r if all(r.get(n) for n in x['nodes']) else None)(
        call('node1', path, {'action': 'result', 'id': x['id']}, S)[1].get('nodes') or {}))
    return c, x, res or {}


call('node1', '/api/settings', {'settings': {'isemon': 1, 'isemon_targets': '127.0.0.1:%d/udp' % UPORT,
                                             'siem': 1, 'siem_targets': 'udp://127.0.0.1:%d' % UPORT}}, S)
time.sleep(7)
c, x, res = ask('/api/proxy', {'action': 'try', 'url': 'http://127.0.0.1:%d/' % N['node2']['api']})
ok('Try it on both nodes: %s' % {n: (r or {}).get('mode') for n, r in res.items()}, x.get('nodes') == ['node1', 'node2'] and
   all((res.get(n) or {}).get('node') == n and res[n]['mode'] == 'direct' for n in N))
c, x, res = ask('/api/isemon', {'action': 'test', 'node': 'node2'})
ok('isemon: a test line from node2, asked on node1 (%s)' % {n: (r or {}).get('ok') for n, r in res.items()},
   x.get('nodes') == ['node2'] and (res.get('node2') or {}).get('ok') and res.get('node1') is None)
ok('... it arrived, from node2', until(lambda: [l for l in GOT if 'a test from otp' in l and 'on node2' in l], 10))
c, x, res = ask('/api/siem', {'action': 'test'})
ok('syslog: a test line from both (%s)' % {n: (r or {}).get('test') for n, r in res.items()},
   all((res.get(n) or {}).get('ok') for n in N))
c, v = call('node1', '/api/isemon', None, S)
time.sleep(4)
c, v = call('node1', '/api/isemon', None, S)
ok('isemon: both nodes shown (%s)' % [(n['node'], n.get('on'), bool(n.get('at'))) for n in v.get('nodes', [])],
   [n['node'] for n in v.get('nodes', [])] == ['node1', 'node2'] and all(n.get('on') for n in v['nodes']))
c, x, res = ask('/api/directories', {'action': 'check_all', 'name': 'AD'})
ok('the directory checked from both nodes (%s)' % {n: (r or {}).get('ok') for n, r in res.items()},
   all(res.get(n) and res[n].get('check') and res[n]['ok'] is False for n in N))
c, x, res = ask('/api/directories', {'action': 'check_all', 'name': 'nope'})
ok('... a directory there is not: 404 (%s)' % c, c == 404)
c, v = call('node1', '/api/siem', None, S)
ok('syslog: both nodes shown with what each sent (%s)' % [(n['node'], sum((n.get('sent') or {}).values())) for n in v.get('nodes', [])],
   all(sum((n.get('sent') or {}).values()) >= 1 for n in v.get('nodes', [])) and len(v['nodes']) == 2)
print('ALL %d / %d' % (sum(R), len(R)))
