import json, urllib.request
U = 'http://127.0.0.1:8088/api_jsonrpc.php'
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def rpc(m, p, auth=None):
    h = {'Content-Type': 'application/json-rpc'}
    if auth: h['Authorization'] = 'Bearer ' + auth
    return json.loads(op.open(urllib.request.Request(U, json.dumps({'jsonrpc': '2.0', 'method': m, 'params': p, 'id': 1}).encode(), h), timeout=300).read())
tok = rpc('user.login', {'username': 'Admin', 'password': 'zabbix'})['result']
it = rpc('item.get', {'hostids': '10684', 'output': ['key_', 'state', 'error', 'lastvalue', 'lastclock'], 'webitems': True}, tok)['result']
bad = [(i['key_'], i['error'][:120]) for i in it if i['state'] == '1']
got = [i for i in it if int(i['lastclock'] or 0) > 0]
print('items', len(it), 'with data', len(got), 'not supported', len(bad))
for b in bad: print('  NS', b)
for i in it:
    if i['key_'] in ('otp.host.cpu.util', 'otp.host.mem.util', 'otp.radius.rate[reject]', 'otp.version', 'otp.snmp.available', 'otp.db.latency'):
        print('  ', i['key_'], i['lastvalue'])
lld = rpc('discoveryrule.get', {'hostids': '10684', 'output': ['key_', 'state', 'error']}, tok)['result']
for r in lld: print('LLD', r['key_'], r['state'], r['error'][:100])
pr = rpc('problem.get', {'hostids': '10684', 'output': ['name', 'severity']}, tok)['result']
print('problems', [(p['name'], p['severity']) for p in pr])
