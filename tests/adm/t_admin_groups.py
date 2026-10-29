import os, sys, json, time, subprocess, urllib.request, tempfile, shutil
# The administrators from the directory: no group set lets nobody in; only members of a set group, with its role; a change of the groups ends the open sign-ins. Needs the mock LDAP on 3899 (test/mockldap.py). Usage: python3 t_admin_groups.py VERSION
V='/home/claude/build/out/otp-%s' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.153')
D=tempfile.mkdtemp(prefix='otp-admgroups-'); run=D+'/run'; os.makedirs(run)
env=dict(os.environ, OTP_STATE=D, OTP_CONFIG=D+'/config.json', OTP_LOGDIR=D, OTP_RUN=run, OTP_STAY_ROOT='1')
json.dump({'db_engine':'sqlite','radius_bind':'127.0.0.1','radius_auth_port':31912,'radius_acct_port':31913,'api_port':29871,'node_name':'admtest'}, open(D+'/config.json','w'))
os.environ.update(env); sys.path.insert(0,V); sys.argv=['x']
import otp
otp.load_config(saved=None)
st=otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
st.directory_save({'name':'corp','hosts':'127.0.0.1:3899','tls':'none','port':389,'base':'DC=corpnet,DC=loc',
  'bind_dn':'CN=otp,OU=Service,DC=corpnet,DC=loc','bind_pw':'the-otp-service-password','timeout_s':5,'user_attr':'sAMAccountName'})
st.add_account('local','fulladmin','Local-Admin-Pass-152!', must_change=0)
p=subprocess.Popen([sys.executable, V+'/otp.py','--daemon'], env=env, stdout=open(D+'/d.out','w'), stderr=subprocess.STDOUT)
time.sleep(6)
import atexit; atexit.register(lambda: (p.terminate(), p.wait(10)))
TOK=open(run+'/api-token').read().strip()
def call(path, body=None, sess=None):
    h={'X-Otp-Token':TOK,'Content-Type':'application/json','X-Otp-Client':'127.0.0.1'}
    if sess: h['X-Otp-Session']=sess
    req=urllib.request.Request('http://127.0.0.1:29871'+path, data=json.dumps(body).encode() if body is not None else None, headers=h, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')
_, a=call('/api/auth/login', {'name':'local','password':'Local-Admin-Pass-152!'}); S=a['token']
def setg(**kw):
    c,r=call('/api/settings', {'settings':kw}, S); assert c==200, r
def login(n,pw):
    c,r=call('/api/auth/login', {'name':n,'password':pw})
    if c!=200: return c, r.get('error'), None
    w=call('/api/auth/whoami', None, r.get('token'))[1]
    return c, (w.get('who') or {}).get('role'), r.get('token')
R=[]
def ok(w,c): R.append(bool(c)); print('ok  ' if c else 'FAIL', w)
setg(login_tries=100, admin_directory='corp', admin_group_full='', admin_group_token='', admin_group_readonly='')
for u,pw in (('falco','falco-password-1'),('outsider','outsider-password-1')):
    c,role,_=login(u,pw); ok('no group set: %s refused (%s %s)'%(u,c,role), c==401)
setg(admin_group_full='VPN_SUPPLIER_X')
c,role,_=login('nested','nested-password-1'); ok('full = VPN_SUPPLIER_X: nested (member) let in as %s'%role, c==200 and role=='fulladmin')
c,role,_=login('falco','falco-password-1'); ok('full = VPN_SUPPLIER_X: falco (not member) refused %s'%c, c==401)
c,role,_=login('outsider','outsider-password-1'); ok('outsider (no groups) refused %s'%c, c==401)
setg(admin_group_full='', admin_group_readonly='CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc')
c,role,_=login('falco','falco-password-1'); ok('readonly by DN: falco let in as %s'%role, c==200 and role=='readonly')
c,role,_=login('nested','nested-password-1'); ok('readonly by DN, nested via nested group: %s %s'%(c,role), True)
c,role,_=login('outsider','outsider-password-1'); ok('outsider still refused %s'%c, c==401)
c,role,_=login('falco','wrong'); ok('falco wrong password refused %s'%c, c==401)
# the account made by an earlier sign-in, groups taken away since
c,role,FS=login('falco','falco-password-1')
c2,w=call('/api/auth/whoami', None, FS); ok('falco signed in: whoami %s %s'%(c2,(w.get('who') or {}).get('role')), (w.get('who') or {}).get('role')=='readonly')
ok('falco reads the tokens before the change', call('/api/tokens', None, FS)[0]==200)
setg(admin_group_full='', admin_group_token='', admin_group_readonly='CN=Helpdesk,OU=Groups,DC=corpnet,DC=loc')
c2,w=call('/api/tokens', None, FS); ok('group changed: falco\'s open sign-in ended at once (%s)'%c2, c2==401)
setg(admin_group_readonly='')
c,role,_=login('falco','falco-password-1'); ok('groups emptied: falco, who signed in before, refused %s'%c, c==401)
setg(admin_group_full='  ; ;  ')
c,role,_=login('falco','falco-password-1'); ok('only spaces and ; : refused %s'%c, c==401)
setg(admin_group_full='DC=corpnet,DC=loc')
c,role,_=login('falco','falco-password-1'); ok('the domain root given as a group: refused %s'%c, c==401)
setg(admin_group_full='Domain Users')
c,role,_=login('outsider','outsider-password-1'); ok('a group nobody here is in: outsider refused %s'%c, c==401)
print('ALL %d / %d'%(sum(R),len(R)))
p.terminate(); p.wait(10)
