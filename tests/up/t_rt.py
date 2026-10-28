exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import time
print('login', call('login', {'name':'admin','password':PW}).get('ok'))
for node in ('', 'nodeb'):
  for how in ('udp','direct'):
    t=time.time()
    d=call('radtest', {'user':'falco@corpnet.cz','password':'000000','how':how,'client':1,'node':node})
    print(node or 'here', how, d.get('result'), d.get('node'), d.get('error'), '%.1fs'%(time.time()-t))
time.sleep(2)
d=call('activity&hours=1&limit=6&kind=all')
for r in (d.get('rows') or [])[:6]: print(r.get('kind'), r.get('name'), r.get('source'), r.get('node'))
d=call('events&limit=4')
for r in d.get('rows',[])[:4]: print('ev', r.get('node'), r.get('words')[:70])
