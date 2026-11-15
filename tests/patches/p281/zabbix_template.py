# zabbix_template.py OUT.yaml - the Zabbix 7.0 template "otp by SNMP" (1.0.281), made from one table
# of what otp's SNMPv3 agent answers (OTP-MIB): items, discovery (walk[] + SNMP_WALK_TO_JSON, as
# Zabbix's own templates do), triggers, value maps, graphs and a dashboard of five pages.
# The UUIDs come from the names - the same template made again imports over the one before.
import hashlib, sys
import yaml

T = 'otp by SNMP'
B = '1.3.6.1.4.1.8072.9999.9999.7'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'otp_by_snmp.yaml'
VERSION = sys.argv[2] if len(sys.argv) > 2 else '1.0.281'


def uid(*parts):
    h = bytearray(hashlib.md5(('otp-zabbix|' + '|'.join(parts)).encode()).digest())
    h[6] = (h[6] & 0x0F) | 0x40
    h[8] = (h[8] & 0x3F) | 0x80
    return h.hex()


def tags(*pairs):
    return [{'tag': k, 'value': v} for k, v in pairs]


VALUEMAPS = {
    'otp: yes/no': [('0', 'no'), ('1', 'yes')],
    'otp: up/down': [('0', 'down'), ('1', 'up')],
    'otp: on/off': [('0', 'off'), ('1', 'on')],
    'otp: listening': [('0', 'not listening'), ('1', 'listening')],
    'otp: running': [('0', 'stopped'), ('1', 'running')],
    'otp: ok/failed': [('0', 'failed'), ('1', 'ok')],
    'otp: holds the VIP': [('0', 'no'), ('1', 'holds the VIP address')],
    'otp: none': [('-1', 'none')],
    'Host availability status': [('0', 'not available'), ('1', 'available'), ('2', 'unknown')],
}

MACROS = [
    ('{$OTP.NODATA.TIMEOUT}', '10m', 'No SNMP answer for this long: a problem.'),
    ('{$OTP.CPU.UTIL.WARN}', '80', 'CPU utilization (%) for a warning.'),
    ('{$OTP.CPU.UTIL.CRIT}', '90', 'CPU utilization (%) for a problem.'),
    ('{$OTP.MEM.UTIL.WARN}', '90', 'Memory utilization (%) for a warning.'),
    ('{$OTP.FS.PUSED.WARN}', '85', 'A file system this full (%): a warning.'),
    ('{$OTP.FS.PUSED.CRIT}', '95', 'A file system this full (%): a problem.'),
    ('{$OTP.FS.INODES.WARN}', '90', 'Inodes of a file system used (%): a warning.'),
    ('{$OTP.RADIUS.QUEUE.WARN}', '200', 'RADIUS requests waiting for a worker, for 5 minutes.'),
    ('{$OTP.DB.LATENCY.WARN}', '0.2', 'SELECT 1 taking longer than this (seconds), for 5 minutes.'),
    ('{$OTP.CERT.EXPIRY.WARN}', '21', 'A certificate of the pages ending within this many days: a warning.'),
    ('{$OTP.CERT.EXPIRY.CRIT}', '7', 'A certificate of the pages ending within this many days: a problem.'),
    ('{$OTP.HA.HEARTBEAT.MAX}', '120', 'A node of the cluster not heard from for this long (seconds).'),
    ('{$OTP.HA.BEHIND.WARN}', '104857600', 'The other node this far behind in taking this node\'s rows (bytes).'),
    ('{$OTP.BACKUP.AGE.MAX}', '129600', 'The newest nightly copy older than this (seconds).'),
    ('{$OTP.RBACKUP.AGE.MAX}', '129600', 'The newest good backup sent away older than this (seconds; 691200 for weekly).'),
    ('{$OTP.CLOCK.OFFSET.MAX}', '1000', 'This node this far from the time servers (milliseconds).'),
    ('{$OTP.MAIL.WAITING.MAX}', '20', 'Mail waiting for 30 minutes, at most.'),
]

ITEMS = []      # (key, name, oid|None, opts)


def item(key, name, oid=None, **o):
    ITEMS.append((key, name, oid, o))


# -- the agent and otp itself
item('otp.snmp.available', 'SNMP agent availability', None, type='INTERNAL', ikey='zabbix[host,snmp,available]',
     valuemap='Host availability status', comp='health', delay='1m',
     desc='Availability of SNMP checks on the host, as the host list shows it.')
item('otp.sysname', 'System name', '1.3.6.1.2.1.1.5.0', vt='CHAR', delay='1h', comp='system', inv='NAME', heartbeat='12h')
item('otp.sysdescr', 'System description', '1.3.6.1.2.1.1.1.0', vt='CHAR', delay='1h', comp='system', inv='OS', heartbeat='12h')
item('otp.syscontact', 'System contact', '1.3.6.1.2.1.1.4.0', vt='CHAR', delay='1h', comp='system', inv='CONTACT', heartbeat='12h')
item('otp.syslocation', 'System location', '1.3.6.1.2.1.1.6.0', vt='CHAR', delay='1h', comp='system', inv='LOCATION', heartbeat='12h')
item('otp.version', 'Version', B + '.1.1.0', vt='CHAR', delay='15m', comp='system', inv='SOFTWARE', heartbeat='12h')
item('otp.node', 'Node name', B + '.1.2.0', vt='CHAR', delay='1h', comp='system', heartbeat='12h')
item('otp.site', 'Site', B + '.1.3.0', vt='CHAR', delay='1h', comp='system', heartbeat='12h')
item('otp.db.engine', 'Database engine', B + '.1.4.0', vt='CHAR', delay='1h', comp='database', heartbeat='12h')
item('otp.high_security', 'High security', B + '.1.5.0', valuemap='otp: on/off', delay='5m', comp='security')
item('otp.in_cluster', 'In a cluster', B + '.1.6.0', valuemap='otp: yes/no', delay='5m', comp='cluster')
item('otp.uptime', 'Uptime (otp)', B + '.1.7.0', units='uptime', mult='0.01', vt='FLOAT', comp='system',
     desc='Since the otp daemon started.')
# -- RADIUS
item('otp.radius.listening', 'RADIUS listening', B + '.2.1.0', valuemap='otp: listening', comp='radius')
item('otp.radius.queued', 'RADIUS requests waiting', B + '.2.2.0', comp='radius', units='')
for i, (k, n) in enumerate([('packets', 'packets'), ('accept', 'Access-Accept'), ('reject', 'Access-Reject'),
                            ('challenge', 'Access-Challenge'), ('accounting', 'Accounting answered'),
                            ('status', 'Status-Server answered'), ('dropped', 'dropped'),
                            ('malformed', 'malformed packets'), ('unknown', 'from no client'),
                            ('repeated', 'sent again'), ('no_database', 'without the database'),
                            ('maintenance', 'not answered in maintenance')], 3):
    item('otp.radius.rate[%s]' % k, 'RADIUS %s, per second' % n, B + '.2.%d.0' % i, vt='FLOAT', units='rps',
         rate=True, comp='radius')
item('otp.radius.clients', 'RADIUS clients', B + '.2.15.0', comp='radius', delay='15m')
item('otp.radius.realms', 'Realms', B + '.2.16.0', comp='radius', delay='15m')
item('otp.radius.directories', 'Directories', B + '.2.17.0', comp='directory', delay='15m')
item('otp.radius.day[accept]', 'Accepted in the last 24 hours', B + '.2.18.0', comp='radius', delay='5m')
item('otp.radius.day[reject]', 'Rejected in the last 24 hours', B + '.2.19.0', comp='radius', delay='5m')
item('otp.radius.day[challenge]', 'Challenged in the last 24 hours', B + '.2.20.0', comp='radius', delay='5m')
# -- the database, the tokens, the alerts
item('otp.db.up', 'Database up', B + '.3.1.0', valuemap='otp: up/down', comp='database')
item('otp.db.latency', 'Database latency', B + '.3.2.0', vt='FLOAT', units='s', mult='0.000001', comp='database')
for i, (k, n) in enumerate([('all', 'all'), ('active', 'active'), ('pending', 'pending'), ('disabled', 'disabled'),
                            ('used_30d', 'used in 30 days'), ('never_used', 'never used')], 1):
    item('otp.tokens[%s]' % k, 'Tokens: %s' % n, B + '.4.%d.0' % i, comp='tokens', delay='5m')
item('otp.alerts[bad]', 'Problems otp sees: bad', B + '.5.1.0', comp='alerts')
item('otp.alerts[warn]', 'Problems otp sees: warnings', B + '.5.2.0', comp='alerts')
# -- the machine
item('otp.host.cpu.idle.rate', 'CPU idle ticks, per second', B + '.10.1.0', vt='FLOAT', rate=True, comp='cpu', history='1d')
item('otp.host.cpu.total.rate', 'CPU ticks in all, per second', B + '.10.2.0', vt='FLOAT', rate=True, comp='cpu', history='1d')
item('otp.host.cpu.util', 'CPU utilization', None, type='CALCULATED', vt='FLOAT', units='%', comp='cpu',
     params='100*(1-last(//otp.host.cpu.idle.rate)/last(//otp.host.cpu.total.rate))',
     desc='All cores: the part of the time not idle.')
item('otp.host.cpu.cores', 'CPU cores', B + '.10.3.0', comp='cpu', delay='1h')
for i, m in ((4, 1), (5, 5), (6, 15)):
    item('otp.host.load[%d]' % m, 'Load average (%d min)' % m, B + '.10.%d.0' % i, vt='FLOAT', mult='0.01', comp='cpu')
item('otp.host.mem.total', 'Memory: total', B + '.10.7.0', units='B', mult='1024', comp='memory', delay='15m')
item('otp.host.mem.used', 'Memory: used', B + '.10.8.0', units='B', mult='1024', comp='memory')
item('otp.host.mem.util', 'Memory utilization', None, type='CALCULATED', vt='FLOAT', units='%', comp='memory',
     params='100*last(//otp.host.mem.used)/last(//otp.host.mem.total)')
item('otp.host.swap.used', 'Swap: used', B + '.10.9.0', units='B', mult='1024', comp='memory')
item('otp.host.disk.read', 'Disks: read', B + '.10.10.0', vt='FLOAT', units='Bps', rate=True, comp='storage')
item('otp.host.disk.write', 'Disks: written', B + '.10.11.0', vt='FLOAT', units='Bps', rate=True, comp='storage')
item('otp.host.net.rx', 'Network: in', B + '.10.12.0', vt='FLOAT', units='bps', rate=True, mult8=True, comp='network')
item('otp.host.net.tx', 'Network: out', B + '.10.13.0', vt='FLOAT', units='bps', rate=True, mult8=True, comp='network')
item('otp.host.uptime', 'Uptime (machine)', B + '.10.14.0', units='uptime', comp='system')
# -- the cluster
item('otp.ha.cluster', 'Cluster', B + '.12.1.0', valuemap='otp: yes/no', comp='cluster', delay='5m')
item('otp.ha.vip.on', 'VIP address set', B + '.12.2.0', valuemap='otp: yes/no', comp='cluster', delay='5m')
item('otp.ha.vip.here', 'VIP address on this node', B + '.12.3.0', valuemap='otp: holds the VIP', comp='cluster')
item('otp.ha.vip.address', 'VIP address', B + '.12.4.0', vt='CHAR', comp='cluster', delay='15m', heartbeat='12h')
# -- backups, mail
item('otp.backup.nightly', 'Nightly copy', B + '.13.1.0', valuemap='otp: on/off', comp='backup', delay='15m')
item('otp.backup.age', 'Nightly copy: age', B + '.13.3.0', units='s', comp='backup', delay='5m', none=True, vt='FLOAT',
     valuemap='otp: none')
item('otp.rbackup.on', 'Backups sent away', B + '.13.4.0', valuemap='otp: on/off', comp='backup', delay='15m')
item('otp.rbackup.ok', 'Backup sent away: the newest went', B + '.13.5.0', valuemap='otp: ok/failed', comp='backup', delay='5m')
item('otp.rbackup.age', 'Backup sent away: age of the newest good one', B + '.13.7.0', units='s', comp='backup', delay='5m',
     none=True, vt='FLOAT', valuemap='otp: none')
for i, st in enumerate(('sending', 'waiting', 'sent', 'failed', 'expired'), 1):
    item('otp.mail[%s]' % st, 'Mail: %s' % st, B + '.14.%d.0' % i, comp='mail')
# -- signing in to the administration
item('otp.signin.kerberos', 'Sign-in with Windows', B + '.15.1.0', valuemap='otp: on/off', comp='signin', delay='5m')
item('otp.signin.cert', 'Sign-in with a certificate', B + '.15.2.0', valuemap='otp: on/off', comp='signin', delay='5m')
item('otp.signin.password_off', 'No password at all', B + '.15.3.0', valuemap='otp: yes/no', comp='signin', delay='5m')
item('otp.signin.second_step', 'Second step of the administrators', B + '.15.4.0', valuemap='otp: on/off', comp='signin', delay='5m')
item('otp.crl.count', 'CRLs kept', B + '.15.5.0', comp='signin')
item('otp.crl.bad', 'CRLs not had or run out', B + '.15.6.0', comp='signin')
item('otp.ocsp.mode', 'OCSP', B + '.15.7.0', vt='CHAR', comp='signin', delay='5m', heartbeat='12h')
item('otp.ocsp.count', 'OCSP answers kept', B + '.15.8.0', comp='signin')
item('otp.ocsp.bad', 'OCSP answers not good', B + '.15.9.0', comp='signin')
# -- the clock, the logs sent away
item('otp.clock.engaged', 'Clock guard holding codes back', B + '.16.1.0', valuemap='otp: yes/no', comp='clock')
item('otp.clock.mode', 'Clock guard', B + '.16.2.0', vt='CHAR', comp='clock', delay='15m', heartbeat='12h')
item('otp.clock.offset', 'Clock: offset from the time servers', B + '.16.3.0', vt='FLOAT', units='s', mult='0.001', comp='clock')
item('otp.clock.skew', 'Clock: skew from the other node or the directory', B + '.16.4.0', vt='FLOAT', units='s', mult='0.001', comp='clock')
for w, n in ((1, 'isemon'), (2, 'SIEM')):
    s = 'isemon' if w == 1 else 'siem'
    item('otp.logs.on[%s]' % s, 'Logs to %s' % n, B + '.17.%d.1.0' % w, valuemap='otp: on/off', comp='logs', delay='5m')
    item('otp.logs.trouble[%s]' % s, 'Logs to %s: in trouble' % n, B + '.17.%d.2.0' % w, valuemap='otp: yes/no', comp='logs')
    item('otp.logs.sent[%s]' % s, 'Logs to %s: lines per second' % n, B + '.17.%d.3.0' % w, vt='FLOAT', rate=True, comp='logs')
    item('otp.logs.dropped[%s]' % s, 'Logs to %s: lines dropped per second' % n, B + '.17.%d.4.0' % w, vt='FLOAT', rate=True, comp='logs')

TP = 'otp: '        # every name starts so (triggers, graphs)


def mk_item(key, name, oid, o):
    it = {'uuid': uid('item', key), 'name': name}
    typ = o.get('type', 'SNMP_AGENT')
    if typ != 'ZABBIX_PASSIVE':
        it['type'] = typ
    if typ == 'SNMP_AGENT':
        it['snmp_oid'] = 'get[%s]' % oid
    it['key'] = o.get('ikey', key)
    if o.get('delay', '1m') != '1m':
        it['delay'] = o['delay']
    if o.get('history'):
        it['history'] = o['history']
    vt = o.get('vt')
    if vt:
        it['value_type'] = vt
    if vt in ('CHAR', 'TEXT'):
        it['trends'] = '0'
    if o.get('units'):
        it['units'] = o['units']
    if typ == 'CALCULATED':
        it['params'] = o['params']
    if o.get('desc') or oid:
        it['description'] = (o.get('desc') or '') + ('\n' if o.get('desc') else '') + (
            'OID: %s (OTP-MIB)' % oid if oid else '')
    if o.get('inv'):
        it['inventory_link'] = o['inv']
    if o.get('valuemap'):
        it['valuemap'] = {'name': o['valuemap']}
    pre = []
    if o.get('rate'):
        pre.append({'type': 'CHANGE_PER_SECOND', 'parameters': ['']})
    if o.get('mult8'):
        pre.append({'type': 'MULTIPLIER', 'parameters': ['8']})
    if o.get('mult'):
        pre.append({'type': 'MULTIPLIER', 'parameters': [o['mult']]})
    if o.get('none'):
        # 4294967295 is "none" in OTP-MIB: -1 here, shown as "none" (a value map)
        pre.append({'type': 'JAVASCRIPT', 'parameters': ['return value == 4294967295 ? -1 : value;']})
    if o.get('heartbeat'):
        pre.append({'type': 'DISCARD_UNCHANGED_HEARTBEAT', 'parameters': [o['heartbeat']]})
    if pre:
        it['preprocessing'] = pre
    it['tags'] = tags(('component', o.get('comp', 'otp')))
    return it


def ex(key, fn='last', arg=''):
    return '%s(/%s/%s%s)' % (fn, T, key, (',' + arg) if arg else '')


TRIGGERS = {}     # key -> [triggers]  (single-item)
MULTI = []        # top-level


def trig(key, expr, name, prio, desc='', opdata='Current: {ITEM.LASTVALUE1}', deps=(), scope='availability',
         recovery=None):
    t = {'uuid': uid('trigger', name), 'expression': expr, 'name': TP + name, 'priority': prio}
    if recovery:
        t['recovery_mode'] = 'RECOVERY_EXPRESSION'
        t['recovery_expression'] = recovery
    if opdata:
        t['opdata'] = opdata
    if desc:
        t['description'] = desc
    if deps:
        t['dependencies'] = [{'name': TP + n, 'expression': e} for n, e in deps]
    t['tags'] = tags(('scope', scope))
    if key:
        TRIGGERS.setdefault(key, []).append(t)
    else:
        MULTI.append(t)
    return (name, expr)


nosnmp = trig('otp.snmp.available', 'max(/%s/zabbix[host,snmp,available],{$OTP.NODATA.TIMEOUT})=0' % T,
              'No SNMP answer', 'HIGH', 'The agent of otp does not answer: the node is down, the daemon stopped, '
              'SNMP is off on Settings - Monitoring, or the user and its passphrases differ.')
trig('otp.uptime', ex('otp.uptime') + '<10m', 'otp has been restarted', 'INFO', 'Uptime is less than 10 minutes.',
     scope='notice')
trig('otp.version', 'change(/%s/otp.version)=1 and length(last(/%s/otp.version))>0' % (T, T),
     'Version has changed', 'INFO', 'otp was updated (or went back).', scope='notice')
rl = trig('otp.radius.listening', ex('otp.radius.listening') + '=0', 'RADIUS is not listening', 'DISASTER',
          'Nobody signs in to the VPN through this node.', deps=[('No SNMP answer', nosnmp[1])])
trig('otp.radius.queued', ex('otp.radius.queued', 'min', '5m') + '>{$OTP.RADIUS.QUEUE.WARN}',
     'RADIUS requests are waiting', 'WARNING', 'More than {$OTP.RADIUS.QUEUE.WARN} requests waited for a '
     'worker for 5 minutes: the directory or the database is slow.', scope='performance')
dbd = trig('otp.db.up', ex('otp.db.up') + '=0', 'The database does not answer', 'DISASTER',
           deps=[('No SNMP answer', nosnmp[1])])
trig('otp.radius.rate[no_database]', ex('otp.radius.rate[no_database]', 'min', '5m') + '>0',
     'RADIUS answers without the database', 'HIGH', deps=[('The database does not answer', dbd[1])])
trig('otp.db.latency', ex('otp.db.latency', 'min', '5m') + '>{$OTP.DB.LATENCY.WARN}', 'The database is slow',
     'WARNING', scope='performance', deps=[('The database does not answer', dbd[1])])
trig('otp.alerts[bad]', ex('otp.alerts[bad]') + '>0', 'otp sees {ITEM.LASTVALUE1} problem(s)', 'HIGH',
     'Settings - Alerts and the Overview of the pages say which; each is a problem of its own below too.',
     opdata='', scope='notice')
bad = ('otp sees {ITEM.LASTVALUE1} problem(s)', ex('otp.alerts[bad]') + '>0')
trig('otp.alerts[warn]', ex('otp.alerts[warn]') + '>0', 'otp sees {ITEM.LASTVALUE1} warning(s)', 'WARNING',
     opdata='', scope='notice', deps=[bad])
cc = trig('otp.host.cpu.util', ex('otp.host.cpu.util', 'min', '5m') + '>{$OTP.CPU.UTIL.CRIT}',
          'High CPU utilization', 'AVERAGE', scope='performance')
trig('otp.host.cpu.util', ex('otp.host.cpu.util', 'min', '5m') + '>{$OTP.CPU.UTIL.WARN}',
     'CPU utilization is rising', 'WARNING', scope='performance', deps=[cc])
trig('otp.host.mem.util', ex('otp.host.mem.util', 'min', '5m') + '>{$OTP.MEM.UTIL.WARN}',
     'High memory utilization', 'AVERAGE', scope='capacity')
trig('otp.ha.vip.here', 'change(/%s/otp.ha.vip.here)<>0' % T, 'The VIP address moved', 'INFO',
     'This node took the VIP address, or gave it up.', scope='notice', recovery=None)
MULTI.append({'uuid': uid('trigger', 'nightly'), 'expression': '%s=1 and (%s>{$OTP.BACKUP.AGE.MAX} or %s=-1)' % (
    ex('otp.backup.nightly'), ex('otp.backup.age'), ex('otp.backup.age')), 'name': TP + 'No nightly copy of the database',
    'priority': 'WARNING', 'opdata': 'Age: {ITEM.LASTVALUE2}', 'tags': tags(('scope', 'availability'))})
MULTI.append({'uuid': uid('trigger', 'rbackup-failed'), 'expression': '%s=1 and %s=0' % (
    ex('otp.rbackup.on'), ex('otp.rbackup.ok')), 'name': TP + 'The backup sent away failed', 'priority': 'HIGH',
    'tags': tags(('scope', 'availability'))})
MULTI.append({'uuid': uid('trigger', 'rbackup-old'), 'expression': '%s=1 and (%s>{$OTP.RBACKUP.AGE.MAX} or %s=-1)' % (
    ex('otp.rbackup.on'), ex('otp.rbackup.age'), ex('otp.rbackup.age')), 'name': TP + 'No backup went away in time', 'priority': 'WARNING',
    'opdata': 'Age: {ITEM.LASTVALUE2}', 'tags': tags(('scope', 'availability')),
    'dependencies': [{'name': TP + 'The backup sent away failed', 'expression': '%s=1 and %s=0' % (
        ex('otp.rbackup.on'), ex('otp.rbackup.ok'))}]})
trig('otp.mail[failed]', ex('otp.mail[failed]') + '>0', 'Mail could not be sent', 'WARNING',
     'Settings - Outgoing mail says why.', scope='notice')
trig('otp.mail[waiting]', ex('otp.mail[waiting]', 'min', '30m') + '>{$OTP.MAIL.WAITING.MAX}', 'Mail is piling up',
     'WARNING', scope='performance')
MULTI.append({'uuid': uid('trigger', 'crl-bad'), 'expression': '%s=1 and %s>0' % (
    ex('otp.signin.cert'), ex('otp.crl.bad')), 'name': TP + 'A CRL of the sign-in with a certificate cannot be had',
    'priority': 'HIGH', 'opdata': '{ITEM.LASTVALUE2} CRL(s)', 'description': 'Nobody signs in with a certificate '
    'of its authority until it can (Settings - Accounts, Revocation lists).', 'tags': tags(('scope', 'availability'))})
MULTI.append({'uuid': uid('trigger', 'ocsp-bad'), 'expression': '%s=1 and %s<>"off" and %s>0' % (
    ex('otp.signin.cert'), ex('otp.ocsp.mode'), ex('otp.ocsp.bad')),
    'name': TP + 'An OCSP answer is not good', 'priority': 'WARNING', 'opdata': '{ITEM.LASTVALUE3} answer(s)',
    'description': 'Revoked, unknown, no answer or run out (Settings - Accounts, Online status).',
    'tags': tags(('scope', 'notice'))})
trig('otp.clock.engaged', ex('otp.clock.engaged') + '=1', 'The clock guard holds codes back', 'HIGH',
     'The clock of this node is not to be trusted: codes are refused until it is (Settings - Time).')
trig('otp.clock.offset', 'abs(%s)>{$OTP.CLOCK.OFFSET.MAX}/1000' % ex('otp.clock.offset'),
     'The clock is off', 'WARNING', scope='notice')
for s, n in (('isemon', 'isemon'), ('siem', 'the SIEM')):
    MULTI.append({'uuid': uid('trigger', 'logs', s), 'expression': '%s=1 and %s=1' % (
        ex('otp.logs.on[%s]' % s), ex('otp.logs.trouble[%s]' % s)), 'name': TP + 'Logs to %s are in trouble' % n,
        'priority': 'WARNING', 'tags': tags(('scope', 'availability'))})
    trig('otp.logs.dropped[%s]' % s, ex('otp.logs.dropped[%s]' % s, 'min', '5m') + '>0',
         'Logs to %s are dropped' % n, 'WARNING', scope='capacity')

# -- discovery: walk[] of a table, SNMP_WALK_TO_JSON, its columns as dependent items
DISC = []


def disc(key, name, cols, macro_cols, protos, delay='5m', lifetime='DELETE_IMMEDIATELY', desc='', graphs=(),
         filt=None):
    """cols: [oid of a column]; macro_cols: [(macro, oid)]; protos: [(key, name, column oid, opts, [triggers])]"""
    walk_key = key + '.walk'
    used = list(cols)
    for _m, o in macro_cols:
        used.append(o)
    for p_ in protos:
        used.append(p_[2])
    cols = list(dict.fromkeys(used))
    item(walk_key, '%s: the table' % name, None, type='SNMP_AGENT', walk=cols, vt='TEXT', history='0',
         delay=delay, comp='raw', desc='The table walked; its rows are found by %s.' % name)
    rule = {'uuid': uid('disc', key), 'name': name, 'type': 'DEPENDENT', 'key': key + '.discovery', 'delay': '0',
            'description': desc or name,
            'master_item': {'key': walk_key}}
    if lifetime == 'DELETE_IMMEDIATELY':
        rule['lifetime_type'] = 'DELETE_IMMEDIATELY'
    if filt:
        rule['filter'] = filt
    params = ['{#SNMPVALUE}', cols[0], '0']
    for m, o in macro_cols:
        params += [m, o, '0']
    rule['preprocessing'] = [{'type': 'SNMP_WALK_TO_JSON', 'parameters': params, 'error_handler': 'DISCARD_VALUE'}]
    ips, tps = [], []
    for pkey, pname, col, o, trs in protos:
        it = {'uuid': uid('proto', pkey), 'name': pname, 'type': 'DEPENDENT', 'key': pkey, 'delay': '0'}
        if o.get('vt'):
            it['value_type'] = o['vt']
        if o.get('vt') in ('CHAR', 'TEXT'):
            it['trends'] = '0'
        if o.get('units'):
            it['units'] = o['units']
        it['description'] = 'OID: %s.{#SNMPINDEX} (OTP-MIB)' % col
        if o.get('valuemap'):
            it['valuemap'] = {'name': o['valuemap']}
        pre = [{'type': 'SNMP_WALK_VALUE', 'parameters': [col + '.{#SNMPINDEX}', '0']}]
        if o.get('rate'):
            pre.append({'type': 'CHANGE_PER_SECOND', 'parameters': ['']})
        if o.get('mult'):
            pre.append({'type': 'MULTIPLIER', 'parameters': [o['mult']]})
        it['preprocessing'] = pre
        it['master_item'] = {'key': walk_key}
        it['tags'] = tags(('component', o.get('comp', 'otp')))
        if trs:
            it['trigger_prototypes'] = trs
        ips.append(it)
    rule['item_prototypes'] = ips
    if graphs:
        rule['graph_prototypes'] = list(graphs)
    DISC.append(rule)


def ptrig(name, expr, prio, desc='', opdata='Current: {ITEM.LASTVALUE1}', scope='availability', deps=()):
    t = {'uuid': uid('ptrigger', name), 'expression': expr, 'name': TP + name, 'priority': prio}
    if opdata:
        t['opdata'] = opdata
    if desc:
        t['description'] = desc
    if deps:
        t['dependencies'] = [{'name': TP + n, 'expression': e} for n, e in deps]
    t['tags'] = tags(('scope', scope))
    return t


def pgraph(name, lines, **o):
    g = {'uuid': uid('pgraph', name), 'name': TP + name}
    g.update(o)
    g['graph_items'] = [dict({'color': c, 'item': {'host': T, 'key': k}}, **({'sortorder': str(i)} if i else {}),
                             **x) for i, (k, c, x) in enumerate(lines)]
    return g


A = B + '.5.3.1'
disc('otp.alert', 'Problems otp sees', [A + '.2'], [('{#KEY}', A + '.2'), ('{#LEVEL}', A + '.3'), ('{#TITLE}', A + '.4')], [
    ('otp.alert.level[{#KEY}]', 'Problem [{#KEY}]: level', A + '.3', {'vt': 'CHAR', 'comp': 'alerts'}, [
        ptrig('{#TITLE}', 'find(/%s/otp.alert.level[{#KEY}],,"like","bad")=1' % T, 'HIGH',
              'otp sees it (Settings - Alerts): {#KEY}.', opdata='', scope='notice'),
        ptrig('{#TITLE} (warning)', 'find(/%s/otp.alert.level[{#KEY}],,"like","warn")=1' % T, 'WARNING',
              'otp sees it (Settings - Alerts): {#KEY}.', opdata='', scope='notice')]),
    ('otp.alert.said[{#KEY}]', 'Problem [{#KEY}]: said', A + '.5', {'vt': 'TEXT', 'comp': 'alerts'}, [])],
    delay='1m', desc='Each thing otp sees wrong now - a problem of its own while it lasts, gone when it is right.')
C = B + '.6.1.1'
cw = ('Certificate [{#TARGET}] {#CN}: ends within {$OTP.CERT.EXPIRY.CRIT} days',
      'last(/%s/otp.cert.days[{#TARGET}])<{$OTP.CERT.EXPIRY.CRIT}' % T)
disc('otp.cert', 'Certificates of the pages', [C + '.2'], [('{#TARGET}', C + '.2'), ('{#CN}', C + '.3')], [
    ('otp.cert.days[{#TARGET}]', 'Certificate [{#TARGET}] {#CN}: days left', C + '.4', {'units': 'd', 'vt': 'FLOAT', 'comp': 'certificate'}, [
        ptrig(cw[0], cw[1], 'HIGH', scope='notice'),
        ptrig('Certificate [{#TARGET}] {#CN}: ends within {$OTP.CERT.EXPIRY.WARN} days',
              'last(/%s/otp.cert.days[{#TARGET}])<{$OTP.CERT.EXPIRY.WARN}' % T, 'WARNING', scope='notice', deps=[cw])]),
    ('otp.cert.end[{#TARGET}]', 'Certificate [{#TARGET}] {#CN}: ends', C + '.5', {'units': 'unixtime', 'comp': 'certificate'}, [])],
    delay='1h', lifetime='DELETE_AFTER')
N = B + '.7.1.1'
disc('otp.node', 'Nodes of the cluster', [N + '.2'], [('{#NODE}', N + '.2')], [
    ('otp.node.up[{#NODE}]', 'Node [{#NODE}]: heard from', N + '.3', {'valuemap': 'otp: up/down', 'comp': 'cluster'}, [
        ptrig('Node {#NODE} is not heard from', 'last(/%s/otp.node.up[{#NODE}])=0' % T, 'HIGH')]),
    ('otp.node.age[{#NODE}]', 'Node [{#NODE}]: since heard from', N + '.4', {'units': 's', 'comp': 'cluster'}, [
        ptrig('Node {#NODE}: no heartbeat for {$OTP.HA.HEARTBEAT.MAX} s',
              'min(/%s/otp.node.age[{#NODE}],3m)>{$OTP.HA.HEARTBEAT.MAX}' % T, 'AVERAGE')])],
    graphs=[pgraph('Node {#NODE}: since heard from', [('otp.node.age[{#NODE}]', '1A7C11', {'drawtype': 'GRADIENT_LINE'})])])
F = B + '.10.20.1'
fc = ('{#FSPATH}: the space is critically low', 'last(/%s/otp.fs.pused[{#FSPATH}])>{$OTP.FS.PUSED.CRIT}' % T)
disc('otp.fs', 'File systems', [F + '.2'], [('{#FSPATH}', F + '.2')], [
    ('otp.fs.total[{#FSPATH}]', '{#FSPATH}: total space', F + '.3', {'units': 'B', 'mult': '1024', 'comp': 'storage'}, []),
    ('otp.fs.used[{#FSPATH}]', '{#FSPATH}: used space', F + '.4', {'units': 'B', 'mult': '1024', 'comp': 'storage'}, []),
    ('otp.fs.free[{#FSPATH}]', '{#FSPATH}: free space', F + '.5', {'units': 'B', 'mult': '1024', 'comp': 'storage'}, []),
    ('otp.fs.pused[{#FSPATH}]', '{#FSPATH}: space used', F + '.6', {'units': '%', 'comp': 'storage'}, [
        ptrig(fc[0], fc[1], 'AVERAGE', scope='capacity'),
        ptrig('{#FSPATH}: the space is low', 'last(/%s/otp.fs.pused[{#FSPATH}])>{$OTP.FS.PUSED.WARN}' % T, 'WARNING',
              scope='capacity', deps=[fc])]),
    ('otp.fs.ipused[{#FSPATH}]', '{#FSPATH}: inodes used', F + '.7', {'units': '%', 'comp': 'storage'}, [
        ptrig('{#FSPATH}: the inodes run out', 'last(/%s/otp.fs.ipused[{#FSPATH}])>{$OTP.FS.INODES.WARN}' % T, 'WARNING',
              scope='capacity')])],
    delay='5m', lifetime='DELETE_AFTER',
    graphs=[pgraph('{#FSPATH}: space', [('otp.fs.used[{#FSPATH}]', 'F63100', {'drawtype': 'FILLED_REGION'}),
                                         ('otp.fs.total[{#FSPATH}]', '199C0D', {})], ymin_type_1='FIXED')])
D = B + '.11.1.1'
disc('otp.dir', 'Directories', [D + '.2'], [('{#DIRNAME}', D + '.2')], [
    ('otp.dir.enabled[{#DIRNAME}]', 'Directory [{#DIRNAME}]: used', D + '.3', {'valuemap': 'otp: yes/no', 'comp': 'directory'}, []),
    ('otp.dir.up[{#DIRNAME}]', 'Directory [{#DIRNAME}]: answers', D + '.4', {'valuemap': 'otp: up/down', 'comp': 'directory'}, [
        ptrig('Directory {#DIRNAME} cannot be reached', 'last(/%s/otp.dir.enabled[{#DIRNAME}])=1 and last(/%s/otp.dir.up[{#DIRNAME}])=0' % (T, T),
              'HIGH', 'None of its servers answers this node: sign-ins through it do not pass.')]),
    ('otp.dir.hosts[{#DIRNAME}]', 'Directory [{#DIRNAME}]: servers', D + '.5', {'vt': 'CHAR', 'comp': 'directory'}, [])],
    delay='1m', lifetime='DELETE_AFTER')
RI = B + '.12.10.1'
disc('otp.replin', 'Replication in', [RI + '.2'], [('{#REPL}', RI + '.2')], [
    ('otp.replin.running[{#REPL}]', 'Replication in [{#REPL}]: running', RI + '.3', {'valuemap': 'otp: running', 'comp': 'cluster'}, [
        ptrig('Replication {#REPL} is stopped', 'last(/%s/otp.replin.running[{#REPL}])=0' % T, 'HIGH',
              'This node does not take the other node\'s rows.')]),
    ('otp.replin.errors[{#REPL}]', 'Replication in [{#REPL}]: errors per second', RI + '.4', {'rate': True, 'vt': 'FLOAT', 'comp': 'cluster'}, [
        ptrig('Replication {#REPL} has errors', 'min(/%s/otp.replin.errors[{#REPL}],5m)>0' % T, 'WARNING')])],
    delay='1m', lifetime='DELETE_AFTER')
RO = B + '.12.11.1'
disc('otp.replout', 'Replication out', [RO + '.2'], [('{#REPL}', RO + '.2')], [
    ('otp.replout.behind[{#REPL}]', 'Replication out [{#REPL}]: behind', RO + '.3', {'units': 'B', 'comp': 'cluster'}, [
        ptrig('The other node is behind ({#REPL})', 'min(/%s/otp.replout.behind[{#REPL}],5m)>{$OTP.HA.BEHIND.WARN}' % T, 'WARNING',
              scope='performance')]),
    ('otp.replout.wal[{#REPL}]', 'Replication out [{#REPL}]: WAL', RO + '.4', {'vt': 'CHAR', 'comp': 'cluster'}, [
        ptrig('The other node lost its place ({#REPL})', 'find(/%s/otp.replout.wal[{#REPL}],,"like","lost")=1' % T, 'HIGH',
              'The other node cannot catch up from this one any more: Settings - Cluster.', opdata='')])],
    delay='1m', lifetime='DELETE_AFTER',
    graphs=[pgraph('Replication {#REPL}: behind', [('otp.replout.behind[{#REPL}]', 'FF8F00', {'drawtype': 'GRADIENT_LINE'})])])
RD = B + '.2.30.1'
disc('otp.radiusday', 'RADIUS results of the last day', [RD + '.2'], [('{#RESULT}', RD + '.2')], [
    ('otp.radiusday.count[{#RESULT}]', 'RADIUS last 24 hours: {#RESULT}', RD + '.3', {'comp': 'radius'}, [])],
    delay='5m', lifetime='DELETE_AFTER')


def mk_walk(key, name, o):
    it = mk_item(key, name, None, dict(o, type='SNMP_AGENT'))
    it['snmp_oid'] = 'walk[%s]' % ','.join(o['walk'])
    it['description'] = o.get('desc', '')
    it.pop('preprocessing', None)
    return it


items = []
for key, name, oid, o in ITEMS:
    it = mk_walk(key, name, o) if o.get('walk') else mk_item(key, name, oid, o)
    if key in TRIGGERS:
        it['triggers'] = TRIGGERS[key]
    items.append(it)
items.sort(key=lambda x: x['name'].lower())
for it in items:
    pass

GRAPHS = []


def graph(name, lines, **o):
    g = {'uuid': uid('graph', name), 'name': TP + name}
    g.update(o)
    g['graph_items'] = [dict({'color': c, 'item': {'host': T, 'key': k}}, **({'sortorder': str(i)} if i else {}), **x)
                        for i, (k, c, x) in enumerate(lines)]
    GRAPHS.append(g)


graph('RADIUS requests', [('otp.radius.rate[accept]', '1A7C11', {'drawtype': 'FILLED_REGION'}),
                          ('otp.radius.rate[reject]', 'F63100', {'drawtype': 'FILLED_REGION'}),
                          ('otp.radius.rate[challenge]', '2774A4', {'drawtype': 'FILLED_REGION'}),
                          ('otp.radius.rate[accounting]', 'A54F10', {}), ('otp.radius.rate[status]', 'FC6EA3', {})],
      type='STACKED')
graph('RADIUS trouble', [('otp.radius.rate[dropped]', 'F63100', {}), ('otp.radius.rate[malformed]', 'FF8F00', {}),
                         ('otp.radius.rate[unknown]', '6C59DC', {}), ('otp.radius.rate[repeated]', 'AC8C14', {}),
                         ('otp.radius.rate[no_database]', 'E53935', {}), ('otp.radius.rate[maintenance]', '611F27', {})])
graph('RADIUS queue', [('otp.radius.queued', '2774A4', {'drawtype': 'GRADIENT_LINE'})])
graph('CPU utilization', [('otp.host.cpu.util', '1A7C11', {'drawtype': 'GRADIENT_LINE'})], ymin_type_1='FIXED',
      ymax_type_1='FIXED')
graph('Load average', [('otp.host.load[1]', '1A7C11', {}), ('otp.host.load[5]', '2774A4', {}),
                       ('otp.host.load[15]', 'F63100', {})])
graph('Memory', [('otp.host.mem.used', 'F63100', {'drawtype': 'FILLED_REGION'}), ('otp.host.mem.total', '199C0D', {}),
                 ('otp.host.swap.used', 'FF8F00', {})])
graph('Disk I/O', [('otp.host.disk.read', '1A7C11', {'drawtype': 'GRADIENT_LINE'}),
                   ('otp.host.disk.write', 'F63100', {'drawtype': 'GRADIENT_LINE'})])
graph('Network traffic', [('otp.host.net.rx', '1A7C11', {'drawtype': 'GRADIENT_LINE'}),
                          ('otp.host.net.tx', '2774A4', {'drawtype': 'GRADIENT_LINE'})])
graph('Database latency', [('otp.db.latency', '6C59DC', {'drawtype': 'GRADIENT_LINE'})])
graph('Tokens', [('otp.tokens[active]', '1A7C11', {}), ('otp.tokens[pending]', 'FF8F00', {}),
                 ('otp.tokens[disabled]', '9E9E9E', {}), ('otp.tokens[used_30d]', '2774A4', {})])
graph('Problems otp sees', [('otp.alerts[bad]', 'E53935', {'drawtype': 'FILLED_REGION'}),
                            ('otp.alerts[warn]', 'FFB300', {'drawtype': 'FILLED_REGION'})], type='STACKED')
graph('Mail queue', [('otp.mail[waiting]', 'FF8F00', {}), ('otp.mail[sending]', '2774A4', {}),
                     ('otp.mail[failed]', 'E53935', {})])
graph('Clock', [('otp.clock.offset', '2774A4', {}), ('otp.clock.skew', 'FF8F00', {})])

# -- the dashboard: five pages, 72 columns wide
REFS = iter('%s%s%s%s%s' % (a, b, c, d, e) for a in 'ABCDEFGH' for b in 'ABCDEFGHIJ' for c in 'ABCDE' for d in 'AB' for e in 'A')


def ref():
    return {'type': 'STRING', 'name': 'reference', 'value': next(REFS)}


def w(typ, name, x, y, wd, h, fields, hide=False):
    o = {'type': typ, 'name': name}
    if x:
        o['x'] = str(x)
    if y:
        o['y'] = str(y)
    o.update({'width': str(wd), 'height': str(h)})
    if hide:
        o['hide_header'] = 'YES'
    o['fields'] = fields
    return o


def f(t, n, v):
    return {'type': t, 'name': n, 'value': v}


def fitem(key, n='itemid.0'):
    return f('ITEM', n, {'host': T, 'key': key})


def tile(name, key, x, y, color, wd=12, h=3, units_show=True, thresholds=(), size='40'):
    fl = [f('STRING', 'bg_color', color), f('STRING', 'description', name), f('STRING', 'desc_color', 'FFFFFF'),
          f('INTEGER', 'desc_size', '12'), f('INTEGER', 'desc_v_pos', '0'), fitem(key), f('INTEGER', 'show.0', '2'),
          f('INTEGER', 'show.1', '1'), f('STRING', 'value_color', 'FFFFFF'), f('INTEGER', 'value_size', size),
          f('INTEGER', 'decimal_places', '0')]
    for i, (thr, col) in enumerate(thresholds):
        fl += [f('STRING', 'thresholds.%d.color' % i, col), f('STRING', 'thresholds.%d.threshold' % i, thr)]
    if not units_show:
        fl.append(f('INTEGER', 'units_show', '0'))
    return w('item', name, x, y, wd, h, fl, hide=True)


def gauge(name, key, x, y, wd=18, h=5, warn='80', crit='90', units='%'):
    return w('gauge', name, x, y, wd, h, [
        f('INTEGER', 'decimal_places', '0'), f('STRING', 'description', name), f('INTEGER', 'desc_size', '9'),
        fitem(key), f('STRING', 'thresholds.0.color', '0EC9AC'), f('STRING', 'thresholds.0.threshold', '0'),
        f('STRING', 'thresholds.1.color', 'FFD54F'), f('STRING', 'thresholds.1.threshold', warn),
        f('STRING', 'thresholds.2.color', 'FF465C'), f('STRING', 'thresholds.2.threshold', crit),
        f('INTEGER', 'th_show_arc', '1'), f('INTEGER', 'th_show_labels', '1'), f('STRING', 'units', units),
        f('INTEGER', 'units_size', '15'), f('INTEGER', 'value_size', '20')])


def gr(name, x, y, wd=36, h=5):
    return w('graph', name, x, y, wd, h, [f('GRAPH', 'graphid.0', {'host': T, 'name': TP + name}), ref()])


def gproto(name, x, y, wd=72, h=5, cols='2'):
    return w('graphprototype', name, x, y, wd, h, [f('INTEGER', 'columns', cols),
                                                     f('GRAPH_PROTOTYPE', 'graphid.0', {'host': T, 'name': TP + name}), ref()])


def svg(name, x, y, sets, wd=36, h=5, stacked=False):
    fl = []
    for i, (pattern, color) in enumerate(sets):
        fl += [f('STRING', 'ds.%d.color' % i, color), f('STRING', 'ds.%d.items.0' % i, pattern),
               f('INTEGER', 'ds.%d.fill' % i, '4'), f('INTEGER', 'ds.%d.width' % i, '2')]
        if stacked:
            fl.append(f('INTEGER', 'ds.%d.stacked' % i, '1'))
    fl += [f('INTEGER', 'legend_lines', '2'), f('INTEGER', 'legend_statistic', '1'), ref(),
           f('STRING', 'lefty_min', '0')]
    return w('svggraph', name, x, y, wd, h, fl)


def honey(name, pattern, x, y, wd=36, h=4, thresholds=(('0', 'E53935'), ('1', '43A047')),
          label='{{ITEM.NAME}.regsub("\\[(.*?)\\]", "\\1")}'):
    fl = [f('STRING', 'items.0', pattern), f('STRING', 'primary_label', label),
          f('INTEGER', 'primary_label_size', '15'), f('INTEGER', 'primary_label_size_type', '1'), ref()]
    for i, (thr, col) in enumerate(thresholds):
        fl += [f('STRING', 'thresholds.%d.color' % i, col), f('STRING', 'thresholds.%d.threshold' % i, thr)]
    return w('honeycomb', name, x, y, wd, h, fl)


def problems(name, x, y, wd=72, h=5):
    return w('problems', name, x, y, wd, h, [f('INTEGER', 'show', '3'), f('INTEGER', 'show_opdata', '2'),
                                             f('INTEGER', 'show_tags', '1'), f('STRING', 'tag_priority', 'scope'),
                                             ref()])


def pie(name, x, y, keys, wd=24, h=6):
    fl = [f('INTEGER', 'decimal_places', '0'), f('INTEGER', 'draw_type', '1'), f('INTEGER', 'ds.0.dataset_type', '0'),
          f('STRING', 'ds.0.data_set_label', name)]
    cols = ['43A047', 'E53935', '1E88E5', 'FFB300', '8E24AA']
    for i, k in enumerate(keys):
        fl += [f('STRING', 'ds.0.color.%d' % i, cols[i % len(cols)]), fitem(k, 'ds.0.itemids.%d' % i),
               f('INTEGER', 'ds.0.type.%d' % i, '0')]
    fl += [f('INTEGER', 'legend_lines', '3'), f('INTEGER', 'legend_lines_mode', '1'), f('INTEGER', 'legend_value', '1'),
           f('INTEGER', 'space', '2'), f('INTEGER', 'stroke', '1'), f('INTEGER', 'total_show', '1'), ref()]
    return w('piechart', name, x, y, wd, h, fl)


GOOD, BAD, WARN, BLUE, GREY = '43A047', 'E53935', 'FFB300', '1E88E5', '546E7A'
pages = [
    {'name': 'Overview', 'widgets': [
        tile('RADIUS', 'otp.radius.listening', 0, 0, BLUE, thresholds=(('0', BAD), ('1', GOOD)), size='18'),
        tile('Database', 'otp.db.up', 12, 0, BLUE, thresholds=(('0', BAD), ('1', GOOD)), size='25'),
        tile('Problems', 'otp.alerts[bad]', 24, 0, GOOD, thresholds=(('0', GOOD), ('1', BAD))),
        tile('Warnings', 'otp.alerts[warn]', 36, 0, GOOD, thresholds=(('0', GOOD), ('1', WARN))),
        tile('Active tokens', 'otp.tokens[active]', 48, 0, BLUE),
        tile('Version', 'otp.version', 60, 0, GREY, size='20'),
        gauge('CPU', 'otp.host.cpu.util', 0, 3, 18, 5, '80', '90'),
        gauge('Memory', 'otp.host.mem.util', 18, 3, 18, 5, '80', '90'),
        svg('RADIUS requests per second', 36, 3, [('RADIUS Access-Accept*', GOOD), ('RADIUS Access-Reject*', BAD),
                                                  ('RADIUS Access-Challenge*', BLUE)], 36, 5),
        problems('Problems', 0, 8, 72, 6)]},
    {'name': 'RADIUS', 'widgets': [
        tile('Accepted (24 h)', 'otp.radius.day[accept]', 0, 0, GOOD),
        tile('Rejected (24 h)', 'otp.radius.day[reject]', 12, 0, BAD),
        tile('Challenged (24 h)', 'otp.radius.day[challenge]', 24, 0, BLUE),
        tile('Waiting', 'otp.radius.queued', 36, 0, BLUE, thresholds=(('0', GOOD), ('50', WARN), ('200', BAD))),
        tile('Clients', 'otp.radius.clients', 48, 0, GREY),
        tile('Realms', 'otp.radius.realms', 60, 0, GREY),
        gr('RADIUS requests', 0, 3, 48, 6),
        pie('The last 24 hours', 48, 3, ['otp.radius.day[accept]', 'otp.radius.day[reject]', 'otp.radius.day[challenge]'], 24, 6),
        gr('RADIUS trouble', 0, 9), gr('RADIUS queue', 36, 9),
        gr('Database latency', 0, 14), gr('Tokens', 36, 14)]},
    {'name': 'Machine', 'widgets': [
        gauge('CPU', 'otp.host.cpu.util', 0, 0, 18, 5, '80', '90'),
        gauge('Memory', 'otp.host.mem.util', 18, 0, 18, 5, '80', '90'),
        gr('CPU utilization', 36, 0),
        gr('Load average', 0, 5), gr('Memory', 36, 5),
        gr('Disk I/O', 0, 10), gr('Network traffic', 36, 10),
        honey('File systems: space used', '*: space used', 0, 15, 72, 4,
              thresholds=(('0', GOOD), ('85', WARN), ('95', BAD)), label='{{ITEM.NAME}.regsub("^(.*): space used", "\\1")}'),
        gproto('{#FSPATH}: space', 0, 19, 72, 5, '3')]},
    {'name': 'Cluster and directories', 'widgets': [
        tile('In a cluster', 'otp.ha.cluster', 0, 0, GREY, size='25'),
        tile('VIP address here', 'otp.ha.vip.here', 12, 0, BLUE, thresholds=(('0', GREY), ('1', GOOD)), size='14'),
        tile('VIP address', 'otp.ha.vip.address', 24, 0, GREY, wd=24, size='25'),
        tile('Directories', 'otp.radius.directories', 48, 0, GREY),
        tile('Clock offset', 'otp.clock.offset', 60, 0, BLUE, size='25'),
        honey('Nodes', 'Node *: heard from', 0, 3, 36, 4),
        honey('Directories', 'Directory *: answers', 36, 3, 36, 4),
        gproto('Node {#NODE}: since heard from', 0, 7, 36, 5, '1'),
        gproto('Replication {#REPL}: behind', 36, 7, 36, 5, '1'),
        gr('Clock', 0, 12, 72, 5)]},
    {'name': 'Certificates, sign-in, backups', 'widgets': [
        honey('Certificates: days left', 'Certificate *: days left', 0, 0, 72, 4,
              thresholds=(('0', BAD), ('7', WARN), ('21', GOOD))),
        tile('CRLs kept', 'otp.crl.count', 0, 4, GREY),
        tile('CRLs not had', 'otp.crl.bad', 12, 4, GOOD, thresholds=(('0', GOOD), ('1', BAD))),
        tile('OCSP', 'otp.ocsp.mode', 24, 4, GREY, size='25'),
        tile('OCSP not good', 'otp.ocsp.bad', 36, 4, GOOD, thresholds=(('0', GOOD), ('1', WARN))),
        tile('Nightly copy age', 'otp.backup.age', 48, 4, BLUE, size='22'),
        tile('Backup sent away', 'otp.rbackup.age', 60, 4, BLUE, size='22'),
        gr('Problems otp sees', 0, 7), gr('Mail queue', 36, 7)]},
]
dashboard = {'uuid': uid('dashboard', 'otp'), 'name': 'otp', 'display_period': '60', 'pages': pages}

tmpl = {'uuid': uid('template', T), 'template': T, 'name': T,
        'description': ('otp, the one-time password server (RADIUS): every node by its own SNMPv3 agent '
                        '(Settings - Monitoring - SNMP).\n\nThe host: an SNMP interface at the node\'s own address '
                        '(not the VIP address), SNMPv3, authPriv, the user and both passphrases of the page; '
                        'link this template. MIB: OTP-MIB (deploy/OTP-MIB.txt in the package).\n\n'
                        'Made by otp %s.' % VERSION),
        'vendor': {'name': 'otp', 'version': '7.0-%s' % VERSION.split('.')[-1]},
        'groups': [{'name': 'Templates/Applications'}],
        'items': items,
        'discovery_rules': DISC,
        'tags': tags(('class', 'software'), ('target', 'otp')),
        'macros': [{'macro': m, 'value': v, 'description': d} for m, v, d in MACROS],
        'dashboards': [dashboard],
        'valuemaps': [{'uuid': uid('valuemap', n), 'name': n, 'mappings': [{'value': a, 'newvalue': b} for a, b in m]}
                      for n, m in sorted(VALUEMAPS.items())]}
for it in tmpl['items']:
    pass
doc = {'zabbix_export': {'version': '7.0',
                         'template_groups': [{'uuid': uid('group', 'Templates/Applications'),
                                              'name': 'Templates/Applications'}],
                         'templates': [tmpl], 'triggers': MULTI, 'graphs': GRAPHS}}


class Q(yaml.SafeDumper):
    pass


def _str(d, v):
    if '\n' in v:
        return d.represent_scalar('tag:yaml.org,2002:str', v, style='|')
    return d.represent_scalar('tag:yaml.org,2002:str', v)


Q.add_representer(str, _str)
open(OUT, 'w').write(yaml.dump(doc, Dumper=Q, sort_keys=False, allow_unicode=True, width=120))
print('%s: %d items, %d discovery rules, %d triggers, %d graphs, %d pages' % (
    OUT, len(items), len(DISC), sum(len(v) for v in TRIGGERS.values()) + len(MULTI), len(GRAPHS), len(pages)))
