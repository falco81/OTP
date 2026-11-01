# A token re-enrolled (new key) on A while B records a sign-in / wrong codes / recovery code on the old one.
from fakeh import *
reset()
node('A'); o = otp.Tokens(store('A')).enroll('erin', 'admin'); old, oldcodes = o['secret'], o['scratch']
settle(); pause()
node('B'); TB = otp.Tokens(store('B'))
print('B old key sign-in:', TB.check('erin', code(old))[:2])
print('B old recovery code:', TB.check('erin', oldcodes[1])[:2])
print('B wrong:', TB.check('erin', '123456')[:2])
node('A'); n = otp.Tokens(store('A')).enroll('erin', 'admin'); new, newcodes = n['secret'], n['scratch']
resume()
eq, a, b = same('tokens')
print('same on both:', eq)
for nn in 'AB':
    r = tok(nn, 'erin', '*')[0]
    print(nn, {k: r[k] for k in ('last_step', 'failures', 'scratch_left', 'last_used', 'last_how', 'created', 'activated')},
          'key is new:', plain(nn, 'erin') == new)
    node(nn); T = otp.Tokens(store(nn))
    print(nn, 'old key:', T.check('erin', code(old), dry=True)[:2], 'old rc:', T.check('erin', oldcodes[2], dry=True)[:2],
          'new key:', T.check('erin', code(new), dry=True)[:2], 'new rc:', T.check('erin', newcodes[0], dry=True)[:2])
if not eq:
    for x, y in zip(a, b):
        print({k: (x[k], y[k]) for k in x if x[k] != y[k]})
print(health())
