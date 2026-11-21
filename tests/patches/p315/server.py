"""1.0.315 (parts): the alerts, the outgoing mail and the sign-ins of the pages on the command line and
in the console; an option that only goes with another, given alone where no one types, no longer
starts the daemon in the foreground."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('95_cli.py', [
# ---- the options
("""    g.add_argument('--lockouts-clear', metavar='all|KIND:WHO', help='forget a lockout (the KIND '
                   'and WHO --lockouts shows), or every one, on every node')
""",
 """    g.add_argument('--lockouts-clear', metavar='all|KIND:WHO', help='forget a lockout (the KIND '
                   'and WHO --lockouts shows), or every one, on every node')
    g.add_argument('--alerts', nargs='?', const='show', choices=('show', 'check', 'test', 'report',
                                                                 'forget'),
                   help='what is wrong now, as Settings - Alerts (exit 1 when anything is bad); '
                        'check: looked at again now; test: a test alert mailed; report: the last '
                        'period\\'s report mailed; forget: what was sent forgotten')
    g.add_argument('--mailq', nargs='?', const='all', choices=('all', 'open', 'waiting', 'sending',
                                                               'sent', 'failed', 'expired',
                                                               'retry-all', 'drop-sent', 'drop-failed'),
                   help='the outgoing mail (all, or only one state); retry-all: what waits or '
                        'failed sent again now; drop-sent, drop-failed: taken out')
    g.add_argument('--mailq-one', metavar='ID', help='one mail of the outgoing mail, every try of it')
    g.add_argument('--mailq-retry', metavar='ID,ID', help='these mails sent again now')
    g.add_argument('--mailq-drop', metavar='ID,ID', help='these mails taken out of the outgoing mail')
    g.add_argument('--sessions', action='store_true', help='who is signed in to the pages (the '
                   'administration and the enrolment pages)')
    g.add_argument('--session-end', type=int, metavar='ID', help='end that sign-in (the ID '
                   '--sessions shows)')
"""),
# ---- the run
("""    only = args.node or ''
    if args.siem_test:
""",
 """    # ---- 1.0.315: the alerts, the outgoing mail and the sign-ins, as the pages show them -----
    if args.alerts:
        if args.alerts == 'show':
            got = api('GET', '/api/alerts')
        else:
            got = api('POST', '/api/alerts', {'action': args.alerts, 'period': 'last'})
        if args.json:
            out(got)
            return 1 if args.alerts in ('show', 'check') and any(
                p.get('level') == 'bad' for p in got.get('problems') or []) else 0
        if got.get('message'):
            print(pal.ok_line(got['message']))
        probs = got.get('problems') or []
        if not probs:
            print(pal.ok_line('nothing is wrong now'))
        else:
            print(table([(tone_cell(p.get('level') or '', pal), p.get('node') or '',
                          p.get('title') or '', stamp(p['since']) if p.get('since') else '',
                          'yes' if p.get('sent') else 'no') for p in probs],
                        ['level', 'node', 'what', 'since', 'mailed'], [6, 10, 50, 19, 6]))
            for p in probs:
                if p.get('said'):
                    # Wrapped (the console's window cuts a line at its edge).
                    print(pal.dim('\\n'.join(textwrap.wrap('%s: %s' % (p.get('title') or p.get('key'), p['said']),
                                                          94, initial_indent='  ', subsequent_indent='    '))))
        if not got.get('mail'):
            print(pal.dim('  sending mail is switched off (Settings - Mail): no alert is mailed'))
        elif not got.get('to'):
            print(pal.dim('  no address to send them to (otp --set alerts_to=ADDRESS)'))
        else:
            print(pal.dim('  mailed to %s%s' % (', '.join(got['to']), '' if got.get('lead') else
                                                ' - by the other node, not this one')))
        if got.get('checked'):
            print(pal.dim('  looked at %s' % stamp(got['checked'])))
        return 1 if args.alerts in ('show', 'check') and any(
            p.get('level') == 'bad' for p in probs) else 0
    if args.mailq or args.mailq_retry or args.mailq_drop:
        if args.mailq in ('retry-all', 'drop-sent', 'drop-failed') or args.mailq_retry or args.mailq_drop:
            ids = [x.strip() for x in (args.mailq_retry or args.mailq_drop or '').split(',') if x.strip()]
            act = (args.mailq or '').replace('-', '_') if not ids else (
                'retry' if args.mailq_retry else 'drop')
            if act.startswith('drop'):
                cli_sure(args, '%s taken out of the outgoing mail' % (
                    ', '.join(ids) if ids else {'drop_sent': 'the mail sent',
                                                'drop_failed': 'the mail that failed or expired'}[act]))
            got = api('POST', '/api/mailq', {'action': act, 'ids': ids})
            if args.json:
                out(got)
            else:
                print(pal.ok_line(got.get('message') or 'done'))
            return 0
        got = api('GET', '/api/mailq', None, {'state': '' if args.mailq == 'all' else args.mailq,
                                              'q': args.search or '', 'limit': str(args.limit)})
        if args.json:
            out(got)
            return 0
        print(table([(r.get('qid') or '', stamp(r['created']) if r.get('created') else '',
                      r.get('state') or '', str(r.get('tries') or 0), ', '.join(r.get('to') or [])
                      if isinstance(r.get('to'), list) else str(r.get('to') or ''),
                      r.get('subject') or r.get('kind_words') or '', r.get('said') or '')
                     for r in got.get('rows') or []],
                    ['id', 'made', 'state', 'tries', 'to', 'subject', 'said'],
                    [22, 19, 8, 5, 26, 34, 30]))
        print(pal.dim('  %d shown of %d - %s; sending is %s' % (
            len(got.get('rows') or []), got.get('total') or 0,
            ', '.join('%s %d' % (k, v) for k, v in sorted(odict(got.get('counts')).items()) if v)
            or 'none at all', got.get('mode') or 'off')))
        return 0
    if args.mailq_one:
        got = api('GET', '/api/mailq/one', None, {'id': args.mailq_one})
        return shown(got)
    if args.sessions or args.session_end is not None:
        if args.session_end is not None:
            cli_sure(args, 'the sign-in %d is ended - whoever it is must sign in again'
                     % args.session_end)
            got = api('POST', '/api/sessions', {'id': args.session_end})
            if args.json:
                out(got)
            else:
                print(pal.ok_line('ended'))
            return 0
        rows = api('GET', '/api/sessions').get('sessions') or []
        if args.json:
            out(rows)
            return 0
        if not rows:
            print(pal.ok_line('nobody is signed in to the pages'))
            return 0
        print(table([(str(r.get('id')), r.get('kind') or '', r.get('name') or '', r.get('role') or '',
                      r.get('ip') or '', stamp(r['created']) if r.get('created') else '',
                      stamp(r['last']) if r.get('last') else '') for r in rows],
                    ['id', 'kind', 'name', 'role', 'from', 'signed in', 'last asked'],
                    [6, 7, 24, 11, 20, 19, 19]))
        return 0

    only = args.node or ''
    if args.siem_test:
"""),
# ---- an option alone, where no one types
("""        if os.environ.get('INVOCATION_ID') or not sys.stdin.isatty():
            return run_daemon()
""",
 """        # Only `otp` itself (1.0.315): `otp --pending` or `otp --yes` from a script or cron - an
        # option that goes with another, nothing asked - started a second daemon in the foreground
        # there and hung. The service is started as `otp --daemon`.
        if os.environ.get('INVOCATION_ID') or not sys.stdin.isatty():
            alone = [a for a in parser._actions if a.option_strings and a.dest not in (
                'no_color', 'json', 'debug', 'config') and getattr(args, a.dest, None) != a.default]
            if alone:
                print('otp: %s alone asks nothing - otp --help says what it goes with'
                      % ', '.join(a.option_strings[0] for a in alone), file=sys.stderr)
                return 2
            return run_daemon()
"""),
])

edit('88z_alerts.py', [
("""                    str(words.get('why') or it.get('why') or '')[:300], 'upgrade')
""",
 """                    _al_cut(str(words.get('why') or it.get('why') or ''), 600), 'upgrade')
"""),
("""REPL_ERRS_FOR_S = 1800
""",
 """REPL_ERRS_FOR_S = 1800


def _al_cut(text, most):
    \"\"\"Words no longer than most, cut where a word ends and said so (1.0.315): what an update left
    to be done by hand went out cut in the middle of a word - '... Firewall and ac'.\"\"\"
    text = str(text or '')
    if len(text) <= most:
        return text
    cut = text[:most - 1]
    if ' ' in cut[most // 2:]:
        cut = cut[:cut.rindex(' ')]
    return cut.rstrip(' ,;:-') + '…'
"""),
])

edit('96_console.py', [
("""            ('20', 'The password policy of local users: how it stands', lambda: self.act('--local-policy')),
            ('21', 'Set the password policy of local users', pwp_set),
        ])
""",
 """            ('20', 'The password policy of local users: how it stands', lambda: self.act('--local-policy')),
            ('21', 'Set the password policy of local users', pwp_set),
            ('22', 'Alerts: what is wrong now', lambda: self.act('--alerts')),
            ('23', 'Send a test alert', lambda: self.act('--alerts', 'test')),
            ('24', 'Outgoing mail', mailq),
            ('25', 'Who is signed in to the pages', lambda: self.act('--sessions')),
            ('26', 'End a sign-in to the pages', session_end),
        ])
"""),
("""        def lockout_clear():
""",
 """        def mailq():
            # The outgoing mail (1.0.315): as Settings - Mail - Outgoing mail.
            which = self.choose('Outgoing mail', [
                ('open', 'What waits or failed'), ('all', 'All of it'),
                ('retry-all', 'Send what waits or failed again now'),
                ('drop-sent', 'Take the mail sent out of the list'),
                ('drop-failed', 'Take the mail that failed or expired out of the list')])
            if which in ('open', 'all'):
                self.act('--mailq', which)
            elif which == 'retry-all':
                self.act('--mailq', which)
            elif which and self.confirm('Outgoing mail', {
                    'drop-sent': 'The mail sent is taken out of the list.',
                    'drop-failed': 'The mail that failed or expired is taken out of the list; '
                                   'it is not sent.'}[which], 'Take it out', danger=True):
                self.act('--mailq', which, '--yes')

        def session_end():
            rows = [r for r in (self.out('--sessions') or []) if isinstance(r, dict)]
            if not rows:
                self.note('Sign-ins', 'Nobody is signed in to the pages.')
                return
            which = self.choose('End a sign-in to the pages', [
                (str(r.get('id')), '%s (%s, %s) from %s' % (r.get('name') or '?', r.get('kind') or '',
                                                            r.get('role') or '-', r.get('ip') or '?'))
                for r in rows])
            if which is not None and self.confirm('End the sign-in', 'Whoever it is must sign in '
                                                  'again.', 'End it', danger=True):
                self.act('--session-end', which, '--yes')

        def lockout_clear():
"""),
])

# ---- the firewall and who may reach the pages, from the command line: the way back in when the
# pages shut the one who set them out
edit('95_cli.py', [
("""    g.add_argument('--sessions', action='store_true', help='who is signed in to the pages (the '
""",
 """    g.add_argument('--firewall', nargs='?', const='show', choices=('show', 'on', 'off'),
                   help='otp\\'s firewall and who may reach the pages, as Settings - Firewall and '
                        'access; on / off: otp\\'s rules put in or taken away on every node (the '
                        'rest of the firewall stays as it was)')
    g.add_argument('--web-access', action='append', metavar='KIND=any|NET,NET',
                   help='who may reach the pages (KIND: admin, portal, health), on every node; '
                        'the others stay as they are. On trial as on the pages: --change-keep fw')
    g.add_argument('--sessions', action='store_true', help='who is signed in to the pages (the '
"""),
("""    if args.sessions or args.session_end is not None:
""",
 """    if args.firewall or args.web_access:
        got = api('GET', '/api/firewall')
        acc = {k: {'any': bool(odict(v).get('any')), 'from': list(odict(v).get('from') or [])}
               for k, v in odict(got.get('access')).items() if k in ACCESS_WORDS}
        for k in ACCESS_WORDS:
            # Not set and nothing read from nginx: nobody is kept out, as nginx has it.
            one = acc.setdefault(k, {'any': True, 'from': []})
            if not one['any'] and not one['from']:
                one['any'] = True
        if args.web_access:
            for w in args.web_access:
                kind, eq, val = str(w).partition('=')
                kind = kind.strip().lower()
                if not eq or kind not in ACCESS_WORDS or not val.strip():
                    raise SystemExit('otp: --web-access KIND=any or KIND=NET,NET - KIND one of %s'
                                     % ', '.join(ACCESS_WORDS))
                acc[kind] = ({'any': True, 'from': []} if val.strip().lower() == 'any' else
                             {'any': False, 'from': [x for x in re.split(r'[\\s,;]+', val) if x]})
            for k in ACCESS_WORDS:
                acc.setdefault(k, {'any': True, 'from': []})
            cli_sure(args, 'who may reach the pages, on every node: %s' % '; '.join(
                '%s %s' % (k, 'everybody' if v['any'] else ', '.join(v['from'])) for k, v in acc.items()))
            said = api('POST', '/api/firewall', dict(acc, action='access'))
            if args.json:
                out(said)
                return 0
            print(pal.ok_line(said.get('message') or 'kept'))
            if fw_trial_min():
                print(pal.dim('  on trial: it goes back by itself in %d min - otp --change-keep fw '
                              'keeps it, otp --change-back fw puts it back now' % fw_trial_min()))
            return 0
        if args.firewall in ('on', 'off'):
            if args.firewall == 'off':
                cli_sure(args, 'otp\\'s firewall rules are taken away on every node (the rest of the '
                               'firewall stays as it was)')
            said = api('POST', '/api/firewall', {'action': args.firewall})
            if args.json:
                out(said)
            else:
                print(pal.ok_line(said.get('message') or 'kept'))
            return 0
        if args.json:
            out(got)
            return 0
        conf = got.get('conf') or {}
        print(pal.ok_line('otp\\'s firewall rules: on (%d of your own)' % len(conf.get('rules') or []))
              if conf.get('on') else pal.dim('  otp\\'s firewall rules: off - the machine\\'s own '
                                             'firewall as it is (otp --firewall on)'))
        if conf.get('off'):
            print(pal.dim('  its own rules turned off: %s' % ', '.join(conf['off'])))
        for r in conf.get('rules') or []:
            print('    %-6s %-4s %-14s %-22s %s%s' % (r.get('action') or '', r.get('proto') or '',
                                                  r.get('port') or 'any', r.get('source') or 'anywhere',
                                                  r.get('note') or '', ' (off)' if r.get('disabled') else ''))
        for k, words in ACCESS_WORDS.items():
            v = acc.get(k) or {'any': True}
            print('  %-42s %s' % (words + ':', 'everybody' if v.get('any') else ', '.join(v.get('from') or [])))
        return 0
    if args.sessions or args.session_end is not None:
"""),
])

edit('96_console.py', [
("""            ('26', 'End a sign-in to the pages', session_end),
        ])
""",
 """            ('26', 'End a sign-in to the pages', session_end),
            ('27', 'Firewall and who may reach the pages', lambda: self.act('--firewall')),
            ('28', 'Let everybody reach the administration pages', web_open),
            ('29', 'Take otp\\'s firewall rules away', fw_off),
        ])
"""),
("""        def session_end():
""",
 """        def web_open():
            # The way back in (1.0.315): the pages shut the one who set them out.
            if self.confirm('Let everybody reach the administration pages', 'On every node, from '
                            'any address - the sign-in still asked. On trial as on the pages: keep '
                            'it with otp --change-keep fw.', 'Let them in', danger=True):
                self.act('--web-access', 'admin=any', '--yes')

        def fw_off():
            if self.confirm('Take otp\\'s firewall rules away', 'On every node; the rest of the '
                            'machine\\'s firewall stays as it was.', 'Take them away', danger=True):
                self.act('--firewall', 'off', '--yes')

        def session_end():
"""),
])
