# Wrong codes sent to both nodes at once, replication running: how many are counted?
import threading
from fakeh import *
otp.CONFIG['rate_limit_tries'] = 0          # only the lockout counts
reset()
node('A'); out = otp.Tokens(store('A')).enroll('carol', 'admin'); settle()
TA, TB = otp.Tokens(store('A')), otp.Tokens(store('B'))
sent = 0
for i in range(10):
    bar = threading.Barrier(2)
    def go(T, n):
        bar.wait(); T.check('carol', '%06d' % (100000 + i), src='10.9.9.%s' % n)
    # once_node() reads the process-wide CONFIG; failures do not use it
    th = [threading.Thread(target=go, args=(TA, 1)), threading.Thread(target=go, args=(TB, 2))]
    [t.start() for t in th]; [t.join() for t in th]
    sent += 2
    time.sleep(0.3)
settle()
for n in 'AB':
    r = tok(n, 'carol', 'failures, locked_until, fail_times')[0]
    print(n, 'wrong codes sent:', sent, 'failures:', r['failures'], 'locked:', bool(r['locked_until']),
          'fail_times kept:', len(json.loads(r['fail_times'] or '[]')))
print(health())
