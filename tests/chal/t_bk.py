exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import json, time, base64, hmac, hashlib, struct
ok=n=0
def t(name, cond, extra=''):
    global ok,n; n+=1; ok+=bool(cond); print('ok  ' if cond else 'FAIL', name, extra)
def totp(secret, at=None):
    k=base64.b32decode(secret+'='*((8-len(secret)%8)%8)); c=int((at or time.time())//30)
    h=hmac.new(k,struct.pack('>Q',c),hashlib.sha1).digest(); o=h[-1]&15
    return '%06d'%((struct.unpack('>I',h[o:o+4])[0]&0x7fffffff)%1000000)
call('login', {'name':'admin','password':PW})
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('admin_show_key',)}
call('settings',{'settings':{'admin_show_key':1}})
T=[('bk.app@corpnet.cz',{}),('bk.mail@corpnet.cz',{'kind':'mail','dest':'bk.mail@firma.cz'}),('bk.sms@corpnet.cz',{'kind':'sms','dest':'+420777999888','lang':'en'}),('bk.off@corpnet.cz',{})]
for nm,extra in T:
    call('token',{'action':'delete','name':nm}); time.sleep(0.2)
    call('token',dict({'action':'enroll','name':nm},**extra))
call('token',{'action':'disable','name':'bk.off@corpnet.cz'})
call('token',{'action':'mail_fmt','name':'bk.mail@corpnet.cz','value':'text'})
d=call('tokens-backup',{'q':'name:bk.*'})
data=json.loads(d.get('file','{}'))
t('plain backup of 4', d.get('count')==4 and data.get('kind')=='otp-tokens' and len(data['tokens'])==4, str(d.get('count')))
app=[x for x in data['tokens'] if x['name']=='bk.app@corpnet.cz'][0]
t('app token: key and 5 codes in it', len(app.get('secret',''))>=16 and len(app['codes'])==5)
sms=[x for x in data['tokens'] if x['name']=='bk.sms@corpnet.cz'][0]
t('sms token: kind, number, lang', sms['kind']=='sms' and sms['dest']=='+420777999888' and sms.get('lang')=='en')
mail=[x for x in data['tokens'] if x['name']=='bk.mail@corpnet.cz'][0]
t('mail token: format text', mail.get('mail_fmt')=='text')
d2=call('tokens-backup',{'q':'name:bk.*','kind':'sms'})
t('kind filter', d2.get('count')==1)
lk=call('tokens-backup',{'q':'name:bk.*','passphrase':'correct-horse-battery'})
locked=json.loads(lk['file'])
t('locked backup has no key in the clear', 'locked' in locked and app['secret'] not in lk['file'])
short=call('tokens-backup',{'passphrase':'abc'})
t('too short passphrase refused', 'error' in short)
for nm,_ in T: call('token',{'action':'delete','name':nm})
f=[{'name':'b.json','text':lk['file']}]
r=call('token-import',{'files':f,'action':'peek'})
t('locked: asks for the passphrase', r.get('http')==423 or 'passphrase' in str(r.get('error')), str(r)[:80])
r=call('token-import',{'files':f,'action':'peek','passphrase':'wrong-one-xx'})
t('wrong passphrase refused', 'not the one' in str(r.get('error')), str(r.get('error'))[:60])
r=call('token-import',{'files':f,'action':'peek','passphrase':'correct-horse-battery'})
bk=r.get('backup',{})
t('peek: 4 tokens, none here', bk.get('count')==4 and not any(x['here'] for x in bk['tokens']))
r=call('token-import',{'files':f,'action':'peek','passphrase':'correct-horse-battery','q':'kind:sms'})
t('peek search kind:sms', [x['name'] for x in r['backup']['tokens']]==['bk.sms@corpnet.cz'], str(r.get('backup',{}).get('tokens'))[:80])
r=call('token-import',{'files':f,'action':'peek','passphrase':'correct-horse-battery','q':'777999'})
t('peek search by number', len(r['backup']['tokens'])==1)
r=call('token-import',{'files':f,'action':'peek','passphrase':'correct-horse-battery','q':'nosuchfield:x'})
t('peek bad field: said', bool(r.get('q_error')), str(r.get('q_error'))[:60])
r=call('token-import',{'files':f,'passphrase':'correct-horse-battery','names':['bk.app@corpnet.cz','bk.sms@corpnet.cz','bk.off@corpnet.cz']})
t('restore 3 picked', len([x for x in r.get('done',[]) if x['said'].startswith('restored')])==3, str(r)[:200])
t('the 4th not restored', not call('token&name=bk.mail@corpnet.cz').get('token'))
tk=call('token&name=bk.sms@corpnet.cz').get('token',{})
t('sms restored as it was', tk.get('kind')=='sms' and tk.get('dest')=='+420777999888' and tk.get('lang')=='en', str({k:tk.get(k) for k in ('kind','dest','lang')}))
t('switched off stays off', call('token&name=bk.off@corpnet.cz').get('token',{}).get('state')=='disabled')
cn=call('token',{'action':'code_now','name':'bk.app@corpnet.cz','first':True})
t('app token gives the same codes', cn.get('code')==totp(app['secret']), '%s vs %s'%(cn.get('code'),totp(app['secret'])))
r=call('token-import',{'files':f,'passphrase':'correct-horse-battery','names':['bk.app@corpnet.cz']})
t('again: kept without replace', r['done'][0]['said'].startswith('kept'))
r=call('token-import',{'files':f,'passphrase':'correct-horse-battery','names':['bk.app@corpnet.cz'],'replace':True})
t('with replace: restored', r['done'][0]['said'].startswith('restored'))
# plain backup restores too, all
r=call('token-import',{'files':[{'name':'p.json','text':d['file']}],'replace':True})
t('plain backup, everything', len([x for x in r['done'] if x['said'].startswith('restored')])==4)
# legacy .totp still works
r=call('token-import',{'files':[{'name':'legacy.one@corpnet.cz.totp','text':'JBSWY3DPEHPK3PXPJBSWY3DP\n" RATE_LIMIT 3 30\n" WINDOW_SIZE 3\n" TOTP_AUTH\n12345678\n87654321\n'}],'replace':True})
t('legacy .totp import', r['done'][0]['said'].startswith('imported'), str(r)[:100])
# mail queue search, same words
m=call('mailq&q='+'state:sent')
t('mailq: field search', 'rows' in m and not m.get('q_error'))
m=call('mailq&q='+'bogus:x')
t('mailq: a field it does not know is said', bool(m.get('q_error')), str(m.get('q_error'))[:60])
m=call('suggest&list=mailq')
t('mailq: fields offered', any(f[0]=='to' for f in m.get('fields',[])))
for nm,_ in T+[('legacy.one@corpnet.cz',{})]: call('token',{'action':'delete','name':nm})
call('settings',{'settings':keep})
print('%d/%d'%(ok,n))
