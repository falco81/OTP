# The .totp export locked with a passphrase, or not (1.0.167): a ZIP with
# AES-256 that 7-Zip opens and otp reads back; one token alone; not locked
# only when asked for. Usage (as root): python3 t_totpzip.py VERSION
import os, sys, json, time, subprocess, urllib.request, tempfile, atexit, base64, io, zipfile

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.167'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-zip-'); os.makedirs(D + '/run')
APORT = 30291
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': 35910, 'radius_acct_port': 35911,
           'api_port': APORT, 'node_name': 'otp1'}, open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-167!', must_change=0)
st.save_setting('admin_show_key', 1, 'test')
tk = otp.Tokens(st)
for n in ('anna@x.cz', 'bob@x.cz', 'eva@x.cz'):
    tk.enroll(n, 'test')
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env, stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(d.terminate)
time.sleep(6)
TOK = open(D + '/run/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w, flush=True)


S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-167!'})[1]['token']
E = lambda b: call('/api/tokens/export', b, S)
c, x = E({})
ok('locked unless asked otherwise: no passphrase refused (%s)' % c, c == 400)
c, x = E({'passphrase': 'short'})
ok('a short passphrase refused (%s)' % c, c == 400)
c, x = call('/api/tokens/export?q=', None, S)
ok('the old GET export is gone (%s)' % c, c in (404, 405))
c, x = E({'passphrase': 'Tajne-heslo-167'})
ok('locked: %s %s %s' % (c, x.get('name'), x.get('count')), c == 200 and x['locked'] and x['count'] == 3 and x['name'].endswith('.zip'))
raw = base64.b64decode(x['file'])
z = zipfile.ZipFile(io.BytesIO(raw))
ok('... every entry AES (method 99, locked): %s' % [(i.filename, i.compress_type) for i in z.infolist()],
   all(i.compress_type == 99 and i.flag_bits & 1 for i in z.infolist()) and len(z.infolist()) == 4)
ok('... no key readable in it', all(otp.totp_file_text(st.token(n)).split('\n')[0].encode() not in raw for n in ('anna@x.cz', 'bob@x.cz')))
open(D + '/l.zip', 'wb').write(raw)
os.makedirs(D + '/x')
r = subprocess.run(['7z', 'x', '-pTajne-heslo-167', '-o' + D + '/x', D + '/l.zip'], capture_output=True, text=True)
ok('7-Zip opens it with the passphrase: %s' % sorted(os.listdir(D + '/x')), r.returncode == 0 and 'anna@x.cz.totp' in os.listdir(D + '/x'))
ok('... the file as totpcgi keeps it', open(D + '/x/anna@x.cz.totp').read() == otp.totp_file_text(st.token('anna@x.cz')))
r = subprocess.run(['7z', 't', '-pwrong-one', D + '/l.zip'], capture_output=True, text=True)
ok('... and not with another', r.returncode != 0)
c, x2 = E({'lock': False})
z2 = zipfile.ZipFile(io.BytesIO(base64.b64decode(x2['file'])))
ok('not locked, as asked: a plain ZIP (%s)' % c, c == 200 and not x2['locked'] and z2.read('bob@x.cz.totp').decode() == otp.totp_file_text(st.token('bob@x.cz')))
c, x3 = E({'name': 'eva@x.cz', 'passphrase': 'Tajne-heslo-167'})
z3 = zipfile.ZipFile(io.BytesIO(base64.b64decode(x3['file'])))
ok('one token, locked: a ZIP with its file (%s)' % x3.get('name'), c == 200 and x3['name'] == 'eva@x.cz.zip' and [i.filename for i in z3.infolist()] == ['eva@x.cz.totp'])
c, x4 = E({'name': 'eva@x.cz', 'lock': False})
ok('one token, not locked: the .totp itself (%s)' % x4.get('name'), c == 200 and x4['name'] == 'eva@x.cz.totp'
   and base64.b64decode(x4['file']).decode() == otp.totp_file_text(st.token('eva@x.cz')))
ev = json.dumps(call('/api/events?limit=50', None, S)[1])
ok('each export in the events, locked or NOT LOCKED', 'locked with a passphrase' in ev and 'NOT LOCKED' in ev)
# Read back: another server's worth, the tokens gone here first.
for n in ('anna@x.cz', 'bob@x.cz', 'eva@x.cz'):
    st.db.run('DELETE FROM tokens WHERE name = ?', (n,))
f = [{'name': 'l.zip', 'zip': x['file']}]
c, y = call('/api/token/import', {'files': f}, S)
ok('a locked ZIP read back without its passphrase: asked for it (%s %s)' % (c, y.get('error')), c == 423)
c, y = call('/api/token/import', {'files': f, 'passphrase': 'nope-nope-nope'}, S)
ok('... with another: refused (%s)' % c, c == 423)
c, y = call('/api/token/import', {'files': f, 'passphrase': 'Tajne-heslo-167'}, S)
ok('... with its own: imported (%s)' % [r['said'][:20] for r in y.get('done', [])], c == 200 and len([r for r in y['done'] if r['said'].startswith('imported')]) == 3)
# A ZIP 7-Zip locked, read too.
subprocess.run('cd %s/x && 7z a -tzip -mem=AES256 -pSeven-Seven-7 ../s.zip eva@x.cz.totp >/dev/null' % D, shell=True)
st.db.run('DELETE FROM tokens WHERE name = ?', ('eva@x.cz',))
c, y = call('/api/token/import', {'files': [{'name': 's.zip', 'zip': base64.b64encode(open(D + '/s.zip', 'rb').read()).decode()}],
                                  'passphrase': 'Seven-Seven-7'}, S)
ok('a ZIP 7-Zip locked with AES-256 read: %s' % y.get('done'), c == 200 and y['done'] and y['done'][0]['said'].startswith('imported'))
# The whole backup (1.0.168): locked, or not when asked; high security takes "not locked" away.
B = lambda b: call('/api/tokens/backup', b, S)
c, x = B({})
ok('backup: no passphrase refused (%s)' % c, c == 400)
c, x = B({'lock': False})
ok('backup not locked, as asked: plain JSON with the tokens (%s)' % c, c == 200 and not x['locked'] and json.loads(x['file']).get('tokens'))
c, y = call('/api/token/import', {'files': [{'name': 'b.json', 'text': x['file']}], 'action': 'peek'}, S)
ok('... read back without a passphrase (%s)' % c, c == 200 and len(y['backup']['tokens']) == 3)
c, x = B({'passphrase': 'Tajne-heslo-168'})
ok('backup locked (%s)' % c, c == 200 and x['locked'] and 'locked' in json.loads(x['file']))
st.set_meta('web:access', json.dumps({'admin': {'any': False, 'from': ['10.0.0.0/8']}}))
call('/api/settings', {'settings': {'radius_guard': 1}}, S)
# The rest that stands against it made exceptions (1.0.169) - but the exports.
for r in call('/api/hisec', None, S)[1].get('block', []):
    if r['rule'] != 'export:unlocked':
        call('/api/hisec', {'action': 'waive', 'rule': r['rule'], 'on': True}, S)
c, _ = call('/api/settings', {'settings': {'high_security': 1}}, S)
ok('high security on: %s' % c, c == 200)
time.sleep(1.5)
c1, _ = B({'lock': False}); c2, _ = E({'lock': False}); c3, _ = E({'name': 'eva@x.cz', 'lock': False})
ok('... every export not locked refused (%s %s %s)' % (c1, c2, c3), c1 == c2 == c3 == 403)
c1, _ = B({'passphrase': 'Tajne-heslo-168'}); c2, _ = E({'passphrase': 'Tajne-heslo-168'})
ok('... locked ones still go (%s %s)' % (c1, c2), c1 == c2 == 200)
st_ = call('/api/status', None, S)[1]
ok('... and the page is told (%s)' % st_.get('high_security'), st_.get('high_security') is True)
print('ALL %d / %d' % (sum(R), len(R)))
