import sys, time, subprocess, os, json
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
def helpers():
    subprocess.run(['python3','-I','/usr/local/lib/otp/otp_web.py'], capture_output=True)
    subprocess.run(['python3','-I','/usr/local/lib/otp/otp_web.py'], capture_output=True, env=dict(os.environ, OTP_STATE='/tmp/nodeb/state'))
if 'start' in sys.argv[1:] or len(sys.argv)<2:
    pass
r=call('ha',{'action':'tls_link'}); print('start:', r.get('message') or r)
for i in range(90):
    helpers(); time.sleep(2)
    d=call('ha'); lt=d.get('link_tls') or {}
    st=[(n['name'], n.get('step'), (n.get('said') or n.get('error') or '')[:110]) for n in lt.get('nodes',[])]
    if i%5==0 or not lt.get('running'): print(i, lt.get('mode'), lt.get('running'), st)
    if not lt.get('running') and i>3: break
print('repl healthy', d['replication'].get('healthy'))
