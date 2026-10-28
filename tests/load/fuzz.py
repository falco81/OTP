import socket, os, random, struct, hashlib, sys, time
N=sys.argv[:]; sys.argv=["otp"]; sys.path.insert(0,'/usr/local/lib/otp')
random.seed(7)
S=b'testing123'
def valid():
    auth=os.urandom(16); attrs=b''
    u=b'u001@load.test'; attrs+=bytes([1,len(u)+2])+u
    pw=os.urandom(16); attrs+=bytes([2,18])+pw
    pkt=bytes([1,random.randrange(256)])+struct.pack('>H',20+len(attrs))+auth+attrs
    return bytearray(pkt)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(0.02)
n=0
for i in range(int(N[1]) if len(N)>1 else 20000):
    k=i%8; p=valid()
    if k==0: p=bytearray(os.urandom(random.randrange(0,200)))
    elif k==1: p=p[:random.randrange(len(p))]
    elif k==2: p[22]=random.choice([0,1,255,2])  # attr len
    elif k==3: struct.pack_into('>H',p,2,random.choice([0,19,20,4096,65535]))
    elif k==4: p[0]=random.choice([0,2,3,4,5,11,12,13,40,43,255])
    elif k==5: p+=bytes([26,6,0,0,0,9])  # truncated VSA
    elif k==6: p+=bytes([80,18])+os.urandom(16)  # bogus Message-Authenticator
    elif k==7: p+=bytes([26,255])+os.urandom(253)
    port=random.choice([1812,1813])
    s.sendto(bytes(p),('127.0.0.1',port)); n+=1
    try: s.recv(4096)
    except Exception: pass
print('sent',n)
import otp
print(otp.radius_ask('127.0.0.1',1812,S,'nobody@load.test','x',timeout=3,tries=1)[0])
