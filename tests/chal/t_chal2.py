import os, sys, tempfile, time, base64, glob, re
V=sys.argv[1] if len(sys.argv)>1 else '1.0.109'
d=tempfile.mkdtemp(dir='/tmp/claude-0/chal'); os.environ['OTP_STATE']=d; sys.path.insert(0,'/home/claude/build/out/otp-%s'%V); sys.argv=['opt']
import otp as opt
spool=tempfile.mkdtemp(dir='/tmp/claude-0/chal')
opt.CONFIG.update({'db_engine':'sqlite','rate_limit_tries':0,'lockout_after':10,'sms_mode':'spool','sms_spool_dir':spool,
                   'mail_mode':'smtp','mail_from':'otp@corpnet.cz','smtp_host':'x','code_send_max':4,'code_tries':3})
SENT=[]
opt.mail_send=lambda store,msg,to,mode=None: (SENT.append((to,msg)), [{'ok':True,'said':'250 ok'}])[1]
store=opt.Storage(opt.open_db()); store.db.make_tables(); tk=opt.Tokens(store); opt.sealing_key(make=True)
store.directory_save({'name':'MOCK','hosts':'127.0.0.1:3899','port':389,'tls':'none','base':'DC=corpnet,DC=loc','bind_dn':'otp@corpnet.loc','bind_pw':'the-otp-service-password','user_attr':'sAMAccountName'})
store.realm_save({'name':'corp','suffix':'corpnet.cz','directory':'MOCK','lookup':'upn','auth_mode':'password_otp','methods':['totp','mail','sms']})
dirs={r['name'].lower(): opt.Directory(r) for r in store.directories(with_secret=True)}
auth=opt.Authenticator(store, tk, dirs)
store.client_save({'name':'asa','address':'10.0.0.1','secret':'s3cret'}) if hasattr(store,'client_save') else None
CL={'id':7,'name':'asa'}
R=[]
def ok(w,c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
def last_mail_code():
    time.sleep(0.4); return re.search(r'\b(\d{6})\b', SENT[-1][1].get_body(('plain',)).get_content()).group(1)
def last_sms_code():
    time.sleep(0.4); f=sorted(glob.glob(spool+'/otp-*'), key=os.path.getmtime)[-1]; return re.search(r'\b(\d{6})\b', open(f).read().split('\n\n',1)[1]).group(1), open(f).read()
PW='falco-password-1'
# --- a TOTP user in the same realm: as before
g=tk.enroll('falco@corpnet.cz','t'); k=g['secret']
code=lambda: opt.totp(base64.b32decode(k+'='*(-len(k)%8)), time.time())
dd=auth.decide('falco@corpnet.cz', PW+code(), client=CL)
ok('TOTP user, password_otp realm: let in exactly as before', dd.result=='accept')
# --- the same person switched to mail
m=tk.enroll_sent('falco@corpnet.cz','admin','mail','falco@corpnet.cz')
ok('mail token made with recovery codes', store.token('falco@corpnet.cz')['kind']=='mail' and len(m['scratch'])>0)
dd=auth.decide('falco@corpnet.cz', PW, client=CL)
ok('mail token: password alone -> challenge', dd.result=='challenge' and dd.state and 'f***' in dd.message.replace('*****','***') or ('@corpnet.cz' in dd.message))
print('   asks:', dd.message)
c=last_mail_code()
ok('the code went by mail to the address', SENT[-1][0]==['falco@corpnet.cz'])
a=auth.answer('falco@corpnet.cz','000000',dd.state,client=CL)
ok('wrong code -> asked again (challenge, same state)', a.result=='challenge' and a.state==dd.state)
a=auth.answer('falco@corpnet.cz',c,dd.state,client=CL)
ok('right code -> let in', a.result=='accept'); print([ (x['what'], x.get('said','')[:150]) for x in a.steps][:3])
a=auth.answer('falco@corpnet.cz',c,dd.state,client=CL)
ok('same answer again -> refused (state gone)', a.result=='reject')
# wrong password -> no mail sent
n=len(SENT); dd=auth.decide('falco@corpnet.cz','nope', client=CL); time.sleep(0.3)
ok('wrong directory password -> refused, no code sent', dd.result=='reject' and len(SENT)==n)
# recovery code in the second window
dd=auth.decide('falco@corpnet.cz', PW, client=CL); last_mail_code()
a=auth.answer('falco@corpnet.cz', m['scratch'][0], dd.state, client=CL)
ok('recovery code in the second window -> let in', a.result=='accept')
# tries exhausted
dd=auth.decide('falco@corpnet.cz', PW, client=CL); last_mail_code()
for i in range(3): a=auth.answer('falco@corpnet.cz','11111%d'%i, dd.state, client=CL)
ok('3 wrong codes -> refused and the question gone', a.result=='reject' and opt.chal_get(store, dd.state)[0] is None)
# send limit (4 in the window: used 3 so far + this one ok, next refused)
dd=auth.decide('falco@corpnet.cz', PW, client=CL)
dd2=auth.decide('falco@corpnet.cz', PW, client=CL)
ok('send limit: the 5th code in the window is refused', dd.result=='challenge' and dd2.result=='reject' and 'too many' in dd2.reason)
store.db.run("DELETE FROM meta WHERE k LIKE 'codesent:%'")
# another client / another name cannot answer
dd=auth.decide('falco@corpnet.cz', PW, client=CL); c=last_mail_code()
a=auth.answer('falco@corpnet.cz', c, dd.state, client={'id':8,'name':'other'})
ok('answer through another client is refused', a.result=='reject')
# expired
dd=auth.decide('falco@corpnet.cz', PW, client=CL); c=last_mail_code()
ch,raw=opt.chal_get(store, dd.state); ch['exp']=time.time()-1; opt.chal_put(store, dd.state, raw, ch)
a=auth.answer('falco@corpnet.cz', c, dd.state, client=CL)
ok('ran-out code refused', a.result=='reject' and 'ran out' in a.reason)
# --- SMS token
store.db.run("DELETE FROM meta WHERE k LIKE 'codesent:%'")
tk.enroll_sent('falco@corpnet.cz','admin','sms','603 123 456')
ok('number normalised with the prefix', store.token('falco@corpnet.cz')['dest']=='+420603123456')
dd=auth.decide('falco@corpnet.cz', PW, client=CL)
c,f=last_sms_code()
ok('SMS: challenge and a spool file "To: 420603123456"', dd.result=='challenge' and 'To: 420603123456' in f)
print('   asks:', dd.message)
a=auth.answer('falco@corpnet.cz', c, dd.state, client=CL)
ok('SMS code -> let in', a.result=='accept')
# --- realm in challenge mode: TOTP user gets second window
store.realm_save({'id':store.realms()[0]['id'],'name':'corp','suffix':'corpnet.cz','directory':'MOCK','lookup':'upn','auth_mode':'challenge'})
ok('methods kept when a save does not say', store.realms()[0]['methods']==['totp','mail','sms'])
g=tk.enroll('falco@corpnet.cz','t'); k=g['secret']
dd=auth.decide('falco@corpnet.cz', PW, client=CL)
ok('challenge realm, TOTP token: second window asks for the app code', dd.result=='challenge' and ('app' in dd.message or 'aplikace' in dd.message))
a=auth.answer('falco@corpnet.cz', code(), dd.state, client=CL)
ok('... and the app code lets in', a.result=='accept')
# --- mail not set up -> refused clearly
opt.CONFIG['mail_mode']='off'; tk.enroll_sent('falco@corpnet.cz','admin','mail','falco@corpnet.cz')
dd=auth.decide('falco@corpnet.cz', PW, client=CL)
ok('mail switched off -> refused with the reason', dd.result=='reject' and 'not set up' in dd.reason)
print('%d/%d'%(sum(R),len(R)))
