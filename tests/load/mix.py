import sys, threading, time, collections, random
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
EPS=['status','dashboard','radius','activity','otp','tokens','clients','realms','directories','settings','users','sessions','events','enrolment','mail','log','db','upgrade','ha','ha-history','web','firewall','auth-whoami','suggest']
res=collections.Counter(); bad=[]; lat=collections.defaultdict(list)
stop=time.time()+60
def w():
    while time.time()<stop:
        e=random.choice(EPS); t=time.time(); d=call(e); ms=(time.time()-t)*1000; lat[e].append(ms)
        if isinstance(d,dict) and ('http' in d or 'err' in d or d.get('error')):
            k='%s %s'%(e, d.get('http') or d.get('err') or d.get('error'))
            res[k[:90]]+=1
        else: res['ok']+=1
        time.sleep(0.15)
ts=[threading.Thread(target=w) for _ in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
print(dict(res))
for e,v in sorted(lat.items(), key=lambda kv:-max(kv[1]))[:8]:
    v.sort(); print('%-12s n=%3d p50=%5d max=%5d'%(e,len(v),v[len(v)//2],v[-1]))
