# As s1, then the next write lands on A first (an administrator's Unlock of the token
# A now lists as "alice", key lost): B takes name=alice too - both nodes end broken.
from fakeh import *
reset()
node('A'); out = otp.Tokens(store('A')).enroll('alice', 'admin'); secret, codes = out['secret'], out['scratch']
settle(); pause()
node('B'); print('B sign-in with TOTP:', otp.Tokens(store('B')).check('alice', code(secret), src='10.0.0.1')[:2])
node('A'); act('A', 'rename', 'alice', to='alice2')
resume()
for n in 'AB':
    for r in q(n, 'SELECT id, name FROM tokens'): print('crossed', n, dict(r), 'key opens:', plain(n, r['name']) == secret)
node('A'); print('A unlock alice:', act('A', 'unlock', 'alice'))
settle()
for n in 'AB':
    for r in q(n, 'SELECT id, name FROM tokens'): print('after', n, dict(r), 'key opens:', plain(n, r['name']) == secret)
    node(n); print(n, 'sign in as alice2:', otp.Tokens(store(n)).check('alice2', code(secret), dry=True)[:2],
                   'as alice:', otp.Tokens(store(n)).check('alice', code(secret), dry=True)[:2])
print(health())
