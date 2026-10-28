import sys, time, subprocess, os, json
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
def helpers():
    subprocess.run(['python3','-I','/usr/local/lib/otp/otp_web.py'], capture_output=True)
    subprocess.run(['python3','-I','/usr/local/lib/otp/otp_web.py'], capture_output=True, env=dict(os.environ, OTP_STATE='/tmp/nodeb/state'))
for i in range(60):
    helpers(); time.sleep(3)
    lt=call('ha').get('link_tls') or {}
    st=[(n['name'], n.get('step'), (n.get('said') or n.get('error') or '')[:90]) for n in lt.get('nodes',[])]
    if i%3==0: print(i, len(lt.get('authority_end',[])), st)
    if i>4 and not lt.get('running') and all(n.get('step')=='done' for n in lt.get('nodes',[])): print('end', i, st); break
