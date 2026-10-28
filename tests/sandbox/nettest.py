import sys, json, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
d=call('net',{'action':'read','node':'nodeb'}); time.sleep(8); d=call('net')
b=[n for n in d['nodes'] if n['name']=='nodeb'][0]; print('b now ip', (b['now'].get('data') or {}).get('conf',{}).get('ipv4_addresses'))
want={'con':'System eth0','ipv4':{'addr':'127.0.0.4/8','gw':'127.0.0.254','dns':['192.0.2.53'],'search':['example.test']},'ipv6':{'on':True,'mode':'manual','addr':'2001:db8::4/64','gw':'2001:db8::1'},'hostname':'nodeb2.example.test','vip_elsewhere':True}
p=call('net',{'action':'plan','node':'nodeb','want':want}); print(json.dumps(p.get('plan') or p, indent=0)[:900])
print(call('net',{'action':'apply','node':'nodeb','want':want}))
for i in range(40):
    time.sleep(3); j=[n for n in call('net')['nodes'] if n['name']=='nodeb'][0]['job']
    print(j.get('state'), j.get('pct'), (j.get('steps') or [{}])[-1].get('what','')[:150])
    if j.get('state') in ('rebooting','failed','done') and j.get('pct',0)>=85 or j.get('state')=='failed': break
