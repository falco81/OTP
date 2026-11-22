"""t_fix.py - 1.0.316: the certificate sign-in's last English hints, the directory's reasons for a refusal and
a database agent's steps in Czech; no Teltonika gateway set is 400, not 502. The built otp.py loaded as a
module over SQLite - no daemon, no ports.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, re, shutil, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.316'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r316_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx316', 'api_port': 29946}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)

# ==== 1 Czech: every one of these has its words, and none is the English again
cs = json.load(open(V + '/web/lang/cs.json'))
words = {v['source']: v['text'] for v in cs['strings'].values()}
for k in ('admin_cert_crl_ldap', 'admin_cert_ocsp', 'admin_cert_ocsp_url'):
    en = m.SAYS[k]
    ok('1 %s in Czech' % k, words.get(en) and words[en] != en and re.search('[áčďéěíňóřšťúůýž]', words[en]), en[:60])
for name in ('LDAP_SAYS', 'AD_REASONS', 'DBAGENT_APPLIES'):
    d = getattr(m, name)
    left = [v for k, v in d.items() if v != 'success' and not words.get(v)]
    ok('1 %s: each in Czech' % name, not left, left)
ok('1 a code, a path, a name kept as written', 'pg_hba hostssl' in words[m.DBAGENT_APPLIES['ha_link']]
   and 'ldap:///CN=...,CN=CDP' in words[m.SAYS['admin_cert_crl_ldap']])
ok('1 the version of the file', cs['_meta']['version'] == VER, cs['_meta'])

# ==== 2 the gateway's certificate with no gateway: the administrator's to put in
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)
d = type('Dm', (), {'store': st})()
for host, code in (('', 400), ('   ', 400), ('/', 400)):
    m.CONFIG['sms_tel_host'] = host
    try:
        m.cli_api(d, 'command line', 'POST', '/api/mail', {'action': 'sms_ca_fetch'})
        got = 'no error'
    except SystemExit as e:
        got = str(e)
    ok('2 no address (%r): said, not a failing gateway' % host, 'no address of the Teltonika gateway is set' in got, got)
H = m.CliApiHandler(d, 'command line', {'action': 'sms_ca_fetch'}, None, '/api/mail')
m.CONFIG['sms_tel_host'] = ''
try:
    m.ROUTES[('POST', '/api/mail')](H); c = 0
except m.ApiError as e:
    c = e.status
ok('2 ...as 400', c == 400, c)
m.CONFIG['sms_tel_host'] = '127.0.0.1:1'
try:
    m.ROUTES[('POST', '/api/mail')](H); c = 0
except m.ApiError as e:
    c = e.status
ok('2 a gateway set that does not answer: still 502', c == 502, c)
src = open(V + '/otp.py').read()
ok('2 one place', src.count("raise ApiError(400, 'no address of the Teltonika gateway is set')") == 1)


# ==== 3 Settings → Logs: otp's own sentence in the page's language, a tool's line as it is
js = open(V + '/web/assets/admin.js').read()
ok('3 the logs pane: a sentence no longer kept from translation',
   "var lsaid = noI18n(el('div', 'si-said small', n.said));" in js and "if (/\\s/.test(n.said)) lsaid.removeAttribute('data-no-i18n');" in js)
ok('3 ...nowhere else changed', js.count('lsaid') == 3)
pat = [v for v in cs['patterns'].values() if v['source'].startswith('the root helper of this node did not answer in {0} s')]
ok('3 its words are there in Czech', pat and all(v['text'] for v in pat), pat)

print('ALL %d / %d' % (sum(R), len(R)))
