exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
from urllib.parse import quote
import time
call('login', {'name':'admin','password':PW})
for n,k,d in (('sms.user@corpnet.cz','sms','+420777123456'),('mailer@corpnet.cz','mail','petra.posta@firma.cz')):
    call('token',{'action':'delete','name':n}); time.sleep(0.3)
    call('token',{'action':'enroll','name':n,'kind':k,'dest':d})
ok=n=0
def q(text, want):
    global ok,n
    d=call('tokens&q='+quote(text)+'&state=&limit=500&offset=0')
    got=sorted(r['name'] for r in d.get('rows',[]))
    good=(got==want) and not d.get('q_error'); n+=1; ok+=good
    print('ok  ' if good else 'FAIL', repr(text), got[:3], d.get('q_error') or '')
S=['sms.user@corpnet.cz']; M=['mailer@corpnet.cz']
for t in ('777123456','777 123 456','+420 777 123 456','00420777123456','420-777-123-456','kind:sms 777 123 456','to:777123456','to~123','to:+420777123456','to:777*'):
    q(t,S)
for t in ('petra.posta','petra.posta@firma.cz','firma.cz kind:mail','to:*@firma.cz','to:petra.posta@firma.cz'):
    q(t,M)
q('to:123', [])
print('%d/%d'%(ok,n))
