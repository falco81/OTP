# 1.0.300: SELinux - what is refused put right by id on the card, otp's own local rules taken away;
# asked of the node it is on (each node's own root helper, as every step).   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('87e_selinux.py', [
("""SE_ACTIONS = ('check', 'prepare', 'enforce', 'permissive', 'report')""",
 """SE_ACTIONS = ('check', 'prepare', 'enforce', 'permissive', 'report', 'fix', 'rule_drop')
SE_STEPS = ('prepare', 'enforce', 'permissive', 'fix', 'rule_drop')     # a step: done once, said in Events"""),
("""def selinux_ask(store, node, action, by):
    known = [node_name()] + [n['name'] for n in ha_nodes(store)]
    if node not in known:
        raise ValueError('there is no node %s' % node)
    if action not in SE_ACTIONS:
        raise ValueError('check, prepare, enforce or permissive')""",
 """def selinux_ask(store, node, action, by, ids=None, rule=None):
    known = [node_name()] + [n['name'] for n in ha_nodes(store)]
    if node not in known:
        raise ValueError('there is no node %s' % node)
    if action not in SE_ACTIONS:
        raise ValueError('check, prepare, enforce or permissive')
    # Put right by id, a rule taken away (1.0.300): only ids travel - that node's root helper finds
    # each in its own audit log again and works out what to do itself.
    if action == 'fix':
        if not isinstance(ids, list) or not ids or len(ids) > 300 or \\
                not all(isinstance(x, str) and re.match(r'^[0-9a-f]{12}\\Z', x) for x in ids):
            raise ValueError('what to put right: the findings\\' ids')
        ids = sorted(set(ids))
    if action == 'rule_drop' and not (isinstance(rule, str) and re.match(r'^[0-9a-f]{12}\\Z', rule)):
        raise ValueError('which rule: its id')"""),
("""    if action in ('check', 'report') and was.get('do') in ('prepare', 'enforce', 'permissive') and \\""",
 """    if action in ('check', 'report') and was.get('do') in SE_STEPS and \\"""),
("""    store.set_meta('host:selinux:want:' + node, json.dumps({
        'id': secrets.token_hex(6), 'do': action, 'by': by, 'at': time.time()}))
    if action == 'report':""",
 """    if action in ('fix', 'rule_drop') and was.get('do') in SE_STEPS and was.get('id') != now.get('done') and \\
            time.time() - fnum(was.get('at')) < 600:
        raise ValueError('%s has not done the step asked of it yet (%s) - wait for it' % (node, was.get('do')))
    row = {'id': secrets.token_hex(6), 'do': action, 'by': by, 'at': time.time()}
    if action == 'fix':
        row['ids'] = ids
    if action == 'rule_drop':
        row['rule'] = rule
    store.set_meta('host:selinux:want:' + node, json.dumps(row))
    if action == 'fix':
        store.add_event('settings', '%s asked SELinux on %s: put right %d thing(s) refused (%s)' % (
            by, node, len(ids), ', '.join(ids[:8]) + (' ...' if len(ids) > 8 else '')), 'warn', who=by)
    elif action == 'rule_drop':
        store.add_event('settings', '%s asked SELinux on %s: take away otp\\'s local rule %s' % (by, node, rule),
                        'warn', who=by)
    elif action == 'report':"""),
("""    if asked and want.get('do') in ('prepare', 'enforce', 'permissive') and \\
            time.time() - fnum(want.get('at')) > SE_STEP_STALE_S:""",
 """    if asked and want.get('do') in SE_STEPS and \\
            time.time() - fnum(want.get('at')) > SE_STEP_STALE_S:"""),
("""                data = root_ask('selinux.ask', 'selinux.json',
                                dict(selinux_want(store), do=do), 120 if do == 'check' else 600)""",
 """                ask = dict(selinux_want(store), do=do)
                if do == 'fix':
                    ask.update(ids=want.get('ids') or [], by=str(want.get('by') or '')[:100])
                elif do == 'rule_drop':
                    ask.update(rule=str(want.get('rule') or ''), by=str(want.get('by') or '')[:100])
                data = root_ask('selinux.ask', 'selinux.json', ask, 120 if do == 'check' else 600)"""),
("""    out = list(d.get('problems') or [])
    if d.get('mode') == 'Permissive' and not out:""",
 """    out = list(d.get('problems') or [])
    # How many of them the card puts right (1.0.300).
    n = sum(int(v or 0) for k, v in odict(d.get('counts')).items() if k in ('boolean', 'label', 'port', 'rule'))
    if n and out:
        out.append('%d of what SELinux refused can be put right on the card (Settings → High security → '
                   'SELinux, "Put in what is selected")' % n)
    if d.get('mode') == 'Permissive' and not out:"""),
])

edit('90n_net_api.py', [
("""        selinux_ask(h.store, node, action, s['name'])
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'message': {'check': 'asked: %s looks within seconds',""",
 """        selinux_ask(h.store, node, action, s['name'], ids=b.get('ids'), rule=b.get('rule'))
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'message': {'check': 'asked: %s looks within seconds',
                        'fix': 'asked: %s puts right what was selected within seconds',
                        'rule_drop': 'asked: %s takes the rule away within seconds',"""),
])

edit('95_cli.py', [
("""    g.add_argument('--selinux-report', nargs='?', const='', metavar='FILE',""",
 """    g.add_argument('--selinux-fix', nargs='+', metavar='ID',
                   help='put right what SELinux refused, by the ids --selinux-check lists (or "all" '
                        'that may be): a boolean, a label, a port, a rule of otp\\'s own local module '
                        '(otp_local) - listed and asked first unless --yes (as root)')
    g.add_argument('--selinux-rules', action='store_true',
                   help='the rules of otp\\'s own local SELinux module (otp_local) (as root)')
    g.add_argument('--selinux-take-away', metavar='ID',
                   help='take one rule of otp\\'s local SELinux module away (as root)')
    g.add_argument('--selinux-report', nargs='?', const='', metavar='FILE',"""),
("""    if args.selinux_check or args.selinux or args.selinux_report is not None:
        return cli_selinux(args, pal)""",
 """    if args.selinux_check or args.selinux or args.selinux_report is not None or args.selinux_fix or \\
            args.selinux_rules or args.selinux_take_away:
        return cli_selinux(args, pal)"""),
("""    step = args.selinux or 'check'
    if step == 'check':""",
 """    if args.selinux_fix or args.selinux_rules or args.selinux_take_away:
        return cli_selinux_fix(args, pal, want)
    step = args.selinux or 'check'
    if step == 'check':"""),
("""CLI_STARTED_ROOT = os.geteuid() == 0""",
 """def cli_selinux_fix(args, pal, want):
    \"\"\"otp --selinux-fix ID...|all, --selinux-rules, --selinux-take-away ID (1.0.300): as on the card.\"\"\"
    got = _selinux_helper(['--selinux-check', '--want-stdin', '--json'], want, 600)
    try:
        c = json.loads(got.stdout or '{}')
    except ValueError:
        sys.stderr.write(got.stderr)
        raise SystemExit('otp: the root helper did not say how SELinux is here')
    rules = c.get('local_rules') or []
    if args.selinux_rules:
        if args.json:
            print(json.dumps(rules))
            return 0
        if not rules:
            print('otp\\'s local module (otp_local) has no rule')
        for x in rules:
            print('%s  %s\\n              %s - put in %s by %s' % (x['id'], x['rule'], x.get('why') or '',
                                                         time.strftime('%Y-%m-%d %H:%M', time.localtime(float(x.get('at') or 0))),
                                                         x.get('by') or '?'))
        return 0
    try:
        base = json.loads(want or '{}')
    except ValueError:
        base = {}
    base['by'] = cli_who()
    if args.selinux_take_away:
        rule = next((x for x in rules if x['id'] == args.selinux_take_away), None)
        if rule is None:
            raise SystemExit('otp: otp\\'s local module has no rule %s (otp --selinux-rules)' % args.selinux_take_away)
        words = 'the rule %s taken away from otp\\'s local module: %s' % (rule['id'], rule['rule'])
        base.update(rule=rule['id'])
        do = 'rule_drop'
    else:
        found = c.get('findings') or []
        fixable = [f for f in found if f.get('kind') in ('boolean', 'label', 'port', 'rule') and f.get('fix')]
        ids = [f['id'] for f in fixable] if args.selinux_fix == ['all'] else args.selinux_fix
        pick = [f for f in fixable if f['id'] in ids]
        other = [i for i in ids if i not in [f['id'] for f in pick]]
        for i in other:
            f = next((x for x in found if x['id'] == i), None)
            print(pal.warn_line('%s: %s' % (i, (f.get('why') or f.get('kind')) if f else 'not refused here (otp --selinux-check lists the ids)')))
        if not pick:
            print('nothing to put right')
            return 1 if other else 0
        print('root does exactly this - nothing else:')
        for f in pick:
            print('  %s  %s\\n      %s: %s -> %s %s { %s }' % (f['id'], f['fix']['cmd'], f.get('program') or '?', f['source'],
                                                         f['target'], f['class'], ' '.join(f['perms'])))
        words = '%d thing(s) put right' % len(pick)
        base.update(ids=[f['id'] for f in pick])
        do = 'fix'
    if not args.yes:
        if not sys.stdin.isatty():
            raise SystemExit('otp: %s - add --yes to do it without a terminal' % words)
        if input('%s. Go on? [y/N] ' % words).strip().lower() not in ('y', 'yes'):
            print('nothing done')
            return 1
    got = _selinux_helper(['--selinux-do', do] + (['--json'] if args.json else []), json.dumps(base))
    sys.stdout.write(got.stdout)
    sys.stderr.write(got.stderr)
    return got.returncode


CLI_STARTED_ROOT = os.geteuid() == 0"""),
])
print('ok')
