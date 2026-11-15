# 1.0.281: OTP-MIB.txt - the objects added to the agent (otp_mib_more): python3 mib.py OUTDIR
import re, sys
O = sys.argv[1].rstrip('/') + '/'
F = O + 'deploy/OTP-MIB.txt'
s = open(F).read()


def scalar(name, syntax, parent, n, desc, units=''):
    u = ' UNITS "%s"' % units if units else ''
    return ('%s OBJECT-TYPE\n    SYNTAX %s%s MAX-ACCESS read-only STATUS current\n'
            '    DESCRIPTION "%s" ::= { %s %d }\n' % (name, syntax, u, desc, parent, n))


def table(tname, ename, etype, parent, n, tdesc, edesc, cols):
    """cols: [(name, syntax, desc, units)] - the first is the index."""
    out = ('%s OBJECT-TYPE\n    SYNTAX SEQUENCE OF %s MAX-ACCESS not-accessible STATUS current\n'
           '    DESCRIPTION "%s" ::= { %s %d }\n' % (tname, etype, tdesc, parent, n))
    out += ('%s OBJECT-TYPE\n    SYNTAX %s MAX-ACCESS not-accessible STATUS current\n'
            '    DESCRIPTION "%s" INDEX { %s } ::= { %s 1 }\n' % (ename, etype, edesc, cols[0][0], tname))
    seq = []
    for c in cols:
        base = c[1].split(' (')[0].split(' UNITS')[0]
        seq.append('%s %s' % (c[0], base))
    out += '%s ::= SEQUENCE { %s }\n' % (etype, ', '.join(seq))
    for i, c in enumerate(cols, 1):
        out += scalar(c[0], c[1], ename, i, c[2], c[3] if len(c) > 3 else '')
    return out


idx = ('Integer32 (1..65535)', 'Its number now.')
add = '''
otpHost          OBJECT IDENTIFIER ::= { otp 10 }
otpDirectories   OBJECT IDENTIFIER ::= { otp 11 }
otpHa            OBJECT IDENTIFIER ::= { otp 12 }
otpBackups       OBJECT IDENTIFIER ::= { otp 13 }
otpMail          OBJECT IDENTIFIER ::= { otp 14 }
otpSignIn        OBJECT IDENTIFIER ::= { otp 15 }
otpClock         OBJECT IDENTIFIER ::= { otp 16 }
otpLogs          OBJECT IDENTIFIER ::= { otp 17 }
otpLogsIsemon    OBJECT IDENTIFIER ::= { otpLogs 1 }
otpLogsSiem      OBJECT IDENTIFIER ::= { otpLogs 2 }
'''
s = s.replace('otpMetrics       OBJECT IDENTIFIER ::= { otp 9 }\n',
              'otpMetrics       OBJECT IDENTIFIER ::= { otp 9 }' + add, 1)
s = s.replace('''    REVISION     "202610300000Z"
    DESCRIPTION  "First: 1.0.182."''', '''    REVISION     "202611150000Z"
    DESCRIPTION  "1.0.281: the machine, the directories, the VIP address and the replication,
                  the backups, the mail, the ways of signing in, the clock, the logs sent."
    REVISION     "202610300000Z"
    DESCRIPTION  "First: 1.0.182."''', 1)
s = s.replace('    LAST-UPDATED "202610300000Z"', '    LAST-UPDATED "202611150000Z"', 1)

m = '\n-- otpRadius, more (1.0.281)\n\n'
m += scalar('otpRadiusClients', 'Gauge32', 'otpRadius', 15, 'RADIUS clients set.')
m += scalar('otpRadiusRealms', 'Gauge32', 'otpRadius', 16, 'Realms set.')
m += scalar('otpRadiusDirectories', 'Gauge32', 'otpRadius', 17, 'Directories (Active Directory) set.')
m += scalar('otpRadiusDayAccepts', 'Gauge32', 'otpRadius', 18, 'Access-Requests accepted in the last 24 hours (both nodes).')
m += scalar('otpRadiusDayRejects', 'Gauge32', 'otpRadius', 19, 'Access-Requests rejected in the last 24 hours (both nodes).')
m += scalar('otpRadiusDayChallenges', 'Gauge32', 'otpRadius', 20, 'Access-Requests challenged in the last 24 hours (both nodes).')
m += table('otpRadiusDayTable', 'otpRadiusDayEntry', 'OtpRadiusDayEntry', 'otpRadius', 30,
           'The Access-Requests of the last 24 hours, by result.', 'One result.',
           [('otpRadiusDayIndex',) + idx, ('otpRadiusDayResult', 'DisplayString', 'The result, as the log has it.'),
            ('otpRadiusDayCount', 'Gauge32', 'How many.')])
m += '\n-- otpHost: this node\'s machine (1.0.281)\n\n'
for i, (n, syn, d, u) in enumerate([
        ('otpHostCpuIdle', 'Counter64', 'CPU time idle (and waiting for the disks), all cores, since boot.', 'jiffies'),
        ('otpHostCpuTotal', 'Counter64', 'CPU time in all, all cores, since boot.', 'jiffies'),
        ('otpHostCpuCores', 'Integer32', 'CPU cores.', ''),
        ('otpHostLoad1', 'Gauge32', 'The load average of a minute, times 100.', ''),
        ('otpHostLoad5', 'Gauge32', 'The load average of 5 minutes, times 100.', ''),
        ('otpHostLoad15', 'Gauge32', 'The load average of 15 minutes, times 100.', ''),
        ('otpHostMemTotal', 'Gauge32', 'Memory in all.', 'KiB'),
        ('otpHostMemUsed', 'Gauge32', 'Memory used (all but what is available).', 'KiB'),
        ('otpHostSwapUsed', 'Gauge32', 'Swap used.', 'KiB'),
        ('otpHostDiskRead', 'Counter64', 'Bytes read from the disks since boot.', 'bytes'),
        ('otpHostDiskWritten', 'Counter64', 'Bytes written to the disks since boot.', 'bytes'),
        ('otpHostNetRx', 'Counter64', 'Bytes received by the network cards since boot.', 'bytes'),
        ('otpHostNetTx', 'Counter64', 'Bytes sent by the network cards since boot.', 'bytes'),
        ('otpHostUptime', 'Gauge32', 'Since the machine started.', 'seconds')], 1):
    m += scalar(n, syn, 'otpHost', i, d, u)
m += table('otpFsTable', 'otpFsEntry', 'OtpFsEntry', 'otpHost', 20,
           'The file systems otp lives on, each once.', 'One file system.',
           [('otpFsIndex',) + idx, ('otpFsPath', 'DisplayString', 'A path on it.'),
            ('otpFsTotal', 'Gauge32', 'Its size.', 'KiB'), ('otpFsUsed', 'Gauge32', 'Used.', 'KiB'),
            ('otpFsFree', 'Gauge32', 'Free for otp.', 'KiB'), ('otpFsUsedPct', 'Gauge32', 'How full.', 'percent'),
            ('otpFsInodesPct', 'Gauge32', 'How many of its inodes are used.', 'percent')])
m += '\n-- otpDirectories (1.0.281)\n\n'
m += table('otpDirTable', 'otpDirEntry', 'OtpDirEntry', 'otpDirectories', 1,
           'Each directory (Active Directory) and whether a server of it answers this node.', 'One directory.',
           [('otpDirIndex',) + idx, ('otpDirName', 'DisplayString', 'Its name.'),
            ('otpDirEnabled', 'Integer32 (0..1)', '1 when it is used.'),
            ('otpDirUp', 'Integer32 (0..1)', '1 when a server of it answers this node.'),
            ('otpDirHosts', 'DisplayString', 'Its servers.')])
m += '\n-- otpHa: the VIP address and the replication (1.0.281)\n\n'
m += scalar('otpHaCluster', 'Integer32 (0..1)', 'otpHa', 1, '1 when this node is one of a cluster.')
m += scalar('otpHaVipOn', 'Integer32 (0..1)', 'otpHa', 2, '1 when the cluster has a VIP address.')
m += scalar('otpHaVipHere', 'Integer32 (0..1)', 'otpHa', 3, '1 while this node holds the VIP address.')
m += scalar('otpHaVipAddress', 'DisplayString', 'otpHa', 4, 'The VIP address.')
m += table('otpReplInTable', 'otpReplInEntry', 'OtpReplInEntry', 'otpHa', 10,
           'This node taking the other node\'s rows (each subscription).', 'One subscription.',
           [('otpReplInIndex',) + idx, ('otpReplInName', 'DisplayString', 'Its name.'),
            ('otpReplInRunning', 'Integer32 (0..1)', '1 while it runs.'),
            ('otpReplInErrors', 'Counter32', 'Its errors (applying and syncing).')])
m += table('otpReplOutTable', 'otpReplOutEntry', 'OtpReplOutEntry', 'otpHa', 11,
           'The other node taking this node\'s rows (each slot).', 'One slot.',
           [('otpReplOutIndex',) + idx, ('otpReplOutName', 'DisplayString', 'Its name.'),
            ('otpReplOutBehind', 'Gauge32', 'How far behind the other node is.', 'bytes'),
            ('otpReplOutWal', 'DisplayString', 'reserved, extended, unreserved or lost.')])
m += '\n-- otpBackups (1.0.281)\n\n'
for i, (n, syn, d, u) in enumerate([
        ('otpBackupNightly', 'Integer32 (0..1)', '1 when this node makes a copy of the database every night.', ''),
        ('otpBackupLast', 'Integer32', 'When the newest copy kept on this node was made, unix time (0: none).', ''),
        ('otpBackupLastAge', 'Gauge32', 'Since then (4294967295: none).', 'seconds'),
        ('otpRemoteBackupOn', 'Integer32 (0..1)', '1 when backups are sent away.', ''),
        ('otpRemoteBackupLastOk', 'Integer32 (0..1)', '1 when the newest backup this node sent went everywhere.', ''),
        ('otpRemoteBackupLastGood', 'Integer32', 'When the newest good one went, unix time (0: none).', ''),
        ('otpRemoteBackupLastGoodAge', 'Gauge32', 'Since then (4294967295: none).', 'seconds')], 1):
    m += scalar(n, syn, 'otpBackups', i, d, u)
m += '\n-- otpMail (1.0.281)\n\n'
for i, st in enumerate(('sending', 'waiting', 'sent', 'failed', 'expired'), 1):
    m += scalar('otpMail' + st.capitalize(), 'Gauge32', 'otpMail', i, 'Mail %s (the queue of both nodes).' % st)
m += '\n-- otpSignIn: the administration (1.0.281)\n\n'
for i, (n, syn, d) in enumerate([
        ('otpSignInKerberos', 'Integer32 (0..1)', '1 when signing in with Windows (Kerberos) is on.'),
        ('otpSignInCert', 'Integer32 (0..1)', '1 when signing in with a certificate is on.'),
        ('otpSignInPasswordOff', 'Integer32 (0..1)', '1 when no password at all is offered.'),
        ('otpSignInSecondStep', 'Integer32 (0..1)', '1 when the administrators\' second step is on.'),
        ('otpCrlCount', 'Gauge32', 'CRLs kept on this node.'),
        ('otpCrlBad', 'Gauge32', 'Of them not had or run out.'),
        ('otpOcspMode', 'DisplayString', 'off, first, only or both.'),
        ('otpOcspCount', 'Gauge32', 'OCSP answers kept on this node.'),
        ('otpOcspBad', 'Gauge32', 'Of them not good: revoked, unknown, no answer or run out.')], 1):
    m += scalar(n, syn, 'otpSignIn', i, d)
m += '\n-- otpClock: the clock guard (1.0.281)\n\n'
for i, (n, syn, d, u) in enumerate([
        ('otpClockEngaged', 'Integer32 (0..1)', '1 while the clock guard holds codes back.', ''),
        ('otpClockMode', 'DisplayString', 'How the clock guard is set.', ''),
        ('otpClockOffset', 'Integer32', 'This node against the time servers.', 'milliseconds'),
        ('otpClockSkew', 'Integer32', 'This node against the other node or the directory.', 'milliseconds'),
        ('otpClockCorrection', 'Integer32', 'What the codes are corrected by.', 'milliseconds')], 1):
    m += scalar(n, syn, 'otpClock', i, d, u)
m += '\n-- otpLogs: the logs sent away (1.0.281)\n\n'
for parent, what in (('otpLogsIsemon', 'Isemon'), ('otpLogsSiem', 'Siem')):
    for i, (n, syn, d) in enumerate([
            ('On', 'Integer32 (0..1)', '1 when they are sent.'),
            ('Trouble', 'Integer32 (0..1)', '1 when a target is in trouble now.'),
            ('Sent', 'Counter64', 'Lines sent since the daemon started.'),
            ('Dropped', 'Counter64', 'Lines dropped, the queue full.')], 1):
        m += scalar('otpLogs%s%s' % (what, n), syn, parent, i, d)
m += '\n'
anchor = '-- what the traps carry -----------------------------------------------------------\n'
s = s.replace('-- otpMetrics: every Prometheus sample ---------------------------------------------\n',
              '-- otpMetrics: every Prometheus sample\n', 1)
assert s.count(anchor) == 1
s = s.replace(anchor, m.lstrip('\n') + '\n-- what the traps carry\n', 1)
# Conformance (1.0.281): every object in a group, as SMIv2 wants - MIB browsers and Zabbix's
# import take it without a warning.
names = re.findall(r'(?m)^(otp\w+) OBJECT-TYPE\n    SYNTAX (?!SEQUENCE)[^\n]*MAX-ACCESS (read-only)', s)
notif = re.findall(r'(?m)^(otp\w+) OBJECT-TYPE\n    SYNTAX [^\n]*MAX-ACCESS accessible-for-notify', s)
traps = re.findall(r'(?m)^(otp\w+) NOTIFICATION-TYPE', s)
conf = '''
-- conformance (1.0.281)

otpConformance   OBJECT IDENTIFIER ::= { otp 99 }
otpGroups        OBJECT IDENTIFIER ::= { otpConformance 1 }
otpCompliances   OBJECT IDENTIFIER ::= { otpConformance 2 }

otpObjectsGroup OBJECT-GROUP
    OBJECTS { %s }
    STATUS current
    DESCRIPTION "Every object otp answers."
    ::= { otpGroups 1 }
otpTrapObjectsGroup OBJECT-GROUP
    OBJECTS { %s }
    STATUS current
    DESCRIPTION "What the traps carry."
    ::= { otpGroups 2 }
otpNotificationsGroup NOTIFICATION-GROUP
    NOTIFICATIONS { %s }
    STATUS current
    DESCRIPTION "The traps otp sends."
    ::= { otpGroups 3 }
otpCompliance MODULE-COMPLIANCE
    STATUS current
    DESCRIPTION "An otp node."
    MODULE MANDATORY-GROUPS { otpObjectsGroup, otpTrapObjectsGroup, otpNotificationsGroup }
    ::= { otpCompliances 1 }

''' % (',\n              '.join(n for n, _ in names), ', '.join(notif), ', '.join(traps))
assert s.rstrip().endswith('END')
s = s.rstrip()[:-3].rstrip() + '\n' + conf + 'END\n'
s = s.replace('''    DisplayString
        FROM SNMPv2-TC''', '''    DisplayString
        FROM SNMPv2-TC
    OBJECT-GROUP, NOTIFICATION-GROUP, MODULE-COMPLIANCE
        FROM SNMPv2-CONF''', 1)
s = s.replace('''    Integer32, Gauge32, Counter64, TimeTicks
        FROM SNMPv2-SMI''', '''    Integer32, Gauge32, Counter32, Counter64, TimeTicks
        FROM SNMPv2-SMI''', 1)
open(F, 'w').write(s)
print('MIB written')
