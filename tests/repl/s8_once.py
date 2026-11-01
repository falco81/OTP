# Recovery codes / TOTP steps used on both nodes while their rows cross (replication paused,
# the peer's database asked directly as otp does).
from fakeh import *
def peer(n):
    other = 'B' if n == 'A' else 'A'
    otp.once_peer_forget()
    otp.CONFIG['ha_peer'] = '127.0.0.1'
    otp.ha_peer_conf = lambda timeout=None, tls=None, o=other: dict(CONF[o], db_timeout_s=timeout or 10)
def T(n):
    st = store(n); peer(n); return otp.Tokens(st)
reset()
o = T('A').enroll('ivy', 'admin'); s, rc = o['secret'], o['scratch']; settle(); pause()
print('A rc0', T('A').check('ivy', rc[0])[:2], '| B rc1', T('B').check('ivy', rc[1])[:2])
print('A rc2', T('A').check('ivy', rc[2])[:2], '| B rc2 (same)', T('B').check('ivy', rc[2])[:2])
c = code(s)
print('A code', T('A').check('ivy', c)[:2], '| B same code', T('B').check('ivy', c)[:2])
resume()
eq, a, b = same('tokens', 'id', 'id,name,scratch,scratch_left,last_step,failures')
print('tokens same:', eq, [ (r['scratch_left'], r['last_step']) for r in a+b])
for n in 'AB':
    TT = T(n)
    print(n, [TT.check('ivy', x, dry=True)[1] for x in rc], 'codes view:', [bool(x.get('used')) for x in otp.codes_open(tok(n, 'ivy', '*')[0])])
print('token_once same:', same('token_once', 'id', 'k,node')[0], len(q('A', 'select * from token_once')))
print([r['apply_error_count'] for n in 'AB' for r in health()[n]])
