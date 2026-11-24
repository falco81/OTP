"""1.0.329 (parts): otp --del-user asks before anything is changed - a full administrator
was switched off when the question was answered no."""
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
("""                raise ValueError('that is the last full administrator who can sign in')
            if (flag in ('del_user', 'disable_user') or (flag == 'set_role' and args.role != 'fulladmin')) \\
                    and acc.get('role') == 'fulladmin' and not (flag == 'set_role' and acc.get('source') == 'directory'):
""",
 """                raise ValueError('that is the last full administrator who can sign in')
            if flag == 'del_user':
                # Asked before anything is changed (1.0.329): a full administrator was switched off
                # by the recount below, then the answer was no - "nothing was changed" said.
                cli_sure(args, 'the account %s is removed' % acc['name'])
            if (flag in ('del_user', 'disable_user') or (flag == 'set_role' and args.role != 'fulladmin')) \\
                    and acc.get('role') == 'fulladmin' and not (flag == 'set_role' and acc.get('source') == 'directory'):
"""),
("""            elif flag == 'del_user':
                cli_sure(args, 'the account %s is removed' % acc['name'])
                store.drop_account(name)
""",
 """            elif flag == 'del_user':
                store.drop_account(name)
"""),
])
