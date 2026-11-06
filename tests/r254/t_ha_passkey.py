"""t_ha_passkey.py - 1.0.254: the passkey second step on both nodes (HA sandbox, replicated).
Set up: the question asked on node a, answered on node b. Signing in: the password on b, the
question on b, the answer on a. The same answer again on either node: refused (once). The
counter of the device kept on both. A reset on a: b asks to set it up again. Off: as before."""
import sys, os, time, json, re, urllib.request
sys.path.insert(0, '/home/claude/ws/tests/hasb/full')
import halib as HL

# the device of t_webauthn.py (ES256, RS256, Ed25519 keys made there)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 't_webauthn.py')).read()
exec(src.split("\nh = H('otp.firma.cz')")[0])

for n in 'ab':
    if not HL.running(n):
        HL.start(n)
    HL.up(n)
HL.in_node('a', "try:\n    st.add_account('local', 'fulladmin', %r, must_change=0)\nexcept Exception: pass\n" % HL.ADMIN_PW)
PW = 'Pk-Ha-254-pass!'
# from nothing, whatever a run before left (the second step off, no pkha, no passkey of it)
HL.in_node('a', "st.db.run(\"DELETE FROM settings WHERE k IN ('admin_2fa', 'admin_2fa_passkey')\")\n"
           "st.db.run(\"DELETE FROM meta WHERE k = 'adm2fa:pkha'\")\n"
           "try:\n    st.drop_account('pkha')\nexcept Exception: pass\n")
time.sleep(4)
HL.in_node('a', "try:\n    st.add_account('pkha', 'fulladmin', %r, must_change=0)\nexcept Exception: pass\n" % PW)
time.sleep(3)
for n in 'ab':
    if not HL.login(n):
        HL.stop(n); HL.start(n); HL.login(n)
HOST = 'otp.firma.cz'
ORIGIN = 'https://' + HOST


def call(n, path, body=None, tok=None, host=HOST):
    hd = {'X-Otp-Token': HL.TOK.get(n, ''), 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1',
          'X-Otp-Host': host}
    if tok:
        hd['X-Otp-Session'] = tok
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (HL.PORT[n], path),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=hd, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def password(n):
    st, got = call(n, '/api/auth/login', {'name': 'pkha', 'password': PW})
    return got.get('token') if st == 200 else None


def settings(**kw):
    st, _ = HL.call('a', '/api/settings', {'settings': kw})
    time.sleep(4)
    return st


HL.ok('the second step on, the passkey on', settings(admin_2fa=1, admin_2fa_passkey=1) == 200)
for n in 'ab':
    # the other node takes the setting at its next look (a few seconds, more under load)
    for _ in range(30):
        t = password(n)
        st, got = call(n, '/api/auth/mfa', tok=t)
        if 'passkey' in (got.get('methods') or []):
            break
        call(n, '/api/auth/logout', {}, tok=t)
        time.sleep(1)
    HL.ok('node %s: the passkey offered after the password' % n, 'passkey' in (got.get('methods') or []) and got.get('stage') == 'enrol', got)
    st, got = call(n, '/api/auth/mfa', tok=t, host='192.168.40.10')
    HL.ok('node %s: by an address not offered' % n, 'passkey' not in (got.get('methods') or []), got)
    call(n, '/api/auth/logout', {}, tok=t)

dev = Device('es')
t = password('a')
st, opts = call('a', '/api/auth/mfa', {'action': 'enrol_start', 'kind': 'passkey'}, tok=t)
HL.ok('set up: the question asked on a', st == 200 and opts.get('publicKey', {}).get('rp', {}).get('id') == HOST, (st, opts))
time.sleep(2)
st, got = call('b', '/api/auth/mfa', {'action': 'enrol_confirm', **dev.create(opts, ORIGIN)}, tok=t)
HL.ok('...answered on b: set up, signed in', st == 200 and got.get('done') and got.get('token'), (st, got))
full = got.get('token')
st, got = call('a', '/api/auth/whoami', tok=full)
HL.ok('...the sign-in good on a too', st == 200 and (got.get('who') or {}).get('role') == 'fulladmin', (st, got))
rec = HL.dbq('b', "SELECT v FROM meta WHERE k = 'adm2fa:pkha'")
HL.ok('...the passkey kept on b (its public half, no secret)', '"passkey"' in rec and '"pub"' in rec and HOST in rec, rec[:200])
call('a', '/api/auth/logout', {}, tok=full)

for first, second in (('b', 'a'), ('a', 'b')):
    t = password(first)
    st, got = call(first, '/api/auth/mfa', tok=t)
    HL.ok('sign-in on %s: the passkey asked, for %s' % (first, HOST), got.get('stage') == 'check' and got.get('kind') == 'passkey' and got.get('hosts') == [HOST], got)
    st, o = call(first, '/api/auth/mfa', {'action': 'pk_begin'}, tok=t)
    HL.ok('...the question on %s' % first, st == 200 and o.get('publicKey', {}).get('allowCredentials'), (st, o))
    ans = dev.get(o, ORIGIN)
    time.sleep(2)
    st, got = call(second, '/api/auth/mfa', {'action': 'check', **ans}, tok=t)
    HL.ok('...answered on %s: in' % second, st == 200 and got.get('done'), (st, got))
    tok2 = got.get('token')
    st, got = call(first, '/api/auth/mfa', {'action': 'check', **ans}, tok=t)
    HL.ok('...the same answer again on %s: refused' % first, st in (400, 401, 409), (st, got))
    # a second sign-in with the same answer (the question taken once, on both nodes)
    t2 = password(first)
    call(first, '/api/auth/mfa', {'action': 'pk_begin'}, tok=t2)
    st, got = call(second, '/api/auth/mfa', {'action': 'check', **ans}, tok=t2)
    HL.ok('...an old answer for a new sign-in on %s: refused' % second, st != 200, (st, got))
    call(first, '/api/auth/logout', {}, tok=t2)
    call(first, '/api/auth/logout', {}, tok=tok2)

# 1.0.257: the passkeys of the account signed in, across the nodes - added on a, answered on b,
# named on a, seen on b, the last one kept
if os.path.exists(HL.V + '/web/assets/admin.js') and '/api/auth/passkeys' in open(HL.V + '/otp.py').read():
    t = password('a')
    st, o = call('a', '/api/auth/mfa', {'action': 'pk_begin'}, tok=t)
    st, got = call('b', '/api/auth/mfa', {'action': 'check', **dev.get(o, ORIGIN)}, tok=t)
    full = got.get('token')
    st, l = call('b', '/api/auth/passkeys', tok=full)
    HL.ok('Your account (b): the passkey listed', st == 200 and l.get('mine') and len(l.get('keys') or []) == 1 and l.get('can_add'), l)
    rdev2 = Device('rs')
    st, opts = call('a', '/api/auth/passkeys', {'action': 'add_begin'}, tok=full)
    HL.ok('...another one asked for on a', st == 200 and opts.get('publicKey', {}).get('excludeCredentials'), (st, opts))
    time.sleep(2)
    st, got = call('b', '/api/auth/passkeys', {'action': 'add_finish', **rdev2.create(opts, ORIGIN)}, tok=full)
    HL.ok('...its answer taken on b: two', st == 200 and len(got.get('keys') or []) == 2, (st, got))
    new_id = [k['id'] for k in got.get('keys') or [] if k['id'] != l['keys'][0]['id']][0]
    st, got = call('a', '/api/auth/passkeys', {'action': 'rename', 'id': new_id, 'name': 'Windows Hello'}, tok=full)
    time.sleep(2)
    st, l2 = call('b', '/api/auth/passkeys', tok=full)
    HL.ok('...named on a, seen on b', any(k['name'] == 'Windows Hello' for k in l2.get('keys') or []), l2)
    call('b', '/api/auth/logout', {}, tok=full)
    t = password('b')
    st, o = call('b', '/api/auth/mfa', {'action': 'pk_begin'}, tok=t)
    st, got = call('a', '/api/auth/mfa', {'action': 'check', **rdev2.get(o, ORIGIN)}, tok=t)
    HL.ok('...the new one signs in (asked on b, answered on a)', st == 200 and got.get('done'), (st, got))
    full = got.get('token')
    st, got = call('a', '/api/auth/passkeys', {'action': 'delete', 'id': new_id}, tok=full)
    HL.ok('...taken away on a: one left', st == 200 and len(got.get('keys') or []) == 1, (st, got))
    st, got = call('b', '/api/auth/passkeys', {'action': 'delete', 'id': l['keys'][0]['id']}, tok=full)
    HL.ok('...the last one refused on b', st == 409, (st, got))
    call('a', '/api/auth/logout', {}, tok=full)

# a copied device: the counter back (an RS key counts)
rdev = Device('ed')
HL.call('a', '/api/users', {'action': 'mfa_reset', 'name': 'pkha'})
time.sleep(2)
t = password('a')
st, opts = call('a', '/api/auth/mfa', {'action': 'enrol_start', 'kind': 'passkey'}, tok=t)
time.sleep(2)                       # the question over to b first
st, got = call('b', '/api/auth/mfa', {'action': 'enrol_confirm', **rdev.create(opts, ORIGIN)}, tok=t)
HL.ok('an Ed25519 passkey set up across the nodes', st == 200 and got.get('done'), (st, got))
call('b', '/api/auth/logout', {}, tok=got.get('token'))
t = password('b')
st, o = call('b', '/api/auth/mfa', {'action': 'pk_begin'}, tok=t)
st, got = call('a', '/api/auth/mfa', {'action': 'check', **rdev.get(o, ORIGIN)}, tok=t)
HL.ok('...in, its counter kept', st == 200, (st, got))
call('a', '/api/auth/logout', {}, tok=got.get('token'))
time.sleep(2)
t = password('a')
st, o = call('a', '/api/auth/mfa', {'action': 'pk_begin'}, tok=t)
st, got = call('b', '/api/auth/mfa', {'action': 'check', **rdev.get(o, ORIGIN, count=1)}, tok=t)
HL.ok('...the counter back on the other node: refused as copied', st != 200 and 'counter' in json.dumps(got), (st, got))
ev = HL.dbq('a', "SELECT words FROM events WHERE words LIKE 'pkha: the passkey was refused%' ORDER BY id DESC LIMIT 1")
HL.ok('...said in the events', 'counter' in ev, ev)

# reset by a full administrator on a: b asks to set it up again
st, got = HL.call('a', '/api/users', {'action': 'mfa_reset', 'name': 'pkha'})
HL.ok('reset on a', st == 200, (st, got))
time.sleep(2)
t = password('b')
st, got = call('b', '/api/auth/mfa', tok=t)
HL.ok('...b asks to set it up again', got.get('stage') == 'enrol', got)
call('b', '/api/auth/logout', {}, tok=t)

HL.ok('back: the second step off', settings(admin_2fa=0, admin_2fa_passkey=0) == 200)
for i in range(30):
    t = password('b')
    st, got = call('b', '/api/auth/whoami', tok=t)
    if (got.get('who') or {}).get('role'):
        break
    time.sleep(1)
print('b took the setting in %d s' % (i + 4))
HL.ok('...the password alone signs in, as before', (got.get('who') or {}).get('role') == 'fulladmin', got)
HL.call('a', '/api/users', {'action': 'delete', 'name': 'pkha'})
HL.done()
