# One "daemon": python3 stress_node.py A|B seconds. Drives otp's engine against its own node's
# database while the other process does the same on the other node; replication live.
import sys, random
from fakeh import *
me = sys.argv[1]; secs = float(sys.argv[2])
other = 'B' if me == 'A' else 'A'
st = store(me)
otp.CONFIG['ha_peer'] = '127.0.0.1'
otp.ha_peer_conf = lambda timeout=None, tls=None: dict(CONF[other], db_timeout_s=timeout or 10)
otp.CONFIG['rate_limit_tries'] = 0
T = otp.Tokens(st)
info = json.load(open('/home/claude/ws/tests/repl/stress_tokens.json'))
acc = []
t0 = time.time(); random.seed(me)
while time.time() - t0 < secs:
    name = random.choice(list(info))
    r = random.random()
    try:
        if r < 0.4:
            c = code(info[name]['secret'])
            ok = T.check(name, c, src=me)[0]
            if ok: acc.append(('step', name, otp.totp_step()))
        elif r < 0.6:
            c = random.choice(info[name]['rc'])
            ok = T.check(name, c, src=me)[0]
            if ok: acc.append(('rc', name, c))
        elif r < 0.85:
            T.check(name, '%06d' % random.randint(0, 999999), src=me)
        elif r < 0.9:
            act(me, 'unlock', name)
        else:
            act(me, 'note', name, note='%s %f' % (me, time.time()))
    except Exception as e:
        print(me, 'error', type(e).__name__, e)
json.dump(acc, open('/home/claude/ws/tests/repl/stress_acc_%s.json' % me, 'w'))
print(me, 'accepted', len(acc))
