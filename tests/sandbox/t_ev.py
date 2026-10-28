import sys; a=sys.argv[1:]; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
import time
print(call('ha',{'action':'pause_in'}).get('message'))
time.sleep(12)
print(call('ha',{'action':'resume_in'}).get('message'))
time.sleep(12)
for r in call('ha-history')['rows'][:6]: print(r['kind'], r['level'], r['what'], r['words'][:120])
