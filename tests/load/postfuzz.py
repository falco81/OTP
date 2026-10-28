import sys, random, collections, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
random.seed(5)
JUNK=[None, 0, -1, 1e308, True, [], {}, [1,2], {'a':1}, '', 'x'*3000, 'zz-nobody@nowhere.test', "'; DROP TABLE tokens;--", '\u0000', 'žž', '../../etc/passwd']
PLAN={'token':['fill_names','disable','enable','unlock','note','window','drop_staged','code_now','show','codes','delete','scratch','rename','test','confirm'],
      'clients':['delete','secret'],'realms':['delete','try'],'directories':['delete','whois','people','ca','try','check','groups','lookup'],
      'sessions':['end','end_all','x'],'users':['delete','x'],'radtest':[None],'mail':['test','x'],'ha':['errors','history','x'],'upgrade':['x','check'],'web':['x','lb_facts'],'firewall':['rule_check','x']}
FIELDS=['name','to','note','window','code','new','id','directory','dn','q','user','password','server','port','secret','node','rule','family','proto','source','limit']
bad=collections.Counter(); ex={}; n=0
for ep,acts in PLAN.items():
    for a in acts:
        for i in range(12):
            b={k:random.choice(JUNK) for k in random.sample(FIELDS, random.randint(1,4))}
            if a: b['action']=a
            if 'name' not in b: b['name']=random.choice(['zz-nobody@nowhere.test',None,[],'x'*300])
            d=call(ep,b); n+=1; time.sleep(0.13)
            if isinstance(d,dict) and (d.get('http') in (500,502,504) or 'err' in d or 'broke' in str(d.get('error',''))):
                k='%s/%s %s'%(ep,a,str(d.get('http') or d.get('err') or d.get('error'))[:70]); bad[k]+=1; ex.setdefault(k,repr(b)[:200])
print('calls',n)
for k,v in bad.most_common(40): print(v,k,'|',ex[k])
