import sys, json, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
call('net',{'action':'read','node':'nodeb'}); time.sleep(8); d=call('net')
b=[n for n in d['nodes'] if n['name']=='nodeb'][0]; c=(b['now'].get('data') or {}).get('conf',{})
print('b now', c.get('ipv4_addresses'), (b['now'].get('data') or {}).get('hostname'))
want={'con':'System eth0','ipv4':{'addr':c['ipv4_addresses'][0],'gw':c.get('ipv4_gateway'),'dns':c.get('ipv4_dns'),'search':c.get('ipv4_search')},
      'ipv6':{'on': c.get('ipv6_method')=='manual','mode':'manual','addr':(c.get('ipv6_addresses') or [''])[0],'gw':c.get('ipv6_gateway')},
      'hostname': sys.argv[1] if len(sys.argv)>1 and sys.argv[1]!='none' else 'nodeb-trial.example.test','vip_elsewhere':True}
want['hostname']='nodeb-trial.example.test'
print(call('net',{'action':'apply','node':'nodeb','want':want}).get('message'))
last=None
for i in range(120):
    time.sleep(4); j=[n for n in call('net')['nodes'] if n['name']=='nodeb'][0]['job']
    cur=(j.get('id'), j.get('state'), (j.get('steps') or [{}])[-1].get('what','')[:140])
    if cur!=last: print(time.strftime('%H:%M:%S'), *cur); last=cur
    s=call('status'); 
    if s.get('trials') and i%5==0: print('   trials:', [(t['kind'],t['node'],int(t['until']-time.time())) for t in s['trials']])
    if j.get('state')=='done' and j.get('rollback'): break
    if j.get('state')=='failed': break
