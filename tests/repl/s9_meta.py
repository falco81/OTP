# The same meta key changed on both nodes while their writes cross (no newer-wins trigger on meta).
from fakeh import *
reset()
store('A').set_meta('scratchclear:jo', '1.0'); settle(); pause()
store('A').set_meta('scratchclear:jo', '100.0')
store('B').set_meta('scratchclear:jo', '200.0')
resume()
print('meta crossed:', [ (n, q(n, "select v from meta where k='scratchclear:jo'")[0]['v']) for n in 'AB'])
# A staged replacement's wrong codes, counted in meta staged:NAME, on both nodes
node('A'); otp.Tokens(store('A')).enroll('jo', 'admin'); otp.Tokens(store('A')).stage_replacement('jo', 'jo'); settle(); pause()
for i in range(3): node('A'); otp.Tokens(store('A')).confirm('jo', '11111%d' % i)
for i in range(2): node('B'); otp.Tokens(store('B')).confirm('jo', '22222%d' % i)
resume()
print('staged fails:', [(n, json.loads(q(n, "select v from meta where k='staged:jo'")[0]['v'])['fails']) for n in 'AB'])
print([r['apply_error_count'] for n in 'AB' for r in health()[n]])
