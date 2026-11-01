# Delete vs update / re-enrol crossing; the same name enrolled on both at once.
from fakeh import *
def show(t):
    eq, a, b = same('tokens', 'id', 'id,name,state,key_at')
    print(t, 'same:', eq, 'A:', [(r['id'], r['name']) for r in a], 'B:', [(r['id'], r['name']) for r in b])
reset()
node('A'); o = otp.Tokens(store('A')).enroll('gina', 'admin'); s = o['secret']; settle(); pause()
store('A').token_drop('gina')
node('B'); print('B sign-in:', otp.Tokens(store('B')).check('gina', code(s))[:2])
resume(); show('delete(A) x sign-in(B)')
# delete on A, re-enrol (same row, new key) on B
node('A'); otp.Tokens(store('A')).enroll('gina', 'admin'); settle(); pause()
store('A').token_drop('gina')
node('B'); nb = otp.Tokens(store('B')).enroll('gina', 'admin')
resume(); show('delete(A) x re-enrol(B)')
# delete on A then enrol again on A (new id), while B signs in on the old row
node('A'); o = otp.Tokens(store('A')).enroll('gina', 'admin'); s = o['secret']; settle(); pause()
store('A').token_drop('gina'); otp.Tokens(store('A')).enroll('gina', 'admin')
node('B'); otp.Tokens(store('B')).check('gina', code(s))
resume(); show('delete+enrol(A) x sign-in(B)')
# both enrol the same new name at once
pause()
node('A'); ka = otp.Tokens(store('A')).enroll('hank', 'admin')['secret']
node('B'); kb = otp.Tokens(store('B')).enroll('hank', 'admin')['secret']
resume(); show('enrol(A) x enrol(B)')
for n in 'AB': print(n, 'hank key is', 'A' if plain(n, 'hank') == ka else 'B' if plain(n, 'hank') == kb else '?')
print([r['apply_error_count'] for n in 'AB' for r in health()[n]])
