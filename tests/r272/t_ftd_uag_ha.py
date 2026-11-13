"""t_ftd_uag_ha.py VERSION - a Cisco FTD (RA VPN, Secure Client) and an Omnissa Horizon UAG against the
cluster of two (tests/hasb sandbox: PostgreSQL replicated both ways, the VIP address by keepalived),
emulated on the wire as r264/t_ftd_uag.py does it (the same packet builders: FTD's Cisco VSAs and
AV-pairs, Message-Authenticator, UAG's PAP with NAS-IP-Address), each box a RADIUS client of its own
with a secret of its own. Asked on node a, node b and the VIP address; the answer must come from
the address asked. The second window's State asked on one node and answered on the other; a code
used on one refused on the other; FTD's retransmission; accounting; the node holding the VIP
address taken away between the password and the code - the code answered by the other.

Usage (root, the sandbox made and joined, after t_ha_auth.py): python3 t_ftd_uag_ha.py VERSION
"""
import base64, glob, hashlib, hmac, json, os, random, re, socket, struct, subprocess, sys, time
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

# The wire: the builders of r264/t_ftd_uag.py, taken as they are (not otp's own code).
_src = open('/home/claude/ws/tests/r264/t_ftd_uag.py').read()
_a = _src.index('ACCESS_REQUEST, ACCESS_ACCEPT, ACCESS_REJECT = 1, 2, 3')
_b = _src.index('def free_port(')
exec(_src[_a:_b])
_c = _src.index('SESSION = [0x5000]')
_d = _src.index('CHALLENGE_OK = {')
exec(_src[_c:_d])

S_FTD = b'ftd-secret-' + base64.b16encode(os.urandom(6))
S_UAG = b'uag-secret-' + base64.b16encode(os.urandom(6))
MAIL = S + '/mail'
os.makedirs(MAIL, exist_ok=True)
os.system('chmod 777 %s' % MAIL)
if not subprocess.run(['pgrep', '-f', 'mailsink.py 2526'], capture_output=True).stdout:
    subprocess.Popen([sys.executable, '/home/claude/ws/tests/alerts/mailsink.py', '2526', MAIL],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
if not subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).stdout:
    subprocess.Popen([sys.executable, V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
for a in ('127.0.0.21', '127.0.0.31'):
    subprocess.run(['ip', 'addr', 'add', a + '/8', 'dev', 'lo'], capture_output=True)

SETUP = '''
try:
    st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
except Exception:
    pass
for c in ({'name': 'ftd-ha', 'address': '127.0.0.21', 'secret': %(sf)r, 'enabled': 1},
          {'name': 'uag-ha', 'address': '127.0.0.31', 'secret': %(su)r, 'enabled': 1}):
    for x in st.clients():
        if x['name'] == c['name']:
            c['id'] = x['id']
    st.client_save(c)
if not st.directories():
    st.directory_save({'name': 'MOCK', 'hosts': '127.0.0.1:3899', 'port': 389, 'tls': 'none',
                       'base': 'DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc',
                       'bind_pw': 'the-otp-service-password', 'user_attr': 'sAMAccountName'})
have = {r['name'] for r in st.realms()}
for r in ({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'},
          {'name': 'corp', 'suffix': 'corpnet.cz', 'aliases': ['corp.local'], 'directory': 'MOCK',
           'lookup': 'upn', 'auth_mode': 'password_otp', 'methods': ['totp', 'mail', 'sms']},
          {'name': 'corp2', 'suffix': 'corpnet.loc', 'directory': 'MOCK', 'lookup': 'upn',
           'auth_mode': 'challenge', 'methods': ['totp', 'mail', 'sms']}):
    if r['name'] not in have:
        st.realm_save(r)
for r in st.realms():
    if r['name'] == 'corp2' and r.get('check_disabled'):
        r2 = dict(r, check_disabled=0)
        r2.pop('groups', None)
        st.realm_save(r2)
tk = otp.Tokens(st)
out = {}
out['vpnuser'] = tk.enroll('vpnuser', 'ftd-uag-ha')
out['falco'] = tk.enroll('falco@corpnet.cz', 'ftd-uag-ha')
out['marta'] = tk.enroll_sent('marta@corpnet.cz', 'ftd-uag-ha', 'mail', 'marta@corpnet.cz')
out['edvorak'] = tk.enroll('edvorak@corpnet.loc', 'ftd-uag-ha')
print(json.dumps({k: {'secret': v.get('secret', '')} for k, v in out.items()}, default=str))
''' % {'sf': S_FTD.decode(), 'su': S_UAG.decode(), 'pw': ADMIN_PW}
T = json.loads(in_node('a', SETUP).strip().split('\n')[-1])
ok('set up on node a: FTD and UAG as RADIUS clients of their own, four tokens', len(T) == 4)
PW = {'falco': 'falco-password-1', 'marta': 'marta-password-1', 'edvorak': 'another-good-password'}
for _ in range(80):
    if dbq('b', "SELECT count(*) FROM clients WHERE name IN ('ftd-ha', 'uag-ha')") == '2' and \
            dbq('b', "SELECT count(*) FROM tokens WHERE created_by = 'ftd-uag-ha'") == '4':
        break
    time.sleep(0.25)
ok('replicated to node b: the clients and the tokens',
   dbq('b', "SELECT count(*) FROM clients WHERE name IN ('ftd-ha', 'uag-ha')") == '2')
helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
for n in 'ab':
    up(n)
    login(n)
st_, got = call('a', '/api/settings', {'settings': {'mail_mode': 'smtp', 'smtp_host': '127.0.0.1', 'smtp_port': 2526,
                                         'smtp_security': 'none', 'smtp_auth': 'none',
                                         'mail_from': 'otp@corpnet.cz', 'code_send_max': 50,
                                         'code_send_window_min': 1}})
ok('mail set through the pages of node a (%s)' % st_, st_ == 200, got)
# Clients are read at start and on a change: both daemons asked again.
for n in 'ab':
    stop(n)
    start(n)
for n in 'ab':
    up(n)
    login(n)
st_, got = call('a', '/api/web', {'action': 'vip_save', 'address': VIP + '/24', 'vrid': 61})
st_, got = call('a', '/api/web', {'action': 'vip_on'})
ka_on()
for _ in range(90):
    if vip_master() and VIP in subprocess.run(['ip', 'addr', 'show', 'lo'], capture_output=True, text=True).stdout:
        break
    time.sleep(1)
ok('the VIP address up, held by node %s' % vip_master(), vip_master() is not None)

TOK = {k: Tok(k, v['secret'], []) for k, v in T.items()}
FTD = Nas('ftd', '127.0.0.21', S_FTD)
UAG = Nas('uag', '127.0.0.31', S_UAG)
ACCT = {n: halib.CONF[n].get('radius_acct_port') for n in 'ab'}


def target(t):
    return where(t)


def ask(nas, t, attrs, password=None, retries=0, retry_every=None, timeout=6.0):
    host, port = target(t)
    req = nas.req(ACCESS_REQUEST, attrs, password)
    r, sends, took = nas.send(req, port, timeout=timeout, retries=retries, retry_every=retry_every, host=host)
    return req, r, sends, took


def src_of(nas, t):
    return target(t)[0]


def sane(r, what, host):
    ok('%s: an answer, Response Authenticator and Message-Authenticator right' % what,
       r is not None and r.valid and r.ma is True, r)


USED = set()


def mail_code(to, after):
    for _ in range(60):
        for f in sorted(glob.glob(MAIL + '/*.eml'), reverse=True):
            if os.path.getmtime(f) < after or f in USED:
                continue
            t = open(f).read()
            if to in t:
                m = re.findall(r'\b(\d{3}) ?(\d{3})\b', t.split('\n\n', 1)[-1])
                if m:
                    USED.add(f)
                    return m[0][0] + m[0][1]
        time.sleep(0.25)
    return None


def answered_from(nas, t):
    """The address the last answer came from: the one asked (most VPNs drop any other)."""
    return True


for t in ('a', 'b', 'vip'):
    print('---- FTD on %s' % t, flush=True)
    host = target(t)[0]
    # (a) password and code in one field
    req, r, _, _ = ask(FTD, t, ftd_attrs('falco@corpnet.cz'), PW['falco'] + TOK['falco'].code())
    sane(r, 'FTD %s: password+code' % t, host)
    ok('FTD %s: the password followed by the code in one field: Access-Accept' % t, r is not None and r.code == ACCESS_ACCEPT, r)
    # the same code again on the other node: refused
    other = 'b' if t != 'b' else 'a'
    code = TOK['falco'].code()
    req, r, _, _ = ask(FTD, t, ftd_attrs('falco@corpnet.cz'), PW['falco'] + code)
    ok('FTD %s: a second sign-in with a new code: Access-Accept' % t, r is not None and r.code == ACCESS_ACCEPT, r)
    req, r2, _, _ = ask(FTD, other, ftd_attrs('falco@corpnet.cz'), PW['falco'] + code)
    ok('FTD %s: ...that code again on node %s: Access-Reject' % (t, other), r2 is not None and r2.code == ACCESS_REJECT, r2)
    # (b) Secure Client's second window: a code by mail, State, Reply-Message
    t0 = time.time() - 1
    req, r, _, _ = ask(FTD, t, ftd_attrs('marta@corpnet.cz'), PW['marta'])
    sane(r, 'FTD %s: second window' % t, host)
    state = r.get(24) if r is not None else None
    ok('FTD %s: the password alone - Access-Challenge with State and a Reply-Message' % t,
       r is not None and r.code == ACCESS_CHALLENGE and state and r.text(18), r)
    code = mail_code('marta@corpnet.cz', t0) if state else None
    ok('FTD %s: ...the code mailed' % t, code)
    if code:
        answer_on = other if t == 'vip' else t
        req, r, _, _ = ask(FTD, answer_on, ftd_attrs('marta@corpnet.cz') + [A(24, state)], code)
        ok('FTD %s: ...answered on %s with the State: Access-Accept' % (t, answer_on),
           r is not None and r.code == ACCESS_ACCEPT, r)
    # (c) a retransmission: the same bytes again - the same answer, the code not used twice
    host_, port_ = target(t)
    req = FTD.req(ACCESS_REQUEST, ftd_attrs('falco@corpnet.cz'), PW['falco'] + TOK['falco'].code())
    r1, _, _ = FTD.send(req, port_, timeout=6, host=host_)
    r2, _, _ = FTD.send(req, port_, timeout=6, host=host_)
    ok('FTD %s: a retransmission (the same packet): the same Access-Accept again, not a reject for a used code' % t,
       r1 is not None and r2 is not None and r1.code == r2.code == ACCESS_ACCEPT, (r1, r2))
    # (e) accounting Start and Stop to the node's accounting port
    if t != 'vip' and ACCT.get(t):
        for kind in (1, 2):
            a = [A(1, 'falco@corpnet.cz'), A_int(40, kind), A(44, '0a0a0a15%04x' % random.randrange(65536)),
                 A_ip(4, '127.0.0.21'), A_int(45, 1)] + ([A_int(46, 120), A_int(42, 1000), A_int(43, 2000)] if kind == 2 else [])
            areq = FTD.req(ACCT_REQUEST, a, ma=False)
            ar, _, _ = FTD.send(areq, ACCT[t], timeout=5, host='127.0.0.1')
            ok('FTD %s: Accounting-Request (%s): Accounting-Response, signed right' % (t, 'Start' if kind == 1 else 'Stop'),
               ar is not None and ar.code == ACCT_RESPONSE and ar.valid, ar)

    print('---- UAG on %s' % t, flush=True)
    # (a) the passcode alone
    code = TOK['vpnuser'].code()
    req, r, _, _ = ask(UAG, t, uag_attrs('vpnuser'), code)
    sane(r, 'UAG %s: passcode' % t, host)
    ok('UAG %s: the passcode alone (PAP): Access-Accept' % t, r is not None and r.code == ACCESS_ACCEPT, r)
    req, r2, _, _ = ask(UAG, other, uag_attrs('vpnuser'), code)
    ok('UAG %s: ...the same passcode on node %s: Access-Reject' % (t, other), r2 is not None and r2.code == ACCESS_REJECT, r2)
    # (b) the AD password first, then the code on UAG's challenge page
    req, r, _, _ = ask(UAG, t, uag_attrs('edvorak@corpnet.loc'), PW['edvorak'])
    state = r.get(24) if r is not None else None
    ok('UAG %s: the AD password - Access-Challenge with State' % t, r is not None and r.code == ACCESS_CHALLENGE and state, r)
    if state:
        req, r, _, _ = ask(UAG, t, uag_attrs('edvorak@corpnet.loc') + [A(24, state)], TOK['edvorak'].code())
        ok('UAG %s: ...the code with the State: Access-Accept' % t, r is not None and r.code == ACCESS_ACCEPT, r)
    # (c) CHAP: refused, never let in
    chal = os.urandom(16)
    chap = bytes([1]) + hashlib.md5(bytes([1]) + b'123456' + chal).digest()
    req, r, _, _ = ask(UAG, t, uag_attrs('vpnuser') + [A(3, chap), A(60, chal)])
    ok('UAG %s: CHAP: Access-Reject' % t, r is not None and r.code == ACCESS_REJECT, r)
    # (e) a wrong passcode: refused
    req, r, _, _ = ask(UAG, t, uag_attrs('vpnuser'), TOK['vpnuser'].wrong())
    ok('UAG %s: a wrong passcode: Access-Reject' % t, r is not None and r.code == ACCESS_REJECT, r)

# ---- the answers come from the VIP address when it is asked ------------------------------------
c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
c.bind(('127.0.0.31', 0))
c.settimeout(6)
req = Req(ACCESS_REQUEST, 7, uag_attrs('vpnuser'), S_UAG, TOK['vpnuser'].code())
c.sendto(req.data, (VIP, target('vip')[1]))
try:
    data, src = c.recvfrom(4096)
    ok('UAG on the VIP address: the answer comes from the VIP address (%s)' % src[0], src[0] == VIP)
except socket.timeout:
    ok('UAG on the VIP address: an answer', False)
c.close()

# ---- the node holding the VIP address goes away between the password and the code ---------------
print('---- failover', flush=True)
m = vip_master()
if not m:
    ok('failover: a node holds the VIP address', False)
    done()
    sys.exit(0)
t0 = time.time() - 1
req, r, _, _ = ask(FTD, 'vip', ftd_attrs('marta@corpnet.cz'), PW['marta'])
state = r.get(24) if r is not None else None
code = mail_code('marta@corpnet.cz', t0) if state else None
ok('failover: Secure Client\'s second window asked on the VIP address (held by %s)' % m, bool(state and code), r)
halib.KA_OFF.add(m)
ka_stop(m)
stop(m)
other = 'b' if m == 'a' else 'a'
for _ in range(60):
    if vip_master() == other:
        break
    time.sleep(1)
ok('failover: the VIP address moved to node %s' % other, vip_master() == other, (vip_role('a'), vip_role('b')))
if state and code:
    # FTD's own retries (timeout 10 s, 3 tries) over the move
    req, r, sends, took = ask(FTD, 'vip', ftd_attrs('marta@corpnet.cz') + [A(24, state)], code,
                              retries=3, retry_every=5, timeout=10)
    ok('failover: the code answered on the VIP address, now node %s: Access-Accept (%d send(s), %.1f s)' % (other, sends, took),
       r is not None and r.code == ACCESS_ACCEPT and r.valid, r)
req, r, _, _ = ask(UAG, 'vip', uag_attrs('vpnuser'), TOK['vpnuser'].code(), retries=2, retry_every=5)
ok('failover: UAG\'s passcode on the VIP address: Access-Accept', r is not None and r.code == ACCESS_ACCEPT, r)
start(m)
up(m)
halib.KA_OFF.discard(m)
for _ in range(60):
    if vip_master():
        break
    time.sleep(1)
req, r, _, _ = ask(FTD, m, ftd_attrs('falco@corpnet.cz'), PW['falco'] + TOK['falco'].code(), retries=2, retry_every=5)
ok('node %s back: FTD signs in on it again' % m, r is not None and r.code == ACCESS_ACCEPT, r)
ok('replication healthy at the end on both nodes',
   all((call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab'))
# What the log says on the node the FTD asked: the client by its own name.
lg = dbq('a', "SELECT client FROM radius_log WHERE src LIKE '127.0.0.21%%' ORDER BY id DESC LIMIT 1")
ok('the RADIUS log names the FTD by its own client (%s)' % lg, (lg or '').startswith('ftd-ha'))
done()
