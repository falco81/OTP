import sys, os, time, socket, secrets, glob, re
sys.argv=['t','none'];exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
sys.path.insert(0,'/home/claude/build/out/otp-1.0.109'); sys.argv=['x']
import otp as O
SP='/tmp/otpspool'
d=call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'sms','dest':'+420603111222'}); print(d.get('message'))
time.sleep(2)
def ask(port,user,pw,state=None):
    pairs=[O.attr_bytes('User-Name',user), bytes([4,6])+socket.inet_aton('127.0.0.3')]
    if state: pairs.append(O.attr_bytes('State','0x'+state.hex()))
    ident=secrets.randbelow(256)
    data,auth=O.build_request(O.ACCESS_REQUEST, ident, pairs, b'chal-secret-1', password=pw)
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(('127.0.0.3',0)); s.settimeout(8)
    s.sendto(data,('127.0.0.1',port)); got,_=s.recvfrom(4096); s.close()
    p=O.Packet.parse(got); return p.code, p.get(24), dict(p.words())
before=set(glob.glob(SP+'/otp-*'))
code,state,w=ask(1812,'falco@corpnet.cz','falco-password-1'); print('node A:', code, w.get('Reply-Message'))
time.sleep(1.5)
new=[f for f in glob.glob(SP+'/otp-*') if f not in before]
c=re.search(r'\b(\d{6})\b', open(new[0]).read().split('\n\n',1)[1]).group(1)
code2,_,w2=ask(11812,'falco@corpnet.cz',c,state); print('node B answers:', code2, '(2 = Access-Accept)')
code3,_,_=ask(1812,'falco@corpnet.cz',c,state); print('node A again with the same:', code3, '(3 = Access-Reject)')
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
print('PASS' if (code==11 and code2==2 and code3==3) else 'FAIL')
