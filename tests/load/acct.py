import socket, struct, hashlib, os, random, threading, time, collections, sys
S=b'testing123'; R=collections.Counter(); lat=[]
def a(t,v): return bytes([t,len(v)+2])+v
def pkt(i):
    attrs=a(1,b'u%03d@load.test'%(i%200))+a(40,struct.pack('>I',random.choice([1,2,3])))+a(44,os.urandom(6).hex().encode())+a(4,bytes([127,0,0,1]))+a(8,bytes([10,1,i%250,1]))+a(31,b'1.2.3.4')
    ident=i%256; L=20+len(attrs)
    au=hashlib.md5(bytes([4,ident])+struct.pack('>H',L)+b'\0'*16+attrs+S).digest()
    return bytes([4,ident])+struct.pack('>H',L)+au+attrs
stop=time.time()+float(sys.argv[1])
def w(n):
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(3); i=n*100000
    while time.time()<stop:
        i+=1; t=time.time(); s.sendto(pkt(i),('127.0.0.1',1813))
        try:
            d=s.recv(4096); R['code%d'%d[0]]+=1; lat.append((time.time()-t)*1000)
        except socket.timeout: R['timeout']+=1
ts=[threading.Thread(target=w,args=(k,)) for k in range(int(sys.argv[2]))]; [t.start() for t in ts]; [t.join() for t in ts]
lat.sort(); print(dict(R), 'rate %.0f/s'%(sum(R.values())/float(sys.argv[1])), 'p50 %d p99 %d max %d'%(lat[len(lat)//2],lat[int(len(lat)*.99)],lat[-1]))
