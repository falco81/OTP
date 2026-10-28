import sys, time, re, subprocess, os
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
env=dict(os.environ, OTP_CONFIG='/etc/otp/config.json')
subprocess.run(['python3','/usr/local/lib/otp/otp.py','--set','admin_2fa=1'],env=env,capture_output=True)
subprocess.run(['python3','/usr/local/lib/otp/otp.py','--reset-2fa','admin'],env=env,capture_output=True)
time.sleep(10)
def fresh():
    global op
    cj=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj))
    globals()['op']=op
    return call('login', {'name':'admin','password':PW})
def lastcode():
    time.sleep(2)
    s=open('/tmp/claude-0/chal/sink.eml').read()
    return re.findall(r'Subject:.*?(\d{6})', s)[-1]
print(fresh().get('mfa'))
print(call('mfa', {'action':'enrol_start','kind':'mail','dest':'boss@example.cz'}))
print('again too soon', call('mfa', {'action':'enrol_start','kind':'mail','dest':'boss@example.cz'}).get('error'))
print('confirm', call('mfa', {'action':'enrol_confirm','code':lastcode()}))
print(fresh().get('mfa'), call('mfa').get('dest'))
print('send', call('mfa', {'action':'send'}))
c=lastcode()
print('check', call('mfa', {'action':'check','code':c}))
print('usage', call('mfa', {'action':'check','code':c}).get('error'))
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--users'],env=env,capture_output=True,text=True).stdout[-600:])
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--reset-2fa','admin'],env=env,capture_output=True,text=True).stdout.strip())
subprocess.run(['python3','/usr/local/lib/otp/otp.py','--set','admin_2fa=0'],env=env,capture_output=True)
