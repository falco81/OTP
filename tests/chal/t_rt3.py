exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import time,sys
call('login', {'name':'admin','password':PW})
c=call('token', {'action':'code_now','name':'after-rebuild@corpnet.cz','first':True})
print('code', c.get('code'), c.get('error'))
t=time.time()
d=call('radtest', {'user':'after-rebuild@corpnet.cz','password':c.get('code') or '000000','how':'direct','client':1,'node':'nodeb'})
print(round(time.time()-t,1),'s', d.get('result'), d.get('node'), d.get('reason'), d.get('error'))
