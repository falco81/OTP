# ui_sso_setup.py up|down VERSION - the installed pages set up for ui_sso.js: a mock AD (../cz/mockldap_cz.py on 23977,
# started beforehand), its realm, the enrolment pages on, signed in by the balancer from 127.0.0.1 with a key, and the
# root helper's nginx line put in by hand (no systemd here). down: everything as it was.
import sys, json, subprocess, os, importlib.util
sys.path.insert(0, '/tmp/claude-0/r3/d')
from lib import admin
VER = sys.argv[2] if len(sys.argv) > 2 else '1.0.239'
V = '/home/claude/build/out/otp-%s' % VER
KEEP = '/tmp/claude-0/ui_sso_before.json'
CONF = '/etc/nginx/conf.d/otp.conf'
KEYS = ('portal', 'portal_realm', 'portal_tries', 'names_czsk_letters', 'portal_sso', 'portal_sso_from',
        'portal_sso_header', 'portal_sso_logout', 'portal_first_code', 'web_proxy', 'web_proxy_from')
os.environ['OTP_VIP_NO_SERVICES'] = '1'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
a = admin()
if sys.argv[1] == 'up':
    c, st = a.call('settings')
    keep = {s['key']: s['value'] for s in st['settings'] if s['key'] in KEYS}
    json.dump({'keep': keep, 'conf': open(CONF).read()}, open(KEEP, 'w'))
    print(a.call('directories', {'action': 'save', 'directory': {'name': 'SsoDom', 'hosts': '127.0.0.1:23977', 'tls': 'none', 'port': 389,
          'base': 'OU=Česká Lípa,DC=corpnet,DC=loc', 'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password',
          'timeout_s': 5, 'user_attr': 'sAMAccountName'}})[0])
    print(a.call('realms', {'action': 'save', 'realm': {'name': 'ssocorp', 'suffix': 'corpnet.cz', 'directory': 'SsoDom', 'lookup': 'upn',
          'auth_mode': 'password_otp', 'enabled': 1, 'methods': ['totp'], 'groups': [{'group': 'Uživatelé VPN', 'reply': ''}]}})[0])
    print(a.call('settings', {'settings': {'portal': 1, 'portal_realm': 'corpnet.cz', 'portal_tries': 100, 'names_czsk_letters': 1,
          'portal_first_code': 'off', 'portal_sso_from': '127.0.0.1/32', 'portal_sso_logout': ''}}))
    c, k = a.call('portal-sso', {'action': 'key'})
    print('key', c)
    print(a.call('settings', {'settings': {'portal_sso': 1}}))
    open('/tmp/claude-0/ui_sso_key', 'w').write(k['key'])
    open(CONF, 'w').write(W.sso_peer_into(open(CONF).read(), True))
    t = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    print('nginx -t', t.returncode, t.stderr[-200:] if t.returncode else '')
    subprocess.run(['nginx', '-s', 'reload'])
else:
    b = json.load(open(KEEP))
    open(CONF, 'w').write(b['conf'])
    subprocess.run(['nginx', '-s', 'reload'])
    keep = b['keep']
    print(a.call('settings', {'settings': {'portal_sso': keep.get('portal_sso', 0)}}))
    print(a.call('settings', {'settings': {k: v for k, v in keep.items() if k != 'portal_sso'}}))
    c, rs = a.call('realms')
    for r in rs.get('realms') or []:
        if r['name'] == 'ssocorp':
            print(a.call('realms', {'action': 'delete', 'id': r['id']})[0])
    c, ds = a.call('directories')
    for d in (ds.get('directories') or []):
        if d['name'] == 'SsoDom':
            print(a.call('directories', {'action': 'delete', 'id': d['id']})[0])
    subprocess.run(['otp', '--delete', 'jcermak@corpnet.cz'], capture_output=True)
    c, st = a.call('settings')
    now = {s['key']: s['value'] for s in st['settings'] if s['key'] in KEYS}
    print('settings back:', all(now.get(k) == keep.get(k) for k in keep), {k: (keep.get(k), now.get(k)) for k in KEYS if keep.get(k) != now.get(k)})
    print('nginx back:', open(CONF).read() == b['conf'])
