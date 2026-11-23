"""1.0.321 (parts): a local user taken away and a new balancer key only with --yes or at a terminal;
--api refuses what streams a file and reads the query as the pages do; a directory's certificate
check put back on; the console's port follows a new way of reaching a directory; --local-user's help
names aging."""
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
("""            if sys.stdin.isatty() and input('take %s away on %s%s? type yes: ' % (
                    name, ', '.join(nodes), ' with the home folder' if f['home'] else '')).strip() != 'yes':
                print('nothing done')
                return 1
""",
 """            # As every step that takes something away (1.0.321): from a script without --yes it
            # went ahead unasked, and at a terminal --yes was asked all the same.
            cli_sure(args, 'take %s away on %s%s' % (name, ', '.join(nodes),
                                                      ' with the home folder' if f['home'] else ''))
"""),
("""        if not args.yes and sys.stdin.isatty():
            got = input('a new key: the one the balancer sends now is no longer taken. Go on? [y/N] ')
            if got.strip().lower() not in ('y', 'yes'):
                print('nothing changed')
                return 1
""",
 """        # Not from a script without --yes (1.0.321): the balancer was shut out unasked.
        cli_sure(args, 'a new key: the one the balancer sends now is no longer taken')
"""),
("""    def session(self, kind='admin'):
        return self.me()


def cli_api(daemon, who, method, path, body=None, args=None):
""",
 """    def session(self, kind='admin'):
        return self.me()

    # A file sent or taken (1.0.321): no socket here - a traceback, not words.
    def _no_file(self, *a, **k):
        raise ApiError(400, 'that one sends or takes a file - from the pages only')

    send_file = send_bytes = _send_open_file = body_to_file = _no_file


def cli_api(daemon, who, method, path, body=None, args=None):
"""),
("""        qs = dict(x.split('=', 1) if '=' in x else (x, '') for x in query.split('&') if x)
""",
 """        # As the pages read it (1.0.321): %20 and + undone, empty values left out.
        qs = {k: v[-1] for k, v in urllib.parse.parse_qs(query).items()}
"""),
("""                'verify': 0 if args.no_verify else old.get('verify', 1),
""",
 """                # Back on too (1.0.321): --no-verify once, and nothing here put it back.
                'verify': 0 if args.no_verify else (int(args.dir_cert_check == 'on') if args.dir_cert_check
                                                     else old.get('verify', 1)),
"""),
("""    g.add_argument('--no-verify', action='store_true', help='do not check its certificate')
""",
 """    g.add_argument('--no-verify', action='store_true', help='do not check its certificate')
    g.add_argument('--dir-cert-check', choices=('on', 'off'),
                   help='check its certificate (on, as when added) or not (off, as --no-verify)')
"""),
("""                        'sudo-on, sudo-off, drop or drop-home - a password is asked, never given on '
                        'the command line')
""",
 """                        'sudo-on, sudo-off, drop, drop-home or aging (with --local-max-days, '
                        '--local-min-days, --local-warn-days) - a password is asked, never given on '
                        'the command line')
"""),
])

edit('96_console.py', [
("""            {'key': 'port', 'label': 'port', 'value': str(r.get('port') or ''), 'help': 'Empty: as reached by says.'}])
        if not got:
            return
        args = ['--add-directory', got.get('name') or r['name'], '--hosts', got['hosts'], '--base', got['base'],
                '--bind-dn', got['bind_dn'], '--tls', got['tls']] + (['--port', got['port']] if got['port'] else [])
""",
 """            {'key': 'port', 'label': 'port', 'value': str(r.get('port') or ''), 'help': 'Empty: as reached by says.'},
            {'key': 'verify', 'label': 'its certificate', 'kind': 'choice',
             'value': 'on' if r.get('verify', 1) else 'off',
             'options': [('on', 'checked'), ('off', 'not checked')]}])
        if not got:
            return
        port = got['port']
        was_tls = r.get('tls') or 'ldaps'
        if r.get('name') and got['tls'] != was_tls and \\
                port == {'ldaps': '636'}.get(was_tls, '389'):
            port = ''       # the old way's own port left as it was: the new way's (1.0.321)
        args = ['--add-directory', got.get('name') or r['name'], '--hosts', got['hosts'], '--base', got['base'],
                '--bind-dn', got['bind_dn'], '--tls', got['tls']] + (['--port', port] if port else []) + \\
            ['--dir-cert-check', got.get('verify') or 'on']
"""),
])
