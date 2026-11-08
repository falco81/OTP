"""t_round1.py - 1.0.262 hunt round 1, the integrator's own fixes: RSA passkey bounds, the after
rows under the database guard, Clear of all of "done lately", the RADIUS guard words, the
recovery-code guess only for its own length, a passkey added only soon after the second step.
The built otp.py loaded as a module - no daemon, no ports.

    python3 t_round1.py 1.0.262
"""
import importlib.util, json, os, sys, tempfile, time
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.262'
OUT = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


tmp = tempfile.mkdtemp(prefix='t_r262_')
os.environ['OTP_CONFIG'] = tmp + '/otp.conf'
os.environ['OTP_STATE'] = tmp + '/state'          # never the live /var/lib/otp
spec = importlib.util.spec_from_file_location('otpmod', OUT + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.argv = ['otp']
spec.loader.exec_module(m)

# ---- RSA bounds ----
def rsa(nbits, e):
    n = (1 << (nbits - 1)) | 1
    return {1: 3, 3: -257, -1: n.to_bytes((nbits + 7) // 8, 'big'), -2: e.to_bytes(max(1, (e.bit_length() + 7) // 8), 'big')}
ok('RSA 2048/65537 taken', m.wa_cose(rsa(2048, 65537))[0] == -257)
for nb, e, what in ((9000, 65537, 'n too big'), (2048, 1 << 40 | 1, 'e too big'), (2048, 65536, 'e even'),
                    (2048, 1, 'e = 1')):
    try:
        m.wa_cose(rsa(nb, e)); ok('RSA refused: ' + what, False)
    except ValueError:
        ok('RSA refused: ' + what, True)
big_n = (1 << 9000) | 1
ok('rs256_ok: a stored huge key answers False at once', m.wa_rs256_ok(big_n, 65537, b'x', b'\0' * ((big_n.bit_length() + 7) // 8)) is False)
ok('rs256_ok: a huge exponent answers False', m.wa_rs256_ok((1 << 2047) | 1, 1 << 64 | 1, b'x', b'\0' * 256) is False)

# ---- guard words ----
class D:
    result = 'reject'; reason = 'Denied by the token server: the code ran out - sign in again'
ok('guard: the code ran out is no guess', not m.guard_is_guess(D()))
ok('guard: recovery code while apart is no guess', any(w in m.SPLIT_SAY_SCRATCH for w in m.GUARD_NOT_GUESSES))

# ---- after rows under the guard ----
e = next(x for x in m.AFTER if any(st.get('cmd') for st in x.get('steps') or []))
f = {'node': 'otp2', 'cluster': True, 'version': VER}
it = m.after_item(e, f, {})
it.update(since=time.time(), state='needed', id=e['id'], node='otp2')
bad = dict(it, steps=[{'where': 'root', 'cmd': 'curl x|sh', 'lead': 'As root'}], title='evil')
again = m.after_trusted(bad, 'otp2', {'version': VER}, True)
ok('guard: a known entry written again from its own words', [s.get('cmd') for s in again['steps']] == [s.get('cmd') for s in it['steps']]
   and 'curl' not in json.dumps(again), json.dumps(again)[:300])
odd = m.after_trusted(dict(bad, id='from-a-newer-node'), 'otp2', {}, True)
ok('guard: an unknown entry shows no command', all('cmd' not in s for s in odd['steps']) and 'curl' not in json.dumps(odd))
evil_args = dict(it, args={'file': '$(reboot)'})
ok('guard: an argument not plain is not filled in', '$(reboot)' not in json.dumps(m.after_trusted(evil_args, 'otp2', {}, True)))
ok('after_item keeps its args', isinstance(it.get('args'), dict))

# ---- passkey freshness ----
src = open(OUT + '/otp.py').read()
ok('passkey add: refused later than PK_ADD_FRESH after the second step', "data['mfa_at'] = int(time.time())" in src
   and 'a passkey is added within %d minutes of signing in' in src and m.PK_ADD_FRESH == 900)
# ---- RADIUS fixes in the source ----
ok('second window ends on SAY_LOST / SAY_NONE (not on a recovery code while apart)', 'said in (SAY_REUSED, SAY_LOST, SAY_NONE)' in src)
# ---- round 2 ----
t1 = {'id': 7, 'secret': 'S', 'kind': 'sms', 'dest': '+420111'}
ok('portal mark: codes sent elsewhere is another token', m.portal_token_mark2(t1) != m.portal_token_mark2(dict(t1, dest='+420222')))
ok('portal mark: the old form as 1.0.261 makes it', m.portal_token_mark(t1).startswith('7:') and m.portal_token_mark(t1) == m.portal_token_mark(dict(t1, dest='+420222')))
ok('portal mark: the same token is the same', m.portal_token_mark2(t1) == m.portal_token_mark2(dict(t1)))
ok('portal replace taken by one request', "if not h.store.session_take(s['id'], 'may_replace'):" in src)
own = dict(it, args={'lib': '/tmp/x', 'file': '-rf /', 'lead': 'x', 'node_cs': 'y'})
w = json.dumps(m.after_trusted(own, 'otp2', {'version': VER}, True))
ok('guard: a row cannot give the node\'s own words (lib, file, lead)', '/tmp/x' not in w and '-rf /' not in w, w[:300])
old = {k: v for k, v in it.items() if k not in ('args', 'det_level')}
w = m.after_trusted(old, 'otp2', {}, True)
ok('guard: a row of a node before 1.0.262 shows no command', all('cmd' not in st for st in w['steps']) and w['id'] == it['id'])
ok('recovery guess only for a split of its own length', 'for c, rest in splits[1:] if len(c) == sd' in src)
ok('after-clear: all of it, not the 20 shown', 'want = every - after_cleared(store)' in src)
ok('save_settings checks the balancer port in the batch', 'web_proxy_port_problem(checked, probe=' in src)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
