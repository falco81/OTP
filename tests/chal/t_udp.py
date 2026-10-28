import sys, os, time, socket, secrets, glob, re, json
sys.argv=['t','none'];exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
sys.path.insert(0,'/home/claude/build/out/otp-1.0.109'); sys.argv=['x']
import otp as O
SP='/tmp/otpspool'
R=[]
def ok(w,c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
print(call('settings',{'settings':{'sms_mode':'spool','sms_spool_dir':SP,'code_send_max':20}}).get('message'))
r=[x for x in call('realms')['realms'] if x['name']=='corpnet.cz'][0]
r['methods']=['totp','mail','sms']
print(call('realms',{'action':'save','realm':r}).get('message') or 'saved?')
print(call('clients',{'action':'save','client':{'name':'chaltest','address':'127.0.0.3','secret':'chal-secret-1','enabled':1}}).get('message'))
d=call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'sms','dest':'+420 603 111 222'}); print(d.get('message') or d)
time.sleep(1.5)
def ask(user,pw,state=None):
    pairs=[O.attr_bytes('User-Name',user), bytes([4,6])+socket.inet_aton('127.0.0.3')]
    if state: pairs.append(O.attr_bytes('State','0x'+state.hex()))
    ident=secrets.randbelow(256)
    data,auth=O.build_request(O.ACCESS_REQUEST, ident, pairs, b'chal-secret-1', password=pw)
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.3',0)); s.settimeout(8)
    s.sendto(data,('127.0.0.1',1812)); got,_=s.recvfrom(4096); s.close()
    assert O.reply_ok(got,auth,b'chal-secret-1'), 'bad signature'
    p=O.Packet.parse(got); return p.code, p.get(24), dict(p.words())
before=set(glob.glob(SP+'/otp-*'))
code,state,w=ask('falco@corpnet.cz','falco-password-1')
ok('Access-Challenge with State and Reply-Message', code==11 and state and w.get('Reply-Message'))
print('   Reply-Message:', w.get('Reply-Message'))
time.sleep(1)
new=[f for f in glob.glob(SP+'/otp-*') if f not in before]
ok('an SMS file was written to the spool', len(new)==1)
txt=open(new[0]).read(); print('   SMS file:', repr(txt[:120]))
c=re.search(r'\b(\d{6})\b', txt.split('\n\n',1)[1]).group(1)
code2,_,w2=ask('falco@corpnet.cz','999999',state)
ok('wrong code -> another Access-Challenge', code2==11 and 'not right' in (w2.get('Reply-Message') or '') or 'nebyl' in (w2.get('Reply-Message') or ''))
code3,_,w3=ask('falco@corpnet.cz',c,state)
ok('right code -> Access-Accept', code3==2)
code4,_,_=ask('falco@corpnet.cz',c,state)
ok('the same answer again -> Access-Reject', code4==3)
code5,_,_=ask('falco@corpnet.cz','wrong-pw')
ok('wrong directory password -> Access-Reject, no SMS', code5==3)
# log rows
time.sleep(1)
rq=call('radius&q=falco&limit=6'); res=[x['result'] for x in rq.get('rows',[])]
print('   log results (newest first):', res)
ok('the log shows challenge, accept and reject rows', 'challenge' in res and 'accept' in res)
# put back: token as totp again
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
print('%d/%d'%(sum(R),len(R)))
