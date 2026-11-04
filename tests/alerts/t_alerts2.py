# t_alerts2.py VERSION - the alerts of 1.0.242: what the nodes see and was not mailed. In one process, over a SQLite
# database of its own: each node's health row (the tokens' key missing, two nodes under one name, RADIUS in trouble,
# logs not shipped, SNMP, rows not written by otp, time without chrony), a certificate the CA did not renew, the
# internal certificates, a failed update and upgrade, mails that do not go, SELinux, the security check; each off by
# its switch; the noisy ones off by default. The events: a change on trial that went back, a sign-in by the balancer
# refused - in the mail as they happen. Nothing is sent: the sending is caught.
import os, sys, json, time, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.242'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-al2-'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'al1', 'api_port': 29899, 'radius_auth_port': 31972,
           'radius_acct_port': 31973}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STAY_ROOT='1')
sys.path.insert(0, V); sys.argv = ['x']
import otp  # noqa: E402
otp.load_config(saved=None)
st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


now = time.time()
me = otp.node_name()
otp.CONFIG.update(alerts=1, alerts_to='ops@example.cz', acme=1, snmp=1, mail_from='otp@example.cz', mail_mode='smtp', smtp_host='127.0.0.1')
st.set_meta('node:' + me, json.dumps({'at': now, 'version': otp.__version__, 'radius': True}))
health = {'at': now, 'radius': ['0.0.0.0:1812'], 'key_lost': True, 'name_clash': 'two nodes are called al1',
          'radius_trouble': 'the reply port is refused', 'ntp_problem': '',
          'siem': {'on': True, 'trouble': {'10.0.0.9:514': 'connection refused'}, 'dropped': 12},
          'isemon': {'on': True, 'trouble': {}}, 'snmp': {'listening': False, 'error': 'port 161 is taken'},
          'dbguard_refused': [{'what': 'meta web:vip', 'why': 'its signature is not right', 'at': now}]}
st.set_meta('host:health:' + me, json.dumps(health))
st.set_meta('acme:state:' + me, json.dumps({'ok': False, 'failed_at': now - 3600, 'said': 'the CA refused: rateLimited'}))
st.set_meta('dbtls:server:' + me, json.dumps({'cert_end': now + 5 * 86400}))
st.set_meta('hatls:node:' + me, json.dumps({'cert_end': now + 400 * 86400}))
st.set_meta('host:osup:plan', json.dumps({'state': 'failed', 'ended': now - 600, 'failed_on': me}))
st.set_meta('host:osup:node:' + me, json.dumps({'said': 'dnf: no space left'}))
st.set_meta('host:osup:check:' + me, json.dumps({'state': 'failed', 'at': now - 60, 'error': 'mirror down'}))
st.set_meta('upgrade:plan', json.dumps({'id': 'u1', 'version': '9.9.9', 'order': [me]}))
st.set_meta('upgrade:node:' + me, json.dumps({'id': 'u1', 'state': 'failed', 'said': 'checks failed'}))
st.set_meta('mailq:x1', json.dumps({'state': 'failed', 'kind': 'code', 'created': now - 100, 'last_try': now - 50, 'said': '550 no such user'}))
st.set_meta('mailq:x2', json.dumps({'state': 'failed', 'kind': 'alert', 'created': now - 100}))
st.set_meta('host:selinux:now:' + me, json.dumps({'data': {'mode': 'Permissive', 'problems': ['the boolean httpd_can_network_connect is off']}}))
p = otp.alert_problems(st, 'en')
want = {'key:' + me: 'the tokens\' key missing', 'clash:' + me: 'two nodes under one name', 'radius:trouble:' + me: 'RADIUS in trouble',
        'ship:siem:' + me: 'logs not reaching syslog', 'snmp:' + me: 'the SNMP agent not listening', 'acme:' + me: 'the CA did not renew',
        'cert:pg:' + me: 'PostgreSQL\'s certificate running out', 'osup:failed': 'the update of the system failed',
        'osup:check:' + me: 'it cannot look for updates', 'upgrade:u1': 'the upgrade failed', 'dbguard:' + me: 'rows not written by otp',
        'mailq': 'mails with a code that did not go'}
for k, words in want.items():
    ok('on by default: %s (%s)' % (words, k), k in p, sorted(p))
ok('...the link\'s certificate a year away: not said', 'cert:link:' + me not in p)
ok('...isemon with nothing wrong: not said', 'ship:isemon:' + me not in p)
ok('...the dropped lines told', '12 lines dropped' in p['ship:siem:' + me]['said'], p['ship:siem:' + me])
ok('...a failed alert mail itself is not one of the mails counted', p['mailq']['title'].startswith('1 mail'), p['mailq'])
ok('...the tokens\' key: bad, to the database pane', p['key:' + me]['level'] == 'bad' and p['key:' + me]['pane'] == 'db')
ok('...each links to a pane of the pages', all(x['pane'] in ('db', 'ha', 'radius', 'siem', 'isemon', 'monitor', 'acme', 'osup', 'upgrade', 'hisec', 'mailq', 'time', 'web', 'backup', 'codes', 'dir', 'guard', 'network', 'portal') for x in p.values()),
   {k: x['pane'] for k, x in p.items()})
ok('off by default: SELinux, the security check, the replication behind - not said', not any(k.startswith(('selinux:', 'hisec', 'repl:behind')) for k in p), sorted(p))
otp.CONFIG.update(alerts_selinux=1)
p = otp.alert_problems(st, 'en')
ok('SELinux switched on: said', 'selinux:' + me in p and 'httpd_can_network_connect' in p['selinux:' + me]['said'], sorted(p))
for sw, gone in (('alerts_nodes', ('key:', 'clash:', 'radius:trouble:')), ('alerts_shipping', ('ship:',)), ('alerts_snmp', ('snmp:',)),
                 ('alerts_acme', ('acme:',)), ('alerts_updates', ('osup:',)), ('alerts_upgrade', ('upgrade:',)),
                 ('alerts_dbguard', ('dbguard:',)), ('alerts_mailq', ('mailq',)), ('alerts_selinux', ('selinux:',))):
    otp.CONFIG[sw] = 0
    p = otp.alert_problems(st, 'en')
    ok('%s off: %s not said' % (sw, '/'.join(gone)), not any(k.startswith(gone) for k in p), sorted(p))
    otp.CONFIG[sw] = 1
otp.CONFIG['alerts_cert_days'] = 0
ok('the certificates switched off (0 days): PostgreSQL\'s not said', 'cert:pg:' + me not in otp.alert_problems(st, 'en'))
otp.CONFIG['alerts_cert_days'] = 21
otp.CONFIG['snmp'] = 0
ok('SNMP not switched on: its agent not looked at', 'snmp:' + me not in otp.alert_problems(st, 'en'))
otp.CONFIG['acme'] = 0
ok('ACME not switched on: its state not looked at', 'acme:' + me not in otp.alert_problems(st, 'en'))
# time without chrony
h2 = dict(health, ntp_problem='the clock is not synchronised (timedatectl): Settings → Time')
st.set_meta('host:health:' + me, json.dumps(h2))
st.set_meta('ntp:now:' + me, json.dumps({'data': {'chrony': False}}))
p = otp.alert_problems(st, 'en')
ok('a clock without chrony (timedatectl not in sync): said', 'time:' + me in p and 'timedatectl' in p['time:' + me]['said'], sorted(p))
ok('Czech words too', 'klíč' in otp.alert_problems(st, 'cs')['key:' + me]['title'])
# the events, mailed as they happen
sent = []


def mails(msgs):
    out = []
    for m in msgs:
        for part in m.walk():
            if part.get_content_maintype() == 'text':
                out.append((part.get_payload(decode=True) or b'').decode('utf-8', 'replace'))
    return '\n'.join(out)



otp.alert_send = lambda store, msg, to, kind, keys: (sent.append(msg), {'ok': True})[1]
otp.alerts_evaluate(st)            # the first turn: where the events begin
st.add_event('settings', 'the firewall and access went back to what they were before 10:00: not kept in time', 'warn')
st.add_event('settings', 'al1 went back to the network it had before (10.0.0.5): not kept within 5 min', 'warn')
st.add_event('settings', 'the new network of al1 is on trial: kept within 5 min, or it goes back', 'warn')
st.add_event('enrolment', 'a sign-in by the load balancer was refused (from 203.0.113.9, for novak): not from the balancers named', 'warn')
sent.clear()
r = otp.alerts_evaluate(st)
body = mails(sent)
ok('a change on trial that went back: in the mail (firewall, network)', 'went back to what they were' in body and 'went back to the network it had before' in body, body[:500])
ok('...the trial merely begun: not', 'is on trial' not in body)
ok('...a sign-in by the balancer refused: not (off by default)', 'by the load balancer was refused' not in body)
otp.CONFIG['alerts_sso'] = 1
st.add_event('enrolment', 'a sign-in by the load balancer was refused (from 203.0.113.10, for svoboda): the key in X-Otp-Sso-Key is not the one set', 'warn')
sent.clear(); otp.alerts_evaluate(st)
body = mails(sent)
ok('...switched on: in the mail', 'svoboda' in body, body[:300])
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
