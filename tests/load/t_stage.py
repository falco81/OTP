import sys,time;sys.argv=['otp'];sys.path.insert(0,'/usr/local/lib/otp');import otp
otp.load_config()
st=otp.Storage(otp.open_db()); tk=otp.Tokens(st)
n='stagetest@load.test'
st.token_drop(n) if st.token(n) else None
tk.enroll(n,'t'); tk.stage_replacement(n,'t')
for i in range(12):
    ok,said=tk.confirm(n,'000000')
print(said)
t=st.token(n); print('state',t['state'],'failures',t['failures'],'locked',t['locked_until'],'pending',bool(t['pending_secret']))
# enable/disable pending
st.token_drop(n); tk.enroll(n,'t',pending=True)
print(otp.token_switch_state(st,n,False)); st.token_write(n,{'state':'disabled'})
print(otp.token_switch_state(st,n,True))
st.token_drop(n)
# overview day buckets
o=st.overview_now(since=time.time()-40*86400)
print(o['step'], len(o['series']), [time.strftime('%m-%d %H:%M',time.localtime(b['t'])) for b in o['series'][:3]])
