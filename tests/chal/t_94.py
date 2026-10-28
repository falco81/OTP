import json, ssl, sys, time, urllib.request, http.cookiejar
exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
ok=n=0
def t(name, cond, extra=''):
    global ok,n; n+=1; ok+=bool(cond); print('ok  ' if cond else 'FAIL', name, extra)
call('login', {'name':'admin','password':PW})
# a token admin
call('users',{'action':'delete','name':'tadm'})
r=call('users',{'action':'add','name':'tadm','role':'tokenadmin','password':'Tadm-pass-12345!','must_change':0}); print(r)
for n_,k,d in (('sms.user@corpnet.cz','sms','+420777123456'),):
    call('token',{'action':'delete','name':n_}); time.sleep(0.2)
    call('token',{'action':'enroll','name':n_,'kind':k,'dest':d})
# second session as tokenadmin
cj2=http.cookiejar.CookieJar()
op2=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj2))
def call2(api, body=None):
    req=urllib.request.Request(B+'?api='+api, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json'})
    try:
        with op2.open(req, timeout=60) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return dict(json.loads(e.read()), http=e.code)
        except Exception: return {'http': e.code}
print('tadm login', call2('login',{'name':'tadm','password':'Tadm-pass-12345!'}).get('ok'))
r=call2('token',{'action':'dest','name':'sms.user@corpnet.cz','dest':'+420111222333'})
t('token admin cannot redirect codes of a token in use', r.get('http')==403, str(r.get('error') or r)[:90])
r=call2('token',{'action':'delete','name':'sms.user@corpnet.cz'})
t('token admin cannot take away a token in use', r.get('http')==403, str(r.get('error') or r)[:90])
r=call2('token',{'action':'disable','name':'sms.user@corpnet.cz'})
t('token admin may switch it off', not r.get('http'), str(r)[:80])
call('token',{'action':'enable','name':'sms.user@corpnet.cz'})
r=call('token',{'action':'dest','name':'sms.user@corpnet.cz','dest':'+420777123456'})
t('full admin may change where codes go', not r.get('http') and not r.get('error'), str(r)[:80])
# pending token: token admin may delete
call('token',{'action':'delete','name':'pend.user@corpnet.cz'})
call('token',{'action':'enroll','name':'pend.user@corpnet.cz','pending':True})
r=call2('token',{'action':'delete','name':'pend.user@corpnet.cz'})
t('token admin may take away a pending token', not r.get('http'), str(r)[:80])
# empty picture upload does not delete logo
r=call('art',{'action':'upload','slot':'portal','data':''})
t('empty picture refused', r.get('http')==400 or 'no picture' in str(r), str(r)[:80])
# mail settings with newline refused
r=call('settings',{'settings':{'mail_from_name':'OTP\nBcc: x@y'}})
t('newline in mail setting refused', 'line' in str(r).lower() and not r.get('message','').startswith('changed'), str(r)[:100])
# lockout counts from zero after the pause
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('lockout_after','lockout_min','rate_limit_tries')}
call('settings',{'settings':{'lockout_after':3,'lockout_min':1,'rate_limit_tries':0}})
name='after-rebuild@corpnet.cz'
call('token',{'action':'enable','name':name})
for i in range(3): call('token',{'action':'test','name':name,'code':'000000','use':1})
tk=call('token&name='+name).get('token',{})
t('locked after 3 wrong, count kept (1.0.109)', (tk.get('locked_until') or 0) > time.time() and int(tk.get('failures') or 0)>=3, 'failures=%s locked=%s'%(tk.get('failures'), tk.get('locked_until')))
call('token',{'action':'enable','name':name})
call('settings',{'settings':keep})
call('users',{'action':'delete','name':'tadm'})
print('%d/%d'%(ok,n))
