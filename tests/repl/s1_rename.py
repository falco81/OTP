# Rename on A crossing a sign-in (TOTP code, then a recovery code) on B.
from fakeh import *
reset()
node('A'); sA = store('A'); tA = otp.Tokens(sA)
out = tA.enroll('alice', 'admin')
secret, codes = out['secret'], out['scratch']
settle()
print('enrolled, same on both:', same('tokens')[0])
pause()
# B: the person signs in with a recovery code, as alice
node('B'); tB = otp.Tokens(store('B'))
print('B scratch use:', tB.check('alice', codes[0], src='10.0.0.1')[:2])
# A: an administrator renames alice -> alice2 at the same moment
node('A'); print('A rename:', act('A', 'rename', 'alice', to='alice2'))
resume()
print(health())
for n in 'AB':
    for r in tok(n, None, 'id,name,scratch_left,key_at,scratch_at,last_how'):
        print(n, dict(r))
    for r in q(n, 'SELECT name FROM tokens'):
        print(n, r['name'], 'key opens:', plain(n, r['name']) == secret)
# Can the used recovery code be used again, as alice2, on each node?
for n in 'AB':
    node(n)
    print(n, 'reuse of used recovery code as alice2:', otp.Tokens(store(n)).check('alice2', codes[0], dry=True)[:2],
          ' as alice:', otp.Tokens(store(n)).check('alice', codes[0], dry=True)[:2])
node('B'); print('B real reuse as alice2:', otp.Tokens(store('B')).check('alice2', codes[0], src='10.6.6.6')[:2])
# Any later write on A (a wrong code against alice there) carries name=alice over to B
settle()
node('A'); print('A wrong code for alice:', otp.Tokens(store('A')).check('alice', '000000')[:2])
settle()
for n in 'AB':
    for r in q(n, 'SELECT id, name FROM tokens'):
        print('after a later write', n, dict(r), 'key opens:', plain(n, r['name']) == secret)
