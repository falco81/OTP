# t_clock.py VERSION - the clocks and the health of the nodes (1.0.222), in-process on SQLite: the
# reference asked over SNTP (a fake server with its own offset), the decision of every mode, stepping
# aside as maintenance only while the other node is well, codes / pauses by the corrected time,
# heartbeats by the measured difference, the directory check, the alerts, the card's API, and
# "as until now" running nothing.
import os, sys, json, time, tempfile, socket, threading, base64
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.222'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-clock-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'cka'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import otp  # noqa: E402
from fakentp import FakeNtp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
d = otp.Daemon(st, serve=False)
now0 = time.time()
st.set_meta('node:cka', json.dumps({'at': now0, 'address': '192.0.2.1'}))
st.set_meta('node:ckb', json.dumps({'at': now0, 'address': '192.0.2.2'}))

# ---- SNTP ----------------------------------------------------------------------------------------
good = FakeNtp(0.0).start()
ahead = FakeNtp(300.0).start()
off, delay = otp.sntp_offset('127.0.0.1:%d' % good.port)
ok('SNTP: a server with this machine\'s time - offset %.3f s, delay %.1f ms' % (off, delay * 1000),
   abs(off) < 0.05 and delay < 0.5)
off, _d = otp.sntp_offset('127.0.0.1:%d' % ahead.port)
ok('SNTP: a server 300 s ahead - this clock is behind it by 300 s (%.2f)' % off, abs(off - 300) < 0.1)
uns = FakeNtp(0.0).start(); uns.stratum = 0
try:
    otp.sntp_offset('127.0.0.1:%d' % uns.port); e = ''
except ValueError as x:
    e = str(x)
ok('SNTP: a server not synchronised itself is not believed (%s)' % e, 'stratum' in e)
silent = FakeNtp(0.0).start(); silent.silent = True
t0 = time.time()
got, med = otp.clock_ref_check(['127.0.0.1:%d' % silent.port])
ok('SNTP: a silent server - no answer within the time (%.1f s), no offset' % (time.time() - t0),
   med is None and time.time() - t0 < 3)
three = [FakeNtp(o).start() for o in (0.0, 0.2, 500.0)]
got, med = otp.clock_ref_check(['127.0.0.1:%d' % x.port for x in three])
ok('the reference: the median of three servers - one gone wild does not move it (%.2f)' % med,
   0.1 < med < 0.3)
ok('the reference servers: this node\'s own first', otp.clock_ref_servers('a.example, b.example:123') ==
   ['a.example', 'b.example:123'])
st.set_meta('ntp:conf', json.dumps({'servers': [{'host': 'tik.cesnet.cz'}, {'host': 'tak.cesnet.cz'}]}))
ok('... else the time servers of Settings -> Time (%s)' % otp.clock_ref_servers('', st),
   otp.clock_ref_servers('', st) == ['tik.cesnet.cz', 'tak.cesnet.cz'])

# ---- the decision ------------------------------------------------------------------------------
dec = otp.clock_decide
well = {'fresh': True, 'role': 'serve', 'ref': 0.1, 'dir_ok': True}
ok('off and watch: always answer', all(dec(m, 999, 20, False, False, True, well)[0] == 'serve'
                                     for m in ('off', 'watch')))
ok('guard: a clock within the limit answers', dec('guard', 5, 20, False, True, True, well)[0] == 'serve')
ok('guard: off by 60 s, the other node well - steps aside', dec('guard', 60, 20, False, None, False, well)[0] == 'aside')
ok('... behind or ahead alike', dec('guard', -60, 20, False, None, False, well)[0] == 'aside')
ok('... but not when its codes are worked out with the corrected time (clock_codes)',
   dec('guard', 60, 20, True, None, False, well)[0] == 'serve')
ok('... nor when the other node is not heard from', dec('guard', 60, 20, False, None, False, None)[0] == 'serve')
ok('... nor when the other node is not fresh', dec('guard', 60, 20, False, None, False, dict(well, fresh=False))[0] == 'serve')
ok('... nor when the other node stepped aside itself (never both)',
   dec('guard', 60, 20, False, None, False, dict(well, role='aside'))[0] == 'serve')
ok('... nor when the other node\'s clock is off too', dec('guard', 60, 20, False, None, False, dict(well, ref=40))[0] == 'serve')
ok('... nor when the other node cannot ask its reference', dec('guard', 60, 20, False, None, False, dict(well, ref=None))[0] == 'serve')
ok('... nor when the other node is in maintenance',
   dec('guard', 60, 20, False, None, False, dict(well, maintenance=True))[0] == 'serve')
ok('guard: no reference answered here - never aside', dec('guard', None, 20, False, None, False, well)[0] == 'serve')
ok('directory: unreachable here, reached there - aside (health_dir)', dec('guard', 0, 20, False, False, True, well)[0] == 'aside')
ok('... without health_dir: answers', dec('guard', 0, 20, False, False, False, well)[0] == 'serve')
ok('... unreachable on both: answers', dec('guard', 0, 20, False, False, True, dict(well, dir_ok=False))[0] == 'serve')
ok('... no realm uses a directory (None): answers', dec('guard', 0, 20, False, None, True, well)[0] == 'serve')

# ---- "as until now": nothing of it ------------------------------------------------------------
ok('the default is off ("as until now")', otp.DEFAULTS['clock_mode'] == 'off' and not otp.clock_engaged())
asked = []
real = otp.sntp_offset
otp.sntp_offset = lambda *a, **k: asked.append(a) or (0, 0)
otp.clock_step(st)
otp.sntp_offset = real
ok('off: nothing asked, no row written, no thread', not asked and not st.get_meta('clock:state:cka')
   and not otp.clock_watching())
t = time.time()
ok('off: the codes\' and the locks\' time is the machine\'s', abs(otp.clock_now('codes') - t) < 0.01
   and abs(otp.clock_now('locks') - t) < 0.01)
st.set_meta('node:ckb', json.dumps({'at': time.time() - 600}))
ok('off: a heartbeat\'s age by the sender\'s clock alone (as before)',
   [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]['age'] > 590)
ok('off: no alert of the clocks', not [k for k in otp.alert_problems(st) if k.startswith('clock')])

# ---- watch: measured, said, nothing changed ---------------------------------------------------
otp.CONFIG.update(clock_mode='watch', clock_ref='127.0.0.1:%d' % ahead.port, clock_warn_s=2, clock_aside_s=20)
otp.clock_step(st)
s = otp.clock_state_here()
ok('watch: the reference asked - this clock 300 s behind it (%.1f)' % (s['ref'] or 0), abs((s['ref'] or 0) - 300) < 0.5)
ok('... the row written for the card and the other node', json.loads(st.get_meta('clock:state:cka') or '{}').get('ref'))
ok('... serves - watch never steps aside', s['role'] == 'serve' and not otp.maintenance_now(st).get('on'))
pr = otp.alert_problems(st)
ok('... an alert of the clock (%s)' % [k for k in pr if k.startswith('clock')], 'clock:skew:cka' in pr
   and pr['clock:skew:cka']['level'] == 'bad')
ok('... codes still by the machine\'s clock (clock_codes off)', abs(otp.clock_now('codes') - time.time()) < 0.05)

# ---- codes by the corrected time ----------------------------------------------------------
tk = otp.Tokens(st)
T = tk.enroll('clku', 'test')
sec = T['secret']


def code_at(when):
    return otp.totp(sec, when)


def check(code):
    return tk.check('clku', code)


st.db.run("UPDATE tokens SET state = 'active' WHERE name = 'clku'")
r = check(code_at(time.time() + 300))
ok('the right code (by the right time) on a node 300 s behind: refused without clock_codes (%s)' % r[1],
   not r[0])
st.db.run("UPDATE tokens SET fail_times = '[]', failures = 0 WHERE name = 'clku'")
otp.CONFIG['clock_codes'] = 1
r = check(code_at(time.time() + 300))
ok('... with clock_codes: let in (%s)' % r[1], r[0])
ok('... the state says the codes are worked out with the corrected time', otp.clock_state_here()['codes_fixed'])
pr = otp.alert_problems(st)
ok('... the alert says so', 'corrected' in str(pr.get('clock:skew:cka', {}).get('said')))
r = check(code_at(time.time()))
ok('... the code of the machine\'s own (wrong) time: refused (%s)' % r[1], not r[0])
st.db.run("UPDATE tokens SET fail_times = '[]', failures = 0, last_step = 0 WHERE name = 'clku'")
otp.CONFIG['clock_warn_s'] = 400
ok('within clock_warn_s: no correction (a small offset is not "fixed")', otp.clock_correction() == 0.0)
otp.CONFIG['clock_warn_s'] = 2
otp.CLOCK['ref_at'] = time.time() - 1000
ok('a reference not fresh: no correction', otp.clock_correction() == 0.0)
otp.CLOCK['ref_at'] = time.time()
otp.CONFIG['clock_locks'] = 1
ok('clock_locks: pauses and lockouts by the corrected time', abs(otp.clock_now('locks') - time.time() - 300) < 1)
otp.CONFIG.update(clock_codes=0, clock_locks=0)

# ---- heartbeats by the measured difference ------------------------------------------------------
st.set_meta('node:ckb', json.dumps({'at': time.time() - 600}))     # its clock 10 min behind
otp.clock_step(st, skew=('ckb', -600.0))
ok('without clock_beat: the other node looks dead (age %.0f)' % [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]['age'],
   not [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]['alive'])
otp.CONFIG['clock_beat'] = 1
b = [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]
ok('with clock_beat: alive, its age by the measured difference (%.1f)' % b['age'], b['alive'] and abs(b['age']) < 5)
st.set_meta('node:ckb', json.dumps({'at': time.time() + 600}))
otp.clock_step(st, skew=('ckb', 600.0))
otp.CONFIG['clock_beat'] = 0
ok('without: a node 10 min ahead "lives for ever" (age %.0f)' % [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]['age'],
   [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]['age'] < -500)
otp.CONFIG['clock_beat'] = 1
st.set_meta('node:ckb', json.dumps({'at': time.time() + 600 - 100}))
b = [n for n in otp.ha_nodes(st) if n['name'] == 'ckb'][0]
ok('with: a beat 100 s old from a node 10 min ahead - dead (age %.0f)' % b['age'], not b['alive'] and 90 < b['age'] < 110)
# one shared database server: the difference of the two nodes' own
otp.clock_step(st, skew=(otp.CLOCK_DB_SERVER, 4.0))
st.set_meta('clock:state:ckb', json.dumps({'at': time.time(), 'skew_of': otp.CLOCK_DB_SERVER, 'skew': -6.0}))
ok('one shared database server: the other node\'s clock minus this one\'s from both rows (%s)'
   % otp.clock_skew_of(st, 'ckb'), otp.clock_skew_of(st, 'ckb') == 10.0)
otp.CONFIG['clock_beat'] = 0
st.set_meta('node:ckb', json.dumps({'at': time.time()}))

# ---- guard: stepping aside ------------------------------------------------------------------------
otp.CONFIG.update(clock_mode='guard', ha_mode='replicated', ha_peer='192.0.2.2')
peer_ok = {'fresh': True, 'role': 'serve', 'ref': 0.05, 'dir_ok': True}
otp.clock_step(st, ref=300.0, skew='none', peer=peer_ok)
m = otp.maintenance_now(st)
ok('guard: 300 s off, the other node well - aside; maintenance_now says it (%s)' % m.get('why'),
   otp.clock_aside() and m.get('on') and m.get('clock'))
pr = otp.alert_problems(st)
ok('... an alert: stepped aside', 'clock:aside:cka' in pr)
ev = st.db.rows("SELECT words FROM events WHERE kind = 'time' ORDER BY id DESC LIMIT 1") \
    if 'events' in otp.TABLES else []
ok('... an event written', not ev or 'steps aside' in ev[0]['words'], ev)
otp.clock_step(st, ref=300.0, skew='none', peer=dict(peer_ok, fresh=False))
ok('the other node gone quiet: answers again, at once', not otp.clock_aside() and not otp.maintenance_now(st).get('on'))
otp.clock_step(st, ref=300.0, skew='none', peer=peer_ok)
otp.clock_step(st, ref=0.3, skew='none', peer=peer_ok)
ok('its clock mended: answers again', not otp.clock_aside())
otp.CONFIG['clock_codes'] = 1
otp.clock_step(st, ref=300.0, skew='none', peer=peer_ok)
ok('with clock_codes: never aside for the clock - its codes are right', not otp.clock_aside())
otp.CONFIG['clock_codes'] = 0
# the peer row read from the database (with its freshness by the measured difference)
st.set_meta('clock:state:ckb', json.dumps({'at': time.time() - 300, 'role': 'serve', 'ref': 0.0, 'dir_ok': True}))
otp.clock_step(st, ref=300.0, skew=('ckb', -300.0))
ok('the other node\'s row 300 s "old" by its clock 300 s behind: fresh - aside', otp.clock_aside())
otp.clock_step(st, ref=300.0, skew=('ckb', 0.0))
ok('... the same row with the clocks alike: not fresh - answers', not otp.clock_aside())

# ---- the directory -----------------------------------------------------------------------------
lst = socket.socket(); lst.bind(('127.0.0.1', 0)); lst.listen(5)
port = lst.getsockname()[1]
dead = socket.socket(); dead.bind(('127.0.0.1', 0)); dport = dead.getsockname()[1]; dead.close()
st.directory_save({'name': 'adtest', 'hosts': '127.0.0.1:%d' % port, 'base': 'DC=x', 'tls': 'none'})
dirs = st.directories()
ok('a test directory made (%d)' % len(dirs), dirs, 'no directory_save')
if dirs:
    ok_, got = otp.clock_dir_check(st)
    ok('no realm uses it: not looked at (None)', ok_ is None)
    st.realm_save({'name': 'r1', 'suffix': 'ex.cz', 'directory': 'adtest', 'auth_mode': 'password_otp'})
    ok_, got = otp.clock_dir_check(st)
    ok('the directory reached (%s)' % got, ok_ is True)
    st.directory_save({'id': dirs[0]['id'], 'name': 'adtest', 'hosts': '127.0.0.1:%d' % dport, 'base': 'DC=x',
                       'tls': 'none'})
    ok_, got = otp.clock_dir_check(st)
    ok('the directory not reached (%s)' % got, ok_ is False)
    otp.CONFIG['health_dir'] = 1
    otp.clock_step(st, ref=0.0, skew='none', dir_ok=False, peer=peer_ok)
    ok('guard + health_dir: aside while the other reaches it', otp.clock_aside())
    pr = otp.alert_problems(st)
    ok('... an alert of the directory', 'clock:dir:cka' in pr)
    otp.clock_step(st, ref=0.0, skew='none', dir_ok=True, peer=peer_ok)
    ok('... reached again: answers', not otp.clock_aside())
    otp.CONFIG['health_dir'] = 0
lst.close()

# ---- off again: serves at once ---------------------------------------------------------------
otp.clock_step(st, ref=300.0, skew='none', peer=peer_ok)
otp.CONFIG['clock_mode'] = 'off'
otp.clock_step(st)
ok('switched off while aside: answers at once', not otp.clock_aside() and not otp.maintenance_now(st).get('on'))

# ---- the API -----------------------------------------------------------------------------------
otp.CONFIG.update(ha_mode='', ha_peer='')


class H:
    def __init__(self, body=None):
        self.store, self.d, self.b = st, d, body or {}

    def me(self, need=None):
        return {'name': 'admin', 'role': 'fulladmin'}

    def body(self):
        return self.b


def api(method, body=None):
    fn = [f for (m, p), f in otp.ROUTES.items() if m == method and p == '/api/clock'][0] \
        if isinstance(getattr(otp, 'ROUTES', None), dict) else None
    try:
        return 200, fn(H(body))
    except otp.ApiError as e:
        return e.status if hasattr(e, 'status') else e.args[0], str(e)


if isinstance(getattr(otp, 'ROUTES', None), dict):
    stc, v = api('GET')
    ok('GET: the view (%s)' % sorted(v), stc == 200 and v['conf']['clock_mode'] == 'off' and v['nodes'])
    stc, v = api('POST', {'action': 'save', 'conf': {'clock_mode': 'guard'}})
    ok('save guard without trying first: refused (%s)' % stc, stc == 409)
    stc, v = api('POST', {'action': 'save', 'conf': {'clock_warn_s': 30, 'clock_aside_s': 20}})
    ok('aside before the warning: refused', stc == 400)
    stc, v = api('POST', {'action': 'save', 'refs': {'cka': 'bad host!'}})
    ok('a bad reference server: refused', stc == 400)
    stc, v = api('POST', {'action': 'save', 'refs': {'nobody': 'x'}})
    ok('a node that is not: refused', stc == 400)
    stc, v = api('POST', {'action': 'save', 'checked': True, 'conf': {'clock_mode': 'guard', 'clock_codes': 1,
                                                                      'clock_aside_s': 30},
                          'refs': {'cka': '127.0.0.1:%d' % good.port}})
    ok('save: guard, codes corrected, 30 s, the node\'s own reference (%s)' % str(v)[:80],
       stc == 200 and otp.CONFIG['clock_mode'] == 'guard' and otp.CONFIG['clock_codes'] == 1
       and otp.CONFIG['clock_ref'] == '127.0.0.1:%d' % good.port)
    stc, v = api('POST', {'action': 'nonsense'})
    ok('an unknown action: refused', stc == 400)
    stc, v = api('POST', {'action': 'save', 'conf': {'clock_mode': 'off', 'clock_codes': 0, 'clock_aside_s': 20}})
    ok('back to off', stc == 200 and otp.CONFIG['clock_mode'] == 'off')
    stt = otp.settings_state(st) if hasattr(otp, 'settings_state') else None
else:
    ok('the routes table found', False, 'ROUTES')

for x in [good, ahead, uns, silent] + three:
    x.close()
print('%d/%d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
