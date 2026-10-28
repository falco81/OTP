exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import time
print('login', call('login', {'name':'admin','password':PW}).get('ok'))
print(call('upgrade', {'action':'start'}).get('message'))
time.sleep(2)
print('cancel:', (call('upgrade', {'action':'cancel'}) or {}).get('message'))
for i in range(8):
    d=call('upgrade'); p=d.get('plan') or {}
    print(p.get('state'), ' | '.join('%s:%s(%s)'%(s['name'],s.get('state'),(s.get('said') or '')[:50]) for s in p.get('steps',[])),
          [(n['name'], (n.get('maintenance') or {}).get('on')) for n in d.get('nodes',[])])
    time.sleep(4)
