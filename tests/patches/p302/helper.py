# 1.0.302: SELinux - only otp's and the services' it works with may become a fix; restorecon only on
# otp's own real paths; otp_local's list written only once the policy took it; a batch's other fixes
# kept when the module does not load; a port of the right type already is done.   python3 helper.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/deploy/otp_web.py'


def edit(pairs):
    s = open(F).read()
    for a, b in pairs:
        assert s.count(a) == 1, (s.count(a), a[:90])
        s = s.replace(a, b)
    open(F, 'w').write(s)


edit([
("""    title = (g.get('proctitle') or '') + ' ' + (g.get('exe') or '')
    mine_proc = 'otp.py' in title or (g.get('exe') or '').startswith(SE_LIB + '/') or \\
        (g.get('program') or '').startswith('otp')""",
 """    # Which program it was, by what it cannot choose for itself (1.0.302): its executable under otp's
    # folder, or otp's own command line in full - never its name (comm), which any process sets.
    title = g.get('proctitle') or ''
    mine_proc = (g.get('exe') or '').startswith(SE_LIB + '/') or \\
        bool(re.search(r'(?:^|\\s)%s/otp\\.py(?:\\s|$)' % re.escape(SE_LIB), title))"""),
("""    if st in SE_DOMAINS:
        return 'otp' if (_se_otp_path(g['path']) or otp_port or mine_proc) else 'near'
    return 'otp' if (_se_otp_path(g['path']) or mine_proc) else 'other'""",
 """    if st in SE_DOMAINS:
        return 'otp' if (_se_otp_path(g['path']) or otp_port or mine_proc) else 'near'
    # Any other domain is another program's (1.0.302), on otp's files too: a rule for it would let
    # that program reach them (a user_t reading the API token) - shown, never put right here.
    return 'other'"""),
("""            label_want = None
            if g['path'] and _se_otp_path(g['path']) and os.path.lexists(g['path']):""",
 """            label_want = None
            # Only a real path of otp's own (1.0.302): the path is what the program asked for - with
            # "..", or through a link, restorecon -R went wherever it led.
            if g['path'] and se_plain_otp_path(g['path']):"""),
("""def se_rule_text(g):""",
 """def se_plain_otp_path(p):
    \"\"\"`p` is one of otp's own paths as it is - absolute, no "..", no link on the way.\"\"\"
    if not p or not p.startswith('/') or '/../' in p + '/' or '/./' in p + '/' or '//' in p:
        return False
    try:
        return os.path.realpath(p) == p.rstrip('/') and _se_otp_path(p) and os.path.lexists(p)
    except (OSError, ValueError):
        return False


def se_rule_text(g):"""),
("""        elif f['kind'] == 'label':
            if not os.path.lexists(fx['restorecon']):""",
 """        elif f['kind'] == 'label':
            if not se_plain_otp_path(fx['restorecon']):
                said.append('%s: %s is not one of otp\\'s own folders as it is (a link, "..") - not labelled'
                            % (i, fx['restorecon']))
                continue
            if not os.path.lexists(fx['restorecon']):"""),
("""            got = _se_run(['semanage', 'port', '-a', '-t', fx['type'], '-p', fx['proto'], str(fx['port'])], 300)
            if got is not None and got.returncode != 0 and 'already defined' in (got.stderr or ''):""",
 """            if se_port_has(se_ports(), fx['type'], fx['proto'], fx['port']):
                # The type it needs already (1.0.302): put in before, by hand or a batch whose module
                # did not load - done, not "another service's".
                said.append('port %d/%s is %s already' % (fx['port'], fx['proto'], fx['type']))
                fixed[i] = {'at': now, 'by': by, 'how': how, 'kind': f['kind']}
                continue
            got = _se_run(['semanage', 'port', '-a', '-t', fx['type'], '-p', fx['proto'], str(fx['port'])], 300)
            if got is not None and got.returncode != 0 and 'already defined' in (got.stderr or ''):"""),
("""    if new_rules:
        try:
            se_local_load(rules, said)
        except Refused:
            # Not loaded: none of the new rules counts as put right.
            for x in rules:
                if x.get('at') == now:
                    fixed.pop(x['id'], None)
            root_state_write(SE_LOCAL_RULES, json.dumps([x for x in rules if x.get('at') != now]))
            raise""",
 """    if new_rules:
        try:
            se_local_load(rules, said)
        except Refused:
            # Not loaded: none of the new rules counts as put right - the booleans, labels and ports
            # of the same batch were, and are kept as such (1.0.302).
            for x in rules:
                if x.get('at') == now:
                    fixed.pop(x['id'], None)
            root_state_write(SE_FIXED, json.dumps({k: v for k, v in fixed.items() if isinstance(v, dict)}))
            raise"""),
("""def se_local_load(rules, said):
    \"\"\"otp_local written from its list and put into the policy - or taken out with the last.\"\"\"
    root_state_write(SE_LOCAL_RULES, json.dumps(rules))
    if not rules:
        if se_local_in():
            got = _se_run(['semodule', '-r', SE_LOCAL], 300)
            if got is None or got.returncode != 0:
                raise Refused('semodule -r %s: %s' % (SE_LOCAL, ((got.stderr or '') if got else '').strip()[-200:]))
            said.append('otp\\'s local module (%s) taken out of the policy - no rule left in it' % SE_LOCAL)
        for p in (SE_LOCAL_CIL, SE_LOCAL_CIL + '.in-policy'):
            try:
                os.unlink(p)
            except OSError:
                pass
        return
    text = se_local_text(rules)
    _put_file(SE_LOCAL_CIL, text)
    got = _se_run(['semodule', '-i', SE_LOCAL_CIL], 300)
    if got is None or got.returncode != 0:
        raise Refused('semodule -i %s: %s' % (SE_LOCAL_CIL, ((got.stderr or got.stdout) if got else
                                                            'semodule is not on this machine').strip()[-300:]))
    try:
        _put_file(SE_LOCAL_CIL + '.in-policy', text)
    except (OSError, Refused):
        pass""",
 """def se_local_load(rules, said):
    \"\"\"otp_local written from its list and put into the policy - or taken out with the last. The list
    is written only once the policy took it (1.0.302): a semodule that failed (its store locked by
    dnf) left a rule in the policy that the card no longer listed, nor could take away.\"\"\"
    if not rules:
        if se_local_in():
            got = _se_run(['semodule', '-r', SE_LOCAL], 300)
            if got is None or got.returncode != 0:
                raise Refused('semodule -r %s: %s' % (SE_LOCAL, ((got.stderr or '') if got else '').strip()[-200:]))
            said.append('otp\\'s local module (%s) taken out of the policy - no rule left in it' % SE_LOCAL)
        root_state_write(SE_LOCAL_RULES, json.dumps(rules))
        for p in (SE_LOCAL_CIL, SE_LOCAL_CIL + '.in-policy'):
            try:
                os.unlink(p)
            except OSError:
                pass
        return
    text = se_local_text(rules)
    was = _read_or(SE_LOCAL_CIL)
    _put_file(SE_LOCAL_CIL, text)
    got = _se_run(['semodule', '-i', SE_LOCAL_CIL], 300)
    if got is None or got.returncode != 0:
        # The file as it was, as the policy has it.
        try:
            if was is None:
                os.unlink(SE_LOCAL_CIL)
            else:
                _put_file(SE_LOCAL_CIL, was)
        except (OSError, Refused):
            pass
        raise Refused('semodule -i %s: %s' % (SE_LOCAL_CIL, ((got.stderr or got.stdout) if got else
                                                            'semodule is not on this machine').strip()[-300:]))
    root_state_write(SE_LOCAL_RULES, json.dumps(rules))
    try:
        _put_file(SE_LOCAL_CIL + '.in-policy', text)
    except (OSError, Refused):
        pass"""),
    ("""                taken = [t for (t, pr), spans in known_ports.items()
                         if pr == proto and t not in SE_FREE_PORT_TYPES and any(lo <= int(n) <= hi for lo, hi in spans)]
                if taken:""",
     """                taken = [t for (t, pr), spans in known_ports.items()
                         if pr == proto and t not in SE_FREE_PORT_TYPES and any(lo <= int(n) <= hi for lo, hi in spans)]
                if port_type in taken:
                    # The type it needs since (1.0.302): settled - not "another service's".
                    f['kind'] = 'allowed'
                    out.append(f)
                    continue
                if taken:"""),
])
print('ok')
