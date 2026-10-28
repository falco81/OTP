import sys, json, time, subprocess
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
seen=len(open('/tmp/claude-0/fakenm/power_b').read().splitlines()) - 1
last=None; t0=time.time()
while time.time()-t0 < 520:
    lines=open('/tmp/claude-0/fakenm/power_b').read().splitlines()
    if len(lines)>seen:
        seen=len(lines); time.sleep(3); print(time.strftime('%H:%M:%S'),'** simulated reboot of nodeb', flush=True)
        subprocess.run(['bash','/tmp/claude-0/fwt/reboot_b.sh'])
    try:
        j=[n for n in call('net')['nodes'] if n['name']=='nodeb'][0]['job']
        s=call('status')
    except Exception as e:
        time.sleep(3); continue
    cur=(j.get('id'), j.get('state'), (j.get('steps') or [{}])[-1].get('what','')[:130])
    if cur!=last: print(time.strftime('%H:%M:%S'), *cur, '| trials', [(t['kind'],t['node'],int(t['until']-time.time())) for t in s.get('trials') or []], flush=True); last=cur
    if j.get('state')=='done' and j.get('rollback'): break
    if j.get('state')=='failed': break
    time.sleep(3)
