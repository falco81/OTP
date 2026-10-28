import sys; a=sys.argv[1:]; sys.argv=['x','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
import json, threading, subprocess, time
d=call('ha'); print('mode',d.get('mode'), 'lb', json.dumps(d.get('lb'))[:400], 'errbase', d.get('errbase'))
print('rep', json.dumps(d.get('replication'))[:500])
# helper stands in for otp-web.path
def helper():
    for i in range(20):
        time.sleep(0.5)
        import os
        if os.path.exists('/var/lib/otp/web/pglog.ask'):
            subprocess.run(['python3','-I','/usr/local/lib/otp/otp_web.py']); return
threading.Thread(target=helper).start()
e=call('ha',{'action':'errors'}); print('errors', json.dumps({k:e.get(k) for k in ('subs','log_file','log_said','fresh')})); 
for x in (e.get('log') or [])[-5:]: print('  ', x)
h=call('ha-history'); print('hist', len(h.get('rows',[])), (h.get('rows') or [])[:3])
