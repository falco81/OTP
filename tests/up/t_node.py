import sys; sys.argv=['x','view']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
print(call('settings', {'settings': {'debug': 1}, 'node': 'nodeb'}).get('message'))
print(call('settings', {'settings': {'mail_helo': 'nodea.example.cz'}}).get('message'))
d=call('settings')
for x in d['settings']:
    if x['key'] in ('debug','mail_helo','radius_bind'): print(x['key'], x['value'], x.get('per_node'), x.get('shared'), x['source'])
print(d.get('node'), d.get('cluster'), d.get('nodes'))
