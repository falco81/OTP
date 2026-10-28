import sys; sys.argv=['x','view']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
n='administrator@dpmo.cz'
d=call('token',{'action':'code_now','name':n}); print({k:d.get(k) for k in ('code','next','ends','period')})
r=call('token',{'action':'test','name':n,'code':d['code']}); print('test:', r.get('good'), r.get('said'))
