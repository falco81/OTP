import sys, os, json, time, threading, random, statistics, collections, ssl, urllib.request, http.cookiejar, base64, hmac, hashlib, struct
ARGS=sys.argv[:]; sys.argv=['otp']; sys.path.insert(0,'/usr/local/lib/otp')
import otp
SECRET='testing123'
toks=json.load(open('/tmp/claude-0/load/tokens.json'))
def totp(sec):
    key=base64.b32decode(sec.replace(' ','').upper()+'='*((8-len(sec.replace(' ',''))%8)%8))
    c=int(time.time())//30
    h=hmac.new(key, struct.pack('>Q',c), hashlib.sha1).digest()
    o=h[-1]&15; return '%06d'%((struct.unpack('>I',h[o:o+4])[0]&0x7fffffff)%1000000)
T=int(ARGS[1]) if len(ARGS)>1 else 16
D=float(ARGS[2]) if len(ARGS)>2 else 30
API=len(ARGS)>3 and ARGS[3]=='api'
res=collections.Counter(); lat=[]; lock=threading.Lock(); stop=time.time()+D
def worker(i):
    while time.time()<stop:
        r=random.random()
        if r<0.4: u,p='falco@corpnet.cz', totp(toks['falco@corpnet.cz'])
        elif r<0.7: u,p='falco@corpnet.cz','%06d'%random.randint(0,999999)
        elif r<0.85: u,p='nobody%d@corpnet.cz'%random.randint(0,99999),'123456'
        else: u,p='loadA@corpnet.cz', totp(toks['loadA@corpnet.cz'])
        t0=time.time()
        try:
            code,words,ms=otp.radius_ask('127.0.0.1',1812,SECRET,u,p,timeout=3.0,tries=1)
            k={2:'accept',3:'reject'}.get(code,str(code))
        except Exception as e:
            k='timeout' if 'no answer' in str(e) else 'err:'+str(e)[:40]
        dt=(time.time()-t0)*1000
        with lock: res[k]+=1; lat.append(dt)
api_lat=collections.defaultdict(list)
def apiload():
    PW=open('/home/claude/run/adminpw').read().strip()
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(a, body=None):
        req=urllib.request.Request('https://127.0.0.1/admin/?api='+a, data=json.dumps(body).encode() if body else None, headers={'Content-Type':'application/json'})
        with op.open(req, timeout=30) as r: return r.read()
    call('login',{'name':'admin','password':PW})
    paths=['status','dashboard&hours=720','activity&hours=720&limit=500','events&limit=100','suggest&list=radius&field=name&typed=f','tokens&limit=500','firewall','ha']
    while time.time()<stop:
        for p in paths:
            t0=time.time()
            try: call(p)
            except Exception as e: api_lat['ERR '+p].append(str(e)[:60])
            api_lat[p].append((time.time()-t0)*1000); time.sleep(0.12)
th=[threading.Thread(target=worker,args=(i,)) for i in range(T)]
if API: th += [threading.Thread(target=apiload) for _ in range(1)]
t0=time.time(); [t.start() for t in th]; [t.join() for t in th]; el=time.time()-t0
lat.sort()
q=lambda p: lat[int(len(lat)*p)] if lat else 0
print('threads %d, %.0fs, %d requests, %.0f/s' % (T, el, len(lat), len(lat)/el))
print('results', dict(res))
print('latency ms p50 %.0f p90 %.0f p99 %.0f max %.0f' % (q(.5),q(.9),q(.99),lat[-1] if lat else 0))
for p,v in api_lat.items():
    if p.startswith('ERR'): print(p, v[:2]); continue
    v=sorted(v); print('api %-45s n=%d p50 %.0f max %.0f' % (p, len(v), v[len(v)//2], v[-1]))
