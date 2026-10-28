import sys, json; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
print(call('web',{'action':'vip_on'}).get('message'))
import time; time.sleep(6)
d=call('firewall')
for n in d['nodes']:
    print(n['name'], [(a['key'], a['on'], a['rules']) for a in n['auto'] if a['key'] in ('cluster','vrrp')])
print(call('web',{'action':'vip_off'}).get('message'))
