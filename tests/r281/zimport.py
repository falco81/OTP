import json, sys, urllib.request
U = 'http://127.0.0.1:8088/api_jsonrpc.php'
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def rpc(m, p, auth=None):
    h = {'Content-Type': 'application/json-rpc'}
    if auth: h['Authorization'] = 'Bearer ' + auth
    r = op.open(urllib.request.Request(U, json.dumps({'jsonrpc': '2.0', 'method': m, 'params': p, 'id': 1}).encode(), h), timeout=300)
    return json.loads(r.read())
tok = rpc('user.login', {'username': 'Admin', 'password': 'zabbix'})['result']
src = open(sys.argv[1]).read()
rules = {k: {'createMissing': True, 'updateExisting': True} for k in ('template_groups', 'templates', 'items', 'triggers', 'graphs', 'discoveryRules', 'valueMaps', 'templateDashboards', 'host_groups', 'hosts', 'templateLinkage')}
for k in ('items', 'triggers', 'graphs', 'discoveryRules', 'valueMaps', 'templateDashboards'):
    rules[k]['deleteMissing'] = True
rules['templateLinkage'] = {'createMissing': True}
for k in ('host_groups', 'hosts', 'template_groups', 'templates'):
    rules[k] = {'createMissing': True, 'updateExisting': True}
print(json.dumps(rpc('configuration.import', {'format': 'yaml', 'rules': rules, 'source': src}, tok))[:3000])
