import sys, json; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
out={}
for n in ['loadA@corpnet.cz','falco@corpnet.cz']:
    d=call('token',{'action':'enroll','name':n,'note':'load test'})
    m=d.get('made') or {}
    out[n]=m.get('secret') or m.get('key')
    print(n, list(m.keys())[:10], d.get('error'))
json.dump(out, open('tokens.json','w'))
