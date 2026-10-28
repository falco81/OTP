import tarfile, io
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
def raw_get(q):
    with op.open(urllib.request.Request(B+'?api='+q), timeout=300) as r:
        return r.read(), r.headers.get('Content-Disposition')
print('short', call('db', {'action':'download_ticket','kind':'','passphrase':'short'}))
t = call('db', {'action':'download_ticket','kind':'','passphrase':'correct horse battery'})
print('ticket', {k:t.get(k) for k in ('name','error')})
data, cd = raw_get('db-download&ticket='+t['ticket'])
print('got', len(data), cd)
print('again', call('db-download&ticket='+t['ticket']))
tf = tarfile.open(fileobj=io.BytesIO(data)); print([m.name for m in tf.getmembers()])
print('secret in clear?', open('/var/lib/otp/secrets.key').read().strip()[:16].encode() in data if __import__('os').access('/var/lib/otp/secrets.key', 4) else 'n/a')
chk = call('db-restore&check=1', raw=data)
print('check', {k: chk.get(k) for k in ('upload','locked','file','error')}, (chk.get('says') or {}).get('kind'))
print('wrong', call('db', {'action':'upload_restore','upload':chk['upload'],'passphrase':'nope nope nope','check':True}).get('error'))
ok = call('db', {'action':'upload_restore','upload':chk['upload'],'passphrase':'correct horse battery','check':True})
print('right', ok.get('error'), (ok.get('says') or {}).get('with_key'))
r = call('db', {'action':'upload_restore','upload':chk['upload'],'passphrase':'correct horse battery'})
print('restore', r)
# kept dump with key
d = call('db')
dumps = d.get('dumps') or []
print('dumps', [x.get('name') for x in dumps][:2])
if dumps:
    t = call('db', {'action':'download_ticket','name':dumps[0]['name'],'kind':'dump','passphrase':'correct horse battery'})
    print('dump ticket', t.get('name'), t.get('error'))
    if t.get('ticket'):
        data, cd = raw_get('db-download&ticket='+t['ticket']); print('dump got', len(data), cd)
        chk = call('db-restore&check=1', raw=data); print('dump check', chk.get('error') or (chk.get('says') or {}).get('kind'))
