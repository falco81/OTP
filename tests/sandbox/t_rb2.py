import sys, json, os, time
sys.path.insert(0,'/home/claude/build/out/otp-1.0.109'); sys.argv=['x']
import otp as O
O.load_config()
db=O.db_open({k:O.CONFIG.get(k) for k in O.DB_KEYS}); store=O.Storage(db)
O.CONFIG['rbackup_password']='Test-pass-987'; O.CONFIG['rbackup_keep']=2
hk,fps=O.ssh_keyscan('127.0.0.1',2222)
ca=open('/tmp/claude-0/fwt/ftps.crt').read()
O.rb_put_targets(store, [])
for d in [{'kind':'folder','path':'/tmp/rbfolder/otp','name':'local folder'},
          {'kind':'ftps','host':'127.0.0.1','port':2122,'user':'rbtest','password':'Rb-pass-123','path':'otp','tls_check':'ca','ca':ca,'name':'vsftpd'},
          {'kind':'sftp','host':'127.0.0.1','port':2222,'user':'rbtest','password':'Rb-pass-123','path':'backups/otp','name':'sftp box'},
          {'kind':'smb','host':'127.0.0.1','port':4445,'share':'rb','user':'rbtest','password':'Rb-pass-123','path':'otp/nightly','name':'nas'}]:
    t=O.rb_save(store, d, 'test')
    if t['kind']=='sftp': O.rb_set_fields(store, t['id'], 'test', '', hostkey=hk)
for i in range(3):
    r=O.rb_run(store, 'test', progress=lambda a,b,c: None)
    print(i, r.get('file'), r.get('bytes'), r['ok'], [(x['name'],x['ok'],x.get('error'),x.get('taken_away')) for x in r['targets']], r.get('error'))
    time.sleep(1.1)
for t in O.rb_targets(store):
    print(t['name'], [(x['name'],x['bytes']) for x in O.rb_remote_list(store, t['id'])])
