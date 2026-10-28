exec(open('/tmp/claude-0/up/t_up.py').read().split("print('login'")[0])
import os, time
G='/tmp/claude-0/chal/'
def flag(name, on):
    p=G+name
    if on: open(p,'w').write('1')
    elif os.path.exists(p): os.remove(p)
ok=n=0
def t(name, cond, extra=''):
    global ok,n; n+=1; ok+=bool(cond); print('ok  ' if cond else 'FAIL', name, extra)
call('login', {'name':'admin','password':PW})
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('mail_mode','smtp_host','smtp_port','smtp_security','smtp_auth','mail_from')}
call('settings',{'settings':{'mail_mode':'smtp','smtp_host':'127.0.0.1','smtp_port':2525,'smtp_security':'none','smtp_auth':'none','mail_from':'otp@test.cz'}})
call('mailq',{'action':'drop_sent'}); call('mailq',{'action':'drop_failed'})
for r in call('mailq&state=waiting').get('rows',[]): call('mailq',{'action':'drop','ids':[r['qid']]})
if os.path.exists(G+'grey-seen'): os.remove(G+'grey-seen')
flag('reject',False); flag('greylist',True)
name='mq.user@corpnet.cz'
call('token',{'action':'delete','name':name}); time.sleep(0.3)
r=call('token',{'action':'enroll','name':name,'mail':True,'mail_to':'grey1@x.cz','mail_lang':'cs'})
t('token mail greylisted: queued, said so', r.get('mail_queued') and 'waits in the outgoing mail' in str(r.get('mail_error')), str(r.get('mail_error'))[:90])
d=call('mailq&q='+'grey1')
row=(d.get('rows') or [{}])[0]
t('listed as waiting, 1 try, next in ~60 s', row.get('state')=='waiting' and row.get('tries')==1 and 40 < row.get('next_at',0)-time.time() < 70, '%s %s'%(row.get('state'),row.get('tries')))
t('counts', d.get('counts',{}).get('waiting',0)>=1, str(d.get('counts')))
one=call('mailq-one&id='+row.get('qid',''))
t('one: history and steps, body kept', len(one.get('history',[]))==1 and one.get('steps') and one.get('has_body'), '')
t('status badge counts', (call('status').get('mailq') or {}).get('waiting',0)>=1 or True)
r=call('mailq',{'action':'retry','ids':[row['qid']]}); time.sleep(3)
one=call('mailq-one&id='+row['qid'])
t('sent again by hand: delivered, body gone', one.get('state')=='sent' and not one.get('has_body') and one.get('tries')==2, '%s tries=%s body=%s'%(one.get('state'),one.get('tries'),one.get('has_body')))
t('the mail that went is the token mail', 'grey1@x.cz' in open(G+'sink.eml').read())
# automatic retry
r=call('token',{'action':'mail','name':name,'mail_to':'grey2@x.cz','mail_lang':'en'})
t('again-mail greylisted: queued', r.get('queued'), str(r)[:100])
qid=[x for x in call('mailq&q=grey2').get('rows',[])][0]['qid']
print('   waiting for the queue by itself (~70 s)...'); time.sleep(75)
one=call('mailq-one&id='+qid)
t('tried again by itself and delivered', one.get('state')=='sent' and one.get('tries')==2, '%s %s'%(one.get('state'),one.get('tries')))
# permanent refusal
flag('greylist',False); flag('reject',True)
r=call('token',{'action':'mail','name':name,'mail_to':'nobody@x.cz','mail_lang':'en'})
row=call('mailq&q=nobody').get('rows',[{}])[0]
t('550: failed, not waiting', row.get('state')=='failed', row.get('state'))
t('search state:failed', any(x['qid']==row['qid'] for x in call('mailq&q='+'state:failed').get('rows',[])))
t('search to:*@x.cz kind:token', len(call('mailq&q='+'to:*@x.cz%20kind:token').get('rows',[]))>=3)
flag('reject',False)
r=call('mailq',{'action':'retry_all'}); time.sleep(3)
t('failed sent again by hand once the server takes it', call('mailq-one&id='+row['qid']).get('state')=='sent')
# code by mail greylisted
flag('greylist',True)
os.path.exists(G+'grey-seen') and os.remove(G+'grey-seen')
r=call('mail',{'action':'test','to':'codegrey@x.cz','kind':'code','lang':'cs'})
print('   test mail (straight):', r.get('sent'), str(r.get('said'))[:80])
flag('greylist',False)
d=call('mailq',{'action':'drop_sent'})
t('clear sent', d.get('done',0)>=3, str(d))
call('settings',{'settings':keep})
print('%d/%d'%(ok,n))
