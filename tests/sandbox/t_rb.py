import sys, json, os, time
sys.path.insert(0,'/home/claude/build/out/otp-1.0.109'); sys.argv=['x']
import otp as O
O.load_config()
db=O.db_open({k:O.CONFIG.get(k) for k in O.DB_KEYS}); store=O.Storage(db)
def T(d, old=None): return O.rb_checked(d, old)
res={}
def run(name, t):
    r=O.rb_try(t); res[name]=r['ok']; print('%-14s %s %s %s' % (name, r['ok'], r.get('error',''), r.get('secs')))
    return r
run('folder', T({'kind':'folder','path':'/tmp/rbfolder/otp'}))
run('ftp', T({'kind':'ftp','host':'127.0.0.1','port':2121,'user':'rbtest','password':'Rb-pass-123','path':'otp/backups'}))
r=run('ftps-system', T({'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp'}))
ca=open('/tmp/claude-0/fwt/ftps.crt').read()
run('ftps-ca', T({'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp','tls_check':'ca','ca':ca}))
r=run('ftps-none', T({'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp','tls_check':'none'}))
fp=(r.get('server_cert') or {}).get('fingerprint'); print('fp', fp)
run('ftps-pin', T({'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp','tls_check':'pin','pin':fp}))
run('ftps-implicit', T({'kind':'ftps','implicit':1,'host':'127.0.0.1','port':2990,'user':'rbtest','password':'Rb-pass-123','path':'imp','tls_check':'ca','ca':ca}))
run('ftps-badpin', T({'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp','tls_check':'pin','pin':'0'*64}))
hk,fps=O.ssh_keyscan('127.0.0.1',2222); print('hostkey fps', fps)
t=T({'kind':'sftp','host':'127.0.0.1','port':2222,'user':'rbtest','password':'Rb-pass-123','path':'backups/otp'}); t['hostkey']=hk
run('sftp-pw', t)
t2=dict(t); t2['kind']='scp'; t2['path']='/home/rbtest/scpb'
run('scp-pw', t2)
priv,pub=O.ssh_keygen('otp-test'); os.makedirs('/home/rbtest/.ssh',exist_ok=True); open('/home/rbtest/.ssh/authorized_keys','w').write(pub+'\n'); os.system('chown -R rbtest /home/rbtest/.ssh; chmod 700 /home/rbtest/.ssh; chmod 600 /home/rbtest/.ssh/authorized_keys')
t3=T({'kind':'sftp','host':'127.0.0.1','port':2222,'user':'rbtest','path':'keyb'}); t3['hostkey']=hk; t3['key']=O.seal_secret(priv,bind=O.RB_BIND)
run('sftp-key', t3)
t4=dict(t3); t4['hostkey']=hk.replace('AAAA','AAAB',1)
run('sftp-badhost', t4)
run('smb', T({'kind':'smb','host':'127.0.0.1','port':4445,'share':'rb','user':'rbtest','password':'Rb-pass-123','path':'otp/nightly','smb_encrypt':1}))
run('smb-badpw', T({'kind':'smb','host':'127.0.0.1','port':4445,'share':'rb','user':'rbtest','password':'x','path':'otp'}))
print(res)
