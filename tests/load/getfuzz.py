import sys, itertools, random, urllib.parse, collections
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
import time
EPS=['status','dashboard','radius','radius-row','otp','tokens','activity','token','clients','realms','directories','settings','users','sessions','events','enrolment','suggest','mail','log','db','whoami','my-settings','ha','upgrade','web','firewall','ha-history','export']
VALS=['', '-1', '0', '1e309', 'nan', 'abc', '99999999999999999999', '%', '_', '\\', "'", '"', '%00', 'žluťoučký', 'a'*5000, '[]', '{}', '1.5', '-0', 'null', 'u001@load.test', 'state:active', 'client:', 'ip:999.1.1.1', '*', 'NOT', '(']
KEYS=['q','name','kind','state','sort','result','desc','client','check','user','typed','step','secrets','ok','list','field','from','hours','id','limit','lines','offset','since','to','until']
random.seed(3); bad=collections.Counter(); ex={}
n=0
for ep in EPS:
    for i in range(30):
        params={k:random.choice(VALS) for k in random.sample(KEYS, random.randint(1,5))}
        qs='&'.join('%s=%s'%(k,urllib.parse.quote(v)) for k,v in params.items())
        d=call(ep+'&'+qs); n+=1
        time.sleep(0.12)
        if isinstance(d,dict) and (d.get('http') in (500,502,504) or 'err' in d or (d.get('error') and ('broke' in str(d.get('error')) or 'Traceback' in str(d)))):
            k='%s %s'%(ep, str(d.get('http') or d.get('err') or d.get('error'))[:80]); bad[k]+=1; ex.setdefault(k, qs[:200])
print('calls',n); 
for k,v in bad.most_common(30): print(v,k,'|',ex[k])
