# 1.0.305: SELinux (hunt round 4) - two refusals of one event each get audit2why's word; a rule the same
# as one in otp_local already is not put in twice; a boolean, a folder, a port done once a batch.
#   python3 helper.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/deploy/otp_web.py'


def edit(pairs):
    s = open(F).read()
    for a, b in pairs:
        assert s.count(a) == 1, (s.count(a), a[:90])
        s = s.replace(a, b)
    open(F, 'w').write(s)


edit([
("""    by_avc = {}
    for gid, g in groups.items():
        m = re.search(r'msg=audit\\(([0-9.]+:\\d+)\\)', g['line'])
        if m:
            by_avc[m.group(1)] = gid
    if not by_avc:
        return {}
    got = _se_run(['audit2why'], 300, light=True,
                  data=''.join(groups[g]['line'] + '\\n' for g in by_avc.values()))""",
 """    # Each group's line, in the order sent (1.0.305): two refusals of one event (a folder searched,
    # its file read) share the event's id - the second wrote over the first, which got no word at
    # all (never "allowed now", never its boolean).
    by_avc = {}
    sent = []
    for gid, g in groups.items():
        m = re.search(r'msg=audit\\(([0-9.]+:\\d+)\\)', g['line'])
        if m:
            by_avc.setdefault(m.group(1), []).append(gid)
            sent.append(gid)
    if not sent:
        return {}
    got = _se_run(['audit2why'], 300, light=True,
                  data=''.join(groups[g]['line'] + '\\n' for g in sent))"""),
("""        if m and 'avc:' in line:
            cur = by_avc.get(m.group(1))
            if cur:""",
 """        if m and 'avc:' in line:
            left = by_avc.get(m.group(1)) or []
            cur = left.pop(0) if left else None
            if cur:"""),
("""    rules = se_local_rules()
    new_rules = False
    now = time.time()
    for i in ids:""",
 """    rules = se_local_rules()
    new_rules = False
    now = time.time()
    done = {}                   # what this batch did already: a boolean, a folder, a port (1.0.305)
    for i in ids:"""),
("""        if f['kind'] == 'boolean':
            got = _se_run(['setsebool', '-P', fx['boolean'], '1'], 300)""",
 """        key = (f['kind'], fx.get('boolean') or fx.get('restorecon') or
               ('%s/%s' % (fx.get('port'), fx.get('proto')) if f['kind'] == 'port' else fx.get('rule')))
        if key in done:
            # Done a moment ago in this batch for another refusal: once is enough (each setsebool -P
            # builds the whole policy again - a batch of many took longer than the pages wait).
            if done[key]:
                fixed[i] = {'at': now, 'by': by, 'how': how, 'kind': f['kind']}
                if f['kind'] == 'rule':
                    said.append('rule %s: the same as one put in just now' % i)
            continue
        done[key] = False
        if f['kind'] == 'boolean':
            got = _se_run(['setsebool', '-P', fx['boolean'], '1'], 300)"""),
("""            if not any(x['id'] == i for x in rules):
                rules.append({'id': i, 'rule': fx['rule'], 'at': now, 'by': by,""",
 """            same = next((x for x in rules if x['rule'] == fx['rule'] and x['id'] != i), None)
            if same is not None:
                # The same rule in otp_local already (1.0.305), for another refusal: not put in twice -
                # taking one away would have left the other allowing it.
                said.append('rule %s: the same as %s, in otp_local already' % (i, same['id']))
                done[key] = True
                fixed[i] = {'at': now, 'by': by, 'how': how, 'kind': f['kind']}
                continue
            if not any(x['id'] == i for x in rules):
                rules.append({'id': i, 'rule': fx['rule'], 'at': now, 'by': by,"""),
("""            said.append('rule %s: %s' % (i, fx['rule']))
        fixed[i] = {'at': now, 'by': by, 'how': how, 'kind': f['kind']}""",
 """            said.append('rule %s: %s' % (i, fx['rule']))
        done[key] = True
        fixed[i] = {'at': now, 'by': by, 'how': how, 'kind': f['kind']}"""),
])
print('ok')
