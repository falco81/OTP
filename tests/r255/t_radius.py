"""t_radius.py - 1.0.255: the RADIUS decisions (70_radius_server.py, 72_guard.py).
R1 password_otp never sends a password cut short to the directory when nothing after it is a
code, and a space after the code is no part of it. R2 after a code sent by mail/SMS (or from the
app) was taken, database trouble dropping the question or marking the token is logged, the
person still let in. R3 the realm's and the groups' reply built and measured before the code is
used. R4 this server's own trouble is not counted by the sign-in protection.
All of the daemon is loaded with exec (nothing started); the store, tokens and directory are stubs."""
import os, re, sys, json, time, hashlib
PARTS = '/home/claude/build/parts'
order = re.findall(r'parts/(\S+\.py)', open('/home/claude/build/build.sh').read())
src = ''.join(open(os.path.join(PARTS, f)).read() + '\n' for f in order)
g = {'__name__': 'otp_t255', '__file__': '/nonexistent/otp.py'}
exec(compile(src, 'otp.py', 'exec'), g)
R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


LOGS = []
g['log'] = lambda w, level='info': LOGS.append((level, w))
g['log_sparing'] = lambda k, w, level='warn', every=30: LOGS.append((level, w))


class Store:
    def __init__(self, realm, tok):
        self.realm, self.tok, self.meta = realm, tok, {}
        self.fail_drop = False

    def realm_for(self, user):
        return self.realm

    def token(self, name):
        return self.tok

    def drop_meta(self, k):
        if self.fail_drop:
            raise RuntimeError('database is locked')
        self.meta.pop(k, None)


class Tokens:
    def __init__(self, good):
        self.good, self.checked, self.fail_used = good, [], False

    def check(self, name, code, how='radius', src='', rid='', dry=False, quiet=False):
        self.checked.append((code, dry))
        if code == self.good:
            return True, 'Accepted', {}
        return False, g['SAY_BAD'], {}

    def blocked(self, name):
        return ''

    def used_sent(self, name, how):
        if self.fail_used:
            raise RuntimeError('database is locked')

    def _said(self, *a, **k):
        pass


class Dir:
    name = 'ad'

    def __init__(self):
        self.pw = []

    def password_ok(self, entry, pw):
        self.pw.append(pw)
        if pw != 'Heslo':
            raise g['LdapError']('invalid credentials')


def make(reply='', good='123456', digits=6):
    realm = {'name': 'corp', 'auth_mode': 'password_otp', 'directory': 'ad', 'reply': reply,
             'token_name': 'bare', 'check_disabled': 0}
    tok = {'name': 'novak', 'digits': digits, 'state': 'active', 'kind': 'totp', 'scratch_left': 0}
    st, tk, ad = Store(realm, tok), Tokens(good), Dir()
    a = g['Authenticator'](st, tk, {'ad': ad})
    a.token_for = lambda store, user, realm: ('novak', '')
    a.find_person = lambda ad_, user, lookup, realm_: {'dn': 'CN=novak', 'display': 'Novak'}
    a.alias_clash = lambda *x, **k: ''
    a.same_person = lambda *x, **k: ''
    return a, st, tk, ad


g['CONFIG']['scratch_digits'] = 8
g['CONFIG']['totp_digits'] = 6
g['token_kind'] = lambda t: (t or {}).get('kind') or 'totp'

# ---- R1 ------------------------------------------------------------------------------
a, st, tk, ad = make()
d = a.decide('novak', 'Heslo123456')
ok('R1 Heslo + code: let in', d.result == 'accept', d.reason)
ok('R1 Heslo + code: directory got Heslo', ad.pw == ['Heslo'], ad.pw)

a, st, tk, ad = make()
d = a.decide('novak', 'Heslo123456 ')
ok('R1 code with a space after it: let in', d.result == 'accept', d.reason)
ok('R1 code with a space after it: directory got Heslo', ad.pw == ['Heslo'], ad.pw)

a, st, tk, ad = make()
d = a.decide('novak', 'Heslo123456\r\n')
ok('R1 code with a line end after it: let in', d.result == 'accept' and ad.pw == ['Heslo'], (d.reason, ad.pw))

for pw in ('HesloAbcdefgh', 'Heslo', 'Hesloabcdef ', '123456 ', 'Heslo12345x'):
    a, st, tk, ad = make()
    d = a.decide('novak', pw)
    ok('R1 no code after the password (%r): refused, directory not asked' % pw,
       d.result == 'reject' and ad.pw == [], (d.result, d.reason, ad.pw))

a, st, tk, ad = make()
d = a.decide('novak', 'He slo 123456')
ok('R1 a space inside the password stays', ad.pw == ['He slo '] or ad.pw == ['He slo'],
   ad.pw)
a, st, tk, ad = make(good='12345678')
d = a.decide('novak', 'Heslo1234-5678')
ok('R1 a recovery code typed with a dash still found', d.result == 'accept' and ad.pw == ['Heslo'],
   (d.reason, ad.pw))

# ---- R3 ------------------------------------------------------------------------------
a, st, tk, ad = make(reply='Bogus-Attr = 1')
d = a.decide('novak', 'Heslo123456')
ok('R3 a realm reply that cannot be built: refused', d.result == 'reject', d.reason)
ok('R3 ... and the code was not used', all(dry for _c, dry in tk.checked), tk.checked)
long_reply = '\n'.join('Reply-Message = "%s"' % ('x' * 240) for _ in range(20))
a, st, tk, ad = make(reply=long_reply)
d = a.decide('novak', 'Heslo123456')
ok('R3 a realm reply too long for a packet: refused', d.result == 'reject' and
   'longer than a RADIUS packet' in d.reason, d.reason)
ok('R3 ... and the code was not used', all(dry for _c, dry in tk.checked), tk.checked)
a, st, tk, ad = make(reply='Session-Timeout = 3600')
d = a.decide('novak', 'Heslo123456')
ok('R3 a good reply: let in with it', d.result == 'accept' and ('Session-Timeout', '3600') in d.reply,
   (d.reason, d.reply))
ok('R3 reply_too_long: small fits', g['reply_too_long']([('Session-Timeout', '1')]) == '')
ok('R3 reply_too_long: 4100 bytes do not', g['reply_too_long']([('Reply-Message', 'x' * 240)] * 17) != '')

# ---- R2 ------------------------------------------------------------------------------
def answer_mail(fail_drop, fail_used):
    a, st, tk, ad = make()
    tok = {'name': 'novak', 'kind': 'mail', 'dest': 'n@x.cz', 'state': 'active'}
    st.tok = tok
    state = b'\x01' * 16
    chal = {'name': 'novak', 'user': 'novak', 'realm': 'corp', 'client': None, 'kind': 'mail',
            'reply': [['Session-Timeout', '60']], 'exp': time.time() + 300, 'made': time.time(),
            'tries': 0, 'dest': 'n@x.cz', 'code': g['code_hash']('novak', '482913')}
    box = {'v': json.dumps(chal)}
    a.store.fail_drop = fail_drop
    tk.fail_used = fail_used
    g['chal_get'] = lambda s, k: (json.loads(box['v']), box['v']) if box['v'] else (None, None)
    g['chal_put'] = lambda s, k, raw, nxt: box.update(v=json.dumps(nxt)) or True
    g['chal_take'] = lambda s, k, raw: box.update(v=None)
    g['once_take'] = lambda *x, **k: True
    g['clock_now'] = lambda kind='': time.time()
    g['token_kind'] = lambda t: (t or {}).get('kind') or 'totp'
    g['token_lang'] = lambda t: 'en'
    del LOGS[:]
    try:
        return a.answer('novak', '482913', state)
    except Exception as e:                                  # noqa: BLE001
        return e


d = answer_mail(False, False)
ok('R2 mail code, all well: let in', getattr(d, 'result', None) == 'accept', d)
d = answer_mail(True, False)
ok('R2 mail code, question not dropped: still let in', getattr(d, 'result', None) == 'accept', d)
ok('R2 ... and written down', any('could not be dropped' in w for _l, w in LOGS), LOGS)
d = answer_mail(False, True)
ok('R2 mail code, token not marked used: still let in', getattr(d, 'result', None) == 'accept', d)
ok('R2 ... and written down', any('could not be marked used' in w for _l, w in LOGS), LOGS)
d = answer_mail(True, True)
ok('R2 mail code, both failing: still let in, with its reply',
   getattr(d, 'result', None) == 'accept' and ('Session-Timeout', '60') in d.reply, d)

# ---- R4 ------------------------------------------------------------------------------
class D:
    result = 'reject'

    def __init__(self, r):
        self.reason = r


gi = g['guard_is_guess']
for r in ('Denied by the token server: ' + g['SAY_LOST'],
          'the token server: the directory could not say whether a@b is another account (x)',
          'the code was asked for too long ago: sign in again'):
    ok('R4 not a guess: %s' % r[:60], not gi(D(r)))
ok('R4 a wrong code is still a guess', gi(D('Denied by the token server: ' + g['SAY_BAD'])))

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
