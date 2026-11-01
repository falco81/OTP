import subprocess, collections
from fakeh import *
otp.CONFIG['scratch_count'] = 20
reset()
info = {}
for i in range(4):
    o = otp.Tokens(store('A')).enroll('st%d' % i, 'admin')
    info['st%d' % i] = {'secret': o['secret'], 'rc': o['scratch']}
json.dump(info, open('/home/claude/ws/tests/repl/stress_tokens.json', 'w')); settle()
ps = [subprocess.Popen(['/usr/bin/python3.14', 'stress_node.py', n, '60'], cwd='/home/claude/ws/tests/repl',
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for n in 'AB']
for p in ps:
    out = p.communicate()[0]
    print('\n'.join(l for l in out.splitlines() if not l.startswith('20'))[-800:])
settle()
acc = json.load(open('stress_acc_A.json')) + json.load(open('stress_acc_B.json'))
cnt = collections.Counter(tuple(x) for x in acc)
print('accepted twice:', [k for k, v in cnt.items() if v > 1])
eq, a, b = same('tokens')
print('tokens converge:', eq)
if not eq:
    for x, y in zip(a, b):
        d = {k: (x[k], y[k]) for k in x if x[k] != y[k]}
        if d: print(x['name'], d)
print('token_once same:', same('token_once', 'k,node', 'k,node')[0], 'meta same:', same('meta', 'k', 'k,v')[0])
print([r['apply_error_count'] for n in 'AB' for r in health()[n]], [r['running'] for n in 'AB' for r in health()[n]])
