exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import time
print('login', call('login', {'name':'admin','password':PW}).get('ok'))
print(call('upgrade', {'action':'start'}).get('message') or call('upgrade', {'action':'start'}))
t0=time.time()
while time.time()-t0<30:
    d=call('upgrade'); p=d.get('plan') or {}
    st=[s.get('state') for s in p.get('steps',[])]
    if 'draining' in st: break
    time.sleep(0.5)
print('at cancel', st)
print('cancel:', (call('upgrade', {'action':'cancel'}) or {}).get('message'))
for i in range(6):
    time.sleep(4)
    d=call('upgrade'); p=d.get('plan') or {}
    print(p.get('state'), ' | '.join('%s:%s(%s)'%(s['name'],s.get('state'),(s.get('said') or '')[:50]) for s in p.get('steps',[])),
          [(n['name'], n.get('version'), (n.get('maintenance') or {}).get('on')) for n in d.get('nodes',[])])
