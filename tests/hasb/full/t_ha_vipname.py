# t_ha_vipname.py VERSION - the VIP address with a certificate of its own, its name taken away (1.0.242): root
# refused the whole request for it ("a certificate of its own needs the name it is for"), and no change of nginx,
# keepalived or the firewall reached the node again - the VIP address stayed away for good. Now the node's
# certificate serves the address until a name is given: each node's request done, keepalived's file there, the
# VIP answering; given a name again, its own certificate back on it.
# Usage (root, on the two-node sandbox): python3 t_ha_vipname.py VERSION
import os, sys, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halib import *  # noqa: F401,F403,E402

helpers_on()
for n in 'ab':
    if not running(n):
        start(n)
    up(n)
    login(n)
ka_on()



def vip_now():
    return json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'web:vip'") or '{}')


def status(n):
    try:
        return json.load(open('%s/%s/state/web/status.json' % (S, n)))
    except (OSError, ValueError):
        return {}


def settle(n, since, wait=60):
    end = time.time() + wait
    while time.time() < end:
        st = status(n)
        if float(st.get('at') or 0) > since and st.get('state') in ('done', 'failed'):
            return st
        time.sleep(1)
    return status(n)


def save(fqdn):
    v = vip_now()
    body = {'action': 'vip_save', 'address': v.get('address'), 'fqdn': fqdn, 'vrid': v.get('vrid') or 61,
            'ifaces': v.get('ifaces') or {}, 'address6': v.get('address6') or ''}
    return call('a', '/api/web', body)


v0 = vip_now()
ok('the VIP address is on (%s)' % v0.get('address'), v0.get('on') and v0.get('address'))
prof = json.loads(dbq('a', "SELECT v FROM meta WHERE k = 'web:tls:vip'") or '{}')
ok('a certificate of the VIP address\'s own is kept', bool(prof.get('cert')))

for fqdn, what in (('', 'no name'), ('vip.otp.test', 'a name'), ('', 'the name taken away again')):
    t = time.time()
    c, x = save(fqdn)
    ok('%s: saved (%s)' % (what, c), c == 200, x)
    for n in 'ab':
        st = settle(n, t)
        ok('%s: node %s\'s request done, not refused (%s)' % (what, n, st.get('said')), st.get('state') == 'done')
        ok('%s: node %s keeps keepalived\'s file' % (what, n), os.path.exists('%s/%s/keepalived.conf' % (S, n)))
        vf = '%s/%s/nginx/otp_vip.conf' % (S, n)
        conf = open(vf).read() if os.path.exists(vf) else ''
        has = 'server_name vip.otp.test;' in conf
        ok('%s: node %s - the VIP address\'s own server %s' % (what, n, 'there' if fqdn else 'not there (the node\'s serves it)'),
           has == bool(fqdn))
    if not fqdn:
        log = open('%s/a/log/otp.log' % S).read()
        ok('%s: said in the log why its certificate is not used' % what, 'has a certificate of its own but no name' in log)

# as it was
c, x = save(v0.get('fqdn') or '')
ok('back as it was (%s)' % c, c == 200)
done()
