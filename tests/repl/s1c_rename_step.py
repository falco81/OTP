# Rename on A crossing a TOTP sign-in on B: the same code (same step) is taken again
# under the new name, on both nodes.
from fakeh import *
reset()
node('A'); out = otp.Tokens(store('A')).enroll('alice', 'admin'); secret = out['secret']
settle(); pause()
c = code(secret)
node('B'); print('B sign-in:', otp.Tokens(store('B')).check('alice', c, src='10.0.0.1')[:2])
print('B same code again:', otp.Tokens(store('B')).check('alice', c, src='10.0.0.1')[:2])
node('A'); act('A', 'rename', 'alice', to='alice2')
resume()
for n in 'AB': print(n, tok(n, None, 'id,name,last_step'))
node('B'); print('B same code as alice2:', otp.Tokens(store('B')).check('alice2', c, src='10.6.6.6')[:2])
settle()
node('A'); print('A same code as alice2:', otp.Tokens(store('A')).check('alice2', c, src='10.6.6.7')[:2])
