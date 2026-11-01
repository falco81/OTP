# Clock skew: node B's clock 60 s ahead. Simulated by stamping B's last state change
# (and lockout) 60 s into the future, as B's clock_timestamp() would have.
from fakeh import *
reset()
node('A'); otp.Tokens(store('A')).enroll('dave', 'admin'); settle()
# B: an administrator switches dave off, then on again (B's clock 60 s fast)
act('B', 'disable', 'dave'); act('B', 'enable', 'dave')
q('B', 'UPDATE tokens SET state_at = state_at + 60, lock_at = lock_at + 60 WHERE name = %s', ('dave',))
settle()
print('before', [dict(r) for n in 'AB' for r in tok(n, 'dave', "'%s' AS node, state, state_at" % n)])
time.sleep(1)
# A, seconds later in real time, after B's rows came over: switched off because the phone was stolen
print('A disable:', act('A', 'disable', 'dave'))
settle()
for n in 'AB':
    print(n, dict(tok(n, 'dave', 'state, state_at')[0]))
    node(n); print(n, 'sign-in:', otp.Tokens(store(n)).blocked('dave'))
print(health())
