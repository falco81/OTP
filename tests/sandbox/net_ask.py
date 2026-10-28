import sys, json, time
host, ip = sys.argv[1], sys.argv[2]
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
call('net',{'action':'read','node':'nodeb'}); time.sleep(8); d=call('net')
b=[n for n in d['nodes'] if n['name']=='nodeb'][0]; c=(b['now'].get('data') or {}).get('conf',{})
want={'con':'System eth0','ipv4':{'addr':ip,'gw':c.get('ipv4_gateway'),'dns':c.get('ipv4_dns'),'search':c.get('ipv4_search')},
      'ipv6':{'on': c.get('ipv6_method')=='manual','mode':'manual','addr':(c.get('ipv6_addresses') or [''])[0],'gw':c.get('ipv6_gateway')},
      'hostname': host,'vip_elsewhere':True}
r=call('net',{'action':'apply','node':'nodeb','want':want}); print(r.get('message') or r)
