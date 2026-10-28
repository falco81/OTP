import sys, json, time; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
print(call('realms',{'action':'save','realm':{'name':'load.test','suffix':'load.test','auth_mode':'otp','directory':'','enabled':1,'groups':[],'reply':'Class = LOAD'}}))
out={}
for i in range(200):
    n='u%03d@load.test'%i
    for k in range(5):
        d=call('token',{'action':'enroll','name':n})
        if d.get('made'): break
        time.sleep(1)
    out[n]=(d.get('made') or {}).get('secret')
json.dump(out, open('tokens200.json','w')); print(len([v for v in out.values() if v]))
