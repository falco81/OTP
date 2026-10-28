import sys, json, time, subprocess
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
print(call('power',{'how':'reboot','targets':['nodea2','nodeb'],'order':'rolling'}).get('plan'))
def show():
    d=call('power'); print([(n['name'], (n.get('row') or {}).get('state'), n['alive']) for n in d.get('nodes',[])])
for i in range(15):
    time.sleep(2); show()
    if open('/tmp/claude-0/fakenm/power_b').read(): break
print('B power file:', open('/tmp/claude-0/fakenm/power_b').read().strip())
open('/tmp/btime_b','w').write(str(int(time.time()))); subprocess.run(['bash','/tmp/claude-0/up/startb.sh'])
for i in range(30):
    time.sleep(2)
    try: show()
    except Exception as e: print('err', e)
    if open('/tmp/claude-0/fakenm/power_a').read(): break
print('A power file:', open('/tmp/claude-0/fakenm/power_a').read().strip())
