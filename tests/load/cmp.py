import json, sys
a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); skip=set(sys.argv[3].split(',')) if len(sys.argv)>3 else set()
bad=0
for part in sorted(set(a)|set(b)):
    if part in skip: continue
    x,y=a.get(part),b.get(part)
    if x==y: continue
    if isinstance(x,dict) and isinstance(y,dict):
        for k in sorted(set(x)|set(y)):
            if x.get(k)!=y.get(k):
                bad+=1; print('DIFF %s/%s:\n   before %s\n   after  %s'%(part,k,json.dumps(x.get(k))[:300],json.dumps(y.get(k))[:300]))
    else: bad+=1; print('DIFF',part,x,y)
print('differences:',bad)
