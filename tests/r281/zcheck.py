import json, urllib.request
U = 'http://127.0.0.1:8088/api_jsonrpc.php'
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def rpc(m, p, auth=None):
    h = {'Content-Type': 'application/json-rpc'}
    if auth: h['Authorization'] = 'Bearer ' + auth
    return json.loads(op.open(urllib.request.Request(U, json.dumps({'jsonrpc': '2.0', 'method': m, 'params': p, 'id': 1}).encode(), h), timeout=300).read())
tok = rpc('user.login', {'username': 'Admin', 'password': 'zabbix'})['result']
t = rpc('template.get', {'filter': {'host': 'otp by SNMP'}, 'output': ['templateid']}, tok)['result'][0]['templateid']
c = lambda m, p: len(rpc(m, dict(p, output=['name'] if m != 'trigger.get' else ['description']), tok)['result'])
print('items', c('item.get', {'templateids': t}), 'lld', c('discoveryrule.get', {'templateids': t}),
      'protos', c('itemprototype.get', {'templateids': t}), 'triggers', c('trigger.get', {'templateids': t}),
      'tprotos', c('triggerprototype.get', {'templateids': t}), 'graphs', c('graph.get', {'templateids': t}),
      'gprotos', c('graphprototype.get', {'templateids': t}), 'macros', c('usermacro.get', {'hostids': t}),
      'vmaps', c('valuemap.get', {'hostids': t}))
d = rpc('templatedashboard.get', {'templateids': t, 'output': 'extend', 'selectPages': 'extend'}, tok)['result']
for db in d:
    print('dashboard', db['name'], [(p['name'], len(p['widgets'])) for p in db['pages']])
