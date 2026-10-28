import sys, json, time, subprocess
keep = sys.argv[1]=='keep'; OLD = sys.argv[2] if len(sys.argv)>2 else None
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
seen=len(open('/tmp/claude-0/fakenm/power_b').read().splitlines())
last=None; t0=time.time(); asked=False
old=sys.argv[2] if len(sys.argv)>2 else None
while time.time()-t0 < 520:
    lines=open('/tmp/claude-0/fakenm/power_b').read().splitlines()
    if len(lines)>seen:
        seen=len(lines); time.sleep(3); print(time.strftime('%H:%M:%S'),'** simulated reboot of nodeb', flush=True)
        subprocess.run(['bash','/tmp/claude-0/fwt/reboot_b.sh'])
    try:
        j=[n for n in call('net')['nodes'] if n['name']=='nodeb'][0]['job']
    except Exception: time.sleep(3); continue
    cur=(j.get('id'), j.get('state'), (j.get('steps') or [{}])[-1].get('what','')[:150])
    if cur!=last: print(time.strftime('%H:%M:%S'), *cur, flush=True); last=cur
    if j.get('state')=='trial' and keep and not asked:
        print('   keep ->', call('trial',{'kind':'net','node':'nodeb','action':'keep'})); asked=True
    if j.get('id')==OLD: time.sleep(3); continue
    if j.get('state')=='done' and (j.get('rollback') or j.get('kept')): break
    if j.get('state')=='failed': break
    time.sleep(3)
