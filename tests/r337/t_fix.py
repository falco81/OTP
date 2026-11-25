"""t_fix.py - 1.0.337: an upgrade started on a node in maintenance takes it first; a realm renamed with
another directory; clients.conf's yes/true/on and netmask; a .totp file with a BOM in a ZIP.

    python3 t_fix.py VERSION
"""
import base64, importlib.util, io, json, os, shutil, sys, tempfile, time, zipfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.337'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r337_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx337', 'api_port': 29959}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 clients.conf
got = m.parse_clients_conf('''
client a { ipaddr = 10.0.0.1
  secret = s1
  require_message_authenticator = true }
client b { ipaddr = 10.0.0.2
  secret = s2
  require_message_authenticator = Yes }
client c { ipaddr = 10.0.0.3
  secret = s3
  require_message_authenticator = no }
client 10.1.0.0 {
  netmask = 24
  secret = s4 }
''')
by = {c['name']: c for c in got}
ok('true and Yes: must sign', by['a']['require_ma'] == 1 and by['b']['require_ma'] == 1, got)
ok('no: need not', by['c']['require_ma'] == 0)
ok('netmask: the network', by['10.1.0.0']['address'] == '10.1.0.0/24', by.get('10.1.0.0'))

# ==== 2 a BOM in a ZIP
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as z:
    z.writestr('bob.totp', '﻿JBSWY3DPEHPK3PXP\n" RATE_LIMIT 3 30\n" WINDOW_SIZE 3\n" DISALLOW_REUSE\n" TOTP_AUTH\n'.encode('utf-8'))
out = []
files = m.totp_files_in_zip(base64.b64encode(buf.getvalue()).decode(), 'x.zip', out)
ok('the BOM left out', files and not files[0]['text'].startswith('﻿') and files[0]['text'].startswith('JBSW'), (files, out))

# ==== 3 a realm renamed with another directory
for d in ('AD1', 'AD2'):
    st.directory_save({'name': d, 'hosts': 'dc.example', 'base': 'DC=example,DC=cz'}, 'test')
st.realm_save({'name': 'A', 'suffix': 'a.cz', 'directory': 'AD1', 'token_name': 'bare'}, 'test')
rid = [r for r in st.realms() if r['name'] == 'A'][0]['id']
try:
    st.realm_save({'id': rid, 'name': 'B', 'suffix': 'a.cz', 'directory': 'AD2', 'token_name': 'bare'}, 'test')
    e = None
except ValueError as x:
    e = x
ok('renamed with another directory: saved', e is None and [r['name'] for r in st.realms()] == ['B'], e)
try:
    st.realm_save({'name': 'C', 'suffix': 'c.cz', 'directory': 'AD1', 'token_name': 'bare'}, 'test')
    e = None
except ValueError as x:
    e = x
ok('another realm of names alone in another directory: still refused', e is not None and 'names alone' in str(e), e)

# ==== 4 the upgrade order
src = open(V + '/otp.py').read()
up = src[src.index("    order = sorted(n for n in names if n != me) + ([me] if me in names else [])"):][:600]
ok('the upgrade takes one in maintenance first', "order.sort(key=lambda n: not bool(maintenance_row(store, n).get('on')))" in up)
order = ['node2', 'node1']
st.set_meta('maint:node1', json.dumps({'on': True}))
order.sort(key=lambda n: not bool(m.maintenance_row(st, n).get('on')))
ok('node1 in maintenance: first', order == ['node1', 'node2'], order)
ok('totpcgi realms compared in any letters', "str(r.get('suffix')).lower() == suffix.lower()" in src)
print('ALL %d / %d' % (sum(R), len(R)))
