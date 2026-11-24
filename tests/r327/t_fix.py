"""t_fix.py - 1.0.327: each node of a replicated pair tidies its own counts; a copy put back on the
node that is not the lead has the lead put its names in one form; {account} in a link's address;
the system's list of authorities made again until its tool ran through; MariaDB's TLS folder; the
agent on IPv6 too.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, socket, subprocess, sys, tempfile, time, atexit, unicodedata
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.327'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r327_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx327', 'api_port': 29957}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 chal_tidy: own rows only in a replicated pair
old = json.dumps([time.time() - 86400])


def put_counts():
    for k in ('codesent:jan@@fx327', 'codesent:jan@@other', 'codesent:jan', 'adpw:jan@@other', 'adpw:jan@@fx327'):
        st.set_meta(k, old)


def left():
    return sorted(r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'codesent:%' OR k LIKE 'adpw:%'"))


put_counts()
m.CONFIG['ha_mode'] = 'replicated'
m.ha_lead = lambda store: True
m.chal_tidy(st)
ok('tidy, replicated, the lead: its own and the old one gone, the other\'s kept',
   left() == ['adpw:jan@@other', 'codesent:jan@@other'], left())
put_counts()
m.ha_lead = lambda store: False
m.chal_tidy(st)
ok('tidy, replicated, not the lead: its own gone, the old one kept for the lead',
   left() == ['adpw:jan@@other', 'codesent:jan', 'codesent:jan@@other'], left())
put_counts()
m.CONFIG['ha_mode'] = ''
m.chal_tidy(st)
ok('tidy, one node or one database: all gone as before', left() == [], left())
fresh = json.dumps([time.time()])
st.set_meta('codesent:eva@@fx327', fresh)
m.chal_tidy(st)
ok('tidy: a count still counting kept', st.get_meta('codesent:eva@@fx327') == fresh)

# ==== 2 names: the node that is not the lead asks, the lead does it
dec = unicodedata.normalize('NFD', 'žluťoučký')
st.db.run("INSERT INTO tokens (name) VALUES (?)", (dec,))
m.CONFIG['ha_mode'] = 'replicated'
m.ha_lead = lambda store: False
m.names_nfc_kept(st)
asks = st.db.rows("SELECT k FROM meta WHERE k LIKE 'names:nfc:ask%'")
ok('names: not the lead - asked, under its own key', [r['k'] for r in asks] == ['names:nfc:ask@@fx327'], asks)
ok('names: not the lead - nothing renamed here', st.db.value('SELECT name FROM tokens') == dec)
m.ha_lead = lambda store: True
m.names_nfc_asked(st)
ok('names: the lead put it in one form', st.db.value('SELECT name FROM tokens') == unicodedata.normalize('NFC', dec),
   st.db.value('SELECT name FROM tokens'))
ok('names: the ask taken away', not st.db.rows("SELECT k FROM meta WHERE k LIKE 'names:nfc:ask%'"))
m.ha_lead = lambda store: False
m.names_nfc_kept(st)
ok('names: nothing to put right - nothing asked', not st.db.rows("SELECT k FROM meta WHERE k LIKE 'names:nfc:ask%'"))
m.CONFIG['ha_mode'] = ''

# ==== 3 {account} in a link's address
acc = '<span style="white-space:nowrap">jan.novak@&#8205;corp.cz</span>'
t = 'Help: <a href="https://help.example/u/{account}" style="color:#1d4ed8">your page {account}</a>'
got = m.fill_html(t, {'account': acc}, {'account': 'jan.novak@corp.cz'})
ok('link: the address takes the plain name', 'href="https://help.example/u/jan.novak@corp.cz"' in got, got)
ok('link: the text keeps the span', 'your page ' + acc in got, got)
got = m.fill_html('<a href="https://x/?q={account}">a</a>', {'account': acc}, {'account': 'a"b <c>&d'})
ok('link: a quote, < and & in the value cannot leave the address', 'href="https://x/?q=a%22b%20%3Cc%3E&amp;d"' in got, got)
ok('link: a text with no link as before', m.fill_html('Hi {account}', {'account': acc}, {'account': 'x'}) == 'Hi ' + acc)
ok('link: {{ }} as before', m.fill_html('<a href="https://x/{{a}}">{account}</a>', {'account': 'y'}, {'account': 'y'})
   == '<a href="https://x/{a}">y</a>')
w = dict(m.texts_for('code', 'en'))
for k in list(w):
    if k.startswith('h_') and k.endswith('lede'):
        w[k] = 'See <a href="https://help.example/u/{account}">here</a>.'
html_ = m.code_mail_html('123456', 'mfa', 'en', name='jan.novak@corp.cz', display='Jan', w=w)
ok('code mail: its link whole', 'href="https://help.example/u/jan.novak@corp.cz"' in str(html_), str(html_)[:600])
src = open(V + '/otp.py').read()
ok('token mail: every text filled through fill_html', src.count("fill_html(w['") >= 9 and "w['lede'].format(**fmt)" not in src)

# ==== 4 the system's list made again until its tool ran through
FB = TOP + '/fakebin'; os.makedirs(FB)
ANCH = TOP + '/anchors'; os.makedirs(ANCH)
BUNDLE = TOP + '/extracted/tls-ca-bundle.pem'; os.makedirs(os.path.dirname(BUNDLE))
CALLS, FAIL = TOP + '/calls', TOP + '/fail'
open(FB + '/x', 'w').write('#!/bin/sh\necho run >> %s\n[ -e %s ] && exit 3\ncat %s/* > %s 2>/dev/null; exit 0\n'
                           % (CALLS, FAIL, ANCH, BUNDLE))
open(FB + '/p', 'w').write('#!/bin/sh\necho ca-certificates-1\n')
for f in 'xp':
    os.chmod(FB + '/' + f, 0o755)
HS = TOP + '/hstate'; os.makedirs(HS + '/web')
os.environ.update(OTP_OSROOTS_FLAVOUR='rhel', OTP_OSROOTS_DIR=ANCH, OTP_OSROOTS_BUNDLE=BUNDLE,
                  OTP_OSROOTS_EXTRACT=FB + '/x', OTP_OSROOTS_PKG=FB + '/p', OTP_VIP_NO_SERVICES='1', OTP_STATE=HS,
                  OTP_ROOT_STATE=TOP + '/rootstate')
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', TOP + '/k', '-out', TOP + '/c',
                '-subj', '/CN=R327 Root', '-days', '30', '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign'], capture_output=True, check=True)
CA = open(TOP + '/c').read()
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)


def ncalls():
    try:
        return len(open(CALLS).read().split())
    except OSError:
        return 0


wh = W.osroots_where()
W.osroots_sync(wh, [CA])
ok('osroots: added, the tool run', ncalls() == 1 and os.listdir(ANCH))
open(FAIL, 'w').close()
try:
    W.osroots_sync(wh, []); e = None
except W.Refused as x:
    e = x
ok('osroots: taken away, the tool failed - refused', e is not None and not os.listdir(ANCH), e)
ok('osroots: ...the mark it is owed is there', os.path.exists(TOP + '/rootstate/osroots-pending'))
os.unlink(FAIL)
n = ncalls()
said, _r = W.osroots_sync(wh, [])
ok('osroots: the next look runs it again', ncalls() == n + 1 and any('not made again' in s for s in said), said)
ok('osroots: ...the mark gone', not os.path.exists(TOP + '/rootstate/osroots-pending'))
ok('osroots: ...the bundle without it', 'R327' not in open(BUNDLE).read() and CA.split('\n')[1] not in open(BUNDLE).read())
n = ncalls()
W.osroots_sync(wh, [])
ok('osroots: then nothing to do - not run', ncalls() == n)

# ==== 5 MariaDB's TLS folder
pg = open(V + '/deploy/otp_pg_ops.py').read()
i = pg.index("    old = '/etc/otp-db-agent/mariadb'")
blk = pg[i:i + 3500]
ok('mariadb tls: a folder MariaDB reaches, made 0750 for sure', "'/etc/otp-db-agent-mariadb'" in blk and
   'os.chmod(folder, 0o750)' in blk)
ok('mariadb tls: a hand-made set-up with the old folder kept', "(old + '/') in cnf_was" in blk)
ok('mariadb tls: started again when put back', 'if restarted:' in blk and blk.index('if restarted:') > blk.index('W.write_root(cnf, cnf_was'))
compile(pg, 'otp_pg_ops.py', 'exec')

# ==== 6 the agent on IPv6 too
spec = importlib.util.spec_from_file_location('otp_db_agent', V + '/deploy/otp_db_agent.py')
A = importlib.util.module_from_spec(spec)
sys.argv = ['otp-db-agent']
try:
    spec.loader.exec_module(A)
    try:
        _v = socket.socket(socket.AF_INET6); _v.bind(('::', 0)); _v.close(); V6 = True
    except OSError:
        V6 = False
    c = {'listen': '::', 'port': 0}
    s = A.listen_socket(c)
    p = s.getsockname()[1]
    if V6:
        ok('agent: on :: - IPv6', s.family == socket.AF_INET6 and c['listen'] == '::')
        ok('agent: ...and IPv4 on the same socket', s.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 0)
        t6 = socket.create_connection(('::1', p), 3); t6.close()
    else:
        print('     (this machine has no IPv6: :: falls back to IPv4)')
        ok('agent: no IPv6 here - :: on IPv4 alone', s.family == socket.AF_INET and c['listen'] == '0.0.0.0', c)
    t4 = socket.create_connection(('127.0.0.1', p), 3); t4.close()
    ok('agent: answered on 127.0.0.1', True)
    s.close()
    real = A.socket.socket

    class NoV6(real):
        def __init__(self, fam=socket.AF_INET, *a, **k):
            if fam == socket.AF_INET6:
                raise OSError(97, 'Address family not supported by protocol')
            real.__init__(self, fam, *a, **k)

    A.socket.socket = NoV6
    try:
        c = {'listen': '::', 'port': 0}
        try:
            s = A.listen_socket(c); fell = (s.family, c['listen'])
            s.close()
        except OSError as x:
            fell = x
    finally:
        A.socket.socket = real
    ok('agent: a machine without IPv6 - IPv4 alone', fell == (socket.AF_INET, '0.0.0.0'), fell)
    c = {'listen': '0.0.0.0', 'port': 0}
    s = A.listen_socket(c)
    ok('agent: set up before (0.0.0.0) - as it was', s.family == socket.AF_INET); s.close()
except SystemExit as x:
    ok('agent: loaded', False, x)
sh = open(V + '/deploy/db-server.sh').read()
ok('db-server: a new agent on :: where IPv6 is', "lis = '::'" in sh and "'listen': lis" in sh)
ok('db-server: MariaDB bind-address :: where IPv6 is', 'bind-address = %s' in sh and 'bind=::' in sh)
r = subprocess.run(['bash', '-n', V + '/deploy/db-server.sh'], capture_output=True, text=True)
ok('db-server: bash -n', r.returncode == 0, r.stderr)
cs = json.load(open(V + '/web/lang/cs.json'))
ok('its words in Czech', any(v['source'] == "the system's list was not made again the last time - made now" and v['text'] for v in cs['strings'].values()))

print('ALL %d / %d' % (sum(R), len(R)))
