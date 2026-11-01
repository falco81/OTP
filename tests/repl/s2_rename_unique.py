# Rename alice->bob on A while B enrols a new token for bob: B's apply of A's UPDATE
# hits tokens_name_key; replication A->B stops for good.
from fakeh import *
reset()
node('A'); otp.Tokens(store('A')).enroll('alice', 'admin'); settle(); pause()
node('A'); act('A', 'rename', 'alice', to='bob')
node('B'); otp.Tokens(store('B')).enroll('bob', 'admin')
resume(wait=False); settle(timeout=8); time.sleep(3)
print(health())
for n in 'AB': print(n, [dict(r) for r in tok(n, None, 'id,name')])
