import sys; sys.argv=['x','view']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
print(call('settings', {'settings': {'debug': 0}, 'node': 'nodeb'}).get('message'))
print(call('settings', {'settings': {'mail_helo': ''}, 'node': 'nodea'}).get('message'))
