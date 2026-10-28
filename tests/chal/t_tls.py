exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
call('login', {'name':'admin','password':PW})
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('mail_mode','smtp_host','smtp_port','smtp_security','smtp_auth','smtp_verify')}
for verify in (0,1):
    call('settings',{'settings':{'mail_mode':'smtp','smtp_host':'127.0.0.1','smtp_port':2526,'smtp_security':'starttls','smtp_auth':'none','smtp_verify':verify}})
    r=call('mail',{'action':'test','to':'jan@faltynek.net','kind':'short','lang':'cs'})
    print('verify=%d'%verify, r.get('sent'), str(r.get('said') or r.get('error'))[:150])
print(open('/tmp/claude-0/chal/tls.eml').read()[:5] if __import__('os').path.exists('/tmp/claude-0/chal/tls.eml') else 'no mail')
call('settings',{'settings':keep})
