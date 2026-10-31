# t_ha_auth.py VERSION - signing in on a cluster of two (PostgreSQL replicated both ways,
# the VIP address by keepalived): on node a, on node b and on the VIP address, every way -
# a code from the app, the directory password with a code, a code by mail and by SMS in a
# second window, recovery codes, realms by their suffix and by an alias - and across the
# nodes: a code used on one is refused on the other, a question asked on one answered on
# the other, a name locked out on one locked out on both. RADIUS asked all the time.
# Usage (root, tests/hasb sandbox made and joined): python3 t_ha_auth.py VERSION
import os, sys, time, json, re, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402
import halib  # noqa: E402

MAIL = S + '/mail'
SMS = S + '/sms'
os.makedirs(MAIL, exist_ok=True)
os.makedirs(SMS, exist_ok=True)
os.system('chmod 777 %s %s' % (MAIL, SMS))
sink = subprocess.Popen([sys.executable, '/home/claude/ws/tests/alerts/mailsink.py', '2526', MAIL],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
if not subprocess.run(['pgrep', '-f', 'mockldap.py 3899'], capture_output=True).stdout:
    subprocess.Popen([sys.executable, V + '/test/mockldap.py', '3899'], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)

# ---- what is set up, once, on node a (replicated to b) -------------------------------
SETUP = '''
try:
    st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
except Exception: pass
for c in ({'name': 'lo', 'address': '127.0.0.0/8', 'secret': %(sec)r, 'enabled': 1},
          {'name': 'sandbox', 'address': '10.99.0.0/24', 'secret': %(sec)r, 'enabled': 1}):
    if not [x for x in st.clients() if x['name'] == c['name']]:
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
st.save_settings({'mail_mode': 'smtp', 'smtp_host': '127.0.0.1', 'smtp_port': 2526,
                  'smtp_security': 'none', 'smtp_auth': 'none', 'mail_from': 'otp@corpnet.cz',
                  'sms_mode': 'spool', 'sms_spool_dir': %(sms)r, 'code_send_max': 50,
                  'rate_limit_tries': 0}) if hasattr(st, 'save_settings') else None
for r in st.realms():
    if r['name'] == 'corp2' and r.get('check_disabled'):
        # The test directory's people of corpnet.loc carry no userAccountControl.
        r2 = dict(r, check_disabled=0)
        r2.pop('groups', None)
        st.realm_save(r2)
tk = otp.Tokens(st)
out = {}
out['anna'] = tk.enroll('anna', 'test')
out['lockme'] = tk.enroll('lockme', 'test')
out['falco'] = tk.enroll('falco@corpnet.cz', 'test')
out['marta'] = tk.enroll_sent('marta@corpnet.cz', 'test', 'mail', 'marta@corpnet.cz')
out['jnovak'] = tk.enroll_sent('jnovak@corpnet.loc', 'test', 'sms', '+420777100200')
out['edvorak'] = tk.enroll('edvorak@corpnet.loc', 'test')
print(json.dumps(out, default=str))
''' % {'pw': ADMIN_PW, 'sec': SECRET, 'sms': SMS}
T = json.loads(in_node('a', SETUP).strip().split('\n')[-1])
ok('set up on node a: accounts, clients, a directory, three realms, six tokens', len(T) == 6)
helpers_on()
for n in 'ab':
    start(n)
    login(n)
# Settings through the API (a's daemon writes them, b reads them replicated).
st_, got = call('a', '/api/settings', {'settings': {'mail_mode': 'smtp', 'smtp_host': '127.0.0.1', 'smtp_port': 2526,
                                         'smtp_security': 'none', 'smtp_auth': 'none',
                                         'mail_from': 'otp@corpnet.cz', 'sms_mode': 'spool',
                                         'sms_spool_dir': SMS, 'code_send_max': 50, 'code_send_window_min': 1,
                                         'lockout_after': 10}})
ok('mail and SMS set through the pages of node a (%s)' % st_, st_ == 200, got)


def wait_repl(sql_a, timeout=20):
    """Until node b sees what node a has."""
    want = dbq('a', sql_a)
    if not want:
        return False
    for _ in range(timeout * 4):
        if dbq('b', sql_a) == want:
            return True
        time.sleep(0.25)
    return False


ok('replicated to node b: the tokens', wait_repl("SELECT string_agg(name, ',' ORDER BY name) FROM tokens"))
ok('... the realms', wait_repl("SELECT string_agg(name, ',' ORDER BY name) FROM realms"))
# Made beside the daemons, not through them: started again, they read all of it.
for n in 'ab':
    stop(n)
    start(n)
    login(n)

# ---- the VIP address -----------------------------------------------------------------
st_, got = call('a', '/api/web', {'action': 'vip_save', 'address': VIP + '/24', 'vrid': 61})
ok('the VIP address kept (%s)' % st_, st_ == 200, got)
st_, got = call('a', '/api/web', {'action': 'vip_on'})
ok('... on (%s)' % st_, st_ == 200, got)
ka_on()
for _ in range(90):
    if vip_master() and VIP in subprocess.run(['ip', 'addr', 'show', 'lo'], capture_output=True, text=True).stdout:
        break
    time.sleep(1)
ok('keepalived of both nodes: one MASTER (%s), the address up' % vip_master(), vip_master() is not None,
   (vip_role('a'), vip_role('b'), open('%s/a/ka.log' % S).read()[-400:] if os.path.exists('%s/a/ka.log' % S) else ''))
P = Prober()


USED = set()


def last_mail_code(to, after):
    for _ in range(40):
        for f in sorted(glob.glob(MAIL + '/*.eml'), reverse=True):
            if os.path.getmtime(f) < after or f in USED:
                continue
            t = open(f).read()
            if to in t:
                m = re.findall(r'\b(\d{6})\b', t.split('\n\n', 1)[-1])
                if m:
                    USED.add(f)
                    return m[0]
        time.sleep(0.25)
    return None


def last_sms_code(after):
    for _ in range(40):
        for f in sorted(glob.glob(SMS + '/otp-*'), key=os.path.getmtime, reverse=True):
            if os.path.getmtime(f) < after or f in USED:
                continue
            m = re.findall(r'\b(\d{6})\b', open(f).read().split('\n\n', 1)[-1])
            if m:
                USED.add(f)
                return m[0]
        time.sleep(0.25)
    return None


def fresh_step():
    """Wait for a time step no code was used in yet (a code is good once)."""
    s0 = int(time.time()) // 30
    while int(time.time()) // 30 == s0:
        time.sleep(0.5)


K = {k: v.get('secret', '') for k, v in T.items()}
PW = {'falco': 'falco-password-1', 'marta': 'marta-password-1', 'jnovak': 'a-good-long-password',
      'edvorak': 'another-good-password'}

for tgt in ('a', 'b', 'vip'):
    print('---- on %s' % tgt, flush=True)
    fresh_step()
    c = totp_of(K['anna'])
    ok('%s: a code from the app (local realm): in' % tgt, rad(tgt, 'anna', c)[0] == 'accept')
    other = 'b' if tgt == 'a' else 'a'
    time.sleep(0.5)
    ok('%s: the same code again, on node %s: refused' % (tgt, other), rad(other, 'anna', c)[0] == 'reject')
    ok('%s: a wrong code: refused' % tgt, rad(tgt, 'anna', '%06d' % ((int(c) + 1) % 1000000))[0] == 'reject')
    ok('%s: directory password and code (corp): in' % tgt, rad(tgt, 'falco@corpnet.cz', PW['falco'] + totp_of(K['falco']))[0] == 'accept')
    fresh_step()
    ok('%s: the same by an alias of the realm (falco@corp.local): in' % tgt,
       rad(tgt, 'falco@corp.local', PW['falco'] + totp_of(K['falco']))[0] == 'accept')
    ok('%s: a wrong directory password: refused' % tgt, rad(tgt, 'falco@corpnet.cz', 'nope' + totp_of(K['falco'], 30))[0] == 'reject')
    # a code by mail, in a second window
    t0 = time.time() - 1
    r, at = rad(tgt, 'marta@corpnet.cz', PW['marta'])
    code = last_mail_code('marta@corpnet.cz', t0) if r == 'challenge' else None
    ok('%s: a mail token: the password - asked for the code, mailed (%s)' % (tgt, r), r == 'challenge' and code, at)
    if code:
        r2, _ = rad(tgt, 'marta@corpnet.cz', '000000', state=at.get('State'))
        ok('%s: ... a wrong code: asked again' % tgt, r2 == 'challenge')
        ok('%s: ... the right one: in' % tgt, rad(tgt, 'marta@corpnet.cz', code, state=at.get('State'))[0] == 'accept')
    # a code by SMS, a realm asking in a second window, by its suffix
    t0 = time.time() - 1
    r, at = rad(tgt, 'jnovak@corpnet.loc', PW['jnovak'])
    code = last_sms_code(t0) if r == 'challenge' else None
    ok('%s: an SMS token: the password - asked for the code, sent (%s)' % (tgt, r), r == 'challenge' and code, at)
    if code:
        ok('%s: ... the right one: in' % tgt, rad(tgt, 'jnovak@corpnet.loc', code, state=at.get('State'))[0] == 'accept')
    # an app token in the realm of the second window
    r, at = rad(tgt, 'edvorak@corpnet.loc', PW['edvorak'])
    ok('%s: the challenge realm, an app token: the password - asked for the code (%s)' % (tgt, r), r == 'challenge', at)
    if r == 'challenge':
        fresh_step()
        ok('%s: ... the code: in' % tgt, rad(tgt, 'edvorak@corpnet.loc', totp_of(K['edvorak']), state=at.get('State'))[0] == 'accept')

print('---- across the nodes', flush=True)
# asked on a, answered on b (a VPN that moved over to the other server between the two)
t0 = time.time() - 1
r, at = rad('a', 'marta@corpnet.cz', PW['marta'])
code = last_mail_code('marta@corpnet.cz', t0)
time.sleep(1.5)
ok('asked for the mailed code on a, answered on b: in', r == 'challenge' and code and
   rad('b', 'marta@corpnet.cz', code, state=at.get('State'))[0] == 'accept')
# recovery codes: once, on either node
sc = (T['anna'].get('scratch') or [None])[0]
ok('a recovery code on a: in', sc and rad('a', 'anna', sc)[0] == 'accept')
time.sleep(0.5)
ok('... the same on b: refused', sc and rad('b', 'anna', sc)[0] == 'reject')
# a name locked out on a is locked out on b
for i in range(10):
    rad('a', 'lockme', '%06d' % (111110 + i))
time.sleep(1.5)
fresh_step()
ok('ten wrong codes on a: the right code refused on b too (locked out)', rad('b', 'lockme', totp_of(K['lockme']))[0] == 'reject')
# a code used on b, then sent to the VIP address
fresh_step()
c = totp_of(K['anna'])
ok('a code on b: in', rad('b', 'anna', c)[0] == 'accept')
ok('... the same to the VIP address: refused', rad('vip', 'anna', c)[0] == 'reject')
# the same code on both nodes at the very same moment: let in once at most
fresh_step()
c = totp_of(K['anna'])
import concurrent.futures as cf  # noqa: E402
with cf.ThreadPoolExecutor(2) as ex:
    a1, b1 = ex.submit(rad, 'a', 'anna', c), ex.submit(rad, 'b', 'anna', c)
    res = sorted([a1.result()[0], b1.result()[0]])
ok('the same code on both nodes at once: let in once at most (%s)' % res, res.count('accept') <= 1)
P.stop_flag = True
time.sleep(1)
for t in ('a', 'b', 'vip'):
    ok('the prober: %s answered every time (%d asked, %d not)' % (t, P.asked[t], len(P.lost[t])), not P.lost[t])
ok('replication healthy at the end on both nodes', all((call(n, '/api/ha')[1].get('replication') or {}).get('healthy') for n in 'ab'))
done()
