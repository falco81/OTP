exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import time
print('login', call('login', {'name':'admin','password':PW}).get('ok'))
print(call('upgrade', {'action':'maintenance','node':'nodea','on':True,'why':'t'}).get('message'))
r=call('upgrade', {'action':'start'}); print(r.get('message') or r.get('error'))
time.sleep(12)
d=call('upgrade'); p=d.get('plan') or {}
print(p.get('state'), ' | '.join('%s:%s(%s)'%(s['name'],s.get('state'),(s.get('said') or '')[:50]) for s in p.get('steps',[])))
print(call('upgrade', {'action':'cancel'}).get('message'))
print(call('upgrade', {'action':'maintenance','node':'nodea','on':False}).get('message'))
