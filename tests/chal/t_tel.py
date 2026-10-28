import sys, json, time, urllib.request, subprocess, re, os
sys.argv=['t','none'];exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
def sent():
    return json.loads(urllib.request.urlopen('http://127.0.0.1:18110/').read())['sent']
def reset(): urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18110/reset', data=b'{}', method='POST'))
R=[]
def ok(w,c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'].startswith('sms_')}
for api in ('rest','cgi'):
    reset()
    print(call('settings',{'settings':{'sms_mode':'teltonika','sms_tel_host':'127.0.0.1:18110','sms_tel_https':0,'sms_tel_user':'admin','sms_tel_password':'trbsecret','sms_tel_api':api,'code_send_max':50}}).get('message'))
    d=call('mail',{'action':'sms_test','to':'+420 603 111 222'})
    s=sent()
    ok('%s: test SMS sent (%s)'%(api, d.get('said','')[:60]), d.get('sent') and len(s)==1)
    want='+420603111222' if api=='rest' else '00420603111222'
    ok('%s: number as the box wants it (%s)'%(api, s[0]['number'] if s else '-'), s and s[0]['number']==want)
    ok('%s: no accents in the text: %r'%(api, s[0]['text'] if s else ''), s and all(ord(c)<128 for c in s[0]['text']))
# wrong password
call('settings',{'settings':{'sms_tel_password':'nope','sms_tel_api':'rest'}})
d=call('mail',{'action':'sms_test','to':'+420603111222'}); ok('wrong password: refused with words (%s)'%d.get('said','')[:70], not d.get('sent') and 'let otp in' in d.get('said',''))
call('settings',{'settings':{'sms_tel_password':'trbsecret'}})
# full sign-in through RADIUS with the CLI radtest finishing the second window
reset()
print(call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'sms','dest':'+420603111222'}).get('message'))
time.sleep(1.5)
env=dict(os.environ)
p=subprocess.Popen(['otp','--radtest','falco@corpnet.cz','falco-password-1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
time.sleep(3)
s=sent(); code=re.search(r'\b(\d{6})\b', s[-1]['text']).group(1) if s else '000000'
out,_=p.communicate(code+'\n', timeout=30)
print(out)
ok('otp --radtest: Challenge, the code asked for, then Access-Accept', 'Access-Challenge' in out and 'Access-Accept' in out and p.returncode==0)
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
print(call('settings',{'settings':{k:v for k,v in keep.items() if k!='sms_tel_password' and k!='sms_token'}}).get('message'))
print('%d/%d'%(sum(R),len(R)))
