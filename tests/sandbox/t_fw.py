import sys; a=sys.argv[1:]; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
import json
for x in a:
    if x=='get':
        d=call('firewall'); 
        for n in d.get('nodes',[]): n['fw']={'backend':n['fw'].get('backend'),'now4':len((n['fw'].get('now') or {}).get('4',[]))}; 
        print(json.dumps(d,indent=1)[:4000] if 'nodes' in d else d)
    else:
        print(call('firewall', json.loads(x)))
