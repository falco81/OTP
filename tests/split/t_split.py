# t_split.py VERSION - when the nodes lose each other (1.0.218), in-process on SQLite with the
# other node's database and the arbiter played by the test: the decision of every mode, stepping
# aside as maintenance (RADIUS and the VIP), half the tries, changes frozen on all but the
# preferred node, recovery codes only with the other node asked, the report afterwards, the
# arbiter's ping and TCP, the card's API.
import os, sys, json, time, tempfile, socket, threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.218'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-split-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'spa'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
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
st.set_meta('node:spa', json.dumps({'at': time.time(), 'address': '192.0.2.1'}))
st.set_meta('node:spb', json.dumps({'at': time.time(), 'address': '192.0.2.2'}))

# ---- the decision of every mode -------------------------------------------------------------
dec = otp.split_decide
ok('together: every mode answers', all(dec(m, False, x, p)[0] == 'serve' for m in otp.SPLIT_MODES
                                       for x in (True, False, None) for p in (True, False)))
ok('off: both answer while apart', dec('off', True, False, False)[0] == 'serve')
ok('priority: the preferred answers, the other steps aside',
   dec('priority', True, None, True)[0] == 'serve' and dec('priority', True, True, False)[0] == 'aside')
ok('arbiter: reached - answers; not reached - steps aside; cannot be asked - answers',
   dec('arbiter', True, True, False)[0] == 'serve' and dec('arbiter', True, False, True)[0] == 'aside'
   and dec('arbiter', True, None, False)[0] == 'serve')

# ---- not a replicating pair: nothing at all ---------------------------------------------------
otp.split_step(st, now=1000.0, peer='down', arbiter=False)
ok('one node (or one shared database): never apart, never aside', not otp.split_apart() and not otp.split_aside()
   and not otp.maintenance_now(st).get('on'))

# ---- a replicating pair ----------------------------------------------------------------------
otp.CONFIG.update(ha_mode='replicated', ha_peer='192.0.2.2', ha_slot=2, split_after_s=20)
otp.SPLIT.update(peer_ok_at=1000.0, apart_since=0.0, role='serve')


def step(t, peer=True, arb=True):
    otp.split_step(st, now=t, peer=peer, arbiter=arb)


# ---- "as until now": nothing of it runs at all ------------------------------------------------
asked = []
real_probe = otp._split_peer_probe
otp._split_peer_probe = lambda: asked.append(1) or 'down'
otp.CONFIG.update(split_mode='off', split_scratch=0, split_halve=0, split_freeze=0, split_report=0)
ok('as until now is the default: off, every switch off', all(
    otp.DEFAULTS[k] in ('off', 0) for k in ('split_mode', 'split_scratch', 'split_halve', 'split_freeze',
                                            'split_report')))
for t in (1000, 1030, 1060, 1200):
    otp.split_step(st, now=float(t))
ok('as until now: the other node never asked, never apart, nothing aside, no row written, not engaged',
   not asked and not otp.split_apart() and not otp.split_aside() and not otp.split_engaged()
   and st.get_meta('split:state:spa') is None)
st.set_meta('node:spb', json.dumps({'at': time.time(), 'address': '192.0.2.2'}))
ok('... the tries as set, nothing frozen, no alert of it, maintenance not touched',
   otp.split_limit('lockout_after') == int(otp.CONFIG.get('lockout_after') or 0) and
   otp.split_refuses('POST', '/api/tokens') == '' and
   not any(k.startswith('split') for k in otp.alert_problems(st)) and not otp.maintenance_now(st).get('on'))
otp._split_peer_probe = real_probe
otp.SPLIT.update(peer_ok_at=1000.0, apart_since=0.0, role='serve')

otp.CONFIG['split_mode'] = 'priority'
step(1005, peer='connection refused')
ok('priority, the other node gone for 5 s of 20: not apart yet', not otp.split_apart() and not otp.split_aside())
step(1030, peer='connection refused')
ok('... 30 s: apart, and this node (not the preferred one) steps aside', otp.split_apart() and otp.split_aside())
m = otp.maintenance_now(st)
ok('... as maintenance nobody asked for: RADIUS silent, the VIP address goes (%s)' % m.get('why'),
   m.get('on') and m.get('split'))
ok('... its own row says so, for the other node and the pages',
   json.loads(st.get_meta('split:state:spa'))['role'] == 'aside')
step(1032, peer=True)
ok('the other node\'s database answers again: together, answering', not otp.split_apart() and not otp.split_aside()
   and not otp.maintenance_now(st).get('on'))
otp.CONFIG['split_prefer'] = 'spa'
step(1040, peer='x'); step(1070, peer='x')
ok('the preferred node itself: answers while apart', otp.split_apart() and not otp.split_aside())
step(1071, peer=True)
otp.CONFIG['split_prefer'] = ''

otp.CONFIG['split_mode'] = 'arbiter'
step(1100, peer='x', arb=True); step(1130, peer='x', arb=True)
ok('arbiter: apart, the arbiter reached - answers', otp.split_apart() and not otp.split_aside())
step(1132, peer='x', arb=False)
ok('... the arbiter lost too - this node is the one cut off: steps aside', otp.split_aside())
step(1134, peer='x', arb=True)
ok('... the arbiter back: answers again', not otp.split_aside())
step(1136, peer=True)

# ---- half the tries, changes frozen -----------------------------------------------------------
otp.CONFIG.update(split_mode='off', rate_limit_tries=3, lockout_after=10, split_halve=1, split_freeze=1)
ok('together: the tries as set', otp.split_limit('lockout_after') == 10 and otp.split_limit('rate_limit_tries') == 3)
ok('... and nothing frozen', otp.split_refuses('POST', '/api/tokens') == '')
step(1200, peer='x'); step(1230, peer='x')
ok('apart with "half": 5 of 10 to the lockout, 2 of 3 to the pause',
   otp.split_limit('lockout_after') == 5 and otp.split_limit('rate_limit_tries') == 2)
said = otp.split_refuses('POST', '/api/tokens')
ok('apart with "freeze", not the preferred node: a change refused (%s)' % said[:60], 'changes are made on' in said)
ok('... reading, signing in and this card itself are not',
   otp.split_refuses('GET', '/api/tokens') == '' and otp.split_refuses('POST', '/api/auth/login') == ''
   and otp.split_refuses('POST', '/api/split') == '')
otp.CONFIG['split_prefer'] = 'spa'
ok('... the preferred node: changes go on', otp.split_refuses('POST', '/api/tokens') == '')
otp.CONFIG['split_prefer'] = ''
tk = otp.Tokens(st)
g = tk.enroll('ana', 't')
otp.CONFIG['rate_limit_tries'] = 0          # no pause: the lockout alone
for i in range(5):
    tk.check('ana', '000000', how='t')
row = st.token('ana')
ok('... five wrong codes while apart: locked at half the tries (%s)' % row.get('failures'),
   float(row.get('locked_until') or 0) > time.time())
st.db.run("UPDATE tokens SET failures = 0, fail_times = '[]', locked_until = NULL WHERE name = 'ana'")
otp.CONFIG['rate_limit_tries'] = 3
step(1240, peer=True)
ok('together again: the tries as set, nothing frozen', otp.split_limit('lockout_after') == 10 and
   otp.split_refuses('POST', '/api/tokens') == '')

# ---- recovery codes only with the other node asked ---------------------------------------------
otp.CONFIG.update(split_scratch=1, split_halve=0, split_freeze=0)
step(1300, peer='x'); step(1330, peer='x')
code = g['scratch'][0]
got = tk.check('ana', code, how='t')
row = st.token('ana')
ok('apart with "recovery codes only with the other node asked": refused, not counted, not used up (%s)' % got[1],
   got[0] is False and got[1] == otp.SPLIT_SAY_SCRATCH and int(row.get('failures') or 0) == 0
   and int(row.get('scratch_left') or 0) == len(g['scratch']))
step(1340, peer=True)
real = otp._once_peer_has
otp._once_peer_has = lambda k, me, store=None: None
got = tk.check('ana', code, how='t')
ok('... together but the other node cannot be asked this moment: refused too', got[0] is False and
   got[1] == otp.SPLIT_SAY_SCRATCH)
otp._once_peer_has = lambda k, me, store=None: False
got = tk.check('ana', code, how='t')
ok('... the other node asked: let in', got[0] is True, got)
otp.CONFIG['split_scratch'] = 0

# ---- the report afterwards ---------------------------------------------------------------------
otp._once_peer_has = lambda k, me, store=None: None        # nobody to ask: the codes written down
otp.CONFIG.update(split_report=1)
code2 = g['scratch'][1]
got = tk.check('ana', code2, how='t')
took = st.db.rows("SELECT k, v FROM meta WHERE k LIKE 'split:took:%'")
ok('a code let in without the other node asked: written down for the report (%d)' % len(took),
   got[0] is True and len(took) >= 1)
# the other node let the same one in on its half: its row, as replication brings it
for r in took:
    st.set_meta(r['k'].replace('split:took:spa:', 'split:took:spb:'), r['v'])
otp._once_peer_has = real
otp.CONFIG['split_prefer'] = 'spa'
rep = otp.split_report(st, now=2000.0)
ok('the report: the code let in on both halves found (%s)' % (rep and rep.get('twice')),
   rep and rep['twice_n'] >= 1 and rep['twice'][0]['name'] == 'ana')
ok('... kept for the card, the rows gone, an alert for a day',
   json.loads(st.get_meta('split:report'))['twice_n'] >= 1 and
   not st.db.rows("SELECT k FROM meta WHERE k LIKE 'split:took:%'"))
st.set_meta('split:report', json.dumps(dict(json.loads(st.get_meta('split:report')), at=time.time())))
probs = otp.alert_problems(st)
ok('... and the alerts say it', 'split:twice' in probs, list(probs))
otp.CONFIG['split_prefer'] = ''

# ---- the alert while apart ---------------------------------------------------------------------
step(2100, peer='x'); step(2130, peer='x')
st.set_meta('split:state:spa', json.dumps(otp.split_state_here()))     # as the daemon writes it, now
probs = otp.alert_problems(st)
ok('apart: an alert of this node\'s', any(k.startswith('split:spa') for k in probs), list(probs))
step(2140, peer=True)

# ---- the arbiter: ping and TCP -----------------------------------------------------------------
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(5)
port = srv.getsockname()[1]
got, verdict = otp.split_arbiter_check([('127.0.0.1', port)])
ok('an arbiter over TCP that listens: reached', verdict is True, got)
srv.close()
got, verdict = otp.split_arbiter_check([('127.0.0.1', port)])
ok('... one that refuses: there all the same (it answered)', verdict is True, got)
got, verdict = otp.split_arbiter_check([('192.0.2.254', 9)])
ok('... one that does not answer: not reached', verdict is False, got)
pg = otp.split_ping('127.0.0.1')
ok('ping of 127.0.0.1: answered, or "cannot be asked" said - never "not reached" (%s)' % (pg,),
   pg[0] is True or pg[0] is None)
ok('the arbiters written: addresses, name:port, [v6]:port; nonsense refused',
   otp.split_targets_parse('192.0.2.1, gw.example.cz:443 [2001:db8::1]:53 2001:db8::2') ==
   [('192.0.2.1', None), ('gw.example.cz', 443), ('2001:db8::1', 53), ('2001:db8::2', None)])
try:
    otp.split_targets_parse('a b c d e f')
    five = False
except ValueError:
    five = True
ok('... five at most', five)
ok('the default gateway read from /proc/net/route (%s)' % otp.default_gateway(), isinstance(otp.default_gateway(), str))

# ---- the card's API ----------------------------------------------------------------------------


class H(object):
    def __init__(self, body=None):
        self.store, self.d, self._b = st, d, body or {}

    def me(self, role=None):
        return {'name': 'admin', 'role': 'fulladmin'}

    def body(self):
        return self._b


v = otp.ROUTES[('GET', '/api/split')](H())
ok('GET /api/split: active, both nodes, the conf', v['active'] and len(v['nodes']) == 2 and
   v['conf']['split_mode'] == 'off', v)
try:
    otp.ROUTES[('POST', '/api/split')](H({'action': 'save', 'conf': {'split_mode': 'arbiter'}}))
    refused = ''
except otp.ApiError as e:
    refused = str(e)
ok('saving "arbiter" without the arbiter tried from every node: refused', 'try the arbiter' in refused, refused)
r = otp.ROUTES[('POST', '/api/split')](H({'action': 'save', 'checked': True,
                                           'conf': {'split_mode': 'priority', 'split_prefer': 'spb',
                                                    'split_scratch': 1, 'split_after_s': 30},
                                           'arbiter': {'spa': '192.0.2.1', 'spb': 'gw.example.cz:443'}}))
saved = st.settings_saved()
ok('saved: the mode, the preferred node, a switch, each node\'s own arbiter',
   otp.CONFIG.get('split_mode') == 'priority' and otp.CONFIG.get('split_prefer') == 'spb'
   and saved.get('split_arbiter@spb') == 'gw.example.cz:443', saved)
try:
    otp.ROUTES[('POST', '/api/split')](H({'action': 'save', 'checked': True, 'arbiter': {'spa': 'x y z q w e'}}))
    bad = ''
except otp.ApiError as e:
    bad = str(e)
ok('... a wrong arbiter refused (%s)' % bad, 'five' in bad)
src = open(V + '/otp.py').read()
J = open(V + '/web/assets/admin.js').read()
P = open(V + '/web/admin/index.php').read()
ok('the card on the pages: three choices, four switches, the table of what happens, Try it',
   'id="ha-split-card"' in P and 'function drawSplit()' in J and "'split_freeze'" in J and
   'function splitScenarios()' in J and "action: 'try'" in J)
print('ALL %d / %d' % (sum(R), len(R)))
