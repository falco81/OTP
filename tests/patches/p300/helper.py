# 1.0.300: the root helper's SELinux - what is refused, sorted by what puts it right; put right by
# id; otp's own local module.   python3 helper.py OUTDIR
import os, sys
F = sys.argv[1].rstrip('/') + '/deploy/otp_web.py'
HERE = os.path.dirname(os.path.abspath(__file__))


def edit(pairs):
    s = open(F).read()
    for a, b in pairs:
        assert s.count(a) == 1, (s.count(a), a[:90])
        s = s.replace(a, b)
    open(F, 'w').write(s)


FIND = open(HERE + '/se_find.txt').read()
edit([
("""def se_want_checked(r, left_out=None):""", FIND + """def se_want_checked(r, left_out=None):"""),
("""    if on:
        out['denials'] = se_denials(se_applied_at())""",
 """    if on:
        # What was refused, sorted by what puts it right (1.0.300); the count before enforcing as
        # until now - otp's and the services' otp works with - less what was put right here since.
        since = se_applied_at()
        found, tool = se_findings(r, since)
        live = [f for f in found if f['kind'] not in ('allowed', 'fixed')]
        counted = [f for f in live if f['kind'] != 'other' or f['whose'] == 'near']
        groups = {}
        for f in counted:
            key = (f['source'], f['target'], f['class'], ' '.join(f['perms']))
            g = groups.setdefault(key, {'source': f['source'], 'target': f['target'], 'class': f['class'],
                                        'perms': ' '.join(f['perms']), 'count': 0, 'what': '',
                                        'permissive': False})
            g['count'] += f['count']
            g['what'] = ' '.join(x for x in (f['program'], f.get('name') or os.path.basename(f['path'] or '')
                                             or f['port']) if x)[:120] or g['what']
            g['permissive'] = g['permissive'] or f['permissive']
        out['denials'] = {'tool': tool, 'since': since,
                          'total': sum(f['count'] for f in counted),
                          'settled': sum(f['count'] for f in found if f['kind'] == 'allowed'),
                          'groups': sorted(groups.values(), key=lambda g: -g['count'])[:30]}
        out['findings'] = [f for f in found if f['kind'] != 'allowed']
        out['counts'] = {k: sum(1 for f in found if f['kind'] == k) for k in SE_KIND_ORDER}
        out['local_rules'] = [{k: x.get(k) for k in ('id', 'rule', 'why', 'at', 'by', 'program')}
                              for x in se_local_rules()]
        out['local_module'] = se_local_in() if out['local_rules'] else None"""),
("""    mode = se_mode()
    if mode == 'absent':
        raise Refused('there is no SELinux on this machine')
    if do == 'prepare':""",
 """    mode = se_mode()
    if mode == 'absent':
        raise Refused('there is no SELinux on this machine')
    if do in ('fix', 'rule_drop'):
        # Put right by id, or a rule of otp's own taken away (1.0.300) - under enforcing too.
        if mode == 'Disabled':
            raise Refused('SELinux is disabled - nothing is refused')
        if do == 'fix':
            se_fix(r, said)
        else:
            se_rule_drop(r, said)
        out = se_check(r)
        out['said'] = said
        return out
    if do == 'prepare':"""),
("""    lines.append('ready for enforcing' if c.get('ready') else""",
 """    # What was refused, sorted (1.0.300): each with its id and what puts it right.
    names = {'fixed': 'put right', 'boolean': 'a boolean', 'label': 'a label', 'port': 'a port',
             'rule': 'a rule of otp\\'s', 'nobutton': 'not for a button', 'other': 'not otp\\'s'}
    for f in (c.get('findings') or [])[:40]:
        lines.append('    %s %-16s %4dx %s %s -> %s %s { %s }%s' % (
            f['id'], names.get(f['kind'], f['kind']), f['count'], f.get('program') or '?', f['source'],
            f['target'], f['class'], ' '.join(f['perms']),
            (' ' + (f['path'] or ('port ' + f['port'] if f.get('port') else ''))) if (f.get('path') or f.get('port')) else ''))
        if f.get('fix'):
            lines.append('                 -> %s' % f['fix']['cmd'])
        elif f.get('why'):
            lines.append('                 %s' % f['why'])
    for x in c.get('local_rules') or []:
        lines.append('  otp_local %s: %s' % (x['id'], x['rule']))
    lines.append('ready for enforcing' if c.get('ready') else"""),
("""    parts['README.txt'] = (""",
 """    # The whole machine's side too (1.0.300): every process with its domain, every boolean,
    # port type and module, what was changed on this machine - whoever writes the module sees
    # what the policy is here, not only otp's part of it.
    parts['os/processes.txt'] = '\\n'.join(x[:200] for x in ps.splitlines()) + '\\n'
    parts['os/booleans.txt'] = bools
    parts['os/ports.txt'] = ports
    parts['os/modules.txt'] = _se_out(['semodule', '-lfull'], 300)
    parts['os/local-changes.txt'] = '\\n'.join(
        '==== semanage %s -l -C\\n%s' % (w, _se_out(['semanage', w, '-l', '-C'], 120))
        for w in ('boolean', 'port', 'fcontext', 'login', 'user', 'module', 'permissive'))
    parts['os/semanage-export.txt'] = _se_out(['semanage', 'export'], 300)
    parts['os/listening.txt'] = _se_out(['ss', '-lntupZ'], 60, light=False)
    parts['findings.json'] = json.dumps({'findings': check.get('findings') or [],
                                         'local_rules': check.get('local_rules') or []},
                                        indent=1, sort_keys=True)
    parts['modules.txt'] += '\\n==== %s (the local rules of otp)\\n%s\\n' % (
        SE_LOCAL_CIL, _read_or(SE_LOCAL_CIL) or '(none)')
    parts['README.txt'] = ("""),
("""        'system.txt      the system, the policy and the packages; otp.json: what otp uses here\\n\\n'""",
 """        'system.txt      the system, the policy and the packages; otp.json: what otp uses here\\n'
        'findings.json   what was refused, sorted by what puts it right; the local rules of otp\\n'
        'os/             the whole machine: every process, boolean, port type, module, the local\\n'
        '                changes (semanage -l -C, semanage export), every listening socket\\n\\n'"""),
])
print('ok')
