import sys, json, subprocess, time, os
sys.path.insert(0, '/tmp/claude-0/r3/d')
from lib import admin
a = admin()
KEYS = ('portal', 'portal_realm', 'portal_first_code', 'sms_mode', 'sms_spool_dir', 'portal_tries',
        'names_czsk_letters', 'code_send_max')
if sys.argv[1] == 'up':
    c, st = a.call('settings')
    keep = {s['key']: s['value'] for s in st['settings'] if s['key'] in KEYS}
    c, ds = a.call('directories'); c, rs = a.call('realms')
    json.dump({'keep': keep, 'dirs': [d['name'] for d in (ds.get('directories') or ds if isinstance(ds, list) else ds.get('directories', []))],
               'realms': [r['name'] for r in (rs.get('realms') or [])]}, open('/tmp/claude-0/r6ui/before.json', 'w'))
    print('before', json.load(open('/tmp/claude-0/r6ui/before.json')))
    print(a.call('directories', {'action': 'save', 'directory': {'name': 'R6Dom', 'hosts': '127.0.0.1:23977', 'tls': 'none', 'port': 389,
          'base': 'OU=Česká Lípa,DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password',
          'timeout_s': 5, 'user_attr': 'sAMAccountName'}}))
    print(a.call('realms', {'action': 'save', 'realm': {'name': 'r6corp', 'suffix': 'corpnet.cz', 'directory': 'R6Dom', 'lookup': 'upn',
          'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp', 'sms'], 'groups': [{'group': 'Uživatelé VPN', 'reply': ''}]}}))
    print(a.call('settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'sms_mode': 'spool',
          'sms_spool_dir': '/var/spool/sms/outgoing', 'portal_tries': 100}}))
    print(a.call('settings', {'settings': {'portal_first_code': 'sms'}}))
else:
    b = json.load(open('/tmp/claude-0/r6ui/before.json'))
    keep = b['keep']
    print(a.call('settings', {'settings': {'portal_first_code': keep.get('portal_first_code', 'off')}}))
    print(a.call('settings', {'settings': {k: v for k, v in keep.items() if k != 'portal_first_code'}}))
    c, rs = a.call('realms')
    for r in rs.get('realms') or []:
        if r['name'] == 'r6corp':
            print(a.call('realms', {'action': 'delete', 'id': r['id']}))
    c, ds = a.call('directories')
    for d in (ds.get('directories') or []):
        if d['name'] == 'R6Dom':
            print(a.call('directories', {'action': 'delete', 'id': d['id']}))
    subprocess.run(['otp', '--delete', 'jcermak@corpnet.cz'], capture_output=True)
    c, st = a.call('settings')
    now = {s['key']: s['value'] for s in st['settings'] if s['key'] in KEYS}
    print('settings back:', now == keep, {k: (keep.get(k), now.get(k)) for k in KEYS if keep.get(k) != now.get(k)})
