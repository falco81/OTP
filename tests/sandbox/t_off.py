import sys, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
act=sys.argv[-1] if False else None
import os
act=os.environ.get('ACT','tls_off')
print(call('ha',{'action':act}).get('message'))
for i in range(40):
    time.sleep(3)
    d=call('ha'); lt=d['link_tls']
    if i%3==0 or not lt['running']: print(i, lt['mode'] or '-', lt['running'], [(n['name'],n['step'],(n.get('said') or n.get('error') or '')[:70]) for n in lt['nodes']])
    if not lt['running'] and i>1: break
print('healthy', d['replication']['healthy'])
