import sys, json, time, re, socket, secrets
sys.argv=['t','none'];exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
sys.path.insert(0,'/home/claude/build/out/otp-1.0.109'); sys.argv=['x']
import otp as O
R=[]
def ok(w,c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('mail_mode','smtp_host','smtp_port','smtp_security','smtp_auth','code_mail_fmt')}
call('settings',{'settings':{'mail_mode':'smtp','smtp_host':'127.0.0.1','smtp_port':2525,'smtp_security':'none','smtp_auth':'none','code_mail_fmt':'html'}})
time.sleep(1)
def ask(user,pw,state=None):
    pairs=[O.attr_bytes('User-Name',user), bytes([4,6])+socket.inet_aton('127.0.0.3')]
    if state: pairs.append(O.attr_bytes('State','0x'+state.hex()))
    data,auth=O.build_request(O.ACCESS_REQUEST, secrets.randbelow(256), pairs, b'chal-secret-1', password=pw)
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.3',0)); s.settimeout(8)
    s.sendto(data,('127.0.0.1',1812)); got,_=s.recvfrom(4096); s.close()
    p=O.Packet.parse(got); return p.code, p.get(24), dict(p.words())
def mail(): time.sleep(1.2); return open('/tmp/claude-0/chal/sink.eml').read()
print(call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'mail','dest':'falco@corpnet.cz'}).get('message'))
call('token',{'action':'lang','name':'falco@corpnet.cz','value':'en'})
time.sleep(1)
c,st,w=ask('falco@corpnet.cz','falco-password-1')
ok('token in English: the VPN asks in English (%s)'%w.get('Reply-Message'), 'Type the code' in (w.get('Reply-Message') or ''))
m=mail(); ok('... and the mail is English and HTML', 'Your sign-in code' in m and 'text/html' in m)
call('token',{'action':'mail_fmt','name':'falco@corpnet.cz','value':'text'}); call('token',{'action':'lang','name':'falco@corpnet.cz','value':'cs'})
time.sleep(1)
c,st,w=ask('falco@corpnet.cz','falco-password-1')
ok('token in Czech: the VPN asks in Czech (%s)'%w.get('Reply-Message'), 'Zadejte' in (w.get('Reply-Message') or ''))
m=mail(); ok('... the mail plain text only', 'text/html' not in m and 'text/plain' in m)
t=call('token&name=falco@corpnet.cz')['token']; ok('token shows lang/mail_fmt (%s/%s)'%(t.get('lang'),t.get('mail_fmt')), t.get('lang')=='cs' and t.get('mail_fmt')=='text')
call('token',{'action':'mail_fmt','name':'falco@corpnet.cz','value':''}); call('settings',{'settings':{'code_mail_fmt':'text'}}); time.sleep(1)
ask('falco@corpnet.cz','falco-password-1'); m=mail(); ok('setting plain text, token as the setting: plain text', 'text/html' not in m)
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
call('settings',{'settings':keep})
print('%d/%d'%(sum(R),len(R)))
