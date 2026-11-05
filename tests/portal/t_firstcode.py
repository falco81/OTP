# t_firstcode.py VERSION - a one-time code before the first token on the enrolment pages (1.0.228):
# off is as until now; on, somebody with no token signs in with the directory password, a code goes by
# SMS or mail to what the directory has, and until it is typed the sign-in may do nothing else.
# Starts its own mock AD, SMTP sink, SMS spool and daemon (SQLite).
import os, sys, json, time, subprocess, urllib.request, tempfile, base64, atexit, re, glob, socketserver, threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.228'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix='otp-fc-'); run = D + '/run'; os.makedirs(run)
SPOOL = D + '/sms'; os.makedirs(SPOOL)
LPORT, RPORT, APORT, MPORT = 23989, 31932, 29891, 22525
MAILS = []


class Sink(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda t: self.wfile.write((t + '\r\n').encode())
        w('220 sink'); data = False; buf = []
        while True:
            line = self.rfile.readline()
            if not line:
                break
            s = line.decode('utf-8', 'replace').rstrip('\r\n')
            if data:
                if s == '.':
                    data = False; MAILS.append('\n'.join(buf)); buf = []; w('250 queued')
                else:
                    buf.append(s)
                continue
            c = s[:4].upper()
            if c in ('EHLO', 'HELO'):
                w('250 sink')
            elif c == 'DATA':
                data = True; w('354 go')
            elif c == 'QUIT':
                w('221 bye'); break
            else:
                w('250 ok')


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.ThreadingTCPServer(('127.0.0.1', MPORT), Sink)
threading.Thread(target=srv.serve_forever, daemon=True).start()
mock = subprocess.Popen([sys.executable, HERE + '/../cz/mockldap_cz.py', V, str(LPORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
atexit.register(mock.terminate)
mock.stdout.readline()
env = dict(os.environ, OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=run,
           OTP_STAY_ROOT='1')
json.dump({'db_engine': 'sqlite', 'radius_bind': '127.0.0.1', 'radius_auth_port': RPORT,
           'radius_acct_port': RPORT + 1, 'api_port': APORT, 'node_name': 'fc'},
          open(D + '/config.json', 'w'))
os.environ.update(env); sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.directory_save({'name': 'Domena', 'hosts': '127.0.0.1:%d' % LPORT, 'tls': 'none', 'port': 389,
                   'base': 'OU=Česká Lípa,DC=corpnet,DC=loc',
                   'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password',
                   'timeout_s': 5, 'user_attr': 'sAMAccountName'})
st.realm_save({'name': 'corpnet.cz', 'suffix': 'corpnet.cz', 'directory': 'Domena', 'lookup': 'upn',
               'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp', 'mail', 'sms'],
               'groups': [{'group': 'Uživatelé VPN', 'reply': ''}]})
st.client_save({'name': 'asa', 'address': '127.0.0.1', 'secret': 'tajne', 'enabled': 1})
st.add_account('local', 'fulladmin', 'Local-Admin-Pass-153!', must_change=0)
st.save_setting('names_czsk_letters', 1, 'test'); st.set_meta('names:letters:checked', '1')
tk = otp.Tokens(st)
g = tk.enroll('ostastny@corpnet.cz', 'test')          # one who has a token already
tk.check('ostastny@corpnet.cz', otp.totp(base64.b32decode(g['secret'] + '=' * (-len(g['secret']) % 8))), how='test')
d = subprocess.Popen([sys.executable, V + '/otp.py', '--daemon'], env=env,
                     stdout=open(D + '/d.out', 'w'), stderr=subprocess.STDOUT)
atexit.register(lambda: (d.terminate(), d.wait(10)))
time.sleep(6)
TOK = open(run + '/api-token').read().strip()


def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d' % APORT + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


def sms_code():
    time.sleep(0.5)
    files = sorted(glob.glob(SPOOL + '/otp-*'), key=os.path.getmtime)
    if not files:
        return None, ''
    t = open(files[-1]).read()
    m = re.search(r'\b(\d{6})\b', t.split('\n\n', 1)[-1])
    return (m.group(1) if m else None), t


def mail_code(n_before):
    for _ in range(40):
        if len(MAILS) > n_before:
            break
        time.sleep(0.25)
    if len(MAILS) <= n_before:
        return None, ''
    t = MAILS[-1]
    import email
    msg = email.message_from_string(t)
    subj = str(email.header.make_header(email.header.decode_header(msg['Subject'] or '')))
    m = re.search(r'(\d{6})', subj)
    return (m.group(1) if m else None), subj


_, a = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-153!'}); S = a['token']
c, x = call('/api/settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'portal_tries': 100,
                                           'code_send_max': 20}}, S)
ok('portal on: %s' % c, c == 200, x)

# ---- off: as until now ----------------------------------------------------------------------------
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
ok('off: signed in with the password alone, no gate', c == 200 and not x.get('gate'), x)
c, m = call('/api/portal/me', None, x.get('token'))
ok('off: the enrolment pages open at once', c == 200 and (m.get('me') or {}).get('methods'), m)
call('/api/portal/logout', {}, x.get('token'))

# ---- switched on only with a way to send ------------------------------------------------------------
c, x = call('/api/settings', {'settings': {'portal_first_code': 'sms'}}, S)
ok('on without the SMS gateway: refused (%s)' % c, c == 400 and 'SMS' in str(x.get('error')), x)
c, x = call('/api/settings', {'settings': {'sms_mode': 'spool', 'sms_spool_dir': SPOOL,
                                           'mail_mode': 'smtp', 'mail_from': 'otp@corpnet.cz',
                                           'smtp_host': '127.0.0.1', 'smtp_port': MPORT,
                                           'smtp_security': 'none', 'smtp_auth': 'none'}}, S)
ok('the SMS spool and the mail set up: %s' % c, c == 200, x)
c, x = call('/api/settings', {'settings': {'portal_first_code': 'sms_mail'}}, S)
ok('on: SMS, mail when no number: saved', c == 200, x)
c, x = call('/api/settings', {'settings': {'sms_mode': 'off', 'mail_mode': 'off'}}, S)
ok('the mail and the SMS switched off under it: refused (%s)' % c, c == 400, x)

# ---- somebody with a mobile number: by SMS ---------------------------------------------------------------
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1', 'lang': 'cs'})
gt = x.get('gate') or {}
ok('jcermak: a gate by SMS, the number masked: %s' % gt, c == 200 and gt.get('kind') == 'sms' and '222' in str(gt.get('dest')) and '603' not in str(gt.get('dest')), x)
P = x.get('token')
code, spool = sms_code()
ok('...the SMS went to the directory\'s number with the code', code and '420603111222' in spool.replace(' ', ''), spool[:200])
ok('...in the words of the enrolment pages (Czech, as the SMS sends it)', 'nastaveni prihlasovani' in spool, spool[-200:])
c, m = call('/api/portal/me', None, P)
me = m.get('me') or {}
ok('gated: /me shows the gate and nothing of the person', me.get('gate') and not me.get('about') and not me.get('methods'), m)
c, y = call('/api/portal/enroll', {'kind': 'totp'}, P)
ok('gated: a token cannot be made (%s)' % c, c == 401, y)
c, y = call('/api/portal/codes', {'code': '123456'}, P)
ok('gated: nothing else either (%s)' % c, c == 401, y)
wrong = '%06d' % ((int(code) + 1) % 1000000)
c, y = call('/api/portal/gate', {'code': wrong}, P)
ok('a wrong code: refused (%s)' % c, c == 403, y)
c, y = call('/api/portal/gate', {'code': code[:3] + ' ' + code[3:]}, P)
ok('the right code, typed "123 456": in (%s)' % c, c == 200 and (y.get('me') or {}).get('methods'), y)
old = P
P = y.get('token') or P       # a sign-in of its own after the code (1.0.249)
_c = call('/api/portal/me', None, old)
ok('...a new sign-in after the code, the one before ended', P != old and not (_c[1] or {}).get('me'), (P != old, _c))
c, y = call('/api/portal/gate', {'code': code}, P)
ok('...again: nothing more to do, the pages as they are (%s)' % c, c == 200, y)
c, y = call('/api/portal/enroll', {'kind': 'totp'}, P)
ok('then a token is made (%s)' % c, c == 200 and (y.get('made') or {}).get('uri'), y)
call('/api/portal/logout', {}, P)

# ---- nobody may take the code twice, tries are counted ------------------------------------------------------
n0 = len(MAILS)
c, x = call('/api/portal/login', {'name': 'žofie', 'password': 'Heslo-Ďábel-2', 'lang': 'en'})
gt = x.get('gate') or {}
ok('žofie (no mobile): the gate falls back to mail: %s' % gt, c == 200 and gt.get('kind') == 'mail' and 'z' in str(gt.get('dest')) and '@corpnet.cz' in str(gt.get('dest')), x)
P = x.get('token')
code, subj = mail_code(n0)
ok('...the mail came, its subject the enrolment pages\' own: %s' % subj, code and 'set up your sign-in' in subj, subj)
for i in range(3):
    c, y = call('/api/portal/gate', {'code': '%06d' % ((int(code) + 7 + i) % 1000000)}, P)
ok('three wrong codes: the last try said (%s)' % y.get('error'), c == 403 and 'last try' in str(y.get('error')), y)
c, y = call('/api/portal/gate', {'code': code}, P)
ok('...then the right one is gone too (%s)' % c, c in (403, 410), y)
n0 = len(MAILS)
c, y = call('/api/portal/gate/again', {}, P)
ok('sent again: %s' % c, c == 200 and (y.get('gate') or {}).get('live'), y)
code2, _ = mail_code(n0)
c, y = call('/api/portal/gate', {'code': code2}, P)
ok('the new code lets in (%s)' % c, c == 200, y)
call('/api/portal/logout', {}, P)

# ---- nothing to send it to, or a token already -----------------------------------------------------------
c, x = call('/api/portal/login', {'name': 'pnovak', 'password': 'Heslo-Čárka-3'})
ok('pnovak (no address, no number): told so, no sign-in (%s)' % c, c == 403 and 'ask the administrator' in str(x.get('error')) and not x.get('token'), x)
c, x = call('/api/portal/login', {'name': 'ostastny', 'password': 'Heslo-Vnořený-4'})
ok('ostastny has a token: signs in as before, no gate', c == 200 and not x.get('gate'), x)
call('/api/portal/logout', {}, x.get('token'))

# ---- by mail only -----------------------------------------------------------------------------------------
call('/api/settings', {'settings': {'portal_first_code': 'mail'}}, S)
tk2 = None
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
ok('jcermak has a token now (made above, waiting for its first code): gated again - mail now: %s' % x.get('gate'),
   c == 200 and (x.get('gate') or {}).get('kind') == 'mail', x)
call('/api/portal/logout', {}, x.get('token'))

# ---- right first sign-ins are not wrong passwords (1.0.234) ---------------------------------------------
call('/api/settings', {'settings': {'portal_tries': 3}}, S)
codes = []
for i in range(5):
    c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
    codes.append(c)
    call('/api/portal/logout', {}, x.get('token'))
ok('five right sign-ins through the gate from one address, 3 wrong passwords allowed: none refused (%s)' % codes, codes == [200] * 5, codes)
c, lo = call('/api/lockouts', None, S)
rows = [r for n in lo.get('nodes') or [] for r in n.get('rows') or [] if '127.0.0.1' in str(r.get('who')) and r.get('kind') == 'portal']
ok('...and the address is not among Locked out with wrong passwords', not any((r.get('fails') or 0) >= 3 for r in rows), rows)
call('/api/settings', {'settings': {'portal_tries': 100}}, S)

# ---- nothing of a code in the events ------------------------------------------------------------------------
ev = st.db.rows('SELECT words FROM events')
ok('no code in the events', not any(code and code in r['words'] or code2 and code2 in r['words'] for r in ev))
ok('the gate written in the events', any('one-time code went by SMS' in r['words'] for r in ev) and any('with the one-time code by' in r['words'] for r in ev))
call('/api/settings', {'settings': {'portal_first_code': 'off'}}, S)
c, x = call('/api/portal/login', {'name': 'jcermak', 'password': 'Heslo-Žluťoučký-1'})
ok('off again: as until now', c == 200 and not x.get('gate'), x)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
